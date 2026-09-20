"""tests/test_dsml_unclosed_parameter.py — Test for DSML blocks where parameter and invoke are closed by </tool_calls>.

Model generates:
  <｜｜DSML｜｜tool_calls>
  <｜｜DSML｜｜invoke name="StrReplace">
  <｜｜DSML｜｜parameter name="path" string="true">...</｜｜DSML｜｜parameter>
  <｜｜DSML｜｜parameter name="old_string" string="true">...code...</｜｜DSML｜｜tool_calls>
  </｜｜DSML｜｜tool_calls>

The old_string parameter has no </parameter>, invoke has no </invoke>,
and there are duplicated </tool_calls> tags.
Must emit StrReplace tool call and NOT leak markup or duplicated closing tags to IDE content.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from server.core.stream_handler import StreamHandler
from server.parser.dsml_parser import parse_dsml_tool_calls, clean_tool_text
from server.parser.dsml_sieve import StreamSieve


RAW_STRREPLACE_INPUT = """Now I have the full picture. Let me implement the fix across all files.

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="StrReplace">
<｜｜DSML｜｜parameter name="path" string="true">F:\\PROJEKTY\\vinted\\bot_v2\\src\\vintedbot2\\checkout.py</｜｜DSML｜｜parameter>
<｜｜DSML｜｜parameter name="old_string" string="true">def _extract_carrier(bj: dict) -> str | None:
\"\"\"Wyciąga last-mile carrier z odpowiedzi builda (dyskryminator cache punktu).

[UDOWODNIONE — Odkrycie 35] punkt stabilny per (adres odbiorcy + last-mile carrier).
Preferujemy shipping_option.last_mile_carrier.code; fallback carrier_code.
\"\"\"
pd = (((bj.get("checkout") or {}).get("components") or {})
.get("shipping_pickup_details") or {}).get("pickup_details") or {}
so = pd.get("shipping_option") or {}
lm = (so.get("last_mile_carrier") or {}).get("code")
return lm or so.get("carrier_code")</｜｜DSML｜｜tool_calls>
</｜｜DSML｜｜tool_calls>
"""

TOOL_NAMES = ["Shell", "Glob", "Grep", "Read", "Write", "StrReplace"]


class TestUnclosedParameterAndInvoke:
    def test_parse_dsml_tool_calls_recovers_strreplace(self):
        calls, cleaned = parse_dsml_tool_calls(RAW_STRREPLACE_INPUT, TOOL_NAMES)
        assert len(calls) == 1, f"Expected 1 tool call, got {calls}"
        assert calls[0]["name"] == "StrReplace"
        args = json.loads(calls[0]["arguments"])
        assert "checkout.py" in args["path"]
        assert "def _extract_carrier" in args["old_string"]
        assert "return lm or so.get" in args["old_string"]
        assert "tool_calls" not in cleaned
        assert "<|DSML|" not in cleaned
        assert "<｜｜DSML｜｜" not in cleaned

    def test_stream_sieve_detects_and_emits_tool_calls(self):
        sieve = StreamSieve(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_STRREPLACE_INPUT), 12):
            events.extend(sieve.feed(RAW_STRREPLACE_INPUT[i : i + 12]))
        events.extend(sieve.flush())

        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) == 1, f"Expected 1 tool_calls event, got {events}"
        assert tc_events[0].data[0]["name"] == "StrReplace"

    def test_stream_handler_e2e_emits_tool_call_without_leak(self):
        handler = StreamHandler(tool_names=TOOL_NAMES)
        events = []
        for i in range(0, len(RAW_STRREPLACE_INPUT), 15):
            events.extend(handler.feed(RAW_STRREPLACE_INPUT[i : i + 15]))
        events.extend(handler.flush())

        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) == 1, f"Expected 1 tool_calls event, got {events}"
        assert tc_events[0]["data"][0]["name"] == "StrReplace"

        text_content = "".join(e["data"] for e in events if e["type"] == "text")
        assert "Now I have the full picture." in text_content
        assert "tool_calls" not in text_content
        assert "<|DSML|" not in text_content
        assert "<｜｜DSML｜｜" not in text_content
        assert "<invoke" not in text_content
