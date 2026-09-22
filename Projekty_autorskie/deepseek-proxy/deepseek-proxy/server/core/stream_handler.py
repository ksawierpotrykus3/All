from __future__ import annotations

import json
import os
import re
from typing import Any, Optional


from server.parser.dsml_sieve import StreamSieve
from server.parser.dsml_parser import (
    parse_dsml_tool_calls,
    parse_json_tool_calls,
    clean_tool_text,
)
from server.repair import repair_pipeline
from server.repair.repair_tier1 import _fix_damaged_invoke_opener
from server.logging import get_logger
from server.core.mcp_catalog import mcp_rewrite_calls

logger = get_logger(__name__)


# Tool name alias mapping — model sometimes generates names that differ
# from the tool names provided in the tools schema (e.g. "Edit" instead of "Write").
# This mapping normalizes such aliases to their canonical tool names.
_TOOL_NAME_ALIASES: dict[str, str] = {
    "Edit": "Write",  # model uses Edit instead of Write
    "edit": "Write",
    "Bash": "Shell",  # model uses Bash instead of Shell
}

# Case-insensitive alias map (lowercase → canonical)
# Built from _TOOL_NAME_ALIASES, case-flipped entries above are redundant
# but kept for clarity.
_CI_ALIAS_MAP: dict[str, str] | None = None


def _build_ci_alias_map() -> dict[str, str]:
    """Build case-insensitive alias map from _TOOL_NAME_ALIASES."""
    m: dict[str, str] = {}
    for alias, canonical in _TOOL_NAME_ALIASES.items():
        m[alias.lower()] = canonical
    return m


def _resolve_tool_name(name: str, valid_set: set[str]) -> str:
    """Resolve a tool name to a known canonical name via alias lookup.

    Returns the resolved (canonical) name if found, or the original name unchanged.
    """
    if name in valid_set:
        return name
    global _CI_ALIAS_MAP
    if _CI_ALIAS_MAP is None:
        _CI_ALIAS_MAP = _build_ci_alias_map()
    canonical = _CI_ALIAS_MAP.get(name.lower())
    if canonical and canonical in valid_set:
        return canonical
    return name


