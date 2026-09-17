"""
Catalog loader — turns the per-table YAML metadata into typed Python objects.

The catalog is the single source of truth for table/column metadata. Three
consumers read it:

  * quality/   — drives integrity, enum, null, uniqueness and date-format checks
  * migrations — generates COMMENT ON COLUMN and join-key index DDL
  * (future)   — the semantic layer / Claude tools

A human owns the definitions. The YAML is first drafted from
docs/schema_reference.md, then corrected by a person.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ..config import CATALOG_DIR

# Logical types the catalog understands. Physical (DB) types are recorded
# separately in `db_type` so we can detect drift between the documented type
# and the live column type.
LOGICAL_TYPES = {
    "id",            # opaque identifier / UUID / object id
    "enum",          # constrained vocabulary (enum_values is authoritative)
    "date_string",   # date stored as text or DATE; validated against date_format
    "timestamp",     # full timestamp
    "text",          # free text
    "integer",
    "float",
    "boolean",
    "json",
}


@dataclass
class Column:
    name: str
    logical_type: str = "text"
    db_type: Optional[str] = None          # documented physical type (e.g. TEXT, DATE)
    description: str = ""
    nullable: bool = True
    is_key: bool = False                   # primary or foreign key participant
    enum_values: List[str] = field(default_factory=list)
    date_format: Optional[str] = None      # regex-style hint for date_string columns
    sample_values: List[str] = field(default_factory=list)
    # Semantic facts — used by the generator prompt and the SQL linter
    authority: bool = True                 # False = this column is a copy; query authoritative_source instead
    authoritative_source: Optional[str] = None  # "table.column" when authority=False
    partition: bool = False                # True = enum values are mutually exclusive per row (no multi-value)

    @property
    def is_enum(self) -> bool:
        return self.logical_type == "enum" and bool(self.enum_values)

    @property
    def is_date(self) -> bool:
        return self.logical_type in ("date_string", "timestamp")


@dataclass
class Join:
    """A foreign-key relationship declared on the FK-side (this) table."""
    column: str                # FK column on this table
    references_table: str      # parent table
    references_column: str     # parent key column
    description: str = ""


@dataclass
class Table:
    name: str
    description: str = ""
    grain: str = ""
    owner: str = "unassigned"
    source_csv: Optional[str] = None
    primary_key: Optional[str] = None
    columns: List[Column] = field(default_factory=list)
    joins: List[Join] = field(default_factory=list)

    def column(self, name: str) -> Optional[Column]:
        return next((c for c in self.columns if c.name == name), None)

    @property
    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]

    @property
    def enum_columns(self) -> List[Column]:
        return [c for c in self.columns if c.is_enum]

    @property
    def date_columns(self) -> List[Column]:
        return [c for c in self.columns if c.is_date and c.date_format]

    @property
    def key_columns(self) -> List[Column]:
        return [c for c in self.columns if c.is_key]


@dataclass
class IncompatiblePair:
    """Two columns whose value domains are disjoint and must never be joined or compared."""
    left: str    # "table.column"
    right: str   # "table.column"
    reason: str = ""


@dataclass
class CanonicalMetric:
    """A blessed rate/ratio formula that must be used consistently across all SQL."""
    name: str
    formula: str     # SQL-fragment showing the canonical computation
    description: str = ""


@dataclass
class NegativeFact:
    """Something that does NOT exist in the data — prevents hallucinated filters."""
    fact: str        # human-readable statement, e.g. "activity_type='onboarding_completed' does not exist"
    verified: bool = False   # True = confirmed by catalog verify-rules against live DB


@dataclass
class Catalog:
    tables: Dict[str, Table] = field(default_factory=dict)
    # Cross-table semantic constraints
    incompatible_pairs: List[IncompatiblePair] = field(default_factory=list)
    canonical_metrics: List[CanonicalMetric] = field(default_factory=list)
    negative_facts: List[NegativeFact] = field(default_factory=list)

    def get(self, name: str) -> Optional[Table]:
        return self.tables.get(name)

    def __iter__(self):
        return iter(self.tables.values())

    def __len__(self):
        return len(self.tables)

    @property
    def all_joins(self) -> List[tuple]:
        """All declared joins as (table, Join) pairs."""
        out = []
        for table in self.tables.values():
            for j in table.joins:
                out.append((table, j))
        return out


def _parse_column(raw: dict) -> Column:
    logical = raw.get("logical_type", "text")
    if logical not in LOGICAL_TYPES:
        raise ValueError(
            f"Column '{raw.get('name')}' has unknown logical_type '{logical}'. "
            f"Allowed: {sorted(LOGICAL_TYPES)}"
        )
    return Column(
        name=raw["name"],
        logical_type=logical,
        db_type=raw.get("db_type"),
        description=raw.get("description", ""),
        nullable=raw.get("nullable", True),
        is_key=raw.get("is_key", False),
        enum_values=list(raw.get("enum_values", []) or []),
        date_format=raw.get("date_format"),
        sample_values=[str(v) for v in (raw.get("sample_values", []) or [])],
        authority=raw.get("authority", True),
        authoritative_source=raw.get("authoritative_source"),
        partition=raw.get("partition", False),
    )


def _parse_table(raw: dict) -> Table:
    columns = [_parse_column(c) for c in raw.get("columns", [])]
    joins = [
        Join(
            column=j["column"],
            references_table=j["references_table"],
            references_column=j["references_column"],
            description=j.get("description", ""),
        )
        for j in raw.get("joins", [])
    ]
    return Table(
        name=raw["name"],
        description=raw.get("description", ""),
        grain=raw.get("grain", ""),
        owner=raw.get("owner", "unassigned"),
        source_csv=raw.get("source_csv"),
        primary_key=raw.get("primary_key"),
        columns=columns,
        joins=joins,
    )


def _load_semantic(directory: Path, catalog: Catalog) -> None:
    """Load optional semantic.yaml from the catalog directory into the catalog."""
    sem_path = directory / "semantic.yaml"
    if not sem_path.exists():
        return
    with open(sem_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    for item in raw.get("incompatible_pairs", []):
        catalog.incompatible_pairs.append(
            IncompatiblePair(
                left=item["left"],
                right=item["right"],
                reason=item.get("reason", ""),
            )
        )

    for item in raw.get("canonical_metrics", []):
        catalog.canonical_metrics.append(
            CanonicalMetric(
                name=item["name"],
                formula=item["formula"],
                description=item.get("description", ""),
            )
        )

    for item in raw.get("negative_facts", []):
        catalog.negative_facts.append(
            NegativeFact(
                fact=item["fact"],
                verified=item.get("verified", False),
            )
        )


def load_catalog(catalog_dir: Optional[Path] = None) -> Catalog:
    """Load and validate every table YAML under the catalog directory."""
    directory = Path(catalog_dir) if catalog_dir else CATALOG_DIR
    if not directory.exists():
        raise FileNotFoundError(f"Catalog directory not found: {directory}")

    catalog = Catalog()
    for path in sorted(directory.glob("*.yaml")):
        if path.name == "semantic.yaml":
            continue  # loaded separately after tables
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not raw or "name" not in raw:
            raise ValueError(f"{path.name}: missing required 'name' field")
        table = _parse_table(raw)
        catalog.tables[table.name] = table

    # Load cross-table semantic constraints
    _load_semantic(directory, catalog)

    # Validate join targets resolve within the catalog.
    for table, join in catalog.all_joins:
        parent = catalog.get(join.references_table)
        if parent is None:
            raise ValueError(
                f"{table.name}: join references unknown table "
                f"'{join.references_table}'"
            )
        if parent.column(join.references_column) is None:
            raise ValueError(
                f"{table.name}: join references unknown column "
                f"'{join.references_table}.{join.references_column}'"
            )
    return catalog
