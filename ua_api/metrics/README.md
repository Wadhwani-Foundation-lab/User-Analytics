# metrics — Certified Metrics / Semantic Layer (Phase 1)

Implements the **"Sources of Truth"** layer from Anthropic's self-service
analytics architecture. Certified metrics are the **default path**: for a known
question, Claude only *classifies* the question to a metric and *extracts
parameters* — the backend renders a reviewed, version-controlled SQL template.
The LLM never writes SQL for a matched metric. Free-form text-to-SQL is the
fallback.

> *"If a question maps cleanly to a defined metric, the agent calls a function
> and gets one number."*

## Why this raises accuracy
The hallucination surface for the ~40 questions in `questions_to_sql.md` is
removed: the SQL is certified and parameters are validated. A drift like
`activity_type='ai_chat'` (instead of `message`) is now **structurally
impossible** — segment values are checked against the `data_context` catalog
vocabulary before rendering.

## Flow
```
question
  └─ resolve()  ── LLM classify → {metric, params} | null
        ├─ match → render() certified template (params validated) → run_sql (read-only)
        └─ null  → caller falls back to existing text-to-SQL
```

## Layout
```
metrics/
├── config.py        # env loading + model id
├── registry.py      # load definitions/*.yaml → Metric objects
├── params.py        # validate params (dates, choices, catalog-checked segments)
├── renderer.py      # Metric + params → trusted SQL (no leftover placeholders)
├── resolver.py      # LLM classify (resolve) + full path (answer)
├── definitions/     # 8 certified metrics (YAML), seeded from questions_to_sql.md
├── __main__.py      # CLI
└── api/             # self-contained endpoint (mount or run standalone)
```

## CLI
```bash
python -m ua_api.metrics list
python -m ua_api.metrics show active_users
python -m ua_api.metrics render active_users --params '{"grain":"week","period":{"start":"2026-01-01","end":"2026-02-01"}}'
python -m ua_api.metrics validate                 # run every template against the live DB
python -m ua_api.metrics resolve "how many MAU over time?"
python -m ua_api.metrics answer  "how many users registered in January 2026?"
```

## Integration (opt-in — chat_api is NOT modified)
```bash
# Standalone
uvicorn ua_api.metrics.api.main:app --port 8002
#   POST /api/metric-answer {question, today?}  → {matched, metric, sql, rows, ...}
#   GET  /api/metrics                            → certified catalog
```
```python
# Or mount into the existing app at composition time:
from ua_api.metrics.api.main import router as metrics_router
app.include_router(metrics_router)
```
The intended wiring: in the chat flow, call `metrics.answer(question)` first; if
`matched` is true, format `rows` using the returned `response_type`/`label`/
`value` (same formatter as today); otherwise fall through to the current
text-to-SQL path. That adapter is a small, separate step to approve.

## Metrics included (first increment — 8)
`active_users` (DAU/WAU/MAU) · `new_registrations` ·
`registration_to_question_conversion` · `repeat_users` · `power_users` ·
`event_attendance_rate` · `mentors_by_industry` · `activity_type_breakdown`.
All validated against the live DB and traced to their `questions_to_sql.md`
source. ~12–17 more metrics remain to cover the full corpus.

## Built on data_context
- `data_context.config.run_sql` — read-only execution (same trusted path)
- `data_context.catalog` — segment values validated against enum vocabularies;
  metric grain choices reflect the corrected mentor/activity grain findings

## Relationship to sql_cache.py
The registry supersedes the cache for *known, parameterised* questions
(deterministic + correct beats verbatim-string match). The cache stays useful
for arbitrary free-form questions that fall through to text-to-SQL.

## Deliberately Phase 1 (not yet)
- Resolution is an LLM classification call, **not tool-use** — Phase 2 turns
  `resolve()` into a `get_metric()` tool with no registry change.
- No automatic wiring into `/api/chat` (opt-in adapter pending).
- Eval harness over the metric set is Phase 4.
