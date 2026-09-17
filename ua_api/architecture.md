# ua_api — Architecture

> Detailed architecture reference for the `ua_api/` analytics support layer.
> This document describes every module, how they connect, the design decisions
> behind them, and how to extend the system.

---

## 1. Purpose and Positioning

`ua_api` is an **additive analytics layer** that sits around — not inside — the
existing `chat_api/` backend. It was built against Anthropic's recommended
4-layer self-service analytics architecture to improve answer accuracy, safety,
and observability without touching the deployed backend.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Anthropic Architecture Layer        ua_api Module                   │
│  ─────────────────────────────────   ───────────────────────────────  │
│  1. Data Foundations                 data_context/                   │
│  2. Sources of Truth (semantic)      metrics/                        │
│  3. Skills (prompt assembly)         skills/                         │
│  4. Validation                       validation/                     │
│  ── Cross-cutting ──────────────────────────────────────────────── ── │
│  Intercept proxy (certified answers) chat_adapter/                   │
│  Feedback signal loop                feedback/                       │
└──────────────────────────────────────────────────────────────────────┘
```

The existing `chat_api/` (FastAPI + Claude + Supabase) is never modified.
All `ua_api` modules add capability by wrapping or sitting beside it.

---

## 2. System Overview

```
                          ┌──────────────────────────────────────────┐
                          │  Browser  ·  Next.js 16 (port 3000)      │
                          │  chat_ui/                                  │
                          │  ProvenanceBadge  ·  ChatThread  ·  etc.  │
                          └────────────────┬─────────────────────────┘
                                           │ POST /api/chat
                                           │ (x-api-key header)
                                           ▼
          ┌────────────────────────────────────────────────────────┐
          │  chat_adapter  ·  FastAPI  (port 8001)                  │
          │  ua_api/chat_adapter/main.py                            │
          │                                                          │
          │  1. Auth check (x-api-key)                              │
          │  2. try_certified_answer(question)                       │
          │       ├─ resolver → metrics path (LLM tool-use call)    │
          │       └─ matched? ──yes──▶ render SQL ──▶ execute       │
          │                 │           ──▶ interpret_results        │
          │                 │           ──▶ persist to Supabase      │
          │                 │           ──▶ return ChatResponse      │
          │                 │              + Provenance badge        │
          │                 └──no──▶ proxy to chat_api (below)      │
          └───────────────────┬────────────────────────────────────┘
                              │ httpx proxy (non-certified questions)
                              ▼
          ┌───────────────────────────────────────────────────────┐
          │  chat_api  ·  FastAPI  (port 8003, internal only)      │
          │  chat_api/main.py                                       │
          │                                                          │
          │  Free-form text-to-SQL path:                            │
          │  question → Claude (LLM) → SQL → Supabase → answer     │
          └──────────────────┬────────────────────────────────────┘
                             │  execute_sql RPC (read-only)
                             ▼
          ┌────────────────────────────────────────────────────────┐
          │  Supabase PostgreSQL                                     │
          │  nep_master_user_table_sample_data    (user profiles)   │
          │  nep_liftoffx_data_sample             (activity/AI chat)│
          │  nep_master_live_events_data          (events)          │
          │  nep_mentor_profiles_sample_data      (mentors)         │
          │  nep_data_catalog                     (freshness/load)  │
          │  nep_chat_sessions + nep_chat_messages (conversations)  │
          └────────────────────────────────────────────────────────┘
