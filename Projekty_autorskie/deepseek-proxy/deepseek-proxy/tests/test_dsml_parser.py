"""tests/test_dsml_parser.py — DSML/TOOL parser unit tests"""

import json
import pytest
from server.parser.dsml_parser import (
    parse_dsml_tool_calls,
    parse_json_tool_calls,
    strip_dsml_markup,
    clean_tool_text,
    format_tool_calls_for_prompt,
    _normalize_dsml,
    _fix_inverted_dsml_close,
)


def test_parse_single_tool_call_tool_prefix():
    text = '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="file_path"><![CDATA[/path/file.txt]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    args = json.loads(calls[0]["arguments"])
    assert args["file_path"] == "/path/file.txt"


def test_parse_single_tool_call_dsml_prefix_backward_compat():
    """Old DSML prefix must still parse for backward compatibility."""
    text = '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="file_path"><![CDATA[/path/file.txt]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    args = json.loads(calls[0]["arguments"])
    assert args["file_path"] == "/path/file.txt"


def test_parse_multiple_tool_calls():
    text = '<|DSML|tool_calls>\n  <|DSML|invoke name="Read"><|DSML|parameter name="a"><![CDATA[1]]></|DSML|parameter></|DSML|invoke>\n  <|DSML|invoke name="Write"><|DSML|parameter name="b"><![CDATA[2]]></|DSML|parameter></|DSML|invoke>\n</|DSML|tool_calls>'
    calls, cleaned = parse_dsml_tool_calls(text, ["Read", "Write"])
    assert len(calls) == 2


def test_parse_no_prefix():
    text = '<tool_calls><invoke name="Read"><parameter name="x"><![CDATA[val]]></parameter></invoke></tool_calls>'
    calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
    assert len(calls) == 1


def test_parse_cdata_with_special_chars():
    text = '<|DSML|tool_calls><|DSML|invoke name="Write"><|DSML|parameter name="content"><![CDATA[def hello():\n    print("world")]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    calls, cleaned = parse_dsml_tool_calls(text, ["Write"])
    assert len(calls) == 1
    args = json.loads(calls[0]["arguments"])
    assert "def hello():" in args["content"]


def test_parse_auto_types():
    text = '<|DSML|tool_calls><|DSML|invoke name="Search"><|DSML|parameter name="limit"><![CDATA[10]]></|DSML|parameter><|DSML|parameter name="enabled"><![CDATA[true]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    calls, cleaned = parse_dsml_tool_calls(text, ["Search"])
    args = json.loads(calls[0]["arguments"])
    assert args["limit"] == 10
    assert args["enabled"] is True


def test_strip_dsml_markup_removes_tool_prefix():
    text = "hello <|DSML|tool_calls>stuff</|DSML|tool_calls> world"
    result = strip_dsml_markup(text)
    assert "<|DSML|" not in result


def test_strip_dsml_markup_also_removes_dsml_prefix():
    text = "hello <|DSML|tool_calls>stuff</|DSML|tool_calls> world"
    result = strip_dsml_markup(text)
    assert "<|DSML|" not in result


def test_clean_tool_text():
    text = "some text <|DSML|tool_calls><invoke name='X'></invoke></|DSML|tool_calls> more text"
    result = clean_tool_text(text)
    assert "<|DSML|" not in result
    assert "some text" in result
    assert "more text" in result


def test_format_tool_calls_for_prompt():
    calls = [{"name": "Read", "arguments": '{"file_path": "/path/file.txt"}'}]
    result = format_tool_calls_for_prompt(calls)
    assert "<|DSML|tool_calls>" in result
    assert "Read" in result
    assert "<![CDATA[" in result


# ─── Regression: DeepSeek Pro inverted DSML close tags ─────────────────────
# Bug report 2026-08: when DeepSeek Pro emits closing tags with the slash
# AFTER the DSML/TOOL marker (e.g. ``<|DSML|/invoke>``) instead of the
# canonical ``</|DSML|invoke>``, every regex in the parser failed to
# recognise the closing tag — the entire tool-call XML leaked out into
# the response ``content`` field instead of being emitted as a tool_call.


