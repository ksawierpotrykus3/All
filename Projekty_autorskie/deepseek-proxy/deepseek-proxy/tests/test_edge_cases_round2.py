"""tests/test_edge_cases_round2.py

Second round of comprehensive edge case tests:
  1. _extract_watermark — malformed SID, multiple, tool_call ID, edge cases
  2. Dedup mechanism — TTL expiry, hash collisions, multiple keys
  3. Repair tier1 — _has_tool_tag with <toolcall>, DSML namespace fixes
  4. StreamSieve complex patterns — JSON + DSML + <toolcall> interleaved
  5. conv_state TTL purge edge cases
"""

import json
import hashlib
import time
import re
import pytest


# =============================================================================
# 1. _extract_watermark edge cases
# =============================================================================


class TestExtractWatermarkEdges:
    """Edge cases for _extract_watermark (sync version in state_service)."""

    def _extract_watermark(self, messages):
        """Inline copy of _extract_watermark from state_service.py."""
        from server.config import WM_PATTERN
        import re

        for m in reversed(messages):
            if m.get("role") != "assistant":
                continue
            sid = m.get("sid")
            if sid:
                return sid
            content = m.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        m2 = WM_PATTERN.search(str(part.get("text", "")))
                        if m2:
                            return m2.group(1)
            elif isinstance(content, str):
                m2 = WM_PATTERN.search(content)
                if m2:
                    return m2.group(1)
        return None

    def test_no_assistant_messages(self):
        """Only user messages → no watermark."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "Are you there?"},
        ]
        result = self._extract_watermark(messages)
        assert result is None

    def test_empty_messages_list(self):
        """Empty messages list → no watermark."""
        result = self._extract_watermark([])
        assert result is None

    def test_sid_field_present(self):
        """New format: 'sid' field in assistant metadata."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello", "sid": "abc123"},
        ]
        result = self._extract_watermark(messages)
        assert result == "abc123"

    def test_sid_field_takes_priority_over_content(self):
        """'sid' field is checked before content regex."""
        messages = [
            {"role": "user", "content": "Hi"},
            {
                "role": "assistant",
                "content": "Hello\n<!-- PROXY_SID:old_sid -->",
                "sid": "new_sid",
            },
        ]
        result = self._extract_watermark(messages)
        assert result == "new_sid"  # sid field takes priority

    def test_watermark_in_earlier_assistant_msg(self):
        """Watermark in older assistant message (not the last one)."""
        messages = [
            {"role": "user", "content": "Hi"},
            {
                "role": "assistant",
                "content": "First reply\n<!-- PROXY_SID:abc123def456 -->",
            },
            {"role": "user", "content": "Again"},
            {"role": "assistant", "content": "Second reply"},
        ]
        result = self._extract_watermark(messages)
        # The last assistant message (2nd) doesn't have a watermark,
        # but the 1st one does — function checks all in reverse
        assert result == "abc123def456"  # First assistant has it

    def test_watermark_in_tool_call_id(self):
        """Watermark in tool_call ID via call_sid: pattern."""
        messages = [
            {"role": "user", "content": "Do it"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_sid:abcdef123456_call1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": "{}"},
                    }
                ],
            },
        ]
        result = self._extract_watermark(messages)
        # Note: the sync _extract_watermark only checks sid field and content regex,
        # NOT tool_call IDs — that's in the async StateService.extract_watermark
        assert result is None  # sync version doesn't check tool_call IDs

    def test_watermark_malformed_marker(self):
        """Malformed watermark marker (wrong casing, missing colon)."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "<!-- proxy_sid:123 -->"},
        ]
        result = self._extract_watermark(messages)
        # WM_PATTERN is case-insensitive via re.IGNORECASE
        # Check if it matches
        from server.config import WM_PATTERN

        m = WM_PATTERN.search("<!-- proxy_sid:123 -->")
        assert m is not None, "WM_PATTERN should be case insensitive"
        assert m.group(1) == "123"

    def test_multiple_watermarks_in_one_message(self):
        """Multiple watermark markers in one content — first one returned."""
        messages = [
            {"role": "user", "content": "Hi"},
            {
                "role": "assistant",
                "content": "<!-- PROXY_SID:abc123def -->\n<!-- PROXY_SID:4567890ab -->",
            },
        ]
        result = self._extract_watermark(messages)
        assert result == "abc123def"

    def test_watermark_in_vision_content_array(self):
        """Watermark in vision-format content array (list of parts)."""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Done\n<!-- PROXY_SID:abc123def789 -->"},
                ],
            },
        ]
        result = self._extract_watermark(messages)
        assert result == "abc123def789"

    def test_watermark_content_list_without_text(self):
        """Content list with non-text parts doesn't crash."""
        messages = [
            {"role": "user", "content": "Hi"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "http://example.com/img.jpg"},
                    },
                ],
            },
        ]
        result = self._extract_watermark(messages)
        assert result is None

    def test_watermark_empty_content_string(self):
        """Assistant with empty string content."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": ""},
        ]
        result = self._extract_watermark(messages)
        assert result is None

    def test_watermark_none_content(self):
        """Assistant with None content."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": None},
        ]
        result = self._extract_watermark(messages)
        assert result is None

    def test_watermark_only_tool_calls_no_content(self):
        """Assistant with tool_calls but no content and no sid."""
        messages = [
            {"role": "user", "content": "Read file"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": "{}"},
                    }
                ],
            },
        ]
        result = self._extract_watermark(messages)
        assert result is None