```

---

## 3. Module Map

```
ua_api/
├── __init__.py
├── architecture.md          ← this file
├── CLAUDE.md                ← instructions for AI coding tools
├── MEMORY.md                ← durable decisions and build state
│
├── data_context/            ── Layer 1: Data Foundations ──────────────
│   ├── config.py            ·  Supabase client, run_sql(), env loading
│   ├── catalog/             ·  Machine-readable table/column metadata
│   │   ├── catalog.py       ·  Typed loader: YAML → Catalog/Table/Column
│   │   └── tables/          ·  4 YAML definitions (one per analytics table)
│   │       ├── nep_master_user_table_sample_data.yaml
│   │       ├── nep_liftoffx_data_sample.yaml
│   │       ├── nep_master_live_events_data.yaml
│   │       └── nep_mentor_profiles_sample_data.yaml
│   ├── quality/             ·  Read-only data quality + integrity checks
│   │   ├── checks.py        ·  6 check families (enum, FK, null, unique, date, volume)
│   │   └── runner.py        ·  Runs all checks; emits CheckResult[]
│   ├── freshness/           ·  Load provenance tracking
│   │   └── freshness.py     ·  record_load(), get_freshness(); writes nep_data_catalog
│   ├── ingest/              ·  Governed CSV → Supabase pipeline
│   │   └── pipeline.py      ·  Env-credential upload (replaces hardcoded key)
│   ├── migrations/          ·  Reviewable DDL emission (column comments, indexes)
│   │   └── generate.py      ·  Emits migrations 002 and 003 from catalog metadata
│   ├── api/                 ·  Self-contained FastAPI router
│   │   ├── models.py
│   │   └── main.py          ·  GET /api/health, /api/freshness, /api/catalog
│   └── __main__.py          ·  CLI: python -m ua_api.data_context <cmd>
│
├── metrics/                 ── Layer 2: Certified Metrics (Semantic Layer) ─
│   ├── config.py            ·  Env loading, LLM model name
│   ├── registry.py          ·  YAML → typed Metric/Choice/DateFilter/Segment
│   ├── params.py            ·  Date, choice, catalog-segment parameter validation
│   ├── renderer.py          ·  Safe SQL rendering (placeholder substitution)
│   ├── resolver.py          ·  LLM tool-use classifier: question → {metric, params}
│   ├── definitions/         ·  20 certified metric YAML files
│   │   ├── active_users.yaml
│   │   ├── new_registrations.yaml
│   │   ├── repeat_users.yaml
│   │   ├── total_questions_asked.yaml
│   │   ├── questions_growth.yaml
│   │   ├── weekly_retention.yaml
│   │   ├── retention_by_channel.yaml
│   │   ├── user_engagement_tiers.yaml
│   │   ├── power_users.yaml
│   │   ├── activity_type_breakdown.yaml
│   │   ├── user_type_engagement.yaml
│   │   ├── signup_to_first_message.yaml
│   │   ├── registration_to_question_conversion.yaml
│   │   ├── mentors_by_stage.yaml
│   │   ├── mentors_by_industry.yaml
│   │   ├── mentor_sessions_by_industry.yaml
│   │   ├── events_by_program.yaml
│   │   ├── monthly_events_trend.yaml
│   │   ├── event_attendance_rate.yaml
│   │   └── event_noshow_by_gap.yaml
│   ├── api/                 ·  Standalone FastAPI router
│   │   ├── models.py
│   │   └── main.py          ·  GET /api/metrics, POST /api/metric-answer
│   └── __main__.py          ·  CLI: python -m ua_api.metrics <cmd>
│
├── skills/                  ── Layer 3: Modular System Prompt Assembly ──
│   ├── blocks.py            ·  9 focused prompt-block constants
│   └── prompt_builder.py    ·  build_prompt(profile) → SYSTEM_PROMPT string
│
├── chat_adapter/            ── Certified-Metrics Proxy ─────────────────
│   ├── config.py            ·  UPSTREAM_CHAT_URL, API_SECRET_KEY, env
│   ├── models.py            ·  ChatRequest / ChatResponse / Provenance (mirrors chat_api)
│   ├── formatter.py         ·  Chart + table formatting (replicated palette)
│   ├── interpreter.py       ·  interpret_results() + explain_empty_results()
│   ├── interceptor.py       ·  try_certified_answer() — the intercept core
│   └── main.py              ·  FastAPI app: /api/chat + catch-all proxy
│
├── validation/              ── Layer 4: Evaluation Harness ──────────────
│   ├── eval_set.py          ·  15 frozen EvalCase records
│   └── runner.py            ·  Ablation runner (certified_only, adapter, sql_guard)
│   └── __main__.py          ·  CLI: python -m ua_api.validation
│
└── feedback/                ── Feedback Signal Loop ──────────────────────
    ├── signals.py           ·  overall_rating(), rating_by_period(), low_rated_questions()
    └── __main__.py          ·  CLI: python -m ua_api.feedback
```

---

## 4. Data Flow: Certified Metric Path

This is the primary accuracy improvement. Questions that match a certified metric
never go through the LLM's SQL generation — they execute a human-reviewed
SQL template instead.

```
User question: "how many monthly active users in Q4 2025?"
    │
    ▼
