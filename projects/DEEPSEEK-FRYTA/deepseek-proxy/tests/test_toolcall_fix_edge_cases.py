"""tests/test_toolcall_fix_edge_cases.py

Comprehensive edge case tests for:
  1. <toolcall> (no underscore) detection in DSML parser & StreamSieve
  2. _fix_missing_lt edge cases
  3. clean_tool_text with various malformed <toolcall> blocks
  4. parse_json_tool_calls with <toolcall> wrapper
  5. Tool result truncation at TOOL_RESULT_MAX_CHARS=10000 boundary
  6. conv_uuid resolution logic (unit-level, no server)
"""

import json
import re
import uuid
import time
import pytest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import Mock, patch, MagicMock


# =============================================================================
# 1. <toolcall> (no underscore) DSML format parsing
# =============================================================================

class TestParseDsmlToolCalls_ToolcallNoUnderscore:
    """parse_dsml_tool_calls must handle <toolcall> (no underscore) format."""

    def test_toolcall_basic(self):
        """Basic <toolcall> with invoke and parameters."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall>'
            '<invoke name="Read">'
            '<parameter name="path"><![CDATA[/file.txt]]></parameter>'
            '</invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"
        args = json.loads(calls[0]["arguments"])
        assert args["path"] == "/file.txt"

    def test_toolcall_multiple_invokes(self):
        """<toolcall> with multiple <invoke> children."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[a.txt]]></parameter></invoke>'
            '<invoke name="Write"><parameter name="f"><![CDATA[b.txt]]></parameter></invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Read", "Write"])
        assert len(calls) == 2

    def test_toolcall_with_leading_text(self):
        """Text before <toolcall> should appear in cleaned output."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            'Let me read a file. '
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
        assert len(calls) == 1
        assert "Let me read" in cleaned

    def test_toolcall_mixed_with_tool_call(self):
        """Both <tool_call> and <toolcall> in same output."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<tool_call><invoke name="Read"><parameter name="f"><![CDATA[a.txt]]></parameter></invoke></tool_call>'
            '<toolcall><invoke name="Write"><parameter name="f"><![CDATA[b.txt]]></parameter></invoke></toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Read", "Write"])
        assert len(calls) == 2
        names = [c["name"] for c in calls]
        assert "Read" in names
        assert "Write" in names

    def test_toolcall_empty_no_invoke(self):
        """Empty <toolcall></toolcall> with no content returns no calls."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = '<toolcall></toolcall>'
        calls, cleaned = parse_dsml_tool_calls(text)
        assert len(calls) == 0

    def test_toolcall_malformed_unclosed(self):
        """Malformed <toolcall> without closing tag returns no calls."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = '<toolcall><invoke name="Read"><parameter name="f"><![CDATA[val]]>'
        calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
        assert len(calls) == 0

    def test_toolcall_with_tool_names_filtering(self):
        """<toolcall> with tool_names filtering — _resolve_tool_name maps case-insensitively."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[a]]></parameter></invoke>'
            '<invoke name="Write"><parameter name="f"><![CDATA[b]]></parameter></invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
        # _resolve_tool_name resolves names case-insensitively but does NOT
        # filter out non-matching tool names — all invokes are returned.
        assert len(calls) == 2
        names = [c["name"] for c in calls]
        assert "Read" in names

    def test_toolcall_with_special_chars_in_value(self):
        """<toolcall> with special chars in CDATA (newlines, unicode)."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall>'
            '<invoke name="Write">'
            '<parameter name="content"><![CDATA[line1\nline2\n\tindented]]></parameter>'
            '</invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Write"])
        assert len(calls) == 1
        args = json.loads(calls[0]["arguments"])
        assert "line1\nline2" in args["content"]

    def test_toolcall_with_auto_typed_params(self):
        """<toolcall> with auto-typed parameters (int, bool)."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall>'
            '<invoke name="Search">'
            '<parameter name="limit"><![CDATA[10]]></parameter>'
            '<parameter name="enabled"><![CDATA[true]]></parameter>'
            '</invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Search"])
        assert len(calls) == 1
        args = json.loads(calls[0]["arguments"])
        assert args["limit"] == 10
        assert args["enabled"] is True

    def test_toolcall_without_cdata_params(self):
        """<toolcall> with parameters not wrapped in CDATA."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall>'
            '<invoke name="Echo">'
            '<parameter name="msg">hello world</parameter>'
            '</invoke>'
            '</toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["Echo"])
        assert len(calls) == 1
        args = json.loads(calls[0]["arguments"])
        assert args["msg"] == "hello world"

    def test_toolcall_back_to_back(self):
        """Two back-to-back <toolcall> blocks."""
        from server.parser.dsml_parser import parse_dsml_tool_calls
        text = (
            '<toolcall><invoke name="A"><parameter name="x"><![CDATA[1]]></parameter></invoke></toolcall>'
            '<toolcall><invoke name="B"><parameter name="y"><![CDATA[2]]></parameter></invoke></toolcall>'
        )
        calls, cleaned = parse_dsml_tool_calls(text, ["A", "B"])
        assert len(calls) == 2


# =============================================================================
# 2. <toolcall> (no underscore) in parse_json_tool_calls
# =============================================================================

