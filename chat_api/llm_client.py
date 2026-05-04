"""
Anthropic Claude claude-sonnet-4-5 LLM client.
Parses the model's structured JSON response and returns it as a dict.

Robustness improvements:
- Appends a short JSON reminder to every user message (counters multi-turn drift)
- Auto-retries once with a correction prompt if Claude returns plain text
"""
from __future__ import annotations
from typing import Optional
import os
import json
import re

import anthropic

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096

# Appended to every user message to re-anchor Claude to JSON output.
# Kept short so it doesn't dominate the context.
_JSON_REMINDER = (
    "\n\n[REMINDER: Your response MUST start with a valid JSON block "
    "exactly matching the required format. No plain-text answer before the JSON.]"
)

# Correction prompt sent on retry when Claude returns plain text.
_CORRECTION_PROMPT = (
    "Your last response did not contain a valid JSON block. "
    "Please restate your answer strictly in the required JSON format:\n"
    "```json\n"
    '{{"sql": "SELECT ...", "response_type": "text|table|bar_chart|line_chart|pie_chart", '
    '"nl_answer_template": "...", "chart_label_column": "", "chart_value_column": ""}}\n'
    "```\n"
    "Output ONLY the JSON block. Do not add any text before or after it."
)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:  # type: ignore[return]
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _extract_json_object(text: str) -> str | None:
    """Find the first complete {...} block, respecting nested braces and strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_response(raw_text: str) -> dict | None:
    """
    Try to extract and parse a JSON block from raw LLM output.
    Returns parsed dict on success, None if no valid JSON block found.
    """
    # First try: inside a ```json ... ``` fence
    fenced = re.search(r"```json\s*([\s\S]*?)\s*```", raw_text)
    if fenced:
        json_str = _extract_json_object(fenced.group(1)) or _extract_json_object(raw_text)
    else:
        json_str = _extract_json_object(raw_text)

    if not json_str:
        return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def interpret_results(question: str, rows: list[dict]) -> str:
    """
    Called after SQL executes successfully with rows. Returns a 2-3 sentence
    natural language interpretation of the actual data — key patterns, top values,
    anomalies — so the user gets insight alongside the table.
    """
    client = _get_client()

    # Summarise the data: send up to 30 rows to stay within token budget
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
        "Write as if giving a direct insight to an analyst. Plain text only."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def ask_with_cached_sql(system_prompt: str, history: list[dict], question: str, cached_sql: str) -> dict:
    """
    Ask Claude to format a response for a question whose SQL is already known.
    Skips SQL generation — Claude only determines response_type, nl_answer_template,
    and chart columns.

    Returns a dict in the same shape as ask():
        sql, response_type, nl_answer_template, chart_label_column, chart_value_column
    """
    client = _get_client()

    formatting_prompt = (
        f"{question}{_JSON_REMINDER}\n\n"
        f"[NOTE: The SQL for this question is already determined:\n```sql\n{cached_sql}\n```\n"
        "Use exactly this SQL in your response. Your only task is to set "
        "response_type, nl_answer_template, chart_label_column, and chart_value_column "
        "appropriately for the question.]"
    )

    messages = history + [{"role": "user", "content": formatting_prompt}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    raw_text: str = response.content[0].text
    parsed = _parse_response(raw_text)

    if parsed is not None:
        # Always enforce the cached SQL (LLM must not override it)
        parsed["sql"] = cached_sql
        parsed["_raw_response"] = raw_text
        parsed["_from_cache"] = True
        return parsed

    # Fallback: return minimal dict with cached SQL so execution can still proceed
    return {
        "sql": cached_sql,
        "response_type": "table",
        "nl_answer_template": "",
        "chart_label_column": "",
        "chart_value_column": "",
        "_from_cache": True,
        "_fallback": True,
    }


def explain_empty_results(question: str, sql: str) -> str:
    """
    Called when a SQL query returns 0 rows. Returns a plain-text explanation
    of what was searched and why there may be no matching data.
    """
    client = _get_client()
    prompt = (
        f"A database query was run to answer this question but returned no results:\n\n"
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
    return response.content[0].text.strip()


def ask(system_prompt: str, history: list[dict], question: str) -> dict:
    """
    Send a question (with history) to Claude and return parsed JSON response.

    Returns a dict with at minimum:
        sql, response_type, nl_answer_template,
        chart_label_column (optional), chart_value_column (optional)

    Strategy:
    1. Append a JSON reminder to the user question to counter multi-turn drift.
    2. If Claude returns plain text (no JSON block), send one correction prompt
       as a follow-up and try to parse again before raising.
    """
    client = _get_client()

    # --- Attempt 1: question + JSON reminder --------------------------------
    question_with_reminder = question + _JSON_REMINDER
    messages = history + [{"role": "user", "content": question_with_reminder}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    raw_text: str = response.content[0].text
    parsed = _parse_response(raw_text)

    if parsed is not None:
        parsed["_raw_response"] = raw_text
        return parsed

    # --- Attempt 2: correction prompt retry ---------------------------------
    # Keep original question (without reminder) in history so context is clean.
    correction_messages = (
        history
        + [{"role": "user", "content": question_with_reminder}]
        + [{"role": "assistant", "content": raw_text}]
        + [{"role": "user", "content": _CORRECTION_PROMPT}]
    )

    retry_response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=correction_messages,
    )
    retry_text: str = retry_response.content[0].text
    parsed_retry = _parse_response(retry_text)

    if parsed_retry is not None:
        parsed_retry["_raw_response"] = retry_text
        parsed_retry["_retried"] = True   # flag for debugging
        return parsed_retry

    # Both attempts failed — raise descriptive error
    raise ValueError(
        f"LLM did not return a valid JSON block. Raw response (first 300 chars): {raw_text[:300]}"
    )
