# DSML Prompt Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current custom flat-text prompt format with DSML (DeepSeek Model Language) format using ds2api-style tokens and CDATA-wrapped tool calls.

**Architecture:** Three new files (dsml_prompt.py, dsml_parser.py, dsml_sieve.py) replace the existing StructuredResponseStreamParser and tool_parser.py. Two existing files (prompt_service.py, stream_service.py) are modified to delegate to the new modules. The interface to ProxyService stays the same.

**Tech Stack:** Python 3.11+, curl_cffi (unchanged), existing FastAPI app (unchanged).

**Spec:** [2026-07-13-dsml-prompt-format-design.md](../specs/2026-07-13-dsml-prompt-format-design.md)

---

### Task 1: Create `server/parser/dsml_sieve.py` — StreamSieve

**Files:**
- Create: `server/parser/dsml_sieve.py`
- Test: `tests/test_dsml_sieve.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/test_dsml_sieve.py — StreamSieve unit tests"""
import pytest
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
    events = sieve.feed("Some text before <|DSML|tool_calls><|DSML|invoke name=\"Read\"><|DSML|parameter name=\"file_path\"><![CDATA[/path/file.txt]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>")
    text_events = [e for e in events if e.type == "text"]
    tc_events = [e for e in events if e.type == "tool_calls"]
    assert len(text_events) == 1
    assert "Some text before" in text_events[0].data
    assert len(tc_events) >= 1

def test_sieve_flush_returns_remaining():
    sieve = StreamSieve()
    sieve.feed("partial")
    events = sieve.flush()
    assert len(events) == 1
    assert events[0].type == "text"
    assert events[0].data == "partial"

def test_sieve_handles_split_chunks():
    sieve = StreamSieve()
    events = sieve.feed('<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="x">')
    assert len(events) == 0  # not yet complete, buffered
    events2 = sieve.feed('<![CDATA[val]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>')
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
    text_events = [e for e in events if e.type == "text"]
    assert any("trailing text" in e.data for e in text_events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dsml_sieve.py -v`
Expected: FAIL with ImportError (module not found)

- [ ] **Step 3: Write the StreamSieve implementation**

