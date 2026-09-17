# data_context — Data Foundations & Metadata Layer

This module establishes the **trustworthy data foundation** the NEP analytics
assistant sits on top of. It implements the "Data Foundations" + "treat metadata
as first-class" layers from Anthropic's self-service analytics architecture,
addressing the data blockers: no metadata catalog, no integrity validation, no
freshness/provenance, and an ungoverned (and credential-leaking) ingestion path.

It is **self-contained** and **non-destructive**: validation runs as read-only
`SELECT`s through the existing `execute_sql` RPC, and all structural changes are
emitted as reviewable SQL.

## Layout

```
data_context/
├── config.py        # env-based credentials + read_sql helper (no hardcoded keys)
├── catalog/         # machine-readable metadata — the single source of truth
│   ├── catalog.py   #   YAML loader → typed Table/Column/Join objects
│   └── tables/*.yaml#   one file per analytics table (drafted from schema_reference.md)
├── quality/         # catalog-driven data-quality checks + report
├── freshness/       # load provenance tracking (nep_data_catalog)
├── ingest/          # governed CSV → Supabase pipeline
├── migrations/      # 001 catalog table (hand) + 002/003 generated from catalog
├── api/             # self-contained freshness-aware health API (own models.py + main.py)
└── reports/         # quality_report.json output
```

## Freshness-aware health API (`data_context.api`)

A **new, self-contained** API layer with its own `models.py` and `main.py`. It
surfaces per-table load provenance/freshness from `nep_data_catalog` and does
**not** modify `chat_api`. Run it standalone or mount its router:

```bash
# Standalone
uvicorn ua_api.data_context.api.main:app --port 8001
# GET /api/health     -> status, supabase_connected, llm_model, catalog_provisioned, data_freshness[]
# GET /api/freshness  -> per-table load provenance
```

```python
# Or mount into the existing app without editing chat_api source:
from ua_api.data_context.api.main import router as data_context_router
app.include_router(data_context_router)
```

It degrades gracefully: if `migrations/001` has not been applied,
`catalog_provisioned` is `false` and `data_freshness` is empty.

## Setup

```bash
pip install -r data_context/requirements.txt
```

Credentials are read from `chat_api/.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
or the process environment. **Nothing is hardcoded** — this replaces the leaked
service key in the old `upload_to_supabase.py` / `verify_upload.py`.

## Commands

```bash
# Inspect the catalog
python -m ua_api.data_context catalog show

# Reconcile catalog against the LIVE database (finds the VARCHAR-vs-DATE drift)
python -m ua_api.data_context catalog validate

# Run all data-quality checks → console + reports/quality_report.json
python -m ua_api.data_context quality run
python -m ua_api.data_context quality run --table nep_liftoffx_data_sample

# Generate DDL from the catalog (column comments + join-key indexes)
python -m ua_api.data_context migrations emit

# Show data freshness / load provenance
python -m ua_api.data_context freshness show

# Governed load of CSVs into Supabase, recording provenance
python -m ua_api.data_context ingest
python -m ua_api.data_context ingest --table nep_mentor_profiles_sample_data --truncate
```

## One-time DB setup

Run these in the Supabase SQL editor (the `execute_sql` RPC is read-only and
cannot apply DDL):

1. `migrations/001_data_catalog_table.sql` — creates the freshness table.
2. `python -m ua_api.data_context migrations emit`, then run the generated
   `002_column_comments.sql` and `003_join_key_indexes.sql`.

## What the quality checks cover

| Check | What it catches |
|-------|-----------------|
| `referential_integrity` | FK values (`userid`, `participant_user_id`, `mentor_id`) with no parent row |
| `enum_validation` | values outside the catalogued vocabulary (e.g. an `ai_chat` that should be `message`) |
| `null_keys` | NULLs in declared NOT-NULL key columns |
| `uniqueness` | duplicate primary-key values |
| `date_format` | date/timestamp strings not matching the expected pattern |
| `volume` | empty tables |

`FAIL`/`ERROR` are blocking; `WARN` (orphans, date smells on dirty sample data)
is informational at this phase.

## Deliberately out of scope (later phases)

- Metrics / semantic layer (separate module).
- Hard `PRIMARY KEY` / `FOREIGN KEY` constraints and `VARCHAR → DATE` type
  changes — only safe **after** the quality report is clean. Migrations here
  add comments and indexes only.
- Scheduled ETL / real production tables (infra track).
```
