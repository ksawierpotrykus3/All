"""Utility functions — no I/O, no service dependencies."""

import json
from typing import Any

from server.logging import get_logger

logger = get_logger(__name__)


def _ensure_valid_json(s: str) -> str:
    if not isinstance(s, str):
        return json.dumps(s)
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return s
        return json.dumps({"value": parsed})
    except Exception:
        return json.dumps({"raw_value": s})


def _chunk(completion_id: str, created: int, model: str, delta: dict, fr: str | None = None, sid: str | None = None) -> str:
    c = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta}],
    }
    if fr:
        c["choices"][0]["finish_reason"] = fr
    if sid:
        c["sid"] = sid
    if delta.get("content") or delta.get("tool_calls") or delta.get("role") or fr or sid:
        return f"data: {json.dumps(c, ensure_ascii=False)}\n\n"
    return ""