def _lt():
    return chr(60)


def _gt():
    return chr(62)


def _sl():
    return chr(47)


def _fw():
    return chr(0xFF5C)


def _pipe():
    return "|"


def _q():
    return chr(34)


def _nl():
    return chr(10)


# Close-tag sentinel (avoid XML parsing inside Python source strings)
_INV_CLOSE_SENTINEL = "INVCLOSE"


def test_fix_inverted_dsml_close_ascii():
    """ASCII variant: <|DSML|/invoke> -></|DSML|invoke>"""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    bad = _LT + _pipe() + "DSML" + _pipe() + _SL + "invoke" + _GT
    good = _LT + _SL + _pipe() + "DSML" + _pipe() + "invoke" + _GT
    assert _fix_inverted_dsml_close(bad) == good


def test_fix_inverted_dsml_close_fullwidth():
    """Full-width pipe variant: <｜DSML｜/invoke> -></｜DSML｜invoke>"""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    _FW = _fw()
    bad = _LT + _FW + "DSML" + _FW + _SL + "invoke" + _GT
    good = _LT + _SL + _FW + "DSML" + _FW + "invoke" + _GT
    assert _fix_inverted_dsml_close(bad) == good


def test_fix_inverted_dsml_close_tool_marker():
    """<|TOOL|/invoke> also gets fixed."""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    bad = _LT + _pipe() + "TOOL" + _pipe() + _SL + "invoke" + _GT
    good = _LT + _SL + _pipe() + "TOOL" + _pipe() + "invoke" + _GT
    assert _fix_inverted_dsml_close(bad) == good


def test_fix_inverted_dsml_close_parameter():
    """<|DSML|/parameter> -></|DSML|parameter>"""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    bad = _LT + _pipe() + "DSML" + _pipe() + _SL + "parameter" + _GT
    good = _LT + _SL + _pipe() + "DSML" + _pipe() + "parameter" + _GT
    assert _fix_inverted_dsml_close(bad) == good


def test_fix_inverted_dsml_close_tool_result():
    """<|DSML|/tool_result> -></|DSML|tool_result>"""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    bad = _LT + _pipe() + "DSML" + _pipe() + _SL + "tool_result" + _GT
    good = _LT + _SL + _pipe() + "DSML" + _pipe() + "tool_result" + _GT
    assert _fix_inverted_dsml_close(bad) == good


def test_fix_inverted_dsml_close_passthrough():
    """Canonical close tags must pass through unchanged."""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    canonical = _LT + _SL + _pipe() + "DSML" + _pipe() + "invoke" + _GT
    assert _fix_inverted_dsml_close(canonical) == canonical
    # Plain</invoke> also untouched
    plain = _LT + _SL + "invoke" + _GT
    assert _fix_inverted_dsml_close(plain) == plain


def test_fix_inverted_dsml_close_empty():
    assert _fix_inverted_dsml_close("") == ""


def test_parse_dsml_inverted_close_bug_report():
    """Regression: full tool-call XML with inverted DSML close tags must
    still parse to a single bash tool_call with the right arguments.

    Before the fix this entire string leaked out as text content.
    """
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    _Q = chr(34)
    _NL = chr(10)
    bad = (
        _LT
        + _pipe()
        + "DSML"
        + _pipe()
        + "invoke name="
        + _Q
        + "bash"
        + _Q
        + _GT
        + _NL
        + _LT
        + _pipe()
        + "DSML"
        + _pipe()
        + "parameter name="
        + _Q
        + "command"
        + _Q
        + _GT
        + "uv run ruff check src tests 2>&1 | Select-Object -First 20"
        + _LT
        + _pipe()
        + "DSML"
        + _pipe()
        + _SL
        + "parameter"
        + _GT
        + _NL
        + _LT
        + _pipe()
        + "DSML"
        + _pipe()
        + _SL
        + "invoke"
        + _GT
    )
    calls, cleaned = parse_dsml_tool_calls(bad, ["bash"])
    assert len(calls) == 1, f"Expected 1 tool_call, got {len(calls)}: {calls}"
    assert calls[0]["name"] == "bash"
    args = json.loads(calls[0]["arguments"])
    assert "uv run ruff check src tests" in args["command"]
    assert "Select-Object -First 20" in args["command"]


