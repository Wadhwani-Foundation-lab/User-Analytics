"""
Central configuration and connection handling for data_context.

Credentials are read from the environment ONLY. This replaces the leaked,
hardcoded Supabase service key that previously lived in upload_to_supabase.py
and verify_upload.py. By default we also load chat_api/.env so the module
shares the backend's existing configuration.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv

# Repo layout anchors --------------------------------------------------------
MODULE_DIR = Path(__file__).resolve().parent
# Module now lives at <repo>/ua_api/data_context, so the repo root is two up.
REPO_ROOT = MODULE_DIR.parent.parent
CATALOG_DIR = MODULE_DIR / "catalog" / "tables"
MIGRATIONS_DIR = MODULE_DIR / "migrations"
REPORTS_DIR = MODULE_DIR / "reports"
CSV_DIR = REPO_ROOT / "csvfiles"

# Metadata table that records load provenance / freshness.
CATALOG_TABLE = "nep_data_catalog"

# The analytics tables are owned by this role (an Airflow ETL loader), not
# postgres. COMMENT and CREATE INDEX require table ownership, so the generated
# DDL runs them via SET ROLE <owner>. postgres is a member of this role, so the
# SQL editor can assume it. Override if the owning role differs.
OWNER_ROLE = os.getenv("ANALYTICS_TABLE_OWNER", "airflow_loader")

# Load env from chat_api/.env (shared with the backend) unless already set.
_DEFAULT_ENV = REPO_ROOT / "chat_api" / ".env"
if _DEFAULT_ENV.exists():
    load_dotenv(_DEFAULT_ENV, override=False)
load_dotenv(override=False)  # also pick up a process-level .env if present

_supabase: Optional[Any] = None


def supabase_url() -> str:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise EnvironmentError("SUPABASE_URL is not set in the environment.")
    return url


def supabase_key() -> str:
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not key:
        raise EnvironmentError("SUPABASE_SERVICE_KEY is not set in the environment.")
    return key


def get_client():
    """Return a cached Supabase client built from environment credentials."""
    global _supabase
    if _supabase is None:
        from supabase import create_client

        _supabase = create_client(supabase_url(), supabase_key())
    return _supabase


def run_sql(query: str) -> List[dict]:
    """
    Run a read-only SELECT through the existing `execute_sql` RPC and return
    rows as a list of dicts. Mirrors chat_api/supabase_runner so data_context
    stays self-contained but uses the same trusted read path.
    """
    client = get_client()
    response = client.rpc("execute_sql", {"query": query.rstrip(";").strip()}).execute()
    data = response.data
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def scalar(query: str, key: str = "value") -> Any:
    """Convenience: run a query expected to return a single row/column."""
    rows = run_sql(query)
    if not rows:
        return None
    row = rows[0]
    if key in row:
        return row[key]
    # fall back to the first column whatever it is named
    return next(iter(row.values()), None)
