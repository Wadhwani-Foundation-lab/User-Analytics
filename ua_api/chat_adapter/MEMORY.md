# MEMORY.md — chat_adapter module

> Durable record of why this module is shaped the way it is.

## Why the module exists

The metrics and data_context modules were built and verified in isolation, but
users couldn't benefit from certified metrics until the question-routing logic
was wired into the chat flow. `chat_adapter` is that wire — it adds the certified
path without touching `chat_api/`, which was the user's explicit requirement.

## Key design decisions

- **Proxy, not a monkey-patch.** The adapter is a standalone FastAPI app that
  sits in front of chat_api. chat_api runs unchanged on an internal port.
  Alternative considered: editing `chat_api/main.py` to call `try_certified_answer`.
  Rejected: user explicitly requires no chat_api edits.

- **`try_certified_answer` returns `None`, not raises.** Any failure in the
  certified path (resolver error, bad params, Anthropic timeout) must silently
  fall through to the upstream chat_api. The user gets an answer either way;
  only the path changes.

- **Session persistence via direct Supabase write.** When the adapter intercepts
  a request, the exchange never reaches chat_api, so chat_api's in-memory session
  store (`session_store.py`) and its Supabase writer (`chat_history_store.py`)
  are not invoked. The adapter writes directly to `nep_chat_messages` using
  `data_context.config.get_client()`. This keeps session history consistent
  for the frontend's history view. The in-memory store in chat_api will be
  inconsistent for intercepted turns — multi-turn context for certified questions
  is a known Phase 1 limitation.

- **Interpretation call for certified metrics.** chart_api calls
  `interpret_results()` for table and chart responses. The adapter replicates
  this in `interpreter.py` (same Anthropic call, same prompt) so certified
  answers have the same prose quality as free-form answers. This is intentional:
  the user should not be able to tell whether a response came from the certified
  path or the text-to-SQL path.

- **Palette replicated, not imported.** `formatter.py` replicates the colour
  palette from `chat_api/chart_formatter.py`. Chart colours must be consistent
  across both paths. If the palette drifts, charts will look different within the
  same session depending on which path answered. This is a maintenance burden,
  but importing from chat_api is ruled out.

## Known limitations (Phase 1)

- **Multi-turn context for certified questions.** When the adapter intercepts,
  chat_api's in-memory history is not updated. A follow-up question ("show me
  the same for the previous month") won't have the previous certified answer as
  context if it falls through to chat_api. Phase 2 mitigation: pass the adapter's
  answered turns in `req.history` so chat_api has the full context.

- **Session in-memory store divergence.** chat_api's `session_store.py` is
  process-local. Running two processes (adapter + chat_api) means the in-memory
  history is split. Supabase persistence is consistent (both write to
  `nep_chat_messages`), but `req.history` from the frontend is the reliable
  context source for cross-process turns.

## Current state (as of 2026-06-10)

Built. Not yet smoke-tested against live DB. Pending:
- `pip install httpx` in the adapter's environment
- Start chat_api on 8001, adapter on 8000, send a test question

## Next after smoke-test

1. Update `ua_api/MEMORY.md` — mark chat_adapter as built.
2. Begin expanding metric definitions from 8 to ~20.
