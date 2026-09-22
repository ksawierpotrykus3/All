"""Hypothesis strategies for generating DSML tool call test data."""

from __future__ import annotations

import json as _json
import re
from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

TOOL_NAMES = [
    "Read", "Write", "Edit", "SearchReplace", "Glob", "Grep",
    "Bash", "RunCommand", "WebSearch", "WebFetch", "Task",
    "AskUserQuestion", "TodoWrite", "NotifyUser", "Skill",
]

PARAM_NAMES = st.sampled_from([
    "file_path", "path", "pattern", "query", "command", "content",
    "old_string", "new_string", "replacement", "target", "url",
    "name", "description", "title", "message", "question",
])

XML_SAFE_CHARS = st.characters(
    min_codepoint=32,
    max_codepoint=0x10FFFF,
    blacklist_categories=("Cc", "Cs"),
    blacklist_characters="&<[]>|",
)

JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.text(alphabet=XML_SAFE_CHARS, max_size=100),
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20), children, max_size=5),
    max_leaves=10,
)


def _json_to_str(val):
    """Convert a JSON-serializable value to a string for CDATA."""
    if isinstance(val, bool):
        return str(val).lower()
    elif val is None:
        return ""
    elif isinstance(val, (dict, list)):
        return _json.dumps(val, ensure_ascii=False)
    else:
        return str(val)


@st.composite
def tool_call_dsml(draw) -> str:
    """Generate a valid DSML tool call block."""
    name = draw(st.sampled_from(TOOL_NAMES))
    num_params = draw(st.integers(min_value=0, max_value=5))

    params = []
    for _ in range(num_params):
        param_name = draw(PARAM_NAMES)
        param_value = draw(JSON_VALUES)
        value_str = _json_to_str(param_value)
        params.append(f'      <parameter name="{param_name}">{value_str}</parameter>')

    param_block = "\n".join(params) if params else ""
    return f'<|tool_calls|>\n<invoke name="{name}">\n{param_block}\n</invoke>\n</tool_calls>'


@st.composite
def text_with_dsml(draw) -> str:
    """Generate text that contains DSML tool calls mixed with prose."""
    whitespace = st.just(" ") | st.just("\n") | st.just("\t")
    prose_alphabet = XML_SAFE_CHARS | whitespace
    prose = draw(st.text(alphabet=prose_alphabet, min_size=0, max_size=200))
    calls = draw(st.lists(tool_call_dsml(), max_size=3))
    result = prose
    for call in calls:
        result += call + draw(st.text(alphabet=prose_alphabet, min_size=0, max_size=200))
    return result


@st.composite
def arbitrary_text(draw) -> str:
    """Generate arbitrary text that may contain malformed DSML."""
    return draw(st.text(min_size=0, max_size=500))


@st.composite
def valid_dsml_stream(draw) -> str:
    """Generate a valid DSML stream with proper nesting."""
    name = draw(st.sampled_from(TOOL_NAMES))
    num_params = draw(st.integers(min_value=0, max_value=5))

    params = []
    for _ in range(num_params):
        param_name = draw(PARAM_NAMES)
        param_value = draw(JSON_VALUES)
        value_str = _json_to_str(param_value)
        params.append(f'    <parameter name="{param_name}">{value_str}</parameter>')

    param_block = "\n".join(params) if params else ""
    return f'<tool_calls><invoke name="{name}">\n{param_block}\n</invoke></tool_calls>'


def tool_name_strategy() -> SearchStrategy[str]:
    return st.sampled_from(TOOL_NAMES)


def json_value_strategy() -> SearchStrategy:
    return JSON_VALUES
