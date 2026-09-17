"""
metrics — certified metrics / semantic layer for NEP User Analytics (Phase 1).

Makes certified metrics the default path: for known questions Claude only
classifies the question to a metric and extracts parameters; the backend renders
a reviewed, version-controlled SQL template. Free-form text-to-SQL is the
fallback, not the default.

Public surface:
    from metrics import answer, load_registry
    result = answer("How many MAU over time?")   # {matched, metric, params, sql, rows}

Built on the data_context foundation (catalog for enum/join correctness,
config.run_sql for read-only execution).
"""
from .registry import Metric, Registry, load_registry
from .resolver import answer, resolve

__all__ = ["Metric", "Registry", "load_registry", "answer", "resolve"]
