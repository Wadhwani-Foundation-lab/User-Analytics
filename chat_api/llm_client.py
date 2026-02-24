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

    # Extract JSON block from the response (handles markdown code fences)
    json_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", raw_text)
    if not json_match:
        # Try raw JSON without fences
        json_match = re.search(r"\{[\s\S]*?\}", raw_text)

    if not json_match:
        raise ValueError(
            f"LLM did not return a valid JSON block. Raw response (first 300 chars): {raw_text[:300]}"
        )

    json_str = json_match.group(1) if json_match.lastindex else json_match.group(0)

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM JSON: {e}. Raw JSON string: {json_str[:300]}")

    # Attach full raw text for any downstream use
    parsed["_raw_response"] = raw_text
    return parsed