```python
"""server/parser/dsml_sieve.py — StreamSieve: real-time DSML tool call detection in streaming chunks.

Detects <|DSML|tool_calls> blocks in character streams, buffers them,
and emits SieveEvent objects when a complete block is parsed.
"""

from __future__ import annotations
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple


@dataclass
class SieveEvent:
    """Event emitted by StreamSieve."""
    type: str  # "text" | "tool_calls"
    data: Any  # str for text, list[dict] for tool_calls


ToOL_STARTS = [
    "<|DSML|tool_calls>",
    "|DSML|tool_calls>",       # model sometimes drops opening <
    "<tool_calls>",
    "<tool_call>",
    "<invoke ",
    "<|DSML|invoke ",
    "|DSML|invoke ",           # model sometimes drops opening <
]

CLOSE_TAGS = [
    "</|DSML|tool_calls>",
    "</tool_calls>",
    "</tool_call>",
]


class StreamSieve:
    """DSML mode stream sieve — separates text from DSML tool call blocks in real-time."""

    def __init__(self, tool_names: Optional[List[str]] = None):
        self.tool_names = tool_names or []
        self._pending = ""
        self._capture_buf = ""
        self._capturing = False
        self._parse_fn = None

    def feed(self, chunk: str) -> List[SieveEvent]:
        events: List[SieveEvent] = []
        if not chunk:
            return events

        if self._capturing:
            self._capture_buf += chunk
            result = self._try_finish_capture()
            if result is not None:
                prefix_text, tool_calls, suffix = result
                if prefix_text:
                    events.append(SieveEvent("text", prefix_text))
                if tool_calls:
                    events.append(SieveEvent("tool_calls", tool_calls))
                if suffix:
                    self._pending = suffix
                self._capture_buf = ""
                self._capturing = False
                if suffix:
                    events.extend(self.feed(""))
            return events

        self._pending += chunk
        start_idx = self._find_tool_start(self._pending)
        if start_idx >= 0:
            prefix = self._pending[:start_idx]
            rest = self._pending[start_idx:]
            self._pending = ""
            if prefix:
                events.append(SieveEvent("text", prefix))
            self._capture_buf = rest
            self._capturing = True
            result = self._try_finish_capture()
            if result is not None:
                prefix_text, tool_calls, suffix = result
                if prefix_text:
                    events.append(SieveEvent("text", prefix_text))
                if tool_calls:
                    events.append(SieveEvent("tool_calls", tool_calls))
                if suffix:
                    self._pending = suffix
                self._capture_buf = ""
                self._capturing = False
        else:
            safe, hold = self._split_safe(self._pending)
            if safe:
                events.append(SieveEvent("text", safe))
            self._pending = hold

        return events

    def flush(self) -> List[SieveEvent]:
        events: List[SieveEvent] = []
        if self._capturing:
            result = self._try_finish_capture()
            if result is not None:
                _, tool_calls, suffix = result
                if tool_calls:
                    events.append(SieveEvent("tool_calls", tool_calls))
                if suffix:
                    events.append(SieveEvent("text", suffix))
            elif self._capture_buf:
                events.append(SieveEvent("text", self._capture_buf))
            self._capture_buf = ""
            self._capturing = False
        if self._pending:
            events.append(SieveEvent("text", self._pending))
            self._pending = ""
        return events

    def _find_tool_start(self, text: str) -> int:
        for tag in ToOL_STARTS:
            pos = text.find(tag)
            if pos >= 0:
                return pos
        # Generic DSML prefix detection
        for prefix in ("<|DSML|", "|DSML|", "<tool_calls", "<tool_call", "<invoke", "|DSML|invoke"):
            pos = text.find(prefix)
            if pos >= 0:
                return pos
        return -1

    def _find_close_tag(self, text: str) -> int:
        for tag in CLOSE_TAGS:
            pos = text.find(tag)
            if pos >= 0:
                return pos + len(tag)
        return -1

    def _split_safe(self, text: str) -> Tuple[str, str]:
        last_lt = text.rfind("<")
        if last_lt == -1:
            last_lt = text.rfind("|")
        if last_lt == -1:
            return text, ""
        tail = text[last_lt:]
        for tag in ToOL_STARTS:
            if tag.startswith(tail) or tail == tag[:len(tail)]:
                return text[:last_lt], tail
        for prefix in ("<|DSML|", "|DSML|", "<tool_calls", "<tool_call", "<invoke", "|DSML|invoke"):
            if prefix.startswith(tail) or (len(tail) <= len(prefix) and tail == prefix[:len(tail)]):
                return text[:last_lt], tail
        return text, ""

    def _is_capture_complete(self) -> bool:
        buf = self._capture_buf
        if "<|DSML|tool_calls>" in buf or "<tool_calls>" in buf:
            return "</|DSML|tool_calls>" in buf or "</tool_calls>" in buf
        if "<tool_call>" in buf or "<|DSML|tool_call>" in buf:
            return "</tool_call>" in buf or "</|DSML|tool_call>" in buf
        if "<invoke " in buf or "<|DSML|invoke " in buf:
            return "</invoke>" in buf or "</|DSML|invoke>" in buf
        return False

    def _try_finish_capture(self):
        if not self._capture_buf:
            return None
        if not self._is_capture_complete():
            return None
        # Parse using the external parser
        from server.parser.dsml_parser import parse_dsml_tool_calls
        tool_calls, cleaned = parse_dsml_tool_calls(self._capture_buf, self.tool_names)
        if tool_calls:
            leftover = self._extract_post_wrapper(self._capture_buf)
            return ("", tool_calls, leftover)
        else:
            return (self._capture_buf, None, "")

    def _extract_post_wrapper(self, text: str) -> str:
        """Extract text after the closing tool_calls tag."""
        for tag in CLOSE_TAGS:
            pos = text.find(tag)
            if pos >= 0:
                after = text[pos + len(tag):]
                return after.strip()
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dsml_sieve.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add server/parser/dsml_sieve.py tests/test_dsml_sieve.py
git commit -m "feat: add StreamSieve for real-time DSML tool call detection"
```

---

### Task 2: Create `server/parser/dsml_parser.py` — DSML Parser

**Files:**
- Create: `server/parser/dsml_parser.py`
- Test: `tests/test_dsml_parser.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/test_dsml_parser.py — DSML parser unit tests"""
import json
import pytest
from server.parser.dsml_parser import (
    parse_dsml_tool_calls,
    strip_dsml_markup,
    clean_tool_text,
    format_tool_calls_for_prompt,
    build_dsml_tool_prompt,
)

def test_parse_single_tool_call():
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

def test_parse_no_dsml_prefix():
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

def test_strip_dsml_markup():
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

def test_build_dsml_tool_prompt():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "Read",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"}
                    },
                    "required": ["file_path"]
                }
            }
        }
    ]
    result = build_dsml_tool_prompt(tools)
    assert "Read" in result
    assert "<![CDATA[" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dsml_parser.py -v`
Expected: FAIL with ImportError (module not found)

- [ ] **Step 3: Write the DSML parser implementation**

