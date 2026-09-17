# CLAUDE.md — metrics module

> Module-scoped instructions for `ua_api/metrics/`. These sit below the
> `ua_api/CLAUDE.md` and add detail specific to the certified-metrics layer.

## What this module is

`metrics` is the **Certified Metrics / Semantic Layer** for NEP User Analytics.
It provides a curated library of reviewed, parameterised SQL templates that the
LLM can match to a user's question without ever writing SQL itself.

```
metrics/
├── definitions/    # one YAML per certified metric
├── registry.py     # YAML loader → typed Metric objects
├── params.py       # parameter validation (dates, choices, catalog segments)
├── renderer.py     # safe SQL rendering (placeholder substitution, leak check)
├── resolver.py     # LLM classifier: question → {metric, params} or null
├── config.py       # env loading (chat_api/.env), LLM model name
├── __main__.py     # CLI (list / show / render / validate / resolve / answer)
└── api/            # standalone FastAPI router (GET /api/metrics, POST /api/metric-answer)
    ├── models.py
    └── main.py
```

## Core invariants

1. **The LLM never writes SQL.** The resolver makes one classification call and
   returns `{metric, params}` or `null`. All SQL lives in `definitions/*.yaml`,
   reviewed by humans.
2. **Every parameter is validated before rendering.** Dates → regex, choices →
   allowed set, segments → `data_context.catalog` enum vocabulary. A `ParamError`
   causes graceful fallback, never a raw string in SQL.
3. **No leftover placeholders.** `renderer.py` checks for un-substituted
   `{...}` tokens after rendering and raises `ValueError` rather than sending
   broken SQL to the DB.
4. **`matched=False` is a valid, expected result.** The resolver returns `None`
   for a low-confidence or unmatched question; `answer()` returns `{"matched": False}`.
   Callers MUST handle this by falling back to text-to-SQL — never surface the
   miss as an error.
5. **No imports from `chat_api/`.** The module is self-contained except for
   the relative cross-module path to `data_context` (`..data_context.config`,
   `..data_context.catalog`).

## Adding a new metric

1. Create `definitions/<metric_name>.yaml` following the schema below:
   ```yaml
   name: <slug>           # unique, snake_case
   description: |         # natural-language, used verbatim in resolver prompt
     ...
   aliases: []            # alternative names the LLM might use
   certified: true
   owner: analytics-team
   source: "Q<N>"         # questions_to_sql.md question number(s)
   returns:
     response_type: table | bar_chart | line_chart | text
     label: <column>      # label column for charts
     value: <column>      # value column for charts / text
   date_filter:           # omit if metric has no date range
     column: <col_name>
   choices:               # omit if no discrete params
     grain:
       default: month
       map:
         month: { ... }
         week:  { ... }
         day:   { ... }
   segment:               # omit if no segmentation
     column: <col_name>
     table: <catalog_table_name>
   sql_template: |
     SELECT ...
     {DATE_FILTER}        # injected by renderer when period given
     {SEGMENT_FILTER}     # injected by renderer when segment given
     LIMIT 500
   ```
2. Add natural-language aliases a user might phrase. The resolver's accuracy
   depends on good aliases and a clear description.
3. Run `python -m ua_api.metrics validate --name <name>` against the live DB.
4. Run `python -m ua_api.metrics resolve "<a typical question>"` to confirm the
   classifier picks it up at confidence ≥ 0.5.

## SQL template rules

- Always include `LIMIT 500`.
- CTEs (`WITH ... AS`) are supported by the Supabase `execute_sql` RPC (verified).
  Existing templates use subquery form by convention; either is valid.
- For mentor counts, always `COUNT(DISTINCT user_id)` — the mentor table is
  exploded ~33×.
- The `{DATE_FILTER}` and `{SEGMENT_FILTER}` placeholders are injected as
  `AND <col> >= '<start>' AND <col> < '<end>'` and
  `AND <col> = '<value>'`. Prefix accordingly (`WHERE 1=1` makes appending safe).
- Dates in `nep_master_live_events_data` are real `TIMESTAMP`, so `TO_CHAR` works.
  All other date columns are `DATE`; simple string comparison (`>=`, `<`) is fine.

## Commands

```bash
python -m ua_api.metrics list                        # all metrics + params
python -m ua_api.metrics show <name>                 # detail + SQL template
python -m ua_api.metrics render <name> [--params JSON]  # rendered SQL, no DB
python -m ua_api.metrics validate [--name N]         # render defaults → live DB
python -m ua_api.metrics resolve "<question>"        # classification only
python -m ua_api.metrics answer "<question>"         # full path + live execution
uvicorn ua_api.metrics.api.main:app --port 8002
```

## Gotchas

- `config.py` is imported for its side-effect: loading `chat_api/.env` so
  `ANTHROPIC_API_KEY` is set before `resolver.py` calls `anthropic.Anthropic()`.
  Import `MODEL` from `config`, not directly from `os.getenv`.
- The resolver's confidence threshold is `min_confidence=0.6`. Questions that
  loosely match but score below this return `null` (text-to-SQL fallback). Adjust
  per metric by setting a higher floor in the caller if needed.
- `catalog_for_resolver()` produces the prompt fragment. Keep metric descriptions
  short and distinct — the LLM must disambiguate between 8+ candidates in a
  single call.
- The `api/` router is self-contained; when mounting into the main app, use
  `app.include_router(metrics_router, prefix="")` — prefixes are defined in the
  router itself.
