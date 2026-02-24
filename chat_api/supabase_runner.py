"""
Read-only SQL executor that runs queries against Supabase.
Uses an RPC function (execute_sql) on the Supabase database.
Blocks all non-SELECT operations before sending to the database.
"""
from __future__ import annotations
from typing import Optional, List
import os
import re

from supabase import create_client, Client

_supabase: Optional[Client] = None

BLOCKED_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|CALL)\b",
    re.IGNORECASE,
)

MAX_ROWS = int(os.getenv("MAX_RESULT_ROWS", 500))


def _get_client() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment."
            )
        _supabase = create_client(url, key)
    return _supabase


def execute(sql: str) -> List[dict]:
    """
    Execute a SELECT SQL query and return results as a list of dicts.
    Raises PermissionError for any non-SELECT query.
    """
    stripped = sql.strip()

    # Block dangerous operations
    if BLOCKED_PATTERN.search(stripped):
        raise PermissionError(
            "Only SELECT queries are permitted. Destructive SQL was detected."
        )

    upper = stripped.upper()

    # Allow queries starting with SELECT or WITH (CTEs like WITH cte AS (...) SELECT ...)
    # Block everything else — only these two forms are safe read-only queries
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise PermissionError(
            "Query must begin with SELECT (or WITH for CTEs). Only read-only queries are allowed."
        )

    # For plain SELECT queries, append LIMIT if not already present.
    # For CTEs (WITH ...) Claude is instructed to include LIMIT in the final SELECT —
    # we trust the LLM's LIMIT and don't try to inject one into the CTE structure.
    if upper.startswith("SELECT") and "LIMIT" not in upper:
        stripped = stripped.rstrip(";") + f" LIMIT {MAX_ROWS}"

    # Always strip trailing semicolon — the execute_sql RPC wraps the query
    # inside FROM (...) t subquery, so a semicolon inside it is a syntax error
    stripped = stripped.rstrip(";").strip()

    client = _get_client()

    # Call the execute_sql RPC function in Supabase
    response = client.rpc("execute_sql", {"query": stripped}).execute()

    data = response.data
    if data is None:
        return []

    # The RPC returns json_agg result — may be a list or a single dict
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return [data]
    else:
        return []


def test_connection() -> bool:
    """Quick connectivity check — returns True if Supabase is reachable."""
    try:
        client = _get_client()
        client.rpc("execute_sql", {"query": "SELECT 1 AS ok LIMIT 1;"}).execute()
        return True
    except Exception:
        return False