```python
"""server/parser/dsml_parser.py — DSML parser for DeepSeek Model Language tool calls.

Parses <|DSML|tool_calls> blocks with CDATA, strips DSML markup,
and formats tool calls for history reconstruction.
"""

from __future__ import annotations
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple


_CDATA_OPEN = "<![CDATA["
_CDATA_CLOSE = "]]>"
_DSML_NS: set[str] = set("| \t\r\n")
_DSML_NS.add(chr(0xFF5C))  # full-width pipe

TOOL_CALLS_PATTERN = re.compile(
    r"<(?:\|DSML\|)?tool_calls?\s*>(.*?)</(?:\|DSML\|)?tool_calls?\s*>",
    re.DOTALL | re.IGNORECASE,
)
INVOKE_PATTERN = re.compile(
    r'<(?:\|DSML\|)?invoke\s+name=["\']([^"\']+)["\']>(.*?)</(?:\|DSML\|)?invoke\s*>',
    re.DOTALL | re.IGNORECASE,
)
PARAM_PATTERN = re.compile(
    r'<(?:\|DSML\|)?parameter\s+name=["\']([^"\']+)["\']>(.*?)</(?:\|DSML\|)?parameter\s*>',
    re.DOTALL | re.IGNORECASE,
)


def strip_dsml_markup(text: str) -> str:
    """Remove DSML namespace prefixes and normalize tags."""
    if not text:
        return text
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i:].startswith(_CDATA_OPEN):
            cl = text.find(_CDATA_CLOSE, i + len(_CDATA_OPEN))
            if cl == -1:
                result.append(text[i:])
                break
            result.append(text[i:cl + len(_CDATA_CLOSE)])
            i = cl + len(_CDATA_CLOSE)
            continue
        if text[i] != '<':
            result.append(text[i])
            i += 1
            continue
        end = text.find('>', i)
        if end == -1:
            result.append(text[i:])
            break
        inner = text[i + 1:end]
        is_close = inner.startswith('/')
        tag = inner[1:] if is_close else inner
        # Strip DSML prefix noise: <|DSML|tag> -> <tag>
        cleaned = _strip_dsml_noise(tag)
        if cleaned != tag:
            prefix = '</' if is_close else '<'
            result.append(prefix + cleaned + '>')
            i = end + 1
        else:
            result.append(text[i:end + 1])
            i = end + 1
    return ''.join(result)


def _strip_dsml_noise(tag: str) -> str:
    """Strip DSML namespace noise from a tag name."""
    # Remove |DSML| prefix (with optional pipe chars)
    m = re.match(r'^(?:\|*\s*(?:DSML|dsml)\s*\|*\s*)?(.+)$', tag, re.IGNORECASE)
    if m:
        return m.group(1)
    return tag


def clean_tool_text(text: str) -> str:
    """Remove all DSML/XML tool call tags from text, leaving only content."""
    if not text:
        return text
    # Remove <|DSML|tool_calls> ... </|DSML|tool_calls> blocks
    text = TOOL_CALLS_PATTERN.sub("", text)
    # Remove bare invoke/parameter tags
    text = re.sub(
        r'<(?:\|DSML\|)?invoke[^>]*>.*?</(?:\|DSML\|)?invoke\s*>',
        "", text, flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r'<(?:\|DSML\|)?parameter[^>]*>.*?</(?:\|DSML\|)?parameter\s*>',
        "", text, flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r'<!\[CDATA\[.*?\]\]>', "", text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _auto_type(val: str) -> Any:
    """Convert a string value to its Python type automatically."""
    if not val:
        return val
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() in ("null", "none"):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _extract_cdata(raw: str) -> str:
    """Extract content from CDATA wrapper, or return raw if not CDATA."""
    raw = raw.strip()
    if raw.startswith(_CDATA_OPEN) and raw.endswith(_CDATA_CLOSE):
        inner = raw[len(_CDATA_OPEN):-len(_CDATA_CLOSE)]
        inner = inner.replace("]]]]><![CDATA[>", "]]>")
        return inner
    return raw


def _resolve_tool_name(name: str, tool_names: list[str]) -> str:
    if not tool_names:
        return name
    if name in tool_names:
        return name
    # Case-insensitive match
    for tn in tool_names:
        if tn.lower() == name.lower():
            return tn
    # Snake_case match
    snake = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', name).lower()
    if snake in tool_names:
        return snake
    return name


def parse_dsml_tool_calls(
    text: str,
    tool_names: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Parse DSML tool calls from text.

    Returns:
        (tool_calls_list, cleaned_text)
        tool_calls_list: list of {"name": str, "arguments": str (JSON)}
        cleaned_text: original text with tool call blocks removed
    """
    if not text:
        return [], text

    tool_names = tool_names or []
    normalized = strip_dsml_markup(text)

    # Find tool_calls or tool_call blocks
    blocks: list[str] = []
    for m in TOOL_CALLS_PATTERN.finditer(normalized):
        blocks.append(m.group(1))

    # Also try bare invoke (no wrapper)
    if not blocks:
        bare_invokes = INVOKE_PATTERN.findall(normalized)
        # These will be handled below

    tool_calls: list[dict] = []

    for block_text in blocks:
        for m in INVOKE_PATTERN.finditer(block_text):
            name = m.group(1).strip()
            inner = m.group(2)
            resolved = _resolve_tool_name(name, tool_names)
            args = _parse_parameters(inner)
            tc = _format_tool_call(resolved, args)
            if tc:
                tool_calls.append(tc)

    cleaned = clean_tool_text(text)
    return tool_calls, cleaned


def _parse_parameters(inner_text: str) -> Dict[str, Any]:
    """Parse <parameter name="...">...</parameter> entries into a dict."""
    args: dict[str, Any] = {}
    for m in PARAM_PATTERN.finditer(inner_text):
        key = m.group(1).strip()
        val_raw = m.group(2).strip()
        val = _extract_cdata(val_raw)
        # Auto-type only if not CDATA-wrapped (CDATA means string)
        is_cdata = val_raw.startswith(_CDATA_OPEN) and val_raw.endswith(_CDATA_CLOSE)
        if is_cdata:
            typed_val = val  # CDATA content is always string
        else:
            typed_val = _auto_type(val)
        if key in args:
            existing = args[key]
            if isinstance(existing, list):
                existing.append(typed_val)
            else:
                args[key] = [existing, typed_val]
        else:
            args[key] = typed_val
    return args


def _format_tool_call(name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    return {
        "id": f"call_{uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def format_tool_calls_for_prompt(tool_calls_raw: Any) -> str:
    """Format tool call history back into DSML format for prompt injection."""
    if isinstance(tool_calls_raw, str):
        try:
            tool_calls_raw = json.loads(tool_calls_raw)
        except (json.JSONDecodeError, ValueError):
            return ""
    if not isinstance(tool_calls_raw, list) or not tool_calls_raw:
        return ""

    blocks: list[str] = []
    for tc in tool_calls_raw:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function", {})
        name = tc.get("name") or fn.get("name", "")
        if not name:
            continue
        args_raw = tc.get("arguments") or fn.get("arguments") or "{}"
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except (json.JSONDecodeError, ValueError):
                args = {"content": args_raw}
        else:
            args = args_raw

        params = _format_params_dsml(args)
        if params.strip():
            block = (
                f'  <|DSML|invoke name="{name}">\n'
                f'{params}\n'
                f'  </|DSML|invoke>'
            )
        else:
            block = f'  <|DSML|invoke name="{name}"></|DSML|invoke>'
        blocks.append(block)

    if not blocks:
        return ""

    return (
        "<|DSML|tool_calls>\n"
        + "\n".join(blocks)
        + "\n</|DSML|tool_calls>"
    )


def _format_params_dsml(args: Any, indent: str = "    ") -> str:
    """Format parameter dict into DSML parameter nodes with CDATA."""
    if isinstance(args, dict):
        if not args:
            return ""
        return "\n".join(
            _format_param_node(k, v, indent) for k, v in sorted(args.items())
        )
    elif isinstance(args, list):
        return "\n".join(
            _format_param_node("item", item, indent) for item in args
        )
    else:
        return f'{indent}<|DSML|parameter name="content">{_cdata(str(args))}</|DSML|parameter>'


def _format_param_node(name: str, value: Any, indent: str) -> str:
    """Format a single parameter node."""
    open_tag = f'<|DSML|parameter name="{_escape_xml(name)}">'
    close = "</|DSML|parameter>"
    if value is None:
        return f"{indent}{open_tag}{close}"
    elif isinstance(value, (bool, int, float)):
        return f"{indent}{open_tag}{str(value).lower() if isinstance(value, bool) else str(value)}{close}"
    elif isinstance(value, (dict, list)):
        inner = json.dumps(value, ensure_ascii=False)
        return f"{indent}{open_tag}{_cdata(inner)}{close}"
    elif isinstance(value, str):
        return f"{indent}{open_tag}{_cdata(value)}{close}"
    else:
        return f"{indent}{open_tag}{_cdata(str(value))}{close}"


def _cdata(text: str) -> str:
    """Wrap text in CDATA, handling nested termination markers."""
    if "]]>" in text:
        text = text.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{text}]]>"


def _escape_xml(text: str) -> str:
    """Escape XML attribute value."""
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def build_dsml_tool_prompt(tools: list[dict]) -> str:
    """Build DSML tool definitions for injection into system prompt.

    Each tool gets its own <|DSML|tool_calls> block with parameter descriptions
    as CDATA values.
    """
    if not tools:
        return ""

    blocks: list[str] = []
    for tool in tools:
        fn = tool.get("function", tool)
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})

        if not name:
            continue

        param_lines: list[str] = []
        props = params.get("properties", {}) if isinstance(params, dict) else {}
        required = params.get("required", []) if isinstance(params, dict) else []

        for pname, pdef in props.items():
            if not isinstance(pdef, dict):
                continue
            ptype = pdef.get("type", "string")
            pdesc = pdef.get("description", "")
            is_req = pname in required
            req_str = " (required)" if is_req else " (optional)"
            desc_text = f"{ptype} - {pdesc}{req_str}" if pdesc else f"{ptype}{req_str}"
            param_lines.append(
                f'    <|DSML|parameter name="{pname}"><![CDATA[{desc_text}]]></|DSML|parameter>'
            )

        if not param_lines:
            continue

        block = f'<|DSML|tool_calls>\n  <|DSML|invoke name="{name}">\n'
        block += "\n".join(param_lines)
        block += '\n  </|DSML|invoke>\n</|DSML|tool_calls>'
        blocks.append(block)

    if not blocks:
        return ""

    # Add the instruction block
    instruction_block = """When you need to call a tool, output EXACTLY this format — no markdown fences, no extra text:

<|DSML|tool_calls>
  <|DSML|invoke name="ToolName">
    <|DSML|parameter name="param1"><![CDATA[value1]]></|DSML|parameter>
  </|DSML|invoke>
</|DSML|tool_calls>

RULES:
1. Use <|DSML|tool_calls> wrapper.
2. ALL string values MUST use <![CDATA[...]]> even for short values.
3. No markdown code fences around the DSML block.
4. The first non-whitespace characters must be exactly <|DSML|tool_calls> when calling a tool.
5. Do not add any explanatory text before or after the DSML block when calling a tool.
"""

    return instruction_block + "\nAvailable tools:\n\n" + "\n\n".join(blocks)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dsml_parser.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add server/parser/dsml_parser.py tests/test_dsml_parser.py
git commit -m "feat: add DSML parser with CDATA support"
```

