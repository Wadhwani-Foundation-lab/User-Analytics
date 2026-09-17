"""
Resolver — maps a natural-language question to a certified metric + parameters.

Phase 2: uses Claude's native tool-use API.

  resolve() asks Claude to call the `get_metric` tool when a metric fits.
  If Claude returns no tool call (just text), the question doesn't match —
  fall back to text-to-SQL. No JSON parsing needed; metric names are enumerated
  in the tool schema so hallucination is structurally impossible.

  answer() ties it all together: resolve → render certified SQL → execute.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import MODEL  # importing also loads chat_api/.env (ANTHROPIC_API_KEY)
from .registry import Registry, load_registry
from .renderer import render

MAX_TOKENS = 1024

_RESOLVER_SYSTEM = """\
You are a metric router for an analytics assistant.
You are given a catalog of certified metrics. Decide whether the user's question
maps to exactly one metric, and extract its parameters via the get_metric tool.
You do NOT write SQL.

COVERAGE CHECK — mandatory before calling get_metric:
1. List every filter dimension the question names (e.g. company_type=startup,
   user_type=External, country=India, visibility=PUBLIC, revenue_range=pre-revenue,
   traffic_source, mentor_type, stage).
2. For each filter, verify the target metric has a matching choice key or segment.
   Date ranges are always covered by the metric's date_filter. user_type is
   covered by a metric's segment field.
3. If ANY filter dimension is NOT covered by the metric's choices or segment,
   do NOT call get_metric — fall through to free-form SQL.
4. If the question asks for independent counts from multiple different tables
   (e.g. "compare mentors AND events AND signups across programs"), no single
   metric covers all of them — do NOT call get_metric.
5. A partial match that silently ignores a filter is worse than no match.

DATE RANGE RULES:
- A whole month: "January 2026" → start=2026-01-01, end=2026-02-01 (next month).
- A specific inclusive end date: "Dec 17 to Jan 10" → start=2025-12-17, end=2026-01-11
  (end is EXCLUSIVE — always add 1 day to a specific inclusive end date).
- "Q1 2026" → start=2026-01-01, end=2026-04-01.
- "last 7 days" relative to TODAY → start=TODAY-7, end=TODAY+1.

TIME-GRAIN RULES:
- If the question asks for "month-over-month", "monthly trend", or compares
  named months, set grain=monthly on metrics that support it.
- Only include parameters the question actually specifies; omit the rest.

CONFIDENCE:
- Call get_metric ONLY when ALL filters are covered and confidence >= 0.7.
- Prefer no call over a low-confidence or partial-coverage match.
"""


def _build_tool(metric_names: List[str]) -> dict:
    """Build the get_metric tool definition with enumerated metric names."""
    return {
        "name": "get_metric",
        "description": (
            "Match a user question to a certified metric and extract its parameters. "
            "Call this ONLY when a metric clearly fits. Do not call it for a low-confidence match."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": metric_names,
                    "description": "The certified metric name that best answers the question.",
                },
                "params": {
                    "type": "object",
                    "description": "Extracted parameters (period, grain, segment).",
                    "properties": {
                        "period": {
                            "type": "object",
                            "description": "Optional date range (end exclusive).",
                            "properties": {
                                "start": {"type": "string", "description": "YYYY-MM-DD"},
                                "end": {"type": "string", "description": "YYYY-MM-DD (exclusive)"},
                            },
                            "required": ["start", "end"],
                        },
                        "grain": {
                            "type": "string",
                            "enum": ["month", "week", "day"],
                            "description": "Time granularity, only for metrics with a grain choice.",
                        },
                        "segment": {
                            "type": "string",
                            "description": "Optional categorical segment value.",
                        },
                    },
                    "additionalProperties": True,
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "How confident you are this metric is the right match (0–1).",
                },
                "reason": {
                    "type": "string",
                    "description": "One-line rationale for the match.",
                },
            },
            "required": ["metric", "params", "confidence", "reason"],
        },
    }


def _call_claude_tool(
    registry: Registry,
    user_message: str,
) -> Optional[Dict[str, Any]]:
    """
    Call Claude with the get_metric tool. Returns the tool input dict when Claude
    calls the tool, or None when Claude produces a text response (no match).
    """
    import anthropic

    client = anthropic.Anthropic()
    metric_names = list(registry.metrics.keys())
    tool = _build_tool(metric_names)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_RESOLVER_SYSTEM,
        tools=[tool],
        # tool_choice="auto" is the default — Claude decides whether to call it
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "get_metric":
            return block.input  # validated by Anthropic against the tool schema

    return None  # no tool call → no match


def resolve(
    question: str,
    registry: Optional[Registry] = None,
    today: Optional[str] = None,
    min_confidence: float = 0.6,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return {metric, params, confidence, reason} for a match, or None.

    `today` (YYYY-MM-DD) anchors relative-date resolution; the caller supplies it.
    `history` is a list of {"role": "user"|"assistant", "content": "..."} dicts;
    the last 4 turns are included so the resolver can resolve pronouns and
    implicit context ("that program", "those users") from prior turns.
    """
    from datetime import date as _date

    registry = registry or load_registry()
    today = today or _date.today().isoformat()
    catalog = registry.catalog_for_resolver()

    import json
    context_block = ""
    if history:
        recent = history[-4:]  # last 2 user+assistant pairs
        lines = []
        for turn in recent:
            role = turn.get("role", "").upper()
            content = (turn.get("content") or "")[:300]
            lines.append(f"{role}: {content}")
        context_block = "PRIOR CONVERSATION:\n" + "\n".join(lines) + "\n\n"

    user_message = (
        f"TODAY: {today}\n\n"
        f"{context_block}"
        f"METRIC CATALOG:\n{json.dumps(catalog, indent=2)}\n\n"
        f"QUESTION: {question}"
    )

    tool_input = _call_claude_tool(registry, user_message)
    if not tool_input:
        return None

    name = tool_input.get("metric")
    if not name or registry.get(name) is None:
        return None

    if float(tool_input.get("confidence", 0)) < min_confidence:
        return None

    return {
        "metric": name,
        "params": tool_input.get("params") or {},
        "confidence": tool_input.get("confidence"),
        "reason": tool_input.get("reason", ""),
    }


def answer(
    question: str,
    today: Optional[str] = None,
    execute: bool = True,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Full metric path: resolve → render certified SQL → (optionally) execute.

    Returns a dict with `matched`. When matched and executed, includes the
    rendered `sql`, `rows`, and rendering hints (response_type/label/value) so a
    caller can format identically to the existing flow. When not matched, the
    caller should fall back to free-form text-to-SQL.
    """
    registry = load_registry()
    match = resolve(question, registry=registry, today=today, history=history)
    if not match:
        return {"matched": False}

    metric = registry.get(match["metric"])
    try:
        sql, resolved = render(metric, match["params"])
    except Exception as exc:  # noqa: BLE001 - bad params => fall back gracefully
        return {"matched": False, "resolver": match, "render_error": str(exc)}

    result = {
        "matched": True,
        "metric": metric.name,
        "tier": "certified" if metric.certified else "registered",
        "params": match["params"],
        "confidence": match.get("confidence"),
        "sql": sql,
        "response_type": metric.response_type,
        "label_column": metric.label_column,
        "value_column": metric.value_column,
        "source": metric.source,
    }
    if execute:
        from ..data_context.config import run_sql

        result["rows"] = run_sql(sql)
    return result
