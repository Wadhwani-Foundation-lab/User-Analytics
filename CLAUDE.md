# CLAUDE.md — NEP User Analytics

## Project Overview

**NEP Analytics Chat** is an internal AI-powered analytics tool for the Wadhwani Foundation. Users ask natural-language questions about platform engagement, and the system translates them into SQL, executes against Supabase, and returns text, tables, or charts.

**Repository:** `Wadhwani-Foundation-lab/User-Analytics`

---

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌───────────┐
│  chat_ui/    │──────▶│   chat_api/      │──────▶│  Supabase │
│  (Next.js)   │ REST  │   (FastAPI)      │  SQL  │  Postgres │
│  Port 3000   │◀──────│   Port 8000      │◀──────│           │
└──────────────┘       │   + Claude LLM   │       └───────────┘
                       └──────────────────┘
```

### Frontend — `chat_ui/`
- **Framework:** Next.js 16 + React 19, TypeScript, Tailwind CSS v4
- **Entry point:** `app/page.tsx` (single-page chat interface)
- **Components:** `ChartBlock`, `ChatInput`, `ChatThread`, `SqlBlock`, `TableBlock`
- **Types:** `lib/types.ts` — `ChatResponse`, `ChatMessage`, `Session`, etc.
- **Charting:** Chart.js + react-chartjs-2 + chartjs-plugin-datalabels
- **Deploy:** Netlify (`netlify.toml` with `@netlify/plugin-nextjs`)

### Backend — `chat_api/`
- **Framework:** FastAPI + Uvicorn
- **LLM:** Anthropic Claude (claude-sonnet-4-5) via `llm_client.py`
- **Database:** Supabase PostgreSQL via `supabase_runner.py` (RPC `execute_sql`)
- **System prompt:** Built dynamically from `docs/schema_reference.md` + `docs/questions_to_sql.md`
- **Session management:** In-memory (`session_store.py`) + Supabase-persisted (`chat_history_store.py`)
- **Models:** `models.py` (Pydantic v2)
- **Chart formatting:** `chart_formatter.py`

---

## Database Schema (4 tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `nep_master_user_table_sample_data` | User profiles | `user_id` (PK), `created_datetime`, `user_type`, `user_email` |
| `nep_liftoffx_data_sample` | User activity/engagement | `userid` (FK, no underscore!), `activity_type`, `message_query` |
| `nep_master_live_events_data` | Live events & attendance | `participant_user_id` (FK), `event_id`, `start_date` |
| `nep_mentor_profiles_sample_data` | Mentor profiles | `user_id` (FK), `first_name`, `mentor_type` |

### Critical `activity_type` values (exact strings)
`message`, `mentor`, `session`, `resource`, `visitors`, `repeat visitors`, `signup`, `jounrney_explore` (typo is intentional), `introductory_video_reg_users`

### Date handling
- **All dates are VARCHAR**, not real date/timestamp types
- Never use `NOW()`, `CURRENT_DATE`, or `::timestamp` casts
- Compare using string literals: `created_datetime >= '2026-02-01' AND created_datetime < '2026-03-01'`
- Exception: `nep_master_live_events_data.start_date` supports `TO_CHAR(start_date, 'YYYY-MM')`

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Health check (DB connectivity + LLM model) |
| `POST` | `/api/chat` | Main chat — accepts question, returns AI answer |
| `GET` | `/api/history/{session_id}` | Get conversation history |
| `DELETE` | `/api/history/{session_id}` | Clear session history |
| `POST` | `/api/sessions` | Create a named chat session |
| `GET` | `/api/sessions` | List recent sessions |
| `GET` | `/api/sessions/{session_id}/messages` | Get all messages for a session |

All endpoints require `x-api-key` header when `API_SECRET_KEY` is configured.

---

## Development

### Prerequisites
- Python 3.10+
- Node.js 18+
- Supabase project with the 4 tables + `execute_sql` RPC function

### Backend
```bash
cd chat_api
cp .env.example .env        # Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd chat_ui
cp .env.local.example .env.local   # Set NEXT_PUBLIC_API_URL
npm install
npm run dev                         # → http://localhost:3000
```

### Environment Variables
**Backend (`chat_api/.env`):**
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_KEY` — Service role key (never commit)
- `ANTHROPIC_API_KEY` — Claude API key
- `API_SECRET_KEY` — x-api-key header value
- `ALLOWED_ORIGINS` — Comma-separated CORS origins
- `MAX_HISTORY_TURNS` — Conversation context window (default 10)
- `MAX_RESULT_ROWS` — SQL result row cap (default 500)

**Frontend (`chat_ui/.env.local`):**
- `NEXT_PUBLIC_API_URL` — Backend API base URL

---

## Key Documentation

- `docs/schema_reference.md` — Full database schema details (loaded into system prompt)
- `docs/questions_to_sql.md` — Few-shot SQL examples (loaded into system prompt)
- `docs/architecture.md` — System architecture document
- `docs/technical_spec.md` — Technical specification
- `docs/api_documentation.md` — API reference

---

## Branching

| Branch | Purpose |
|--------|---------|
| `main` | Production |
| `user-analytics-testing` | Testing/QA |
| `user-analytics-dev` | Active development |
| `Applogs-add` | Application logging feature |

---

## Important Conventions

1. **No CTEs** — Use subqueries instead of `WITH ... AS` (Supabase RPC limitation)
2. **JOIN keys differ** — `user_id` in users table, `userid` (no underscore) in activity table
3. **LIMIT 500** — Always applied to SQL queries
4. **LLM responses are always JSON** — Even clarification/follow-up answers wrap in JSON
5. **Auto table upgrade** — Backend auto-upgrades `text` responses to `table` when results have multiple columns/rows
6. **System prompt is dynamic** — Built at import time from docs, cached as `SYSTEM_PROMPT` singleton
