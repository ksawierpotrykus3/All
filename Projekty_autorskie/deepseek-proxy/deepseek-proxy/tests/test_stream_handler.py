"""tests/test_stream_handler.py — StreamHandler + ToolMgr unit tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from server.core.stream_handler import StreamHandler, ToolMgr


class TestToolMgr:
    def test_tier3_recovers_broken(self):
        # Fragment missing closing tags
        broken = '<tool_call name="Bash"><parameter name="command">ls</parameter>'
        calls = ToolMgr.try_parse(broken, ["Bash", "Read"])
        assert len(calls) >= 1
        assert calls[0]["name"] == "Bash"

    def test_tier4_legacy_fallback_catches_function_call(self):
        text = '<function_call>{"name":"Read","arguments":{"file_path":"/tmp/x"}}</function_call>'
        calls = ToolMgr.try_parse(text, ["Read"])
        assert len(calls) >= 1
        assert calls[0]["name"] == "Read"

    def test_tier4_legacy_fallback_catches_tool_use_json(self):
        text = '<tool_use_json>{"tool_name":"Read","arguments":{"file_path":"/tmp/x"}}</tool_use_json>'
        calls = ToolMgr.try_parse(text, ["Read"])
        assert len(calls) >= 1
        assert calls[0]["name"] == "Read"

    # ── Tool name alias resolution ─────────────────────────────────

    def test_validate_accepts_exact_name(self):
        """Exact match passes through unchanged."""
        calls_in = [{"name": "Write", "arguments": '{"file_path":"/tmp/x"}'}]
        out = ToolMgr.validate(calls_in, ["Write", "Read"])
        assert len(out) == 1
        assert out[0]["name"] == "Write"

    def test_validate_rejects_unknown_name(self):
        """Unknown tool name (no alias) is filtered out."""
        calls_in = [{"name": "FooBar", "arguments": "{}"}]
        out = ToolMgr.validate(calls_in, ["Write", "Read"])
        assert len(out) == 0

    def test_validate_aliases_edit_to_write_simple(self):
        """'Edit' → 'Write' alias works in validate()."""
        calls_in = [
            {"name": "Edit", "arguments": '{"file_path":"/tmp/x","content":"hello"}'}
        ]
        out = ToolMgr.validate(calls_in, ["Write", "Read"])
        assert len(out) == 1
        assert out[0]["name"] == "Write"  # renamed

    def test_validate_aliases_edit_to_write_with_function(self):
        """Alias also renames the nested 'function' dict."""
        calls_in = [
            {
                "name": "Edit",
                "function": {"name": "Edit", "arguments": '{"file_path":"/tmp/x"}'},
                "arguments": '{"file_path":"/tmp/x"}',
            }
        ]
        out = ToolMgr.validate(calls_in, ["Write"])
        assert len(out) == 1
        assert out[0]["name"] == "Write"
        assert out[0]["function"]["name"] == "Write"

    def test_validate_copies_toplevel_args_into_function_dict(self):
        """Parser format {"name":"Bash","arguments":"..."} + alias → function.arguments populated."""
        calls_in = [{"name": "Bash", "arguments": '{"command":"ls"}'}]
        out = ToolMgr.validate(calls_in, ["Shell"])
        assert len(out) == 1
        assert out[0]["name"] == "Shell"
        assert out[0]["function"]["name"] == "Shell"
        assert out[0]["function"]["arguments"] == '{"command":"ls"}'

    def test_validate_preserves_existing_function_args(self):
        """If function already has arguments, don't overwrite with top-level."""
        calls_in = [
            {
                "name": "Edit",
                "function": {
                    "name": "Edit",
                    "arguments": '{"file_path":"/tmp/x","content":"hi"}',
                },
                "arguments": '{"file_path":"/tmp/x"}',
            }
        ]
        out = ToolMgr.validate(calls_in, ["Write"])
        assert len(out) == 1
        assert (
            out[0]["function"]["arguments"] == '{"file_path":"/tmp/x","content":"hi"}'
        )

    def test_validate_aliases_case_insensitive(self):
        """'edit' (lowercase) is also resolved."""
        calls_in = [{"name": "edit", "arguments": '{"file_path":"/tmp/x"}'}]
        out = ToolMgr.validate(calls_in, ["Write"])
        assert len(out) == 1
        assert out[0]["name"] == "Write"

    def test_validate_no_alias_when_canonical_missing(self):
        """If 'Write' is not in tool_names, 'Edit' is rejected (no canonical target)."""
        calls_in = [{"name": "Edit", "arguments": "{}"}]
        out = ToolMgr.validate(calls_in, ["Read"])  # Write not available
        assert len(out) == 0  # can't map Edit→Write because Write isn't allowed

    def test_validate_aliased_via_stream_handler(self):
        """End-to-end: StreamHandler with Edit tool call produces Write."""
        chunks = [
            "<tool_calls>",
            '<invoke name="Edit">',
            '<parameter name="file_path">/tmp/x</parameter>',
            '<parameter name="content">hello</parameter>',
            "</invoke>",
            "</tool_calls>",
        ]
        handler = StreamHandler(tool_names=["Write", "Read"])
        events = []
        for c in chunks:
            events.extend(handler.feed(c))
        events.extend(handler.flush())

        tool_events = [e for e in events if e.get("type") == "tool_calls"]
        assert len(tool_events) >= 1
        calls = tool_events[0]["data"]
        assert len(calls) >= 1
        assert calls[0]["name"] == "Write"  # renamed from Edit

    def test_rewrites_bare_mcp_tool_call_to_call_mcp_tool(self):
        """Bare <invoke name="git_status"> (MCP tool) is rewritten to CallMcpTool
        instead of being dropped, so the IDE can execute it."""
        chunks = [
            "<tool_calls>",
            '<invoke name="git_status">',
            '<parameter name="repo_path">F:\\PROJEKTY\\joaxx</parameter>',
            "</invoke>",
            "</tool_calls>",
        ]
        catalog = {"git_status": {"server": "user-git", "description": "Shows status"}}
        handler = StreamHandler(
            tool_names=["Shell", "Read", "CallMcpTool"], mcp_catalog=catalog
        )
        events = []
        for c in chunks:
            events.extend(handler.feed(c))
        events.extend(handler.flush())

        tool_events = [e for e in events if e.get("type") == "tool_calls"]
        assert len(tool_events) == 1
        calls = tool_events[0]["data"]
        assert len(calls) == 1
        tc = calls[0]
        assert tc["name"] == "CallMcpTool"
        assert tc["arguments"]["server"] == "user-git"
        assert tc["arguments"]["toolName"] == "git_status"
        assert tc["arguments"]["arguments"]["repo_path"] == "F:\\PROJEKTY\\joaxx"