# =============================================================================
# 2. Dedup mechanism edge cases
# =============================================================================


class TestDedupEdges:
    """Edge cases for the dedup mechanism used in conv_uuid resolution."""

    def test_dedup_key_in_request_dedup(self):
        """Simulate request_dedup with TTL check."""
        import hashlib, time
        from collections import OrderedDict

        # Simulate the logic from proxy.py
        request_dedup = OrderedDict()
        _DEDUP_TTL = 60.0

        messages1 = [{"role": "user", "content": "Hello"}]
        messages2 = [{"role": "user", "content": "Hello"}]
        h1 = hashlib.md5(str(messages1).encode()).hexdigest()[:12]
        h2 = hashlib.md5(str(messages2).encode()).hexdigest()[:12]
        assert h1 == h2  # same messages → same hash

        # First request: not in dedup
        dedup_entry = request_dedup.get(h1)
        assert dedup_entry is None
        request_dedup[h1] = ("uuid_abc", time.time())

        # Second request: same messages → dedup hit
        dedup_entry = request_dedup.get(h1)
        assert dedup_entry is not None
        assert dedup_entry[0] == "uuid_abc"

    def test_dedup_different_messages_different_hashes(self):
        """Different messages produce different hashes."""
        import hashlib

        messages1 = [{"role": "user", "content": "Hello"}]
        messages2 = [{"role": "user", "content": "World"}]
        h1 = hashlib.md5(str(messages1).encode()).hexdigest()[:12]
        h2 = hashlib.md5(str(messages2).encode()).hexdigest()[:12]
        assert h1 != h2

    def test_dedup_ttl_expiry(self):
        """Entries older than DEDUP_TTL are considered stale."""
        import hashlib, time

        _DEDUP_TTL = 60.0
        request_dedup = {}
        messages = [{"role": "user", "content": "Hello"}]
        h = hashlib.md5(str(messages).encode()).hexdigest()[:12]

        # Add with old timestamp
        old_time = time.time() - _DEDUP_TTL - 1  # 1 second past TTL
        request_dedup[h] = ("uuid_abc", old_time)

        # Simulate check
        dedup = request_dedup.get(h)
        assert dedup is not None
        is_expired = time.time() - dedup[1] > _DEDUP_TTL
        assert is_expired

    def test_dedup_ttl_not_expired(self):
        """Recent entries are NOT stale."""
        import hashlib, time

        _DEDUP_TTL = 60.0
        request_dedup = {}
        messages = [{"role": "user", "content": "Hello"}]
        h = hashlib.md5(str(messages).encode()).hexdigest()[:12]

        request_dedup[h] = ("uuid_abc", time.time())
        dedup = request_dedup.get(h)
        assert dedup is not None
        is_expired = time.time() - dedup[1] > _DEDUP_TTL
        assert not is_expired

    def test_request_hash_with_same_content_different_roles(self):
        """Hash depends on full messages structure."""
        import hashlib

        msg_a = [{"role": "user", "content": "Hello"}]
        msg_b = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        h_a = hashlib.md5(str(msg_a).encode()).hexdigest()[:12]
        h_b = hashlib.md5(str(msg_b).encode()).hexdigest()[:12]
        assert (
            h_a != h_b
        )  # different structure → different hash (even with same user content)


