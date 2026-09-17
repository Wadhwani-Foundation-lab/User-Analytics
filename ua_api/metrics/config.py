"""
metrics configuration — loads environment (shared with the backend) so the
resolver's Anthropic client and the model id are available. Mirrors
data_context.config's env handling; credentials are never hardcoded.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Module now lives at <repo>/ua_api/metrics, so the repo root is three up.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ENV = REPO_ROOT / "chat_api" / ".env"
if _DEFAULT_ENV.exists():
    load_dotenv(_DEFAULT_ENV, override=False)
load_dotenv(override=False)

# Same default model as the backend's llm_client.
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
