"""Tests for tier 1 — text-level DSML/XML repair."""

from __future__ import annotations

import json
from server.repair.repair_tier1 import repair_tier1, _fix_tool_called_child_format


def test_fix_missing_lt():
    """Prepend < to DSML tags that lost their opening bracket."""
    text = '|DSML|tool_calls>\n<invoke name="Bash">\n</invoke>\n</|DSML|tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert result.startswith("<|DSML|tool_calls>")


def test_strip_markdown_fences():
    """Strip ```xml ... ``` fences around tool blocks."""
    text = '```xml\n<tool_calls>\n<invoke name="Read">\n<parameter name="file_path">/tmp/x</parameter>\n</invoke>\n</tool_calls>\n```'
    result = repair_tier1(text)
    assert result is not None
    assert "```" not in result
    assert "<tool_calls>" in result


def test_fix_unclosed_cdata():
    """Append ]]> if CDATA section is unclosed."""
    text = '<tool_calls>\n<invoke name="Bash">\n<parameter name="command"><![CDATA[echo hello</parameter>\n</invoke>\n</tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert "<![CDATA[echo hello]]>" in result or "echo hello" in result


def test_fix_broken_namespace():
    """Fix common namespace typos like |DSL| → |DSML|."""
    text = '<|DSL|tool_calls>\n<|DSL|invoke name="Bash">\n<|DSL|parameter name="command">ls</|DSL|parameter>\n</|DSL|invoke>\n</|DSL|tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert "|DSML|" in result or "|TOOL|" in result


def test_fix_truncated_tag():
    """Gracefully handle truncated last tag."""
    text = '<tool_calls>\n<invoke name="Bash">\n<parameter name="command">ls</'
    result = repair_tier1(text)
    assert result is not None


def test_strip_leading_prose():
    """Remove human text before the tool block."""
    text = 'I will call the tool now.\n\n<tool_calls>\n<invoke name="Bash">\n<parameter name="command">ls</parameter>\n</invoke>\n</tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert result.strip().startswith("<")


def test_clean_text_returns_none():
    """Return None if text has no tool call content after cleaning."""
    assert repair_tier1("Hello, how can I help you?") is None
    assert repair_tier1("") is None


# ── <tool_called> with <tool_name>/<tool_args> child elements ──────────────

def test_tool_called_child_format_conversion():
    """Convert <tool_called> with <tool_name>/<tool_args> to DSML format."""
    text = (
        '<tool_called>\n'
        '<tool_name>Skill</tool_name>\n'
        '<tool_args>\n'
        '{"name": "using-superpowers"}\n'
        '</tool_args>\n'
        '</tool_called>'
    )
    result = _fix_tool_called_child_format(text)
    assert '<tool_calls>' in result
    assert '<invoke name="Skill">' in result
    assert '<parameter name="name">' in result
    assert '<![CDATA[using-superpowers]]>' in result
    assert '</invoke>' in result
    assert '</tool_calls>' in result


def test_tool_called_child_full_pipeline():
    """Full repair_tier1 pipeline handles <tool_called> with child elements."""
    text = (
        '<tool_called>\n'
        '<tool_name>Skill</tool_name>\n'
        '<tool_args>\n'
        '{"name": "using-superpowers"}\n'
        '</tool_args>\n'
        '</tool_called>'
    )
    result = repair_tier1(text)
    assert result is not None
    assert '<tool_calls>' in result
    assert '<invoke name="Skill">' in result


def test_tool_called_child_multiple_args():
    """Handle multiple JSON arguments in <tool_args>."""
    text = (
        '<tool_called>\n'
        '<tool_name>Read</tool_name>\n'
        '<tool_args>\n'
        '{"path": "/tmp/x", "line": 42}\n'
        '</tool_args>\n'
        '</tool_called>'
    )
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="Read">' in result
    assert '<parameter name="path">' in result
    assert '<parameter name="line">' in result
    assert '42' in result


def test_tool_called_old_format_still_works():
    """Old format with name='X' attribute still works after changes."""
    text = '<tool_called name="Bash"><parameter name="command"><![CDATA[ls]]></parameter></tool_called>'
    result = repair_tier1(text)
    assert result is not None
    assert '<tool_calls>' in result
    assert '<invoke name="Bash">' in result


# ── Edge cases for <tool_called> child format ─────────────────────────────

def test_tool_called_child_empty_args():
    """Empty JSON object <tool_args>{} should produce no parameter elements."""
    text = '<tool_called><tool_name>Skill</tool_name><tool_args>{}</tool_args></tool_called>'
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="Skill">' in result
    # no <parameter> elements for empty object
    assert '<parameter' not in result


def test_tool_called_child_bool_and_none_args():
    """Handle boolean and null JSON values."""
    text = (
        '<tool_called>\n'
        '<tool_name>Validator</tool_name>\n'
        '<tool_args>{"enabled": true, "debug": false, "extra": null}</tool_args>\n'
        '</tool_called>'
    )
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="Validator">' in result
    assert '<parameter name="enabled">true</parameter>' in result
    assert '<parameter name="debug">false</parameter>' in result
    assert '<parameter name="extra"></parameter>' in result or '<parameter name="extra"/>' in result


