import pytest
from server.repair.repair_tier1 import _fix_direct_tool_tags, repair_tier1
from server.repair.repair_tier3 import repair_tier3
from server.parser.dsml_parser import parse_dsml_tool_calls


def test_fix_direct_tool_tags_within_tool_calls():
    raw = "<tool_calls>\n<Shell>\n<command>git status</command>\n</Shell>\n</tool_calls>"
    fixed = _fix_direct_tool_tags(raw, ["Shell", "Read"])
    assert '<invoke name="Shell">' in fixed
    assert '<parameter name="command">git status</parameter>' in fixed
    assert '</invoke>' in fixed

    calls, _ = parse_dsml_tool_calls(fixed, ["Shell", "Read"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Shell"
    assert "git status" in calls[0]["arguments"]


def test_fix_direct_tool_tags_with_attributes():
    raw = '<tool_calls>\n<Read file_path="server/main.py"/>\n</tool_calls>'
    fixed = _fix_direct_tool_tags(raw, ["Shell", "Read"])
    assert '<invoke name="Read">' in fixed
    assert '<parameter name="file_path">server/main.py</parameter>' in fixed

    calls, _ = parse_dsml_tool_calls(fixed, ["Shell", "Read"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    assert "server/main.py" in calls[0]["arguments"]


def test_repair_tier3_closes_unclosed_invoke_and_tool_calls():
    truncated = '<tool_calls>\n<invoke name="Shell"><parameter name="command">pytest tests/'
    repaired = repair_tier3(truncated, ["Shell"])
    assert repaired is not None
    assert repaired.endswith("</tool_calls>")
    assert "</invoke>" in repaired
    assert "</parameter>" in repaired

    calls, _ = parse_dsml_tool_calls(repaired, ["Shell"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Shell"
    assert "pytest tests/" in calls[0]["arguments"]
