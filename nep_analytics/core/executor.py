"""
SQL executor — safety guard + Supabase RPC execution.
Only SELECT statements are allowed through.
"""
from __future__ import annotations

import re

from .config import run_sql as _run_sql


_FORBIDDEN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)",
    re.IGNORECASE,
)


def execute(sql: str) -> list[dict]:
    """
    Execute sql through the Supabase execute_sql RPC.
    Raises PermissionError for any non-SELECT statement.
    Raises RuntimeError on DB-level errors.
    """
    cleaned = sql.strip()
    if not cleaned:
        raise ValueError("Empty SQL string")

    if _FORBIDDEN.match(cleaned):
        raise PermissionError(f"Only SELECT statements are allowed. Got: {cleaned[:60]}")

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        raise PermissionError(f"Only SELECT statements are allowed. Got: {cleaned[:60]}")

    try:
        return _run_sql(cleaned)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
