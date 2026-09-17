"""
Pydantic v2 request/response models for nep_analytics API.
Self-contained — no imports from chat_api/ or ua_api/.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    question: str
    history: List[HistoryTurn] = Field(default_factory=list)


class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie", "funnel"]
    labels: List[str]
    datasets: List[Dict[str, Any]]
    title: Optional[str] = None
    stacked: Optional[bool] = None


class TableData(BaseModel):
    columns: List[str]
    rows: List[List[Any]]


class Provenance(BaseModel):
    certified: bool
    metric: Optional[str] = None
    confidence: Optional[float] = None
    metric_source: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    response_type: Literal["text", "table", "bar_chart", "line_chart", "pie_chart", "funnel_chart"]
    chart_config: Optional[ChartConfig] = None
    table_data: Optional[TableData] = None
    sql_used: Optional[str] = None
    session_id: str
    provenance: Optional[Provenance] = None


class HistoryResponse(BaseModel):
    session_id: str
    history: List[HistoryTurn]


class HealthResponse(BaseModel):
    status: str
    supabase_connected: bool
    sql_gen_model: str
    interpreter_model: str
    resolver_model: str


class SessionCreateRequest(BaseModel):
    session_id: str
    title: str
