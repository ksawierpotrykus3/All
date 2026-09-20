import time
from unittest.mock import MagicMock, patch
import pytest
from server.services.proxy_service import _prepare_new_session_payload, _stream_gen


def test_prepare_new_session_payload_packs_history_into_file():
    messages = [
        {"role": "system", "content": "You are assistant."},
        {"role": "user", "content": "Hello turn 1"},
        {"role": "assistant", "content": "Hi there!", "tool_calls": [{"id": "call_1", "function": {"name": "test_tool", "arguments": "{}"}}]},
        {"role": "tool", "content": "Result 1", "name": "test_tool"},
        {"role": "user", "content": "Now do turn 2"},
    ]

    mock_ds = MagicMock()
    mock_ds.upload_file.return_value = "doc_fid_123"

    with patch("server.services.proxy_service.ds", mock_ds):
        prompt, file_ids = _prepare_new_session_payload(
            target_slot=1,
            messages=messages,
            tools=[{"type": "function", "function": {"name": "test_tool", "description": "desc"}}],
            model_type="default",
        )

        # Must upload conversation_history.md
        mock_ds.upload_file.assert_called_once()
        call_kwargs = mock_ds.upload_file.call_args[1]
        assert call_kwargs["filename"] == "conversation_history.md"
        assert call_kwargs["slot"] == 1
        assert file_ids == ["doc_fid_123"]

        # Prompt must be concise and reference the attached document
        assert "conversation_history.md" in prompt
        assert "Now do turn 2" in prompt
        # Inline prompt should not contain the raw old dialogue turns
        assert len(prompt) < 10000


def test_stream_gen_migrates_to_alt_account_even_with_parent_id():
    def failing_stream():
        raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")
        yield

    def success_stream():
        yield 'data: {"choices": [{"delta": {"content": "Success on slot 0"}, "finish_reason": null}]}\n\n'
        yield 'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'

    mock_ds = MagicMock()
    mock_ds.create_session.return_value = "chat_alt_999"
    mock_ds.upload_file.return_value = "doc_alt_file"
    mock_ds.stream_completion.return_value = (success_stream(), {"resp_msg_id": 555})

    mock_ap = MagicMock()
    mock_ap.is_valid.side_effect = lambda slot: True  # both slots 0 and 1 are valid

    mock_rl = MagicMock()
    mock_rl.get_until.side_effect = lambda slot: 0.0  # alt slot is not rate limited

    messages = [
        {"role": "system", "content": "You are assistant."},
        {"role": "user", "content": "First query"},
        {"role": "assistant", "content": "Response"},
        {"role": "user", "content": "Second query"},
    ]

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.ap", mock_ap), \
         patch("server.services.proxy_service.rate_limiter", mock_rl), \
         patch("server.services.proxy_service.time.sleep", return_value=None):

        gen = _stream_gen(
            stream_gen=failing_stream(),
            stream_meta={"resp_msg_id": 100},
            messages=messages,
            parent_id="msg_existing_parent",  # parent_id is NOT None!
            chat_id="chat_curr_123",
            conv_uuid="conv_test",
            account_idx=1,  # fails on slot 1
            tools=[],
            model="deepseek-chat",
            t0=time.time(),
            t4=time.time(),
            prompt="query",
        )

        chunks = list(gen)
        # Should have migrated to slot 0 and succeeded
        assert any("Success on slot 0" in c for c in chunks)
        mock_ds.create_session.assert_called_with(0, throttle=False)
