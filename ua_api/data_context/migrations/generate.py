"""
Generate reviewable, non-destructive DDL from the catalog:

  * 002_column_comments.sql  — COMMENT ON COLUMN for every catalogued column,
                               so the data dictionary also lives inside the DB
                               (queryable via information_schema / pg_catalog).
  * 003_join_key_indexes.sql — btree indexes on declared PKs and join keys to
                               make the integrity checks and analytics JOINs fast.

This phase deliberately does NOT emit PRIMARY KEY / FOREIGN KEY constraints or
type changes: the data must pass the quality report before integrity can be
enforced rather than merely validated.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from ..catalog import Catalog, load_catalog
from ..config import MIGRATIONS_DIR, OWNER_ROLE


def _escape(text: str) -> str:
    return (text or "").replace("'", "''").strip()


def build_column_comments(catalog: Catalog) -> str:
    lines: List[str] = [
        "-- Migration 002 — column comments (generated from the catalog)",
        "-- Regenerate with: python -m data_context migrations emit",
        "-- Run in the Supabase SQL editor. Safe / non-destructive.",
        f"-- COMMENT requires table ownership; the analytics tables are owned by",
        f"-- '{OWNER_ROLE}'. postgres is a member of it, so we assume the role.",
        f"SET ROLE {OWNER_ROLE};",
        "",
    ]
    for table in catalog:
        lines.append(f"-- {table.name}: {_escape(table.description)}")
        if table.grain:
            lines.append(f"COMMENT ON TABLE {table.name} IS '{_escape(table.grain)}';")
        for col in table.columns:
            note = _escape(col.description)
            if col.is_enum:
                note += f" [enum: {', '.join(col.enum_values)}]"
            lines.append(
                f"COMMENT ON COLUMN {table.name}.{col.name} IS '{note}';"
            )
        lines.append("")
    lines.append("RESET ROLE;")
    return "\n".join(lines)


def build_indexes(catalog: Catalog) -> str:
    lines: List[str] = [
        "-- Migration 003 — join-key & primary-key indexes (generated from the catalog)",
        "-- Regenerate with: python -m data_context migrations emit",
        "-- Run in the Supabase SQL editor. Safe / non-destructive.",
        f"-- CREATE INDEX requires table ownership; assume the owner role.",
        f"SET ROLE {OWNER_ROLE};",
        "",
    ]
    seen = set()

    def add_index(table: str, column: str):
        key = (table, column)
        if key in seen:
            return
        seen.add(key)
        idx = f"idx_{table}_{column}"
        lines.append(
            f"CREATE INDEX IF NOT EXISTS {idx} ON {table} ({column});"
        )

    for table in catalog:
        if table.primary_key:
            lines.append(f"-- {table.name} primary key")
            add_index(table.name, table.primary_key)
        if table.joins:
            lines.append(f"-- {table.name} foreign keys")
            for join in table.joins:
                add_index(table.name, join.column)
                # also index the parent key it points at
                add_index(join.references_table, join.references_column)
        lines.append("")
    lines.append("RESET ROLE;")
    return "\n".join(lines)


def emit_migrations(catalog: Catalog = None) -> List[Path]:
    """Write 002 and 003 to the migrations directory; return the paths."""
    catalog = catalog or load_catalog()
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    targets = [
        ("002_column_comments.sql", build_column_comments(catalog)),
        ("003_join_key_indexes.sql", build_indexes(catalog)),
    ]
    for filename, content in targets:
        path = MIGRATIONS_DIR / filename
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content + "\n")
        written.append(path)
    return written
