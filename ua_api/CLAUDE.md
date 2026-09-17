# CLAUDE.md — ua_api package

> Top-level instructions for the `ua_api/` package. These sit **below** the
> repo-root `CLAUDE.md` and **above** each submodule's own `CLAUDE.md`. When
> working inside a submodule, its CLAUDE.md takes precedence on module-specific
> detail; these rules apply everywhere in `ua_api/`.

## What this package is

`ua_api` is the **analytics support layer** for NEP User Analytics, built around
Anthropic's self-service analytics architecture. It is additive — it never edits
the existing `chat_api/` backend directly; it provides modules that can be
mounted beside it.

```
ua_api/
├── data_context/   # Data Foundations + metadata (catalog, quality, freshness, ingest, migrations, api)
└── metrics/        # Certified metrics / semantic layer (registry, params, renderer, resolver, api)
```

The two submodules are **intentionally separate concerns** (you could extract
either to its own package without touching the other), but they share
`data_context.config` as their database access point and `data_context.catalog`
as the vocabulary source for segment validation.

## Non-negotiable package rules

1. **Never edit `chat_api/`.** This package is additive. Each submodule has its
   own `api/models.py` + `api/main.py` and is mounted via `include_router` — not
   by modifying `chat_api/main.py` or `chat_api/models.py`.
2. **Credentials from env only.** Both submodules load `chat_api/.env` via
   `dotenv` at import time. No hardcoded keys, ever.
3. **`data_context` is the authority for data shape.** `metrics` reads
   `data_context.catalog` for segment enum validation. Do not duplicate column
   lists or enum vocabularies in `metrics/`.
4. **LLM never writes SQL for certified metrics.** The resolver's only job is
   to classify a question to a metric name + params (one LLM call). All SQL is
   pre-written in `definitions/*.yaml` templates.
5. **Graceful degradation throughout.** If the metrics path fails (bad params,
   LLM timeout, no match) the caller falls back to text-to-SQL. If the catalog is
   unavailable, segment validation degrades to permissive. Health endpoints return
   `degraded` rather than 500.

## REPO_ROOT anchor depths

Both submodules need to find `chat_api/.env` relative to the repo root:

| File | `REPO_ROOT` expression |
|------|------------------------|
| `ua_api/data_context/config.py` | `Path(__file__).resolve().parent.parent.parent` |
| `ua_api/metrics/config.py` | `Path(__file__).resolve().parent.parent.parent` |

If you add another submodule at `ua_api/<name>/config.py`, the same
`.parent.parent.parent` depth applies — one for the file, one for `<name>/`,
one for `ua_api/`, arrives at repo root.

## Inter-module import rule

Use **relative imports** for any cross-submodule reference within `ua_api`:

```python
from ..data_context.catalog import load_catalog  # in ua_api/metrics/...
from ..data_context.config import run_sql         # in ua_api/metrics/...
```

Absolute `from data_context.xxx` breaks when the package is imported from
outside the repo root (e.g. tests, uvicorn, the future chat adapter).

## Running commands

```bash
# data_context
python -m ua_api.data_context catalog show
python -m ua_api.data_context quality run
python -m ua_api.data_context freshness show
uvicorn ua_api.data_context.api.main:app --port 8001

# metrics
python -m ua_api.metrics list
python -m ua_api.metrics validate
python -m ua_api.metrics answer "how many MAU last month?"
uvicorn ua_api.metrics.api.main:app --port 8002
```

## Adding a new submodule

1. Create `ua_api/<name>/config.py` — load `chat_api/.env`, set `REPO_ROOT` as
   above.
2. Create `ua_api/<name>/api/models.py` + `main.py` — self-contained, no
   `chat_api` imports.
3. Use relative imports for any dependency on `data_context` or `metrics`.
4. Add a `CLAUDE.md` + `MEMORY.md` under `ua_api/<name>/` following the
   same structure as the existing submodules.
5. Note the new module in this file and in `ua_api/MEMORY.md`.

## What not to do

- Do not run `python -m ua_api.data_context ingest --truncate` against the live
  DB. Live tables are loaded by Airflow (154,904+ activity rows); sample CSVs
  would overwrite them.
- Do not apply migrations 002 or 003 without the data team / Airflow owner
  sign-off (requires `airflow_loader` table ownership — see `data_context/MEMORY.md`).
- Do not commit secrets. The committed Supabase service key in
  `upload_to_supabase.py` and `verify_upload.py` still needs rotating in Supabase
  (ops action; tracked in `data_context/MEMORY.md`).
