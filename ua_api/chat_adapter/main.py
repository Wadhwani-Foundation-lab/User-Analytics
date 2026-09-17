"""
chat_adapter FastAPI application.

Drop-in proxy that sits in front of chat_api and intercepts /api/chat
for certified-metric questions. All other paths are forwarded unchanged.

Deployment:
  # 1. Move chat_api to internal port
  cd chat_api && uvicorn main:app --port 8001

  # 2. Start adapter on the public port
  cd <repo-root> && uvicorn ua_api.chat_adapter.main:app --port 8000

  Frontend NEXT_PUBLIC_API_URL stays pointed at 8000 — no frontend change needed.

Standalone (no upstream, certified metrics only):
  uvicorn ua_api.chat_adapter.main:app --port 8000
  Then /api/chat returns 503 for non-certified questions (useful in dev).
"""
from __future__ import annotations

import logging
import os
from datetime import date

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import API_SECRET_KEY, UPSTREAM_CHAT_URL
from .interceptor import try_certified_answer
from .models import ChatRequest, ChatResponse
from ..sql_guard import lint_with_message

log = logging.getLogger(__name__)

MAX_REPAIR_RETRIES = 2

app = FastAPI(
    title="NEP Analytics Chat — certified-metrics adapter",
    description=(
        "Proxy layer that intercepts /api/chat for certified metric questions "
        "and forwards everything else to the upstream chat_api."
    ),
    version="0.1.0",
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Auth (mirrors chat_api) ───────────────────────────────────────────────────

def _check_api_key(x_api_key: str) -> None:
    if API_SECRET_KEY and x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ── /api/chat — intercept first, proxy on miss ────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_api_key: str = Header(default=""),
) -> ChatResponse:
    """
    Enhanced chat endpoint.

    1. Tries the certified-metrics path (resolver → render → execute).
    2. On match: returns the formatted response directly (no LLM SQL generation).
    3. On miss: proxies the request to the upstream chat_api unchanged.
    """
    _check_api_key(x_api_key)

    today = date.today().isoformat()

    # ── Attempt certified-metric intercept ────────────────────────────────────
    history = [{"role": t.role, "content": t.content} for t in (req.history or [])]
    certified = try_certified_answer(req.question, req.session_id, today=today, history=history)
    if certified is not None:
        log.info("chat_adapter: serving certified response for session %s", req.session_id)
        return certified

    # ── Fall back: proxy to upstream chat_api ─────────────────────────────────
    return await _proxy_chat(req, x_api_key)


async def _proxy_chat(req: ChatRequest, x_api_key: str) -> ChatResponse:
    headers = {"Content-Type": "application/json"}
    if x_api_key:
        headers["x-api-key"] = x_api_key

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{UPSTREAM_CHAT_URL}/api/chat",
                json=req.model_dump(),
                headers=headers,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        response = ChatResponse(**resp.json())
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Upstream chat_api is not reachable at {UPSTREAM_CHAT_URL}. "
                "Start it with: cd chat_api && uvicorn main:app --port 8001"
            ),
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream chat_api timed out.")

    return await _lint_and_repair(response, req, headers)


async def _lint_and_repair(
    response: ChatResponse,
    original_req: ChatRequest,
    headers: dict,
) -> ChatResponse:
    """
    Lint the SQL in an upstream response. If violations are found, send up to
    MAX_REPAIR_RETRIES follow-up requests to the upstream using an ephemeral
    session so the real session history is never polluted.

    Always returns a valid ChatResponse — never raises. On any repair error,
    falls back to the original (potentially unrepaired) response.
    """
    for attempt in range(MAX_REPAIR_RETRIES):
        sql = response.sql_used
        if not sql:
            break

        repair_msg = lint_with_message(sql)
        if repair_msg is None:
            break  # SQL is clean

        log.info(
            "chat_adapter: SQL lint violations (attempt %d) for session %s — repairing",
            attempt + 1,
            original_req.session_id,
        )

        repair_req = ChatRequest(
            session_id=f"{original_req.session_id}_sqlrepair",
            question=f"Original question: {original_req.question}\n\n{repair_msg}",
            history=[],
        )
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{UPSTREAM_CHAT_URL}/api/chat",
                    json=repair_req.model_dump(),
                    headers=headers,
                )
            if resp.status_code != 200:
                log.warning(
                    "chat_adapter: repair attempt %d HTTP %d — returning best response so far",
                    attempt + 1,
                    resp.status_code,
                )
                break
            repaired = ChatResponse(**resp.json())
            repaired.session_id = original_req.session_id  # restore real session id
            response = repaired
        except Exception as exc:
            log.warning(
                "chat_adapter: repair attempt %d raised %s — returning best response so far",
                attempt + 1,
                exc,
            )
            break

    return response


# ── Catch-all proxy — forward everything else to upstream ─────────────────────

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "DELETE", "OPTIONS", "PUT", "PATCH"],
)
async def proxy_all(path: str, request: Request) -> Response:
    """Forward any request not handled above to the upstream chat_api."""
    body = await request.body()
    headers = dict(request.headers)
    # Remove hop-by-hop headers that httpx / uvicorn will re-add
    for h in ("host", "content-length", "transfer-encoding"):
        headers.pop(h, None)

    target = f"{UPSTREAM_CHAT_URL}/{path}"
    params = str(request.url.query)
    if params:
        target = f"{target}?{params}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            upstream = await client.request(
                method=request.method,
                url=target,
                headers=headers,
                content=body,
            )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    f"Upstream chat_api is not reachable at {UPSTREAM_CHAT_URL}. "
                    "Start it with: cd chat_api && uvicorn main:app --port 8001"
                )
            },
        )
