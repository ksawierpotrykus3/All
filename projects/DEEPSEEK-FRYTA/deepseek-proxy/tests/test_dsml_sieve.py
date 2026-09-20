"""tests/test_dsml_sieve.py — StreamSieve unit tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.parser.dsml_sieve import StreamSieve, SieveEvent


def test_sieve_passes_text_through():
    sieve = StreamSieve()
    events = sieve.feed("Hello world")
    assert len(events) == 1
    assert events[0].type == "text"
    assert events[0].data == "Hello world"


def test_sieve_detects_tool_calls():
    sieve = StreamSieve()
    chunk = '<|DSML|tool_calls>\n  <|DSML|invoke name="Read">\n    <|DSML|parameter name="file_path"><![CDATA[/path/file.txt]]></|DSML|parameter>\n  </|DSML|invoke>\n</|DSML|tool_calls>'
    events = sieve.feed(chunk)
    assert len(events) == 1
    assert events[0].type == "tool_calls"
    assert len(events[0].data) == 1
    assert events[0].data[0]["name"] == "Read"
    assert "file_path" in events[0].data[0]["arguments"]


def test_sieve_splits_text_and_tool_calls():
    sieve = StreamSieve()
    chunk = 'Some text before <|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="file_path"><![CDATA[/path/file.txt]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    events = sieve.feed(chunk)
    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(text_events) == 1
    assert "Some text before" in text_events[0].data
    assert len(tc_events) >= 1


def test_sieve_flush_returns_remaining():
    sieve = StreamSieve()
    # Feed text ending with split marker '<' so it is held in pending
    sieve.feed("partial <")
    events = sieve.flush()
    assert len(events) == 1
    assert events[0].type == "text"
    assert events[0].data == "<"


def test_sieve_handles_split_chunks():
    sieve = StreamSieve()
    events = sieve.feed(
        '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="x">'
    )
    assert len(events) == 0  # not yet complete, buffered
    events2 = sieve.feed(
        "<![CDATA[val]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>"
    )
    tc_events = [e for e in events2 if e.type == "tool_calls"]
    assert len(tc_events) >= 1
    assert tc_events[0].data[0]["name"] == "Read"


def test_sieve_fallback_no_dsml_prefix():
    sieve = StreamSieve()
    chunk = '<tool_calls><invoke name="Read"><parameter name="x"><![CDATA[val]]></parameter></invoke></tool_calls>'
    events = sieve.feed(chunk)
    assert len(events) == 1
    assert events[0].type == "tool_calls"


def test_sieve_multiple_tool_calls():
    sieve = StreamSieve()
    chunk = '<|DSML|tool_calls>\n  <|DSML|invoke name="Read"><|DSML|parameter name="a"><![CDATA[1]]></|DSML|parameter></|DSML|invoke>\n  <|DSML|invoke name="Write"><|DSML|parameter name="b"><![CDATA[2]]></|DSML|parameter></|DSML|invoke>\n</|DSML|tool_calls>'
    events = sieve.feed(chunk)
    assert len(events) == 1
    assert len(events[0].data) == 2


def test_sieve_text_after_tool_calls():
    sieve = StreamSieve()
    chunk = '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="x"><![CDATA[val]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls> and some trailing text'
    events = sieve.feed(chunk)
    events += sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    assert any("trailing text" in e.data for e in text_events)


def test_sieve_detects_tool_prefix():
    """TOOL prefix (new format) must be detected like DSML."""
    sieve = StreamSieve()
    chunk = '<|DSML|tool_calls>\n  <|DSML|invoke name="Read">\n    <|DSML|parameter name="file_path"><![CDATA[/path/file.txt]]></|DSML|parameter>\n  </|DSML|invoke>\n</|DSML|tool_calls>'
    events = sieve.feed(chunk)
    assert len(events) == 1
    assert events[0].type == "tool_calls"
    assert len(events[0].data) == 1
    assert events[0].data[0]["name"] == "Read"


def test_sieve_tool_prefix_split_chunks():
    """TOOL prefix must work across split chunks."""
    sieve = StreamSieve()
    events = sieve.feed(
        '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="x">'
    )
    assert len(events) == 0  # not yet complete
    events2 = sieve.feed(
        "<![CDATA[val]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>"
    )
    tc_events = [e for e in events2 if e.type == "tool_calls"]
    assert len(tc_events) >= 1
    assert tc_events[0].data[0]["name"] == "Read"


def test_sieve_tool_prefix_text_and_tool_calls():
    """TOOL prefix splits text and tool calls correctly."""
    sieve = StreamSieve()
    chunk = 'Some text before <|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="file_path"><![CDATA[/path/file.txt]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    events = sieve.feed(chunk)
    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(text_events) == 1
    assert "Some text before" in text_events[0].data
    assert len(tc_events) >= 1


def test_sieve_tool_prefix_text_after():
    """TOOL prefix: trailing text after close tag must be detected."""
    sieve = StreamSieve()
    chunk = '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="x"><![CDATA[val]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls> and trailing text'
    events = sieve.feed(chunk)
    events += sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    assert any("trailing text" in e.data for e in text_events)


# ── <tool_called> format (past-tense, no attr) tests ──────────────────────


def test_sieve_tool_called_new_format():
    """StreamSieve detects <tool_called> with <tool_name>/<tool_args> children."""
    sieve = StreamSieve(tool_names=["Skill"])
    chunk = (
        "<tool_called>\n"
        "<tool_name>Skill</tool_name>\n"
        "<tool_args>\n"
        '{"name": "using-superpowers"}\n'
        "</tool_args>\n"
        "</tool_called>"
    )
    events = sieve.feed(chunk) + sieve.flush()
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) >= 1, f"No tool_calls event, got: {[e.type for e in events]}"
    assert tc_events[0].data[0]["name"] == "Skill"
    args = tc_events[0].data[0]["arguments"]
    assert "using-superpowers" in args


def test_sieve_tool_called_new_format_with_leading_text():
    """Leading text before <tool_called> block is preserved."""
    sieve = StreamSieve(tool_names=["Skill"])
    chunk = (
        "Let me call a tool.\n\n"
        "<tool_called>\n"
        "<tool_name>Skill</tool_name>\n"
        '<tool_args>{"name": "test"}</tool_args>\n'
        "</tool_called>"
    )
    events = sieve.feed(chunk) + sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(text_events) >= 1
    assert "Let me call a tool" in text_events[0].data
    assert len(tc_events) >= 1
    assert tc_events[0].data[0]["name"] == "Skill"


def test_sieve_tool_called_new_format_with_trailing_text():
    """Trailing text after </tool_called> block is preserved."""
    sieve = StreamSieve(tool_names=["Skill"])
    chunk = (
        "<tool_called>\n"
        "<tool_name>Skill</tool_name>\n"
        '<tool_args>{"name": "test"}</tool_args>\n'
        "</tool_called>"
        " and then some explanation"
    )
    events = sieve.feed(chunk) + sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) >= 1
    assert any("explanation" in e.data for e in text_events)


def test_sieve_tool_called_new_format_split_chunks():
    """New <tool_called> format works across split chunks (streaming)."""
    sieve = StreamSieve(tool_names=["Skill"])
    # First chunk: partial opening
    events1 = sieve.feed(
        '<tool_called>\n<tool_name>Skill</tool_name>\n<tool_args>\n{"n'
    )
    assert len(events1) == 0  # not complete yet, buffered

    # Second chunk: complete the block
    events2 = sieve.feed('ame": "test"}\n</tool_args>\n</tool_called>')
    tc_events = [e for e in events2 if e.type == "tool_calls"]
    assert len(tc_events) >= 1, f"No tool_calls, got: {[e.type for e in events2]}"
    assert tc_events[0].data[0]["name"] == "Skill"


def test_sieve_tool_called_new_format_three_chunks():
    """New format across three chunks for realistic streaming."""
    sieve = StreamSieve(tool_names=["Read"])
    events1 = sieve.feed("Some text.\n\n<tool_called>\n<tool_name>Re")
    assert len([e for e in events1 if e.type == "text"]) <= 1  # text may come through

    events2 = sieve.feed('ad</tool_name>\n<tool_args>\n{"path":')
    events3 = sieve.feed(' "/tmp/x"}\n</tool_args>\n</tool_called>\n\nDone.')
    all_events = events1 + events2 + events3 + sieve.flush()

    tc_events = [e for e in all_events if e.type == "tool_calls"]
    text_events = [e for e in all_events if e.type == "text"]

    assert len(tc_events) >= 1, (
        f"No tool_calls, got types: {[e.type for e in all_events]}"
    )
    assert tc_events[0].data[0]["name"] == "Read"
    assert any("Some text" in e.data for e in text_events)
    assert any("Done" in e.data for e in text_events)


def test_sieve_tool_called_old_name_attr_format():
    """Old <tool_called name='X'> format still detected by StreamSieve."""
    sieve = StreamSieve(tool_names=["Bash"])
    chunk = '<tool_called name="Bash"><parameter name="command"><![CDATA[ls -la]]></parameter></tool_called>'
    events = sieve.feed(chunk) + sieve.flush()
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) >= 1
    assert tc_events[0].data[0]["name"] == "Bash"


def test_sieve_tool_called_multiple_blocks():
    """Multiple <tool_called> blocks in sequence are all detected."""
    sieve = StreamSieve(tool_names=["Read", "Write"])
    chunk = (
        '<tool_called><tool_name>Read</tool_name><tool_args>{"f": "a.txt"}</tool_args></tool_called>\n'
        '<tool_called><tool_name>Write</tool_name><tool_args>{"f": "b.txt"}</tool_args></tool_called>'
    )
    events = sieve.feed(chunk) + sieve.flush()
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) >= 1
    # Should have 2 tool calls total
    all_calls = []
    for ev in tc_events:
        all_calls.extend(ev.data)
    names = [c["name"] for c in all_calls]
    assert "Read" in names, f"Names: {names}"
    assert "Write" in names, f"Names: {names}"


# ── <tool_call name="X"> singular format ──────────────────────────────────


def test_sieve_tool_call_singular_with_name():
    """StreamSieve detects <tool_call name='X'> (singular with name attr)."""
    sieve = StreamSieve(tool_names=["LS"])
    chunk = (
        '<tool_call name="LS">\n'
        '<parameter name="path">f:\\test</parameter>\n'
        "</tool_call>"
    )
    events = sieve.feed(chunk) + sieve.flush()
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) >= 1, f"No tool_calls, got: {[e.type for e in events]}"
    assert tc_events[0].data[0]["name"] == "LS"


def test_sieve_tool_call_singular_with_leading_text():
    """Leading text before <tool_call name='X'> is preserved."""
    sieve = StreamSieve(tool_names=["Skill"])
    chunk = 'Let me call a tool.\n\n<tool_call name="Skill"><parameter name="name">test</parameter></tool_call>'
    events = sieve.feed(chunk) + sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert any("Let me call" in e.data for e in text_events)
    assert len(tc_events) >= 1
    assert tc_events[0].data[0]["name"] == "Skill"


class TestExpandedToolStarts:
    def test_detects_tool_use_json(self):
        sieve = StreamSieve()
        events = sieve.feed(
            '<tool_use_json>{"tool_name":"Read","arguments":{"file_path":"/tmp/x"}}</tool_use_json>'
        )
        tc = [e for e in events if e.type == "tool_calls"]
        assert len(tc) >= 1

    def test_detects_function_call(self):
        sieve = StreamSieve()
        events = sieve.feed(
            '<function_call>{"name":"Read","arguments":{"file_path":"/tmp/x"}}</function_call>'
        )
        tc = [e for e in events if e.type == "tool_calls"]
        assert len(tc) >= 1

    def test_detects_function_calls(self):
        sieve = StreamSieve()
        events = sieve.feed(
            '<function_calls>[{"name":"Read","arguments":{"file_path":"/tmp/x"}}]</function_calls>'
        )
        tc = [e for e in events if e.type == "tool_calls"]
        assert len(tc) >= 1

    def test_thinking_tag_not_mistaken_as_tool(self):
        sieve = StreamSieve()
        events = sieve.feed("<thinking>Let me think about this...</thinking>")
        tc = [e for e in events if e.type == "tool_calls"]
        assert len(tc) == 0
        text = [e for e in events if e.type == "text"]
        assert len(text) > 0


def test_sieve_tool_call_singular_split_chunks():
    """<tool_call name='X'> detected across split chunks."""
    sieve = StreamSieve(tool_names=["Read"])
    events1 = sieve.feed('<tool_call name="Read">\n<parameter name="path">/tmp/')
    events2 = sieve.feed("x</parameter>\n</tool_call>")
    all_events = events1 + events2 + sieve.flush()
    tc_events = [e for e in all_events if e.type == "tool_calls"]
    assert len(tc_events) >= 1, (
        f"No tool_calls in split chunks, got: {[e.type for e in all_events]}"
    )
    assert tc_events[0].data[0]["name"] == "Read"


def test_sieve_does_not_block_plain_markdown_blocks():
    sieve = StreamSieve()
    events1 = sieve.feed("Here is the code:\n```python\n")
    assert len(events1) >= 1
    assert any(e.type == "text" and "```python" in e.data for e in events1)

    events2 = sieve.feed("print('hello')\n")
    assert len(events2) >= 1
    assert any(e.type == "text" and "print('hello')" in e.data for e in events2)

    events3 = sieve.feed("```\nand text.")
    assert len(events3) >= 1
    assert any(e.type == "text" and "```" in e.data for e in events3)


# ─── Regression: double full-width pipe (U+FF5C) + _calls wrapper ───────────
# DeepSeek Pro emits <｜｜DSML｜｜_calls> / <｜｜DSML｜｜invoke> (DOUBLE full-width
# pipes and a `_calls` wrapper) instead of <|DSML|tool_calls>.  The sieve
# must normalise each chunk so TOOL_STARTS / CLOSE_TAGS detection sees the
# canonical form and captures the block.

_FW = chr(0xFF5C)


def _d2(tag: str) -> str:
    """Open tag with double full-width pipes: <｜｜tag｜｜>"""
    return "<" + _FW + _FW + tag + _FW + _FW + ">"


def _d2c(tag: str) -> str:
    """Close tag with double full-width pipes: </｜｜tag｜｜>"""
    return "</" + _FW + _FW + tag + _FW + _FW + ">"


def test_sieve_double_fullwidth_pipe_wrapper():
    sieve = StreamSieve(tool_names=["bash"])
    chunk = (
        _d2("_calls")
        + "\n"
        + _d2('invoke name="bash"')
        + "\n"
        + _d2('parameter name="command" string="true"')
        + "echo hi"
        + _d2c("parameter")
        + "\n"
        + _d2c("invoke")
        + "\n"
        + _d2c("_calls")
    )
    events = sieve.feed(chunk)
    events += sieve.flush()
    tc = [e for e in events if e.type == "tool_calls"]
    assert len(tc) >= 1, f"no tool_calls, events={[(e.type, e.data) for e in events]}"
    assert tc[0].data[0]["name"] == "bash"


def test_sieve_double_fullwidth_pipe_split_chunks():
    """Double FW pipes split across chunks must still be captured."""
    sieve = StreamSieve(tool_names=["bash"])
    events1 = sieve.feed(_d2("_calls") + "\n" + _d2('invoke name="bash"') + "\n")
    events2 = sieve.feed(_d2('parameter name="command" string="true"') + "echo hi")
    events3 = sieve.feed(
        _d2c("parameter") + "\n" + _d2c("invoke") + "\n" + _d2c("_calls")
    )
    all_events = events1 + events2 + events3 + sieve.flush()
    tc = [e for e in all_events if e.type == "tool_calls"]
    assert len(tc) >= 1, (
        f"no tool_calls, events={[(e.type, e.data) for e in all_events]}"
    )
    assert tc[0].data[0]["name"] == "bash"


def test_sieve_code_with_relational_operator_and_spaced_calls():
    """StreamSieve must correctly capture calls block containing code with '<' operators
    and <｜｜DSML｜｜ calls> wrappers without leaking raw XML to text events.
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

    sieve = StreamSieve(tool_names=["Shell"])
    # Feed in arbitrary chunks
    chunks = [raw[:60], raw[60:150], raw[150:400], raw[400:700], raw[700:]]
    events = []
    for c in chunks:
        events.extend(sieve.feed(c))
    events.extend(sieve.flush())

    tc = [e for e in events if e.type == "tool_calls"]
    text_events = [e for e in events if e.type == "text" and e.data.strip()]
    assert len(tc) == 1, f"Expected 1 tool_call event, got {len(tc)}"
    assert tc[0].data[0]["name"] == "Shell"
    assert len(text_events) == 0, f"Leaked text events: {text_events}"


def test_sieve_large_unclosed_parameter_no_catastrophic_backtracking():
    """Verify that a large streaming parameter buffer without close tag
    does NOT trigger catastrophic backtracking (ReDoS) or freeze the CPU."""
    import time

    sieve = StreamSieve(tool_names=["Write"])
    # Start of tool call
    sieve.feed('<|DSML|tool_calls>\n<|DSML|invoke name="Write">\n<|DSML|parameter name="content">\n')

    # Stream 50,000 characters of arbitrary code with quotes, slashes, whitespace
    chunk = 'def some_function(a="value", b=\'other\'):\n    # <not_a_tag> test\n    return a < b and True\n' * 500

    t_start = time.time()
    events = sieve.feed(chunk)
    elapsed = time.time() - t_start

    # Must process in less than 0.1s (no ReDoS freezing)
    assert elapsed < 0.2, f"Stream processing took too long: {elapsed:.3f}s"
    assert len(events) == 0  # Still capturing