chat_adapter/interceptor.py  ── try_certified_answer()
    │
    ├─ 1. RESOLVE  ───────────────────────────────────────────────────────
    │   metrics/resolver.py  ── resolve(question, registry, today)
    │   │
    │   │  Builds a METRIC CATALOG from the registry (names + descriptions
    │   │  + aliases + param signatures) and sends ONE LLM call:
    │   │
    │   │  Claude tools=[get_metric]  (metric names enumerated as enum)
    │   │   └─ tool_choice="auto"  → Claude may or may not call the tool
    │   │
    │   │  If Claude calls get_metric: returns {metric, params, confidence}
    │   │  If Claude responds with text (no tool call): returns None → fallback
    │   │
    │   └─ Result: {metric: "active_users", params: {period: {...}, grain: "month"},
    │               confidence: 0.95}
    │
    ├─ 2. RENDER  ────────────────────────────────────────────────────────
    │   metrics/renderer.py  ── render(metric, params)
    │   │
    │   │  Validates every param:
    │   │    - dates → regex check + chronological order
    │   │    - choices (grain) → allowed enum in metric definition
    │   │    - segments → catalog enum vocabulary (no invented values)
    │   │
    │   │  Substitutes placeholders in sql_template:
    │   │    {grain_select}    → "month_year AS period, month_year_order,"
    │   │    {grain_group}     → "month_year, month_year_order"
    │   │    {grain_order}     → "month_year_order"
    │   │    {date_filter}     → " AND message_date >= '2025-10-01'
    │   │                           AND message_date < '2026-01-01'"
    │   │
    │   │  Leak check: raises ValueError if any {placeholder} remains
    │   │
    │   └─ Result: rendered SQL string (no CTEs, LIMIT 500, fully safe)
    │
    ├─ 3. EXECUTE  ───────────────────────────────────────────────────────
    │   data_context/config.py  ── run_sql(sql)
    │   │
    │   └─ Supabase execute_sql RPC → [{period: "Oct 2025", active_users: 417}, ...]
    │
    ├─ 4. FORMAT  ────────────────────────────────────────────────────────
    │   chat_adapter/formatter.py  ── build_chart() / build_table()
    │   │
    │   └─ ChartConfig(type="line", labels=[...], datasets=[...])
    │
    ├─ 5. INTERPRET  ─────────────────────────────────────────────────────
    │   chat_adapter/interpreter.py  ── interpret_results(question, rows)
    │   │
    │   └─ "Monthly active users peaked in November 2025 at 1,425 users..."
    │
    ├─ 6. PERSIST  ───────────────────────────────────────────────────────
    │   chat_adapter/interceptor.py  ── _persist() [fire-and-forget]
    │   │
    │   └─ Writes user + assistant turns to nep_chat_messages (Supabase table API)
    │
    └─ 7. RESPOND
        ChatResponse(
          answer="Monthly active users peaked...",
          response_type="line_chart",
          chart_config={...},
          session_id="...",
          provenance={certified: true, metric: "active_users",
                      confidence: 0.95, metric_source: "questions_to_sql.md#Q1,Q3"}
        )
```

---

## 5. Data Flow: Text-to-SQL Fallback Path

When the resolver returns `None` (no certified metric match), the adapter
transparently proxies the request to `chat_api/` unchanged:

```
User question: "which users registered after Feb 2026?"
    │
    ▼
chat_adapter  ── try_certified_answer() returns None
    │
    ▼  httpx.AsyncClient POST → http://localhost:8003/api/chat
    │
    ▼
chat_api/main.py
    ├─ Build system prompt from docs/schema_reference.md + questions_to_sql.md
    ├─ Claude (claude-sonnet-4-5): question + history → {sql, response_type, ...}
    ├─ Supabase execute_sql RPC → rows
    ├─ interpret_results(question, rows)  ← LLM prose narration
    └─ ChatResponse(answer=..., response_type=..., sql_used=..., provenance=None)
