"""FastAPI route definitions for the DeepSeek proxy server.

Defines HTTP endpoints using dependency injection for service access.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from server.services.proxy_service import ProxyService
from server.api.deps import get_proxy_service

router = APIRouter()

# Simple in-memory rate limiter for login endpoint
_login_last_call: dict[int, float] = {}
_LOGIN_COOLDOWN = 60.0  # seconds between login attempts per slot


@router.post("/v1/chat/completions")
async def chat_completions(
    raw_request: Request,
    proxy: ProxyService = Depends(get_proxy_service),
) -> Any:
    """Proxy chat completions to DeepSeek web chat.

    Full implementation is in ProxyService — uses injected services
    for prompt building, state management, and streaming.
    """
    return await proxy.chat_completions(raw_request)


@router.post("/v1/chat/completions/dry-run")
async def dry_run(
    raw_request: Request,
    proxy: ProxyService = Depends(get_proxy_service),
) -> Any:
    """Dry-run: process and log the request without calling DeepSeek.

    Logs raw IDE payload + what the server would actually send to dry_run_logs.ndjson.
    Returns both views as JSON for instant inline inspection.
    No jitter, no account usage, completely non-destructive.
    """
    return await proxy.dry_run(raw_request)


@router.get("/v1/models")
async def list_models(
    proxy: ProxyService = Depends(get_proxy_service),
) -> dict:
    """Return available models (OpenAI-compatible)."""
    return await proxy.list_models()


@router.post("/v1/login")
async def login(
    slot: int = 0,
    proxy: ProxyService = Depends(get_proxy_service),
) -> dict:
    """Trigger Chrome-based login for a specific account slot.

    Rate-limited to prevent resource abuse (Chrome spawns are expensive).
    """
    now = time.time()
    last = _login_last_call.get(slot, 0)
    if now - last < _LOGIN_COOLDOWN:
        remaining = int(_LOGIN_COOLDOWN - (now - last))
        raise HTTPException(
            status_code=429,
            detail=f"Login rate limit: wait {remaining}s before retrying slot {slot}",
            headers={"Retry-After": str(remaining)},
        )
    _login_last_call[slot] = now
    return await proxy.login(slot)


@router.get("/v1/accounts")
async def list_accounts(
    proxy: ProxyService = Depends(get_proxy_service),
) -> dict:
    """Return status of all account slots."""
    return await proxy.list_accounts()


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
