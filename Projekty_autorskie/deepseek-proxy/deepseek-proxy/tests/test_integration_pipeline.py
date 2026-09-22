"""Integration test: full pipeline without DeepSeek API."""

import json
import re
import pytest
from server.core.input_parser import InputParser, ParsedRequest
from server.core.prompt_builder import PromptBuilder
from server.core.stream_handler import StreamHandler, ToolMgr
from server.services.proxy_service import _extract_prompt_parts, _build_tc_list, _tc_id
from server.repair.repair_tier3 import repair_tier3


SAMPLE_TOOLS = [
    {
        "name": "Read",
        "description": "Read a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "Write",
        "description": "Write a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
        },
    },
]


class TestInputToPrompt:
    def test_input_parser_to_prompt_builder(self):
        raw = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Read file /tmp/test.txt"},
            ],
            "tools": SAMPLE_TOOLS,
            "model": "deepseek-v4-pro",
        }

        parsed = InputParser.parse(raw)
        assert isinstance(parsed, ParsedRequest)
        assert parsed.tools is not None
        assert not parsed.has_tools_in_system_prompt

        system_prompt = "You are a helpful assistant."
        user_message = "Read file /tmp/test.txt"
        prompt = PromptBuilder.build(
            user_message,
            system_prompt=system_prompt,
            tools_schema=parsed.tools,
        )

        assert "[System]:" in prompt
        assert "[User]:" in prompt
        assert "[Assistant]:" in prompt
        assert "[Available Tool]: Read(" in prompt
        assert "file_path: string (required)" in prompt
        assert "[Available Tool]: Write(" in prompt

    def test_input_parser_detects_existing_tools(self):
        raw = {
            "messages": [
                {"role": "system", "content": "You have <tool_call>. Available Tools: Read"},
                {"role": "user", "content": "Do something"},
            ],
            "tools": [{"name": "Read", "description": "Read files"}],
            "model": "deepseek-v4-pro",
        }

        parsed = InputParser.parse(raw)
        assert parsed.has_tools_in_system_prompt

        system_prompt = "You have <tool_call>. Available Tools: Read"
        prompt = PromptBuilder.build(
            "Do something",
            system_prompt=system_prompt,
            tools_schema=parsed.tools,
        )

        # FIX 2026-09-04: Tools are ALWAYS added when provided, even if system_prompt mentions them
        assert "[Available Tool]: Read" in prompt
        assert "IMPORTANT: When you need to call a tool" in prompt


class TestStreamHandlerPipeline:
    def test_stream_handler_detects_tool_calls(self):
        chunks = [
            "Let me read that file for you.",
            '<tool_call name="Read">',
            '<parameter name="file_path">/tmp/test.txt</parameter>',
            '</tool_call>',
            "\nDone.",
        ]

        handler = StreamHandler(tool_names=["Read", "Write"])
        text_parts = []
        tool_calls = []

        for chunk in chunks:
            events = handler.feed(chunk)
            for evt in events:
                if evt["type"] == "text":
                    text_parts.append(evt["data"])
                elif evt["type"] == "tool_calls":
                    tool_calls.extend(evt["data"])

        flush_events = handler.flush()
        for evt in flush_events:
            if evt["type"] == "text":
                text_parts.append(evt["data"])
            elif evt["type"] == "tool_calls":
                tool_calls.extend(evt["data"])

        assert len(text_parts) >= 1
        assert "Let me read that file" in " ".join(text_parts)

        assert len(tool_calls) >= 1
        assert tool_calls[0]["name"] == "Read"
        assert "/tmp/test.txt" in tool_calls[0].get("arguments", "")

    def test_tool_mgr_validates_names(self):
        calls = [
            {"name": "Read", "arguments": '{"file_path": "test.txt"}'},
            {"name": "UnknownTool", "arguments": "{}"},
            {"name": "Write", "arguments": '{"file_path": "out.txt", "content": "data"}'},
        ]

        validated = ToolMgr.validate(calls, ["Read", "Write"])
        assert len(validated) == 2
        assert validated[0]["name"] == "Read"
        assert validated[1]["name"] == "Write"

    def test_tool_mgr_tier3_recovers_truncated(self):
        broken = '<tool_call name="Read"><parameter name="file_path">test.txt</parameter>'
        calls = ToolMgr.try_parse(broken, ["Read", "Write"])
        assert len(calls) >= 1
        assert calls[0]["name"] == "Read"

    def test_stream_handler_rejects_unknown_tools(self):
        chunks = [
            '<tool_call name="Unknown">',
            '<parameter name="x">1</parameter>',
            '</tool_call>',
        ]

        handler = StreamHandler(tool_names=["Read"])
        tool_calls = []
        for chunk in chunks:
            for evt in handler.feed(chunk):
                if evt["type"] == "tool_calls":
                    tool_calls.extend(evt["data"])
        for evt in handler.flush():
            if evt["type"] == "tool_calls":
                tool_calls.extend(evt["data"])

        assert len(tool_calls) == 0


