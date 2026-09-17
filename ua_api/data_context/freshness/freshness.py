"""
Freshness / provenance tracking against the nep_data_catalog table.

Reads go through the read-only execute_sql RPC; writes use the Supabase client's
table API (PostgREST upsert) with the service key — the RPC blocks writes by
design, so freshness rows are written directly to the metadata table.

Requires migration 001_data_catalog_table.sql to have been applied.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional

from ..config import CATALOG_TABLE, get_client, run_sql


def file_checksum(path: Path, chunk_size: int = 65536) -> str:
    """SHA-256 of a source file, used to detect whether a reload changed data."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def record_load(
    table_name: str,
    row_count: int,
    source_file: Optional[str] = None,
    source_checksum: Optional[str] = None,
    last_loaded_at: Optional[str] = None,
    load_status: str = "success",
    loaded_by: str = "data_context.ingest",
    notes: Optional[str] = None,
) -> None:
    """Upsert one freshness row. `last_loaded_at` is an ISO timestamp supplied
    by the caller (the module avoids reading the clock directly)."""
    client = get_client()
    record = {
        "table_name": table_name,
        "row_count": row_count,
        "source_file": source_file,
        "source_checksum": source_checksum,
        "last_loaded_at": last_loaded_at,
        "load_status": load_status,
        "loaded_by": loaded_by,
        "notes": notes,
    }
    client.table(CATALOG_TABLE).upsert(record, on_conflict="table_name").execute()


def backfill_freshness(timestamp: Optional[str] = None) -> List[dict]:
    """
    Record a freshness baseline for data that already exists in the database
    WITHOUT re-loading it. For each catalogued table, reads the current
    COUNT(*) and upserts a provenance row marked load_status='baseline'.

    Use this for the existing live tables (which hold the real dataset, not the
    sample CSVs) instead of `ingest`, which is for provisioning a fresh target.
    """
    from ..catalog import load_catalog

    catalog = load_catalog()
    recorded = []
    print("\nFRESHNESS BACKFILL (non-destructive — records current row counts)")
    print("=" * 70)
    for table in catalog:
        try:
            rows = run_sql(f"SELECT COUNT(*) AS n FROM {table.name}")
            count = int(rows[0]["n"]) if rows else 0
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {table.name}: could not count ({exc})")
            continue
        record_load(
            table_name=table.name,
            row_count=count,
            source_file=table.source_csv,
            source_checksum=None,
            last_loaded_at=timestamp,
            load_status="baseline",
            loaded_by="data_context.backfill",
            notes="Baseline from pre-existing live data; not loaded by data_context.",
        )
        recorded.append({"table_name": table.name, "row_count": count})
        print(f"  ✓ {table.name}: {count} rows recorded")
    print("=" * 70)
    return recorded


def table_freshness(table_name: str) -> Optional[dict]:
    rows = run_sql(
        f"SELECT * FROM {CATALOG_TABLE} WHERE table_name = '{table_name}'"
    )
    return rows[0] if rows else None


def show_freshness() -> List[dict]:
    """Return all freshness rows, newest first. Prints a readable table."""
    try:
        rows = run_sql(
            f"SELECT table_name, row_count, source_file, last_loaded_at, "
            f"load_status, loaded_by FROM {CATALOG_TABLE} "
            f"ORDER BY last_loaded_at DESC NULLS LAST"
        )
    except Exception as exc:  # noqa: BLE001
        print(
            f"Could not read {CATALOG_TABLE}: {exc}\n"
            f"Did you apply migrations/001_data_catalog_table.sql?"
        )
        return []

    print("\n" + "=" * 78)
    print("DATA FRESHNESS")
    print("=" * 78)
    if not rows:
        print("(no load records yet — run `python -m data_context ingest`)")
        return rows
    header = f"{'table':40} {'rows':>8}  {'loaded_at':24} status"
    print(header)
    print("-" * 78)
    for r in rows:
        print(
            f"{r['table_name']:40} {str(r.get('row_count','')):>8}  "
            f"{str(r.get('last_loaded_at','')):24} {r.get('load_status','')}"
        )
    print("=" * 78)
    return rows
