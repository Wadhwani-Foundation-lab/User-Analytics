"""
metrics API — self-contained endpoint for the certified-metric path.

This is the opt-in integration surface. Two ways to use it without touching
chat_api:

  1. Standalone:  uvicorn metrics.api.main:app --port 8002
  2. Mounted:     from metrics.api.main import router as metrics_router
                  app.include_router(metrics_router)

POST /api/metric-answer {question, today?}
  -> {matched, metric, params, sql, rows, response_type, ...}
     matched=false means the caller should fall back to free-form text-to-SQL.

GET  /api/metrics
  -> the certified metric catalog (names, descriptions, params).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from ..registry import load_registry
from ..resolver import answer

router = APIRouter(tags=["Metrics"])


class MetricAnswerRequest(BaseModel):
    question: str
    today: Optional[str] = None  # YYYY-MM-DD; defaults to server date


class MetricAnswerResponse(BaseModel):
    matched: bool
    metric: Optional[str] = None
    tier: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    response_type: Optional[str] = None
    label_column: Optional[str] = None
    value_column: Optional[str] = None
    source: Optional[str] = None


@router.get("/api/metrics")
def list_metrics():
    return {"metrics": load_registry().catalog_for_resolver()}


@router.post("/api/metric-answer", response_model=MetricAnswerResponse)
def metric_answer(req: MetricAnswerRequest) -> MetricAnswerResponse:
    today = req.today or date.today().isoformat()
    result = answer(req.question, today=today)
    return MetricAnswerResponse(**{k: result.get(k) for k in MetricAnswerResponse.model_fields})


app = FastAPI(
    title="NEP metrics API",
    description="Certified metrics / semantic layer (Phase 1).",
    version="0.1.0",
)
app.include_router(router)
