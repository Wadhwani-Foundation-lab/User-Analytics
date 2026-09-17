# CLAUDE.md — data_context module

> Module-scoped instructions. These apply when working anywhere under
> `data_context/`. They sit **below** the repo-root `CLAUDE.md` and add detail
> specific to the data-foundation layer.

## What this module is

`data_context` is the **Data Foundations + first-class metadata** layer for NEP
User Analytics, modelled on Anthropic's self-service analytics architecture. It
exists to make the data *trustworthy* before the assistant queries it:

- **catalog/** — machine-readable metadata; the single source of truth
- **quality/** — read-only data-quality & integrity checks
- **freshness/** — load provenance tracking (`nep_data_catalog` table)
- **ingest/** — governed CSV → Supabase pipeline (env creds, validated)
- **migrations/** — reviewable, non-destructive DDL
- **api/** — self-contained freshness-aware health endpoint (own `models.py`/`main.py`)

## Non-negotiable conventions

1. **Read-only by default.** All validation/inspection runs as `SELECT` through
   the existing `execute_sql` RPC (`config.run_sql`). Never route DDL/DML through
   it — the RPC blocks it anyway. Structural change is *emitted as SQL* for human
   review, not applied implicitly.
2. **The catalog is the source of truth.** `quality`, `migrations`, and (later)
   the semantic layer all read from `catalog/tables/*.yaml`. Add a fact once, in
   the catalog — don't hardcode column lists, enum values, or join keys anywhere
   else.
3. **A human owns the definitions.** YAML may be *drafted* from
   `docs/schema_reference.md`, but descriptions/enums/grain are reviewed by a
   person. Don't silently invent enum vocabularies.
4. **No hardcoded credentials, ever.** Credentials come from env / `chat_api/.env`
   via `config.py`. The whole point of the `ingest` rewrite was to kill the
   service key that was committed in `upload_to_supabase.py` / `verify_upload.py`.
5. **Do not edit `chat_api/` from here.** This module is additive. The `api`
   submodule deliberately re-implements its own `models.py`/`main.py` and is
   *mounted* into the app rather than editing backend source.
6. **Phase discipline on DDL.** This phase emits **comments + indexes only**.
   Do NOT generate `PRIMARY KEY`/`FOREIGN KEY` constraints or `VARCHAR→DATE`
   type changes until a `quality run` against live data is clean — enforcing
   integrity on dirty data just errors.

## Data quirks the catalog already encodes (don't "fix" these)

- Join key is `userid` (**no underscore**) in `nep_liftoffx_data_sample`;
  `user_id` everywhere else.
- Intentional misspellings in the source data: `activity_type = 'jounrney_explore'`,
  column `activity_tittle` (double t), column `particpant_country` (missing i).
- `activity_type` vocabulary is closed — `message`, `mentor`, `session`,
  `resource`, `visitors`, `repeat visitors`, `signup`, `jounrney_explore`,
  `introductory_video_reg_users`. `ai_chat` / `mentor_session` / `live_event`
  do NOT exist; the enum check exists to catch exactly that drift.
- **Date-type ambiguity (unresolved):** `schema_reference.md` documents dates as
  `DATE`/`TIMESTAMP`, but `create_tables.sql` declares everything `VARCHAR(500)`.
  `catalog validate` reconciles this against the live DB. Until run, treat the
  physical type as unverified.
- `nep_master_live_events_data` has **no single-column PK** (grain is
  `event_id` × participant); its `primary_key` is intentionally `null`.

## Adding things

- **New table** → add `catalog/tables/<name>.yaml` (name, grain, owner,
  source_csv, primary_key, columns, joins). The CLI, checks, and migrations pick
  it up automatically.
- **New check** → add a function in `quality/checks.py` and call it from
  `run_all_checks`. Each check must be read-only and isolated (wrapped so one
  failure doesn't abort the run). Use `Status.WARN` for data smells on dirty
  sample data, `FAIL` for true defects, `ERROR` only when the check can't run.
- **New logical type** → extend `LOGICAL_TYPES` in `catalog/catalog.py`.

## Commands

```bash
python -m ua_api.data_context catalog show         # summarise the catalog
python -m ua_api.data_context catalog validate     # reconcile catalog vs live DB
python -m ua_api.data_context quality run [--table T]
python -m ua_api.data_context migrations emit      # regenerate 002/003 from catalog
python -m ua_api.data_context freshness show
python -m ua_api.data_context ingest [--table T] [--truncate]
uvicorn ua_api.data_context.api.main:app --port 8001
```

## Gotchas

- The module avoids reading the clock internally (resume-safety habit): the CLI
  passes `timestamp` into `quality.run` / `ingest`. Keep new entry points doing
  the same rather than calling `datetime.now()` deep in library code.
- `freshness.record_load` writes via the Supabase **table API** (PostgREST upsert),
  not the RPC — writes can't go through the read-only RPC.
- Quality checks that capture sample rows expect `v` (value) and `n` (count)
  aliases — keep that contract when adding sampling queries.
