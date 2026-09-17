"""
data_context.api — self-contained, freshness-aware health API.

Exposes `router` (mountable into any FastAPI app) and `app` (standalone).
Does not import from or modify chat_api.
"""
from .main import app, router

__all__ = ["app", "router"]
