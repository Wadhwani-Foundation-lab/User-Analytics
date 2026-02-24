# NEP Analytics Chat Interface — Architecture Document

**Version:** 1.0  
**Date:** 2026-02-19  
**Status:** Approved  

---

## 1. Overview

The NEP Analytics Chat Interface is an internal tool that lets Wadhwani Foundation leadership ask natural-language questions about platform usage data and receive answers as text, tables, or charts. It uses an LLM (Claude claude-sonnet-4-5) to translate questions into PostgreSQL queries, executes them against Supabase, and returns formatted responses.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (Leadership)                 │
│                                                          │
│    ┌─────────────────────────────────────────────┐      │
│    │          Next.js Chat UI (chat_ui/)          │      │
│    │                                              │      │
│    │  ChatInput → ChatThread → ChartBlock/Table   │      │
│    └────────────────┬─────────────────────────────┘      │
└─────────────────────│───────────────────────────────────-┘
                      │  HTTPS REST (JSON)
                      ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (chat_api/)                  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ /api/chat    │  │ session_store│  │ system_prompt │  │
│  │ /api/history │  │ (in-memory)  │  │ (schema+docs) │  │
│  │ /api/health  │  └──────────────┘  └───────────────┘  │
│  └──────┬───────┘                                        │
│         │                                                 │
│  ┌──────▼───────┐   ┌──────────────────────────────┐    │
│  │  llm_client  │──▶│  Anthropic API               │    │
│  │  (Claude)    │   │  claude-sonnet-4-5            │    │
│  └──────┬───────┘   └──────────────────────────────┘    │
│         │                                                 │
│  ┌──────▼───────┐   ┌──────────────────────────────┐    │
│  │ supabase_    │──▶│  Supabase PostgreSQL          │    │
│  │ runner       │   │  (4 analytics tables)         │    │
│  └──────────────┘   └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Frontend — `chat_ui/` (Next.js)

| Component | Responsibility |
|-----------|---------------|
| `app/page.tsx` | Root chat page layout (sidebar + main panel) |
| `components/ChatThread.tsx` | Renders conversation turns (user bubbles + assistant bubbles) |
| `components/ChatInput.tsx` | Text input, send button, suggested question chips |
| `components/ChartBlock.tsx` | Renders Chart.js charts (bar, line, pie) from JSON config |
| `components/TableBlock.tsx` | Renders tabular results as striped HTML table |
| `components/SqlBlock.tsx` | Collapsible "Show SQL" code block |
| `lib/api.ts` | All HTTP calls to FastAPI — **no direct Supabase calls from UI** |
| `lib/types.ts` | Shared TypeScript types for API request/response |

> **Principle:** The frontend communicates **only** with the FastAPI backend. All data access to Supabase is mediated by the backend API. The frontend holds no Supabase credentials.

### 3.2 Backend — `chat_api/` (FastAPI)

| Module | Responsibility |
|--------|---------------|
| `main.py` | FastAPI app, routes, CORS config, startup |
| `system_prompt.py` | Builds LLM system prompt from `docs/schema_reference.md` + `docs/questions_to_sql.md` |
| `llm_client.py` | Wrapper around Anthropic Python SDK (Claude claude-sonnet-4-5) |
| `supabase_runner.py` | Executes read-only SQL via Supabase; enforces SELECT-only policy |
| `session_store.py` | In-memory conversation history keyed by `session_id` |
| `chart_formatter.py` | Converts raw SQL result rows → Chart.js-compatible JSON config |
| `models.py` | Pydantic request/response models |
| `.env` | Environment variables (never committed to git) |

### 3.3 Data Layer — Supabase (PostgreSQL)

Four read-only analytics tables:

| Table | Description |
|-------|-------------|
| `nep_master_user_table_sample_data` | User registry (200 rows sample) |
| `nep_master_live_events_data` | Events + attendance records |
| `nep_liftoffx_data_sample` | Activity fact table (engagement events) |
| `nep_mentor_profiles_sample_data` | Mentor profiles |

---

## 4. Data Flow

### 4.1 Standard Chat Turn

