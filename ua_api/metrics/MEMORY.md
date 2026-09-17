# MEMORY.md — metrics module

> Durable notes on why this module is shaped the way it is. Read before changing
> architecture or reversing a decision. For data-level facts (table shapes,
> quality findings), see `../data_context/MEMORY.md`.

## Why the module exists

The existing `chat_api` backend sends every user question to the LLM as a
free-form text-to-SQL request. Known queries (DAU, MAU, registration funnels,
activity breakdowns) hit the same single-LLM path as exotic one-offs, with no
guarantee of correctness on the repeated cases.

`metrics` is the **certified metrics layer**: SQL for known questions is written
once by a human, reviewed, stored in YAML, and rendered deterministically.
The LLM's role is narrow: classify the question to a metric name, extract date
range / grain / segment from the phrasing. It never writes SQL for a matched
metric. This mirrors Anthropic's reported accuracy jump when a semantic layer is
added on top of raw text-to-SQL.

## Design decisions

- **Single LLM classification call, not tool-use (Phase 1).** The resolver calls
  Claude once with the full metric catalog and expects a JSON object back. No
  tool-use API. This keeps Phase 1 simple and the prompt inspectable.
  When Phase 2 lands, the resolver becomes a `get_metric()` tool call with
  identical registry YAML — no schema change needed.

- **`matched=False` is first-class, not an error.** The caller (future chat
  adapter) must handle it by falling back to text-to-SQL. Do not convert a no-match
  into an error or a default metric. Overconfident matching is worse than a miss.

- **Segment values validated against `data_context.catalog`.** The resolver
  could hallucinate segment values (e.g. `activity_type='ai_chat'` which doesn't
  exist). `params.py` rejects these before they reach SQL. If the catalog can't
  be loaded, validation degrades to permissive (never blocks).

- **No CTEs in SQL templates.** The Supabase `execute_sql` RPC does not support
  CTEs. All templates use subqueries.

- **Mentor metrics always `COUNT(DISTINCT user_id)`.** The mentor table has
  ~49,486 rows but only 1,515 distinct mentors (exploded ~33× for multi-valued
  attributes). `COUNT(*)` overcounts by that factor. This is encoded in the
  `mentors_by_industry` template and is a hard rule for any new mentor metric.

- **`definitions/*.yaml` are the single source of truth for certified SQL.**
  Do not duplicate SQL logic in `resolver.py`, `__main__.py`, or the API.
  The registry loader is the only reader; if a YAML changes, the change is
  immediately live on the next `load_registry()` call.

## Initial 8 metrics (all validated against live DB, 2026-06-09)

| Metric | Response type | Source | Key params |
|--------|---------------|--------|------------|
| `active_users` | line_chart | Q1, Q3 | grain (month/week/day), period, segment |
| `activity_type_breakdown` | bar_chart | Q27 | period |
| `event_attendance_rate` | table | Q24 | period |
| `mentors_by_industry` | bar_chart | Q21 | none |
| `new_registrations` | text | Q5 | period |
| `power_users` | bar_chart | Q16 | none |
| `registration_to_question_conversion` | table | Q7 | period |
| `repeat_users` | table | Q14 | none |

## End-to-end verification (2026-06-09)

- `python -m ua_api.metrics validate` → 8/8 pass against live DB.
- `python -m ua_api.metrics answer "how many MAU over time?"` → resolver matched
  `active_users` (grain=month), rendered certified SQL, returned real row data.
- Segment rejection working: `activity_type='ai_chat'` blocked by catalog
  (not in enum vocabulary).
- `.env` load chain confirmed: `config.py` loads `chat_api/.env`; `ANTHROPIC_API_KEY`
  present for `resolver.py`.

## What is deferred

- **~12-17 additional metrics** to cover the full `questions_to_sql.md` corpus.
  Prioritise questions that recur most in user history.
- **Chat adapter** — a new `ua_api/chat_adapter/` module (NOT editing `chat_api/`)
  that wraps `metrics.answer()` as an opt-in pre-check before the existing LLM
  text-to-SQL path.
- **Phase 2: native tool-use resolver** — replace the single-call classify with a
  `get_metric()` tool. No YAML changes needed; only `resolver.py` changes.
- **Resolver confidence tuning** — currently `min_confidence=0.5`. Measure false
  positive rate on real user questions before adjusting.

## Next obvious step

Expand the metric definitions from 8 to ~20 by mining `docs/questions_to_sql.md`
for recurring, parameterisable queries. Prioritise metrics where text-to-SQL is
known to make mistakes (mentor counts, activity type filters, funnel queries).