class TestStreamHandler:
    def test_detects_tool_calls(self):
        chunks = [
            "Hello",
            '<tool_call name="Read">',
            '<parameter name="file_path">/tmp/test.txt</parameter>',
            "</tool_call>",
            "Done",
        ]
        handler = StreamHandler(tool_names=["Read"])
        events = []
        for chunk in chunks:
            evts = handler.feed(chunk)
            events.extend(evts)
        evts = handler.flush()
        events.extend(evts)

        tool_events = [e for e in events if e.get("type") == "tool_calls"]
        assert len(tool_events) >= 1
        calls = tool_events[0]["data"]
        assert len(calls) >= 1
        assert calls[0]["name"] == "Read"
        assert "/tmp/test.txt" in calls[0].get("arguments", "")

    def test_preserves_formatting_and_newlines_after_tool_call(self):
        chunks = [
            "<tool_calls>",
            '<invoke name="Read"><parameter name="file_path">/tmp/test.txt</parameter></invoke>',
            "</tool_calls>\n",
            "### 6. Potencjalne problemy / uwagi\n",
            "| Problem | Priorytet |\n",
            "|---------|-----------|",
        ]
        handler = StreamHandler(tool_names=["Read"])
        events = []
        for chunk in chunks:
            events.extend(handler.feed(chunk))
        events.extend(handler.flush())

        text_events = [e for e in events if e.get("type") == "text"]
        text_content = "".join([e["data"] for e in text_events])

        # Verify that the newline after </tool_calls> is preserved and not swallowed
        assert "\n### 6. Potencjalne problemy / uwagi\n" in text_content
        assert "| Problem | Priorytet |\n" in text_content


def test_detect_repetition_loop():
    from server.core.stream_handler import detect_repetition_loop

    # Normal text should not trigger
    normal = "Here is some code:\n```python\nfor i in range(10):\n    print(i)\n```\nDone."
    assert detect_repetition_loop(normal) is None

    # DSML malformed tag loop
    tag_loop = "Some initial response</｜｜DSML｜｜ parameter></｜｜DSML｜｜ parameter></｜｜DSML｜｜ parameter></｜｜DSML｜｜ parameter>"
    pat = detect_repetition_loop(tag_loop)
    assert pat is not None

    # Plain </parameter> tag loop
    plain_loop = "Processing results...</parameter></parameter></parameter></parameter>"
    assert detect_repetition_loop(plain_loop) is not None

    # Substring loop
    substr_loop = "Prefix text" + ("repeat_pattern_1234_" * 5)
    pat_sub = detect_repetition_loop(substr_loop)
    assert pat_sub is not None
    assert "repeat_pattern_1234_" in pat_sub

