"""Tests for JSON tool call parsing (CO-STAR format)."""

import json
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.parser.dsml_parser import parse_json_tool_calls, clean_tool_call_markers


class TestParseJsonToolCalls:
    def test_single_tool_call(self):
        text = 'Hello ```tool_call\n{"name": "get_weather", "arguments": {"location": "Warsaw"}}\n``` world'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "get_weather"
        args = json.loads(tc[0]["arguments"])
        assert args["location"] == "Warsaw"
        assert "Hello" in cleaned
        assert "world" in cleaned

    def test_multiple_tool_calls(self):
        text = (
            '```tool_call\n{"name": "tool_a", "arguments": {"x": 1}}\n```\n'
            '```tool_call\n{"name": "tool_b", "arguments": {"y": 2}}\n```'
        )
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 2
        assert tc[0]["name"] == "tool_a"
        assert tc[1]["name"] == "tool_b"

    def test_malformed_json_ignored(self):
        text = 'some text ```tool_call\nnot valid json\n``` more text'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 0
        assert "some text" in cleaned
        assert "more text" in cleaned

    def test_no_tool_call_markers(self):
        text = "Just a regular response without any tool calls."
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 0
        assert cleaned == text.strip()

    def test_empty_text(self):
        tc, cleaned = parse_json_tool_calls("")
        assert len(tc) == 0
        assert cleaned == ""

    def test_tool_call_with_no_arguments(self):
        text = '```tool_call\n{"name": "simple_tool", "arguments": {}}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "simple_tool"
        assert json.loads(tc[0]["arguments"]) == {}

    def test_json_fallback_format(self):
        text = '```json\n{"name": "json_tool", "arguments": {"key": "val"}}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "json_tool"

    def test_string_arguments_parsed(self):
        text = '```tool_call\n{"name": "test", "arguments": "{\\"a\\": 1}"}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        args = json.loads(tc[0]["arguments"])
        assert args["a"] == 1

    def test_tool_name_variants(self):
        """Support both 'name' and 'tool' keys."""
        text = '```tool_call\n{"tool": "alt_name", "arguments": {}}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "alt_name"

    def test_cleaned_text_has_no_code_blocks(self):
        text = 'Some text ```tool_call\n{"name": "x", "arguments": {}}\n``` more text'
        tc, cleaned = parse_json_tool_calls(text)
        assert "```" not in cleaned
        assert "Some text" in cleaned
        assert "more text" in cleaned


class TestCleanToolCallMarkers:
    def test_removes_partial_markers(self):
        assert clean_tool_call_markers("```tool_call\nsomething") == "something"
        assert clean_tool_call_markers("pre ```tool_call") == "pre"
        assert clean_tool_call_markers("text ```") == "text"
        assert clean_tool_call_markers("no markers") == "no markers"
        assert clean_tool_call_markers("") == ""