def test_parse_dsml_inverted_close_fullwidth():
    """Same bug but with full-width pipes (some terminals emit these).
    Verifies that the normaliser rewrites the inverted close tag so a
    downstream ASCII-only regex at least has a chance to match.

    Full parse support for ``｜DSML｜invoke`` is out of scope of this fix;
    see ``test_fix_inverted_dsml_close_fullwidth`` for the unit-level
    guarantee.
    """
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    _FW = _fw()
    # A bare inverted close tag with full-width pipes — the normaliser
    # must rewrite it to the canonical ``</｜DSML｜invoke>`` form.
    bad = _LT + _FW + "DSML" + _FW + _SL + "invoke" + _GT
    fixed = _normalize_dsml(bad)
    expected = _LT + _SL + _FW + "DSML" + _FW + "invoke" + _GT
    assert fixed == expected


def test_normalize_dsml_runs_both_fixes():
    """_normalize_dsml runs _fix_missing_lt AND _fix_inverted_dsml_close."""
    _LT = _lt()
    _SL = _sl()
    _GT = _gt()
    # Combined: missing < on opener AND inverted slash on closer
    bad = (
        _pipe()
        + "DSML"
        + _pipe()
        + "invoke name="
        + _q()
        + "bash"
        + _q()
        + _GT
        + _nl()
        + _LT
        + _pipe()
        + "DSML"
        + _pipe()
        + _SL
        + "invoke"
        + _GT
    )
    normalized = _normalize_dsml(bad)
    # Both bugs fixed in one pass
    assert _LT + _pipe() + "DSML" + _pipe() + "invoke" in normalized
    assert _LT + _SL + _pipe() + "DSML" + _pipe() + "invoke" in normalized


# ─── Regression: bug report "tool call leaks to content" ──────────────────
# The user reported: DeepSeek Pro emits tool calls in the Trae/Claude
# style (plain ``<invoke name="...">`` with ``<parameter name="..."
# string="true">`` attributes) and the parser failed to emit them as
# tool_calls — only fragments like ``oke name="bash">`` leaked into the
# response ``content`` field.  These tests guard against that exact
# pattern being silently dropped.


def test_parse_bug_report_tra_style_invoke():
    """Bug report: Trae/Claude-style <invoke> with parameter string='true'
    attribute must parse to a tool_call, not leak as text.
    """
    _LT = _lt()
    _GT = _gt()
    _Q = _q()
    _SL = _sl()
    _NL = _nl()
    text = (
        _LT
        + "invoke name="
        + _Q
        + "bash"
        + _Q
        + _GT
        + _NL
        + _LT
        + "parameter name="
        + _Q
        + "command"
        + _Q
        + " string="
        + _Q
        + "true"
        + _Q
        + _GT
        + "uv run ruff check src tests 2>&1 | Select-Object -First 20"
        + _LT
        + _SL
        + "parameter"
        + _GT
        + _NL
        + _LT
        + "parameter name="
        + _Q
        + "workdir"
        + _Q
        + " string="
        + _Q
        + "true"
        + _Q
        + _GT
        + "F:\\PROJEKTY\\ALLEGRO_SCRAPER"
        + _LT
        + _SL
        + "parameter"
        + _GT
        + _NL
        + _LT
        + _SL
        + "invoke"
        + _GT
    )
    calls, cleaned = parse_dsml_tool_calls(text, ["bash"])
    assert len(calls) == 1
    assert calls[0]["name"] == "bash"
    args = json.loads(calls[0]["arguments"])
    assert "uv run ruff check src tests" in args["command"]
    assert args["workdir"] == "F:\\PROJEKTY\\ALLEGRO_SCRAPER"
    # Cleaned text should not contain the raw XML markup
    assert "<invoke" not in cleaned
    invoke_close = _LT + _SL + "invoke" + _GT
    assert invoke_close not in cleaned


