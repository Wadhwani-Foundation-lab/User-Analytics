"""
Renderer — turns a Metric + validated params into trusted SQL.

The LLM never produces this SQL. The template is human-certified; the renderer
only substitutes (a) grain fragments from the metric's choice map, (b) a date
filter built from the metric's declared date column, and (c) a segment equality
validated against the catalog. Any leftover placeholder is an error, not a
silent gap.
"""
from __future__ import annotations

import re
from typing import Tuple

from .params import ResolvedParams, validate
from .registry import Metric

_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def render(metric: Metric, raw_params=None) -> Tuple[str, ResolvedParams]:
    """Validate params and render the certified SQL. Returns (sql, resolved)."""
    resolved = validate(metric, raw_params)
    subs = {}

    # (a) grain / choice fragments
    for name, value in resolved.grain_values.items():
        subs.update(metric.choices[name].value_map[value])

    # (b) date filter (leading space + AND, or empty)
    if resolved.period_start and resolved.period_end and metric.date_filter:
        col = metric.date_filter.column
        subs["date_filter"] = (
            f" AND {col} >= '{_sql_quote(resolved.period_start)}'"
            f" AND {col} < '{_sql_quote(resolved.period_end)}'"
        )
    else:
        subs["date_filter"] = ""

    # (c) segment equality (validated value)
    if resolved.segment_value and metric.segment:
        subs["segment_filter"] = (
            f" AND {metric.segment.column} = '{_sql_quote(resolved.segment_value)}'"
        )
    else:
        subs["segment_filter"] = ""

    sql = metric.sql_template
    for key, fragment in subs.items():
        sql = sql.replace("{" + key + "}", fragment)

    # Any unresolved placeholder means the template/registry are inconsistent.
    leftover = _PLACEHOLDER_RE.findall(sql)
    if leftover:
        raise ValueError(
            f"metric '{metric.name}': unresolved placeholder(s) {sorted(set(leftover))}"
        )
    return sql.strip(), resolved
