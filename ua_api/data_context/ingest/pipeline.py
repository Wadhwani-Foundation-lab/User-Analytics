"""
Governed CSV -> Supabase ingestion.

Improvements over the original upload_to_supabase.py:
  * Credentials come from the environment (no committed service key).
  * Each CSV is validated against the catalog BEFORE loading: required columns
    present, no unexpected/extra columns.
  * Load provenance (row count, source file + checksum, timestamp, status) is
    recorded in nep_data_catalog so freshness is always known.
  * Re-runnable: a table can be truncated-and-reloaded or appended.

This does NOT create the analytics tables — that remains create_tables.sql.
It loads data into existing tables and tracks the load.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from ..catalog import Table, load_catalog
from ..config import CSV_DIR, REPO_ROOT, get_client
from ..freshness import file_checksum, record_load

BATCH_SIZE = 1000


@dataclass
class LoadResult:
    table: str
    source_file: str
    total_rows: int
    uploaded: int
    failed: int
    validation_errors: List[str]

    @property
    def ok(self) -> bool:
        return not self.validation_errors and self.uploaded == self.total_rows

    @property
    def status(self) -> str:
        if self.validation_errors:
            return "failed"
        if self.failed:
            return "partial"
        return "success"


# --- CSV cleaning (kept compatible with the original loader) ----------------

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace([float("inf"), float("-inf")], None)
    df = df.where(pd.notna(df), None)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def _to_records(df: pd.DataFrame) -> List[dict]:
    import numpy as np

    def safe(v):
        if pd.isna(v):
            return None
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return None if (np.isnan(v) or np.isinf(v)) else float(v)
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        return v

    return [{c: safe(v) for c, v in row.items()} for _, row in df.iterrows()]


# --- Validation -------------------------------------------------------------

def _validate_columns(table: Table, df: pd.DataFrame) -> List[str]:
    """Compare CSV columns to the catalog. Returns a list of error strings."""
    catalog_cols = set(table.column_names)
    csv_cols = set(df.columns)

    errors = []
    missing = catalog_cols - csv_cols
    extra = csv_cols - catalog_cols
    if missing:
        errors.append(f"CSV is missing catalogued columns: {sorted(missing)}")
    if extra:
        errors.append(f"CSV has columns not in the catalog: {sorted(extra)}")
    return errors


# --- Load -------------------------------------------------------------------

def ingest_table(
    table_name: str,
    timestamp: Optional[str] = None,
    truncate: bool = False,
) -> LoadResult:
    catalog = load_catalog()
    table = catalog.get(table_name)
    if table is None:
        raise ValueError(f"'{table_name}' is not in the catalog")
    if not table.source_csv:
        raise ValueError(f"'{table_name}' has no source_csv declared in the catalog")

    csv_path = REPO_ROOT / table.source_csv
    if not csv_path.exists():
        # fall back to csvfiles/ by basename
        csv_path = CSV_DIR / Path(table.source_csv).name
    if not csv_path.exists():
        raise FileNotFoundError(f"Source CSV not found: {table.source_csv}")

    print(f"\n■ {table_name}  <-  {csv_path.name}")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  read {len(df)} rows, {len(df.columns)} columns")

    errors = _validate_columns(table, df)
    if errors:
        for e in errors:
            print(f"  ✗ validation: {e}")
        record_load(
            table_name=table_name,
            row_count=0,
            source_file=str(csv_path.name),
            source_checksum=file_checksum(csv_path),
            last_loaded_at=timestamp,
            load_status="failed",
            notes="; ".join(errors),
        )
        return LoadResult(table_name, csv_path.name, len(df), 0, len(df), errors)

    df = _clean(df)
    records = _to_records(df)

    client = get_client()
    if truncate:
        # PostgREST delete-all requires a filter; delete where PK is not null.
        try:
            client.table(table_name).delete().neq(
                table.primary_key or "ctid", "__never__"
            ).execute()
            print("  truncated existing rows")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! truncate skipped: {exc}")

    uploaded = 0
    failed = 0
    total = len(records)
    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        try:
            client.table(table_name).insert(batch).execute()
            uploaded += len(batch)
            print(f"  batch {i // BATCH_SIZE + 1}: +{len(batch)} ({uploaded}/{total})")
        except Exception as exc:  # noqa: BLE001
            failed += len(batch)
            print(f"  ✗ batch {i // BATCH_SIZE + 1} failed: {str(exc)[:120]}")

    result = LoadResult(table_name, csv_path.name, total, uploaded, failed, [])
    record_load(
        table_name=table_name,
        row_count=uploaded,
        source_file=csv_path.name,
        source_checksum=file_checksum(csv_path),
        last_loaded_at=timestamp,
        load_status=result.status,
        notes=None if result.ok else f"{failed} rows failed",
    )
    return result


def ingest_all(
    timestamp: Optional[str] = None,
    truncate: bool = False,
) -> List[LoadResult]:
    catalog = load_catalog()
    results = []
    for table in catalog:
        if not table.source_csv:
            continue
        try:
            results.append(ingest_table(table.name, timestamp=timestamp, truncate=truncate))
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {table.name}: {exc}")
            results.append(LoadResult(table.name, table.source_csv or "?", 0, 0, 0, [str(exc)]))

    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    for r in results:
        flag = "✓" if r.ok else "✗"
        print(f"  {flag} {r.table:42} {r.uploaded}/{r.total_rows} rows [{r.status}]")
    print("=" * 70)
    return results
