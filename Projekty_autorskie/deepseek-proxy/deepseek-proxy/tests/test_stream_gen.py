"""Testy _stream_gen — największe ryzyko, 200 linii, zero testów."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from server.services.proxy_service import _stream_gen, _tc_id


def _parse_sse(chunks: list[str]) -> list[dict]:
    """Parsuje SSE strumień na listę dictów."""
    result = []
    for c in chunks:
        if c.startswith("data: ") and not c.startswith("data: [DONE]"):
            try:
                result.append(json.loads(c[6:].strip()))
            except json.JSONDecodeError:
                pass
    return result


class TestStreamGenTextOnly:
    """_stream_gen — same tekst, bez tool calls."""

    def test_single_chunk(self):
        def gen():
            yield "Hello world"

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(),
            stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0, tools=None,
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        texts = [c["choices"][0]["delta"].get("content", "") for c in parsed if "content" in c["choices"][0].get("delta", {})]
        assert "Hello world" in "".join(texts)
        assert any(c["choices"][0].get("finish_reason") == "stop" for c in parsed)
        assert "data: [DONE]" in chunks[-1] if chunks else True

    def test_two_chunks(self):
        def gen():
            yield "Hello "
            yield "world"

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0, tools=None,
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
        )
        assert texts == "Hello world"

    def test_empty_chunks_skipped(self):
        def gen():
            yield ""
            yield "Actual text"
            yield ""

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0, tools=None,
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
        )
        assert texts == "Actual text"


class TestStreamGenToolCalls:
    """_stream_gen — wykrywanie tool calls."""

    @patch("server.services.proxy_service.set_conv")
    def test_single_tool_call(self, mock_set_conv):
        def gen():
            yield '<tool_call name="Read">'
            yield '<parameter name="path">/tmp/x</parameter>'
            yield '</tool_call>'

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Read", "description": "Read"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        calls = tool_deltas[0]
        assert any(tc["function"]["name"] == "Read" for tc in calls)
        assert any("path" in tc["function"]["arguments"] for tc in calls)
        mock_set_conv.assert_called_once()

    @patch("server.services.proxy_service.set_conv")
    def test_text_then_tool_call(self, mock_set_conv):
        def gen():
            yield "Let me read that "
            yield '<tool_call name="Read">'
            yield '<parameter name="path">/tmp/x</parameter>'
            yield '</tool_call>'

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Read", "description": "Read"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)

        text_parts = [
            c["choices"][0]["delta"]["content"]
            for c in parsed if "content" in c["choices"][0].get("delta", {})
        ]
        assert "Let me read that" in "".join(text_parts)

        tool_deltas = [
            c["choices"][0]["delta"]["tool_calls"]
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        assert tool_deltas[0][0]["function"]["name"] == "Read"

    @patch("server.services.proxy_service.set_conv")
    def test_unknown_tool_filtered(self, mock_set_conv):
        def gen():
            yield '<tool_call name="UnknownTool">'
            yield '<parameter name="x">1</parameter>'
            yield '</tool_call>'

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Read", "description": "Read"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        # Nieznane narzędzie → brak tool_calls w SSE
        assert len(tool_deltas) == 0


@patch("server.services.proxy_service.set_conv")
class TestStreamGenStopSequence:
    """_stream_gen — stop sequence."""

    def test_stop_sequence_truncates(self, mock_set_conv):
        def gen():
            yield "Hello wor STOP ld more text"

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0, tools=None,
            model="deepseek-chat", t0=0.0, t4=0.0,
            stop="STOP",
        ))
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
        )
        assert "STOP" not in texts
        assert "Hello wor" in texts

    def test_stop_as_list(self, mock_set_conv):
        def gen():
            yield "Hello||world"

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0, tools=None,
            model="deepseek-chat", t0=0.0, t4=0.0,
            stop=["||", "<end>"],
        ))
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
        )
        assert "||" not in texts
        assert "Hello" in texts


@patch("server.services.proxy_service.set_conv")
class TestStreamGenThinkingFallback:
    """_stream_gen — thinking fallback z meta."""

    def test_thinking_fallback_emits_tool_calls(self, mock_set_conv):
        def gen():
            yield ""

        meta = {
            "thinking_fallback": '<tool_call name="Read"><parameter name="path">/tmp/x</parameter></tool_call>',
        }
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Read", "description": "Read"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1

    def test_thinking_fallback_too_many_treated_as_text(self, mock_set_conv):
        calls = ''.join(
            f'<tool_call name="Read"><parameter name="x">{i}</parameter></tool_call>'
            for i in range(10)
        )

        def gen():
            yield ""

        meta = {"thinking_fallback": calls}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Read", "description": "Read"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        # > 8 calls → traktowane jako tekst, nie narzędzia
        assert len(tool_deltas) == 0

    def test_thinking_fallback_yields_as_text_when_no_tools(self, mock_set_conv):
        def gen():
            yield ""

        meta = {"thinking_fallback": "Here is my thinking process"}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0, tools=None,
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
        )
        assert "thinking process" in texts

    def test_thinking_fallback_damaged_invoke_emits_tool_calls(self, mock_set_conv):
        def gen():
            yield ""

        meta = {
            "thinking_fallback": (
                'oke name="Shell">\n'
                '<parameter name="command" string="true">git add -A; git commit -m "feat: test"</parameter>\n'
                '<parameter name="description" string="true">Commit changes</parameter>\n'
                '<parameter name="working_directory" string="true">f:\\PROJEKTY\\vinted</parameter>\n'
                '</invoke>\n'
                '</tool_calls>'
            ),
        }
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Shell", "description": "Shell"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        fn = tool_deltas[0][0]["function"]
        assert fn["name"] == "Shell"
        import json
        args = json.loads(fn["arguments"])
        assert "git commit" in args["command"]
        assert args["description"] == "Commit changes"


class TestStreamGenFlushToolCalls:
    """_stream_gen — tool calls wykryte dopiero po flush."""

    @patch("server.services.proxy_service.set_conv")
    def test_tool_call_detected_on_flush(self, mock_set_conv):
        def gen():
            yield '<tool_call name="Read"><parameter name="x">1</parameter>'

        meta = {}
        chunks = list(_stream_gen(
            stream_gen=gen(), stream_meta=meta,
            messages=[], parent_id=None, chat_id="chat_1",
            conv_uuid="c1", account_idx=0,
            tools=[{"name": "Read", "description": "Read"}],
            model="deepseek-chat", t0=0.0, t4=0.0,
        ))
        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        # Tier 3 powinien odzyskać brakujący </tool_call>
        assert len(tool_deltas) >= 1


class TestStreamGenTransientErrors:
    """_stream_gen — obsługa błędu 'Server is temporarily unavailable.'."""

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_temporarily_unavailable_triggers_retry_when_no_content_sent(
        self, mock_stream_completion, mock_sleep
    ):
        def failing_gen():
            raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")
            yield ""

        def success_gen():
            yield "Recovered after retry"

        mock_stream_completion.return_value = (success_gen(), {})

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen(),
                stream_meta={},
                messages=[],
                parent_id="msg_123",
                chat_id="chat_123",
                conv_uuid="c1",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )
        mock_stream_completion.assert_called_once()
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Recovered after retry" in texts
        assert "[Stream error:" not in texts

    def test_temporarily_unavailable_emits_error_when_content_already_sent(self):
        def partially_failing_gen():
            yield "Some initial content that is definitely longer than fifty characters so that it gets flushed to SSE"
            raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")

        chunks = list(
            _stream_gen(
                stream_gen=partially_failing_gen(),
                stream_meta={},
                messages=[],
                parent_id="msg_123",
                chat_id="chat_123",
                conv_uuid="c1",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Some initial content" in texts
        assert "[Stream error: DeepSeek error: Server is temporarily unavailable.]" in texts


class TestStreamGenRepromptPrematureStop:
    """Test automatycznego resume przez natywny continue gdy model zakończył odpowiedź bez tool calla w trybie agenta."""

    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_continue")
    def test_reprompt_when_model_stops_after_thinking_without_tool_call(
        self, mock_stream_continue, mock_set_conv
    ):
        def first_empty_gen():
            yield ""

        def continue_success_gen():
            yield '<tool_calls><invoke name="Shell"><parameter name="command">pytest</parameter></invoke></tool_calls>'

        mock_stream_continue.return_value = (continue_success_gen(), {"resp_msg_id": "429"})

        messages = [
            {"role": "user", "content": "Run tests"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "Write", "arguments": "{}"}}]},
            {"role": "tool", "content": "Wrote script"},
        ]
        tools = [{"type": "function", "function": {"name": "Shell"}}]

        chunks = list(
            _stream_gen(
                stream_gen=first_empty_gen(),
                stream_meta={"thinking_fallback": "Let me run the test script.", "resp_msg_id": "428"},
                messages=messages,
                parent_id="msg_427",
                chat_id="chat_75f8f",
                conv_uuid="c1",
                account_idx=0,
                tools=tools,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        mock_stream_continue.assert_called_once()
        # Weryfikacja że message_id w continue to int resp_msg_id (428)
        assert mock_stream_continue.call_args[0][2] == 428

        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed
            if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        fn = tool_deltas[0][0]["function"]
        assert fn["name"] == "Shell"
        assert "pytest" in fn["arguments"]
        assert any(c["choices"][0].get("finish_reason") == "tool_calls" for c in parsed)

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_empty_retry_triggers_next_backoff_until_success(
        self, mock_stream_completion, mock_set_conv, mock_sleep
    ):
        def failing_gen():
            raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")
            yield ""

        def empty_retried_gen():
            yield ""

        def successful_retried_gen():
            yield "Recovered on second retry attempt"

        # 1st retry call: returns empty generator (0 tokens)
        # 2nd retry call: succeeds with actual content
        mock_stream_completion.side_effect = [
            (empty_retried_gen(), {}),
            (successful_retried_gen(), {}),
        ]

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen(),
                stream_meta={},
                messages=[],
                parent_id="msg_123",
                chat_id="chat_123",
                conv_uuid="c1",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )
        assert mock_stream_completion.call_count == 2
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Recovered on second retry attempt" in texts

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_continue")
    def test_internal_thoughts_never_leak_as_response_when_tools_present(
        self, mock_stream_continue, mock_set_conv, mock_sleep
    ):
        """In tool mode, internal thinking thoughts must never leak as assistant content."""
        def first_empty_gen():
            yield ""

        def continue_success_gen():
            yield "<tool_calls><invoke name=\"Shell\"><parameter name=\"command\">pytest</parameter></invoke></tool_calls>"

        mock_stream_continue.return_value = (continue_success_gen(), {"resp_msg_id": "999"})

        messages = [
            {"role": "user", "content": "Execute tests"},
        ]
        tools = [{"type": "function", "function": {"name": "Shell"}}]

        chunks = list(
            _stream_gen(
                stream_gen=first_empty_gen(),
                stream_meta={"thinking_fallback": "I need to run the debug script. Let me just run it.", "resp_msg_id": 999},
                messages=messages,
                parent_id="msg_100",
                chat_id="chat_test",
                conv_uuid="c1",
                account_idx=0,
                tools=tools,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "I need to run the debug script" not in texts
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed
            if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert tool_deltas[0][0]["function"]["name"] == "Shell"

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_completion")
    @patch("server.services.proxy_service.ds.stream_continue")
    def test_already_finished_without_tokens_triggers_reprompt(
        self, mock_stream_continue, mock_stream_completion, mock_set_conv, mock_sleep
    ):
        """When continue returns already_finished on DeepSeek and 0 tokens were yielded with tools present,
        proxy must immediately reprompt on the same session instead of returning empty data: [DONE]."""
        def empty_gen():
            yield ""

        def reprompt_success_gen():
            yield '<tool_calls><invoke name="Shell"><parameter name="command">ls</parameter></invoke></tool_calls>'

        mock_stream_continue.return_value = (empty_gen(), {"already_finished": True, "resp_msg_id": 500})
        mock_stream_completion.return_value = (reprompt_success_gen(), {"resp_msg_id": 501})

        messages = [
            {"role": "user", "content": "List files"},
        ]
        tools = [{"type": "function", "function": {"name": "Shell"}}]

        chunks = list(
            _stream_gen(
                stream_gen=empty_gen(),
                stream_meta={"resp_msg_id": 500},
                messages=messages,
                parent_id="msg_499",
                chat_id="chat_test_af",
                conv_uuid="c_af",
                account_idx=0,
                tools=tools,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        mock_stream_continue.assert_called_once()
        mock_stream_completion.assert_called_once()
        assert mock_stream_completion.call_args[1]["chat_session_id"] == "chat_test_af"
        assert mock_stream_completion.call_args[1]["parent_message_id"] == 500

        parsed = _parse_sse(chunks)
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed
            if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        assert tool_deltas[0][0]["function"]["name"] == "Shell"

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_unyielded_buffer_does_not_block_retry(
        self, mock_stream_completion, mock_set_conv, mock_sleep
    ):
        """When text_buffer has data but text_yielded_len == 0, retry must proceed."""
        def failing_gen_with_buffered_content():
            # A short chunk (< 40 chars) stays in sieve/buffer and is NOT yielded to client
            yield "Short unyielded token"
            raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")

        def successful_retry_gen():
            yield "Success after retry with full answer that exceeds threshold"

        mock_stream_completion.return_value = (successful_retry_gen(), {})

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen_with_buffered_content(),
                stream_meta={},
                messages=[],
                parent_id="msg_123",
                chat_id="chat_123",
                conv_uuid="c1",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )
        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Success after retry" in texts
        assert "[Stream error:" not in texts

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.create_session", return_value="new_rolled_session_id")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_existing_session_fast_backoff_and_session_rollover(
        self, mock_stream_completion, mock_create_session, mock_set_conv, mock_sleep
    ):
        """Existing session with permanent error (chat session not found) performs immediate Session Rollover with trimmed prompt."""
        def failing_gen():
            yield "partial"
            raise RuntimeError("DeepSeek error: chat session not found")

        def rollover_gen():
            yield "Hello from rolled over fresh session!"

        # Initial stream fails, then rollover call succeeds
        mock_stream_completion.side_effect = [
            (rollover_gen(), {}),
        ]

        huge_content = "X" * 5000
        messages = [
            {"role": "system", "content": "You are a bot"},
            {"role": "user", "content": "Here is large file: " + huge_content},
            {"role": "assistant", "content": "Reading file"},
            {"role": "tool", "content": "Tool output: " + huge_content},
            {"role": "user", "content": "What is next?"},
        ]

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen(),
                stream_meta={},
                messages=messages,
                parent_id="msg_existing_123",
                chat_id="old_dead_session",
                conv_uuid="c1",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        # Verify rollover session was created on least loaded account
        assert mock_create_session.called
        assert mock_create_session.call_args[0][0] in (0, 1)
        # Verify stream_completion was called for rollover with fresh session
        rollover_call_args = mock_stream_completion.call_args_list[-1]
        assert rollover_call_args[0][1] == "new_rolled_session_id"
        assert rollover_call_args[0][3] is None  # parent_id is None for new session
        # Verify prior conversation history is preserved via attachment
        prompt_used = rollover_call_args[0][2]
        assert "conversation_history.md" in prompt_used or "attached in document" in prompt_used
        assert len(prompt_used) < 25000
        # Verify ref_file_ids were passed for uploaded history attachment
        ref_file_ids_passed = rollover_call_args[1].get("ref_file_ids")
        assert ref_file_ids_passed is not None

        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Hello from rolled over fresh session!" in texts

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.create_session")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_existing_session_503_stays_on_same_session(
        self, mock_stream_completion, mock_create_session, mock_set_conv, mock_sleep
    ):
        """Transient 503 error retries on the SAME session and NEVER creates a new session."""
        def failing_gen():
            yield "partial"
            raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")

        def success_gen():
            yield "Success on retry!"

        # Retry 1 succeeds on same session
        mock_stream_completion.side_effect = [
            (success_gen(), {}),
        ]

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen(),
                stream_meta={},
                messages=[{"role": "user", "content": "hi"}],
                parent_id="msg_parent_456",
                chat_id="session_keep_alive",
                conv_uuid="c2",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        # New session must NOT be created on 503
        mock_create_session.assert_not_called()
        # Stream completion must be retried on SAME session and SAME parent
        retry_call = mock_stream_completion.call_args_list[0]
        assert retry_call[0][1] == "session_keep_alive"
        assert retry_call[0][3] == "msg_parent_456"

        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Success on retry!" in texts

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_continue")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_midstream_503_retries_via_stream_continue_when_resp_msg_id_assigned(
        self, mock_stream_completion, mock_stream_continue, mock_set_conv, mock_sleep
    ):
        """When DeepSeek assigned resp_msg_id (e.g. 30) before 503 error, backoff retries via stream_continue instead of creating new message."""
        def failing_gen():
            yield ""
            raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")

        def continue_success_gen():
            yield "Hello after continue resumed message 30"

        mock_stream_continue.return_value = (continue_success_gen(), {"resp_msg_id": 30})

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen(),
                stream_meta={"resp_msg_id": 30},
                messages=[{"role": "user", "content": "hi"}],
                parent_id="msg_29",
                chat_id="session_continue_flow",
                conv_uuid="c3",
                account_idx=0,
                tools=None,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        # Must NOT call stream_completion (which would send a new message)
        mock_stream_completion.assert_not_called()
        # Must call stream_continue on message 30
        mock_stream_continue.assert_called_once_with(
            0,
            "session_continue_flow",
            30,
            model_type="default",
            thinking_enabled=True,
            throttle=False,
        )

        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        assert "Hello after continue resumed message 30" in texts

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.stream_completion")
    @patch("server.services.proxy_service.ds.stream_continue")
    def test_thinking_fallback_suppressed_and_retries_on_reprompt_failure(
        self, mock_stream_continue, mock_stream_completion, mock_set_conv, mock_sleep
    ):
        """When model stops after thinking, continue is already finished, and reprompt throws
        'Server is temporarily unavailable.', proxy must NOT leak thinking as response and must retry."""
        def empty_gen():
            yield ""

        mock_stream_continue.return_value = (empty_gen(), {"already_finished": True, "resp_msg_id": 6})

        call_count = [0]
        def mock_completion_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call is the reprompt which fails due to transient cluster error
                raise RuntimeError("DeepSeek error: Server is temporarily unavailable.")
            # Retry call succeeds with a tool call
            def success_tool_gen():
                yield '<tool_calls><invoke name="Shell"><parameter name="command">ls</parameter></invoke></tool_calls>'
            return success_tool_gen(), {"resp_msg_id": 10}

        mock_stream_completion.side_effect = mock_completion_side_effect

        thoughts = "wants me to review the project structure and clean up. Let me do parallel exploration"
        chunks = list(
            _stream_gen(
                stream_gen=empty_gen(),
                stream_meta={"thinking_fallback": thoughts, "resp_msg_id": 6},
                messages=[{"role": "user", "content": "Clean up project"}],
                parent_id="msg_5",
                chat_id="session_cluster_err",
                conv_uuid="c_err",
                account_idx=0,
                tools=[{"name": "Shell", "description": "run command"}],
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        parsed = _parse_sse(chunks)
        texts = "".join(
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        )
        # 1. Critical: thinking buffer must NEVER leak into assistant response
        assert "wants me to review" not in texts
        assert "Let me do parallel exploration" not in texts

        # 2. Retry must be triggered and tool call emitted
        assert mock_stream_completion.call_count >= 2
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed
            if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        assert tool_deltas[0][0]["function"]["name"] == "Shell"

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.create_session", return_value="rescued_session_id")
    @patch("server.services.proxy_service.ds.stream_continue")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_exhausted_stream_backoff_triggers_account_failover_or_rollover(
        self, mock_stream_completion, mock_stream_continue, mock_create_session, mock_set_conv, mock_sleep
    ):
        """When all STREAM BACKOFF retries are exhausted on an overloaded existing session,

        proxy performs Account Failover or Session Rollover with conversation_history.md rather than failing to user.
        """
        def empty_gen():
            yield ""

        mock_stream_continue.return_value = (empty_gen(), {"already_finished": True, "resp_msg_id": 12})

        # All 4 retry attempts fail with Premature stop
        def mock_completion_side_effect(*args, **kwargs):
            session_arg = args[1]
            if session_arg == "rescued_session_id":
                def success_gen():
                    yield '<tool_calls><invoke name="Search"><parameter name="query">test</parameter></invoke></tool_calls>'
                return success_gen(), {"resp_msg_id": 100}
            # Otherwise it's a failing retry attempt on the old overloaded session
            raise RuntimeError('Premature stop: model stopped after thinking without tool call or response (intent: "exploring")')

        mock_stream_completion.side_effect = mock_completion_side_effect

        thoughts = "wants me to continue. I'm in plan mode. I need to research this."
        chunks = list(
            _stream_gen(
                stream_gen=empty_gen(),
                stream_meta={"thinking_fallback": thoughts, "resp_msg_id": 12},
                messages=[
                    {"role": "user", "content": "Initial query"},
                    {"role": "assistant", "content": "First response"},
                    {"role": "user", "content": "Continue plan"},
                ],
                parent_id="msg_11",
                chat_id="overloaded_session_xyz",
                conv_uuid="c_overloaded",
                account_idx=1,
                tools=[{"name": "Search", "description": "search code"}],
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        parsed = _parse_sse(chunks)
        # Ensure error message was NOT emitted to user
        stream_errors = [
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "[Stream error:" in c["choices"][0].get("delta", {}).get("content", "")
        ]
        assert not stream_errors

        # Verify rescue session was created
        tool_deltas = [
            c["choices"][0]["delta"].get("tool_calls")
            for c in parsed
            if "tool_calls" in c["choices"][0].get("delta", {})
        ]
        assert len(tool_deltas) >= 1
        assert tool_deltas[0][0]["function"]["name"] == "Search"

    @patch("time.sleep", return_value=None)
    @patch("server.services.proxy_service.set_conv")
    @patch("server.services.proxy_service.ds.create_session", return_value="new_session_len_limit")
    @patch("server.services.proxy_service.ds.upload_file", return_value="dfid_history_123")
    @patch("server.services.proxy_service.ds.stream_completion")
    def test_length_limit_triggers_immediate_session_rollover_without_backoff(
        self, mock_stream_completion, mock_upload_file, mock_create_session, mock_set_conv, mock_sleep
    ):
        """When DeepSeek returns 'Length limit reached. Please start a new chat.', proxy MUST NOT

        waste time in _STREAM_BACKOFF on the same dead session, but immediately roll over to
        a fresh session on the least loaded account with full history in conversation_history.md.
        """
        def failing_gen():
            yield ""
            raise RuntimeError("DeepSeek error: Length limit reached. Please start a new chat.")

        def fresh_session_gen():
            yield "Odpowiedź z nowej sesji po rolloverze."

        mock_stream_completion.return_value = (fresh_session_gen(), {"resp_msg_id": 10})

        messages = [
            {"role": "system", "content": "You are assistant"},
            {"role": "user", "content": "Long task step 1"},
            {"role": "assistant", "content": "Doing step 1"},
            {"role": "user", "content": "Now step 2"},
        ]

        chunks = list(
            _stream_gen(
                stream_gen=failing_gen(),
                stream_meta={},
                messages=messages,
                parent_id="msg_99",
                chat_id="exceeded_session_id",
                conv_uuid="c_len",
                account_idx=0,
                tools=[{"name": "Read", "description": "read"}],
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
            )
        )

        # 1. Verification: time.sleep should NOT be called for backoff retries on the same session
        assert mock_sleep.call_count == 0

        # 2. Verification: fresh session was created immediately
        assert mock_create_session.called

        # 3. Verification: stream_completion was called with new session and conversation_history.md
        completion_args = mock_stream_completion.call_args[0]
        completion_kwargs = mock_stream_completion.call_args[1]
        assert completion_args[1] == "new_session_len_limit"
        assert completion_args[3] is None  # fresh session, parent_id is None
        assert "conversation_history.md" in completion_args[2] or "attached in document" in completion_args[2]
        assert completion_kwargs.get("ref_file_ids") == ["dfid_history_123"]

        # 4. Verification: User received the answer from the fresh session
        parsed = _parse_sse(chunks)
        content_deltas = [
            c["choices"][0]["delta"].get("content", "")
            for c in parsed
            if "content" in c["choices"][0].get("delta", {})
        ]
        assert "Odpowiedź z nowej sesji po rolloverze." in "".join(content_deltas)



