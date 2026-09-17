"""
Natural-language interpretation of query results.

Replicates chat_api/llm_client.py's interpret_results() and explain_empty_results()
without importing that module, keeping the adapter self-contained.
Same prompts, same model — output is indistinguishable to the frontend.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .config import MODEL


def _response_text(response) -> str:
    """Return the first text block's content, skipping thinking blocks."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def interpret_results(question: str, rows: List[Dict[str, Any]]) -> str:
    """
    2-3 sentence natural-language insight from SQL result rows.
    Mirrors llm_client.interpret_results exactly.
    """
    import anthropic

    client = anthropic.Anthropic()
    sample = rows[:30]
    rows_text = "\n".join(str(r) for r in sample)
    total = len(rows)
    sample_note = f"(showing {len(sample)} of {total} rows)" if total > 30 else f"({total} rows)"

    prompt = (
        f"The user asked: \"{question}\"\n\n"
        f"The query returned the following data {sample_note}:\n{rows_text}\n\n"
        "Write 2-3 sentences interpreting this data. Highlight the key finding, "
        "top value or pattern, and any notable anomaly. Be specific — mention actual "
        "values from the data. Do not say 'the table shows' or 'the data shows'. "
        "Write as if giving a direct insight to an analyst. Plain text only.\n\n"
        "CRITICAL: Only state numbers and figures that appear explicitly in the rows "
        "above. Do not approximate, estimate, or synthesise values not present in the "
        "data. If the data does not contain enough information to answer part of the "
        "question, say so explicitly rather than inferring."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return _response_text(response).strip()


def explain_empty_results(question: str, sql: str) -> str:
    """
    1-2 sentence explanation when a query returns 0 rows.
    Mirrors llm_client.explain_empty_results exactly.
    """
    import anthropic

    client = anthropic.Anthropic()
    prompt = (
        "A database query was run to answer this question but returned no results:\n\n"
        f"Question: {question}\n\n"
        f"SQL executed:\n```sql\n{sql}\n```\n\n"
        "In 1-2 sentences, explain what was being searched for and why there might be "
        "no matching data. Be specific about the filters used. Do not suggest running "
        "a different query. Respond with plain text only — no JSON, no markdown."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return _response_text(response).strip()