---

### Task 3: Create `server/services/dsml_prompt.py` — DSML Prompt Builder

**Files:**
- Create: `server/services/dsml_prompt.py`
- Test: `tests/test_dsml_prompt.py`

- [ ] **Step 1: Write the failing tests**

```python
"""tests/test_dsml_prompt.py — DSML prompt builder unit tests"""
import pytest
from server.services.dsml_prompt import (
    build_dsml_prompt,
    DSML_BOS, DSML_SYS, DSML_USER, DSML_ASST,
    DSML_TOOL, DSML_EOS, DSML_TOOL_END, DSML_INSTR_END,
)

def test_basic_user_assistant():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    result = build_dsml_prompt(messages)
    assert result.startswith(DSML_BOS + DSML_SYS)
    assert "You are a helpful assistant." in result
    assert DSML_INSTR_END in result
    assert DSML_USER + "Hello" in result
    assert DSML_ASST + "Hi there!" in result
    assert result.endswith(DSML_EOS)

def test_with_tool_definitions():
    messages = [{"role": "user", "content": "Read file.txt"}]
    tools = [{
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file"}
                },
                "required": ["file_path"]
            }
        }
    }]
    result = build_dsml_prompt(messages, tools=tools, tool_choice="auto")
    assert "<|DSML|tool_calls>" in result
    assert "Read" in result
    assert "<![CDATA[" in result

def test_with_tool_history():
    messages = [
        {"role": "user", "content": "Read file.txt"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "Read", "arguments": '{"file_path": "/path/file.txt"}'}}
        ]},
        {"role": "tool", "content": "File contents", "tool_call_id": "call_1"},
        {"role": "user", "content": "Thanks"},
    ]
    result = build_dsml_prompt(messages)
    assert DSML_TOOL in result
    assert "File contents" in result
    assert DSML_TOOL_END in result
    # Tool calls should be in DSML format
    assert "<|DSML|tool_calls>" in result

def test_no_system_message_with_tools():
    messages = [{"role": "user", "content": "Hello"}]
    tools = [{"type": "function", "function": {"name": "Test", "description": "Test tool", "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}}]
    result = build_dsml_prompt(messages, tools=tools)
    assert DSML_BOS + DSML_SYS in result
    assert "<|DSML|tool_calls>" in result

def test_tool_result_truncation():
    messages = [
        {"role": "user", "content": "Search"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "Search", "arguments": "{}"}}]},
        {"role": "tool", "content": "A" * 5000, "tool_call_id": "c1"},
    ]
    result = build_dsml_prompt(messages)
    assert DSML_TOOL in result
    tool_idx = result.index(DSML_TOOL)
    end_idx = result.index(DSML_TOOL_END)
    tool_content = result[tool_idx + len(DSML_TOOL):end_idx]
    assert len(tool_content) <= 1000  # truncated

def test_max_history_len():
    messages = [{"role": "user", "content": f"msg_{i}"} for i in range(30)]
    result = build_dsml_prompt(messages, max_history_len=10)
    # Only recent messages should be present
    assert "msg_0" not in result
    assert "msg_29" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dsml_prompt.py -v`
