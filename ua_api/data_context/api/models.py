"""
Pydantic response models for the data_context API layer.

Self-contained — does NOT import from chat_api. This mirrors chat_api's
HealthResponse shape and extends it with data-freshness/provenance so the
endpoint can be used as a drop-in replacement or mounted alongside the
existing API without editing it.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class TableFreshness(BaseModel):
    table_name: str
    row_count: Optional[int] = None
    source_file: Optional[str] = None
    last_loaded_at: Optional[str] = None
    load_status: Optional[str] = None


class HealthResponse(BaseModel):
    status: str                     # "ok" | "degraded"
    supabase_connected: bool
    llm_model: str
    catalog_provisioned: bool       # is the nep_data_catalog table present?
    data_freshness: List[TableFreshness] = []


class FreshnessResponse(BaseModel):
    catalog_provisioned: bool
    tables: List[TableFreshness] = []
