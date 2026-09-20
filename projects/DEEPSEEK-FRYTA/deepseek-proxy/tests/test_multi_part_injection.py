"""tests/test_multi_part_injection.py — Integration test for multi-part prompt injection."""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from server.services.prompt_chunker import split_prompt_payload
from server.services.state_service import set_conv, get_conv, _msg_hash


def test_chunking_and_state_continuity():
    """Verify that multi-part chunking updates parent_id across interim chunks
    while maintaining exact conversation hash stability.
    """
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "<user_info>OS: win32</user_info>"},
        {"role": "user", "content": "<user_query>Run speed audit</user_query>"},
        {"role": "assistant", "content": "Running tools..."},
        {"role": "tool", "content": "<tool_result>\n<t>read_file</t>\n<id>1</id>\n<content>\n" + ("A" * 600) + "\n</content>\n</tool_result>"},
        {"role": "tool", "content": "<tool_result>\n<t>read_file</t>\n<id>2</id>\n<content>\n" + ("B" * 600) + "\n</content>\n</tool_result>"},
    ]

    # 1. Check hash stability:
    h1 = _msg_hash(messages[:3])  # Turn 1
    h2 = _msg_hash(messages)      # Turn 2 with tool results
    assert h1 == h2, "Conversation hash must remain identical across turns despite tool results"

    # 2. Simulate initial state in conv_state (Turn 1 completed with parent_id=10)
    set_conv(messages[:3], "chat_session_xyz", 10, 0)
    entry = get_conv(messages)
    assert entry is not None
    assert entry["chat_id"] == "chat_session_xyz"
    assert entry["parent_id"] == 10

    # 3. Build a large prompt that requires splitting
    oversized_prompt = (
        "[User]:\n"
        "<tool_result>\n<t>read_file</t>\n<id>1</id>\n<content>\n" + ("A" * 600) + "\n</content>\n</tool_result>\n\n"
        "<tool_result>\n<t>read_file</t>\n<id>2</id>\n<content>\n" + ("B" * 600) + "\n</content>\n</tool_result>\n\n"
        "CRITICAL: You are an AGENT with tools.\n\n[Assistant]:\n"
    )

    chunks = split_prompt_payload(oversized_prompt, max_chunk_size=700)
    assert len(chunks) >= 2

    # 4. Simulate the interim injection flow:
    current_parent_id = entry["parent_id"]  # 10
    mock_ds = MagicMock()
    # Mock send_interim_chunk returning 20 as response_message_id for part 1
    mock_ds.send_interim_chunk.return_value = 20

    for interim_chunk in chunks[:-1]:
        current_parent_id = mock_ds.send_interim_chunk(
            0,
            "chat_session_xyz",
            interim_chunk,
            current_parent_id,
            model_type="expert",
        )

    assert current_parent_id == 20
    assert mock_ds.send_interim_chunk.called

    # 5. Simulate final stream_completion using the new parent_id (20) and generating response 30
    final_parent_id = 30
    set_conv(messages, "chat_session_xyz", final_parent_id, 0)

    # 6. Verify subsequent turn lookup:
    updated_entry = get_conv(messages)
    assert updated_entry is not None
    assert updated_entry["chat_id"] == "chat_session_xyz"
    assert updated_entry["parent_id"] == 30, "Next turn must continue from the final response message ID"


def test_send_interim_chunk_pow_retry():
    """Verify that send_interim_chunk clears PoW cache and retries upon INVALID_POW_RESPONSE."""
    from server.core.deepseek_client import DeepSeek, AccountPool

    pool = MagicMock(spec=AccountPool)
    ds = DeepSeek(pool)

    # First response returns INVALID_POW_RESPONSE, second returns valid SSE with response_message_id
    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 200
    mock_resp_fail.iter_lines.return_value = [
        b'{"code": 40005, "msg": "INVALID_POW_RESPONSE"}'
    ]

    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.iter_lines.return_value = [
        b'data: {"response_message_id": 42, "model_type": "expert"}'
    ]

    with patch("server.core.deepseek_client.requests.post", side_effect=[mock_resp_fail, mock_resp_ok]), \
         patch.object(ds, "_get_pow", return_value={"pow": "test"}), \
         patch.object(ds, "_throttle"), \
         patch.object(ds, "_ses"):
        res_id = ds.send_interim_chunk(0, "sess_123", "chunk text", 10)
        assert res_id == 42


def test_send_interim_chunk_rate_limit():
    """Verify that send_interim_chunk raises DeepSeekRateLimitError on server is busy."""
    from server.core.deepseek_client import DeepSeek, AccountPool, DeepSeekRateLimitError

    pool = MagicMock(spec=AccountPool)
    ds = DeepSeek(pool)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        b'data: {"type": "error", "content": "Server is busy. Try again later."}'
    ]

    with patch("server.core.deepseek_client.requests.post", return_value=mock_resp), \
         patch.object(ds, "_get_pow", return_value={"pow": "test"}), \
         patch.object(ds, "_throttle"), \
         patch.object(ds, "_ses"):
        with pytest.raises(DeepSeekRateLimitError):
            ds.send_interim_chunk(0, "sess_123", "chunk text", 10)


@pytest.mark.asyncio
async def test_orchestrate_chunks_if_needed():
    """Verify _orchestrate_chunks_if_needed splits oversized prompt and updates parent_id."""
    from server.services.proxy_service import ProxyService

    service = ProxyService()
    oversized = (
        "[User]:\n"
        + "<tool_result>\n<t>r</t>\n<id>1</id>\n<content>\n"
        + ("A" * 70_000)
        + "\n</content>\n</tool_result>\n\n"
        + "<tool_result>\n<t>r</t>\n<id>2</id>\n<content>\n"
        + ("B" * 70_000)
        + "\n</content>\n</tool_result>\n\n"
        + "CRITICAL: You are an AGENT with tools.\n\n[Assistant]:\n"
    )
    assert len(oversized) > 120_000

    messages = [{"role": "user", "content": "hello"}]

    with patch("server.services.proxy_service.ds.send_interim_chunk", return_value=99) as mock_send, \
         patch("server.services.proxy_service.set_conv") as mock_set_conv, \
         patch("asyncio.sleep", return_value=None):
        final_prompt, new_parent, was_chunked = await service._orchestrate_chunks_if_needed(
            prompt=oversized,
            account_idx=0,
            chat_id="chat_123456789012",
            parent_id=10,
            model_type="expert",
            messages=messages,
            tools=None,
            thinking_enabled=True,
            search_enabled=False,
        )

        assert mock_send.called
        assert new_parent == 99
        assert was_chunked is True
        assert len(final_prompt) < len(oversized)
        assert mock_set_conv.called