Expected: FAIL with ImportError (module not found)

- [ ] **Step 3: Write the DSML prompt builder**

```python
"""server/services/dsml_prompt.py — DSML prompt builder for DeepSeek V4 Pro.

Constructs flat-text prompts using ds2api-style tokens and DSML tool call format.
"""

from __future__ import annotations
import json
from typing import Any, List, Optional

from server.parser.dsml_parser import (
    build_dsml_tool_prompt,
    format_tool_calls_for_prompt,
    clean_tool_text,
)

# DSML tokens (ds2api style)
DSML_BOS = "<｜begin▁of▁sentence｜>"
DSML_SYS = "<｜System｜>"
DSML_USER = "<｜User｜>"
DSML_ASST = "<｜Assistant｜>"
DSML_TOOL = "<｜Tool｜>"
DSML_EOS = "<｜end▁of▁sentence｜>"
DSML_TOOL_END = "<｜end▁of▁toolresults｜>"
DSML_INSTR_END = "<｜end▁of▁instructions｜>"


def build_dsml_prompt(
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    tool_choice: Optional[str] = None,
    images: Optional[List[str]] = None,
    max_history_len: Optional[int] = None,
) -> str:
    """Build a DSML-format flat-text prompt from OpenAI-compatible messages.

    Args:
        messages: List of message dicts with "role", "content", "tool_calls", "tool_call_id"
        tools: Optional list of tool definitions (OpenAI format)
        tool_choice: "auto", "required", "none", or a specific tool name
        images: Not used in DSML format (handled separately by DeepSeek)
        max_history_len: If set, truncate to this many recent messages

    Returns:
        Flat text prompt in DSML format
    """
    if max_history_len and len(messages) > max_history_len:
        messages = messages[-max_history_len:]

    parts: list[str] = [DSML_BOS]

    # Build system section
    system_content = _extract_system_content(messages)
    non_system_msgs = [m for m in messages if m.get("role") != "system"]

    tool_defs = ""
    if tools:
        tool_defs = build_dsml_tool_prompt(tools)
        if tool_choice:
            tool_defs += f"\ntool_choice: {tool_choice}"

    sys_text = system_content or ""
    if tool_defs:
        if sys_text.strip():
            sys_text = sys_text.strip() + "\n\n" + tool_defs
        else:
            sys_text = tool_defs

    if sys_text.strip():
        parts.append(DSML_SYS + sys_text.strip() + DSML_INSTR_END)

    last_role = ""
    for msg in non_system_msgs:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, list):
                texts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                text = " ".join(texts)
            else:
                text = str(content) if content else ""
            parts.append(DSML_USER + text)

        elif role == "assistant":
            segments: list[str] = []
            if content and str(content).strip():
                segments.append(str(content).strip())

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                dsml = format_tool_calls_for_prompt(tool_calls)
                if dsml:
                    segments.append(dsml)

            if segments:
                parts.append(DSML_ASST + "\n\n".join(segments) + DSML_EOS)

        elif role == "tool":
            tool_content = str(content) if content else ""
            # Truncate long tool results
            if len(tool_content) > 1000:
                tool_content = tool_content[:1000] + "...(truncated)"
            parts.append(DSML_TOOL + tool_content + DSML_TOOL_END)

        last_role = role

    # Ensure prompt ends with Assistant marker (so model starts generating)
    if last_role != "assistant" and not parts[-1].endswith(DSML_EOS):
        parts.append(DSML_ASST)

    return "".join(parts)


def _extract_system_content(messages: List[dict]) -> str:
    """Extract and concatenate system messages."""
    contents: list[str] = []
    for m in messages:
        if m.get("role") == "system":
            c = m.get("content", "")
            if c:
                contents.append(str(c).strip())
    return "\n\n".join(contents)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dsml_prompt.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/dsml_prompt.py tests/test_dsml_prompt.py
git commit -m "feat: add DSML prompt builder with ds2api-style tokens"
```

