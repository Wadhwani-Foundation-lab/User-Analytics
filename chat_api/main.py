"""
FastAPI application — NEP Analytics Chat API
All UI data interactions are routed through this API.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from models import ChatRequest, ChatResponse, HistoryResponse, HealthResponse, TableData
from system_prompt import SYSTEM_PROMPT
from llm_client import ask
from supabase_runner import execute, test_connection
from session_store import get_history, append_turn, clear_session
from chart_formatter import format_chart

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

    # ── 2. Call Claude ──────────────────────────────────────────────────────────
    try:
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
                answer = f"{nl_template} **{first_val}**"
            else:
                answer = nl_template or "No data found for that query."
        else:
            answer = "No data found for that query."

    # ── 6. Update session ───────────────────────────────────────────────────────
    append_turn(req.session_id, "user", req.question)
    append_turn(req.session_id, "assistant", answer)

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
