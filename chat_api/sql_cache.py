"""
FAQ/SQL cache for NEP Analytics Chat.

Stores: normalized question → SQL string only.
On a cache hit, the cached SQL is passed directly to the LLM for response
formatting, skipping the expensive SQL-generation step.

Persistence:
- Cache is saved to sql_cache_store.json (same directory as this file)
- On startup the JSON is loaded automatically — cache survives server restarts
- File is written after every set / invalidate / clear operation

Policy:
- Exact match on normalized question (lowercased, whitespace-collapsed)
- Max 500 entries; oldest entry evicted when full (FIFO)
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import OrderedDict
from typing import Optional

_MAX_ENTRIES = 500
_CACHE_FILE = os.path.join(os.path.dirname(__file__), "sql_cache_store.json")

_cache: OrderedDict[str, dict] = OrderedDict()
_stats = {"hits": 0, "misses": 0, "evictions": 0}


# ── Persistence helpers ────────────────────────────────────────────────────────

def _save() -> None:
    """Write the current cache to sql_cache_store.json."""
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(dict(_cache), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[CACHE] Failed to save cache to disk: {e}")


def _load() -> None:
    """Load cache from sql_cache_store.json if it exists."""
    if not os.path.exists(_CACHE_FILE):
        return
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            data: dict = json.load(f)
        for key, entry in data.items():
            if isinstance(entry, dict) and "sql" in entry:
                _cache[key] = entry
        print(f"[CACHE] Loaded {len(_cache)} entries from {_CACHE_FILE}")
    except Exception as e:
        print(f"[CACHE] Failed to load cache from disk: {e}")


# ── Core operations ────────────────────────────────────────────────────────────

def _normalize(question: str) -> str:
    """Lowercase + collapse whitespace."""
    return re.sub(r"\s+", " ", question.strip().lower())


def get(question: str) -> Optional[str]:
    """Return cached SQL string for the question, or None if not cached."""
    key = _normalize(question)
    if key in _cache:
        _cache.move_to_end(key)
        _cache[key]["hits"] = _cache[key].get("hits", 0) + 1
        _stats["hits"] += 1
        sql = _cache[key]["sql"]
        print(f"[CACHE HIT] '{question[:70]}' (total hits={_cache[key]['hits']})")
        return sql
    _stats["misses"] += 1
    return None


def set(question: str, sql: str) -> None:
    """Cache SQL for a question and persist to disk. Evicts oldest if at capacity."""
    if not sql or not sql.strip():
        return
    key = _normalize(question)
    if key in _cache:
        _cache[key]["sql"] = sql
        _cache[key]["updated_at"] = time.time()
        _cache.move_to_end(key)
        _save()
        return
    if len(_cache) >= _MAX_ENTRIES:
        _cache.popitem(last=False)
        _stats["evictions"] += 1
    _cache[key] = {"sql": sql, "hits": 0, "added_at": time.time()}
    print(f"[CACHE SET] '{question[:70]}' (cache size={len(_cache)})")
    _save()


def invalidate(question: str) -> bool:
    """Remove a question from the cache and persist. Returns True if it was present."""
    key = _normalize(question)
    if key in _cache:
        del _cache[key]
        _save()
        return True
    return False


def clear() -> None:
    """Flush the entire cache and persist the empty state."""
    _cache.clear()
    _save()
    print("[CACHE CLEAR] All entries removed.")


def stats() -> dict:
    """Return cache statistics."""
    total = _stats["hits"] + _stats["misses"]
    return {
        "size": len(_cache),
        "max_size": _MAX_ENTRIES,
        "cache_file": _CACHE_FILE,
        "hits": _stats["hits"],
        "misses": _stats["misses"],
        "evictions": _stats["evictions"],
        "hit_rate_pct": round(_stats["hits"] / total * 100, 1) if total else 0.0,
    }


def list_entries() -> list[dict]:
    """Return all cached entries (for the admin endpoint)."""
    return [
        {
            "question": key,
            "sql_preview": entry["sql"][:120],
            "hits": entry.get("hits", 0),
            "added_at": entry.get("added_at"),
        }
        for key, entry in _cache.items()
    ]


# ── Auto-load on import ────────────────────────────────────────────────────────
_load()