def _normalize_newlines_for_edit_tool(tc: dict) -> dict:
    """Normalize newlines in SearchReplace / Edit / replace_file_content tool calls to match the file's line endings on disk."""
    name = tc.get("name")
    if name not in ("SearchReplace", "Edit", "replace_file_content"):
        return tc

    # Load arguments
    args_raw = tc.get("arguments", "")
    if not args_raw:
        return tc

    try:
        if isinstance(args_raw, str):
            args = json.loads(args_raw)
        else:
            args = dict(args_raw)
    except Exception:
        return tc

    # Find the target file path
    file_path = args.get("file_path") or args.get("path") or args.get("TargetFile")
    if not file_path or not os.path.exists(file_path):
        return tc

    # Check the line endings of the target file
    try:
        with open(file_path, "rb") as f:
            sample = f.read(4096)
        target_crlf = b"\r\n" in sample
    except Exception:
        target_crlf = False

    # Normalize fields: old_string/new_string, oldText/newText, TargetContent/ReplacementContent
    fields_to_normalize = [
        "old_string",
        "new_string",
        "oldText",
        "newText",
        "TargetContent",
        "ReplacementContent",
        "content",
    ]

    modified = False
    for field in fields_to_normalize:
        if field in args and isinstance(args[field], str):
            val = args[field]
            val_lf = val.replace("\r\n", "\n")
            if target_crlf:
                normalized = val_lf.replace("\n", "\r\n")
            else:
                normalized = val_lf

            if normalized != val:
                args[field] = normalized
                modified = True

    if modified:
        tc = dict(tc)
        if isinstance(args_raw, str):
            tc["arguments"] = json.dumps(args, ensure_ascii=False)
        else:
            tc["arguments"] = args
        if "function" in tc:
            tc["function"] = dict(tc["function"])
            if isinstance(args_raw, str):
                tc["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
            else:
                tc["function"]["arguments"] = args
_REPETITION_TAG_RE = re.compile(
    r"((?:</(?:｜｜)?(?:DSML|TOOL)?(?:｜｜)?\s*(?:parameter|invoke)[^>]*>[ \t\r\n]*){4,})$",
    re.IGNORECASE,
)


def detect_repetition_loop(
    text: str,
    min_pat_len: int = 8,
    max_pat_len: int = 80,
    min_repeats: int = 4,
) -> str | None:
    """Detect if text ends in a degenerate autoregressive repetition loop.

    Checks:
    1. Tail of 4+ consecutive malformed DSML closing tags (e.g. </parameter> loop).
    2. Any repeating substring pattern of length min_pat_len..max_pat_len repeated
       at least min_repeats times back-to-back at the end of the text.

    Returns the repeating pattern if found, or None.
    """
    if not text or len(text) < min_pat_len * min_repeats:
        return None

    # Fast check: XML/DSML tag loop
    tail = text[-2000:]
    tag_m = _REPETITION_TAG_RE.search(tail)
    if tag_m:
        return tag_m.group(1)[:50]

    # Substring loop check
    max_len = min(max_pat_len, len(tail) // min_repeats)
    for pat_len in range(min_pat_len, max_len + 1):
        candidate = tail[-pat_len:]
        if tail.endswith(candidate * min_repeats):
            return candidate

    return None


class ToolMgr:
    """Manages tool call parsing with multi-tier fallback."""

    @staticmethod
    def try_parse(text: str, tool_names: list[str]) -> list[dict]:
        # Tier 1: Fast path — DSML format (most common when format instruction works)
        calls, _ = parse_dsml_tool_calls(text, tool_names)
        if calls:
            return calls

        # Tier 2: Repair malformed XML then re-parse
        repaired = repair_pipeline(text, tool_names)
        if repaired is not None:
            calls, _ = parse_dsml_tool_calls(repaired, tool_names)
            if calls:
                return calls

        # Tier 3: JSON-based formats (```tool_call, <function_call>, etc.)
        calls, _ = parse_json_tool_calls(text)
        if calls:
            return calls

        # Tier 4: Direct Tier 3 repair for truncated fragments
        from server.repair.repair_tier3 import repair_tier3

        repaired = repair_tier3(text, tool_names)
        if repaired is not None:
            calls, _ = parse_dsml_tool_calls(repaired, tool_names)
            if calls:
                return calls

        # Tier 5: Legacy format fallback (function_call, tool_use_json, raw XML, <ToolName> tags)
        from server.parser.tool_parser import legacy_fallback

        calls = legacy_fallback(text, tool_names)
        if calls:
            return calls

        return []

    @staticmethod
    def validate(calls: list[dict], tool_names: list[str]) -> list[dict]:
        if not tool_names or not calls:
            return calls
        valid_set = set(tool_names)
        result = []
        for tc in calls:
            name = tc.get("name", "")
            canonical = _resolve_tool_name(name, valid_set)
            if canonical in valid_set:
                if canonical != name:
                    # Rename the tool call to its canonical name
                    tc = dict(tc)
                    tc["name"] = canonical
                    fn = dict(tc.get("function", {}))
                    fn["name"] = canonical
                    # Copy top-level arguments into function dict so downstream
                    # readers (e.g. _repair_empty_tc_args) find them there.
                    if "arguments" not in fn and "arguments" in tc:
                        fn["arguments"] = tc["arguments"]
                    tc["function"] = fn
                # Normalize newlines for SearchReplace / Edit tools to match file CRLF/LF
                tc = _normalize_newlines_for_edit_tool(tc)
                result.append(tc)
        return result


_FINAL_ANSWER_MARKER = "FINAL ANSWER:"


def _try_parse_damaged_invoke(text: str, tool_names: list[str]) -> list[dict]:
    """Parse a tool block whose opener lost its ``<inv`` prefix.

    The sieve normally captures and repairs such blocks, but on the
    deepseek fallback path the malformed block can reach the handler as a
    single text event.  Repair the opener and parse; return [] when the text
    is not a damaged tool block.
    """
    if "<invoke" in text or "<parameter" not in text or "</invoke>" not in text:
        return []
    repaired = _fix_damaged_invoke_opener(text)
    if repaired == text:
        return []
    calls, _ = parse_dsml_tool_calls(repaired, tool_names)
    return calls


class StreamHandler:
    """Wraps StreamSieve + ToolMgr, yields dict events."""

    def __init__(
        self,
        tool_names: Optional[list[str]] = None,
        mcp_catalog: Optional[dict] = None,
    ):
        self._sieve = StreamSieve(tool_names=tool_names)
        self._tool_names = tool_names or []
        self._mcp_catalog = mcp_catalog or {}
        self._had_tool_calls = False
        self._found_final_answer = False

    def _try_emit_tool_calls(self, calls, events) -> bool:
        """Rewrite bare MCP tool calls, validate, append tool_calls event on success.

        Returns True when at least one tool call was emitted.  Rewriting happens
        BEFORE ``ToolMgr.validate`` so an MCP name (e.g. ``git_status``) the model
        read from the GetMcpTools catalog becomes a real ``CallMcpTool`` invocation
        instead of being silently dropped (which previously left the IDE waiting).
        """
        calls = list(calls)
        if not calls:
            return False
        rewritten = [
            c.get("name", "")
            for c in calls
            if isinstance(c, dict) and c.get("name") in self._mcp_catalog
        ]
        prepped = mcp_rewrite_calls(calls, self._mcp_catalog)
        if rewritten:
            logger.info(
                f"[MCP_REWRITE] bare MCP tool call(s) -> CallMcpTool: {rewritten}"
            )
        validated = ToolMgr.validate(prepped, self._tool_names)
        logger.info(
            f"[HANDLER_DIAG] sieve returned {len(calls)} call(s), "
            f"tool_names={self._tool_names}, validated={len(validated)}"
        )
        if validated:
            self._had_tool_calls = True
            events.append({"type": "tool_calls", "data": validated})
            return True
        logger.warning(
            f"[TOOL_DROP] tool call(s) dropped after validation: "
            f"names={[c.get('name', '') for c in calls]}"
        )
        return False

    def feed(self, chunk: str) -> list[dict]:
        """Consume a text chunk and return list of event dicts.

        Event types: {"type": "text", "data": str} | {"type": "tool_calls", "data": [...]}
        """
        if not chunk:
            return []

        # Check for FINAL ANSWER marker
        if _FINAL_ANSWER_MARKER in chunk:
            self._found_final_answer = True

        events = []
        for se in self._sieve.feed(chunk):
            if se.type == "text":
                # Only clean tool call XML markup if the text actually contains structural tags
                # that would leak. Ordinary model responses (including markdown tables with | or code blocks)
                # should not be passed through clean_tool_text to avoid altering line breaks and spacing.
                data = se.data
                if any(
                    tag in data
                    for tag in (
                        "<tool_calls",
                        "<tool_call",
                        "<toolcall",
                        "<invoke",
                        "<parameter",
                        "</tool_calls",
                        "</tool_call",
                        "</toolcall",
                        "</invoke",
                        "</parameter",
                    )
                ):
                    repaired_calls = _try_parse_damaged_invoke(data, self._tool_names)
                    if repaired_calls:
                        if self._try_emit_tool_calls(repaired_calls, events):
                            continue
                    cleaned = clean_tool_text(data)
                else:
                    cleaned = data

                if cleaned:
                    # Strip FINAL ANSWER marker from visible output, preserve formatting
                    cleaned = cleaned.replace(_FINAL_ANSWER_MARKER, "")
                    if cleaned:
                        events.append({"type": "text", "data": cleaned})
            elif se.type == "tool_calls":
                self._try_emit_tool_calls(se.data, events)

        return events

    def flush(self) -> list[dict]:
        """Flush remaining buffer through sieve + ToolMgr repair."""
        # Capture before sieve.flush() clears it
        capture_before = self._sieve._capture_buf

        # Check for FINAL ANSWER in capture buffer
        if capture_before and _FINAL_ANSWER_MARKER in capture_before:
            self._found_final_answer = True

        events = []
        for se in self._sieve.flush():
            if se.type == "text":
                data = se.data
                if any(
                    tag in data
                    for tag in (
                        "<tool_calls",
                        "<tool_call",
                        "<toolcall",
                        "<invoke",
                        "<parameter",
                        "</tool_calls",
                        "</tool_call",
                        "</toolcall",
                        "</invoke",
                        "</parameter",
                    )
                ):
                    repaired_calls = _try_parse_damaged_invoke(data, self._tool_names)
                    if repaired_calls:
                        if self._try_emit_tool_calls(repaired_calls, events):
                            continue
                    cleaned = clean_tool_text(data)
                else:
                    cleaned = data

                if cleaned:
                    cleaned = cleaned.replace(_FINAL_ANSWER_MARKER, "")
                    if cleaned:
                        events.append({"type": "text", "data": cleaned})
            elif se.type == "tool_calls":
                self._try_emit_tool_calls(se.data, events)

        # Tier 3 repair on capture buffer before sieve flushed it
        if capture_before:
            # Try to complete truncated closing tags (e.g. stream ended with
            # "</invoke" missing the final ">"). This fixes the case where
            # DeepSeek's stream exhausts before the XML tag is fully formed.
            _repaired_buf = capture_before
            if _repaired_buf.rstrip().endswith(
                ("</invoke", "</tool_calls", "</tool_call", "</parameter")
            ):
                _repaired_buf = _repaired_buf.rstrip() + ">"
            calls = ToolMgr.try_parse(_repaired_buf, self._tool_names)
            if calls:
                self._try_emit_tool_calls(calls, events)

        return events
