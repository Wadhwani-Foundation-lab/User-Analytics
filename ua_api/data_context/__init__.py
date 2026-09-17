"""
data_context — Data Foundations & first-class metadata layer for NEP User Analytics.

This module establishes the trustworthy data foundation that the analytics
assistant sits on top of:

  * catalog/    — machine-readable metadata (single source of truth)
  * quality/    — read-only data-quality & integrity validation
  * freshness/  — load/provenance tracking
  * ingest/     — governed CSV -> Supabase pipeline (env creds, validated)
  * migrations/ — reviewable, non-destructive DDL (comments, indexes, catalog table)

Nothing here mutates the analytics schema implicitly. Validation runs as
read-only SELECTs; structural changes are emitted as SQL for review.
"""

__version__ = "0.1.0"