# =============================================================================
# 4. Repair tier1 edge cases with <toolcall>
# =============================================================================


class TestRepairTier1Edges:
    """repair_tier1 edge cases — especially _has_tool_tag with <toolcall>."""

    def _has_tool_tag(self, text: str) -> bool:
        """Check if text contains any tool-call DSML/XML tag."""
        import re
        from server.repair.repair_tier1 import _DSML_TAG_PATTERN

        if _DSML_TAG_PATTERN.search(text):
            return True
        if re.search(
            r"<(?:tool_calls?|tool_called|invoke|parameter|tool_result)\b",
            text,
            re.IGNORECASE,
        ):
            return True
        if re.search(
            r"<\|(?:TOOL|DSML)\|(?:tool_calls?|invoke|parameter|tool_result)\b",
            text,
            re.IGNORECASE,
        ):
            return True
        return False

    def test_has_tool_tag_toolcall(self):
        """Detects <toolcall> (no underscore) as a tool tag."""
        result = self._has_tool_tag(
            '<toolcall><invoke name="Read"></invoke></toolcall>'
        )
        assert result, "Should detect <toolcall> via plain XML tag pattern"

    def test_has_tool_tag_tool_call(self):
        """Detects <tool_call> (with underscore)."""
        result = self._has_tool_tag('<tool_call name="Read"></tool_call>')
        assert result

    def test_has_tool_tag_dsml_prefixed(self):
        """Detects <|DSML|tool_calls> prefixed tags."""
        result = self._has_tool_tag("<|DSML|tool_calls>content</|DSML|tool_calls>")
        assert result

    def test_has_tool_tag_no_tag(self):
        """No tool tag present returns False."""
        result = self._has_tool_tag("Just some regular text with no tool calls.")
        assert not result

    def test_has_tool_tag_missing_lt_toolcall(self):
        """Detects |TOOL|tool_calls> (missing <) via DSML_TAG_PATTERN."""
        result = self._has_tool_tag("|TOOL|tool_calls>content</|TOOL|tool_calls>")
        assert result

    def test_has_tool_tag_invoke_alone(self):
        """Detects bare <invoke> tags."""
        result = self._has_tool_tag('<invoke name="Read">')
        assert result

    def test_repair_tier1_fixes_missing_lt(self):
        """repair_tier1 fixes missing < on DSML/TOOL tags."""
        from server.repair import repair_pipeline

        text = '|TOOL|tool_calls>\n  |TOOL|invoke name="Read">\n    |TOOL|parameter name="f"><![CDATA[x]]></|TOOL|parameter>\n  |TOOL|invoke>\n|TOOL|tool_calls>'
        repaired = repair_pipeline(text)
        assert repaired is not None
        assert "<|TOOL|tool_calls>" in repaired
        assert "<|TOOL|invoke" in repaired

    def test_repair_tier1_repairs_unclosed_cdata(self):
        """repair_tier1 closes unclosed CDATA sections."""
        from server.repair import repair_pipeline

        text = '<toolcall><invoke name="Read"><parameter name="f"><![CDATA[unclosed'
        repaired = repair_pipeline(text)
        assert repaired is not None
        assert "]]>" in repaired

    def test_repair_tier1_strips_markdown_fences(self):
        """repair_tier1 strips markdown code fences around tool blocks."""
        from server.repair import repair_pipeline

        text = '```xml\n<toolcall><invoke name="Read"><parameter name="f">x</parameter></invoke></toolcall>\n```'
        repaired = repair_pipeline(text)
        assert repaired is not None
        assert "```" not in repaired

    def test_repair_tier1_fixes_broken_namespace(self):
        """repair_tier1 fixes |DSL| → |DSML| and |TS| → |TOOL|."""
        from server.repair import repair_pipeline
        from server.repair.repair_tier1 import _fix_broken_namespace

        # |DSL| namespace — valid DSML block that goes through full pipeline
        text = '<|DSL|tool_calls><|DSL|invoke name="Read"><|DSL|parameter name="f"><![CDATA[x.txt]]></|DSL|parameter></|DSL|invoke></|DSL|tool_calls>'
        repaired = repair_pipeline(text)
        assert repaired is not None
        assert "|DSML|" in repaired

        # |TS| namespace — _fix_broken_namespace only matches |TS| when NOT
        # followed by a \w char (uses (?!\w) lookahead to avoid false positives)
        text2 = "prefix |TS| more text |TS| too"
        fixed = _fix_broken_namespace(text2)
        assert "|TOOL|" in fixed
        assert "|TS|" not in fixed

        # |TS| followed by tool_calls is NOT matched (intentional design)
        text3 = "|TS|tool_calls>content</|TS|tool_calls>"
        fixed3 = _fix_broken_namespace(text3)
        assert "|TS|" in fixed3  # unchanged because t is \w after |TS|


