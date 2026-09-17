"""
Central configuration for nep_analytics.
Loads credentials from chat_api/.env (shared with the rest of the repo).
No secrets are hardcoded here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client
import anthropic as _anthropic_sdk

# Locate repo root: this file is at nep_analytics/core/config.py
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = REPO_ROOT / "chat_api" / ".env"
load_dotenv(_ENV_PATH, override=False)

# ── Credentials ─────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "")

# ── Model names ──────────────────────────────────────────────────────────────
SQL_GEN_MODEL: str = os.getenv("SQL_GEN_MODEL", "claude-opus-5")
INTERPRET_MODEL: str = os.getenv("INTERPRET_MODEL", "claude-sonnet-5")
RESOLVER_MODEL: str = os.getenv("RESOLVER_MODEL", "claude-sonnet-5")

# ── Server settings ──────────────────────────────────────────────────────────
ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")
MAX_RESULT_ROWS: int = int(os.getenv("MAX_RESULT_ROWS", "500"))

# ── Lazy singletons ──────────────────────────────────────────────────────────
_supabase: Client | None = None
_anthropic: _anthropic_sdk.Anthropic | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase


def get_anthropic() -> _anthropic_sdk.Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = _anthropic_sdk.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic


def run_sql(sql: str) -> list[dict]:
    """Execute a read-only SELECT via the Supabase execute_sql RPC."""
    sql = sql.rstrip(";").strip()
    result = get_supabase().rpc("execute_sql", {"query": sql}).execute()
    return result.data or []
