"""
Feedback signal reader.

Reads message_rating and message_rating_feedback from nep_liftoffx_data_sample
to surface aggregate AI-chat quality signals. These ratings are the ground truth
for whether users found answers useful — the closest proxy we have for certified
metric quality until the frontend starts tagging responses with provenance.

Returns data in three shapes:
  overall_rating()  — aggregate mean/count across all rated AI-chat messages
  rating_by_period()— month-by-month rating trend
  low_rated_questions() — sampled questions with low ratings (for review)

Run via: python -m ua_api.feedback
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _run(sql: str) -> List[Dict[str, Any]]:
    from ..data_context.config import run_sql
    return run_sql(sql)


def overall_rating() -> Dict[str, Any]:
    """Aggregate rating stats across all rated AI-chat messages."""
    rows = _run("""
        SELECT
            COUNT(*) AS total_rated,
            ROUND(AVG(message_rating::INTEGER::NUMERIC), 2) AS avg_rating,
            COUNT(CASE WHEN message_rating::INTEGER >= 4 THEN 1 END) AS high_rated,
            COUNT(CASE WHEN message_rating::INTEGER <= 2 THEN 1 END) AS low_rated,
            COUNT(CASE WHEN message_rating_feedback IS NOT NULL
                       AND message_rating_feedback != '' THEN 1 END) AS with_text_feedback
        FROM nep_liftoffx_data_sample
        WHERE activity_type = 'message'
          AND message_rating IS NOT NULL
          AND message_rating ~ '^[0-9]+$'
        LIMIT 1
    """)
    if not rows:
        return {"total_rated": 0, "avg_rating": None, "high_rated": 0, "low_rated": 0, "with_text_feedback": 0}
    return rows[0]


def rating_by_period(grain: str = "month") -> List[Dict[str, Any]]:
    """
    Rating trend over time.

    grain: "month" (default) | "week"
    """
    if grain == "week":
        period_expr = "week_range"
        order_expr = "MIN(message_date)"
    else:
        period_expr = "month_year"
        order_expr = "month_year_order"

    return _run(f"""
        SELECT
            {period_expr} AS period,
            COUNT(*) AS rated_messages,
            ROUND(AVG(message_rating::INTEGER::NUMERIC), 2) AS avg_rating,
            COUNT(CASE WHEN message_rating::INTEGER >= 4 THEN 1 END) AS high_rated,
            COUNT(CASE WHEN message_rating::INTEGER <= 2 THEN 1 END) AS low_rated
        FROM nep_liftoffx_data_sample
        WHERE activity_type = 'message'
          AND message_rating IS NOT NULL
          AND message_rating ~ '^[0-9]+$'
          AND {period_expr} IS NOT NULL
        GROUP BY {period_expr}
        ORDER BY {order_expr}
        LIMIT 500
    """)


def low_rated_questions(
    max_rating: int = 2,
    limit: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Sample of low-rated questions for manual review.

    These are candidate cases to add to the eval set or fix with a new certified metric.
    """
    date_clause = ""
    if start_date:
        date_clause += f" AND message_date >= '{start_date}'"
    if end_date:
        date_clause += f" AND message_date < '{end_date}'"

    return _run(f"""
        SELECT
            message_date,
            message_query,
            message_rating,
            message_rating_feedback
        FROM nep_liftoffx_data_sample
        WHERE activity_type = 'message'
          AND message_rating IS NOT NULL
          AND message_rating ~ '^[0-9]+$'
          AND message_rating::INTEGER <= {max_rating}
          AND message_query IS NOT NULL
          {date_clause}
        ORDER BY message_date DESC
        LIMIT {limit}
    """)


def print_report(verbose: bool = False) -> None:
    """Print a human-readable signal report to stdout."""
    line = "=" * 60

    print(line)
    print("  AI Chat Quality Signals")
    print(line)

    overall = overall_rating()
    total = overall.get("total_rated", 0)
    if not total:
        print("  No rated messages found in nep_liftoffx_data_sample.")
        print(line)
        return

    avg = overall.get("avg_rating")
    high = overall.get("high_rated", 0)
    low = overall.get("low_rated", 0)
    text_fb = overall.get("with_text_feedback", 0)
    print(f"  Total rated messages : {total}")
    print(f"  Average rating       : {avg}/5")
    print(f"  High (≥4)            : {high}  ({round(high/total*100, 1)}%)")
    print(f"  Low (≤2)             : {low}  ({round(low/total*100, 1)}%)")
    print(f"  With text feedback   : {text_fb}")
    print(line)

    trend = rating_by_period("month")
    if trend:
        print("  Monthly trend:")
        for row in trend:
            print(
                f"    {row['period']:>10}  "
                f"rated={row['rated_messages']:>4}  "
                f"avg={row['avg_rating']}  "
                f"high={row['high_rated']}  low={row['low_rated']}"
            )
        print(line)

    if verbose:
        low_qs = low_rated_questions(max_rating=2, limit=10)
        if low_qs:
            print("  Sample low-rated questions (rating ≤ 2):")
            for q in low_qs:
                fb = q.get("message_rating_feedback") or ""
                snippet = (q.get("message_query") or "")[:70]
                print(f"    [{q['message_rating']}] {snippet}")
                if fb:
                    print(f"        feedback: {fb[:80]}")
            print(line)
