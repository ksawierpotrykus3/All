"""Unit tests for deepseek_client streaming, handling BATCH chunks, and fallback logic."""

import json
from unittest.mock import MagicMock, patch
import pytest

from server.core.deepseek_client import DeepSeek


class TestDeepSeekClientStream:
    """Test suite for stream_completion in DeepSeek."""

    def _setup_mock_response(self, lines: list[str]):
        """Helper to create a mock response with specified SSE lines."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        byte_lines = [l.encode("utf-8") for l in lines]
        mock_resp.iter_lines.return_value = iter(byte_lines)
        return mock_resp

    @patch("curl_cffi.requests.post")
    def test_batch_does_not_abort_stream(self, mock_post):
        """Verify that BATCH chunk with token update does not prematurely abort the stream."""
        lines = [
            'data: {"request_message_id": 1, "response_message_id": 2}',
            'data: {"v": {"response": {"message_id": 2, "fragments": [{"type": "THINKING", "content": ""}]}}}',
            'data: {"p": "response/fragments/0/content", "v": "Thinking about the files..."}',
            # Intermediate BATCH with token update (previously caused unconditional break)
            'data: {"o": "BATCH", "v": [{"p": "response/accumulated_token_usage", "v": 150}]}',
            # Response fragment starts
            'data: {"p": "response/fragments", "v": [{"type": "RESPONSE", "content": "I will read the files."}]}',
            'data: {"p": "response/fragments/1/content", "v": " First file: test.md"}',
            # FINISHED inside BATCH
            'data: {"o": "BATCH", "v": [{"p": "quasi_status", "v": "FINISHED"}]}',
        ]
        mock_post.return_value = self._setup_mock_response(lines)

        client = DeepSeek(pool=MagicMock())
        client._get_pow = MagicMock(return_value={"pow": "mock"})
        client._ses = MagicMock()
        client._throttle = MagicMock()

        stream_gen, meta = client.stream_completion(
            slot=0,
            chat_session_id="test_sess",
            prompt="hi",
            thinking_enabled=True,
        )

        chunks = list(stream_gen)
        full_text = "".join(chunks)

        assert "I will read the files." in full_text
        assert " First file: test.md" in full_text
        # Thinking text should NOT leak into generated response chunks
        assert "Thinking about the files..." not in full_text
        assert meta["resp_msg_id"] == 2

    @patch("curl_cffi.requests.post")
    def test_batch_finished_stops_stream(self, mock_post):
        """Verify that BATCH containing FINISHED stops the stream properly."""
        lines = [
            'data: {"request_message_id": 1, "response_message_id": 2}',
            'data: {"p": "response/fragments", "v": [{"type": "RESPONSE", "content": "Hello!"}]}',
            'data: {"o": "BATCH", "v": [{"p": "response/status", "o": "SET", "v": "FINISHED"}]}',
            'data: {"p": "response/fragments/0/content", "v": "Should not be received"}',
        ]
        mock_post.return_value = self._setup_mock_response(lines)

        client = DeepSeek(pool=MagicMock())
        client._get_pow = MagicMock(return_value={"pow": "mock"})
        client._ses = MagicMock()
        client._throttle = MagicMock()

        stream_gen, meta = client.stream_completion(
            slot=0,
            chat_session_id="test_sess",
            prompt="hi",
            thinking_enabled=True,
        )

        chunks = list(stream_gen)
        full_text = "".join(chunks)
        assert full_text == "Hello!"
        assert "Should not be received" not in full_text

    @patch("curl_cffi.requests.post")
    def test_thinking_does_not_leak_on_interrupted_stream(self, mock_post):
        """Verify that when stream ends abruptly during thinking, thoughts are preserved in thinking_fallback and not yielded directly."""
        lines = [
            'data: {"request_message_id": 1, "response_message_id": 2}',
            'data: {"v": "Thinking process part 1..."}',
            'data: {"v": " thinking process part 2..."}',
        ]
        mock_post.return_value = self._setup_mock_response(lines)

        client = DeepSeek(pool=MagicMock())
        client._get_pow = MagicMock(return_value={"pow": "mock"})
        client._ses = MagicMock()
        client._throttle = MagicMock()

        stream_gen, meta = client.stream_completion(
            slot=0,
            chat_session_id="test_sess",
            prompt="hi",
            thinking_enabled=True,
        )

        chunks = list(stream_gen)
        full_text = "".join(chunks)

        # Nothing yielded directly when thinking_enabled=True
        assert full_text == ""
        # Thoughts preserved in thinking_fallback
        assert "Thinking process part 1... thinking process part 2..." in meta["thinking_fallback"]

    @patch("curl_cffi.requests.post")
    def test_quasi_status_does_not_abort_before_response(self, mock_post):
        """Verify that quasi_status=FINISHED does not prematurely abort before RESPONSE is received."""
        lines = [
            'data: {"request_message_id": 1, "response_message_id": 2}',
            'data: {"v": {"response": {"message_id": 2, "fragments": [{"type": "THINKING", "content": ""}]}}}',
            'data: {"p": "response/fragments/0/content", "v": "Planning the solution..."}',
            # quasi_status=FINISHED emitted when thinking phase ends
            'data: {"p": "quasi_status", "v": "FINISHED"}',
            # Response fragment begins after quasi phase
            'data: {"p": "response/fragments", "v": [{"type": "RESPONSE", "content": "Here is the response code."}]}',
            'data: {"p": "response/fragments/1/content", "v": "\\nprint(\'done\')"}',
            # Final completion signal
            'data: {"p": "response/status", "o": "SET", "v": "FINISHED"}',
        ]
        mock_post.return_value = self._setup_mock_response(lines)

        client = DeepSeek(pool=MagicMock())
        client._get_pow = MagicMock(return_value={"pow": "mock"})
        client._ses = MagicMock()
        client._throttle = MagicMock()

        stream_gen, meta = client.stream_completion(
            slot=0,
            chat_session_id="test_sess",
            prompt="hi",
            thinking_enabled=True,
        )

        chunks = list(stream_gen)
        full_text = "".join(chunks)

        assert "Here is the response code." in full_text
        assert "print('done')" in full_text
        assert "Planning the solution..." not in full_text
        assert meta["resp_msg_id"] == 2

    @patch("curl_cffi.requests.post")
    def test_response_fragments_in_initial_response_object(self, mock_post):
        """Verify that RESPONSE fragments inside item['v']['response'] activate response_started immediately."""
        lines = [
            'data: {"request_message_id": 5, "response_message_id": 6}',
            'data: {"v": {"response": {"message_id": 6, "fragments": [{"id": 2, "type": "THINK", "content": "Let me think"}, {"id": 3, "type": "RESPONSE", "content": "<"}]}}}',
            'data: {"p": "response/fragments/-1/content", "o": "APPEND", "v": "｜｜DSML｜｜"}',
            'data: {"v": " calls>\\n"}',
            'data: {"p": "response/status", "o": "SET", "v": "FINISHED"}',
        ]
        mock_post.return_value = self._setup_mock_response(lines)

        client = DeepSeek(pool=MagicMock())
        client._get_pow = MagicMock(return_value={"pow": "mock"})
        client._ses = MagicMock()
        client._throttle = MagicMock()

        stream_gen, meta = client.stream_completion(
            slot=0,
            chat_session_id="test_sess",
            prompt="hi",
            thinking_enabled=True,
        )

        chunks = list(stream_gen)
        full_text = "".join(chunks)

        assert "<" in full_text
        assert "｜｜DSML｜｜" in full_text
        assert " calls>\n" in full_text
        assert meta["resp_msg_id"] == 6
        assert meta["thinking_fallback"] == ""

    @patch("curl_cffi.requests.post")
    def test_stream_continue_sends_correct_payload(self, mock_post):
        """Verify that stream_continue posts fallback_to_resume and message_id to /api/v0/chat/continue."""
        lines = [
            'data: {"request_message_id": 5, "response_message_id": 6}',
            'data: {"v": {"response": {"message_id": 6, "fragments": [{"type": "RESPONSE", "content": "resumed text"}]}}}',
            'data: {"p": "response/status", "o": "SET", "v": "FINISHED"}',
        ]
        mock_post.return_value = self._setup_mock_response(lines)

        client = DeepSeek(pool=MagicMock())
        client._ses = MagicMock()
        client._throttle = MagicMock()

        stream_gen, meta = client.stream_continue(
            slot=0,
            chat_session_id="test_sess_continue",
            message_id=6,
        )

        chunks = list(stream_gen)
        assert "".join(chunks) == "resumed text"
        assert meta["resp_msg_id"] == 6

        # Verify POST call
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "/api/v0/chat/continue" in mock_post.call_args[0][0]
        assert call_kwargs["json"] == {
            "chat_session_id": "test_sess_continue",
            "message_id": 6,
            "fallback_to_resume": True,
        }