class TestSystemReminderFiltering:
    def test_input_parser_filters_old_reminders(self):
        raw = {
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "system", "content": "<system-reminder>Old context</system-reminder>"},
                {"role": "system", "content": "<system-reminder>New context</system-reminder>"},
                {"role": "user", "content": "Hello"},
            ],
            "model": "deepseek-v4-pro",
        }

        parsed = InputParser.parse(raw)
        reminder_count = sum(
            1 for m in parsed.messages
            if m.get("role") == "system" and "<system-reminder>" in str(m.get("content", ""))
        )
        assert reminder_count == 1

    def test_input_parser_detects_resume(self):
        raw = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "deepseek-chat",
        }

        state = {"parent_id": "msg_123", "chat_id": "chat_456", "account": 0}
        parsed = InputParser.parse(raw, state)
        assert parsed.is_resume


class TestExtractPromptParts:
    def test_basic_system_and_user(self):
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        sp, hist, um = _extract_prompt_parts(msgs)
        assert sp == "You are helpful."
        assert um == "Hello"
        assert hist == []

    def test_with_history(self):
        msgs = [
            {"role": "system", "content": "Assistant."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]
        sp, hist, um = _extract_prompt_parts(msgs)
        assert sp == "Assistant."
        assert um == "How are you?"
        assert len(hist) == 2
        assert hist[0] == {"role": "user", "content": "Hi"}
        assert hist[1] == {"role": "assistant", "content": "Hello!"}

    def test_with_tool_results(self):
        msgs = [
            {"role": "system", "content": "Assistant."},
            {"role": "user", "content": "Read file"},
            {"role": "assistant", "content": '<tool_call name="Read">...'},
            {"role": "tool", "content": "file contents here"},
            {"role": "user", "content": "Thanks"},
        ]
        sp, hist, um = _extract_prompt_parts(msgs)
        assert sp == "Assistant."
        assert um == "Thanks"
        assert hist[2]["content"].startswith("<tool_result>")

    def test_fallback_when_no_user_message(self):
        msgs = [
            {"role": "system", "content": "Assistant."},
            {"role": "assistant", "content": "I am responding."},
        ]
        sp, hist, um = _extract_prompt_parts(msgs)
        assert um == "I am responding."
        assert hist == []

    def test_with_list_content(self):
        msgs = [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}, {"type": "image_url", "image_url": {"url": "data:img"}}]},
        ]
        sp, hist, um = _extract_prompt_parts(msgs)
        assert isinstance(um, str)
        assert "Hello" in um

    def test_no_system_prompt(self):
        msgs = [{"role": "user", "content": "Hello"}]
        sp, hist, um = _extract_prompt_parts(msgs)
        assert sp is None
        assert um == "Hello"


class TestTcId:
    def test_with_conv_uuid(self):
        tid = _tc_id("abc123")
        assert tid.startswith("call_sid:abc123_")
        assert len(tid) > len("call_sid:abc123_")

    def test_without_conv_uuid(self):
        tid = _tc_id()
        assert tid.startswith("call_")
        assert len(tid) > 5

    def test_unique_ids(self):
        ids = {_tc_id("same") for _ in range(10)}
        assert len(ids) == 10


class TestBuildTcList:
    def test_basic_items(self):
        calls = [
            {"name": "Read", "arguments": '{"path": "x"}'},
            {"name": "Write", "arguments": '{"path": "y"}'},
        ]
        result = _build_tc_list(calls, "conv123")
        assert len(result) == 2
        assert result[0]["function"]["name"] == "Read"
        assert result[1]["function"]["name"] == "Write"
        assert result[0]["id"].startswith("call_sid:conv123_")

    def test_function_format(self):
        calls = [
            {"function": {"name": "Read", "arguments": '{"path": "x"}'}},
        ]
        result = _build_tc_list(calls, "conv123")
        assert result[0]["function"]["name"] == "Read"

    def test_respects_max_10(self):
        calls = [{"name": f"Tool{i}", "arguments": "{}"} for i in range(15)]
        result = _build_tc_list(calls, "c")
        assert len(result) == 10


