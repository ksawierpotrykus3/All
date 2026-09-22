"""tests/test_stream_service_utils.py — Tests for stream service helper utilities."""
import json
from server.utils.helpers import _ensure_valid_json, _chunk


# =============================================================================
# _ensure_valid_json
# =============================================================================

def test_ensure_valid_json_valid_dict():
    """Passes through valid JSON dict strings."""
    input_str = '{"key": "value", "num": 42}'
    result = _ensure_valid_json(input_str)
    assert result == input_str
    # Should be parseable
    parsed = json.loads(result)
    assert parsed["key"] == "value"
    assert parsed["num"] == 42


def test_ensure_valid_json_valid_list():
    """Valid JSON that is not a dict gets wrapped in {'value': ...}."""
    input_str = '["a", "b", "c"]'
    result = _ensure_valid_json(input_str)
    parsed = json.loads(result)
    assert "value" in parsed
    assert parsed["value"] == ["a", "b", "c"]


def test_ensure_valid_json_valid_scalar():
    """Valid JSON scalar gets wrapped."""
    input_str = '"just a string"'
    result = _ensure_valid_json(input_str)
    parsed = json.loads(result)
    assert parsed["value"] == "just a string"


def test_ensure_valid_json_valid_int():
    """Valid JSON int gets wrapped."""
    input_str = '42'
    result = _ensure_valid_json(input_str)
    parsed = json.loads(result)
    assert parsed["value"] == 42


def test_ensure_valid_json_truncated():
    """Truncated JSON gets wrapped in {'raw_value': ...}."""
    input_str = '{"key": "value", "num"'
    result = _ensure_valid_json(input_str)
    parsed = json.loads(result)
    assert "raw_value" in parsed
    assert parsed["raw_value"] == input_str


def test_ensure_valid_json_single_quoted():
    """Single-quoted strings are not valid JSON, get wrapped."""
    input_str = "{'key': 'value'}"
    result = _ensure_valid_json(input_str)
    parsed = json.loads(result)
    assert "raw_value" in parsed
    assert parsed["raw_value"] == input_str


def test_ensure_valid_json_empty_string():
    """Empty string gets wrapped in {'raw_value': ''}."""
    result = _ensure_valid_json("")
    parsed = json.loads(result)
    assert "raw_value" in parsed
    assert parsed["raw_value"] == ""


def test_ensure_valid_json_none():
    """None gets converted to 'null' via json.dumps."""
    result = _ensure_valid_json(None)
    assert result == "null"


def test_ensure_valid_json_int_value():
    """Integer value gets converted to string JSON."""
    result = _ensure_valid_json(42)
    assert result == "42"


# =============================================================================
# _chunk
# =============================================================================

def test_chunk_basic():
    """Produces valid SSE format with content delta."""
    result = _chunk("cmpl_123", 1000000, "deepseek-chat", {"content": "Hello"})
    assert result.startswith("data: ")
    assert result.endswith("\n\n")
    parsed = json.loads(result[6:].strip())
    assert parsed["id"] == "cmpl_123"
    assert parsed["object"] == "chat.completion.chunk"
    assert parsed["choices"][0]["delta"]["content"] == "Hello"


def test_chunk_with_finish_reason():
    """Handles stop/finish_reason."""
    result = _chunk("cmpl_123", 1000000, "deepseek-chat", {}, fr="stop")
    assert result.startswith("data: ")
    parsed = json.loads(result[6:].strip())
    assert parsed["choices"][0]["finish_reason"] == "stop"


def test_chunk_with_tool_calls():
    """Handles tool_calls delta."""
    delta = {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "Read", "arguments": "{}"}}]}
    result = _chunk("cmpl_123", 1000000, "deepseek-chat", delta)
    assert result.startswith("data: ")
    parsed = json.loads(result[6:].strip())
    assert parsed["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "Read"


def test_chunk_empty_delta():
    """Empty delta without finish_reason returns empty string."""
    result = _chunk("cmpl_123", 1000000, "deepseek-chat", {})
    assert result == ""


def test_chunk_with_finish_reason_tool_calls():
    """Finish reason 'tool_calls' is handled."""
    result = _chunk("cmpl_123", 1000000, "deepseek-chat", {}, fr="tool_calls")
    parsed = json.loads(result[6:].strip())
    assert parsed["choices"][0]["finish_reason"] == "tool_calls"

