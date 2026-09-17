"""
data_context API layer — a freshness-aware health surface.

This is a NEW, self-contained module. It does not modify chat_api. Use it two ways:

  1. Standalone:   uvicorn data_context.api.main:app --port 8001
  2. Mounted into the existing app WITHOUT editing chat_api source:
         from data_context.api.main import router as data_context_router
         app.include_router(data_context_router)

It reads load provenance from the nep_data_catalog table (created by
migrations/001) through the read-only execute_sql RPC, and degrades gracefully
when that table has not been provisioned yet.
"""
from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, FastAPI

from ..config import CATALOG_TABLE, run_sql
from .models import FreshnessResponse, HealthResponse, TableFreshness

# Model id is read from env so this module owns no hardcoded provider string.
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")

router = APIRouter(tags=["DataContext"])


def _check_connection() -> bool:
    try:
        run_sql("SELECT 1 AS ok")
        return True
    except Exception:
        return False


def _read_freshness() -> tuple[bool, List[TableFreshness]]:
    """Return (catalog_provisioned, rows). provisioned=False means the
    nep_data_catalog table does not exist yet."""
    try:
        rows = run_sql(
            f"SELECT table_name, row_count, source_file, last_loaded_at, load_status "
            f"FROM {CATALOG_TABLE} ORDER BY last_loaded_at DESC NULLS LAST"
        )
    except Exception:
        return False, []

    freshness = [
        TableFreshness(
            table_name=r.get("table_name"),
            row_count=r.get("row_count"),
            source_file=r.get("source_file"),
            last_loaded_at=str(r["last_loaded_at"]) if r.get("last_loaded_at") else None,
            load_status=r.get("load_status"),
        )
        for r in rows
    ]
    return True, freshness


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check — API up, Supabase reachable, and per-table data freshness."""
    connected = _check_connection()
    provisioned, freshness = _read_freshness() if connected else (False, [])
    return HealthResponse(
        status="ok" if connected else "degraded",
        supabase_connected=connected,
        llm_model=LLM_MODEL,
        catalog_provisioned=provisioned,
        data_freshness=freshness,
    )


@router.get("/api/freshness", response_model=FreshnessResponse)
def freshness() -> FreshnessResponse:
    """Per-table load provenance / freshness from nep_data_catalog."""
    provisioned, rows = _read_freshness()
    return FreshnessResponse(catalog_provisioned=provisioned, tables=rows)


# Standalone app (uvicorn data_context.api.main:app)
app = FastAPI(
    title="NEP data_context API",
    description="Freshness-aware health surface for the data foundation layer.",
    version="0.1.0",
)
app.include_router(router)