class TestStreamHandlerSplitChunks:
    def test_tool_call_across_two_chunks(self):
        chunks = [
            'Hello, <tool_call name="Read">',
            '<parameter name="file_path">test.txt</parameter>',
            '</tool_call> done',
        ]
        handler = StreamHandler(tool_names=["Read"])
        calls = []
        for c in chunks:
            for evt in handler.feed(c):
                if evt["type"] == "tool_calls":
                    calls.extend(evt["data"])
        for evt in handler.flush():
            if evt["type"] == "tool_calls":
                calls.extend(evt["data"])
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"

    def test_tool_call_one_char_at_a_time(self):
        full = '<tool_call name="Read"><parameter name="x">1</parameter></tool_call>'
        handler = StreamHandler(tool_names=["Read"])
        calls = []
        for ch in full:
            for evt in handler.feed(ch):
                if evt["type"] == "tool_calls":
                    calls.extend(evt["data"])
        for evt in handler.flush():
            if evt["type"] == "tool_calls":
                calls.extend(evt["data"])
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"

    def test_multiple_tool_calls_in_stream(self):
        chunks = [
            '<tool_call name="Read"><parameter name="x">1</parameter></tool_call>',
            '<tool_call name="Write"><parameter name="y">2</parameter></tool_call>',
        ]
        handler = StreamHandler(tool_names=["Read", "Write"])
        calls = []
        for c in chunks:
            for evt in handler.feed(c):
                if evt["type"] == "tool_calls":
                    calls.extend(evt["data"])
        for evt in handler.flush():
            if evt["type"] == "tool_calls":
                calls.extend(evt["data"])
        assert len(calls) == 2
        assert calls[0]["name"] == "Read"
        assert calls[1]["name"] == "Write"


class TestPromptBuilderEdgeCases:
    def test_with_history_and_tools(self):
        prompt = PromptBuilder.build(
            "Summarize the file",
            system_prompt="You are an assistant.",
            history=[
                {"role": "user", "content": "Read file /tmp/test.txt"},
                {"role": "assistant", "content": "Reading..."},
            ],
            tools_schema=[{"name": "Read", "description": "Read a file"}],
        )
        assert "[System]:" in prompt
        assert "[User]:" in prompt
        assert "[Assistant]:" in prompt
        assert "[Available Tool]: Read" in prompt
        assert "Summarize the file" in prompt
        assert "Read file /tmp/test.txt" in prompt

    def test_empty_system_and_no_tools(self):
        prompt = PromptBuilder.build("Hello")
        assert "[User]:\nHello" in prompt

    def test_multiple_tools_formatted(self):
        tools = [
            {"name": "Read", "description": "Read files"},
            {"name": "Write", "description": "Write files"},
            {"name": "Delete", "description": "Delete files"},
        ]
        prompt = PromptBuilder.build(
            "Work",
            system_prompt="Helper",
            tools_schema=tools,
        )
        assert "[Available Tool]: Read() - Read files" in prompt
        assert "[Available Tool]: Write() - Write files" in prompt
        assert "[Available Tool]: Delete() - Delete files" in prompt


class TestInputParserEdgeCases:
    def test_parse_with_tool_choice_filter(self):
        raw = {
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [
                {"function": {"name": "Read"}},
                {"function": {"name": "Write"}},
            ],
            "tool_choice": {"type": "function", "function": {"name": "Read"}},
            "model": "deepseek-chat",
        }
        parsed = InputParser.parse(raw)
        assert parsed.tool_choice is not None

    def test_parse_no_tools(self):
        raw = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "deepseek-chat",
        }
        parsed = InputParser.parse(raw)
        assert parsed.tools is None
        assert not parsed.has_tools_in_system_prompt
        assert not parsed.is_resume