```

The frontend receives identical `ChatResponse` shapes from both paths. The only
difference: `provenance` is populated on the certified path and `null` on the
text-to-SQL path. The `ProvenanceBadge` component renders only when
`provenance.certified === true`.

---

## 6. Module Detail

### 6.1 data_context — Data Foundations

The lowest layer. Its job is to make the data *machine-readable and trustworthy*
before any query touches it.

#### Catalog

Four YAML files (one per analytics table) are the single source of truth for:

| Property | Used by |
|---|---|
| Column names + logical types | quality checks, migration DDL |
| Enum vocabularies | quality enum validation, param validation in metrics |
| Join declarations | quality FK checks, documentation |
| Primary key | uniqueness checks |
| Source CSV path | ingest pipeline |
| Owner role | migration DDL (`SET ROLE`) |

The `load_catalog()` function validates join targets at load time — a bad YAML
reference is a hard error, not a silent miss.

#### Quality checks

Six families run read-only against the live DB via the same `execute_sql` RPC
the analytics assistant uses:

| Family | What it checks |
|---|---|
| `referential_integrity` | FK values that have no parent row |
| `enum_validation` | Column values outside the catalog's allowed vocabulary |
| `null_keys` | NULLs in declared key columns |
| `uniqueness` | Duplicate primary-key values |
| `date_format` | Date strings that don't match the documented format |
| `volume` | Row counts (sanity / emptiness guard) |

Results: `PASS / WARN / FAIL / ERROR`. WARN is used for known data-quality
smells in sample data that aren't defects (e.g. nullable orphans expected from
sampling). FAIL is for genuine defects. This distinction matters because the
sample data was not drawn consistently across tables, so cross-table joins
have known orphan counts.

#### Freshness

`nep_data_catalog` table (migration 001, applied) stores load provenance:

```
table_name | loaded_at | row_count | loaded_by | notes
```

`record_load()` writes via the Supabase table API (not the read-only RPC).
`get_freshness()` exposes this through the health endpoint so the assistant could
answer "when was the data last updated?" from metadata, not a live query.

#### Migrations

Generates DDL for human review — never applies automatically:
- Migration 002: `COMMENT ON COLUMN` for every documented column description
- Migration 003: `CREATE INDEX` on join keys (requires `airflow_loader` ownership)

Both deferred until the analytics table owner (Airflow role) can co-own the DDL.

---

### 6.2 metrics — Certified Metrics / Semantic Layer

The core accuracy layer. The fundamental invariant: **the LLM never writes SQL
for a certified metric**. The LLM's only job here is classification.

#### Metric YAML schema

```yaml
name: active_users                    # snake_case, unique
description: |                        # fed verbatim to the resolver prompt
  Distinct users who asked at least one AI question per period...
aliases: ["MAU", "monthly active users", ...]  # alternate phrasings
certified: true
owner: analytics-team
source: questions_to_sql.md#Q1,Q3    # traceability to the example set

returns:
  response_type: line_chart           # drives frontend rendering
  label: period                       # chart X-axis / label column
  value: active_users                 # chart Y-axis / value column

date_filter:
  column: message_date                # which column receives the date range filter

choices:
  grain:                              # discrete parameter
    default: month
    map:
      month: { grain_select: "...", grain_group: "...", grain_order: "..." }
      week:  { ... }
      day:   { ... }

segment:
  column: user_type                   # optional categorical breakdown
  table: nep_liftoffx_data_sample     # catalog table to validate enum values from

sql_template: |
  SELECT {grain_select}
         COUNT(DISTINCT userid) AS active_users
  FROM nep_liftoffx_data_sample
  WHERE activity_type = 'message'{date_filter}{segment_filter}
  GROUP BY {grain_group}
  ORDER BY {grain_order}
  LIMIT 500
```

The `{date_filter}` and `{segment_filter}` placeholders expand to `AND col >= 'date'
AND col < 'date'` or `AND col = 'value'` respectively. When no period or segment
is provided, they expand to empty strings.

#### Resolver — tool-use API

The resolver uses Claude's native `tools=` parameter rather than asking Claude
to produce JSON and parsing the output. This eliminates hallucinated metric names
at the structural level: metric names are enumerated as an `enum` in the tool's
input schema. Claude can only return a name that exists in the registry.

```
Claude API call:
  model:  claude-sonnet-4-5
  system: "You are a metric router. Call get_metric only when a metric clearly fits."
  tools:  [{
    name: "get_metric",
    input_schema: {
      properties: {
        metric: { type: "string", enum: ["active_users", "new_registrations", ...] },
        params: { ... period, grain, segment ... },
        confidence: { type: "number", min: 0, max: 1 },
        reason: { type: "string" }
      }
    }
  }]
  messages: [{ role: "user", content: "TODAY: ...\nMETRIC CATALOG: ...\nQUESTION: ..." }]

