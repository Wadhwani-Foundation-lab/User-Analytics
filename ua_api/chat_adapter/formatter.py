"""
Chart and table formatting for certified metric responses.

Replicates the logic in chat_api/chart_formatter.py without importing it,
so the adapter has zero dependency on chat_api/. Returns plain dicts that
map directly onto the models.ChartConfig / models.TableData shapes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import ChartConfig, TableData

# Matches chat_api/chart_formatter.py exactly — keep in sync if palette changes there.
CHART_TYPE_MAP = {
    "bar_chart": "bar",
    "line_chart": "line",
    "pie_chart": "pie",
    "funnel_chart": "funnel",
}

PALETTE = [
    "rgba(99, 102, 241, 0.85)",
    "rgba(16, 185, 129, 0.85)",
    "rgba(245, 158, 11, 0.85)",
    "rgba(239, 68, 68, 0.85)",
    "rgba(59, 130, 246, 0.85)",
    "rgba(168, 85, 247, 0.85)",
    "rgba(20, 184, 166, 0.85)",
    "rgba(249, 115, 22, 0.85)",
]
BORDER_PALETTE = [c.replace("0.85", "1") for c in PALETTE]

CHART_RESPONSE_TYPES = {"bar_chart", "line_chart", "pie_chart", "funnel_chart"}


def build_chart(
    rows: List[Dict[str, Any]],
    response_type: str,
    label_col: str,
    value_col: str,
    title: str = "",
) -> ChartConfig:
    """Build a ChartConfig from SQL result rows. Mirrors chart_formatter.format_chart."""
    chart_type = CHART_TYPE_MAP.get(response_type, "bar")
    labels: List[str] = []
    values: List[float] = []

    for row in rows:
        lv = row.get(label_col, "")
        vv = row.get(value_col, 0)
        labels.append(str(lv) if lv is not None else "NULL")
        try:
            values.append(float(vv) if vv is not None else 0.0)
        except (TypeError, ValueError):
            values.append(0.0)

    n = len(labels)
    bg = [PALETTE[i % len(PALETTE)] for i in range(n)]
    bd = [BORDER_PALETTE[i % len(BORDER_PALETTE)] for i in range(n)]
    human_label = value_col.replace("_", " ").title()

    if chart_type == "line":
        dataset: Dict[str, Any] = {
            "label": human_label,
            "data": values,
            "backgroundColor": PALETTE[0],
            "borderColor": BORDER_PALETTE[0],
            "borderWidth": 2,
            "tension": 0.4,
            "fill": False,
            "pointBackgroundColor": BORDER_PALETTE[0],
            "pointRadius": 4,
        }
    else:
        dataset = {
            "label": human_label,
            "data": values,
            "backgroundColor": bg,
            "borderColor": bd,
            "borderWidth": 1,
            **({"borderRadius": 4} if chart_type == "bar" else {}),
        }

    return ChartConfig(
        type=chart_type,  # type: ignore[arg-type]
        labels=labels,
        datasets=[dataset],
        title=title or human_label,
    )


def build_table(rows: List[Dict[str, Any]]) -> Optional[TableData]:
    """Build a TableData from SQL result rows. Returns None when rows is empty."""
    if not rows:
        return None
    columns = list(rows[0].keys())
    return TableData(
        columns=columns,
        rows=[[row.get(c) for c in columns] for row in rows],
    )
