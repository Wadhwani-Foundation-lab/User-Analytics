"""metrics.api — self-contained endpoint exposing the metric path. Mountable
(`include_router`) or standalone; does not import or modify chat_api."""
from .main import app, router

__all__ = ["app", "router"]
