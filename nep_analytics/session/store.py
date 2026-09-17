"""
Supabase-backed session and message persistence.
Uses the same nep_chat_sessions / nep_chat_messages tables as the rest of the repo.
All writes are intended to be called fire-and-forget from the router.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.config import get_supabase

_SESSIONS_TABLE = "nep_chat_sessions"
_MESSAGES_TABLE = "nep_chat_messages"


def create_session(session_id: str, title: str) -> None:
    get_supabase().table(_SESSIONS_TABLE).insert(
        {"id": session_id, "title": title}
    ).execute()


def list_sessions(limit: int = 20) -> List[Dict]:
    result = (
        get_supabase()
        .table(_SESSIONS_TABLE)
        .select("id, title, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def delete_session(session_id: str) -> None:
    get_supabase().table(_SESSIONS_TABLE).delete().eq("id", session_id).execute()


def save_message(
    session_id: str,
    role: str,
    content: str,
    response_type: str = "text",
    chart_config: Optional[Dict] = None,
    table_data: Optional[Dict] = None,
    sql_used: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "response_type": response_type,
    }
    if chart_config is not None:
        payload["chart_config"] = chart_config
    if table_data is not None:
        payload["table_data"] = table_data
    if sql_used is not None:
        payload["sql_used"] = sql_used

    get_supabase().table(_MESSAGES_TABLE).insert(payload).execute()


def get_session_messages(session_id: str) -> List[Dict]:
    result = (
        get_supabase()
        .table(_MESSAGES_TABLE)
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return result.data or []
