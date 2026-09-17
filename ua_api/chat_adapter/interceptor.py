"""
Certified-metric intercept layer.

try_certified_answer() is the single entry point.  It:
  1. Calls metrics.resolver.answer() — one LLM classification call.
  2. On match: formats the full ChatResponse (chart / table / text).
  3. Persists the exchange to Supabase (same nep_chat_messages table chat_api uses).
  4. Returns a ChatResponse dict, or None if no metric matched.

None means "fall through to the upstream chat_api" — never an error.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .formatter import CHART_RESPONSE_TYPES, build_chart, build_table
from .interpreter import explain_empty_results, interpret_results
from .models import ChatResponse, Provenance

log = logging.getLogger(__name__)


# ── Supabase session persistence ─────────────────────────────────────────────

def _persist(
    session_id: str,
    question: str,
    answer: str,
    response_type: str,
    chart_config,
    table_data,
    sql: str,
) -> None:
    """Write user + assistant turns to nep_chat_messages (fire-and-forget)."""
    try:
        from ..data_context.config import get_client

        db = get_client()
        db.table("nep_chat_messages").insert({
            "session_id": session_id,
            "role": "user",
            "content": question,
        }).execute()
        row: Dict[str, Any] = {
            "session_id": session_id,
            "role": "assistant",
            "content": answer,
            "response_type": response_type,
        }
        if sql:
            row["sql_used"] = sql
        if chart_config:
            row["chart_config"] = json.dumps(chart_config.model_dump())
        if table_data:
            row["table_data"] = json.dumps(table_data.model_dump())
        db.table("nep_chat_messages").insert(row).execute()
        db.table("nep_chat_sessions").update(
            {"updated_at": "now()"}
        ).eq("id", session_id).execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("chat_adapter: failed to persist session %s: %s", session_id, exc)


# ── Core intercept ────────────────────────────────────────────────────────────

def try_certified_answer(
    question: str,
    session_id: str,
    today: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[ChatResponse]:
    """
    Attempt to answer using a certified metric.

    Returns a fully-formed ChatResponse on match, or None when the question
    doesn't map to any certified metric (caller should fall back to chat_api).
    `history` — list of {"role", "content"} dicts from prior turns; passed to
    the resolver so it can resolve pronouns and implicit context.
    """
    today = today or date.today().isoformat()

    # ── 1. Resolve metric ────────────────────────────────────────────────────
    try:
        from ..metrics.resolver import answer as metrics_answer
        result: Dict[str, Any] = metrics_answer(question, today=today, history=history)
    except Exception as exc:  # noqa: BLE001
        log.warning("chat_adapter: metrics resolver error, falling back: %s", exc)
        return None

    if not result.get("matched"):
        return None

    rows: List[Dict[str, Any]] = result.get("rows") or []
    response_type: str = result.get("response_type", "table")
    label_col: str = result.get("label_column") or ""
    value_col: str = result.get("value_column") or ""
    sql: str = result.get("sql", "")
    metric_name: str = result.get("metric", "result")

    log.info(
        "chat_adapter: certified metric '%s' matched (confidence=%.2f)",
        metric_name,
        result.get("confidence", 0),
    )

    # ── 2. Format response (mirrors chat_api/main.py step 5) ─────────────────
    chart_config = None
    table_data = None

    if response_type in CHART_RESPONSE_TYPES:
        if rows and label_col and value_col:
            chart_config = build_chart(rows, response_type, label_col, value_col)
        else:
            response_type = "table"

    # Auto-upgrade text → table when multiple cols / multiple rows
    if response_type == "text" and rows:
        num_cols = len(rows[0].keys()) if rows else 0
        if num_cols > 1 or len(rows) > 1:
            response_type = "table"

    if response_type == "table" and rows:
        table_data = build_table(rows)

    # ── 3. Generate prose answer ─────────────────────────────────────────────
    try:
        if response_type in CHART_RESPONSE_TYPES and rows:
            answer_text = interpret_results(question, rows)
        elif response_type == "table" and rows:
            answer_text = interpret_results(question, rows)
        elif response_type == "table" and not rows:
            response_type = "text"
            answer_text = explain_empty_results(question, sql)
        elif response_type == "text" and rows:
            first_val = list(rows[0].values())[0] if rows[0] else None
            answer_text = (
                f"**{first_val}**" if first_val is not None
                else "No data found for that query."
            )
        else:
            answer_text = "No data found for that query."
    except Exception as exc:  # noqa: BLE001
        log.warning("chat_adapter: interpretation failed, using fallback text: %s", exc)
        answer_text = f"Here are the {metric_name.replace('_', ' ')} results."

    # ── 4. Persist to Supabase (fire-and-forget) ─────────────────────────────
    _persist(session_id, question, answer_text, response_type, chart_config, table_data, sql)

    return ChatResponse(
        answer=answer_text,
        response_type=response_type,  # type: ignore[arg-type]
        chart_config=chart_config,
        table_data=table_data,
        sql_used=sql,
        session_id=session_id,
        provenance=Provenance(
            certified=True,
            metric=metric_name,
            confidence=result.get("confidence"),
            metric_source=result.get("source"),
        ),
    )
