"""tests/test_nested_stutter_and_child_tags.py — Tests for nested invoke stutter and child XML tags."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.parser.dsml_parser import parse_dsml_tool_calls
from server.repair import repair_pipeline
from server.parser.dsml_sieve import StreamSieve


def test_stutter_with_child_description_and_unclosed_invoke():
    snippet = """<｜｜DSML｜｜tool_calls>
<invoke name="Shell">
<｜｜DSML｜｜tool_calls>
<invoke name="Shell">
<parameter name="command" string="true">git add bot_v2/src/vintedbot2/checkout.py bot_v2/tests/test_experiments.py; git commit -m "feat(checkout): add skip-GET-polling lever (lever 4) behind flag" -q; git rev-parse --short HEAD</parameter>
<description string="true">Commit C6</description>
<parameter name="working_directory" string="true">F:/PROJEKTY/vinted</parameter>
</invoke>
</｜｜DSML｜｜tool_calls>
"""
    calls, cleaned = parse_dsml_tool_calls(snippet, ["Shell"])
    assert len(calls) == 1, f"Expected exactly 1 call (filtered stutter), got {len(calls)}"
    tc = calls[0]
    assert tc["name"] == "Shell"
    import json
    args = json.loads(tc["arguments"])
    assert "git add bot_v2" in args["command"]
    assert args["working_directory"] == "F:/PROJEKTY/vinted"
    assert args["description"] == "Commit C6"


def test_sieve_emits_clean_tool_call_for_stutter_and_child_tags():
    snippet = """<｜｜DSML｜｜tool_calls>
<invoke name="Shell">
<｜｜DSML｜｜tool_calls>
<invoke name="Shell">
<parameter name="command" string="true">git status</parameter>
<description string="true">Check status</description>
</invoke>
</｜｜DSML｜｜tool_calls>
"""
    sieve = StreamSieve(["Shell"])
    events = sieve.feed(snippet)
    events += sieve.flush()

    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(tc_events) == 1
    calls = tc_events[0].data
    assert len(calls) == 1
    import json
    args = json.loads(calls[0]["arguments"])
    assert args["command"] == "git status"
    assert args["description"] == "Check status"
