from pydantic import BaseModel
from typing import Literal, Optional, List, Any, Dict


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    question: str
    history: List[HistoryTurn] = []


class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie"]
    labels: List[str]
    datasets: List[Dict[str, Any]]
    title: Optional[str] = None


class TableData(BaseModel):
    columns: List[str]
    rows: List[List[Any]]


class ChatResponse(BaseModel):
    answer: str
    response_type: Literal["text", "table", "bar_chart", "line_chart", "pie_chart"]
    chart_config: Optional[ChartConfig] = None
    table_data: Optional[TableData] = None
    sql_used: Optional[str] = None
    session_id: str


class HistoryResponse(BaseModel):
    session_id: str
    history: List[HistoryTurn]


class HealthResponse(BaseModel):
    status: str
    supabase_connected: bool
    llm_model: str
