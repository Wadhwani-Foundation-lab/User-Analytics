# MEMORY.md — data_context module

> Durable notes on *why* this module is shaped the way it is. Read this before
> changing architecture or reversing a decision. Facts reflect what was true at
> creation; verify against code if something looks stale.

## Why the module exists

The NEP analytics backend was pure text-to-SQL with no data foundation: a
monolithic system prompt, no metadata catalog, no integrity/quality checks, no
freshness, and an ungoverned CSV upload. Benchmarked against Anthropic's
"How Anthropic enables self-service data analytics" architecture, the project
sits at the pre-foundation stage (their reported ~21% raw accuracy before
layers are added). `data_context` builds the **Data Foundations + first-class
metadata** layer that everything else (a future metrics/semantic layer) depends
on. Scope was deliberately limited to *data context* on the user's instruction —
the semantic/metrics layer is a separate, later module.

## Decisions made (and the reasoning)

- **Top-level module, not inside chat_api.** Data-engineering concern; sits with
  `upload_to_supabase.py` / `create_tables.sql`. (User chose this.)
- **Catalog seeded from `docs/schema_reference.md`, human-owned.** Auto-drafted
  for speed; definitions are reviewed by a person. (User chose this.)
- **Migrations limited to comments + indexes + the catalog table.** No PK/FK
  constraints or type changes yet — they'd fail on dirty sample data. Enforce
  integrity only after `quality run` is clean. (User chose this.)
- **Read-only validation.** Checks run through the existing `execute_sql` RPC so
  the module can never mutate the analytics schema. DDL is emitted as reviewable
  `.sql` to run in the Supabase SQL editor (the RPC blocks DDL).
- **`api/` is a new self-contained submodule, not an edit to chat_api.** The user
  explicitly required leaving `chat_api/main.py` and `chat_api/models.py`
  untouched. So `data_context/api` re-implements its own `models.py`/`main.py`
  and is *mounted* (`include_router`) or run standalone. An earlier edit to
  `chat_api/models.py` was made then reverted.
- **No clock reads inside library code.** Timestamps are injected from the CLI
  (`timestamp=` args) for resume-safety; `freshness.record_load` takes an ISO
  string from the caller.

## Things discovered about the data

- **Date-type contradiction — RESOLVED.** `catalog validate` against the live DB
  reported zero drift: the live database uses real `DATE`/`TIMESTAMP` types
  (matching `schema_reference.md`); `create_tables.sql` was just a stale
  `VARCHAR(500)` bootstrap. The existing `TO_CHAR(start_date, ...)` queries are
  therefore sound. All `date_format` checks pass.
- **Leaked credentials (now mitigated):** the Supabase service-role key was
  hardcoded and committed in `upload_to_supabase.py` and `verify_upload.py`. The
  new `ingest` pipeline reads creds from env only. The committed key itself still
  needs rotating in Supabase — that's an ops action outside this module.
- **Catalog column counts:** user=33, liftoffx=61, events=44, mentor=35.
- **Events table has no single-column primary key** (grain is event × participant).
- **The analytics tables are owned by role `airflow_loader`, not postgres** —
  so there IS an Airflow ETL pipeline loading them (explains why live data
  dwarfs the sample CSVs; partially answers the "no ETL" blocker — it's external
  and undocumented here). `nep_chat_*` tables are owned by postgres. `postgres`
  is a MEMBER of `airflow_loader`. Consequence: `COMMENT` and `CREATE INDEX`
  (which need table ownership) fail from the SQL editor unless wrapped in
  `SET ROLE airflow_loader; ... RESET ROLE;`. migrations/generate.py emits this
  automatically; owner role is configurable via env `ANALYTICS_TABLE_OWNER`.
  Ideally the Airflow pipeline itself should write freshness rows to
  nep_data_catalog on each load (future).