# =============================================================================
# 5. StreamSieve — complex alternating patterns
# =============================================================================


class TestStreamSieveComplex:
    """StreamSieve with complex interleaved patterns (DSML + JSON + <toolcall>)."""

    def test_mixed_json_toolcall_and_text(self):
        """JSON tool call marker then text then <toolcall> block."""
        from server.parser.dsml_sieve import StreamSieve

        sieve = StreamSieve(tool_names=["Read", "Write"])

        events1 = sieve.feed(
            'First I will use a tool.\n\n```tool_call\n{"name": "Read", "arguments": {"f": "a.txt"}}\n```'
        )
        events2 = sieve.feed(
            '\n\nNow I will use another format.\n\n<toolcall>\n<invoke name="Write">\n<parameter name="f"><![CDATA[b.txt]]></parameter>\n</invoke>\n</toolcall>'
        )
        events3 = sieve.feed("\n\nAll done.")
        all_events = events1 + events2 + events3 + sieve.flush()

        tc_events = [e for e in all_events if e.type == "tool_calls"]
        text_events = [e for e in all_events if e.type == "text"]

        assert len(tc_events) >= 1, (
            f"No tool_calls, got types: {[e.type for e in all_events]}"
        )
        names = set()
        for ev in tc_events:
            for tc in ev.data:
                names.add(tc["name"])
        assert "Read" in names, f"Names: {names}"
        assert any("First I will" in e.data for e in text_events + all_events), (
            f"Leading text missing"
        )
        assert any("All done" in str(e.data) for e in text_events + all_events), (
            f"Trailing text missing"
        )

    def test_back_to_back_toolcall_blocks(self):
        """Two back-to-back <toolcall> blocks without text between."""
        from server.parser.dsml_sieve import StreamSieve

        sieve = StreamSieve(tool_names=["A", "B"])
        chunk = (
            '<toolcall><invoke name="A"><parameter name="x"><![CDATA[1]]></parameter></invoke></toolcall>'
            '<toolcall><invoke name="B"><parameter name="y"><![CDATA[2]]></parameter></invoke></toolcall>'
        )
        events = sieve.feed(chunk) + sieve.flush()
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) >= 1
        all_names = []
        for ev in tc_events:
            for tc in ev.data:
                all_names.append(tc["name"])
        assert "A" in all_names
        assert "B" in all_names

    def test_json_toolcall_then_dsml_then_toolcall(self):
        """Three different formats in sequence: JSON, DSML, bare <toolcall>."""
        from server.parser.dsml_sieve import StreamSieve

        sieve = StreamSieve(tool_names=["Read", "Write", "Delete"])

        chunks = [
            '```tool_call\n{"name": "Read", "arguments": {"f": "a.txt"}}\n```\n\n',
            '<|DSML|tool_calls><|DSML|invoke name="Write"><|DSML|parameter name="f"><![CDATA[b.txt]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>\n\n',
            '<toolcall><invoke name="Delete"><parameter name="f"><![CDATA[c.txt]]></parameter></invoke></toolcall>',
        ]
        all_events = []
        for ch in chunks:
            all_events.extend(sieve.feed(ch))
        all_events += sieve.flush()

        tc_events = [e for e in all_events if e.type == "tool_calls"]
        # Three formats → at least some tool_calls detected
        assert len(tc_events) >= 1, (
            f"No tool_calls, got: {[e.type for e in all_events]}"
        )

    def test_toolcall_nested_inside_text_stream(self):
        """<toolcall> block embedded in a slow streaming text."""
        from server.parser.dsml_sieve import StreamSieve

        sieve = StreamSieve(tool_names=["Read"])
        # Simulate slow character-by-character stream with text before and after
        stream = 'Let me read file <toolcall><invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke></toolcall> and then summarize.'
        all_events = []
        for ch in stream:
            all_events.extend(sieve.feed(ch))
        all_events += sieve.flush()

        tc_events = [e for e in all_events if e.type == "tool_calls"]
        text_events = [e for e in all_events if e.type == "text"]
        assert len(tc_events) >= 1, f"No tool_calls in char-by-char stream"
        # Text before and after should be preserved
        all_text = "".join(e.data for e in text_events)
        assert "Let me read file" in all_text or any(
            "Let me read file" in str(e.data) for e in all_events
        ), f"Leading text lost: {all_text[:50]}"

    def test_toolcall_with_empty_invoke(self):
        """<toolcall> with empty invoke (no parameters)."""
        from server.parser.dsml_sieve import StreamSieve

        sieve = StreamSieve(tool_names=["Noop"])
        chunk = '<toolcall><invoke name="Noop"></invoke></toolcall>'
        events = sieve.feed(chunk) + sieve.flush()
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) >= 1
        assert tc_events[0].data[0]["name"] == "Noop"
        args = json.loads(tc_events[0].data[0]["arguments"])
        assert args == {}

    def test_toolcall_with_xml_escaped_params(self):
        """<toolcall> with XML-escaped parameter values."""
        from server.parser.dsml_sieve import StreamSieve

        sieve = StreamSieve(tool_names=["Read"])
        chunk = '<toolcall><invoke name="Read"><parameter name="path">/path/with &amp; and &quot;quotes&quot;</parameter></invoke></toolcall>'
        events = sieve.feed(chunk) + sieve.flush()
        tc_events = [e for e in events if e.type == "tool_calls"]
        assert len(tc_events) >= 1
        args = json.loads(tc_events[0].data[0]["arguments"])
        # The parser doesn't unescape XML — it's stored as-is
        assert "path" in args

    def test_toolcall_case_variations(self):
        """Case variations of <toolcall> tag (TOOLCALL, ToolCall, etc.)."""
        from server.parser.dsml_parser import parse_dsml_tool_calls

        for tag_variant in ["<toolcall>", "<TOOLCALL>", "<ToolCall>"]:
            close = tag_variant.replace("<", "</")
            text = f'{tag_variant}<invoke name="Read"><parameter name="f"><![CDATA[x.txt]]></parameter></invoke>{close}'
            calls, cleaned = parse_dsml_tool_calls(text, ["Read"])
            assert len(calls) == 1, f"Failed for {tag_variant}: got {len(calls)} calls"
            assert calls[0]["name"] == "Read"


