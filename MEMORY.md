# MEMORY.md — Project Decisions & Learnings

> Living document tracking important decisions, gotchas, and learnings accumulated during development.

---

## Known Gotchas

### Database — Column Types (schema docs vs actual DB)
- **`userid` vs `user_id`** — `nep_liftoffx_data_sample` uses `userid` (no underscore). All other tables use `user_id`.
- **`nep_master_user_table_sample_data.created_datetime`** — actual TIMESTAMP in DB. Use `TO_CHAR(created_datetime, 'YYYY-MM-DD')` for range filters. For monthly grouping: `TO_CHAR(created_datetime, 'YYYY-MM')`.
- **`nep_liftoffx_data_sample` has NO `created_datetime` column** — use `signup_date` (VARCHAR) for signup date filters on this table, or join to user table for `u.created_datetime`.
- **`ga_event_date` in activity table** — actual DATE type (not VARCHAR). Compare to date expressions: `a.ga_event_date >= u.created_datetime::DATE`.
- **`nep_master_live_events_data.start_date`** — actual DATE. Use `TO_CHAR(start_date, 'YYYY-MM')` for monthly grouping.
- **All other date-like columns** (`signup_date`, `message_date`) — VARCHAR, string comparison only.
- **`activity_type` has a typo** — `'jounrney_explore'` is the correct value (not `journey_explore`).
- **`activity_type` values** — Never use `'ai_chat'`, `'mentor_session'`, `'live_event'`, or `'resource_view'`. Correct: `'message'`, `'mentor'`, `'session'`, `'resource'`, `'visitors'`, `'repeat visitors'`, `'signup'`, `'jounrney_explore'`, `'introductory_video_reg_users'`.

### Database — Column Locations
- `login_status`, `profile_status`, `company_type`, `company_revenue_range`, `traffic_source_*` → ONLY in user table. NEVER `a.login_status`.
- `signup_date`, `week_range`, `month_year`, `signup_month_year` → ONLY in activity table. NEVER `u.signup_date`.
- `program_key` → ONLY in `nep_master_live_events_data`.
- `program` → ONLY in `nep_mentor_profiles_sample_data` (not `program_key`).

### SQL Patterns
- **No CTEs (in some contexts)** — Supabase `execute_sql` may have CTE limitations. Use subqueries when possible.
- **`ROUND()` requires `::NUMERIC`** — `ROUND(AVG(x)::NUMERIC, 2)` — never ROUND on double precision without cast.
- **`SELECT DISTINCT` + `ORDER BY`** — all ORDER BY columns must appear in SELECT.
- **Window functions** — `COUNT(DISTINCT col) OVER (...)` is NOT valid PostgreSQL. Use subquery with GROUP BY instead.
- **Column ambiguity in JOINs** — always qualify with table alias when multiple tables share a column name.

### API
- **422 errors from malformed JSON** — Raw LLM output sometimes contains invalid escape sequences or control characters. The `llm_client.py` parser must sanitize before `json.loads()`.
- **`LIMIT 500`** — Must be appended to every generated SQL query to prevent runaway result sets.

### Frontend
- **Netlify deploy** — Requires `@netlify/plugin-nextjs` in `netlify.toml` and a `_redirects` fallback for client-side routing. Without this, all non-root routes return 404.

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory + Supabase session storage | In-memory for speed during active chat; Supabase for persistence across restarts. Fire-and-forget writes so DB failures don't block responses. |
| System prompt built at import time | Schema + examples are loaded once from `docs/` and cached as `SYSTEM_PROMPT` singleton. No runtime file I/O per request. |
| Auto table upgrade | Backend auto-promotes `text` responses to `table` when SQL returns multiple columns/rows, so data is never hidden from the user. |
| No CTEs, subqueries only | Supabase RPC `execute_sql` doesn't reliably support CTEs. All complex queries use nested subqueries. |
| LLM always returns JSON | Even conversational follow-ups must be wrapped in the JSON schema. This simplifies response parsing in the backend. |

---

## Resolved Issues

- **Schema `activity_type` mismatch** — System prompt originally used invented values like `'ai_chat'`. Fixed to match actual DB values (`'message'`, etc.). See `docs/schema_reference.md`.
- **Netlify 404 on refresh** — Added `netlify.toml` with Next.js plugin and `_redirects` file.
- **422 JSON parse failures** — LLM responses with control characters in SQL strings caused parsing errors. Added sanitization in `llm_client.py`.
- **Date column confusion** — `nep_master_user_table_sample_data` uses `created_datetime` (not `created_at`). Documented in system prompt rule #9.

---

## Environment Notes

- **Current date context for LLM:** Update the "today" date in `system_prompt.py` (line ~101) when deploying to keep relative date references accurate.
- **Supabase project:** `mybdvsxiynpdbuzmtquu.supabase.co`
- **LLM model:** `claude-sonnet-4-5` (referenced in health endpoint and LLM client)

---

## Future Considerations

- [ ] Move from VARCHAR dates to proper `TIMESTAMP` columns (requires data migration)
- [ ] Fix `jounrney_explore` typo at the database level
- [ ] Add rate limiting to the chat endpoint
- [ ] Add automated tests for SQL generation accuracy
- [ ] Consider streaming LLM responses for better UX