def test_tool_called_child_nested_json():
    """Nested dict/list in <tool_args> should be wrapped in CDATA as JSON string."""
    text = (
        '<tool_called>\n'
        '<tool_name>Config</tool_name>\n'
        '<tool_args>{"nested": {"key": "val"}, "list": [1, 2, 3]}</tool_args>\n'
        '</tool_called>'
    )
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="Config">' in result
    assert 'nested' in result
    assert 'list' in result
    # Nested values should be CDATA-encoded JSON
    assert '<![CDATA[{"key": "val"}]]>' in result
    assert '<![CDATA[[1, 2, 3]]]>' in result


def test_tool_called_child_invalid_json_fallback():
    """Invalid JSON in <tool_args> falls back to a single content parameter."""
    text = (
        '<tool_called>\n'
        '<tool_name>Test</tool_name>\n'
        '<tool_args>not valid json at all</tool_args>\n'
        '</tool_called>'
    )
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="Test">' in result
    assert '<parameter name="content">' in result


def test_tool_called_child_whitespace_variations():
    """Handle extra whitespace and newlines inside <tool_called> tags."""
    text = (
        '<tool_called  >\n\n'
        '  <tool_name>  Skill  </tool_name>\n\n'
        '  <tool_args  >\n'
        '    {"name": "test"}\n'
        '  </tool_args  >\n\n'
        '</tool_called  >'
    )
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="Skill">' in result, f"Got: {result}"
    assert '<![CDATA[test]]>' in result


def test_tool_called_child_name_with_special_chars():
    """Tool name with underscores and numbers."""
    text = '<tool_called><tool_name>My_Tool_V2</tool_name><tool_args>{"x": 1}</tool_args></tool_called>'
    result = _fix_tool_called_child_format(text)
    assert '<invoke name="My_Tool_V2">' in result


def test_tool_called_child_multiple_blocks():
    """Multiple <tool_called> blocks in one text should all be converted."""
    text = (
        '<tool_called><tool_name>First</tool_name><tool_args>{"a": 1}</tool_args></tool_called>\n'
        '<tool_called><tool_name>Second</tool_name><tool_args>{"b": 2}</tool_args></tool_called>'
    )
    result = _fix_tool_called_child_format(text)
    assert result.count('<invoke name="First">') == 1
    assert result.count('<invoke name="Second">') == 1
    assert result.count('<invoke ') == 2


def test_tool_called_child_leading_prose_stripped():
    """Human text before <tool_called> should be stripped by full pipeline."""
    text = (
        'I will call the tool now.\n\n'
        '<tool_called>\n'
        '<tool_name>Skill</tool_name>\n'
        '<tool_args>{"name": "test"}</tool_args>\n'
        '</tool_called>'
    )
    result = repair_tier1(text)
    assert result is not None
    assert result.strip().startswith('<')
    assert 'I will call the tool' not in result


def test_tool_called_child_old_and_new_mixed():
    """Both old format (name= attr) and new format (child elements) in same text."""
    text = (
        '<tool_called name="OldTool"><parameter name="x"><![CDATA[1]]></parameter></tool_called>\n'
        '<tool_called><tool_name>NewTool</tool_name><tool_args>{"y": 2}</tool_args></tool_called>'
    )
    result = repair_tier1(text)
    assert result is not None
    assert '<invoke name="OldTool">' in result
    assert '<invoke name="NewTool">' in result
    assert result.count('<invoke ') == 2


def test_nested_invoke_mismatch():
    """Mismatched nested invoke parameter closed with </parameter> must be repaired."""
    text = (
        '<invoke name="TodoWrite">\n'
        '  <invoke name="todos" string="true">[{"id": "1"}]</parameter>\n'
        '  <parameter name="merge">false</parameter>\n'
        '</invoke>'
    )
    result = repair_tier1(text, ["TodoWrite"])
    assert result is not None
    assert '<parameter name="todos" string="true">' in result
    assert '</parameter>' in result
    assert '<invoke name="todos"' not in result


def test_parameter_with_extra_attributes():
    """Parameters with additional attributes (e.g. string="false") are parsed correctly."""
    from server.parser.dsml_parser import parse_dsml_tool_calls
    text = (
        '<tool_calls>\n'
        '<invoke name="TodoWrite">\n'
        '<parameter name="merge" string="false">true</parameter>\n'
        '<parameter name="todos" string="false">[{"id": "7"}]</parameter>\n'
        '</invoke>\n'
        '</tool_calls>'
    )
    calls, cleaned = parse_dsml_tool_calls(text, ["TodoWrite"])
    assert len(calls) == 1
    assert calls[0]["name"] == "TodoWrite"
    args = json.loads(calls[0]["arguments"])
    assert args["merge"] is True
    assert args["todos"] == [{"id": "7"}]