- **postgres membership of airflow_loader is `inherit_option=False,
  set_option=False, admin_option=True`.** So from the SQL editor (as postgres)
  we can neither `SET ROLE airflow_loader` (set=false → "permission denied to
  set role") nor inherit ownership to COMMENT/CREATE INDEX directly (inherit=
  false → "must be owner"). admin_option=true means postgres *could* self-grant
  `GRANT airflow_loader TO postgres WITH SET TRUE, INHERIT TRUE;` to enable it.
  **Decision: DEFER migrations 002 (comments) and 003 (indexes)** — comments are
  redundant with the catalog YAML, indexes are a perf nicety on small tables, and
  neither blocks freshness. Only migration **001** (the nep_data_catalog table +
  grants, runs cleanly as postgres) is applied. Revisit 002/003 via the data
  team / Airflow owner, or the self-grant, if/when wanted.

## First live quality run — findings (60 pass · 3 warn · 1 fail)

Two categories. Catalog-draft gaps were corrected; genuine data defects remain
flagged on purpose.

Catalog-draft errors I fixed (under-specified from doc "sample values"):
- Grain/PK were wrong for two tables. **Mentor table is exploded ~33×**: 49,486
  rows but only **1,515 distinct user_id AND 1,515 distinct _id** (one row per
  mentor × program/industry/stage/employment/education). Set `primary_key: null`;
  grain now mandates `COUNT(DISTINCT user_id)` for counting mentors — `COUNT(*)`
  overcounts ~33×. **Activity table**: 154,904 rows but only 71,388 distinct
  `activity_id`, so it is not a PK either → `primary_key: null`.
- Enum vocabularies were too narrow. Added from live data:
  `response_type` += regular/journey/new_conversation; `response_flow_state`
  += journey_generated; user `phone_status` += not_entered_otp; mentor
  `company_type` += LIST.

Genuine data defects (still flagged — these are real, not catalog issues):
- **Exact-duplicate user row** (`uniqueness:user_id` FAIL): user_id
  `ef73d77a-…0562108` appears twice with identical email(null)/type/timestamp.
  Only 1 case, but a true dup in the "primary key" table.
- **Orphan FKs (3 WARN) — a sampling artifact of the `*_sample_data` tables.**
  `mentor.user_id`→user has many unmatched (one id ×7280), `liftoffx.mentor_id`
  →mentor and `events.participant_user_id`→user have some. The user/mentor/event
  samples weren't drawn from a consistent population, so cross-table JOINs and
  user-level rollups of mentors/events are unreliable on this sample. This is the
  single biggest *data* limitation for the assistant — not fixable in code; needs
  a consistent extract (or real production tables).

## Current state / what's done

- Catalog (4 YAML + loader), quality (6 check families + runner), freshness,
  governed ingest, migrations (001 hand-written; 002/003 generated), CLI, and the
  `api` submodule are all built and verified offline (catalog parses, 21 checks
  build valid SQL with 0 construction errors, migrations generate, api routes
  build, health degrades gracefully with no DB / no catalog table).
- **Run against the live DB:** `catalog validate` (clean) and `quality run`
  (60 pass · 3 warn · 1 fail) executed. Catalog corrected per findings above;
  re-run is clean except the genuine defects. Report at
  `reports/quality_report.json`.
- **Migration 001 applied (2026-06-09); freshness layer is LIVE.** `nep_data_catalog`
  exists; `freshness backfill` recorded baselines (liftoffx 154,904 · events 291 ·
  user 13,150 · mentor 49,486, all `load_status='baseline'`). `/api/health` now
  returns `catalog_provisioned: true` + `data_freshness[]`, and `/api/freshness`
  works. Migrations 002/003 deferred (see role note above).
- Backfill rows carry `source_file` = the catalog's declared CSV, but the data
  was actually loaded by Airflow, not those CSVs — `load_status='baseline'` and
  the notes field flag this. Re-run `freshness backfill` after each Airflow load
  to refresh counts (or fold it into the pipeline).

## Deliberately deferred (do not assume these exist)

- Metrics / semantic layer (separate module — the real accuracy lever).
- Hard PK/FK constraints and `VARCHAR→DATE` conversion (gated on a clean
  `quality run`).
- Scheduled ETL / real production tables (currently `*_sample_data`, manual load).
- Query/audit logging and the feedback-harvesting loop (the `message_rating` /
  `message_rating_feedback` columns are the available signal for it later).

## Next obvious step

Run `python -m ua_api.data_context quality run` against the live DB to measure how dirty
the data actually is — that report decides whether constraint enforcement and
type tightening are feasible in the next phase.