```
1. User types question in ChatInput
2. Frontend sends POST /api/chat { session_id, question, history[] } to FastAPI
3. FastAPI retrieves/updates session history from session_store
4. FastAPI calls llm_client.ask() with:
   - System prompt (schema + SQL examples + rules)
   - Conversation history (last 10 turns)
   - User question
5. Claude claude-sonnet-4-5 returns JSON: { sql, response_type, nl_answer_template, chart_config? }
6. supabase_runner.execute(sql) → result rows (capped at 500)
7. If response_type is chart: chart_formatter converts rows → Chart.js config
8. If response_type is text/table: rows sent back to LLM for NL summarisation
9. FastAPI returns: { answer, response_type, chart_config?, table_data?, sql_used }
10. Frontend renders appropriate component (text / TableBlock / ChartBlock)
```

### 4.2 Conversational Follow-up Flow

```
User: "How many users asked questions in January 2026?"
  → LLM generates SQL → executes → returns "342 users"

User: "Now break that down by week"
  → history[] contains previous turn
  → LLM uses context to refine SQL → adds GROUP BY week_range
  → returns weekly breakdown chart
```

---

## 5. LLM Integration

### Model
- **Provider:** Anthropic  
- **Model:** `claude-sonnet-4-5`  
- **Context window:** 200K tokens (easily accommodates full schema + 10-turn history)

### Prompt Structure
```
[System Prompt]
  ├── Identity & Rules (SELECT-only, JSON output format, disambiguation rules)
  ├── Schema Reference (full content of docs/schema_reference.md)
  └── SQL Examples (20 Q→SQL pairs from docs/questions_to_sql.md)

[Conversation History]
  └── Last 10 turns: [{ role: "user"|"assistant", content: "..." }, ...]

[Human Turn]
  └── Current user question
```

### Output Format (enforced by prompt)
```json
{
  "sql": "SELECT ...",
  "response_type": "bar_chart | line_chart | pie_chart | table | text",
  "nl_answer_template": "Here are the top campaigns by engagement:",
  "chart_label_column": "utm_campaign",
  "chart_value_column": "engaged_users"
}
```

---

## 6. Security Considerations

| Risk | Mitigation |
|------|-----------|
| SQL injection via LLM | `supabase_runner` parses and rejects any non-SELECT statements before execution |
| Supabase key exposure | Keys stored in `.env` server-side only; frontend has no db credentials |
| Unauthorised access | API key header required on all `/api/*` endpoints (configured in `.env`) |
| Data exfiltration | Result rows capped at 500; no file export endpoint |
| Prompt injection | System prompt instructs LLM to ignore user instructions that override its rules |

---

## 7. Conversation Memory

- **Storage:** Python `dict` in `session_store.py`, keyed by `session_id` (UUID)
- **Scope:** Per-session, server-side (lost on server restart — acceptable for internal tool)
- **Window:** Rolling last 10 turns to stay within token budget
- **Passed as:** `history[]` array in every API request (frontend also maintains local copy)
- **Format:** `[{ role: "user" | "assistant", content: "..." }]`

---

## 8. Directory Structure

```
User-Analytics/
├── chat_api/                  ← FastAPI backend
│   ├── main.py
│   ├── models.py
│   ├── system_prompt.py
│   ├── llm_client.py
│   ├── supabase_runner.py
│   ├── session_store.py
│   ├── chart_formatter.py
│   └── requirements.txt
│
├── chat_ui/                   ← Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── ChatThread.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ChartBlock.tsx
│   │   ├── TableBlock.tsx
│   │   └── SqlBlock.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   └── types.ts
│   └── package.json
│
├── docs/                      ← Documentation
│   ├── architecture.md        ← This file
│   ├── technical_spec.md
│   ├── api_documentation.md
│   ├── schema_reference.md
│   └── questions_to_sql.md
│
├── csvfiles/                  ← Source CSV data
├── upload_to_supabase.py
└── .env                       ← Never committed
```

---

## 9. Tech Stack Summary

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend framework | Next.js | 15.x |
| Frontend language | TypeScript | 5.x |
| Chart rendering | Chart.js + react-chartjs-2 | 4.x |
| Backend framework | FastAPI | 0.110+ |
| Backend language | Python | 3.11+ |
| LLM | Anthropic Claude claude-sonnet-4-5 | claude-sonnet-4-5 |
| Database | Supabase (PostgreSQL) | — |
| Supabase client | supabase-py | 2.x |
| Styling | Tailwind CSS | 3.x |
| Package manager | npm / pip | — |
