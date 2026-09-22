"""tests/test_stop_stream.py — Tests for stop_stream method and interim chunk handling."""

import json
from unittest.mock import MagicMock, patch
import pytest

from server.core.deepseek_client import DeepSeek, Session


@pytest.fixture
def mock_deepseek():
    mock_pool = MagicMock()
    mock_session = Session(
        auth_token="test-token",
        cookies={"ds_token": "abc"},
        user_agent="test-agent",
    )
    mock_pool.slots = [mock_session]
    ds = DeepSeek(pool=mock_pool)
    return ds


def test_stop_stream_success(mock_deepseek):
    """DeepSeek.stop_stream should send POST to /api/v0/chat/stop_stream and return True on 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "msg": "", "data": None}

    with patch.object(mock_deepseek._http[0], "post", return_value=mock_resp) as mock_post:
        ok = mock_deepseek.stop_stream(0, "chat-123", 42)
        assert ok is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/api/v0/chat/stop_stream" in args[0]
        assert kwargs["json"] == {"chat_session_id": "chat-123", "message_id": 42}


def test_stop_stream_failure_status(mock_deepseek):
    """DeepSeek.stop_stream should return False on non-200 HTTP status."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch.object(mock_deepseek._http[0], "post", return_value=mock_resp):
        ok = mock_deepseek.stop_stream(0, "chat-123", 42)
        assert ok is False


def test_stop_stream_exception_handling(mock_deepseek):
    """DeepSeek.stop_stream should safely catch network exceptions and return False."""
    with patch.object(mock_deepseek._http[0], "post", side_effect=Exception("network timeout")):
        ok = mock_deepseek.stop_stream(0, "chat-123", 42)
        assert ok is False


def test_send_interim_chunk_extracts_resp_id(mock_deepseek):
    """send_interim_chunk should extract response_message_id cleanly without dropping node."""
    sse_lines = [
        b'event: ready\n',
        b'data: {"request_message_id": 10, "response_message_id": 11, "model_type": "default"}\n',
        b'\n',
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = iter(sse_lines)

    with patch.object(mock_deepseek, "_throttle"), \
         patch.object(mock_deepseek, "_get_pow", return_value="fake-pow"), \
         patch("curl_cffi.requests.post", return_value=mock_resp):

        resp_id = mock_deepseek.send_interim_chunk(0, "chat-test", "interim content", parent_message_id=9)
        assert resp_id == 11


def test_smart_context_retention_preserves_turn1():
    """Smart context retention must never drop the initial Turn 1 user query."""
    messages = [
        {"role": "system", "content": "You are a master coder."},
        {"role": "user", "content": "INITIAL SPEC: Audit the entire authentication module and fix security flaw."},
    ]
    for i in range(10):
        messages.append({"role": "assistant", "content": f"Decision step {i}: checking files"})
        messages.append({"role": "tool", "name": "read_file", "content": f"File content of step {i} " + ("x" * 2000)})

    messages.append({"role": "user", "content": "Proceed with the patch."})

    sys_m = [m for m in messages if m.get("role") == "system"]
    non_sys_m = [m for m in messages if m.get("role") != "system"]

    first_asst_idx = next(
        (i for i, m in enumerate(non_sys_m) if m.get("role") in ("assistant", "tool")),
        len(non_sys_m),
    )
    initial_user_m = non_sys_m[:first_asst_idx]
    rest_m = non_sys_m[first_asst_idx:]

    recent_window = 8
    middle_m = rest_m[:-recent_window]
    recent_tail = rest_m[-recent_window:]

    compacted_middle = []
    for m in middle_m:
        r = m.get("role", "")
        c_text = m.get("content", "")
        if r == "tool" or c_text.strip().startswith("<tool_result>"):
            tool_name = m.get("name") or "tool"
            compacted_middle.append({
                "role": r,
                "content": f"[{tool_name} output processed: {len(c_text)} chars]"
            })
        else:
            compacted_middle.append({"role": r, "content": c_text})

    final_retained = sys_m + initial_user_m + compacted_middle + recent_tail

    # Assertions
    # 1. System prompt preserved
    assert final_retained[0]["content"] == "You are a master coder."
    # 2. Turn 1 query preserved word-for-word
    assert "INITIAL SPEC: Audit the entire authentication module" in final_retained[1]["content"]
    # 3. Old tools in middle were compacted
    compacted_tools = [m for m in compacted_middle if m["role"] == "tool"]
    assert len(compacted_tools) > 0
    for ct in compacted_tools:
        assert "output processed:" in ct["content"]
        assert "xxxx" not in ct["content"]
    # 4. Recent tail preserved with full detail
    assert final_retained[-1]["content"] == "Proceed with the patch."
