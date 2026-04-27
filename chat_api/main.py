"""
FastAPI application — NEP Analytics Chat API
All UI data interactions are routed through this API.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

from typing import Optional  # noqa: F401 — kept for forward-compat
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from models import ChatRequest, ChatResponse, HistoryResponse, HealthResponse, TableData
from system_prompt import SYSTEM_PROMPT
from llm_client import ask, ask_with_cached_sql
from supabase_runner import execute, test_connection
from session_store import get_history, append_turn, clear_session
from chart_formatter import format_chart
import chat_history_store as chs
import sql_cache

# ─── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NEP Analytics Chat API",
    description="Internal AI chat API for NEP platform user analytics.",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

# ─── Auth dependency ────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """Validates the x-api-key header if API_SECRET_KEY is configured."""
    if API_SECRET_KEY and x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health(_: None = Depends(verify_api_key)):
    """Health check — confirms API is up and Supabase is reachable."""
    connected = test_connection()
    return HealthResponse(
        status="ok" if connected else "degraded",
        supabase_connected=connected,
        llm_model="claude-sonnet-4-5",
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest, _: None = Depends(verify_api_key)):
    """
    Main chat endpoint.
    Accepts a natural-language question and conversation history,
    returns an AI-generated answer (text, table, or chart).
    """
    # ── 1. Build history ────────────────────────────────────────────────────────
    server_history = get_history(req.session_id)
    history = server_history if server_history else [h.model_dump() for h in req.history]

    # ── 2. Call Claude (or use cached SQL) ──────────────────────────────────────
    cached_sql = sql_cache.get(req.question)
    try:
        if cached_sql:
            llm_result = ask_with_cached_sql(SYSTEM_PROMPT, history, req.question, cached_sql)
        else:
            llm_result = ask(SYSTEM_PROMPT, history, req.question)
    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM response could not be parsed: {str(e)}",
        )

    sql: str = llm_result.get("sql", "").strip()
    response_type: str = llm_result.get("response_type", "text")
    nl_template: str = llm_result.get("nl_answer_template", "")
    label_col: str = llm_result.get("chart_label_column", "")
    value_col: str = llm_result.get("chart_value_column", "")

    # ── 3. Handle clarification (LLM chose not to run SQL) ─────────────────────
    if not sql:
        answer = nl_template or "Could you please clarify your question?"
        append_turn(req.session_id, "user", req.question)
        append_turn(req.session_id, "assistant", answer)
        return ChatResponse(
            answer=answer,
            response_type="text",
            session_id=req.session_id,
        )

    # ── 4. Execute SQL ──────────────────────────────────────────────────────────
    print(f"\n[SQL GENERATED]\n{sql}\n")  # Log generated SQL for debugging
    try:
        rows = execute(sql)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)} | SQL: {sql}",
        )

    # ── 4b. Populate cache on first successful execution ────────────────────────
    if not cached_sql and sql:
        sql_cache.set(req.question, sql)

    # ── 5. Format response ──────────────────────────────────────────────────────
    chart_config = None
    table_data = None
    answer = nl_template

    if response_type in ("bar_chart", "line_chart", "pie_chart"):
        if rows and label_col and value_col:
            chart_config = format_chart(rows, response_type, label_col, value_col, nl_template)
        else:
            response_type = "table"

    # Auto-upgrade: if LLM said "text" but rows have multiple columns or multiple
    # rows, render as a table so data is never hidden from the user.
    if response_type == "text" and rows:
        num_cols = len(rows[0].keys()) if rows else 0
        if num_cols > 1 or len(rows) > 1:
            response_type = "table"

    if response_type == "table" and rows:
        columns = list(rows[0].keys())
        table_data = TableData(
            columns=columns,
            rows=[[row.get(c) for c in columns] for row in rows],
        )

    elif response_type == "text":
        if rows:
            first_val = list(rows[0].values())[0] if rows[0] else None
            if first_val is not None:
                str_val = str(first_val)
                # Substitute {result} placeholder inline for a natural sentence,
                # fall back to bolded suffix if the template has no placeholder.
                if "{result}" in nl_template:
                    answer = nl_template.replace("{result}", f"**{str_val}**")
                else:
                    answer = f"{nl_template} **{str_val}**"
            else:
                answer = nl_template or "No data found for that query."
        else:
            answer = "No data found for that query."

    # ── 6. Update session (in-memory + Supabase) ────────────────────────────────
    append_turn(req.session_id, "user", req.question)
    append_turn(req.session_id, "assistant", answer)

    # Persist to Supabase (fire-and-forget — don't fail the response if DB is down)
    try:
        chart_dict = chart_config.model_dump() if chart_config else None
        table_dict = table_data.model_dump() if table_data else None
        chs.save_message(req.session_id, "user", req.question)
        chs.save_message(
            req.session_id, "assistant", answer,
            response_type=response_type,
            chart_config=chart_dict,
            table_data=table_dict,
            sql_used=sql if sql else None,
        )
    except Exception as e:
        print(f"[WARN] Failed to persist message to Supabase: {e}")

    return ChatResponse(
        answer=answer,
        response_type=response_type,
        chart_config=chart_config,
        table_data=table_data,
        sql_used=sql,
        session_id=req.session_id,
    )


@app.get("/api/history/{session_id}", response_model=HistoryResponse, tags=["Session"])
def get_session_history(session_id: str, _: None = Depends(verify_api_key)):
    """Retrieve the full conversation history for a session."""
    history = get_history(session_id)
    return HistoryResponse(session_id=session_id, history=history)


@app.delete("/api/history/{session_id}", tags=["Session"])
def clear_session_history(session_id: str, _: None = Depends(verify_api_key)):
    """Clear all conversation history for a session (e.g. New Chat)."""
    clear_session(session_id)
    return {"message": "Session cleared.", "session_id": session_id}


# ── Chat Sessions (Supabase-backed) ────────────────────────────────────────────

from pydantic import BaseModel as _BM

class SessionCreateRequest(_BM):
    session_id: str
    title: str


@app.post("/api/sessions", tags=["Sessions"])
def create_session(req: SessionCreateRequest, _: None = Depends(verify_api_key)):
    """Register a new named chat session in Supabase."""
    try:
        chs.create_session_with_id(req.session_id, req.title)
        return {"id": req.session_id, "title": req.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions", tags=["Sessions"])
def list_sessions(_: None = Depends(verify_api_key)):
    """Return recent chat sessions."""
    try:
        return chs.list_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/messages", tags=["Sessions"])
def get_messages(session_id: str, _: None = Depends(verify_api_key)):
    """Return all messages for a session."""
    try:
        return chs.get_session_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── SQL Cache admin ─────────────────────────────────────────────────────────────

@app.get("/api/cache/stats", tags=["Cache"])
def cache_stats(_: None = Depends(verify_api_key)):
    """Return SQL cache hit/miss statistics."""
    return sql_cache.stats()


@app.get("/api/cache/entries", tags=["Cache"])
def cache_entries(_: None = Depends(verify_api_key)):
    """List all cached question→SQL entries."""
    return sql_cache.list_entries()


@app.delete("/api/cache", tags=["Cache"])
def cache_clear(_: None = Depends(verify_api_key)):
    """Flush the entire SQL cache."""
    sql_cache.clear()
    return {"message": "Cache cleared."}


@app.delete("/api/cache/entry", tags=["Cache"])
def cache_invalidate(question: str, _: None = Depends(verify_api_key)):
    """Remove a specific question from the cache."""
    removed = sql_cache.invalidate(question)
    return {"removed": removed, "question": question}
