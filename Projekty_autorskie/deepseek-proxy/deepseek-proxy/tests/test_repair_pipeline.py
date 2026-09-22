"""Tests for the repair pipeline orchestrator."""

from __future__ import annotations

from server.repair import repair_pipeline


def test_repair_pipeline_tier1_success():
    """Pipeline returns tier1 result when tier1 succeeds."""
    text = '```xml\n<tool_calls>\n<invoke name="Bash">\n<parameter name="command">ls</parameter>\n</invoke>\n</tool_calls>\n```'
    result = repair_pipeline(text)
    assert result is not None
    assert "<tool_calls>" in result
    assert "```" not in result


def test_repair_pipeline_tier2_success():
    """Pipeline returns tier2 result when tier1 fails but tier2 succeeds."""
    text = '<tool_calls><invoke name="Bash"><parameter name="command">ls</parameter></invoke></tool_calls>'
    result = repair_pipeline(text)
    assert result is not None


def test_repair_pipeline_all_fail():
    """Pipeline returns None when all tiers fail."""
    text = "this is just plain text with no tool calls at all"
    result = repair_pipeline(text)
    assert result is None


def test_repair_pipeline_empty_input():
    """Pipeline returns None for empty input."""
    assert repair_pipeline("") is None
    assert repair_pipeline(None) is None  # type: ignore


# ─── Sieve integration tests ──────────────────────────────

from server.parser.dsml_sieve import StreamSieve


def test_sieve_recovers_missing_lt():
    """Sieve extracts tool calls from text with missing < on DSML tags."""
    sieve = StreamSieve()
    text = 'Some text\n\n|DSML|tool_calls>\n<|DSML|invoke name="Bash">\n<|DSML|parameter name="command">ls</|DSML|parameter>\n</|DSML|invoke>\n</|DSML|tool_calls>'
    events = sieve.feed(text)
    events += sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0, f"No tool_calls events from: {events}"
    calls = tool_events[0].data
    assert len(calls) > 0
    assert calls[0]["name"] == "Bash"


def test_sieve_recovers_markdown_fences():
    """Sieve extracts tool calls from markdown-fenced blocks."""
    sieve = StreamSieve()
    text = '```xml\n<tool_calls>\n<invoke name="Read">\n<parameter name="file_path">test.txt</parameter>\n</invoke>\n</tool_calls>\n```'
    events = sieve.feed(text)
    events += sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0
    calls = tool_events[0].data
    assert len(calls) > 0
    assert calls[0]["name"] == "Read"


def test_sieve_recovers_trailing_comma_json():
    """Sieve extracts tool calls with trailing comma in args JSON."""
    sieve = StreamSieve()
    text = '<tool_calls>\n<invoke name="Bash">\n<parameter name="command"><![CDATA[{"command": "ls",}]]></parameter>\n</invoke>\n</tool_calls>'
    events = sieve.feed(text)
    events += sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0
    calls = tool_events[0].data
    assert len(calls) > 0


def test_sieve_normal_text_unaffected():
    """Regular text without tool calls passes through unchanged."""
    sieve = StreamSieve()
    text = "Hello, how can I help you today?"
    events = sieve.feed(text)
    events += sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    assert len(text_events) > 0
    assert "tool_calls" not in str(events)


# ─── <tool_called> new format integration tests ─────────────

def test_sieve_recovers_tool_called_new_format():
    """Sieve extracts tool calls from <tool_called> with <tool_name>/<tool_args>."""
    sieve = StreamSieve(tool_names=["Skill"])
    text = (
        '<tool_called>\n'
        '<tool_name>Skill</tool_name>\n'
        '<tool_args>\n'
        '{"name": "using-superpowers"}\n'
        '</tool_args>\n'
        '</tool_called>'
    )
    events = sieve.feed(text) + sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0, f"No tool_calls, got: {[e.type for e in events]}"
    calls = tool_events[0].data
    assert len(calls) == 1
    assert calls[0]["name"] == "Skill"
    assert "using-superpowers" in calls[0]["arguments"]


def test_sieve_recovers_tool_called_old_format():
    """Sieve still extracts tool calls from old <tool_called name='X'> format."""
    sieve = StreamSieve(tool_names=["Bash"])
    text = '<tool_called name="Bash"><parameter name="command"><![CDATA[ls]]></parameter></tool_called>'
    events = sieve.feed(text) + sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0
    calls = tool_events[0].data
    assert len(calls) == 1
    assert calls[0]["name"] == "Bash"


def test_pipeline_tool_called_new_format():
    """repair_pipeline directly handles <tool_called> with child elements."""
    text = (
        '<tool_called>\n'
        '<tool_name>Read</tool_name>\n'
        '<tool_args>\n'
        '{"path": "/tmp/x", "line": 42}\n'
        '</tool_args>\n'
        '</tool_called>'
    )
    result = repair_pipeline(text, tool_names=["Read"])
    assert result is not None
    assert '<tool_calls>' in result
    assert '<invoke name="Read">' in result
    # Arguments should be converted to <parameter> elements
    assert '<parameter name="path">' in result
    assert '<parameter name="line">' in result


def test_pipeline_tool_called_both_formats():
    """repair_pipeline handles both old and new <tool_called> formats."""
    text = (
        '<tool_called name="OldTool"><parameter name="x"><![CDATA[1]]></parameter></tool_called>\n'
        '<tool_called><tool_name>NewTool</tool_name><tool_args>{"y": 2}</tool_args></tool_called>'
    )
    result = repair_pipeline(text, tool_names=["OldTool", "NewTool"])
    assert result is not None
    assert '<invoke name="OldTool">' in result
    assert '<invoke name="NewTool">' in result


def test_pipeline_tool_called_with_leading_prose():
    """repair_pipeline strips leading prose before <tool_called>."""
    text = (
        'I will use a tool now.\n\n'
        '<tool_called>\n'
        '<tool_name>Skill</tool_name>\n'
        '<tool_args>{"name": "test"}</tool_args>\n'
        '</tool_called>'
    )
    result = repair_pipeline(text, tool_names=["Skill"])
    assert result is not None
    assert result.strip().startswith('<')
    assert 'I will use a tool' not in result


# ─── <tool_call name="X"> singular format ─────────────

def test_pipeline_tool_call_singular():
    """repair_pipeline returns text as-is for <tool_call name='X'> (parser handles it directly)."""
    text = '<tool_call name="LS"><parameter name="path">f:\\test</parameter></tool_call>'
    result = repair_pipeline(text, tool_names=["LS"])
    # repair_pipeline returns the text as-is because the DSML parser handles
    # LEGACY_TOOL_CALL_PATTERN directly — no conversion needed
    assert result is not None
    assert '<tool_call' in result


def test_sieve_recovers_tool_call_singular():
    """StreamSieve detects <tool_call name='X'> via full stream pipeline."""
    sieve = StreamSieve(tool_names=["Skill"])
    text = '<tool_call name="Skill"><parameter name="name"><![CDATA[test]]></parameter></tool_call>'
    events = sieve.feed(text) + sieve.flush()
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) >= 1
    assert tc_events[0].data[0]["name"] == "Skill"
    assert "test" in tc_events[0].data[0].get("arguments", "")