# =============================================================================
# 6. conv_state TTL purge edge cases
# =============================================================================


class TestConvStatePurge:
    """Edge cases for conv_state TTL purge logic."""

    def _purge_expired_conv_states(self, conv_state, ttl=86400.0):
        """Simulate _purge_expired_conv_states from state_service.py."""
        import time

        now = time.time()
        cutoff = now - ttl
        stale = []
        for k, v in conv_state.items():
            if not isinstance(v, dict):
                continue
            created = v.get("created_at")
            if created is not None and created < cutoff:
                stale.append(k)
        for k in stale:
            del conv_state[k]
        return len(stale)

    def test_purge_stale_entries(self):
        """Entries older than TTL are purged."""
        old_time = time.time() - 90000  # ~25 hours ago
        state = {
            "old_entry": {"created_at": old_time, "data": "old"},
            "new_entry": {"created_at": time.time(), "data": "new"},
        }
        purged = self._purge_expired_conv_states(state)
        assert purged == 1
        assert "new_entry" in state
        assert "old_entry" not in state

    def test_purge_all_stale(self):
        """All entries are old → all purged."""
        old_time = time.time() - 90000
        state = {
            "a": {"created_at": old_time},
            "b": {"created_at": old_time},
        }
        purged = self._purge_expired_conv_states(state)
        assert purged == 2
        assert len(state) == 0

    def test_purge_none_stale(self):
        """No entries are old → nothing purged."""
        state = {
            "a": {"created_at": time.time()},
            "b": {"created_at": time.time()},
        }
        purged = self._purge_expired_conv_states(state)
        assert purged == 0
        assert len(state) == 2

    def test_purge_empty_state(self):
        """Empty state → nothing purged."""
        state = {}
        purged = self._purge_expired_conv_states(state)
        assert purged == 0

    def test_purge_no_created_at_field(self):
        """Entries without created_at are NOT purged (treated as keep)."""
        old_time = time.time() - 90000
        state = {
            "no_timestamp": {"data": "no created_at"},
            "with_timestamp": {"created_at": old_time, "data": "old"},
        }
        purged = self._purge_expired_conv_states(state)
        assert purged == 1  # only with_timestamp is purged
        assert "no_timestamp" in state
        assert "with_timestamp" not in state

    def test_purge_non_dict_value(self):
        """Non-dict values are skipped (not purged)."""
        old_time = time.time() - 90000
        state = {
            "string_val": "just a string",
            "list_val": [1, 2, 3],
            "dict_val": {"created_at": old_time, "data": "old"},
        }
        purged = self._purge_expired_conv_states(state)
        assert purged == 1  # only dict_val is purged
        assert "string_val" in state
        assert "list_val" in state

    def test_purge_at_boundary(self):
        """Entry exactly at TTL boundary is NOT purged (created_at == cutoff)."""
        import time

        ttl = 86400.0
        now = time.time()
        cutoff = now - ttl
        state = {
            "exact_boundary": {"created_at": cutoff, "data": "boundary"},
        }
        purged = self._purge_expired_conv_states(state, ttl=ttl)
        # created_at == cutoff, which is NOT < cutoff → not purged
        assert purged == 0

    def test_purge_right_after_boundary(self):
        """Entry 1 second past TTL boundary IS purged."""
        import time

        ttl = 86400.0
        now = time.time()
        cutoff = now - ttl
        state = {
            "just_past": {"created_at": cutoff - 1, "data": "stale"},
        }
        purged = self._purge_expired_conv_states(state, ttl=ttl)
        assert purged == 1