def test_parse_bug_report_multiple_parallel_invocations():
    """Multiple <invoke> blocks without a wrapper must all be detected."""
    _LT = _lt()
    _GT = _gt()
    _Q = _q()
    _SL = _sl()
    _NL = _nl()
    text = (
        _LT
        + "invoke name="
        + _Q
        + "Read"
        + _Q
        + _GT
        + _NL
        + _LT
        + "parameter name="
        + _Q
        + "file_path"
        + _Q
        + _GT
        + "a.py"
        + _LT
        + _SL
        + "parameter"
        + _GT
        + _NL
        + _LT
        + _SL
        + "invoke"
        + _GT
        + _NL
        + _LT
        + "invoke name="
        + _Q
        + "Read"
        + _Q
        + _GT
        + _NL
        + _LT
        + "parameter name="
        + _Q
        + "file_path"
        + _Q
        + _GT
        + "b.py"
        + _LT
        + _SL
        + "parameter"
        + _GT
        + _NL
        + _LT
        + _SL
        + "invoke"
        + _GT
    )
    calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
    assert len(calls) == 2
    names = [c["name"] for c in calls]
    assert names == ["Read", "Read"]
    paths = [json.loads(c["arguments"])["file_path"] for c in calls]
    assert paths == ["a.py", "b.py"]


# ─── Regression: double full-width pipe (U+FF5C) wrapper ───────────────────
# The model emits <｜｜DSML｜｜_calls> / <｜｜DSML｜｜invoke> (DOUBLE full-width
# pipes, plus a `_calls` wrapper tag) instead of the canonical
# <|DSML|tool_calls> / <|DSML|invoke>.  The parser never matched these, so
# the whole block leaked verbatim into `content` and no tool call fired.


def _fw2(tag: str) -> str:
    """Wrap a tag name with double full-width pipes: <｜｜tag｜｜>"""
    _LT = _lt()
    _GT = _gt()
    _FW = _fw()
    return _LT + _FW + _FW + tag + _FW + _FW + _GT


def _fw2_close(tag: str) -> str:
    """Close tag with double full-width pipes: </｜｜tag｜｜>"""
    _LT = _lt()
    _GT = _gt()
    _SL = _sl()
    _FW = _fw()
    return _LT + _SL + _FW + _FW + tag + _FW + _FW + _GT


def test_parse_double_fullwidth_pipe_wrapper():
    """Bug: double FW-pipe DSML wrapper with _calls must parse to a bash call."""
    _FW = _fw()
    _NL = _nl()
    _Q = _q()
    text = (
        _fw2("_calls")
        + _nl()
        + _fw2('invoke name="bash"')
        + _nl()
        + _fw2('parameter name="command" string="true"')
        + "Get-ChildItem .venv | Format-Table"
        + _fw2_close("parameter")
        + _nl()
        + _fw2('parameter name="workdir" string="true"')
        + "F:\\PROJEKTY\\ALLEGRO_SCRAPER"
        + _fw2_close("parameter")
        + _nl()
        + _fw2_close("invoke")
        + _nl()
        + _fw2_close("_calls")
    )
    calls, cleaned = parse_dsml_tool_calls(text, ["bash"])
    assert len(calls) == 1, f"expected 1 call, got {len(calls)}"
    assert calls[0]["name"] == "bash"
    args = json.loads(calls[0]["arguments"])
    assert "Get-ChildItem" in args["command"]
    assert args["workdir"] == "F:\\PROJEKTY\\ALLEGRO_SCRAPER"


