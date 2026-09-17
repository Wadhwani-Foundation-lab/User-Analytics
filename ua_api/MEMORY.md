# MEMORY.md — ua_api package

> Durable record of why this package exists, the decisions that shaped it, and
> what has been built. Read before changing package structure or reversing a
> decision. Submodule-specific details live in their own `MEMORY.md` files.

## Why this package exists

The NEP analytics backend (`chat_api/`) is pure text-to-SQL with no data
foundation. Benchmarked against Anthropic's "self-service data analytics"
architecture, it sits at the pre-foundation stage (~21% raw accuracy before
layers are added). `ua_api` builds those layers **without touching chat_api** —
the user's explicit requirement. It provides:

1. **`data_context/`** — Data Foundations: machine-readable catalog, data quality
   checks, freshness tracking, governed ingestion, and a self-contained health API.
2. **`metrics/`** — Certified Metrics / semantic layer: parameterised SQL templates
   reviewed by humans, LLM-based question→metric classification, safe SQL rendering,
   and a standalone answer API.

## Structure decision log

- **Single `ua_api/` package, not two separate top-level folders.** Originally
  `data_context/` and `metrics/` were both repo-root packages. Consolidated into
  `ua_api/` on 2026-06-09 so imports are unambiguous and the two modules ship as
  one unit. All cross-module refs are relative imports (`from ..data_context...`).

- **`chat_api/` is read-only from here.** The user explicitly required no edits
  to `chat_api/main.py`, `chat_api/models.py`, or any other backend file. Each
  `ua_api` submodule ships its own `api/models.py` + `api/main.py` and is mounted
  via `include_router` or run standalone.

- **`REPO_ROOT` depth is `.parent.parent.parent` for both submodule `config.py`
  files.** `ua_api/<name>/config.py` is three levels below the repo root. All env
  loading (`chat_api/.env`) depends on this.

## What is built and verified (as of 2026-06-11)

### data_context (complete, live-tested)
- Catalog: 4 YAML table definitions (user 33 cols, liftoffx 61 cols, events 44
  cols, mentor 35 cols), typed loader, validated against live DB (zero drift).
- Quality: 6 check families (referential_integrity, enum_validation, null_keys,
  uniqueness, date_format, volume), 60 pass · 3 warn · 1 fail on live data.
- Freshness: `nep_data_catalog` table live (migration 001 applied 2026-06-09);
  baseline backfill recorded; `/api/freshness` and `/api/health` working.
- Governed ingest: env-cred pipeline replacing the committed service key.
- Migrations: 001 applied; 002/003 (column comments + indexes) deferred pending
  `airflow_loader` ownership resolution.

### metrics (complete, live-tested)
- Registry: **20 certified metric YAML definitions** (expanded from 8 on 2026-06-11).
- New metrics cover: questions_growth, weekly_retention, retention_by_channel, user_engagement_tiers,
  mentors_by_stage, mentor_sessions_by_industry, events_by_program, event_noshow_by_gap,
  user_type_engagement, monthly_events_trend, signup_to_first_message, activity_type_breakdown,
  mentors_by_industry, registration_to_question_conversion.
- Resolver rewritten to use Claude native **tool-use API** (Phase 2): metric names enumerated as
  enum in tool schema — Claude can only return names that exist in the registry. No JSON parsing.
- 20/20 metrics validate against live DB.

### skills (complete, 2026-06-11)
- `ua_api/skills/blocks.py`: 9 focused block constants (IDENTITY, OUTPUT_FORMAT, RESPONSE_TYPES,
  ENUM_VALUES, DATE_HANDLING, SQL_RULES, COLUMN_MAP, PERFORMANCE, CLARIFICATION).
- `ua_api/skills/prompt_builder.py`: `build_prompt(profile=...)` assembles blocks + schema docs.
  4 preset profiles: full, minimal, sql, events. `SYSTEM_PROMPT` singleton = drop-in replacement.

### chat_adapter (complete, live-tested 2026-06-10)
- Proxy FastAPI app: intercepts `/api/chat` for certified metric questions.
- `try_certified_answer()`: metrics.answer() → format chart/table/text → Supabase persist.
- Fall-through: non-certified questions return `None`; caller proxies to chat_api.
- Interpretation call included: same prose quality as chat_api's `interpret_results`.
- Session persistence direct to `nep_chat_messages` (fire-and-forget, FK-safe in production).
- **Provenance fields** (Phase 5): `ChatResponse.provenance` carries `certified`, `metric`,
  `confidence`, `metric_source` on every certified answer.
- Verified: MAU Oct-Dec 2025 → line_chart, labels=["Oct 2025","Nov 2025","Dec 2025"], data=[417,1425,1002].
- Verified: non-certified question returns None (fall-through confirmed).

### validation (complete, 2026-06-11)
- `ua_api/validation/eval_set.py`: 15 frozen `EvalCase` records (10 certified, 3 text-to-SQL,
  2 anti-hallucination guards). Anchor date: 2026-06-10.
- `ua_api/validation/runner.py`: 3 modes — certified_only (no HTTP), adapter (full round-trip),
  sql_guard (text-to-SQL hallucination check).
- Column check degrades to SQL scan when rows are empty (data range gap handling).
- `python -m ua_api.validation` → 10/10 certified cases pass (100%).
- CLI exits with code 1 on any failure (CI-safe).

### feedback (complete, 2026-06-11)
- `ua_api/feedback/signals.py`: `overall_rating()`, `rating_by_period()`, `low_rated_questions()`.
- Reads `message_rating` (TEXT column, cast to INTEGER with guard) from activity table.
- `python -m ua_api.feedback` works; returns "No rated messages" on sample data (expected —
  ratings are production data not in sample).

## Pending / not yet built

| Item | Status | Notes |
|------|--------|-------|
| Migrations 002/003 | Deferred | Need `airflow_loader` ownership or self-grant |
| Rotate committed service key | Ops action | `upload_to_supabase.py` / `verify_upload.py` |
| Airflow → freshness hook | Not started | Pipeline should call `freshness.record_load` |
| Frontend provenance badge | Not started | Display `response.provenance` in chat_ui |
| Per-metric feedback grouping | Not started | Wire frontend thumbs-up metric tag → signals.py GROUP BY metric |
| Adapter mode eval cases | Not started | `--mode adapter` needs adapter running + real session IDs |

## Key data facts (see data_context/MEMORY.md for detail)

- Analytics tables owned by `airflow_loader` (Airflow ETL pipeline exists).
- `nep_mentor_profiles_sample_data` is exploded ~33×; always `COUNT(DISTINCT user_id)`.
- Activity table has no unique PK; `activity_id` is not unique.
- Cross-table JOINs are unreliable on sample data (populations were not drawn
  consistently) — the real limitation for the assistant, not fixable in code.
- Live DB uses real `DATE`/`TIMESTAMP` types (not `VARCHAR`) despite stale
  `create_tables.sql` bootstrap.
