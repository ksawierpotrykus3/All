"""tests/test_bracket_tool_call.py — Tests for Chinese & bracket tool call detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.parser.dsml_parser import parse_bracket_tool_calls, parse_dsml_tool_calls
from server.repair.repair_tier1 import repair_tier1
from server.parser.dsml_sieve import StreamSieve, SieveEvent


def test_parse_bracket_tool_call_basic():
    text = '[调用 Read] {"path": "F:/PROJEKTY/vinted/.superpowers/sdd/task-C1-brief.md"}'
    calls, cleaned = parse_bracket_tool_calls(text, ["Read"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    assert "task-C1-brief.md" in calls[0]["arguments"]
    assert cleaned == ""


def test_parse_bracket_tool_call_variants():
    # Chinese full-width brackets
    text1 = '【调用 Read】 {"path": "a.txt"}'
    calls1, _ = parse_bracket_tool_calls(text1)
    assert len(calls1) == 1
    assert calls1[0]["name"] == "Read"

    # Colon variant
    text2 = '[调用: Read] {"path": "b.txt"}'
    calls2, _ = parse_bracket_tool_calls(text2)
    assert len(calls2) == 1
    assert calls2[0]["name"] == "Read"

    # English call
    text3 = '[call Read] {"path": "c.txt"}'
    calls3, _ = parse_bracket_tool_calls(text3)
    assert len(calls3) == 1
    assert calls3[0]["name"] == "Read"

    # English invoke
    text4 = '[invoke Read] {"path": "d.txt"}'
    calls4, _ = parse_bracket_tool_calls(text4)
    assert len(calls4) == 1
    assert calls4[0]["name"] == "Read"


def test_parse_dsml_fallback_to_bracket():
    text = '[调用 Read] {"path": "F:/PROJEKTY/vinted/.superpowers/sdd/task-C1-brief.md"}'
    calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    assert "task-C1-brief.md" in calls[0]["arguments"]


def test_repair_tier1_converts_bracket_to_dsml():
    text = '[调用 Read] {"path": "F:/PROJEKTY/vinted/.superpowers/sdd/task-C1-brief.md"}'
    repaired = repair_tier1(text, ["Read"])
    assert repaired is not None
    assert "<tool_calls>" in repaired
    assert '<invoke name="Read">' in repaired
    assert "task-C1-brief.md" in repaired


def test_sieve_detects_bracket_tool_call_single_chunk():
    sieve = StreamSieve(tool_names=["Read"])
    chunk = '[调用 Read] {"path": "F:/PROJEKTY/vinted/.superpowers/sdd/task-C1-brief.md"}'
    events = sieve.feed(chunk)
    events += sieve.flush()

    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) == 1
    assert len(tc_events[0].data) == 1
    assert tc_events[0].data[0]["name"] == "Read"
    assert "task-C1-brief.md" in tc_events[0].data[0]["arguments"]


def test_sieve_detects_bracket_tool_call_split_chunks():
    sieve = StreamSieve(tool_names=["Read"])
    # Split between opener and json
    e1 = sieve.feed("[调用 Read] ")
    assert len(e1) == 0  # Buffered, not completed yet

    e2 = sieve.feed('{"path": "F:/test.md"}')
    e2 += sieve.flush()

    tc_events = [e for e in e2 if e.type == "tool_calls"]
    assert len(tc_events) == 1
    assert tc_events[0].data[0]["name"] == "Read"
    assert "F:/test.md" in tc_events[0].data[0]["arguments"]


def test_sieve_detects_bracket_split_on_bracket_character():
    sieve = StreamSieve(tool_names=["Read"])
    # Split exactly on '['
    e1 = sieve.feed("I will read the brief now. [")
    text_events = [e for e in e1 if e.type == "text"]
    assert len(text_events) == 1
    assert "I will read the brief now." in text_events[0].data

    e2 = sieve.feed('调用 Read] {"path": "F:/test.md"}')
    e2 += sieve.flush()

    tc_events = [e for e in e2 if e.type == "tool_calls"]
    assert len(tc_events) == 1
    assert tc_events[0].data[0]["name"] == "Read"


def test_sieve_detects_bracket_split_on_chinese_character():
    sieve = StreamSieve(tool_names=["Read"])
    # Split on '[调'
    e1 = sieve.feed("Planning... [调")
    text_events = [e for e in e1 if e.type == "text"]
    assert len(text_events) == 1
    assert "Planning..." in text_events[0].data

    e2 = sieve.feed('用 Read] {"path": "F:/test.md"}')
    e2 += sieve.flush()

    tc_events = [e for e in e2 if e.type == "tool_calls"]
    assert len(tc_events) == 1
    assert tc_events[0].data[0]["name"] == "Read"


def test_sieve_preserves_text_before_and_after_bracket_call():
    sieve = StreamSieve(tool_names=["Read"])
    chunk = 'Pre-prose\n[调用 Read] {"path": "F:/test.md"}\nPost-prose'
    events = sieve.feed(chunk)
    events += sieve.flush()

    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]

    assert any("Pre-prose" in e.data for e in text_events)
    assert len(tc_events) == 1
    assert tc_events[0].data[0]["name"] == "Read"
    assert any("Post-prose" in e.data for e in text_events)
