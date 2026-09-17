"""
chat_adapter configuration.

Environment variables (all read from chat_api/.env or the process environment):
  UPSTREAM_CHAT_URL  — where the original chat_api is running (default: http://localhost:8001)
  API_SECRET_KEY     — forwarded as x-api-key to the upstream
  SUPABASE_URL       — for direct session persistence when a metric is intercepted
  SUPABASE_SERVICE_KEY
  ANTHROPIC_API_KEY  — for the interpretation call
  LLM_MODEL          — model name (default: claude-sonnet-4-5)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ENV = REPO_ROOT / "chat_api" / ".env"
if _DEFAULT_ENV.exists():
    load_dotenv(_DEFAULT_ENV, override=False)
load_dotenv(override=False)

# Upstream chat_api URL — move chat_api to 8001 when running the adapter on 8000.
UPSTREAM_CHAT_URL = os.getenv("UPSTREAM_CHAT_URL", "http://localhost:8001")

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
