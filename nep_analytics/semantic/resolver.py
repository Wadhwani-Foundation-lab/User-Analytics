"""
Semantic resolver — classifies a question to a certified metric using Claude's
tool-use API. The LLM's only job is classification; it never writes SQL.

Returns {metric, params, confidence, reason} on match, or None on miss.
"""
from __future__ import annotations

import json
from datetime import date as _date
from typing import Any, Dict, List, Optional

from ..core.config import get_anthropic, RESOLVER_MODEL
from .registry import Registry, load_registry

_MAX_TOKENS = 1024

_SYSTEM = """\
You are a metric router for an analytics assistant.
You are given a catalog of certified metrics. Decide whether the user's question
maps to exactly one metric, and extract its parameters via the get_metric tool.
You do NOT write SQL.

COVERAGE CHECK — mandatory before calling get_metric:
1. List every filter dimension the question names (user_type, company_type, date range, etc.).
2. For each filter, verify the metric has a matching choice key or segment. Date ranges
   are always covered by the metric's date_filter. user_type is covered by segment.
3. If ANY filter is NOT covered, do NOT call get_metric — fall through to free-form SQL.
4. If the question asks for counts from multiple different tables simultaneously,
   no single metric covers all — do NOT call get_metric.
5. A partial match that silently ignores a filter is worse than no match.

DATE RANGE RULES:
- Whole month: "January 2026" → start=2026-01-01, end=2026-02-01.
- Specific inclusive end: "Dec 17 to Jan 10" → start=2025-12-17, end=2026-01-11 (end is EXCLUSIVE).
- Q1 2026 → start=2026-01-01, end=2026-04-01.
- "last 7 days" relative to TODAY → start=TODAY-7, end=TODAY+1.

CONFIDENCE: Call get_metric ONLY when ALL filters are covered and confidence >= 0.7.
"""


def _build_tool(metric_names: List[str]) -> dict:
    return {
        "name": "get_metric",
        "description": (
            "Match a question to a certified metric and extract its parameters. "
            "Call ONLY when a metric clearly covers all filter dimensions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": metric_names,
                    "description": "The certified metric name.",
                },
                "params": {
                    "type": "object",
                    "description": "Extracted parameters.",
                    "properties": {
                        "period": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string", "description": "YYYY-MM-DD"},
                                "end": {"type": "string", "description": "YYYY-MM-DD (exclusive)"},
                            },
                            "required": ["start", "end"],
                        },
                        "grain": {
                            "type": "string",
                            "enum": ["month", "week", "day"],
                        },
                        "segment": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reason": {"type": "string"},
            },
            "required": ["metric", "params", "confidence", "reason"],
        },
    }


def resolve(
    question: str,
    registry: Optional[Registry] = None,
    today: Optional[str] = None,
    min_confidence: float = 0.6,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return {metric, params, confidence, reason} or None.
    None means no certified metric matches — caller should use sql_generator.
    """
    registry = registry or load_registry()
    today = today or _date.today().isoformat()
    catalog = registry.catalog_for_resolver()

    context_block = ""
    if history:
        recent = history[-4:]
        lines = [
            f"{t.get('role', '').upper()}: {(t.get('content') or '')[:300]}"
            for t in recent
        ]
        context_block = "PRIOR CONVERSATION:\n" + "\n".join(lines) + "\n\n"

    user_message = (
        f"TODAY: {today}\n\n"
        f"{context_block}"
        f"METRIC CATALOG:\n{json.dumps(catalog, indent=2)}\n\n"
        f"QUESTION: {question}"
    )

    client = get_anthropic()
    metric_names = list(registry.metrics.keys())
    tool = _build_tool(metric_names)

    response = client.messages.create(
        model=RESOLVER_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM,
        tools=[tool],
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "get_metric":
            tool_input = block.input
            name = tool_input.get("metric")
            if not name or registry.get(name) is None:
                return None
            confidence = float(tool_input.get("confidence", 0))
            if confidence < min_confidence:
                return None
            return {
                "metric": name,
                "params": tool_input.get("params") or {},
                "confidence": confidence,
                "reason": tool_input.get("reason", ""),
            }

    return None
