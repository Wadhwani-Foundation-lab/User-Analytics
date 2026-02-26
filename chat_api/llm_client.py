"""
Anthropic Claude claude-sonnet-4-5 LLM client.
Parses the model's structured JSON response and returns it as a dict.
"""
from __future__ import annotations
from typing import Optional
import os
import json
import re

import anthropic

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:  # type: ignore[return]
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def ask(system_prompt: str, history: list[dict], question: str) -> dict:
    """
    Send a question (with history) to Claude and return parsed JSON response.

    Returns a dict with at minimum:
        sql, response_type, nl_answer_template,
        chart_label_column (optional), chart_value_column (optional)
    """
    messages = history + [{"role": "user", "content": question}]

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    raw_text: str = response.content[0].text

    # Extract JSON block — use brace-depth scanner to correctly handle nested JSON
    def extract_json_object(text: str) -> str | None:
        """Find the first complete {...} block, respecting nested braces."""
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

    # First try: extract from inside a ```json ... ``` fence
    fenced = re.search(r"```json\s*([\s\S]*?)\s*```", raw_text)
    if fenced:
        json_str = extract_json_object(fenced.group(1)) or extract_json_object(raw_text)
    else:
        json_str = extract_json_object(raw_text)

    if not json_str:
        raise ValueError(
            f"LLM did not return a valid JSON block. Raw response (first 300 chars): {raw_text[:300]}"
        )

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM JSON: {e}. Raw JSON string: {json_str[:300]}")

    # Attach full raw text for any downstream use
    parsed["_raw_response"] = raw_text
    return parsed