---

### Task 4: Modify `server/services/prompt_service.py` — Wire DSML Prompt Builder

**Files:**
- Modify: `server/services/prompt_service.py`
- Test: `tests/test_prompt_service.py` (existing test if any)

- [ ] **Step 1: Modify prompt_service.py**

Replace the `build_prompt` method and remove `_format_msgs`, `_build_prompt_sync`, `_inject_tools_as_system`.

**Old code in PromptService:**
```python
async def build_prompt(self, messages, tools=None, tool_choice=None, images=None, max_history_len=None):
    return _build_prompt_sync(
        messages, tools=tools, images=images,
        tool_choice=tool_choice, max_history_len=max_history_len,
    )
```

**New code:**
```python
async def build_prompt(self, messages, tools=None, tool_choice=None, images=None, max_history_len=None):
    from server.services.dsml_prompt import build_dsml_prompt
    return build_dsml_prompt(
        messages, tools=tools, tool_choice=tool_choice,
        images=images, max_history_len=max_history_len,
    )
```

Remove these functions from the file (or remove the file entirely if `prompt_service.py` only contained them):
- `_build_prompt_sync`
- `_format_msgs`
- `_inject_tools_as_system`

Keep `_load_prompt_service`, `trim_context`, `cascade_compress_tool_results` if they exist.

