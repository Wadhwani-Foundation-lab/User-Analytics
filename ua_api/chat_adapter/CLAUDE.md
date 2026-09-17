# CLAUDE.md — chat_adapter module

> Module-scoped instructions for `ua_api/chat_adapter/`. These sit below
> `ua_api/CLAUDE.md` and detail the adapter-specific conventions.

## What this module is

`chat_adapter` is a **drop-in proxy FastAPI app** that adds certified-metric
interception to the existing chat_api without modifying it.

```
Request → chat_adapter (port 8000)
              │
              ├─ certified metric matched? ──yes──▶ format + return directly
              │                                     (no LLM SQL generation)
              │
              └─ no match ──▶ proxy to chat_api (port 8001) unchanged
```

The frontend continues to point at port 8000. The upstream chat_api moves
to port 8001 (internal). No frontend changes needed.

### Module layout

```
chat_adapter/
├── config.py       # env loading, UPSTREAM_CHAT_URL, MODEL
├── models.py       # ChatRequest / ChatResponse mirrors (no chat_api import)
├── formatter.py    # chart + table formatting (replicated, palette-matched)
├── interpreter.py  # interpret_results + explain_empty_results (Anthropic call)
├── interceptor.py  # try_certified_answer() → ChatResponse | None
└── main.py         # FastAPI app (/api/chat + catch-all proxy)
```

## Non-negotiable rules

1. **Never import from `chat_api/`.** All shapes are redeclared in `models.py`;
   chart logic is replicated in `formatter.py`; interpretation is in
   `interpreter.py`. If `chat_api` changes a response shape, update `models.py`
   here too.
2. **`try_certified_answer` must return `None` on any error**, not raise.
   The proxy fallback is the safety net — interceptor failures must never block
   a valid user question.
3. **Session persistence is fire-and-forget.** The `_persist()` call in
   `interceptor.py` is wrapped in try/except. A Supabase write failure must
   never fail the HTTP response.
4. **`matched=False` is the happy path for non-certified questions.** Do not
   treat a no-match as an error or log it at WARNING level.

## Deployment commands

```bash
# Run upstream chat_api on internal port
cd chat_api && uvicorn main:app --reload --port 8001

# Run adapter on public port (in repo root)
uvicorn ua_api.chat_adapter.main:app --reload --port 8000

# Frontend: NEXT_PUBLIC_API_URL=http://localhost:8000 (unchanged)
```

## Environment variables

All read from `chat_api/.env` (loaded automatically):
- `UPSTREAM_CHAT_URL` — where chat_api is running (default: `http://localhost:8001`)
- `API_SECRET_KEY` — forwarded as `x-api-key` to upstream
- `ANTHROPIC_API_KEY` — used by `interpreter.py` for interpretation calls
- `LLM_MODEL` — model for interpretation (default: `claude-sonnet-4-5`)
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` — for direct session persistence

## Adding / changing a metric

Nothing changes here. Metrics are defined in `ua_api/metrics/definitions/*.yaml`.
The interceptor calls `metrics.resolver.answer()` which reads the registry. A new
YAML is live on next server restart (registry is loaded per-request).

## Keeping formatter in sync with chat_api

`formatter.py` replicates the palette and chart-type map from
`chat_api/chart_formatter.py`. If someone updates the palette in `chat_formatter`,
update the `PALETTE` constant in `formatter.py` to match — otherwise certified and
free-form answers will render with different colours in the same session.

## Gotchas

- The catch-all proxy route must be declared **after** `/api/chat` in `main.py`.
  FastAPI routes match in declaration order; declaring catch-all first would
  swallow the chat endpoint.
- `httpx` must be installed: `pip install httpx`. It is not in `chat_api/requirements.txt`.
- The interceptor makes two LLM calls per certified match: one in the resolver
  (metric classification) and one in the interpreter (result narration). This is
  equivalent to chat_api's single text-to-SQL call + interpret call. Both paths
  have the same LLM cost.
