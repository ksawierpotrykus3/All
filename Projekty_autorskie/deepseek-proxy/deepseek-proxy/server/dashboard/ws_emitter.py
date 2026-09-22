"""WebSocket + SSE server endpoint — dashboard server connects here to receive events."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from server.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# Shared event queue
_event_queue: asyncio.Queue[dict] = asyncio.Queue()


@router.websocket("/events")
async def dashboard_events(websocket: WebSocket) -> None:
    """WebSocket endpoint — dashboard server connects here for live events."""
    await websocket.accept()
    logger.info("Dashboard server connected to event stream (WS)")
    try:
        while True:
            event = await _event_queue.get()
            try:
                await websocket.send_json(event)
            except Exception:
                logger.warning("Failed to send event to dashboard — reconnecting needed")
                break
    except WebSocketDisconnect:
        logger.info("Dashboard server disconnected from event stream (WS)")
    finally:
        pass


@router.get("/events")
async def dashboard_events_sse():
    """SSE endpoint — dashboard server connects via HTTP GET for live events."""
    async def event_generator():
        while True:
            event = await _event_queue.get()
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")


def emit_event(event: dict[str, Any]) -> None:
    """Thread-safe event emission (called from instrumentor)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(_event_queue.put_nowait, event)
    except RuntimeError:
        pass