- [ ] **Step 2: Verify the prompt_service imports work**

Run: `python -c "from server.services.prompt_service import PromptService; print('OK')"`
Expected: "OK"

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/ -v --timeout=30 2>&1 | head -50`
Expected: Existing tests pass (or skip if no relevant tests)

- [ ] **Step 4: Commit**

```bash
git add server/services/prompt_service.py
git commit -m "refactor: wire DSML prompt builder into PromptService"
```

---

### Task 5: Modify `server/services/stream_service.py` — Wire StreamSieve

**Files:**
- Modify: `server/services/stream_service.py`
- Test: `tests/test_stream_service.py` (existing)

- [ ] **Step 1: Modify stream_service.py**

Replace `StructuredResponseStreamParser` usage with `StreamSieve` + `dsml_parser.parse_dsml_tool_calls`.

**In the generate() method:**

Old code (using StructuredResponseStreamParser):
```python
json_parser = StructuredResponseStreamParser()
# ...
stream_text, parsed_calls = json_parser.feed(text_chunk)
if parsed_calls:
    # handle tool calls
```

New code:
```python
from server.parser.dsml_sieve import StreamSieve

sieve = StreamSieve(tool_names=[t.get("function", t).get("name", "") for t in (tools or [])])

# In the streaming loop:
events = sieve.feed(text_chunk)
for event in events:
    if event.type == "text":
        # Yield as content (same as before)
        yield _chunk({"index": index, "delta": {"content": event.data}})
    elif event.type == "tool_calls":
        tool_calls_list = []
        for idx, tc in enumerate(event.data):
            tool_calls_list.append({
                "index": idx,
                "id": tc["id"],
                "type": "function",
                "function": tc["function"],
            })
        # Emit tool_calls chunk
        yield _chunk({"index": index, "delta": {"tool_calls": tool_calls_list}})
        # Watermark
        yield _chunk({"index": index, "delta": {"content": f"\n\n<!-- PROXY_SID:{conv_uuid} -->"}})
        yield _chunk({"index": index, "delta": {}, "finish_reason": "tool_calls"})
        yield "data: [DONE]\n\n"
        # Save state and return
        slot.accumulated_prompt = None
        # ... save conv_state ...
        return

# At end of stream:
events = sieve.flush()
for event in events:
    if event.type == "text" and event.data.strip():
        yield _chunk({"index": index, "delta": {"content": event.data}})
    elif event.type == "tool_calls":
        # Same tool_calls handling as above
        ...
```

Replace import: remove `StructuredResponseStreamParser`, keep all other imports.

- [ ] **Step 2: Verify the stream_service imports work**

Run: `python -c "from server.services.stream_service import StreamService; print('OK')"`
Expected: "OK"

- [ ] **Step 3: Commit**

```bash
git add server/services/stream_service.py
git commit -m "refactor: replace StructuredResponseStreamParser with StreamSieve"
```

---

### Task 6: Integration test — full streaming cycle with DSML tool calls

**Files:**
- Create: `tests/test_integration_dsml.py`

- [ ] **Step 1: Write integration tests**

```python
"""tests/test_integration_dsml.py — Integration tests for DSML tool call pipeline."""
import json
import pytest
from server.parser.dsml_sieve import StreamSieve
from server.parser.dsml_parser import parse_dsml_tool_calls, build_dsml_tool_prompt
from server.services.dsml_prompt import build_dsml_prompt

