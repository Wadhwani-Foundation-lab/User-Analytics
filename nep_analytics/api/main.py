"""
FastAPI application entry point for nep_analytics.
Runs on port 8002 — independent of chat_api (8003) and ua_api (8001).

Start:
  uvicorn nep_analytics.api.main:app --reload --port 8002
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import ALLOWED_ORIGINS
from .router import router

app = FastAPI(
    title="NEP Analytics Engine",
    description=(
        "Standalone NL-to-SQL analytics engine for the NEP platform. "
        "Converts natural language questions to SQL, executes against Supabase, "
        "and returns text, tables, or charts."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