class TestRepairTier3EdgeCases:
    """repair_tier3 — najbardziej zagrożone krawędzie."""

    def test_bare_tool_call_no_params(self):
        """<tool_call name="X"> bez żadnych parametrów."""
        result = repair_tier3('<tool_call name="Read">', ["Read"])
        assert result is not None
        assert result.strip().endswith("</tool_call>")

    def test_already_complete_returns_none(self):
        """Już zamknięty tool_call → None (nic do naprawy)."""
        result = repair_tier3(
            '<tool_call name="Read"><parameter name="x">1</parameter></tool_call>',
            ["Read"],
        )
        assert result is None

    def test_two_unclosed_tool_calls(self):
        """Dwa tool_calls bez zamknięcia."""
        result = repair_tier3(
            '<tool_call name="Read"><parameter name="x">1</parameter>'
            '<tool_call name="Write"><parameter name="y">2</parameter>',
            ["Read", "Write"],
        )
        assert result is not None
        assert result.count("</tool_call>") == 2

    def test_unclosed_parameters(self):
        """Parametry bez </parameter>."""
        result = repair_tier3(
            '<tool_call name="Read"><parameter name="x">1</parameter>'
            '<parameter name="y">2',
            ["Read"],
        )
        assert result is not None
        assert "</parameter>" in result
        assert result.strip().endswith("</tool_call>")

    def test_no_tool_tags_returns_none(self):
        """Zwykły tekst bez tagów → None."""
        result = repair_tier3("Hello world", [])
        assert result is None

    def test_empty_text_returns_none(self):
        """Pusty tekst → None."""
        result = repair_tier3("", ["Read"])
        assert result is None
        result = repair_tier3("   ", ["Read"])
        assert result is None

    def test_bare_partial_no_tool_names(self):
        """Bare partial ale tool_names=None."""
        result = repair_tier3('<tool_call name="Read">')
        assert result is not None
        assert result.strip().endswith("</tool_call>")

    def test_multi_line_truncated(self):
        """Wieloliniowy z brakującym zamknięciem."""
        text = (
            '<tool_call name="Read">\n'
            '  <parameter name="path">/tmp/test.txt</parameter>\n'
            '  <parameter name="encoding">utf-8'
        )
        result = repair_tier3(text, ["Read"])
        assert result is not None
        assert result.count("</parameter>") == 2
        assert result.strip().endswith("</tool_call>")

    def test_irrelevant_tag_still_closed(self):
        """Tag z <tool_call> jest uważany za potencjalny fragment i zamykany."""
        result = repair_tier3("Check <tool_call> this out", [])
        # repair_tier3 celowo zamyka każdy <tool_call> — bezpieczniej niż pominąć
        assert result is not None
        assert "</tool_call>" in result

    @pytest.mark.xfail(reason="repair_tier3 nie obsługuje <invoke> — do dodania")
    def test_tool_call_with_invoke_variant(self):
        """<invoke> tag też powinien być wykryty."""
        result = repair_tier3('<invoke name="Read">test</invoke>', ["Read"])
        assert result is not None


class TestToolMgrTryParseFullChain:
    """ToolMgr.try_parse — pełny łańcuch naprawczy."""

    def test_valid_dsml_direct(self):
        """Poprawny DSML → idzie przez parse_dsml_tool_calls."""
        calls = ToolMgr.try_parse(
            '<tool_call name="Read"><parameter name="x">1</parameter></tool_call>',
            ["Read"],
        )
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"

    def test_json_format_needs_wrapper(self):
        """JSON fallback wymaga znaczników json_tool_call."""
        # Sama struktura JSON nie wystarczy — potrzebny jest wrapper
        calls = ToolMgr.try_parse(
            '{"name": "Read", "arguments": {"path": "/tmp/x"}}',
            ["Read"],
        )
        assert len(calls) == 0

    def test_json_format_with_code_fence(self):
        """JSON w code fence ```tool_call."""
        calls = ToolMgr.try_parse(
            '```tool_call\n{"name": "Read", "arguments": {"path": "/tmp/x"}}\n```',
            ["Read"],
        )
        assert len(calls) >= 1

    def test_json_format_with_tool_call_tag(self):
        """JSON w <tool_call> tag."""
        calls = ToolMgr.try_parse(
            '<tool_call>\n{"name": "Read", "arguments": {"path": "/tmp/x"}}\n</tool_call>',
            ["Read"],
        )
        assert len(calls) >= 1

    @pytest.mark.xfail(reason="repair_tier1 nie naprawia tool_call bez < bez prefiksu DSML/TOOL")
    def test_broken_xml_recovered_by_tier1(self):
        """Brakujący < przed tagiem."""
        calls = ToolMgr.try_parse(
            'tool_call name="Read"><parameter name="x">1</parameter></tool_call>',
            ["Read"],
        )
        assert len(calls) >= 1

    def test_truncated_recovered_by_tier3(self):
        """Fragment bez </tool_call>."""
        calls = ToolMgr.try_parse(
            '<tool_call name="Read"><parameter name="x">1</parameter>',
            ["Read"],
        )
        assert len(calls) >= 1
        assert calls[0]["name"] == "Read"

    def test_garbage_returns_empty(self):
        """Totalny śmieć → pusta lista."""
        calls = ToolMgr.try_parse("This is just random text", [])
        assert calls == []


