import asyncio
import time
from unittest.mock import patch, MagicMock
import pytest
from server.core.deepseek_client import DeepSeek, DeepSeekRateLimitError
from server.services.proxy_service import _stream_gen, ProxyService


def test_throttle_guard_skips_blocking_sleep_in_async_loop():
    """Verify that _throttle detects running asyncio loop and prevents long time.sleep freezes."""
    client = DeepSeek.__new__(DeepSeek)
    client._throttle_lock = MagicMock()
    client._throttle_lock.__enter__ = MagicMock(return_value=None)
    client._throttle_lock.__exit__ = MagicMock(return_value=None)
    client._MIN_BASE_DELAY = 15.0
    client._MAX_JITTER = 0.0
    client._last_request_time = {0: time.time()}  # Just requested

    async def run_in_loop():
        # Call _throttle inside active event loop
        t_start = time.time()
        client._throttle(0)
        t_elapsed = time.time() - t_start
        # Must not have slept for 15s
        assert t_elapsed < 0.5, f"Expected <0.5s but took {t_elapsed}s (event loop was blocked!)"

    asyncio.run(run_in_loop())


def test_stream_gen_seamless_retry_on_rate_limit_no_429():
    """Verify that _stream_gen emits keep-alive and seamlessly retries without raising HTTP 429."""
    # First stream throws "Messages too frequent"
    def failing_stream():
        raise RuntimeError("DeepSeek error: Messages too frequent. Try again later.")
        yield  # Make it a generator

    # Mock stream to succeed on retry
    def success_stream():
        yield 'data: {"choices": [{"delta": {"content": "Hello after retry"}, "finish_reason": null}]}\n\n'
        yield 'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'

    mock_ds = MagicMock()
    mock_ds.stream_continue.return_value = (success_stream(), {"resp_msg_id": 123})
    mock_ds.stream_completion.return_value = (success_stream(), {"resp_msg_id": 123})

    mock_ap = MagicMock()
    mock_ap.is_valid.side_effect = lambda slot: slot == 0  # Only slot 0 is valid, no alt account

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.ap", mock_ap), \
         patch("server.services.proxy_service.time.sleep", return_value=None):  # Fast forward sleep in proxy_service
        gen = _stream_gen(
            stream_gen=failing_stream(),
            stream_meta={"resp_msg_id": 100},
            messages=[{"role": "user", "content": "hello"}],
            parent_id="msg_0",
            chat_id="chat_123",
            conv_uuid="conv_abc",
            account_idx=0,
            tools=[],
            model="deepseek-chat",
            t0=time.time(),
            t4=time.time(),
            prompt="hello",
        )

        chunks = list(gen)
        # Should contain keep-alive pings and content from retried stream, without throwing DeepSeekRateLimitError
        assert any(": keep-alive" in c for c in chunks), f"Expected keep-alive in chunks: {chunks}"
        # Should contain the successful response
        content_chunks = [c for c in chunks if "Hello after retry" in c]
        assert len(content_chunks) > 0, f"Expected content chunks in: {chunks}"


def test_chat_completions_calls_async_throttle_with_is_resume():
    """Verify ProxyService.chat_completions correctly passes parsed.is_resume to ds.async_throttle."""
    from unittest.mock import AsyncMock
    from starlette.requests import Request
    import json

    proxy = ProxyService()

    def fake_stream():
        yield 'data: {"choices": [{"delta": {"content": "ok"}}]}\n\n'

    mock_ds = MagicMock()
    mock_ds.async_throttle = AsyncMock()
    mock_ds.stream_completion.return_value = (fake_stream(), {"resp_msg_id": "999"})

    mock_state = {
        "chat_id": "chat-resume-123",
        "parent_id": "parent-456",
        "account": 0,
        "ts": time.time(),
    }

    body = {
        "messages": [
            {"role": "user", "content": "Initial query"},
            {"role": "assistant", "content": "Answer"},
            {"role": "tool", "content": "Result"},
            {"role": "user", "content": "Next step"},
        ],
        "model": "deepseek-chat",
        "stream": True,
    }
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

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
    req = Request(scope, receive)

    with patch("server.services.proxy_service.get_conv", return_value=mock_state), \
         patch("server.services.proxy_service.set_conv"), \
         patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.account_selector.select_account", return_value=0), \
         patch("server.services.proxy_service._dashboard"):
        
        resp = asyncio.run(proxy.chat_completions(req))
        assert resp is not None
        # Verify async_throttle was awaited with is_resume=True
        mock_ds.async_throttle.assert_called_once()
        _, kwargs = mock_ds.async_throttle.call_args
        assert kwargs.get("is_resume") is True, f"Expected is_resume=True, got {kwargs}"

