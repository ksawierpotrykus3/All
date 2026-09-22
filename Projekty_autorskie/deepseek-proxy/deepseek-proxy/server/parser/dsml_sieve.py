"""server/parser/dsml_sieve.py — StreamSieve: real-time DSML tool call detection in streaming chunks.

Detects <|DSML|tool_calls> blocks in character streams, buffers them,
and emits SieveEvent objects when a complete block is parsed.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from server.repair import repair_pipeline
from server.repair.repair_tier1 import _DAMAGED_INVOKE_OPENER_RE
from server.logging import get_logger

logger = get_logger(__name__)


# Normaliser for the alternative DSML close-tag ordering that DeepSeek
# Pro emits: ``<|DSML|/invoke>`` (slash AFTER marker) instead of the
# canonical ``</|DSML|invoke>`` (slash BEFORE marker).  Run as a cheap
# pre-pass over every chunk so downstream regexes see one canonical form.
_INV_DSML_CLOSE_RE = re.compile(
    r"<(\|(?:TOOL|DSML)\|)/(tool_calls?|invoke|parameter|tool_result)\s*>",
    re.IGNORECASE,
)
_LT = chr(60)
_SL = chr(47)
_GT = chr(62)

# A trailing fragment of a damaged <invoke opener (the model drops the '<inv'
# prefix, so the opener arrives as 'oke name="X">').  _split_safe holds such
# trailing fragments back so they aren't emitted as prose before the opener
# completes and capture can begin.
_DAMAGED_OPENER_FRAGMENT_RE = re.compile(
    r"(?<![\w<])oke(?:\s+na?m?e?)?(?:=\s*[\"']?[^\"'\r\n]*)?$",
)

_PARAM_BLOCK_RE = re.compile(
    r"<(?:\|?(?:TOOL|DSML)\|?)?parameter\b[^>]*>.*?</(?:\|?(?:TOOL|DSML)\|?)?parameter\s*>",
    re.DOTALL | re.IGNORECASE,
)
_CDATA_RE = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)



def _normalize_inverted_dsml_close(text: str) -> str:
    """Reorder slash-before/after-marker for DSML/TOOL closing tags.

    DeepSeek Pro sometimes emits ``<|DSML|/invoke>`` (slash AFTER
    marker) instead of the canonical ``</|DSML|invoke>`` (slash BEFORE).
    All existing regex patterns in this module expect the slash BEFORE
    the marker, so we normalise up-front.
    """
    if not text:
        return text
    return _INV_DSML_CLOSE_RE.sub(
        lambda m: _LT + _SL + m.group(1) + m.group(2) + _GT,
        text,
    )


@dataclass
class SieveEvent:
    """Event emitted by StreamSieve."""

    type: str  # "text" | "tool_calls"
    data: Any  # str for text, list[dict] for tool_calls


TOOL_STARTS = [
    "<|DSML|tool_calls>",
    "|DSML|tool_calls>",  # model sometimes drops opening <
    "<|TOOL|tool_calls>",
    "|TOOL|tool_calls>",
    "<tool_calls>",
    # Double full-width pipe variants (defense in depth if normalization misses)
    "<｜｜DSML｜｜tool_calls>",
    "｜DSML｜tool_calls>",
    "<｜｜TOOL｜｜tool_calls>",
    "｜TOOL｜tool_calls>",
    # _collection wrapper (Trae todo list format)
    "<｜｜DSML｜｜_collection>",
    "｜DSML｜_collection>",
    "<|DSML|tool_dispatch>",
    "|DSML|tool_dispatch>",
    "<|TOOL|tool_dispatch>",
    "|TOOL|tool_dispatch>",
    "<tool_dispatch>",
    "<tool_call>",
    "<tool_call ",  # model uses <tool_call name="X">
    "<tool_call\n",  # model uses <tool_call\n  name="X">
    "<toolcall>",  # model sometimes drops underscore: <toolcall>
    "<toolcall ",  # model sometimes drops underscore: <toolcall name="X">
    "<invoke ",  # bare <invoke name="X"> without wrapper
    "<invoke\n",  # bare <invoke\n name="X">
    "<invoke>",  # invoke without attributes (self-closing)
    "<|DSML|invoke ",
    "|DSML|invoke ",  # model sometimes drops opening <
    "<|TOOL|invoke ",
    "|TOOL|invoke ",
    "<tool_use_json>",
    "<tool_use_json ",
    "<function_call>",
    "<function_call ",
    "<function_calls>",
    "<function_calls ",
    "<argument ",  # parameter tags like <file_path>
    "<tool_result>",  # tool result tag
    "<tool_result ",  # tool result tag with attrs
    "<|begin▁of▁sentence｜>",  # BOS token leak
    "<|Assistant｜>",  # role leak
    "<|assistant｜>",
    "<thinking>",  # deepseek thinking tag
    "<use_mcp_tool",  # trae MCP tool call format
    # Bracket tool call markers (Chinese & English invoke formats)
    "[调用",
    "【调用",
    "[call ",
    "[invoke ",
]

_TRAILING_BRACKET_OPENER_RE = re.compile(
    r'(?:\[|【)\s*(?:调用|call|invoke)(?:[:：]?\s*[a-zA-Z0-9_\-\.]*)?$',
    re.IGNORECASE,
)

# JSON format markers (CO-STAR mode)
JSON_TOOL_START = "```tool_call"
JSON_TOOL_END = "```"

# Max capture buffer size — abandon capture if exceeded (prevents OOM / regex slowdown)
_MAX_CAPTURE_BUF_SIZE = 500_000

# Note: _is_capture_complete checks for a matching close tag based on
# which opening tag was found. CLOSE_TAGS here lists all possible
# close tags for extracting post-wrapper text in _extract_post_wrapper.
CLOSE_TAGS = [
    "</|DSML|tool_calls>",
    "</|TOOL|tool_calls>",
    "</tool_calls>",
    # Double/single full-width pipe variants (defense in depth)
    "</｜｜DSML｜｜tool_calls>",
    "</｜DSML｜tool_calls>",
    "</｜｜TOOL｜｜tool_calls>",
    "</｜TOOL｜tool_calls>",
    "</|DSML|tool_dispatch>",
    "</|TOOL|tool_dispatch>",
    "</tool_dispatch>",
    "</｜｜DSML｜｜tool_dispatch>",
    "</｜DSML｜tool_dispatch>",
    "</｜｜TOOL｜｜tool_dispatch>",
    "</｜TOOL｜tool_dispatch>",
    "再再",
    "</toolcall>",
    "</tool_called>",
    "</tool_use_json>",
    "</function_call>",
    "</function_calls>",
    "</tool_call>",
    "</invoke>",
    "</｜｜DSML｜｜invoke>",
    "</｜DSML｜invoke>",
    "</｜｜TOOL｜｜invoke>",
    "</｜TOOL｜invoke>",
    "</parameter>",
    "</|DSML|parameter>",
    "</|TOOL|parameter>",
    "</｜｜DSML｜｜parameter>",
    "</｜DSML｜parameter>",
    "</use_mcp_tool>",
    "</tool_result>",
]


# Trailing fragments of broken tool-tag openers/closers that the model
# emits right before a valid capture start (e.g. '_calls>' from a malformed
# '<tool_calls>' opener).  When a capture begins, such debris in the
# preceding text is dropped instead of being emitted as prose (it would
# otherwise pollute assistant content in client history).
_DEBRIS_MIN_LEN = 6
_TAG_DEBRIS_SUFFIXES = sorted(
    {
        tag[i:]
        for tag in (TOOL_STARTS + CLOSE_TAGS)
        for i in range(1, len(tag) - _DEBRIS_MIN_LEN + 1)
        if tag[i:].endswith(">")
    },
    key=len,
    reverse=True,
)


def _strip_tag_debris(prefix: str) -> str:
    """Drop a trailing broken-tag fragment from text emitted immediately
    before a tool-call capture starts.

    Example: model emits ``_calls>\\n<invoke name="X">...`` (malformed
    ``<tool_calls>`` opener) — the sieve starts the capture at ``<invoke``
    and would otherwise emit ``_calls>\\n`` as a text event.
    """
    core = prefix.rstrip()
    if not core:
        return prefix
    for suf in _TAG_DEBRIS_SUFFIXES:
        if core.endswith(suf):
            return prefix[: len(core) - len(suf)]
    return prefix


class StreamSieve:
    """DSML mode stream sieve — separates text from DSML tool call blocks in real-time."""

    def __init__(self, tool_names: Optional[List[str]] = None):
        self.tool_names = tool_names or []
        self._pending = ""
        self._capture_buf = ""
        self._capturing = False
        self._json_capturing = False
        self._json_capture_buf = ""

    def feed(self, chunk: str) -> List[SieveEvent]:
        events: List[SieveEvent] = []
        # Normalise DSML markup BEFORE any tag detection.  DeepSeek Pro
        # emits: double full-width pipes (``<｜｜DSML｜｜invoke>``), a ``_calls``
        # wrapper instead of ``tool_calls``, and inverted close tags
        # (``<|DSML|/invoke>``).  Normalise all of them up-front so
        # TOOL_STARTS / CLOSE_TAGS / regexes see one canonical form.
        from server.parser.dsml_parser import (
            _normalize_tag_delimiters,
            _fix_missing_lt,
        )

        chunk = _normalize_tag_delimiters(chunk)
        chunk = _normalize_inverted_dsml_close(chunk)
        # NOTE: _fix_missing_lt is NOT applied per-chunk — it is context-blind
        # (prepends '<' to a fragment at position 0 even when the previous
        # chunk already ended with '<' / '</', producing a doubled '<').
        # It runs on merged pending / capture buffers only (see below).
        if not chunk:
            # Process JSON capture buffer if in the middle of capturing
            if self._json_capturing:
                from server.parser.dsml_parser import (
                    parse_json_tool_calls,
                    clean_tool_call_markers,
                )

                jtc, cleaned = parse_json_tool_calls(self._json_capture_buf)
                if jtc:
                    events.append(SieveEvent("tool_calls", jtc))
                elif cleaned:
                    has_tool_marker = bool(
                        re.match(r"^\s*```(?:tool_call|json)", self._json_capture_buf)
                    )
                    if has_tool_marker:
                        events.append(
                            SieveEvent("text", clean_tool_call_markers(cleaned))
                        )
                    else:
                        events.append(SieveEvent("text", cleaned))
                self._json_capturing = False
                self._json_capture_buf = ""
            if self._pending:
                events.append(SieveEvent("text", self._pending))
                self._pending = ""
            return events

        if self._capturing:
            self._capture_buf += chunk
            # Abandon capture if buffer exceeds limit (prevents OOM / regex backtracking)
            if len(self._capture_buf) > _MAX_CAPTURE_BUF_SIZE:
                logger.info(
                    f"[SIEVE_DIAG] CAPTURE ABANDONED: buf exceeded {_MAX_CAPTURE_BUF_SIZE}"
                )
                events.append(SieveEvent("text", self._capture_buf))
                self._capture_buf = ""
                self._capturing = False
                return events
            result = self._try_finish_capture()
            if result is not None:
                events = self._process_capture_result(result, events)
                # Diagnostic: log capture completion
                _tool_names_str = ",".join(
                    getattr(tc, "get", lambda k, d=None: d)("name", "?")
                    for tc in (result[1] or [])
                )
                logger.info(
                    f"[SIEVE_DIAG] CAPTURE COMPLETE! calls={result[1] and len(result[1])} names={_tool_names_str}"
                )
            return events

        self._pending += chunk
        # Re-normalize the whole pending buffer: chunks are normalized
        # individually above, so tag regions split across chunk boundaries
        # (e.g. ``<｜｜`` + ``tool_calls>``) may still contain raw full-width
        # or double pipes.  Normalizing the merged text gives the detection
        # below one canonical form.  Positions stay aligned because
        # _normalize_tag_delimiters / _fix_missing_lt only touch tag regions.
        self._pending = _normalize_tag_delimiters(self._pending)
        self._pending = _fix_missing_lt(self._pending)

        # JSON tool call detection (CO-STAR mode)
        if not self._capturing:
            if self._json_capturing:
                self._json_capture_buf += chunk
                if not self._is_json_candidate(self._json_capture_buf):
                    events.append(SieveEvent("text", self._json_capture_buf))
                    self._json_capture_buf = ""
                    self._json_capturing = False
                    self._pending = ""
                    return events
                # Abandon JSON capture if buffer exceeds limit
                if len(self._json_capture_buf) > _MAX_CAPTURE_BUF_SIZE:
                    events.append(SieveEvent("text", self._json_capture_buf))
                    self._json_capture_buf = ""
                    self._json_capturing = False
                    self._pending = ""
                    return events
                self._pending = (
                    ""  # Clear pending to prevent re-triggering JSON mode on next chunk
                )
                # Process all complete JSON blocks in the buffer (handles back-to-back)
                from server.parser.dsml_parser import parse_json_tool_calls

                while True:
                    # Search for JSON_TOOL_END only after the opening marker
                    end_pos = self._json_capture_buf.find(
                        JSON_TOOL_END, len(JSON_TOOL_START)
                    )
                    if end_pos < 0:
                        break  # No complete block yet
                    # Extract the complete block (marker + json + closing ```)
                    complete_block = self._json_capture_buf[
                        : end_pos + len(JSON_TOOL_END)
                    ]
                    jtc, _ = parse_json_tool_calls(complete_block)
                    if jtc:
                        events.append(SieveEvent("tool_calls", jtc))
                        rest = self._json_capture_buf[
                            end_pos + len(JSON_TOOL_END) :
                        ].lstrip("\n\r")
                    else:
                        events.append(SieveEvent("text", complete_block))
                        rest = self._json_capture_buf[end_pos + len(JSON_TOOL_END) :]
                    if not rest:
                        self._json_capturing = False
                        self._json_capture_buf = ""
                        break
                    # Check if rest contains another tool call marker
                    js_pos = rest.find(JSON_TOOL_START)
                    if js_pos >= 0:
                        if rest[:js_pos]:
                            events.append(SieveEvent("text", rest[:js_pos]))
                        self._json_capture_buf = rest[js_pos:]
                        # Continue loop to check if this block is also complete
                    else:
                        # Rest doesn't contain JSON tool call — check for DSML tool starts
                        if rest and self._find_tool_start(rest) >= 0:
                            self._json_capturing = False
                            self._json_capture_buf = ""
                            self._pending = rest
                            self._pending = _normalize_tag_delimiters(self._pending)
                            self._pending = _fix_missing_lt(self._pending)
                            # Fall through to DSML detection below
                            break
                        if rest:
                            events.append(SieveEvent("text", rest))
                        self._json_capturing = False
                        self._json_capture_buf = ""
                        break
                # After JSON capturing ends, check for DSML tool calls in pending
                if not self._json_capturing and not self._capturing and self._pending:
                    start_idx = self._find_tool_start(self._pending)
                    if start_idx >= 0:
                        prefix = _strip_tag_debris(self._pending[:start_idx])
                        rest_dsml = self._pending[start_idx:]
                        self._pending = ""
                        if prefix:
                            events.append(SieveEvent("text", prefix))
                        self._capture_buf = rest_dsml
                        self._capturing = True
                        result = self._try_finish_capture()
                        if result is not None:
                            events = self._process_capture_result(result, events)
                return events

            # Check for JSON tool call start
            js_pos = self._pending.find(JSON_TOOL_START)
            if js_pos >= 0:
                candidate_buf = self._pending[js_pos:]
                if self._is_json_candidate(candidate_buf):
                    prefix = self._pending[:js_pos]
                    if prefix:
                        events.append(SieveEvent("text", prefix))
                    self._json_capturing = True
                    self._json_capture_buf = candidate_buf
                    self._pending = ""
                    return events

            # Check for plain ``` code fence as potential JSON tool call
            # (model sometimes uses ``` instead of ```tool_call)
            plain_fence_pos = self._pending.find("```")
            if plain_fence_pos >= 0:
                candidate_buf = self._pending[plain_fence_pos:]
                if self._is_json_candidate(candidate_buf):
                    prefix = self._pending[:plain_fence_pos]
                    if prefix:
                        events.append(SieveEvent("text", prefix))
                    self._json_capturing = True
                    self._json_capture_buf = candidate_buf
                    self._pending = ""
                    return events

        start_idx = self._find_tool_start(self._pending)
        if start_idx >= 0:
            prefix = _strip_tag_debris(self._pending[:start_idx])
            rest = self._pending[start_idx:]
            self._pending = ""
            if prefix:
                events.append(SieveEvent("text", prefix))
            _diag_tool_start = rest[:60].replace("\n", "\\n")
            logger.info(
                f"[SIEVE_DIAG] CAPTURE START! start_idx={start_idx} rest_len={len(rest)} rest_start={_diag_tool_start!r}"
            )
            self._capture_buf = rest
            self._capturing = True
            result = self._try_finish_capture()
            if result is not None:
                events = self._process_capture_result(result, events)
            else:
                logger.info(f"[SIEVE_DIAG]   → capture started but not complete yet")

        if not self._capturing and not self._json_capturing:
            self._pending = re.sub(
                r"</(?:\|?(?:TOOL|DSML)\|?)?(?:tool_calls?|tool_dispatch|tool_call|toolcall|tool_called|invoke|parameter|tool_result)[^>]*>[ \t]*",
                "",
                self._pending,
                flags=re.IGNORECASE,
            )
            safe_prefix, tail = self._split_safe(self._pending)
            if safe_prefix:
                events.append(SieveEvent("text", safe_prefix))
                self._pending = tail

        return events

    def flush(self) -> List[SieveEvent]:
        events: List[SieveEvent] = []
        if self._capturing:
            result = self._try_finish_capture()
            if result is not None:
                prefix_text, tool_calls, suffix = result
                if tool_calls:
                    events.append(SieveEvent("tool_calls", tool_calls))
                elif prefix_text:
                    # capture was "complete" but parse found no tool calls —
                    # don't silently drop the buffer
                    events.append(SieveEvent("text", prefix_text))
                if suffix:
                    events.append(SieveEvent("text", suffix))
            elif self._capture_buf:
                events.append(SieveEvent("text", self._capture_buf))
            self._capture_buf = ""
            self._capturing = False
        if self._json_capturing and self._json_capture_buf:
            from server.parser.dsml_parser import (
                parse_json_tool_calls,
                parse_dsml_tool_calls,
                clean_tool_call_markers,
            )

            jtc, cleaned = parse_json_tool_calls(self._json_capture_buf)
            if jtc:
                events.append(SieveEvent("tool_calls", jtc))
            elif cleaned:
                # Check for DSML tool calls in the flushed content
                dsml_calls, _ = parse_dsml_tool_calls(cleaned, self.tool_names)
                if dsml_calls:
                    events.append(SieveEvent("tool_calls", dsml_calls))
                else:
                    has_tool_marker = bool(
                        re.match(r"^\s*```(?:tool_call|json)", self._json_capture_buf)
                    )
                    if has_tool_marker:
                        events.append(
                            SieveEvent("text", clean_tool_call_markers(cleaned))
                        )
                    else:
                        events.append(SieveEvent("text", cleaned))
            self._json_capturing = False
            self._json_capture_buf = ""
        if self._pending:
            pending_cleaned = re.sub(
                r"</(?:\|?(?:TOOL|DSML)\|?)?(?:tool_calls?|tool_dispatch|tool_call|toolcall|tool_called|invoke|parameter|tool_result)[^>]*>[ \t]*",
                "",
                self._pending,
                flags=re.IGNORECASE,
            )
            if pending_cleaned:
                events.append(SieveEvent("text", pending_cleaned))
            self._pending = ""
        return events

    def _find_tool_start(self, text: str) -> int:
        # Normalize a copy for detection: callers may pass raw text holding
        # full-width / double pipes at chunk boundaries (tag regions split
        # across chunks).  Normalizing here keeps the index aligned with the
        # (already normalized) pending buffer.
        from server.parser.dsml_parser import (
            _normalize_tag_delimiters,
            _fix_missing_lt,
        )

        text = _normalize_tag_delimiters(text)
        text = _fix_missing_lt(text)
        # Damaged <invoke opener (model drops the '<inv' prefix) — check
        # first since 'oke name="X">' contains no '<' and is unambiguous.
        m = _DAMAGED_INVOKE_OPENER_RE.search(text)
        if m:
            return m.start()
        # Bracket tool call format [调用 ToolName] or [call ToolName]
        from server.parser.dsml_parser import _BRACKET_OPENER_RE
        bm = _BRACKET_OPENER_RE.search(text)
        if bm:
            bracket_pos = bm.start()
        else:
            bracket_pos = -1

        first_pos = -1
        for tag in TOOL_STARTS:
            pos = text.find(tag)
            while pos >= 0:
                # Skip matches that are inside close tags (preceded by < or </)
                if pos > 0 and text[pos - 1] in ("<", "/"):
                    pos = text.find(tag, pos + 1)
                    continue
                if first_pos == -1 or pos < first_pos:
                    first_pos = pos
                break
        # Generic DSML/TOOL prefix detection
        for prefix in (
            "<|DSML|",
            "|DSML|",
            "<|TOOL|",
            "|TOOL|",
            "<tool_calls",
            "<tool_dispatch",
            "<tool_call",
            "<toolcall",
            "<tool_called",
            "<invoke",
            "|DSML|invoke",
            "<tool_use_json",
            "<function_call",
            "<function_calls",
            "<argument",
            "<|begin▁of▁sentence",
            "<|Assistant",
            "<|assistant",
            "<use_mcp_tool",
            "<tool_result",
        ):
            pos = text.find(prefix)
            while pos >= 0:
                # Skip matches that are inside close tags (preceded by < or </)
                # e.g., |DSML| inside </|DSML|tool_calls>
                if pos > 0 and text[pos - 1] in ("<", "/"):
                    pos = text.find(prefix, pos + 1)
                    continue
                if first_pos == -1 or pos < first_pos:
                    first_pos = pos
                break

        if bracket_pos != -1 and (first_pos == -1 or bracket_pos < first_pos):
            return bracket_pos
        return first_pos

    def _split_safe(self, text: str) -> Tuple[str, str]:
        # Check for trailing bracket-call opener at the end of text
        bm = _TRAILING_BRACKET_OPENER_RE.search(text)
        if bm:
            return text[: bm.start()], text[bm.start() :]
        for opener_prefix in ("[调用", "【调用", "[call", "[invoke"):
            for i in range(1, len(opener_prefix) + 1):
                pref = opener_prefix[:i]
                if text.endswith(pref):
                    return text[: -len(pref)], text[-len(pref) :]

        last_lt = text.rfind("<")
        # Only fall back to the last full-width pipe when no '<' is present —
        # a pipe run that follows a '<' is part of the tag opener itself
        # (``<｜｜``), so the tail must start at the '<'.
        if last_lt == -1:
            last_lt = text.rfind("｜")
        if last_lt == -1:
            # No '<' or '|' (ASCII or full-width) present, so the tag-hold logic below can't apply.
            # Still, a damaged <invoke opener (model drops '<inv' → 'oke name="X">')
            # can be split across chunks; hold back a trailing partial opener
            # instead of emitting it as prose.
            fm = _DAMAGED_OPENER_FRAGMENT_RE.search(text)
            if fm:
                return text[: fm.start()], text[fm.start() :]
            return text, ""
        tail = text[last_lt:]
        # Compare against pipe-normalised variants (full-width pipe -> ASCII,
        # double pipes collapsed, lone pipes around bare names stripped,
        # ``_calls``/``_dispatch`` wrappers renamed) so partial tags like
        # ``<｜｜t`` / ``<||tool_ca`` / ``<|DSML|_`` still match the ASCII
        # TOOL_STARTS / prefixes.  The original tail is held back unchanged;
        # positions in ``text`` are unaffected.
        from server.parser.dsml_parser import _collapse_double_pipes

        def _strip_lone_pipes(s: str) -> str:
            if s.startswith("<"):
                inner = s[1:]
                is_close = inner.startswith("/")
                rest = inner[1:] if is_close else inner
                stripped = rest.lstrip("|")
                return "<" + ("/" if is_close else "") + stripped
            return s.lstrip("|")

        def _rename_wrapper(s: str) -> str:
            return s.replace("_calls", "tool_calls").replace(
                "_dispatch", "tool_dispatch"
            )

        tail_norm = tail.replace(chr(0xFF5C), "|")
        tail_candidates = [tail_norm]
        collapsed = _collapse_double_pipes(tail_norm)
        if collapsed != tail_norm:
            tail_candidates.append(collapsed)
        for cand in list(tail_candidates):
            for v in (_strip_lone_pipes(cand), _rename_wrapper(cand)):
                if v not in tail_candidates:
                    tail_candidates.append(v)
        # A trailing run of pure pipe chars can only be a tag fragment —
        # hold it back instead of emitting it as prose.
        if all(c in "|" + chr(0xFF5C) for c in tail_norm):
            return text[:last_lt], tail
        # A '>' in the tail means the fragment is a complete (but unrecognized)
        # tag — i.e. prose.  Emit it instead of holding it back forever.
        if ">" in tail_norm:
            return text, ""
        for tag in TOOL_STARTS:
            for cand in tail_candidates:
                if tag.startswith(cand) or cand == tag[: len(cand)]:
                    return text[:last_lt], tail
                # Short openers (ending in space/newline) are prefixes of
                # longer openers (e.g. ``<invoke name="bash``); hold those too.
                if tag.endswith((" ", "\n")) and cand.startswith(tag):
                    return text[:last_lt], tail
        for prefix in (
            "<|DSML|",
            "|DSML|",
            "<|TOOL|",
            "|TOOL|",
            "<tool_calls",
            "<tool_dispatch",
            "<tool_call",
            "<toolcall",
            "<tool_called",
            "<invoke",
            "|DSML|invoke",
            "<tool_use_json",
            "<function_call",
            "<function_calls",
            "<argument",
            "<|begin▁of▁sentence",
            "<|Assistant",
            "<|assistant",
            "<use_mcp_tool",
            "<tool_result",
        ):
            for cand in tail_candidates:
                if prefix.startswith(cand) or (
                    len(cand) <= len(prefix) and cand == prefix[: len(cand)]
                ):
                    return text[:last_lt], tail
                # Marker prefixes (<|DSML| etc.) are unambiguous DSML delimiters —
                # any tail starting with one is a tag fragment; hold it.
                if prefix in (
                    "<|DSML|",
                    "|DSML|",
                    "<|TOOL|",
                    "|TOOL|",
                ) and cand.startswith(prefix):
                    return text[:last_lt], tail
        for tag in CLOSE_TAGS:
            for cand in tail_candidates:
                if tag.startswith(cand) or cand == tag[: len(cand)]:
                    return text[:last_lt], tail
        for prefix in (
            "</|DSML|",
            "</|TOOL|",
            "</tool_calls",
            "</tool_dispatch",
            "</tool_call",
            "</toolcall",
            "</tool_called",
            "</invoke",
            "</parameter",
            "</use_mcp_tool",
            "</tool_result",
            "</function_call",
            "</function_calls",
            "</tool_use_json",
        ):
            for cand in tail_candidates:
                if prefix.startswith(cand) or (
                    len(cand) <= len(prefix) and cand == prefix[: len(cand)]
                ):
                    return text[:last_lt], tail
        return text, ""

    @staticmethod
    def _sanitize_for_structure(buf: str) -> str:
        """Remove parameter-block and CDATA content so structural tag counting
        is not confused by DSML-like strings inside tool-argument values.

        Content inside ``<parameter name="...">…</parameter>`` or
        ``<![CDATA[…]]>`` is replaced with spaces so that character positions
        from the result can be used as-is on the original buffer.
        """
        # Fast exit: if neither parameter tag nor CDATA exists, no replacement needed
        if "parameter" not in buf and "<![CDATA[" not in buf:
            return buf

        sanitized = buf
        if "parameter" in buf and "</" in buf:
            sanitized = _PARAM_BLOCK_RE.sub(lambda m: " " * (m.end() - m.start()), sanitized)
        if "<![CDATA[" in sanitized and "]]>" in sanitized:
            sanitized = _CDATA_RE.sub(lambda m: " " * (m.end() - m.start()), sanitized)
        return sanitized

    def _is_capture_complete(self) -> bool:
        buf = self._capture_buf
        if not buf:
            return False

        # Fast bail-out: capture CANNOT be complete if there is no closing delimiter
        # (neither XML close '</', bracket close ']', nor JSON fence '```' / '}')
        if "</" not in buf and "]" not in buf and "}" not in buf and "`" not in buf:
            return False

        # Sanitize: strip parameter content so DSML-like strings in tool
        # arguments (e.g. code containing </invoke>) don't confuse counting.
        sane = self._sanitize_for_structure(buf)

        # Normalize pipes for structural tag detection.
        # The model may emit full-width pipes (U+FF5C) which _normalize_dsml
        # collapses to single full-width pipes, but our tag checks use ASCII pipes.
        # Also, double pipes (from double full-width pipe format) need to be
        # collapsed to single ASCII pipes for tag matching.
        from server.parser.dsml_parser import _collapse_double_pipes

        sane = _collapse_double_pipes(sane)
        sane = sane.replace(chr(0xFF5C), "|")
        # tool_calls (plural) — model sometimes drops opening <
        if any(
            x in sane
            for x in (
                "<|DSML|tool_calls>",
                "|DSML|tool_calls>",
                "<|TOOL|tool_calls>",
                "|TOOL|tool_calls>",
                "<tool_calls>",
            )
        ):
            return any(
                x in sane
                for x in ("</|DSML|tool_calls>", "</|TOOL|tool_calls>", "</tool_calls>")
            )
        # tool_dispatch — model uses <tool_dispatch> wrapper
        if any(
            x in sane
            for x in (
                "<|DSML|tool_dispatch>",
                "|DSML|tool_dispatch>",
                "<|TOOL|tool_dispatch>",
                "|TOOL|tool_dispatch>",
                "<tool_dispatch>",
            )
        ):
            return any(
                x in sane
                for x in (
                    "</|DSML|tool_dispatch>",
                    "</|TOOL|tool_dispatch>",
                    "</tool_dispatch>",
                )
            )
        # tool_call (singular) — model sometimes drops opening <
        if any(
            x in sane
            for x in (
                "<|DSML|tool_call>",
                "|DSML|tool_call>",
                "<|TOOL|tool_call>",
                "|TOOL|tool_call>",
                "<tool_call>",
                "<tool_call ",
            )
        ):
            return any(
                x in sane
                for x in ("</|DSML|tool_call>", "</|TOOL|tool_call>", "</tool_call>")
            )
        # tool_calls / tool_dispatch / DSML calls — wrapped container of multiple tool calls
        # MUST BE CHECKED FIRST before bare <invoke> checks so multiple invocations are not cut prematurely!
        if any(x in sane for x in ("<tool_calls", "<|DSML|calls", "<|TOOL|calls")):
            return any(x in sane for x in ("</tool_calls>", "</|DSML|calls>", "</|TOOL|calls>"))
        if "<tool_dispatch" in sane:
            return "</tool_dispatch>" in sane

        # toolcall (no underscore) — model sometimes drops underscore
        if "<toolcall" in sane:
            return "</toolcall>" in sane
        # tool_called (past-tense) — model uses <tool_called name="X"> or <tool_called>
        if "<tool_called" in sane:
            return "</tool_called>" in sane
        # invoke whose '<inv' prefix was dropped by the model ('oke name="X">')
        if _DAMAGED_INVOKE_OPENER_RE.search(sane):
            return "</invoke>" in sane
        # invoke — model sometimes drops opening <
        # IMPORTANT: use balanced counting — DeepSeek nests <invoke> inside <invoke>
        # for parameter values (e.g. <invoke name="Read"><invoke name="file_path">val</invoke>).
        # Checking ANY </invoke> is wrong — we need opens == closes.
        # After normalization, only <|DSML|invoke and <|TOOL|invoke formats exist.
        _INVOKE_OPENS = (
            "<invoke ",
            "<invoke>",
            "<invoke\n",
            "<|DSML|invoke ",
            "<|TOOL|invoke ",
        )
        _INVOKE_CLOSES = ("</invoke>", "</|DSML|invoke>", "</|TOOL|invoke>")
        if any(x in sane for x in _INVOKE_OPENS):
            _opens = sum(sane.count(x) for x in _INVOKE_OPENS)
            _closes = sum(sane.count(x) for x in _INVOKE_CLOSES)
            _result = _opens > 0 and _opens == _closes
            return _result
        # tool_result — tool result block
        if any(x in sane for x in ("<tool_result>", "<tool_result ")):
            return "</tool_result>" in sane
        # thinking — only treat as capture if it contains actual tool markup
        if "<thinking" in sane:
            if not any(
                x in sane
                for x in (
                    "<tool_use_json",
                    "<function_call",
                    "<function_calls",
                    "<invoke ",
                    "<invoke>",
                    "<invoke\n",
                    "<tool_call",
                    "<toolcall",
                    "<tool_result",
                )
            ):
                if "</thinking>" in sane:
                    return True  # complete thinking block, let flush emit as text
                return False
            return "</thinking>" in sane
        # tool_use_json — JSON tool call format
        if "<tool_use_json" in sane:
            return "</tool_use_json>" in sane
        # function_calls — multiple function calls JSON format
        if "<function_calls" in sane:
            return "</function_calls>" in sane
        # function_call — single function call JSON format (check after plural to avoid substring match)
        if "<function_call" in sane:
            return "</function_call>" in sane
        # use_mcp_tool — MCP tool call format
        if "<use_mcp_tool" in sane:
            return "</use_mcp_tool>" in sane
        # bracket tool call — [调用 ToolName] {json}
        from server.parser.dsml_parser import _BRACKET_OPENER_RE

        bm = _BRACKET_OPENER_RE.search(sane)
        if bm:
            after = sane[bm.end() :]
            brace = after.find("{")
            if brace != -1 and after[:brace].strip() == "":
                try:
                    import json

                    _, end_pos = json.JSONDecoder().raw_decode(after[brace:])
                    return True
                except json.JSONDecodeError:
                    return False
        return False

    def _try_finish_capture(self) -> Optional[Tuple[str, Any, str]]:
        if not self._capture_buf:
            return None
        # Re-normalize the whole capture buffer: chunks were normalized
        # individually on feed(), so tag regions split across chunk boundaries
        # (e.g. ``</｜｜tool_calls`` + ``>``) may still contain raw full-width
        # or double pipes.  Normalizing the merged buffer before the
        # completeness check and the parser ensures both see one canonical
        # form (``</tool_calls>`` etc.).
        from server.parser.dsml_parser import (
            _normalize_tag_delimiters,
            _fix_missing_lt,
        )

        self._capture_buf = _normalize_tag_delimiters(self._capture_buf)
        self._capture_buf = _fix_missing_lt(self._capture_buf)
        if not self._is_capture_complete():
            return None

        # Check bracket tool calls if buffer contains bracket opener
        if re.search(
            r"(?:\[|【)\s*(?:调用|call|invoke)", self._capture_buf, re.IGNORECASE
        ):
            from server.parser.dsml_parser import parse_bracket_tool_calls

            b_calls, _ = parse_bracket_tool_calls(
                self._capture_buf, self.tool_names
            )
            if b_calls:
                leftover = self._extract_post_wrapper(self._capture_buf)
                return ("", b_calls, leftover)

        # Parse using the external parser
        from server.parser.dsml_parser import parse_dsml_tool_calls

        tool_calls, cleaned = parse_dsml_tool_calls(self._capture_buf, self.tool_names)
        if tool_calls:
            leftover = self._extract_post_wrapper(self._capture_buf)
            return ("", tool_calls, leftover)

        # Try repair pipeline if parsing returned empty
        repaired = repair_pipeline(self._capture_buf, self.tool_names)
        if repaired is not None:
            tool_calls, cleaned = parse_dsml_tool_calls(repaired, self.tool_names)
            if tool_calls:
                leftover = self._extract_post_wrapper(self._capture_buf)
                return ("", tool_calls, leftover)

        # Tier 4: legacy format fallback (tool_use_json, function_call, function_calls)
        from server.parser.tool_parser import legacy_fallback

        tool_calls = legacy_fallback(self._capture_buf, self.tool_names)
        if tool_calls:
            leftover = self._extract_post_wrapper(self._capture_buf)
            return ("", tool_calls, leftover)

        return (self._capture_buf, None, "")

    def _process_capture_result(self, result, events):
        """Process the result from _try_finish_capture and add events."""
        prefix_text, tool_calls, suffix = result
        if prefix_text:
            events.append(SieveEvent("text", prefix_text))
        if tool_calls:
            events.append(SieveEvent("tool_calls", tool_calls))
        self._capture_buf = ""
        self._capturing = False
        if suffix:
            events.extend(self.feed(suffix))
        return events

    def _extract_post_wrapper(self, text: str) -> str:
        """Extract text after the closing wrapper tag.

        For standalone <invoke> captures (no <tool_calls> wrapper):
        uses the LAST </invoke> (handles nested invokes).

        For <tool_calls> wrapped captures: uses the first close tag
        (the wrapper's own close tag, standard behavior).
        """
        # Standalone <invoke> (no <tool_calls> wrapper):
        # use LAST </invoke> to handle nested invoke tags
        _INVOKE_CLOSE_TAGS = ("</invoke>", "</|DSML|invoke>", "</|TOOL|invoke>")
        _HAS_WRAPPER = any(
            x in text
            for x in (
                "<|DSML|tool_calls>",
                "|DSML|tool_calls>",
                "<|TOOL|tool_calls>",
                "|TOOL|tool_calls>",
                "<tool_calls>",
                "<|DSML|tool_dispatch>",
                "|DSML|tool_dispatch>",
                "<|TOOL|tool_dispatch>",
                "|TOOL|tool_dispatch>",
                "<tool_dispatch>",
            )
        )
        after = ""
        if not _HAS_WRAPPER and any(
            x in text
            for x in (
                "<invoke ",
                "<invoke>",
                "<invoke\n",
                "<|DSML|invoke ",
                "|DSML|invoke ",
                "<|TOOL|invoke ",
                "|TOOL|invoke ",
            )
        ):
            last_pos = -1
            last_len = 0
            for tag in _INVOKE_CLOSE_TAGS:
                pos = text.rfind(tag)
                if pos > last_pos:
                    last_pos = pos
                    last_len = len(tag)
            if last_pos >= 0:
                after = text[last_pos + last_len :]
        else:
            # tool_calls wrapper or non-invoke: find first close tag (default behavior)
            for tag in CLOSE_TAGS:
                pos = text.find(tag)
                if pos >= 0:
                    after = text[pos + len(tag) :]
                    break

        # Bracket call extraction (if no XML wrapper close tag matched)
        if not after:
            from server.parser.dsml_parser import _BRACKET_OPENER_RE

            bm = _BRACKET_OPENER_RE.search(text)
            if bm:
                import json

                decoder = json.JSONDecoder()
                last_end = -1
                for m in _BRACKET_OPENER_RE.finditer(text):
                    after_h = text[m.end() :]
                    brace = after_h.find("{")
                    if brace != -1 and after_h[:brace].strip() == "":
                        try:
                            _, end_pos = decoder.raw_decode(after_h[brace:])
                            last_end = m.end() + brace + end_pos
                        except json.JSONDecodeError:
                            pass
                if last_end != -1:
                    after = text[last_end:]

        # A lone wrapper close-tag or duplicate closing tags right after the last
        # close tag (e.g. repeated </tool_calls>, </invoke>, debris) are not prose.
        # Strip all of them so they don't leak into assistant content.
        all_close_tags = sorted(set(list(CLOSE_TAGS) + list(_INVOKE_CLOSE_TAGS)), key=len, reverse=True)
        while True:
            stripped = after.lstrip()
            matched = False
            for close in all_close_tags:
                if stripped.startswith(close):
                    after = stripped[len(close) :]
                    matched = True
                    break
            if not matched:
                break

        return after.strip(" \t")

    def _is_json_candidate(self, buf: str) -> bool:
        """Check if the buffer is a candidate for a JSON tool call block."""
        if not buf.startswith("```"):
            return False
        rest = buf[3:]
        if not rest:
            return True

        # If first char is space or '{', it must lead to a JSON object
        if rest[0].isspace() or rest[0] == "{":
            stripped = rest.lstrip()
            if not stripped:
                return True
            return stripped.startswith("{")

        # Otherwise, must start with "tool_call" or "json" prefix/full keyword
        rest_lower = rest.lower()
        for keyword in ("tool_call", "json"):
            if keyword.startswith(rest_lower):
                return True
            if rest_lower.startswith(keyword):
                after = rest_lower[len(keyword) :]
                if not after:
                    return True
                if after[0].isspace() or after[0] == "{":
                    stripped_after = after.lstrip()
                    if not stripped_after:
                        return True
                    return stripped_after.startswith("{")

        return False