Response:
  tool_use block → get_metric({ metric: "active_users", params: {...}, confidence: 0.95 })
  OR
  text block     → no tool call, matched=False, fall back to text-to-SQL
```

The confidence gate (`min_confidence=0.5`) rejects forced low-confidence matches.
Questions that loosely fit two metrics will fall below 0.5 and go to text-to-SQL.

#### 20 certified metrics

| Metric | Category | Response type |
|---|---|---|
| `active_users` | Engagement | line_chart |
| `new_registrations` | Growth | text / bar_chart |
| `repeat_users` | Retention | text |
| `total_questions_asked` | AI Chat | text |
| `questions_growth` | AI Chat | line_chart |
| `weekly_retention` | Retention | table |
| `retention_by_channel` | Retention | bar_chart |
| `user_engagement_tiers` | Engagement | bar_chart |
| `power_users` | Engagement | bar_chart |
| `activity_type_breakdown` | Engagement | bar_chart |
| `user_type_engagement` | Engagement | table |
| `signup_to_first_message` | Funnel | bar_chart |
| `registration_to_question_conversion` | Funnel | text |
| `mentors_by_stage` | Mentors | bar_chart |
| `mentors_by_industry` | Mentors | bar_chart |
| `mentor_sessions_by_industry` | Mentors | bar_chart |
| `events_by_program` | Events | table |
| `monthly_events_trend` | Events | line_chart |
| `event_attendance_rate` | Events | table |
| `event_noshow_by_gap` | Events | bar_chart |

---

### 6.3 skills — Modular System Prompt Assembly

The monolithic `chat_api/system_prompt.py` (~15,000 chars) was decomposed into
9 independently readable block constants. The assembler (`prompt_builder.py`)
combines them per question type via preset profiles.

#### Blocks

| Block | Content | Size |
|---|---|---|
| `IDENTITY` | Who the assistant is | ~3 lines |
| `OUTPUT_FORMAT` | Mandatory JSON response contract + safety | ~15 lines |
| `RESPONSE_TYPES` | When to use each `response_type` | ~10 lines |
| `ENUM_VALUES` | Exact allowed vocabulary (never invent) | ~20 lines |
| `DATE_HANDLING` | Column types, date arithmetic, casting rules | ~20 lines |
| `SQL_RULES` | 14 numbered SQL construction rules | ~30 lines |
| `COLUMN_MAP` | Which column lives in which table | ~25 lines |
| `PERFORMANCE` | Anti-timeout patterns (pre-aggregate, no correlated subqueries) | ~15 lines |
| `CLARIFICATION` | When and how to ask for clarification | ~5 lines |

#### Profiles

```python
"full"    → all 9 blocks + schema docs  (drop-in replacement for monolith)
"minimal" → identity + output + enums + clarification  (fast cheap questions)
"sql"     → minimal + response_types + date + sql_rules + column_map
"events"  → full (all blocks, emphasis on event/mentor SQL)
```

The `SYSTEM_PROMPT` singleton at module level is a drop-in replacement for
`chat_api/system_prompt.py`:
```python
from ua_api.skills.prompt_builder import SYSTEM_PROMPT
```

---

### 6.4 chat_adapter — Certified-Metrics Proxy

The proxy is the only runtime component users interact with. It is a FastAPI app
that wraps `chat_api` via HTTP reverse proxy using `httpx`.

#### Why proxy, not monkey-patch

Modifying `chat_api/main.py` in-place was ruled out by the project constraint
("no chat_api edits"). The proxy approach keeps the two concerns cleanly
separated: `chat_adapter` can be deployed or rolled back independently. In
production, `chat_api` moves to an internal-only port and `chat_adapter` becomes
the single ingress for the frontend.

#### Port layout (local development)

| Process | Port | Visibility |
|---|---|---|
| `chat_adapter` (this module) | 8001 | Public (frontend → here) |
| `chat_api` | 8003 | Internal only (adapter → here) |
| `chat_ui` (Next.js) | 3000 | Browser |

#### Provenance

Every certified answer carries a `Provenance` object:

```json
{
  "certified": true,
  "metric": "active_users",
  "confidence": 0.95,
  "metric_source": "questions_to_sql.md#Q1,Q3"
}
```

The frontend `ProvenanceBadge` component renders this as a green pill:
`✓ CERTIFIED METRIC · Active Users · 95% confidence`

The badge is invisible on text-to-SQL responses (`provenance: null`).

#### Session persistence

`_persist()` in `interceptor.py` writes directly to `nep_chat_messages` via
the Supabase table API (bypassing the read-only RPC). It is fire-and-forget
(wrapped in `try/except`) — a Supabase write failure never fails the HTTP
response. In production, sessions are created by the frontend via
`POST /api/sessions` before the first message, so the FK constraint on
`session_id` is satisfied.

---

### 6.5 validation — Evaluation Harness

A frozen set of questions with expected behaviour, used to prevent regressions
as metrics and prompt blocks evolve.

#### EvalCase fields

| Field | Purpose |
|---|---|
| `question` | Natural-language input |
| `expected_path` | `"certified"` or `"text_to_sql"` |
| `expected_metric` | Metric name (certified path only) |
| `must_contain_cols` | Output columns that must be present |
| `must_not_sql` | SQL fragments that must NOT appear (hallucination guards) |
| `min_rows / max_rows` | Row count bounds |
| `tags` | Filter tags (`retention`, `events`, `certified`, etc.) |

#### Three test modes

| Mode | What it tests | Requires |
|---|---|---|
| `certified_only` | Resolver + render + execute for certified path | Supabase connectivity |
| `adapter` | Full HTTP round-trip end to end | Adapter running on port 8001 |
| `sql_guard` | Anti-hallucination: `must_not_sql` fragments in generated SQL | Adapter running |

Column check degrades gracefully when rows are empty (e.g. future date range
query): falls back to scanning expected column names in the SQL SELECT clause.

```bash
python -m ua_api.validation                           # certified_only, all cases
python -m ua_api.validation --mode adapter            # full round-trip
python -m ua_api.validation --tag retention --verbose # filtered + details
python -m ua_api.validation --output results.json     # persist for CI
```

Exit code 0 = all pass, 1 = any failures. Suitable as a CI gate.

---

### 6.6 feedback — Quality Signal Loop

Reads `message_rating` and `message_rating_feedback` from
`nep_liftoffx_data_sample` to surface aggregate AI-chat quality.

```
low_rated_questions()  ──▶  review  ──▶  new EvalCase or new YAML metric
                                         ↑
                        The feedback loop closes here
