"""
chat_adapter models — identical shapes to chat_api/models.py.
Declared here so the adapter has no import dependency on chat_api/.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    question: str
    history: List[HistoryTurn] = []


class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie", "funnel"]
    labels: List[str]
    datasets: List[Dict[str, Any]]
    title: Optional[str] = None


class TableData(BaseModel):
    columns: List[str]
    rows: List[List[Any]]


class Provenance(BaseModel):
    """Stamped on every certified-metric response so the frontend can render a source badge."""
    certified: bool = False
    metric: Optional[str] = None
    confidence: Optional[float] = None
    metric_source: Optional[str] = None   # e.g. "questions_to_sql.md#Q4"


class ChatResponse(BaseModel):
    answer: str
    response_type: Literal["text", "table", "bar_chart", "line_chart", "pie_chart", "funnel_chart"]
    chart_config: Optional[ChartConfig] = None
    table_data: Optional[TableData] = None
    sql_used: Optional[str] = None
    session_id: str
    provenance: Optional[Provenance] = None   # None on text-to-SQL path
