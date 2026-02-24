"""
Converts raw SQL result rows into Chart.js-compatible ChartConfig objects.
"""
from models import ChartConfig

CHART_TYPE_MAP = {
    "bar_chart": "bar",
    "line_chart": "line",
    "pie_chart": "pie",
}

# A curated palette — indigo, emerald, amber, red, blue, purple, teal, orange
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


def format_chart(
    rows: list[dict],
    response_type: str,
    label_col: str,
    value_col: str,
    title: str = "",
) -> ChartConfig:
    """
    Build a Chart.js-compatible config from SQL result rows.

    Args:
        rows: list of dicts from supabase_runner.execute()
        response_type: "bar_chart" | "line_chart" | "pie_chart"
        label_col: column name to use for labels (x-axis or pie segments)
        value_col: column name to use for values (y-axis or pie sizes)
        title: human-readable chart title

    Returns:
        ChartConfig pydantic model
    """
    chart_type = CHART_TYPE_MAP.get(response_type, "bar")

    # Extract labels and values, coercing values to numeric
    labels: list[str] = []
    values: list[float] = []

    for row in rows:
        label_val = row.get(label_col, "")
        value_val = row.get(value_col, 0)

        labels.append(str(label_val) if label_val is not None else "NULL")
        try:
            values.append(float(value_val) if value_val is not None else 0.0)
        except (TypeError, ValueError):
            values.append(0.0)

    n = len(labels)
    # Cycle colours for large datasets
    bg_colors = [PALETTE[i % len(PALETTE)] for i in range(n)]
    border_colors = [BORDER_PALETTE[i % len(BORDER_PALETTE)] for i in range(n)]

    if chart_type == "pie":
        dataset = {
            "label": value_col.replace("_", " ").title(),
            "data": values,
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": 1,
        }
    elif chart_type == "line":
        dataset = {
            "label": value_col.replace("_", " ").title(),
            "data": values,
            "backgroundColor": PALETTE[0],
            "borderColor": BORDER_PALETTE[0],
            "borderWidth": 2,
            "tension": 0.4,
            "fill": False,
            "pointBackgroundColor": BORDER_PALETTE[0],
            "pointRadius": 4,
        }
    else:  # bar
        dataset = {
            "label": value_col.replace("_", " ").title(),
            "data": values,
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": 1,
            "borderRadius": 4,
        }

    return ChartConfig(
        type=chart_type,
        labels=labels,
        datasets=[dataset],
        title=title or value_col.replace("_", " ").title(),
    )