def test_full_cycle_no_tools():
    """Basic conversation without tools."""
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    prompt = build_dsml_prompt(messages)
    assert "<｜begin▁of▁sentence｜>" in prompt
    assert "<｜System｜>" in prompt
    assert "<｜User｜>Hello" in prompt
    assert prompt.endswith("<｜Assistant｜>")  # wait for model response

def test_full_cycle_with_tools():
    """Conversation with tool definitions."""
    messages = [{"role": "user", "content": "Read file.txt"}]
    tools = [{"type": "function", "function": {"name": "Read", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
    prompt = build_dsml_prompt(messages, tools=tools)
    assert "Read" in prompt
    assert "<![CDATA[" in prompt

def test_stream_sieve_with_chunked_input():
    """Simulate realistic chunked streaming."""
    sieve = StreamSieve(tool_names=["Read"])
    chunks = [
        "Hel",
        "lo,",
        " I'll read that file for you.\n\n<|DSML|tool_calls>\n  <|DSML|invoke name=\"Read\">\n    <|DSML|parameter name=\"path\"><![CDATA[/path/file.txt]]></|DSML|parameter>\n  </|DSML|invoke>\n</|DSML|tool_calls>",
    ]
    all_events = []
    for chunk in chunks:
        events = sieve.feed(chunk)
        all_events.extend(events)
    text = "".join(e.data for e in all_events if e.type == "text")
    tool_events = [e for e in all_events if e.type == "tool_calls"]
    assert "Hello, I'll read that file for you." in text
    assert len(tool_events) >= 1
    assert tool_events[0].data[0]["function"]["name"] == "Read"

def test_stream_sieve_multiple_tools_chunked():
    """Multiple tool calls in one response."""
    sieve = StreamSieve(tool_names=["Read", "Write"])
    chunk = '<|DSML|tool_calls><|DSML|invoke name="Read"><|DSML|parameter name="a"><![CDATA[1]]></|DSML|parameter></|DSML|invoke><|DSML|invoke name="Write"><|DSML|parameter name="b"><![CDATA[2]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>'
    events = sieve.feed(chunk)
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) >= 1
    assert len(tool_events[0].data) == 2

def test_prompt_with_tool_history():
    """Prompt with tool calls in history should round-trip cleanly."""
    messages = [
        {"role": "user", "content": "Search for X"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "Search", "arguments": '{"query": "X"}'}}]},
        {"role": "tool", "content": "Result: found Y", "tool_call_id": "c1"},
        {"role": "user", "content": "Thanks"},
    ]
    prompt = build_dsml_prompt(messages)
    assert "<|DSML|tool_calls>" in prompt
    assert "Search" in prompt
    assert "<｜Tool｜>" in prompt
    assert "Result: found Y" in prompt
    assert "<｜end▁of▁toolresults｜>" in prompt
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_integration_dsml.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_dsml.py
git commit -m "test: add integration tests for DSML tool call pipeline"
```

---

### Task 7: Cleanup — remove old parser modules

**Files:**
- Archive/remove: `server/parser/stream_parser.py`
- Archive/remove: `server/parser/tool_parser.py`
- Modify: `_server_legacy.py` — remove imports of old parsers

**Do NOT delete** — move to `server/parser/archive/` or just leave as dead code. Mark them as deprecated with a comment at the top.

- [ ] **Step 1: Mark old parsers as deprecated**

Add to the top of `server/parser/stream_parser.py`:
```python
# DEPRECATED: Replaced by dsml_sieve.py + dsml_parser.py
# This module will be removed in a future cleanup.
```

Add to the top of `server/parser/tool_parser.py`:
```python
# DEPRECATED: Replaced by dsml_parser.py
# This module will be removed in a future cleanup.
```

- [ ] **Step 2: Remove old imports from _server_legacy.py**

Remove these lines from `_server_legacy.py`:
```python
from server.parser.stream_parser import StructuredResponseStreamParser
from server.parser.tool_parser import (
    _parse_tool_calls, _parse_param_value, _parse_param, _get_param_type,
    _clean_xml_string, _fix_json_strings, _parse_xml_to_json_compatible,
    _CONTENT_STRIP_PATTERN, _auto_close_tags,
)
```

- [ ] **Step 3: Verify imports still work**

Run: `python -c "from _server_legacy import app; print('OK')"`
Expected: "OK"

- [ ] **Step 4: Commit**

```bash
git add server/parser/stream_parser.py server/parser/tool_parser.py _server_legacy.py
git commit -m "chore: mark old parsers as deprecated, remove unused imports"
```

---

### Task 8: Run full test suite

**Files:**
- No file changes — just verification

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 2: Quick smoke test — start server**

Run: `timeout 10 python _server_legacy.py 2>&1 || true`
Expected: Server starts without errors, listens on port 4570

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: final cleanup after DSML migration"
```