def test_parse_double_fullwidth_pipe_without_wrapper():
    """Double FW pipes directly on <invoke> (no _calls wrapper) must work."""
    NL = _nl()
    Q = _q()
    text = (
        _fw2('invoke name="bash"')
        + NL
        + _fw2('parameter name="command" string="true"')
        + "echo hi"
        + _fw2_close("parameter")
        + NL
        + _fw2_close("invoke")
    )
    calls, cleaned = parse_dsml_tool_calls(text, ["bash"])
    assert len(calls) == 1
    assert calls[0]["name"] == "bash"
    args = json.loads(calls[0]["arguments"])
    assert args["command"] == "echo hi"


def test_normalize_collapses_double_fullwidth_pipes():
    """_normalize_dsml must collapse double FW pipes to a single pipe."""
    from server.parser.dsml_parser import _normalize_dsml

    _LT = _lt()
    _GT = _gt()
    _FW = _fw()
    raw = _LT + _FW + _FW + "DSML" + _FW + _FW + "invoke" + _GT
    normalized = _normalize_dsml(raw)
    # After collapse, there should be a single pipe per side: <｜DSML｜invoke>
    assert _LT + _FW + "DSML" + _FW + "invoke" + _GT in normalized
    assert _FW + _FW not in normalized


def test_normalize_renames_underscore_calls_wrapper():
    """_normalize_dsml must rewrite <..._calls> wrappers to <...tool_calls>."""
    from server.parser.dsml_parser import _normalize_dsml

    _LT = _lt()
    _GT = _gt()
    _SL = _sl()
    _FW = _fw()
    raw = (
        _LT
        + _FW
        + "DSML"
        + _FW
        + "_calls"
        + _GT
        + "X"
        + _SL
        + _LT
        + _FW
        + "DSML"
        + _FW
        + "_calls"
        + _GT
    )
    normalized = _normalize_dsml(raw)
    expected = (
        _LT
        + _FW
        + "DSML"
        + _FW
        + "tool_calls"
        + _GT
        + "X"
        + _SL
        + _LT
        + _FW
        + "DSML"
        + _FW
        + "tool_calls"
        + _GT
    )
    assert normalized == expected


def test_dsml_code_with_relational_operators_and_spaced_calls():
    """Test that python code with '<' operators inside parameters does not swallow </parameter>
    and that <｜｜DSML｜｜ calls> with whitespace is properly parsed.
    """
    raw = '''<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="Shell">
<｜｜DSML｜｜ parameter name="block_until_ms" string="false">30000</｜｜DSML｜｜ parameter>
<｜｜DSML｜｜ parameter name="command" string="true">python -c "import json,base64,time,pathlib; c=json.loads(pathlib.Path('cookies.json').read_text()); at=c.get('access_token_web',''); p=at.split('.');
import sys
pay=json.loads(base64.urlsafe_b64decode(p[1]+'='*(-len(p[1])%4))) if len(p)>1 else {}
print('keys:',sorted(c.keys())[:20])
print('has_access_token_web:',bool(at),'len',len(at))
print('exp:',pay.get('exp'),'iat:',pay.get('iat'))
print('exp_human:',time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(pay['exp'])) if pay.get('exp') else None)
print('now_human:',time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()))
print('expired:', (pay.get('exp') or 0) < time.time())
print('datadome_len:',len(c.get('datadome') or ''))
"</｜｜DSML｜｜ parameter>
<｜｜DSML｜｜ parameter name="description" string="true">Decode JWT expiry from cookies</｜｜DSML｜｜ parameter>
<｜｜DSML｜｜ parameter name="working_directory" string="true">f:\\PROJEKTY\\vinted\\bot_v2</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>'''

    calls, cleaned = parse_dsml_tool_calls(raw, ["Shell"])
    assert len(calls) == 1
    call = calls[0]
    assert call["name"] == "Shell"
    args = json.loads(call["arguments"])
    assert args["block_until_ms"] == 30000
    assert "print('expired:', (pay.get('exp') or 0) < time.time())" in args["command"]
    assert args["description"] == "Decode JWT expiry from cookies"
    assert args["working_directory"] == "f:\\PROJEKTY\\vinted\\bot_v2"
    assert cleaned.strip() == ""

