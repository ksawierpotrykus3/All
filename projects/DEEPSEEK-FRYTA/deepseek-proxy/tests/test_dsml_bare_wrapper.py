"""tests/test_dsml_bare_wrapper.py — Reproduction and regression test for bare DSML wrapper format.

Model generates:
  <｜｜DSML｜｜>
  <invoke name="Shell">
  <parameter ...>...</parameter>
  </｜｜DSML｜｜>
Without explicit </invoke>, using <｜｜DSML｜｜> / </｜｜DSML｜｜> as outer block.
Must emit tool_calls correctly and NOT leak <|DSML|> into prose text.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from server.core.stream_handler import StreamHandler
from server.parser.dsml_parser import parse_dsml_tool_calls, clean_tool_text
from server.parser.dsml_sieve import StreamSieve


RAW_INPUT = """All files compile. Now run the unit tests.

<｜｜DSML｜｜>
<invoke name="Shell">
<parameter name="command" string="true">python -m pytest tests/ -q 2>&1</parameter>
<parameter name="working_directory" string="true">F:\\PROJEKTY\\vinted\\bot_v2</parameter>
<parameter name="description" string="true">Run fast unit tests</parameter>
</｜｜DSML｜｜>
"""

RAW_INPUT_ASCII = """Prose before call.

<|DSML|>
<invoke name="Read">
<parameter name="path" string="true">/test/path.py</parameter>
</|DSML|>
Prose after call.
"""

RAW_INPUT_BOTH_CLOSES = """Testing both closes.

<｜｜DSML｜｜>
<invoke name="Write">
<parameter name="path" string="true">/test/file.txt</parameter>
<parameter name="content" string="true">hello world</parameter>
</invoke>
</｜｜DSML｜｜>
"""

RAW_INPUT_MULTIPLE_INVOKES = """Multiple invokes in bare DSML.

<｜｜DSML｜｜>
<invoke name="Read">
<parameter name="path" string="true">a.txt</parameter>
</invoke>
<invoke name="Shell">
<parameter name="command" string="true">ls -la</parameter>
</｜｜DSML｜｜>
"""

TOOL_NAMES = ["Shell", "Read", "Write", "Grep"]


class TestBareDsmlWrapper:
    def test_parse_dsml_tool_calls_extracts_invoke(self):
        calls, cleaned = parse_dsml_tool_calls(RAW_INPUT, TOOL_NAMES)
        assert len(calls) == 1, f"Expected 1 tool call, got {calls}"
        assert calls[0]["name"] == "Shell"
        args = json.loads(calls[0]["arguments"])
        assert args["command"] == "python -m pytest tests/ -q 2>&1"
        assert args["working_directory"] == "F:\\PROJEKTY\\vinted\\bot_v2"
        assert "<|DSML|>" not in cleaned
        assert "<｜｜DSML｜｜>" not in cleaned
        assert "All files compile" in cleaned

    def test_stream_sieve_detects_and_emits_tool_calls(self):
        sieve = StreamSieve(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_INPUT), 10):
            events.extend(sieve.feed(RAW_INPUT[i : i + 10]))
        events.extend(sieve.flush())

        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) == 1, f"Expected 1 tool_calls event, got {events}"
        assert tc_events[0].data[0]["name"] == "Shell"

    def test_stream_handler_e2e_no_leak_and_emits_tool_call(self):
        handler = StreamHandler(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_INPUT), 12):
            events.extend(handler.feed(RAW_INPUT[i : i + 12]))
        events.extend(handler.flush())

        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) == 1, f"Expected 1 tool_calls event, got {events}"
        assert tc_events[0]["data"][0]["name"] == "Shell"

        text_content = "".join(e["data"] for e in events if e["type"] == "text")
        assert "All files compile. Now run the unit tests." in text_content
        assert "<|DSML|>" not in text_content
        assert "<｜｜DSML｜｜>" not in text_content
        assert "<invoke" not in text_content

    @pytest.mark.parametrize("chunk_size", [1, 3, 7, 15, 50])
    def test_various_chunk_sizes(self, chunk_size):
        handler = StreamHandler(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_INPUT), chunk_size):
            events.extend(handler.feed(RAW_INPUT[i : i + chunk_size]))
        events.extend(handler.flush())

        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) == 1
        assert tc_events[0]["data"][0]["name"] == "Shell"

        text_content = "".join(e["data"] for e in events if e["type"] == "text")
        assert "<|DSML|>" not in text_content
        assert "<｜｜DSML｜｜>" not in text_content

    def test_ascii_pipes_variant(self):
        handler = StreamHandler(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_INPUT_ASCII), 8):
            events.extend(handler.feed(RAW_INPUT_ASCII[i : i + 8]))
        events.extend(handler.flush())

        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) == 1
        assert tc_events[0]["data"][0]["name"] == "Read"

        text_content = "".join(e["data"] for e in events if e["type"] == "text")
        assert "<|DSML|>" not in text_content
        assert "Prose before call." in text_content

    def test_both_closes_present(self):
        handler = StreamHandler(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_INPUT_BOTH_CLOSES), 10):
            events.extend(handler.feed(RAW_INPUT_BOTH_CLOSES[i : i + 10]))
        events.extend(handler.flush())

        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) == 1
        assert tc_events[0]["data"][0]["name"] == "Write"
        text_content = "".join(e["data"] for e in events if e["type"] == "text")
        assert "<|DSML|>" not in text_content

    def test_multiple_invokes_last_unclosed(self):
        handler = StreamHandler(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_INPUT_MULTIPLE_INVOKES), 10):
            events.extend(handler.feed(RAW_INPUT_MULTIPLE_INVOKES[i : i + 10]))
        events.extend(handler.flush())

        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) >= 1
        call_names = [call["name"] for e in tc_events for call in e["data"]]
        assert "Read" in call_names
        assert "Shell" in call_names
        text_content = "".join(e["data"] for e in events if e["type"] == "text")
        assert "<|DSML|>" not in text_content
