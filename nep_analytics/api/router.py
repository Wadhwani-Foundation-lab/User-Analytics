"""
Route handlers for nep_analytics API.
Two-path dispatch:
  1. Semantic path — certified metric resolver (no LLM SQL generation)
  2. SQL generator path — Claude Opus generates SQL from natural language
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException

from ..core import config as cfg
from ..core.executor import execute
from ..core.formatter import (
    build_chart,
    build_table,
    extract_scalar,
    should_upgrade_to_table,
)
from ..core.interpreter import explain_empty_results, interpret_results
from ..core.sql_generator import (
    generate as sql_generate,
    mentions_completed_events,
    mentions_active_mentors,
    has_breakdown_language,
    wants_session_type_comparison,
    wants_explicit_scalar,
    wants_top_n,
)
from ..session.history import append_turn, get_history
from ..session.store import (
    create_session,
    delete_session,
    get_session_messages,
    list_sessions,
    save_message,
)
from .models import (
    ChatRequest,
    ChatResponse,
    ChartConfig,
    HealthResponse,
    HistoryResponse,
    Provenance,
    SessionCreateRequest,
    TableData,
)

router = APIRouter()


# ── Auth ─────────────────────────────────────────────────────────────────────

def _auth(x_api_key: str = Header(default="")) -> None:
    if cfg.API_SECRET_KEY and x_api_key != cfg.API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/api/health", response_model=HealthResponse, tags=["System"])
def health(_: None = Depends(_auth)):
    try:
        cfg.run_sql("SELECT 1 AS ping")
        connected = True
    except Exception:
        connected = False
    return HealthResponse(
        status="ok" if connected else "degraded",
        supabase_connected=connected,
        sql_gen_model=cfg.SQL_GEN_MODEL,
        interpreter_model=cfg.INTERPRET_MODEL,
        resolver_model=cfg.RESOLVER_MODEL,
    )


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest, _: None = Depends(_auth)):
    today = date.today().isoformat()

    # Merge server-side history with any client-provided history
    server_history = get_history(req.session_id)
    history = server_history or [h.model_dump() for h in req.history]

    # ── 1. Try semantic / certified path ─────────────────────────────────────
    provenance: Provenance | None = None
    sql: str = ""
    response_type: str = "text"
    nl_template: str = ""
    label_col: str = ""
    value_col: str = ""

    try:
        from ..semantic.resolver import resolve as sem_resolve
        from ..semantic.registry import load_registry
        from ..semantic.renderer import render as sem_render

        registry = load_registry()
        match = sem_resolve(req.question, registry=registry, today=today, history=history)

        if match:
            metric = registry.get(match["metric"])
            is_breakdown_metric = bool(metric.label_column)
            wants_breakdown = has_breakdown_language(req.question)
            # event_attendance_rate is naturally list-shaped: "attendance rate
            # for Round Table sessions in Liftoff-Propel" legitimately returns
            # one row per matching event without needing explicit "broken down
            # by" wording, since there are inherently multiple such events.
            # Its other bad case (comparing session types, which needs a
            # coarser sessiontype-level grain than this metric's per-event
            # rows) is handled separately below.
            exempt_from_shape_check = metric.response_type == "funnel_chart" or (
                metric.name == "event_attendance_rate" and not wants_explicit_scalar(req.question)
            )
            shape_mismatch = not exempt_from_shape_check and is_breakdown_metric != wants_breakdown
            if shape_mismatch:
                # Certified-metric analogue of the Rule 30 guard, applied both
                # directions: (a) a breakdown/chart metric (has a label column)
                # matched to a question with no breakdown language — e.g. "how
                # many users are pre-revenue" wrongly matching a
                # group-by-segment metric — or (b) the mirror case, a flat
                # scalar metric (no label column, can't group by anything)
                # matched to a ranking/breakdown question — e.g. "which month
                # had the highest signups" wrongly matching a plain
                # registration-count metric just because it contains the word
                # "signups". Either way the metric structurally cannot satisfy
                # the question's shape, and no amount of prompt wording fixes
                # a hardcoded SQL template — decline the match and fall
                # through to the free-form generator.
                match = None
                metric = None
            elif metric.name == "event_attendance_rate" and wants_session_type_comparison(req.question):
                # event_attendance_rate is hardcoded to GROUP BY event_id (one
                # row per event) — too fine-grained for a question that
                # explicitly compares session types. Decline and fall through
                # to the free-form generator, which produces a correct
                # sessiontype-level comparison per Rule 22/4b.
                match = None
                metric = None
            elif wants_top_n(req.question):
                # No certified metric can express "only the top N rows" — they
                # all have a fixed LIMIT 500. A "share top 5" follow-up would
                # otherwise re-match the same metric and re-render the full,
                # unfiltered breakdown. Decline and let the free-form
                # generator write an actual ORDER BY ... LIMIT N.
                match = None
                metric = None

        if match:
            params = dict(match["params"])
            if metric.choice("event_status") and not mentions_completed_events(req.question, history):
                # Deterministic override: prompt-level guidance alone proved
                # unreliable at keeping certified metrics from silently
                # defaulting to completed-only events (see sql_generator.py).
                params["event_status"] = "all"
            if metric.choice("user_status") and not mentions_active_mentors(req.question, history):
                # Same override, mirrored for mentor status.
                params["user_status"] = "all"
            rendered_sql, _ = sem_render(metric, params)
            sql = rendered_sql
            response_type = metric.response_type
            label_col = metric.label_column or ""
            value_col = metric.value_column or ""
            nl_template = f"Here is the {metric.name.replace('_', ' ')} data:"
            provenance = Provenance(
                certified=metric.certified,
                metric=metric.name,
                confidence=match.get("confidence"),
                metric_source=metric.source,
            )
    except Exception:
        # Semantic layer failure is non-fatal; fall through to SQL generator
        match = None

    # ── 2. SQL generator path (Opus) — used when semantic path misses ────────
    if not sql:
        try:
            gen = sql_generate(req.question, history=history, today=today)
        except EnvironmentError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=502, detail=f"SQL generator error: {e}")

        sql = gen["sql"]
        response_type = gen["response_type"]
        nl_template = gen["nl_answer_template"]
        label_col = gen["chart_label_column"]
        value_col = gen["chart_value_column"]

    # ── 3. Clarification — LLM chose not to generate SQL ─────────────────────
    if not sql:
        answer = nl_template or "Could you please clarify your question?"
        _persist(req.session_id, req.question, answer)
        return ChatResponse(
            answer=answer,
            response_type="text",
            session_id=req.session_id,
            provenance=provenance,
        )

    # ── 4. Execute SQL ────────────────────────────────────────────────────────
    try:
        rows = execute(sql)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e} | SQL: {sql}")

    # ── 5. Format response ────────────────────────────────────────────────────
    chart_config: ChartConfig | None = None
    table_data: TableData | None = None

    if response_type in ("bar_chart", "line_chart", "pie_chart", "funnel_chart"):
        if rows and label_col and value_col:
            chart_dict = build_chart(rows, response_type, label_col, value_col, nl_template)
            chart_config = ChartConfig(**chart_dict)
            answer = interpret_results(req.question, rows)
        else:
            response_type = "table"

    # Auto-upgrade text → table when rows have multiple columns/rows
    if should_upgrade_to_table(rows, response_type):
        response_type = "table"

    if response_type == "table" and rows:
        tbl = build_table(rows)
        table_data = TableData(**tbl)
        answer = interpret_results(req.question, rows)
    elif response_type == "table" and not rows:
        response_type = "text"
        answer = explain_empty_results(req.question, sql)
    elif response_type == "text":
        if rows:
            answer = extract_scalar(rows, nl_template)
        else:
            answer = explain_empty_results(req.question, sql)

    # ── 6. Persist to Supabase and in-memory session ──────────────────────────
    _persist(req.session_id, req.question, answer, response_type, sql,
             chart_config, table_data)

    return ChatResponse(
        answer=answer,
        response_type=response_type,
        chart_config=chart_config,
        table_data=table_data,
        sql_used=sql,
        session_id=req.session_id,
        provenance=provenance,
    )


def _persist(
    session_id: str,
    question: str,
    answer: str,
    response_type: str = "text",
    sql: str | None = None,
    chart_config: ChartConfig | None = None,
    table_data: TableData | None = None,
) -> None:
    """Fire-and-forget: update in-memory history and write to Supabase."""
    append_turn(session_id, "user", question)
    append_turn(session_id, "assistant", answer)
    try:
        save_message(session_id, "user", question)
        save_message(
            session_id,
            "assistant",
            answer,
            response_type=response_type,
            chart_config=chart_config.model_dump() if chart_config else None,
            table_data=table_data.model_dump() if table_data else None,
            sql_used=sql,
        )
    except Exception as exc:
        print(f"[WARN] nep_analytics: failed to persist message: {exc}")


# ── Session endpoints ─────────────────────────────────────────────────────────

@router.get("/api/history/{session_id}", response_model=HistoryResponse, tags=["Session"])
def get_session_history(session_id: str, _: None = Depends(_auth)):
    history = get_history(session_id)
    return HistoryResponse(
        session_id=session_id,
        history=[{"role": t["role"], "content": t["content"]} for t in history],
    )


@router.delete("/api/history/{session_id}", tags=["Session"])
def clear_session_history(session_id: str, _: None = Depends(_auth)):
    from ..session.history import clear_session
    clear_session(session_id)
    return {"message": "Session cleared.", "session_id": session_id}


@router.post("/api/sessions", tags=["Sessions"])
def create_session_route(req: SessionCreateRequest, _: None = Depends(_auth)):
    try:
        create_session(req.session_id, req.title)
        return {"id": req.session_id, "title": req.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/sessions", tags=["Sessions"])
def list_sessions_route(_: None = Depends(_auth)):
    try:
        return list_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/sessions/{session_id}/messages", tags=["Sessions"])
def get_messages_route(session_id: str, _: None = Depends(_auth)):
    try:
        return get_session_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/sessions/{session_id}", tags=["Sessions"])
def delete_session_route(session_id: str, _: None = Depends(_auth)):
    try:
        delete_session(session_id)
        return {"message": "Session deleted.", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
