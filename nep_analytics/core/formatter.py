"""
Converts raw SQL result rows into structured response payloads.
Provides chart config, table data, and auto-upgrade logic.
"""
from __future__ import annotations

from typing import Any

# ── Chart palette (indigo, emerald, amber, red, blue, purple, teal, orange) ──
_PALETTE = [
    "rgba(99, 102, 241, 0.85)",
    "rgba(16, 185, 129, 0.85)",
    "rgba(245, 158, 11, 0.85)",
    "rgba(239, 68, 68, 0.85)",
    "rgba(59, 130, 246, 0.85)",
    "rgba(168, 85, 247, 0.85)",
    "rgba(20, 184, 166, 0.85)",
    "rgba(249, 115, 22, 0.85)",
]
_BORDER = [c.replace("0.85", "1") for c in _PALETTE]

_CHART_TYPE_MAP = {
    "bar_chart": "bar",
    "line_chart": "line",
    "pie_chart": "pie",
    "funnel_chart": "funnel",
}


def _to_float(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def build_chart(
    rows: list[dict],
    response_type: str,
    label_col: str,
    value_col: str,
    title: str = "",
    series_col: str = "",
) -> dict:
    """Return a Chart.js-compatible config dict.

    Without series_col: one dataset, one value per label (existing behaviour).
    With series_col: rows are pivoted into one dataset per distinct series
    value, all sharing the same label axis (e.g. month on x, one line/stack
    per company_type) — bar charts render stacked, line charts render as
    separate lines, one per series.
    """
    chart_type = _CHART_TYPE_MAP.get(response_type, "bar")
    label = value_col.replace("_", " ").title()

    if series_col:
        return _build_multi_series_chart(rows, chart_type, label_col, value_col, series_col, title, label)

    labels: list[str] = []
    values: list[float] = []
    for row in rows:
        labels.append(str(row.get(label_col, "") or "NULL"))
        values.append(_to_float(row.get(value_col, 0)))

    n = len(labels)
    bg = [_PALETTE[i % len(_PALETTE)] for i in range(n)]
    bd = [_BORDER[i % len(_BORDER)] for i in range(n)]

    if chart_type == "line":
        dataset: dict[str, Any] = {
            "label": label,
            "data": values,
            "backgroundColor": _PALETTE[0],
            "borderColor": _BORDER[0],
            "borderWidth": 2,
            "tension": 0.4,
            "fill": False,
            "pointBackgroundColor": _BORDER[0],
            "pointRadius": 4,
        }
    elif chart_type in ("pie", "funnel"):
        dataset = {
            "label": label,
            "data": values,
            "backgroundColor": bg,
            "borderColor": bd,
            "borderWidth": 1,
        }
    else:  # bar
        dataset = {
            "label": label,
            "data": values,
            "backgroundColor": bg,
            "borderColor": bd,
            "borderWidth": 1,
            "borderRadius": 4,
        }

    return {
        "type": chart_type,
        "labels": labels,
        "datasets": [dataset],
        "title": title or label,
    }


def _build_multi_series_chart(
    rows: list[dict],
    chart_type: str,
    label_col: str,
    value_col: str,
    series_col: str,
    title: str,
    value_label: str,
) -> dict:
    """Pivot rows with (label, series, value) into one Chart.js dataset per series."""
    labels: list[str] = []
    seen_labels: set[str] = set()
    series_names: list[str] = []
    seen_series: set[str] = set()
    lookup: dict[tuple[str, str], float] = {}

    for row in rows:
        lbl = str(row.get(label_col, "") or "NULL")
        ser = str(row.get(series_col, "") or "NULL")
        if lbl not in seen_labels:
            seen_labels.add(lbl)
            labels.append(lbl)
        if ser not in seen_series:
            seen_series.add(ser)
            series_names.append(ser)
        lookup[(lbl, ser)] = _to_float(row.get(value_col, 0))

    is_line = chart_type == "line"
    datasets: list[dict[str, Any]] = []
    for i, ser in enumerate(series_names):
        color = _PALETTE[i % len(_PALETTE)]
        border = _BORDER[i % len(_BORDER)]
        data = [lookup.get((lbl, ser), 0.0) for lbl in labels]
        if is_line:
            datasets.append({
                "label": ser,
                "data": data,
                "backgroundColor": color,
                "borderColor": border,
                "borderWidth": 2,
                "tension": 0.4,
                "fill": False,
                "pointBackgroundColor": border,
                "pointRadius": 4,
            })
        else:
            datasets.append({
                "label": ser,
                "data": data,
                "backgroundColor": color,
                "borderColor": border,
                "borderWidth": 1,
                "borderRadius": 4,
            })

    return {
        "type": "line" if is_line else "bar",
        "labels": labels,
        "datasets": datasets,
        "title": title or value_label,
        "stacked": not is_line,
    }


def build_table(rows: list[dict]) -> dict:
    """Return a {columns, rows} table payload."""
    columns = list(rows[0].keys()) if rows else []
    return {
        "columns": columns,
        "rows": [[row.get(c) for c in columns] for row in rows],
    }


def should_upgrade_to_table(rows: list[dict], response_type: str) -> bool:
    """Return True if a 'text' response should be auto-upgraded to a table."""
    if response_type != "text" or not rows:
        return False
    return len(rows[0].keys()) > 1 or len(rows) > 1


def extract_scalar(rows: list[dict], nl_template: str) -> str:
    """Format a single scalar value into a natural language sentence."""
    if not rows:
        return "No data found for that query."
    first_val = list(rows[0].values())[0] if rows[0] else None
    if first_val is None:
        return nl_template or "No data found."
    val_str = str(first_val)
    if "{result}" in nl_template:
        return nl_template.replace("{result}", f"**{val_str}**")
    return f"{nl_template} **{val_str}**" if nl_template else f"**{val_str}**"
