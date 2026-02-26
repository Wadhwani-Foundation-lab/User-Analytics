"""
Supabase-backed chat session & message store.
Tables required (run migration SQL in Supabase SQL Editor):
  - nep_chat_sessions   (id uuid, title text, created_at, updated_at)
  - nep_chat_messages   (id uuid, session_id uuid FK, role, content,
                         response_type, chart_config jsonb, table_data jsonb,
                         sql_used text, created_at)
"""
from __future__ import annotations
import os
import json
from typing import Optional
from supabase import create_client, Client

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        _client = create_client(url, key)
    return _client


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(title: str) -> dict:
    """Insert a new session row and return it."""
    db = _get_client()
    short_title = title[:80]
    res = (
        db.table("nep_chat_sessions")
        .insert({"title": short_title})
        .execute()
    )
    return res.data[0] if res.data else {}


def create_session_with_id(session_id: str, title: str) -> dict:
    """Insert a session with a specific UUID (provided by the frontend)."""
    db = _get_client()
    short_title = title[:80]
    # Upsert so repeated calls (e.g. on reconnect) are safe
    res = (
        db.table("nep_chat_sessions")
        .upsert({"id": session_id, "title": short_title})
        .execute()
    )
    return res.data[0] if res.data else {}


def list_sessions(limit: int = 30) -> list[dict]:
    """Return the most recent sessions, newest first."""
    db = _get_client()
    res = (
        db.table("nep_chat_sessions")
        .select("id, title, created_at, updated_at")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def touch_session(session_id: str) -> None:
    """Update updated_at timestamp on a session."""
    db = _get_client()
    db.table("nep_chat_sessions").update(
        {"updated_at": "now()"}
    ).eq("id", session_id).execute()


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(
    session_id: str,
    role: str,
    content: str,
    response_type: Optional[str] = None,
    chart_config: Optional[dict] = None,
    table_data: Optional[dict] = None,
    sql_used: Optional[str] = None,
) -> None:
    """Persist a single message turn to Supabase."""
    db = _get_client()
    row: dict = {
        "session_id": session_id,
        "role": role,
        "content": content,
    }
    if response_type:
        row["response_type"] = response_type
    if chart_config:
        row["chart_config"] = json.dumps(chart_config)
    if table_data:
        row["table_data"] = json.dumps(table_data)
    if sql_used:
        row["sql_used"] = sql_used

    db.table("nep_chat_messages").insert(row).execute()
    touch_session(session_id)


def get_session_messages(session_id: str) -> list[dict]:
    """Return all messages for a session, ordered by created_at."""
    db = _get_client()
    res = (
        db.table("nep_chat_messages")
        .select("id, role, content, response_type, chart_config, table_data, sql_used, created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    rows = res.data or []
    # Deserialise JSONB fields that Supabase may return as strings
    for row in rows:
        for field in ("chart_config", "table_data"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    row[field] = None
    return rows
