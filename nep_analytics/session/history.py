"""
In-memory conversation history per session.
Provides fast read access for the SQL generator without a DB round-trip per turn.
Supabase is the durable store; this is the hot cache.
"""
from __future__ import annotations

from typing import Dict, List

_store: Dict[str, List[Dict]] = {}
_MAX_TURNS = 20


def get_history(session_id: str) -> List[Dict]:
    return list(_store.get(session_id, []))


def append_turn(session_id: str, role: str, content: str) -> None:
    turns = _store.setdefault(session_id, [])
    turns.append({"role": role, "content": content})
    # Keep only the most recent N turns to bound memory and token usage
    if len(turns) > _MAX_TURNS:
        _store[session_id] = turns[-_MAX_TURNS:]


def clear_session(session_id: str) -> None:
    _store.pop(session_id, None)
