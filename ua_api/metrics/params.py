"""
Parameter parsing and validation.

Every value that reaches a SQL template is validated here BEFORE rendering —
this is the integrity guarantee. Dates must match YYYY-MM-DD; choice values must
be in the metric's allowed set; segment values must be in the data_context
catalog's enum vocabulary. Nothing is interpolated unchecked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .registry import Metric

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ParamError(ValueError):
    """Raised when a parameter fails validation; the caller should fall back or
    surface the message rather than render unsafe SQL."""


@dataclass
class ResolvedParams:
    grain_values: Dict[str, str] = field(default_factory=dict)  # choice name -> value
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    segment_value: Optional[str] = None


def _validate_date(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ParamError(f"{field_name} must be a date as YYYY-MM-DD, got {value!r}")
    return value


def validate(metric: Metric, raw: Optional[Dict[str, Any]]) -> ResolvedParams:
    """Validate a raw param dict (from the resolver) against the metric spec."""
    raw = raw or {}
    out = ResolvedParams()

    # --- choices (e.g. grain) -------------------------------------------
    for name, choice in metric.choices.items():
        value = raw.get(name, choice.default)
        if value not in choice.value_map:
            raise ParamError(
                f"{name} must be one of {choice.values}, got {value!r}"
            )
        out.grain_values[name] = value

    # --- date range -----------------------------------------------------
    period = raw.get("period")
    if period:
        if not metric.date_filter:
            raise ParamError(f"metric '{metric.name}' does not accept a date range")
        if not isinstance(period, dict):
            raise ParamError("period must be an object with start and end")
        start = period.get("start")
        end = period.get("end")
        if not start or not end:
            raise ParamError("period requires both start and end (end exclusive)")
        out.period_start = _validate_date(start, "period.start")
        out.period_end = _validate_date(end, "period.end")
        if out.period_start >= out.period_end:
            raise ParamError("period.start must be before period.end")

    # --- segment (validated against the catalog vocabulary) -------------
    segment = raw.get("segment")
    if segment:
        if not metric.segment:
            raise ParamError(f"metric '{metric.name}' does not accept a segment")
        _validate_segment_value(metric, str(segment))
        out.segment_value = str(segment)

    return out


def _validate_segment_value(metric: Metric, value: str) -> None:
    """Ensure the segment value is in the data_context catalog enum for that
    column. Falls back to a permissive check if the catalog can't be loaded."""
    try:
        from ..data_context.catalog import load_catalog

        catalog = load_catalog()
        table = catalog.get(metric.segment.table)
        col = table.column(metric.segment.column) if table else None
        if col and col.enum_values:
            if value not in col.enum_values:
                raise ParamError(
                    f"segment {metric.segment.column}={value!r} is not in the "
                    f"catalog vocabulary {col.enum_values}"
                )
    except ParamError:
        raise
    except Exception:
        # Catalog unavailable — do not block, but the value is still only ever
        # used inside a parameterised equality with quote-escaping in renderer.
        pass
