"""
Metric registry — loads certified metric YAML definitions into typed objects.
Self-contained; no imports from ua_api/ or chat_api/.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFINITIONS_DIR = Path(__file__).resolve().parent / "metrics"


@dataclass
class Choice:
    name: str
    default: str
    value_map: Dict[str, Dict[str, str]]

    @property
    def values(self) -> List[str]:
        return list(self.value_map.keys())


@dataclass
class DateFilter:
    column: str


@dataclass
class Segment:
    column: str
    table: str


@dataclass
class Metric:
    name: str
    description: str
    sql_template: str
    aliases: List[str] = field(default_factory=list)
    owner: str = "analytics-team"
    certified: bool = False
    source: Optional[str] = None
    response_type: str = "table"
    label_column: Optional[str] = None
    value_column: Optional[str] = None
    date_filter: Optional[DateFilter] = None
    choices: Dict[str, Choice] = field(default_factory=dict)
    segment: Optional[Segment] = None

    def choice(self, name: str) -> Optional[Choice]:
        return self.choices.get(name)


@dataclass
class Registry:
    metrics: Dict[str, Metric] = field(default_factory=dict)

    def get(self, name: str) -> Optional[Metric]:
        return self.metrics.get(name)

    def __iter__(self):
        return iter(self.metrics.values())

    def __len__(self):
        return len(self.metrics)

    def catalog_for_resolver(self) -> List[dict]:
        out = []
        for m in self.metrics.values():
            params: Dict[str, Any] = {}
            if m.date_filter:
                params["period"] = "optional {start, end} as YYYY-MM-DD (end exclusive)"
            for name, ch in m.choices.items():
                params[name] = f"one of {ch.values} (default {ch.default})"
            if m.segment:
                params["segment"] = f"optional value of {m.segment.column}"
            out.append({
                "name": m.name,
                "description": m.description,
                "aliases": m.aliases,
                "parameters": params,
            })
        return out


def _parse_metric(raw: dict) -> Metric:
    choices = {}
    for name, spec in (raw.get("choices") or {}).items():
        choices[name] = Choice(
            name=name,
            default=spec["default"],
            value_map=spec["map"],
        )
    date_filter = None
    if raw.get("date_filter"):
        date_filter = DateFilter(column=raw["date_filter"]["column"])
    segment = None
    if raw.get("segment"):
        segment = Segment(column=raw["segment"]["column"], table=raw["segment"]["table"])

    returns = raw.get("returns") or {}
    return Metric(
        name=raw["name"],
        description=raw["description"],
        sql_template=raw["sql_template"],
        aliases=list(raw.get("aliases") or []),
        owner=raw.get("owner", "analytics-team"),
        certified=raw.get("certified", False),
        source=raw.get("source"),
        response_type=returns.get("response_type", "table"),
        label_column=returns.get("label"),
        value_column=returns.get("value"),
        date_filter=date_filter,
        choices=choices,
        segment=segment,
    )


def load_registry(definitions_dir: Optional[Path] = None) -> Registry:
    directory = Path(definitions_dir) if definitions_dir else DEFINITIONS_DIR
    if not directory.exists():
        raise FileNotFoundError(f"Metric definitions dir not found: {directory}")
    reg = Registry()
    for path in sorted(directory.glob("*.yaml")):
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not raw or "name" not in raw:
            continue
        metric = _parse_metric(raw)
        reg.metrics[metric.name] = metric
    return reg
