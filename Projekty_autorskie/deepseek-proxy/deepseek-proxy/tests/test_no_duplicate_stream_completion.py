"""Regression tests for the duplicate-message / retry-cascade bug fix.

Bugs covered:
1. `_primed_gen` closure captured the rebound `gen` variable -> on the 2nd
   chunk it raised `ValueError: generator already executing`, breaking the
   SSE stream after the first chunk and making the client retry (duplicates).
2. The retry loop had no `break` on the success path -> every request
   re-ran `ds.stream_completion(...)` MAX_ACCOUNTS (3) times, re-sending the
   same user message and creating duplicate streams/responses.
3. `no_data` / EMPTY RESUME handling was dead code after `raise HTTPException`.
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

from starlette.requests import Request

from server.services.proxy_service import ProxyService


def _make_request(body: dict) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [],
        "query_string": b"",
        "asgi": {"version": "3.0"},
        "scheme": "http",
        "server": ("test", 80),
        "client": ("127.0.0.1", 12345),
        "root_path": "",
    }
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(scope, receive)


def _get_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _run(coro):
    return _get_loop().run_until_complete(coro)


def _sse_text(resp):
    """Consume a StreamingResponse and extract joined SSE content text."""
    loop = _get_loop()
    parts = []
    while True:
        try:
            chunk = loop.run_until_complete(resp.body_iterator.__anext__())
        except StopAsyncIteration:
            break
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", "ignore")
        parts.append(chunk)
    text = "".join(parts)
    text_parts = []
    for line in text.splitlines():
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            try:
                data = json.loads(line[6:].strip())
            except json.JSONDecodeError:
                continue
            delta = data.get("choices", [{}])[0].get("delta", {})
            if delta.get("content"):
                text_parts.append(delta["content"])
    return "".join(text_parts)


def _patch_common():
    import contextlib
    stack = contextlib.ExitStack()
    stack.enter_context(patch("server.services.proxy_service.get_conv", return_value=None))
    stack.enter_context(patch("server.services.proxy_service.set_conv"))
    stack.enter_context(patch("server.services.proxy_service.rate_limiter"))
    stack.enter_context(patch("server.services.proxy_service._dashboard"))
    stack.enter_context(patch("server.services.proxy_service.conv_lock", new=MagicMock()))
    stack.enter_context(patch("server.services.proxy_service.account_selector.select_account", return_value=0))
    return stack


class TestStreamCompletionsSingleCall:
    """Bug 2: success path must break the retry loop."""

    def test_stream_completion_called_once(self):
        proxy = ProxyService()

        def fake_stream_completion(*a, **k):
            def gen():
                yield "Hello "
                yield "world"
            return gen(), {"resp_msg_id": "101"}

        with _patch_common(), \
             patch("server.services.proxy_service.ds") as mock_ds, \
             patch("server.services.proxy_service.session_manager") as mock_sm:
            mock_sm.acquire_slot.return_value = True
            mock_ds.create_session.return_value = "chat-1234"
            mock_ds.stream_completion = MagicMock(wraps=fake_stream_completion)

            body = {
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "deepseek-chat",
                "stream": True,
            }
            resp = _run(proxy.chat_completions(_make_request(body)))

        text = _sse_text(resp)
        assert "Hello" in text, f"expected stream content, got: {text!r}"
        assert "world" in text
        assert mock_ds.stream_completion.call_count == 1, (
            f"stream_completion called {mock_ds.stream_completion.call_count} times — "
            "retry loop must break after first success (duplicate-message bug)"
        )

    def test_non_stream_json_response(self):
        """Non-stream mode: JSON body, stream_completion still called once."""
        proxy = ProxyService()

        def fake_stream_completion(*a, **k):
            def gen():
                yield "Just one chunk"
            return gen(), {"meta_2": True}

        with _patch_common(), \
             patch("server.services.proxy_service.ds") as mock_ds, \
             patch("server.services.proxy_service.session_manager") as mock_sm:
            mock_sm.acquire_slot.return_value = True
            mock_ds.create_session.return_value = "chat-5678"
            mock_ds.stream_completion = MagicMock(wraps=fake_stream_completion)

            body = {
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "deepseek-chat",
                "stream": False,
            }
            resp = _run(proxy.chat_completions(_make_request(body)))

        assert mock_ds.stream_completion.call_count == 1
        assert resp.status_code == 200
        payload = json.loads(resp.body)
        assert payload["choices"][0]["message"]["content"] == "Just one chunk"


def _two_chunk_gen():
    yield "Hello "
    yield "world"