"""
Parameter validation for certified metric rendering.
Validates dates, choice values, and segment strings before any SQL substitution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .registry import Metric

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9 _\-\.]+$")


class ParamError(ValueError):
    """Bad parameter — caller should fall back to sql_generator, not crash."""


@dataclass
class ResolvedParams:
    grain_values: Dict[str, str] = field(default_factory=dict)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    segment_value: Optional[str] = None


def _require_date(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ParamError(f"{field_name} must be YYYY-MM-DD, got {value!r}")
    return value


def validate(metric: Metric, raw: Optional[Dict[str, Any]]) -> ResolvedParams:
    raw = raw or {}
    out = ResolvedParams()

    for name, choice in metric.choices.items():
        value = raw.get(name, choice.default)
        if value not in choice.value_map:
            raise ParamError(f"{name} must be one of {choice.values}, got {value!r}")
        out.grain_values[name] = value

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
        out.period_start = _require_date(start, "period.start")
        out.period_end = _require_date(end, "period.end")
        if out.period_start >= out.period_end:
            raise ParamError("period.start must be before period.end")

    segment = raw.get("segment")
    if segment:
        if not metric.segment:
            raise ParamError(f"metric '{metric.name}' does not accept a segment")
        seg_str = str(segment)
        if not _SAFE_VALUE_RE.match(seg_str):
            raise ParamError(f"segment value contains unsafe characters: {seg_str!r}")
        out.segment_value = seg_str

    return out
