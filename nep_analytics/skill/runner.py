"""
AnalyticsSkill — reusable interface for the nep_analytics engine.
Import and call from any Python service: dashboards, Slack bots, scheduled reports.

Usage:
    from nep_analytics.skill import AnalyticsSkill

    skill = AnalyticsSkill()
    response = await skill.ask("how many MAU in Q1 2026?")
    print(response.answer)
    print(response.response_type)  # text | table | bar_chart | line_chart | ...
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

from ..core.config import run_sql as _run_sql, SQL_GEN_MODEL
from ..core.executor import execute
from ..core.formatter import build_chart, build_table, extract_scalar, should_upgrade_to_table
from ..core.interpreter import explain_empty_results, interpret_results
from ..core.sql_generator import generate as sql_generate
from ..session.history import append_turn, clear_session, get_history


class AnalyticsResponse:
    """Structured response from the analytics skill."""

    def __init__(
        self,
        answer: str,
        response_type: str,
        sql_used: Optional[str] = None,
        chart_config: Optional[dict] = None,
        table_data: Optional[dict] = None,
        provenance: Optional[dict] = None,
        session_id: Optional[str] = None,
    ):
        self.answer = answer
        self.response_type = response_type
        self.sql_used = sql_used
        self.chart_config = chart_config
        self.table_data = table_data
        self.provenance = provenance
        self.session_id = session_id

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "response_type": self.response_type,
            "sql_used": self.sql_used,
            "chart_config": self.chart_config,
            "table_data": self.table_data,
            "provenance": self.provenance,
            "session_id": self.session_id,
        }


class AnalyticsSkill:
    """
    Plug-and-play analytics skill for the NEP platform.

    Provides a single ask() method that:
    1. Tries the certified semantic path (no LLM SQL generation)
    2. Falls back to Claude Opus SQL generation
    3. Executes against Supabase
    4. Returns a structured AnalyticsResponse

    Thread-safe: each instance holds no mutable state beyond session_id.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or "skill-default"

    def ask(self, question: str, today: Optional[str] = None) -> AnalyticsResponse:
        """Synchronous ask. Runs the full analytics pipeline and returns a response."""
        today = today or date.today().isoformat()
        history = get_history(self.session_id)

        provenance = None
        sql = ""
        response_type = "text"
        nl_template = ""
        label_col = ""
        value_col = ""

        # ── Certified metric path ──────────────────────────────────────────
        try:
            from ..semantic.resolver import resolve
            from ..semantic.registry import load_registry
            from ..semantic.renderer import render

            registry = load_registry()
            match = resolve(question, registry=registry, today=today, history=history)
            if match:
                metric = registry.get(match["metric"])
                rendered_sql, _ = render(metric, match["params"])
                sql = rendered_sql
                response_type = metric.response_type
                label_col = metric.label_column or ""
                value_col = metric.value_column or ""
                nl_template = f"Here is the {metric.name.replace('_', ' ')} data:"
                provenance = {
                    "certified": metric.certified,
                    "metric": metric.name,
                    "confidence": match.get("confidence"),
                    "metric_source": metric.source,
                }
        except Exception:
            match = None

        # ── SQL generator path (Opus) ──────────────────────────────────────
        if not sql:
            gen = sql_generate(question, history=history, today=today)
            sql = gen["sql"]
            response_type = gen["response_type"]
            nl_template = gen["nl_answer_template"]
            label_col = gen["chart_label_column"]
            value_col = gen["chart_value_column"]

        # ── Clarification ──────────────────────────────────────────────────
        if not sql:
            answer = nl_template or "Could you please clarify your question?"
            append_turn(self.session_id, "user", question)
            append_turn(self.session_id, "assistant", answer)
            return AnalyticsResponse(
                answer=answer,
                response_type="text",
                provenance=provenance,
                session_id=self.session_id,
            )

        # ── Execute ────────────────────────────────────────────────────────
        rows = execute(sql)

        # ── Format ────────────────────────────────────────────────────────
        chart_config = None
        table_data = None

        if response_type in ("bar_chart", "line_chart", "pie_chart", "funnel_chart"):
            if rows and label_col and value_col:
                chart_config = build_chart(rows, response_type, label_col, value_col, nl_template)
                answer = interpret_results(question, rows)
            else:
                response_type = "table"

        if should_upgrade_to_table(rows, response_type):
            response_type = "table"

        if response_type == "table" and rows:
            table_data = build_table(rows)
            answer = interpret_results(question, rows)
        elif response_type == "table" and not rows:
            response_type = "text"
            answer = explain_empty_results(question, sql)
        elif response_type == "text":
            answer = extract_scalar(rows, nl_template) if rows else explain_empty_results(question, sql)

        append_turn(self.session_id, "user", question)
        append_turn(self.session_id, "assistant", answer)

        return AnalyticsResponse(
            answer=answer,
            response_type=response_type,
            sql_used=sql,
            chart_config=chart_config,
            table_data=table_data,
            provenance=provenance,
            session_id=self.session_id,
        )

    async def ask_async(self, question: str, today: Optional[str] = None) -> AnalyticsResponse:
        """Async wrapper — runs ask() in a thread pool so it's non-blocking."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.ask, question, today)

    def new_session(self, session_id: str) -> "AnalyticsSkill":
        """Return a new skill instance with a different session context."""
        return AnalyticsSkill(session_id=session_id)

    def reset(self) -> None:
        """Clear in-memory history for this session."""
        clear_session(self.session_id)
