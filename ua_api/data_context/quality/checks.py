"""
Catalog-driven data-quality checks.

Every check runs as a read-only SELECT through the existing `execute_sql` RPC,
so this module never mutates the analytics schema and can be run safely at any
time against the live database.

Check families:
  * referential_integrity — orphan FK values not present in the parent key
  * enum_validation       — values outside the catalog's allowed vocabulary
  * null_keys             — NULLs in declared key columns
  * uniqueness            — duplicate primary-key values
  * date_format           — date/timestamp strings that don't match the format
  * volume                — row counts (sanity / emptiness)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from ..catalog import Catalog, Table

# How many offending sample values to capture per failing check.
SAMPLE_LIMIT = 10


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"   # data smell, not necessarily a defect (e.g. nullable orphans)
    FAIL = "FAIL"
    ERROR = "ERROR"  # the check itself could not run


@dataclass
class CheckResult:
    check: str            # family name, e.g. "referential_integrity"
    table: str
    target: str           # column / join / "table" being checked
    status: Status
    count: int = 0        # number of offending rows
    detail: str = ""
    samples: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "table": self.table,
            "target": self.target,
            "status": self.status.value,
            "count": self.count,
            "detail": self.detail,
            "samples": self.samples,
        }


def _sql_str_list(values: List[str]) -> str:
    """Render a Python list as a SQL IN (...) list with escaped single quotes."""
    escaped = [v.replace("'", "''") for v in values]
    return ", ".join(f"'{v}'" for v in escaped)


# --- Individual check families ---------------------------------------------

def check_volume(table: Table, run_sql: Callable) -> CheckResult:
    rows = run_sql(f"SELECT COUNT(*) AS n FROM {table.name}")
    n = int(rows[0]["n"]) if rows else 0
    status = Status.PASS if n > 0 else Status.FAIL
    return CheckResult(
        check="volume",
        table=table.name,
        target="table",
        status=status,
        count=n,
        detail=f"{n} rows" if n else "table is empty",
    )


def check_uniqueness(table: Table, run_sql: Callable) -> List[CheckResult]:
    if not table.primary_key:
        return []
    pk = table.primary_key
    rows = run_sql(
        f"SELECT {pk} AS v, COUNT(*) AS n FROM {table.name} "
        f"WHERE {pk} IS NOT NULL GROUP BY {pk} HAVING COUNT(*) > 1 "
        f"ORDER BY n DESC LIMIT {SAMPLE_LIMIT}"
    )
    dup_groups = len(rows)
    samples = [f"{r['v']} (x{r['n']})" for r in rows]
    status = Status.PASS if dup_groups == 0 else Status.FAIL
    return [CheckResult(
        check="uniqueness",
        table=table.name,
        target=pk,
        status=status,
        count=dup_groups,
        detail="primary key is unique" if dup_groups == 0
               else f"{dup_groups}+ duplicated primary-key values",
        samples=samples,
    )]


def check_null_keys(table: Table, run_sql: Callable) -> List[CheckResult]:
    results = []
    for col in table.key_columns:
        if col.nullable:
            continue  # only enforce NOT NULL where the catalog declares it
        rows = run_sql(
            f"SELECT COUNT(*) AS n FROM {table.name} WHERE {col.name} IS NULL"
        )
        n = int(rows[0]["n"]) if rows else 0
        results.append(CheckResult(
            check="null_keys",
            table=table.name,
            target=col.name,
            status=Status.PASS if n == 0 else Status.FAIL,
            count=n,
            detail="no nulls in key" if n == 0 else f"{n} null values in key column",
        ))
    return results


def check_enums(table: Table, run_sql: Callable) -> List[CheckResult]:
    results = []
    for col in table.enum_columns:
        allowed = _sql_str_list(col.enum_values)
        rows = run_sql(
            f"SELECT {col.name} AS v, COUNT(*) AS n FROM {table.name} "
            f"WHERE {col.name} IS NOT NULL AND {col.name} NOT IN ({allowed}) "
            f"GROUP BY {col.name} ORDER BY n DESC LIMIT {SAMPLE_LIMIT}"
        )
        bad = len(rows)
        samples = [f"{r['v']!r} (x{r['n']})" for r in rows]
        results.append(CheckResult(
            check="enum_validation",
            table=table.name,
            target=col.name,
            status=Status.PASS if bad == 0 else Status.FAIL,
            count=bad,
            detail="all values in declared vocabulary" if bad == 0
                   else f"{bad} value(s) outside the {len(col.enum_values)}-value vocabulary",
            samples=samples,
        ))
    return results


def check_date_formats(table: Table, run_sql: Callable) -> List[CheckResult]:
    results = []
    for col in table.date_columns:
        pattern = col.date_format.replace("'", "''")
        rows = run_sql(
            f"SELECT {col.name} AS v, COUNT(*) AS n FROM {table.name} "
            f"WHERE {col.name} IS NOT NULL "
            f"AND {col.name}::text !~ '{pattern}' "
            f"GROUP BY {col.name} ORDER BY n DESC LIMIT {SAMPLE_LIMIT}"
        )
        bad = len(rows)
        samples = [f"{r['v']!r} (x{r['n']})" for r in rows]
        results.append(CheckResult(
            check="date_format",
            table=table.name,
            target=col.name,
            status=Status.PASS if bad == 0 else Status.WARN,
            count=bad,
            detail="dates match expected format" if bad == 0
                   else f"{bad} distinct value(s) not matching /{col.date_format}/",
            samples=samples,
        ))
    return results


def check_referential_integrity(catalog: Catalog, run_sql: Callable) -> List[CheckResult]:
    results = []
    for table, join in catalog.all_joins:
        parent = catalog.get(join.references_table)
        fk, pk = join.column, join.references_column
        # Count distinct orphan FK values (present here, absent in parent).
        rows = run_sql(
            f"SELECT c.{fk} AS v, COUNT(*) AS n FROM {table.name} c "
            f"WHERE c.{fk} IS NOT NULL AND NOT EXISTS ("
            f"SELECT 1 FROM {parent.name} p WHERE p.{pk} = c.{fk}) "
            f"GROUP BY c.{fk} ORDER BY n DESC LIMIT {SAMPLE_LIMIT}"
        )
        orphans = len(rows)
        samples = [f"{r['v']} (x{r['n']})" for r in rows]
        results.append(CheckResult(
            check="referential_integrity",
            table=table.name,
            target=f"{fk} -> {parent.name}.{pk}",
            status=Status.PASS if orphans == 0 else Status.WARN,
            count=orphans,
            detail="all FK values resolve to a parent row" if orphans == 0
                   else f"{orphans}+ FK value(s) with no matching parent row",
            samples=samples,
        ))
    return results


# --- Orchestration ----------------------------------------------------------

def run_all_checks(
    catalog: Catalog,
    run_sql: Callable,
    only_table: Optional[str] = None,
) -> List[CheckResult]:
    """Run every check family across the catalog. Each check is isolated so one
    failure (e.g. a missing column in the live DB) does not abort the rest."""
    results: List[CheckResult] = []
    tables = [catalog.get(only_table)] if only_table else list(catalog)
    tables = [t for t in tables if t is not None]

    def _safe(fn, *args):
        try:
            out = fn(*args)
            return out if isinstance(out, list) else [out]
        except Exception as exc:  # noqa: BLE001 - surface as an ERROR result
            ctx = args[0]
            tname = ctx.name if isinstance(ctx, Table) else "<catalog>"
            return [CheckResult(
                check=getattr(fn, "__name__", "check"),
                table=tname,
                target="-",
                status=Status.ERROR,
                detail=f"check failed to run: {exc}",
            )]

    for table in tables:
        results += _safe(check_volume, table, run_sql)
        results += _safe(check_uniqueness, table, run_sql)
        results += _safe(check_null_keys, table, run_sql)
        results += _safe(check_enums, table, run_sql)
        results += _safe(check_date_formats, table, run_sql)

    # Referential integrity spans tables; run once (respect table filter).
    ri = _safe(check_referential_integrity, catalog, run_sql)
    if only_table:
        ri = [r for r in ri if r.table == only_table]
    results += ri
    return results
