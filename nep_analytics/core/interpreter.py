"""
Natural language interpretation of SQL result rows.
Uses claude-sonnet-5 — lighter than Opus, sufficient for prose generation.
"""
from __future__ import annotations

from collections import Counter

from .config import get_anthropic, INTERPRET_MODEL

_SAMPLE_LIMIT = 30
_MAX_GROUP_COLS = 3
_MAX_GROUP_VALUES = 15


def _response_text(response) -> str:
    """Return the first text block's content, skipping thinking blocks."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _stratified_sample(rows: list[dict], limit: int = _SAMPLE_LIMIT) -> list[dict]:
    """
    Take up to `limit` rows, guaranteeing every distinct value of the most
    likely comparison/category column is represented at least once — a flat
    rows[:limit] slice can silently drop an entire category when the SQL's
    ORDER BY groups one category's rows after the cutoff, which previously
    caused the interpreter to claim a category had "no data" when it simply
    wasn't in the sample.
    """
    if len(rows) <= limit:
        return rows

    candidate_cols = [
        col for col in rows[0].keys()
        if 1 < len({r.get(col) for r in rows}) <= _MAX_GROUP_VALUES
    ]
    if not candidate_cols:
        return rows[:limit]

    group_col = min(candidate_cols, key=lambda c: len({r.get(c) for r in rows}))
    groups: dict = {}
    for r in rows:
        groups.setdefault(r.get(group_col), []).append(r)

    sample: list[dict] = []
    iterators = {k: iter(v) for k, v in groups.items()}
    while len(sample) < limit and iterators:
        for k in list(iterators.keys()):
            try:
                sample.append(next(iterators[k]))
            except StopIteration:
                del iterators[k]
            if len(sample) >= limit:
                break
    return sample


def _group_summary(rows: list[dict]) -> str:
    """
    Ground-truth counts for low-cardinality columns across ALL rows (not just
    the sample), so the interpreter can never contradict what actually exists
    in the full result set — e.g. claim a category is absent when it only
    fell outside the sampled rows.
    """
    if not rows:
        return ""
    lines = []
    for col in rows[0].keys():
        values = [r.get(col) for r in rows]
        distinct = set(values)
        if 1 < len(distinct) <= _MAX_GROUP_VALUES:
            counts = Counter(values)
            parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda x: str(x[0])))
            lines.append(f"  {col}: {parts}")
        if len(lines) >= _MAX_GROUP_COLS:
            break
    if not lines:
        return ""
    return "GROUP COUNTS ACROSS ALL ROWS (ground truth — never contradict this):\n" + "\n".join(lines)


_ROW_LIMIT = 500  # matches Rule 2's LIMIT 500 — hitting this exactly signals possible truncation


def interpret_results(question: str, rows: list[dict]) -> str:
    """
    Return a 2-3 sentence plain-text insight about the query results.
    Sent up to 30 rows (stratified across categories) to stay within token budget.
    """
    client = get_anthropic()
    sample = _stratified_sample(rows)
    rows_text = "\n".join(str(r) for r in sample)
    sample_note = (
        f"(showing {len(sample)} of {len(rows)} rows)" if len(rows) > _SAMPLE_LIMIT else f"({len(rows)} rows)"
    )
    group_summary = _group_summary(rows)
    truncation_note = (
        "\n\nNOTE: This result hit the query's row LIMIT (500) — there may be more "
        "matching data beyond what's shown. Do not state totals or per-category "
        "figures as complete; caveat that the result may be truncated."
        if len(rows) >= _ROW_LIMIT else ""
    )

    prompt = (
        f'The user asked: "{question}"\n\n'
        f"Query results {sample_note}:\n{rows_text}\n\n"
        + (f"{group_summary}\n\n" if group_summary else "")
        + "Write 2-3 sentences interpreting this data. Highlight the key finding, "
        "top value or pattern, and any notable anomaly. Be specific — mention actual "
        "values from the data. Do not say 'the table shows' or 'the data shows'. "
        "Write as if giving a direct insight to an analyst. Plain text only. "
        "Never claim a value or category is missing or absent unless it is confirmed "
        "missing from the GROUP COUNTS section (if present) — the row sample above may "
        "not include every category.\n\n"
        "Before finalizing: verify that any totals, sums, or breakdowns you state are "
        "arithmetically consistent with each other and with the rows above — e.g. parts "
        "you list must add up to the total you claim. If the numbers do not reconcile, "
        "state the figures plainly and note the discrepancy rather than inventing an "
        "explanation (like a 'display bug') that isn't supported by the data shown. "
        "Do not add a caveat or warning unless it is directly supported by the rows shown "
        "(e.g. don't speculate about 'future dates' or data quality without evidence in "
        "the data itself). Do not second-guess or contradict a number that is already "
        "consistent with the rows above just to sound more cautious."
        + truncation_note
    )

    response = client.messages.create(
        model=INTERPRET_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return _response_text(response).strip()


def explain_empty_results(question: str, sql: str) -> str:
    """Return a 1-2 sentence explanation for a query that returned zero rows."""
    client = get_anthropic()
    prompt = (
        "A database query returned no results:\n\n"
        f"Question: {question}\n\nSQL:\n```sql\n{sql}\n```\n\n"
        "In 1-2 sentences, explain what was searched and why there might be no data. "
        "Do not suggest running a different query. Plain text only."
    )
    response = client.messages.create(
        model=INTERPRET_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return _response_text(response).strip()