```

The `message_rating` column is TEXT, cast to INTEGER via `::INTEGER` after
a guard `message_rating ~ '^[0-9]+$'`.

The forward-looking design: once the frontend sends back which certified metric
produced a response alongside a thumbs-up/down signal, `signals.py` can `GROUP
BY metric` to give per-metric quality scores. The `provenance.metric` field in
`ChatResponse` carries the metric name the frontend would send back.

---

## 7. Shared Infrastructure

### 7.1 Environment and credentials

All credentials load from `chat_api/.env` via `python-dotenv`. No module
hardcodes any secret. The loading order is:

1. `chat_api/.env` (the existing backend config, shared)
2. Process-level `.env` if present (override)
3. OS environment (highest priority, always wins)

Every `config.py` in every submodule does the same load:
```python
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ENV = REPO_ROOT / "chat_api" / ".env"
load_dotenv(_DEFAULT_ENV, override=False)
```

### 7.2 Database access

All read-only analytics queries go through `data_context/config.py:run_sql()`,
which calls the `execute_sql` Supabase RPC. This RPC:
- Accepts a single `SELECT` string
- Rejects all DDL/DML (enforced at the DB layer)
- Has an 8-second timeout
- Strips trailing semicolons before calling

Writes (freshness records, chat messages) go through the Supabase table API
directly (`get_client().table(name).insert(...).execute()`).

### 7.3 SQL constraints (all SQL in the system must follow these)

| Rule | Reason |
|---|---|
| No CTEs (`WITH ... AS`) | `execute_sql` RPC rejects them |
| `LIMIT 500` on every query | Prevents timeout from large result sets |
| No `NOW()`, `CURRENT_DATE` | All date comparisons use literal strings |
| No `COUNT(DISTINCT col) OVER(...)` | PostgreSQL does not support DISTINCT in window functions |
| Every JOIN column qualified with table alias | Prevents ambiguity in multi-table queries |
| `COUNT(DISTINCT user_id)` for mentor counts | Mentor profiles table is exploded ~33× |
| `userid` (no underscore) for activity FK | Intentional schema inconsistency in source data |

---

## 8. Dependency Graph

Cross-module imports within `ua_api` use relative paths:

```
chat_adapter  ──▶  metrics.resolver   (answer())
              ──▶  data_context.config (get_client() for persist)
              ──▶  interpreter, formatter (internal)

