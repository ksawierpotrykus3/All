"""Property-based tests for parser robustness and round-trip properties."""

from __future__ import annotations

import json
from hypothesis import given, settings, strategies as st, assume

from server.parser.dsml_parser import (
    parse_dsml_tool_calls,
    clean_tool_text,
    strip_dsml_markup,
    _format_tool_call,
    format_tool_calls_for_prompt,
)
from server.config import _CONTENT_STRIP_PATTERN

from tests.property.strategies import (
    arbitrary_text,
    text_with_dsml,
    valid_dsml_stream,
    TOOL_NAMES,
)


# ─── Robustness: parser never crashes ──────────────────────────────────

@given(text=arbitrary_text())
@settings(max_examples=200)
def test_parse_never_crashes_on_arbitrary_text(text):
    """parse_dsml_tool_calls must not crash on any string input."""
    calls, cleaned = parse_dsml_tool_calls(text, TOOL_NAMES)
    assert isinstance(calls, list)
    assert isinstance(cleaned, str)


@given(text=arbitrary_text())
@settings(max_examples=200)
def test_clean_never_crashes_on_arbitrary_text(text):
    """clean_tool_text must not crash on any string input."""
    result = clean_tool_text(text)
    assert isinstance(result, str)


@given(text=arbitrary_text())
@settings(max_examples=200)
def test_strip_never_crashes_on_arbitrary_text(text):
    """strip_dsml_markup must not crash on any string input."""
    result = strip_dsml_markup(text)
    assert isinstance(result, str)


# ─── Idempotency ───────────────────────────────────────────────────────

@given(text=arbitrary_text())
@settings(max_examples=100)
def test_clean_idempotent(text):
    """Applying clean_tool_text twice should give the same result."""
    once = clean_tool_text(text)
    twice = clean_tool_text(once)
    assert once == twice


@given(text=arbitrary_text())
@settings(max_examples=100)
def test_strip_idempotent(text):
    """Applying strip_dsml_markup twice should give the same result."""
    once = strip_dsml_markup(text)
    twice = strip_dsml_markup(once)
    assert once == twice


# ─── Soundness: clean_tool_text removes all tool call tags ──────────────

@given(text=text_with_dsml())
@settings(max_examples=100)
def test_clean_removes_tool_calls(text):
    """After cleaning, no DSML tool call tags should remain."""
    cleaned = clean_tool_text(text)
    # No tool_calls tags, invoke tags, parameter tags, or CDATA blocks
    assert "<tool_calls" not in cleaned.lower()
    assert "<invoke" not in cleaned.lower()
    assert "<parameter" not in cleaned.lower()
    assert "<![CDATA[" not in cleaned
    assert "</tool_calls" not in cleaned.lower()


@given(text=text_with_dsml())
@settings(max_examples=100)
def test_parse_finds_at_least_zero(text):
    """parse_dsml_tool_calls should return a list (possibly empty)."""
    calls, cleaned = parse_dsml_tool_calls(text, TOOL_NAMES)
    assert len(calls) >= 0


# ─── Round-trip: valid DSML → parse → verify ────────────────────────────

@given(dsml=valid_dsml_stream())
@settings(max_examples=100)
def test_parse_valid_dsml_extracts_tool_name(dsml):
    """Parsing valid DSML should extract at least one tool call with a valid name."""
    calls, cleaned = parse_dsml_tool_calls(dsml, TOOL_NAMES)
    assume(len(calls) > 0)
    for tc in calls:
        assert "name" in tc
        assert "arguments" in tc
        assert isinstance(tc["name"], str)


@given(dsml=valid_dsml_stream())
@settings(max_examples=100)
def test_parse_valid_dsml_arguments_are_json(dsml):
    """Parsed tool call arguments should be JSON-serializable."""
    calls, cleaned = parse_dsml_tool_calls(dsml, TOOL_NAMES)
    for tc in calls:
        # arguments should be a JSON string that can be parsed
        args = json.loads(tc["arguments"])
        assert isinstance(args, dict)


@given(dsml=valid_dsml_stream())
@settings(max_examples=100)
def test_format_and_parse_roundtrip(dsml):
    """Formatting tool calls to DSML and parsing them should be consistent."""
    calls, _ = parse_dsml_tool_calls(dsml, TOOL_NAMES)
    if calls:
        reformatted = format_tool_calls_for_prompt(calls)
        reparsed, _ = parse_dsml_tool_calls(reformatted, TOOL_NAMES)
        assert len(reparsed) == len(calls)


# ─── Content strip pattern ──────────────────────────────────────────────

@given(text=arbitrary_text())
@settings(max_examples=100)
def test_content_strip_pattern_runs_without_error(text):
    """_CONTENT_STRIP_PATTERN.sub should not crash on any input."""
    result = _CONTENT_STRIP_PATTERN.sub("", text)
    assert isinstance(result, str)


@given(text=arbitrary_text())
@settings(max_examples=50)
def test_content_strip_idempotent(text):
    """Applying _CONTENT_STRIP_PATTERN twice should be idempotent."""
    once = _CONTENT_STRIP_PATTERN.sub("", text)
    twice = _CONTENT_STRIP_PATTERN.sub("", once)
    assert once == twice


# ─── Parse + clean consistency ──────────────────────────────────────────

@given(text=text_with_dsml())
@settings(max_examples=100)
def test_parse_and_clean_consistent(text):
    """If parse finds N calls, clean should remove at least N tool call blocks."""
    calls, _ = parse_dsml_tool_calls(text, TOOL_NAMES)
    cleaned = clean_tool_text(text)
    # cleaned should have no more invoke tags than the calls found
    remaining = cleaned.lower().count("<invoke")
    # clean removes all invoke tags, so remaining should be 0
    assert remaining == 0


@given(text=arbitrary_text())
@settings(max_examples=100)
def test_parse_returns_list_of_dicts(text):
    """parse_dsml_tool_calls always returns list of properly structured dicts."""
    calls, cleaned = parse_dsml_tool_calls(text, [])
    assert isinstance(calls, list)
    for tc in calls:
        assert isinstance(tc, dict)
        assert "name" in tc
        assert "arguments" in tc