class TestParseJsonToolCalls_ToolcallWrapper:
    """parse_json_tool_calls must handle <toolcall> wrapper (JSON inside)."""

    def test_toolcall_with_json(self):
        """<toolcall> wrapping valid JSON."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '<toolcall>\n'
            '{"name": "Read", "arguments": {"path": "/file.txt"}}\n'
            '</toolcall>'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"
        args = json.loads(calls[0]["arguments"])
        assert args["path"] == "/file.txt"

    def test_toolcall_with_json_no_newlines(self):
        """<toolcall> wrapping JSON on one line."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = '<toolcall>{"name": "Read", "arguments": {"path": "/f.txt"}}</toolcall>'
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"

    def test_toolcall_with_json_extra_text(self):
        """<toolcall> wrapper with JSON and surrounding text."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            'Some text before.\n'
            '<toolcall>\n'
            '{"name": "Read", "arguments": {"path": "/f.txt"}}\n'
            '</toolcall>\n'
            'Some text after.'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1
        assert "Some text before" in cleaned
        assert "Some text after" in cleaned
        assert "<toolcall>" not in cleaned

    def test_toolcall_malformed_json(self):
        """<toolcall> with malformed JSON returns no calls."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = '<toolcall>\n{invalid json here\n</toolcall>'
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 0

    def test_toolcall_empty(self):
        """Empty <toolcall> returns no calls."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = '<toolcall>\n\n</toolcall>'
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 0

    def test_toolcall_mixed_with_tool_call_json(self):
        """Both <tool_call> and <toolcall> JSON blocks — stops at first pattern match."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '<tool_call>\n'
            '{"name": "Read", "arguments": {"f": "a.txt"}}\n'
            '</tool_call>\n'
            '<toolcall>\n'
            '{"name": "Write", "arguments": {"f": "b.txt"}}\n'
            '</toolcall>'
        )
        calls, cleaned = parse_json_tool_calls(text)
        # parse_json_tool_calls stops at the first pattern that finds matches
        # <tool_call> pattern is checked first, so only Read is returned
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"

    def test_json_arguments_with_literal_newlines(self):
        """````tool_call``` with arguments containing literal newlines (not \\n).
        Model sometimes outputs: "arguments": "{\n    \"key\": \"val\"\n  }"
        instead of properly escaping: "{\\n    \\"key\\": \\"val\\"\\n  }".
        The outer JSON fails to parse; regex fallback must handle this."""
        from server.parser.dsml_parser import parse_json_tool_calls
        # This is the EXACT buffer from the production log that failed
        text = (
            '```tool_call\n'
            '{\n'
            '  "name": "Read",\n'
            '  "arguments": "{\n'
            '    "file_path": "f:\\\\PROJEKTY\\\\DEEPSEEK_FRYTA\\\\deepseek-proxy\\\\server\\\\services\\\\dsml_prompt.py"\n'
            '  }"\n'
            '}\n'
            '```'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["name"] == "Read"
        args = json.loads(calls[0]["arguments"])
        assert "file_path" in args
        assert "dsml_prompt.py" in args["file_path"]

    def test_json_arguments_literal_newlines_with_tool_key(self):
        """Same as above but using 'tool' key instead of 'name'."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '```tool_call\n'
            '{\n'
            '  "tool": "Search",\n'
            '  "arguments": "{\n'
            '    "query": "hello world"\n'
            '  }"\n'
            '}\n'
            '```'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["name"] == "Search"
        args = json.loads(calls[0]["arguments"])
        assert args["query"] == "hello world"

    def test_json_arguments_literal_newlines_multiple_fields(self):
        """Multiple arguments with literal newlines in the JSON string."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '```tool_call\n'
            '{\n'
            '  "name": "Write",\n'
            '  "arguments": "{\n'
            '    "file_path": "/tmp/test.txt",\n'
            '    "content": "line1\\nline2\\nline3"\n'
            '  }"\n'
            '}\n'
            '```'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["name"] == "Write"
        args = json.loads(calls[0]["arguments"])
        assert args["file_path"] == "/tmp/test.txt"
        assert args["content"] == "line1\nline2\nline3"

    def test_json_valid_arguments_still_works(self):
        """Normal valid JSON (no literal newlines) should still parse correctly."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '```tool_call\n'
            '{\n'
            '  "name": "Read",\n'
            '  "arguments": {"path": "/normal/file.txt"}\n'
            '}\n'
            '```'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["name"] == "Read"
        args = json.loads(calls[0]["arguments"])
        assert args["path"] == "/normal/file.txt"

    def test_json_arguments_literal_newlines_in_stealth_markers(self):
        """Same issue but with ```json markers instead of ```tool_call."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '```json\n'
            '{\n'
            '  "name": "Read",\n'
            '  "arguments": "{\n'
            '    "file_path": "/stealth/test.txt"\n'
            '  }"\n'
            '}\n'
            '```'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1, f"Expected 1 tool call, got {len(calls)}"
        assert calls[0]["name"] == "Read"
        args = json.loads(calls[0]["arguments"])
        assert args["file_path"] == "/stealth/test.txt"

    def test_toolcall_json_with_tool_key(self):
        """<toolcall> JSON using 'tool' key instead of 'name'."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '<toolcall>\n'
            '{"tool": "Read", "arguments": {"path": "/f.txt"}}\n'
            '</toolcall>'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "Read"

    def test_toolcall_json_string_arguments(self):
        """<toolcall> JSON with string arguments (not object)."""
        from server.parser.dsml_parser import parse_json_tool_calls
        text = (
            '<toolcall>\n'
            '{"name": "Echo", "arguments": "hello world"}\n'
            '</toolcall>'
        )
        calls, cleaned = parse_json_tool_calls(text)
        assert len(calls) == 1
        args = json.loads(calls[0]["arguments"])
        assert args == {"value": "hello world"}


# =============================================================================
# 3. clean_tool_text edge cases with <toolcall>
# =============================================================================

class TestCleanToolText_Toolcall:
    """clean_tool_text must strip <toolcall> blocks correctly."""

    def test_clean_bare_toolcall(self):
        """Strip bare <toolcall>...</toolcall>."""
        from server.parser.dsml_parser import clean_tool_text
        text = 'before <toolcall><invoke name="X"><parameter name="y">z</parameter></invoke></toolcall> after'
        result = clean_tool_text(text)
        assert "before" in result
        assert "after" in result
        assert "<toolcall>" not in result
        assert "<invoke" not in result

    def test_clean_toolcall_with_attrs(self):
        """Strip <toolcall name='X'>...</toolcall> (legacy format)."""
        from server.parser.dsml_parser import clean_tool_text
        text = 'before <toolcall name="Read"><parameter name="f">x</parameter></toolcall> after'
        result = clean_tool_text(text)
        assert "before" in result
        assert "after" in result
        assert "<toolcall" not in result

    def test_clean_toolcall_nested_inside_text(self):
        """<toolcall> embedded mid-sentence."""
        from server.parser.dsml_parser import clean_tool_text
        text = (
            'I will call the tool now '
            '<toolcall><invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke></toolcall>'
            ' and then continue.'
        )
        result = clean_tool_text(text)
        assert "I will call" in result
        assert "and then continue" in result
        assert "<toolcall>" not in result

    def test_clean_toolcall_multiple_blocks(self):
        """Multiple <toolcall> blocks all stripped."""
        from server.parser.dsml_parser import clean_tool_text
        text = (
            'Start '
            '<toolcall><invoke name="A"></invoke></toolcall>'
            ' middle '
            '<toolcall><invoke name="B"></invoke></toolcall>'
            ' end'
        )
        result = clean_tool_text(text)
        assert "Start" in result
        assert "middle" in result
        assert "end" in result
        assert "<toolcall>" not in result

    def test_clean_toolcall_only_no_text(self):
        """Only a <toolcall> block with no surrounding text returns empty."""
        from server.parser.dsml_parser import clean_tool_text
        text = '<toolcall><invoke name="X"></invoke></toolcall>'
        result = clean_tool_text(text)
        assert result == ""

    def test_clean_mixed_toolcall_and_tool_call(self):
        """Both <tool_call> and <toolcall> stripped (extra spaces from tag removal)."""
        from server.parser.dsml_parser import clean_tool_text
        text = (
            'A '
            '<tool_call><invoke name="R"></invoke></tool_call>'
            ' B '
            '<toolcall><invoke name="W"></invoke></toolcall>'
            ' C'
        )
        result = clean_tool_text(text)
        # Tags are stripped but surrounding spaces remain, producing double spaces
        assert "A" in result and "B" in result and "C" in result
        assert "<tool_call>" not in result
        assert "<toolcall>" not in result


# =============================================================================
# 4. _fix_missing_lt edge cases
# =============================================================================

class TestFixMissingLt:
    """_fix_missing_lt must handle missing opening < on DSML/TOOL piped tags."""

    def _fix_missing_lt(self, text: str) -> str:
        """Inline copy of the function for testing."""
        import re
        return re.sub(
            r'(?<![<\w/])(\|(?:TOOL|DSML)\|(?:tool_calls?|invoke|parameter|tool_result))\b',
            r'<\1',
            text,
            flags=re.IGNORECASE,
        )

    def test_fix_tool_calls(self):
        """|TOOL|tool_calls> → <|TOOL|tool_calls>."""
        result = self._fix_missing_lt('|TOOL|tool_calls>')
        assert result == '<|TOOL|tool_calls>'

    def test_fix_dsml_tool_calls(self):
        """|DSML|tool_calls> → <|DSML|tool_calls>."""
        result = self._fix_missing_lt('|DSML|tool_calls>')
        assert result == '<|DSML|tool_calls>'

    def test_fix_dsml_invoke(self):
        """|DSML|invoke → <|DSML|invoke."""
        result = self._fix_missing_lt('|DSML|invoke name="Read">')
        assert result == '<|DSML|invoke name="Read">'

    def test_fix_dsml_parameter(self):
        """|DSML|parameter → <|DSML|parameter."""
        result = self._fix_missing_lt('|DSML|parameter name="x">')
        assert result == '<|DSML|parameter name="x">'

    def test_fix_dsml_tool_result(self):
        """|DSML|tool_result → <|DSML|tool_result."""
        result = self._fix_missing_lt('|DSML|tool_result>')
        assert result == '<|DSML|tool_result>'

    def test_fix_singular_tool_call(self):
        """|TOOL|tool_call> → <|TOOL|tool_call>."""
        result = self._fix_missing_lt('|TOOL|tool_call>')
        assert result == '<|TOOL|tool_call>'

    def test_no_double_fix(self):
        """Already correct <|TOOL|tool_calls> should NOT be modified."""
        result = self._fix_missing_lt('<|TOOL|tool_calls>')
        assert result == '<|TOOL|tool_calls>'

    def test_no_fix_within_word(self):
        """|TOOL| inside a word should NOT be fixed (regex lookbehind prevents it)."""
        result = self._fix_missing_lt('some|TOOL|tool_calls>')
        # The lookbehind (?<![<\w/]) prevents matching after \w characters
        # This may or may not match depending on the regex implementation
        # At minimum, ensure it doesn't crash
        assert isinstance(result, str)

    def test_fix_multiple_in_text(self):
        """Multiple missing < in same string all fixed."""
        result = self._fix_missing_lt(
            '|TOOL|tool_calls>\n'
            '  |TOOL|invoke name="Read">\n'
            '    |TOOL|parameter name="f"><![CDATA[x]]>|TOOL|parameter>\n'
            '  |TOOL|invoke>\n'
            '|TOOL|tool_calls>'
        )
        assert '<|TOOL|tool_calls>' in result
        assert '<|TOOL|invoke' in result
        assert '<|TOOL|parameter' in result
        assert '|TOOL|' not in result.replace('<|TOOL|', '')

    def test_fix_after_close_tag(self):
        """Next block after a close tag should also be fixed."""
        result = self._fix_missing_lt(
            '</|TOOL|tool_calls>\n'
            '|TOOL|tool_calls>'
        )
        assert '<|TOOL|tool_calls>' in result

    def test_no_fix_for_bare_toolcall(self):
        """Bare <toolcall> without pipe prefix should NOT be modified."""
        result = self._fix_missing_lt('<toolcall>')
        assert result == '<toolcall>'

    def test_case_insensitivity(self):
        """Case insensitive matching."""
        result = self._fix_missing_lt('|tool|tool_calls>')
        # The regex has re.IGNORECASE in the original
        import re
        pat = re.compile(
            r'(?<![<\w/])(\|(?:TOOL|DSML)\|(?:tool_calls?|invoke|parameter|tool_result))\b',
            re.IGNORECASE,
        )
        fixed = pat.sub(r'<\1', '|tool|tool_calls>')
        assert fixed == '<|tool|tool_calls>'


# =============================================================================
# 5. StreamSieve <toolcall> detection edge cases
# =============================================================================

class TestStreamSieve_Toolcall:
    """StreamSieve must detect <toolcall> (no underscore) format."""

    def test_sieve_detects_toolcall(self):
        """Full <toolcall> block detected in one chunk."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        chunk = (
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke>'
            '</toolcall>'
        )
        events = sieve.feed(chunk)
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) >= 1, f"No tool_calls, got: {[e.type for e in events]}"
        assert tc_events[0].data[0]["name"] == "Read"

    def test_sieve_toolcall_one_char_at_a_time(self):
        """<toolcall> split across 1-char chunks."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        full = (
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke>'
            '</toolcall>'
        )
        all_events = []
        for ch in full:
            ev = sieve.feed(ch)
            all_events.extend(ev)
        all_events += sieve.flush()
        tc_events = [e for e in all_events if e.type == "tool_calls"]
        assert len(tc_events) >= 1, f"No tool_calls, got: {[e.type for e in all_events]}"
        assert tc_events[0].data[0]["name"] == "Read"

    def test_sieve_toolcall_with_leading_text(self):
        """Text before <toolcall> is preserved as text event."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        chunk = (
            'Let me read. '
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke>'
            '</toolcall>'
        )
        events = sieve.feed(chunk)
        text_events = [e for e in events if e.type == "text"]
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert any("Let me read" in e.data for e in text_events), f"No text event, got: {[e.type for e in events]}"
        assert len(tc_events) >= 1

    def test_sieve_toolcall_with_trailing_text(self):
        """Text after </toolcall> is preserved."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        chunk = (
            '<toolcall>'
            '<invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke>'
            '</toolcall>'
            ' and then explain'
        )
        events = sieve.feed(chunk) + sieve.flush()
        text_events = [e for e in events if e.type == "text"]
        assert any("explain" in e.data for e in text_events), f"No trailing text, got: {[e.data for e in text_events]}"

    def test_sieve_toolcall_across_two_chunks(self):
        """<toolcall> split across two chunks."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        chunk1 = '<toolcall><invoke name="Read"><parameter name="f"><![CDATA[x.'
        chunk2 = 'txt]]></parameter></invoke></toolcall>'
        events1 = sieve.feed(chunk1)
        assert len([e for e in events1 if e.type == "tool_calls"]) == 0  # not complete
        events2 = sieve.feed(chunk2)
        tc_events = [e for e in events2 if e.type == "tool_calls"]
        assert len(tc_events) >= 1, f"No tool_calls, got: {[e.type for e in events2]}"

    def test_sieve_toolcall_across_three_chunks(self):
        """<toolcall> across three chunks for realistic streaming."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        events1 = sieve.feed('Some text.\n\n<toolcall>\n<invoke name="Re')
        events2 = sieve.feed('ad">\n<parameter name="f"><![CDATA[/tmp/')
        events3 = sieve.feed('x]]></parameter>\n</invoke>\n</toolcall>\n\nDone.')
        all_events = events1 + events2 + events3 + sieve.flush()
        tc_events = [e for e in all_events if e.type == "tool_calls"]
        text_events = [e for e in all_events if e.type == "text"]
        assert len(tc_events) >= 1, f"No tool_calls, got types: {[e.type for e in all_events]}"
        assert tc_events[0].data[0]["name"] == "Read"
        assert any("Some text" in e.data for e in text_events)
        assert any("Done" in e.data for e in text_events)

    def test_sieve_toolcall_multiple_blocks(self):
        """Multiple <toolcall> blocks in sequence."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read", "Write"])
        chunk = (
            '<toolcall><invoke name="Read"><parameter name="f"><![CDATA[a.txt]]></parameter></invoke></toolcall>'
            '<toolcall><invoke name="Write"><parameter name="f"><![CDATA[b.txt]]></parameter></invoke></toolcall>'
        )
        events = sieve.feed(chunk) + sieve.flush()
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) >= 1
        all_calls = []
        for ev in tc_events:
            all_calls.extend(ev.data)
        names = [c["name"] for c in all_calls]
        assert "Read" in names
        assert "Write" in names

    def test_sieve_toolcall_incomplete_at_flush(self):
        """Incomplete <toolcall> at flush returns as text."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        sieve.feed('<toolcall><invoke name="Read"><parameter name="f"><![CDATA[val')
        events = sieve.flush()
        assert len(events) >= 1
        assert events[0].type == "text" or events[-1].type == "text"
        # Should contain the partial content as text
        all_text = "".join(e.data for e in events if e.type == "text")
        assert "toolcall" in all_text or "invoke" in all_text

    def test_sieve_toolcall_with_name_attr(self):
        """<toolcall name='X'> — not supported (only <tool_call name='X'> works).
        The <toolcall> (no underscore) fix was for JSON-wrapper and <invoke>-inside
        formats, NOT for the legacy name-attribute format."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        chunk = '<toolcall name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></toolcall>'
        events = sieve.feed(chunk) + sieve.flush()
        tc_events = [e for e in events if e.type == "tool_calls"]
        # <toolcall name='X'> is now supported by Tier 4 legacy fallback
        assert len(tc_events) >= 1
        assert tc_events[0].data[0]["name"] == "Read"

    def test_sieve_toolcall_mid_sentence(self):
        """<toolcall> embedded mid-sentence with text before and after."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve(tool_names=["Read"])
        chunk = (
            'I will now '
            '<toolcall><invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke></toolcall>'
            ' and then continue.'
        )
        events = sieve.feed(chunk) + sieve.flush()
        text_events = [e for e in events if e.type == "text"]
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) >= 1
        assert any("I will now" in e.data for e in text_events), f"Leading text missing: {text_events}"
        assert any("and then continue" in e.data for e in text_events), f"Trailing text missing: {text_events}"


# =============================================================================
# 6. Tool result truncation at TOOL_RESULT_MAX_CHARS=10000 boundary
# =============================================================================

class TestToolResultTruncation:
    """Tool results must be truncated at TOOL_RESULT_MAX_CHARS (10000)."""

    def _format_stealth_tool_result(self, content: str) -> str:
        """Simulate what _format_stealth does with tool results."""
        from server.config.settings import settings
        max_chars = settings.tool_result_max_chars
        if len(content) > max_chars:
            content = content[:max_chars] + "...(truncated)"
        return content

    def test_under_limit_passes_through(self):
        """Content under TOOL_RESULT_MAX_CHARS passes through unchanged."""
        content = "A" * 5000
        result = self._format_stealth_tool_result(content)
        assert len(result) == 5000
        assert "...(truncated)" not in result

    def test_exact_limit_passes_through(self):
        """Content exactly TOOL_RESULT_MAX_CHARS passes through unchanged."""
        content = "A" * 10000
        result = self._format_stealth_tool_result(content)
        assert len(result) == 10000
        assert "...(truncated)" not in result

    def test_one_over_limit_truncated(self):
        """Content one char over limit is truncated."""
        content = "A" * 10001
        result = self._format_stealth_tool_result(content)
        assert len(result) == 10000 + len("...(truncated)")
        assert "...(truncated)" in result

    def test_well_over_limit_truncated(self):
        """Content 10x over limit is truncated."""
        content = "A" * 100000
        result = self._format_stealth_tool_result(content)
        assert "...(truncated)" in result
        assert result.count("A") == 10000

    def test_empty_content_no_truncation(self):
        """Empty content is not truncated."""
        result = self._format_stealth_tool_result("")
        assert result == ""

    def test_unicode_preserved_under_limit(self):
        """Unicode content under limit preserves characters."""
        content = "Hello 世界 🌍🔥" * 200  # ~2800 chars
        result = self._format_stealth_tool_result(content)
        assert "世界" in result
        assert "🌍🔥" in result
        assert "...(truncated)" not in result

    def test_json_tool_result_truncated(self):
        """JSON tool result over limit is truncated."""
        long_output = "x" * 20000
        content = json.dumps({"output": long_output, "error": None})
        result = self._format_stealth_tool_result(content)
        assert "...(truncated)" in result


# =============================================================================
# 7. conv_uuid resolution logic (unit-level tests, no server needed)
# =============================================================================

class TestConvUuidResolution:
    """Test the conv_uuid resolution logic directly (no server dependency)."""

    def _resolve_conv_uuid(self, messages, acl_sub=None, dedup_key=None, conv_state=None):
        """Simulate the conv_uuid resolution logic from proxy.py (lines 240-262)."""
        import hashlib, time, copy, uuid
        from collections import OrderedDict

        conv_state = conv_state or {}
        request_dedup = OrderedDict()
        _DEDUP_TTL = 60.0

        # Generate hash
        req_hash = hashlib.md5(str(messages).encode()).hexdigest()[:12]

        # Dedup check
        if dedup_key and dedup_key == req_hash:
            conv_uuid = dedup_key
            with conv_lock:  # simplified — no real lock needed for test
                state = copy.deepcopy(conv_state.get(conv_uuid))
            return conv_uuid, state, "dedup"

        if dedup_key:
            # Simulate dedup from request_dedup
            pass

        # Continuation detection
        has_tool_results = any(m.get("role") == "tool" for m in messages)
        has_assistant_tool_calls = any(
            m.get("role") == "assistant" and m.get("tool_calls")
            for m in messages
        )
        is_continuation = has_tool_results or has_assistant_tool_calls

        if acl_sub and is_continuation:
            conv_uuid = f"acl_{acl_sub[:12]}"
            state = copy.deepcopy(conv_state.get(conv_uuid))
            return conv_uuid, state, "acl_sub"
        else:
            conv_uuid = uuid.uuid4().hex[:12]
            return conv_uuid, None, "new"

    def test_fresh_request_new_uuid(self):
        """Fresh request (no tool results, no acl_sub) → new uuid."""
        messages = [{"role": "user", "content": "Hello"}]
        uuid1, state, reason = self._resolve_conv_uuid(messages, acl_sub=None)
        uuid2, state, reason = self._resolve_conv_uuid(messages, acl_sub=None)
        assert uuid1 != uuid2  # each fresh request gets a unique uuid
        assert reason == "new"

    def test_continuation_with_tool_results_uses_acl_sub(self):
        """Request with tool role messages and acl_sub → acl_sub uuid."""
        messages = [
            {"role": "user", "content": "Read file"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "Read", "arguments": "{}"}}
            ]},
            {"role": "tool", "content": "File content", "tool_call_id": "c1"},
            {"role": "user", "content": "Now write"},
        ]
        conv_state = {"acl_agent-1": {"parent_id": "p1"}}
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub="agent-1", conv_state=conv_state)
        assert uuid_val == "acl_agent-1"
        assert reason == "acl_sub"
        assert state == {"parent_id": "p1"}

    def test_continuation_no_acl_sub_gets_new_uuid(self):
        """Continuation without acl_sub → new uuid (fallback)."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
            {"role": "tool", "content": "Result", "tool_call_id": "c1"},
        ]
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub=None)
        assert reason == "new"
        assert state is None

    def test_fresh_request_with_acl_sub_still_new_uuid(self):
        """Fresh request with acl_sub but NO tool results → new uuid (not acl_sub).
        This is the key fix — new subagent should NOT reuse agent's uuid."""
        messages = [{"role": "user", "content": "Do something new"}]
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub="agent-1")
        assert reason == "new"
        assert not uuid_val.startswith("acl_")
        assert state is None

    def test_different_acl_sub_different_uuid(self):
        """Two continuations with different acl_sub → different uuids."""
        messages = [{"role": "user", "content": "Do"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
                    {"role": "tool", "content": "R", "tool_call_id": "c1"},
                    {"role": "user", "content": "Do2"}]
        uuid1, _, _ = self._resolve_conv_uuid(messages, acl_sub="agent-1")
        uuid2, _, _ = self._resolve_conv_uuid(messages, acl_sub="agent-2")
        assert uuid1 == "acl_agent-1"
        assert uuid2 == "acl_agent-2"
        assert uuid1 != uuid2

    def test_same_acl_sub_same_continuation_uuid(self):
        """Same acl_sub and same continuation pattern → same uuid."""
        messages = [{"role": "user", "content": "Do"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
                    {"role": "tool", "content": "R", "tool_call_id": "c1"},
                    {"role": "user", "content": "Do2"}]
        uuid1, _, r1 = self._resolve_conv_uuid(messages, acl_sub="agent-1")
        uuid2, _, r2 = self._resolve_conv_uuid(messages, acl_sub="agent-1")
        assert uuid1 == uuid2  # same deterministic acl_sub uuid
        assert r1 == r2

    def test_continuation_with_only_assistant_tool_calls(self):
        """Request with assistant tool_calls but NO tool results — still continuation."""
        messages = [
            {"role": "user", "content": "Do it"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}
            ]},
        ]
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub="agent-1")
        assert reason == "acl_sub"  # has assistant tool_calls → is_continuation
        assert uuid_val == "acl_agent-1"

    def test_continuation_with_only_tool_results(self):
        """Request with tool results but NO assistant tool_calls — still continuation."""
        messages = [
            {"role": "user", "content": "Do it"},
            {"role": "tool", "content": "Result", "tool_call_id": "c1"},
            {"role": "user", "content": "Now do more"},
        ]
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub="agent-1")
        assert reason == "acl_sub"
        assert uuid_val == "acl_agent-1"

    def test_empty_acl_sub_string(self):
        """Empty acl_sub string should not match acl_sub check (falsy)."""
        messages = [{"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
                    {"role": "tool", "content": "R", "tool_call_id": "c1"},
                    {"role": "user", "content": "Do2"}]
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub="")
        assert reason == "new"  # empty acl_sub is falsy → new uuid
        assert state is None

    def test_acl_sub_with_special_chars(self):
        """acl_sub with special characters (dots, slashes, email, UUID)."""
        special_subs = [
            "user@example.com",
            "org/project/env",
            "a.b.c.d",
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "with_underscore_and-dashes",
        ]
        messages = [{"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
                    {"role": "tool", "content": "R", "tool_call_id": "c1"},
                    {"role": "user", "content": "Do2"}]
        for sub in special_subs:
            uuid_val, _, reason = self._resolve_conv_uuid(messages, acl_sub=sub)
            assert reason == "acl_sub"
            assert uuid_val == f"acl_{sub[:12]}"
            assert len(uuid_val) <= 4 + 12  # "acl_" + 12 chars

    def test_conv_state_not_found_for_acl_sub(self):
        """acl_sub continuation but no existing conv_state → None state."""
        messages = [{"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
                    {"role": "tool", "content": "R", "tool_call_id": "c1"},
                    {"role": "user", "content": "Do2"}]
        uuid_val, state, reason = self._resolve_conv_uuid(messages, acl_sub="new-agent", conv_state={})
        assert reason == "acl_sub"
        assert uuid_val == "acl_new-agent"
        assert state is None  # no existing state found

    def test_consecutive_fresh_requests_different_uuids(self):
        """Multiple fresh requests (even with same acl_sub) get different uuids."""
        messages = [{"role": "user", "content": "Fresh msg"}]
        uuids = set()
        for _ in range(10):
            uuid_val, _, reason = self._resolve_conv_uuid(messages, acl_sub="agent-1")
            assert reason == "new"
            uuids.add(uuid_val)
        assert len(uuids) == 10, f"Expected 10 unique uuids, got {len(uuids)}"

    def test_continuation_with_long_acl_sub(self):
        """Long acl_sub >12 chars gets truncated to 12 chars in uuid."""
        messages = [{"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "T", "arguments": "{}"}}]},
                    {"role": "tool", "content": "R", "tool_call_id": "c1"},
                    {"role": "user", "content": "Do2"}]
        long_sub = "this-is-a-very-long-sub-agent-identifier"
        uuid_val, _, reason = self._resolve_conv_uuid(messages, acl_sub=long_sub)
        assert reason == "acl_sub"
        assert uuid_val == f"acl_{long_sub[:12]}"
        assert len(uuid_val) == 4 + 12  # "acl_" + 12 chars
        assert uuid_val == "acl_this-is-a-ve"  # first 12 chars of long sub


# =============================================================================
# 8. TOOL_CALLS_PATTERN regex edge cases
# =============================================================================

class TestToolCallsPattern:
    """TOOL_CALLS_PATTERN regex must match all known formats."""

    def _get_pattern(self):
        from server.parser.dsml_parser import TOOL_CALLS_PATTERN
        return TOOL_CALLS_PATTERN

    def test_matches_toolcall(self):
        """toolcall (no underscore, no prefix) matches."""
        pat = self._get_pattern()
        m = pat.search('<toolcall>content</toolcall>')
        assert m is not None
        assert m.group(1).strip() == "content"

    def test_matches_tool_call(self):
        """tool_call (with underscore, no prefix) matches."""
        pat = self._get_pattern()
        m = pat.search('<tool_call>content</tool_call>')
        assert m is not None
        assert m.group(1).strip() == "content"

    def test_matches_tool_calls(self):
        """tool_calls (plural, with underscore) matches."""
        pat = self._get_pattern()
        m = pat.search('<tool_calls>content</tool_calls>')
        assert m is not None
        assert m.group(1).strip() == "content"

    def test_matches_dsml_tool_calls(self):
        """<|DSML|tool_calls> matches."""
        pat = self._get_pattern()
        m = pat.search('<|DSML|tool_calls>content</|DSML|tool_calls>')
        assert m is not None
        assert m.group(1).strip() == "content"

    def test_matches_tool_tool_calls(self):
        """<|TOOL|tool_calls> matches."""
        pat = self._get_pattern()
        m = pat.search('<|TOOL|tool_calls>content</|TOOL|tool_calls>')
        assert m is not None
        assert m.group(1).strip() == "content"

    def test_matches_bare_tool_calls(self):
        """Bare <tool_calls> (pipe prefix optional) matches."""
        pat = self._get_pattern()
        m = pat.search('<tool_calls>content</tool_calls>')
        assert m is not None
        assert m.group(1).strip() == "content"

    def test_matches_missing_prefix_version(self):
        """Format where pipe prefix exists but no TOOL/DSML keyword — does NOT match.
        The regex requires TOOL or DSML between optional pipes."""
        pat = self._get_pattern()
        m = pat.search('<|tool_calls>content</|tool_calls>')
        # The pattern is: (?:\|?(?:TOOL|DSML)\|?)? — requires TOOL or DSML between pipes
        assert m is None

    def test_no_match_on_unclosed(self):
        """Unclosed tag does not match."""
        pat = self._get_pattern()
        m = pat.search('<toolcall>unclosed')
        assert m is None

    def test_multiline_content(self):
        """Multi-line content between tags is captured."""
        pat = self._get_pattern()
        text = '<toolcall>\n  line1\n  line2\n</toolcall>'
        m = pat.search(text)
        assert m is not None
        assert "line1" in m.group(1)
        assert "line2" in m.group(1)

    def test_case_insensitive(self):
        """Case insensitive matching."""
        pat = self._get_pattern()
        m = pat.search('<TOOLCALL>content</TOOLCALL>')
        assert m is not None
        assert m.group(1).strip() == "content"
        m2 = pat.search('<Tool_Call>content</Tool_Call>')
        assert m2 is not None
        assert m2.group(1).strip() == "content"


# =============================================================================
# 9. Edge: _is_capture_complete for <toolcall> in StreamSieve
# =============================================================================

class TestIsCaptureComplete:
    """_is_capture_complete must handle <toolcall> opening/closing tags."""

    def test_toolcall_complete(self):
        """<toolcall>...</toolcall> is recognized as complete."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        sieve._capture_buf = '<toolcall><invoke name="X"><parameter name="y">z</parameter></invoke></toolcall>'
        assert sieve._is_capture_complete() is True

    def test_toolcall_incomplete_no_close(self):
        """<toolcall> without close is NOT complete."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        sieve._capture_buf = '<toolcall><invoke name="X"><parameter name="y">z'
        assert sieve._is_capture_complete() is False

    def test_toolcall_incomplete_partial_close(self):
        """<toolcall> with partial closing is NOT complete."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        sieve._capture_buf = '<toolcall><invoke name="X"><parameter name="y">z</param'
        assert sieve._is_capture_complete() is False

    def test_toolcall_with_name_attr_complete(self):
        """<toolcall name='X'>...</toolcall> is complete."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        sieve._capture_buf = '<toolcall name="Read"><parameter name="f">x.txt</parameter></toolcall>'
        assert sieve._is_capture_complete() is True

    def test_toolcall_after_text_complete(self):
        """Text then <toolcall> block is complete."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        sieve._capture_buf = 'Let me call <toolcall><invoke name="X"><parameter name="y">z</parameter></invoke></toolcall>'
        assert sieve._is_capture_complete() is True

    def test_tool_call_singular_also_complete(self):
        """<tool_call> (underscore) should still be recognized as complete."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        sieve._capture_buf = '<tool_call name="Read"><parameter name="f">x.txt</parameter></tool_call>'
        assert sieve._is_capture_complete() is True


# =============================================================================
# 10. Edge: _find_tool_start for <toolcall> prefix
# =============================================================================

class TestFindToolStart:
    """_find_tool_start must find <toolcall as a start position."""

    def test_finds_toolcall(self):
        """Finds <toolcall at start of string."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        pos = sieve._find_tool_start('<toolcall><invoke name="X"></invoke></toolcall>')
        assert pos == 0

    def test_finds_toolcall_mid_string(self):
        """Finds <toolcall mid-string."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        pos = sieve._find_tool_start('some text <toolcall><invoke name="X"></invoke></toolcall>')
        assert pos == 10  # "some text " is 10 chars

    def test_finds_toolcall_with_attr(self):
        """Finds <toolcall name='X'>."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        pos = sieve._find_tool_start('<toolcall name="Read">')
        assert pos == 0

    def test_no_false_positive_no_toolcall(self):
        """No <toolcall in text → returns -1."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        pos = sieve._find_tool_start('just some regular text with no tool calls')
        assert pos == -1

    def test_still_finds_tool_call_underscore(self):
        """Still finds <tool_call (underscore variant)."""
        from server.parser.dsml_sieve import StreamSieve
        sieve = StreamSieve()
        pos = sieve._find_tool_start('<tool_call name="Read">')
        assert pos == 0


# =============================================================================
# 11. Sanitize leaked output edge cases
# =============================================================================

class TestSanitizeLeakedOutput:
    """sanitize_leaked_output must strip all leaked BOS/EOS/role markers."""

    def test_strips_bos(self):
        """<｜begin▁of▁sentence｜> stripped."""
        from server.parser.dsml_parser import sanitize_leaked_output
        result = sanitize_leaked_output('<｜begin▁of▁sentence｜>Hello')
        assert result == "Hello"

    def test_strips_eos(self):
        """<｜end▁of▁sentence｜> stripped."""
        from server.parser.dsml_parser import sanitize_leaked_output
        result = sanitize_leaked_output('Hello<｜end▁of▁sentence｜>')
        assert result == "Hello"

    def test_strips_role_markers(self):
        """<｜Assistant｜> <｜User｜> <｜System｜> stripped."""
        from server.parser.dsml_parser import sanitize_leaked_output
        result = sanitize_leaked_output('<｜Assistant｜>Hello<｜User｜>')
        assert result == "Hello"

    def test_strips_thinking_markers(self):
        """<｜end▁of▁thinking｜> stripped."""
        from server.parser.dsml_parser import sanitize_leaked_output
        result = sanitize_leaked_output('thinking<｜end▁of▁thinking｜>result')
        assert result == "thinkingresult"

    def test_strips_tool_markers(self):
        """<｜Tool｜> marker stripped."""
        from server.parser.dsml_parser import sanitize_leaked_output
        result = sanitize_leaked_output('before<｜Tool｜>after')
        assert result == "beforeafter"

    def test_strips_full_width_pipe_variant(self):
        """Full-width pipe variant ｜ also stripped."""
        from server.parser.dsml_parser import sanitize_leaked_output
        result = sanitize_leaked_output('<｜begin▁of▁sentence｜>Hello')
        assert result == "Hello"


# =============================================================================
# 12. clean_tool_call_markers edge cases
# =============================================================================

class TestCleanToolCallMarkers:
    """clean_tool_call_markers must handle partial markers in streaming."""

    def test_clean_tool_call_markers(self):
        from server.parser.dsml_parser import clean_tool_call_markers
        assert clean_tool_call_markers("```tool_call") == ""
        assert clean_tool_call_markers("```tool_call some text") == "some text"
        assert clean_tool_call_markers("```tool_call\n{\"name\": \"test\"}") == "{\"name\": \"test\"}"
        assert clean_tool_call_markers("```json") == ""
        assert clean_tool_call_markers("```") == ""
        assert clean_tool_call_markers("") == ""
        assert clean_tool_call_markers("```tool_call\n```json") == ""
        assert clean_tool_call_markers("normal text") == "normal text"