metrics       ──▶  data_context.config (run_sql() for execute)
              ──▶  data_context.catalog (segment enum validation in params.py)

validation    ──▶  metrics.resolver   (answer() in certified_only mode)

feedback      ──▶  data_context.config (run_sql())

skills        ──▶  (no ua_api imports — reads docs/ files only)
data_context  ──▶  (no ua_api imports — self-contained)
```

No module imports from `chat_api/`. All shapes that mirror `chat_api` are
re-declared locally (see `chat_adapter/models.py`).

---

## 9. Deployment

### Local development

```bash
# 1. Backend: move chat_api to internal port
cd chat_api
uvicorn main:app --reload --port 8003

# 2. Adapter: public-facing on the port the frontend expects
cd <repo-root>
uvicorn ua_api.chat_adapter.main:app --reload --port 8001

# 3. Frontend: no config change needed (NEXT_PUBLIC_API_URL=http://localhost:8001)
cd chat_ui
npm run dev   # port 3000
```

### Environment variables (all in `chat_api/.env`)

| Variable | Used by | Notes |
|---|---|---|
| `SUPABASE_URL` | data_context, chat_adapter | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | data_context, chat_adapter | Service role key; never commit |
| `ANTHROPIC_API_KEY` | metrics/resolver, chat_adapter/interpreter | Claude API key |
| `API_SECRET_KEY` | chat_adapter (auth check) | x-api-key header value |
| `UPSTREAM_CHAT_URL` | chat_adapter | Defaults to `http://localhost:8001` |
| `LLM_MODEL` | metrics, chat_adapter | Defaults to `claude-sonnet-4-5` |
| `ALLOWED_ORIGINS` | chat_adapter CORS | Comma-separated origins |

---

## 10. Key Design Decisions

| Decision | Alternative considered | Reason chosen |
|---|---|---|
| Proxy (chat_adapter wraps chat_api) | Monkey-patch chat_api in-place | No chat_api edits allowed; proxy enables independent rollback |
| Native tool-use for resolver | JSON-from-text parsing | Enumerating metric names in tool schema makes hallucination structurally impossible |
| Human-reviewed YAML SQL templates | LLM writes SQL for known questions | Certified answers are reproducible, auditable, and don't drift with model updates |
| Relative imports (`from ..data_context`) | Absolute imports | Works when package is imported from any working directory |
| Fire-and-forget session persistence | Awaited persistence | A Supabase write failure must never block the user's response |
| Separate `models.py` in chat_adapter | Import from chat_api/models.py | Keeps chat_adapter self-contained; survives chat_api model changes |
| `message_rating ~ '^[0-9]+$'` guard | Direct cast | The column is TEXT; invalid values cause a runtime cast error without the guard |
| Column check degrades to SQL scan when rows empty | Fail the eval case | A correctly matched metric returning 0 rows (data range gap) is a pass, not a bug |

---

## 11. Extension Points

### Adding a metric
1. Write `ua_api/metrics/definitions/<name>.yaml`
2. Run `python -m ua_api.metrics validate --name <name>` (live DB check)
3. Run `python -m ua_api.metrics resolve "<typical question>"` (classifier check)
4. Add an `EvalCase` in `ua_api/validation/eval_set.py`

### Adding a quality check
1. Add a function in `ua_api/data_context/quality/checks.py`
2. Call it from `run_all_checks()` in `runner.py`
3. Must be read-only, isolated (one failure can't abort the run)

### Adding a catalog table
1. Write `ua_api/data_context/catalog/tables/<name>.yaml`
2. Declare all join relationships; `load_catalog()` validates them at load time
3. Run `python -m ua_api.data_context catalog validate`

### Extending the system prompt
1. Add a new constant to `ua_api/skills/blocks.py`
2. Add it to `_BLOCK_MAP` and the appropriate profiles in `prompt_builder.py`
3. The `SYSTEM_PROMPT` singleton refreshes at import time — no other change needed

### Wiring per-metric feedback
1. Frontend sends `provenance.metric` with thumbs-up/down signals
2. Backend stores metric name alongside rating in `nep_chat_messages`
3. Extend `ua_api/feedback/signals.py` with `GROUP BY metric` aggregation
4. Surface in the health dashboard or as a new `GET /api/metrics/{name}/quality` endpoint