class TestPromptBuilderFormatSchemas:
    """_format_tool_schemas — różne formaty tool schemas."""

    def test_with_function_wrapper(self):
        """Tool w formacie function wrapper."""
        tools = [
            {"function": {"name": "Read", "description": "Read files"}},
        ]
        prompt = PromptBuilder.build(
            "Hello",
            system_prompt="Assistant",
            tools_schema=tools,
        )
        assert "[Available Tool]: Read" in prompt

    def test_no_description(self):
        """Tool bez opisu."""
        tools = [{"name": "Read"}]
        prompt = PromptBuilder.build(
            "Hello",
            system_prompt="Assistant",
            tools_schema=tools,
        )
        assert "[Available Tool]: Read" in prompt

    def test_multiple_tools_without_description(self):
        """Wiele narzędzi, mieszane z/bez opisu."""
        tools = [
            {"name": "A", "description": "Desc A"},
            {"name": "B"},
            {"function": {"name": "C", "description": "Desc C"}},
        ]
        prompt = PromptBuilder.build(
            "Hello",
            system_prompt="Assistant",
            tools_schema=tools,
        )
        assert "[Available Tool]: A() - Desc A" in prompt
        assert "[Available Tool]: B()" in prompt
        assert "[Available Tool]: C() - Desc C" in prompt

    def test_injection_only_when_tools_and_no_dedup(self):
        """Instrukcja tool call dodana tylko gdy narzędzia i brak dedupu."""
        prompt = PromptBuilder.build(
            "Hello",
            system_prompt="You are helpful.",
            tools_schema=[{"name": "Read", "description": "Read"}],
        )
        assert "[Available Tool]: Read" in prompt

    def test_no_injection_without_tools(self):
        """Bez narzędzi → brak instrukcji."""
        prompt = PromptBuilder.build(
            "Hello",
            system_prompt="You are helpful.",
        )
        assert "[Available Tool]:" not in prompt


class TestInputParserVisionAndModel:
    """InputParser — vision i model_type."""

    def test_vision_model(self):
        raw = {
            "messages": [{"role": "user", "content": "What is this?"}],
            "model": "deepseek-vision",
        }
        parsed = InputParser.parse(raw)
        assert parsed.is_vision
        assert parsed.model_type == "default"

    def test_expert_model(self):
        raw = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "deepseek-v4-pro",
        }
        parsed = InputParser.parse(raw)
        assert parsed.model_type == "expert"

    def test_default_model(self):
        raw = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "deepseek-chat",
        }
        parsed = InputParser.parse(raw)
        assert parsed.model_type == "default"

    def test_unknown_model_defaults(self):
        raw = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "gpt-4",
        }
        parsed = InputParser.parse(raw)
        assert parsed.model_type == "default"

    def test_vision_with_state_is_resumable(self):
        """Vision też może mieć resume jeśli state ma parent_id."""
        raw = {
            "messages": [{"role": "user", "content": "What is this?"}],
            "model": "deepseek-vision",
        }
        parsed = InputParser.parse(raw, state={"parent_id": "x", "chat_id": "y", "account": 0})
        # InputParser nie blokuje resume dla vision — decyzja należy do ProxyService
        assert parsed.is_resume


class TestStreamHandlerFlushCapture:
    """StreamHandler.flush — capture buffer + Tier 3."""

    def test_flush_completes_partial_tool_call(self):
        """Flush odzyskuje tool_call przez Tier 3."""
        handler = StreamHandler(tool_names=["Read"])
        handler.feed('<tool_call name="Read"><parameter name="x">1</parameter>')

        # Brak </tool_call> → nie ma eventu podczas feed
        events = handler.flush()
        tool_calls = [e["data"] for e in events if e["type"] == "tool_calls"]
        assert len(tool_calls) >= 1
        assert tool_calls[0][0]["name"] == "Read"

    def test_flush_with_text_after_partial(self):
        """Częściowy tool_call + tekst po flush."""
        handler = StreamHandler(tool_names=["Read"])
        handler.feed("Some text ")
        handler.feed('<tool_call name="Read"><parameter name="x">1</parameter>')

        events = handler.flush()
        tool_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tool_events) >= 1
