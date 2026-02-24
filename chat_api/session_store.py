"""
In-memory conversation history store, keyed by session_id.
Each session stores a rolling list of { role, content } turns.
"""
from __future__ import annotations
from typing import Dict, List
from collections import defaultdict
import os

MAX_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))

# { session_id: [{ "role": "user"|"assistant", "content": "..." }, ...] }
_store: Dict[str, List[dict]] = defaultdict(list)


def get_history(session_id: str) -> List[dict]:
    """Return last MAX_TURNS pairs (MAX_TURNS * 2 items) for a session."""
    return _store[session_id][-(MAX_TURNS * 2):]


def append_turn(session_id: str, role: str, content: str) -> None:
    """Append a single turn to a session's history."""
    _store[session_id].append({"role": role, "content": content})


def clear_session(session_id: str) -> None:
    """Remove all history for a session."""
    _store[session_id] = []


def session_exists(session_id: str) -> bool:
    return session_id in _store and len(_store[session_id]) > 0
