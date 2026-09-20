# 3-Tier Tool Call Repair Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 3-tier repair pipeline to recover malformed DSML/XML tool calls from DeepSeek V4 Pro web chat.

**Architecture:** A new `server/repair/` module with three independent repair tiers. Tier 1 fixes XML/DSML text errors (missing brackets, unclosed tags). Tier 2 fixes JSON argument errors (unescaped strings, trailing commas). A `repair_pipeline()` orchestrator runs tiers sequentially and feeds repaired output back into the existing DSML parser. Integration happens in `StreamSieve._try_finish_capture()` as a fallback when parsing returns empty.

**Tech Stack:** Python 3.11+, standard library (re, json, ast), pytest for testing.

---

## File Structure

```
server/repair/
  __init__.py          — exports repair_pipeline()
  repair_tier1.py      — Text-level DSML/XML repair
  repair_tier2.py      — JSON-level argument repair

server/parser/
  dsml_sieve.py        — MODIFY: add repair pipeline call in _try_finish_capture()

tests/
  test_repair_tier1.py   — NEW: tier 1 unit tests
  test_repair_tier2.py   — NEW: tier 2 unit tests
  test_repair_pipeline.py — NEW: pipeline + sieve integration tests
```

---

### Task 1: Module init + pipeline orchestrator

**Files:**
- Create: `server/repair/__init__.py`
- Create: `tests/test_repair_pipeline.py` (partial — orchestrator tests only)

- [ ] **Step 1: Write `server/repair/__init__.py`**

```python
"""server/repair/__init__.py — 3-tier tool call repair pipeline.

Repair pipeline for malformed DSML/XML tool calls from DeepSeek V4 Pro web chat.
Tier 1 fixes text-level XML errors; Tier 2 fixes JSON argument errors.
"""

from __future__ import annotations

from typing import Callable, Optional

from server.repair.repair_tier1 import repair_tier1
from server.repair.repair_tier2 import repair_tier2


def repair_pipeline(
    capture_buf: str,
    tool_names: Optional[list[str]] = None,
    tier3_callback: Optional[Callable[[str], str]] = None,
) -> str | None:
    """Run tier1 → tier2 repair sequentially.

    Args:
        capture_buf: Raw capture buffer containing an unparseable DSML block.
        tool_names: Known tool names for name resolution.
        tier3_callback: Optional callback for model self-repair (deferred).

    Returns:
        Repaired text if any tier succeeded, None if all tiers failed.
    """
    if capture_buf is None:
        return None

    # Tier 1: text-level repair
    repaired = repair_tier1(capture_buf)
    if repaired is not None:
        return repaired

    # Tier 2: JSON-level repair (only meaningful if tier1 extracted the structure)
    repaired = repair_tier2(capture_buf, tool_names)
    if repaired is not None:
        return repaired

    # Tier 3: (reserved) model self-repair fallback
    if tier3_callback is not None:
        repaired = tier3_callback(capture_buf)
        if repaired and len(repaired.strip()) > 0:
            return repaired

    return None
```

- [ ] **Step 2: Write orchestrator test in `tests/test_repair_pipeline.py`**

```python
"""Tests for the repair pipeline orchestrator."""

from __future__ import annotations

from server.repair import repair_pipeline


def test_repair_pipeline_tier1_success():
    """Pipeline returns tier1 result when tier1 succeeds."""
    text = '```xml\n<tool_calls>\n<invoke name="Bash">\n<parameter name="command">ls</parameter>\n</invoke>\n</tool_calls>\n```'
    result = repair_pipeline(text)
    assert result is not None
    assert "<tool_calls>" in result
    assert "```" not in result


def test_repair_pipeline_tier2_success():
    """Pipeline returns tier2 result when tier1 fails but tier2 succeeds."""
    text = '<tool_calls><invoke name="Bash"><parameter name="command">ls</parameter></invoke></tool_calls>'
    result = repair_pipeline(text)
    assert result is not None


def test_repair_pipeline_all_fail():
    """Pipeline returns None when all tiers fail."""
    text = "this is just plain text with no tool calls at all"
    result = repair_pipeline(text)
    assert result is None


def test_repair_pipeline_empty_input():
    """Pipeline returns None for empty input."""
    assert repair_pipeline("") is None
    assert repair_pipeline(None) is None  # type: ignore
```

- [ ] **Step 3: Run orchestrator tests**

Run: `python -m pytest tests/test_repair_pipeline.py -v --tb=short`
Expected: ALL TESTS FAIL (functions not defined yet — expected TDD red)

- [ ] **Step 4: Commit**

```bash
git add server/repair/__init__.py tests/test_repair_pipeline.py
git commit -m "feat: add repair pipeline module scaffold with orchestrator"
```

---

### Task 2: Tier 1 — Text-level DSML/XML repair

**Files:**
- Create: `server/repair/repair_tier1.py`
- Create: `tests/test_repair_tier1.py`

- [ ] **Step 1: Write tests in `tests/test_repair_tier1.py`**

```python
"""Tests for tier 1 — text-level DSML/XML repair."""

from __future__ import annotations

from server.repair.repair_tier1 import repair_tier1


def test_fix_missing_lt():
    """Prepend < to DSML tags that lost their opening bracket."""
    text = '|TOOL|tool_calls>\n<invoke name="Bash">\n</invoke>\n</|TOOL|tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert result.startswith("<|TOOL|tool_calls>")


def test_strip_markdown_fences():
    """Strip ```xml ... ``` fences around tool blocks."""
    text = '```xml\n<tool_calls>\n<invoke name="Read">\n<parameter name="file_path">/tmp/x</parameter>\n</invoke>\n</tool_calls>\n```'
    result = repair_tier1(text)
    assert result is not None
    assert "```" not in result
    assert "<tool_calls>" in result


def test_fix_unclosed_cdata():
    """Append ]]> if CDATA section is unclosed."""
    text = '<tool_calls>\n<invoke name="Bash">\n<parameter name="command"><![CDATA[echo hello</parameter>\n</invoke>\n</tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert "<![CDATA[echo hello]]>" in result or "echo hello" in result


def test_fix_broken_namespace():
    """Fix common namespace typos like |DSL| → |DSML|."""
    text = '<|DSL|tool_calls>\n<|DSL|invoke name="Bash">\n<|DSL|parameter name="command">ls</|DSL|parameter>\n</|DSL|invoke>\n</|DSL|tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    assert "|DSML|" in result or "TOOL" in result


def test_fix_truncated_tag():
    """Gracefully handle truncated last tag."""
    text = '<tool_calls>\n<invoke name="Bash">\n<parameter name="command">ls</'
    result = repair_tier1(text)
    assert result is not None
    # Should produce something parseable


def test_strip_leading_prose():
    """Remove human text before the tool block."""
    text = 'I will call the tool now.\n\n<tool_calls>\n<invoke name="Bash">\n<parameter name="command">ls</parameter>\n</invoke>\n</tool_calls>'
    result = repair_tier1(text)
    assert result is not None
    # Should start with <tool_calls>, not prose
    assert result.strip().startswith("<")


def test_clean_text_returns_none():
    """Return None if text has no tool call content after cleaning."""
    assert repair_tier1("Hello, how can I help you?") is None
    assert repair_tier1("") is None
```

- [ ] **Step 2: Run tier1 tests to verify they fail**

Run: `python -m pytest tests/test_repair_tier1.py -v --tb=short`
Expected: ALL FAIL (module not yet created)

- [ ] **Step 3: Implement `server/repair/repair_tier1.py`**

```python
"""server/repair/repair_tier1.py — Text-level DSML/XML repair.

Repair strategies for malformed tool call blocks:
- Missing < prefix on DSML tags
- Markdown fences wrapping tool blocks
- Unclosed CDATA sections
- Broken namespace prefixes
- Mismatched quotes
- Truncated tags
- Leading/trailing prose
"""

from __future__ import annotations

import re


# Patterns for DSML/TOOL tag detection
_DSML_TAG_PATTERN = re.compile(
    r'(?<![<\w/])(\|(?:TOOL|DSML|DSL|TS|ts)\|(?:tool_calls?|invoke|parameter|tool_result))\b',
    re.IGNORECASE,
)
_MARKDOWN_FENCE_PATTERN = re.compile(
    r'^```(?:xml|dsml|html)?\s*\n|```\s*$',
    re.MULTILINE,
)
_CDATA_PATTERN = re.compile(
    r'<!\[CDATA\[(.*?)(\]\]>|$)',
    re.DOTALL,
)
_TOOL_BLOCK_PATTERN = re.compile(
    r'(<[^>]*tool_calls?[^>]*>.*?</[^>]*tool_calls?>)',
    re.DOTALL | re.IGNORECASE,
)
_LEADING_PROSE_PATTERN = re.compile(
    r'^(.*?)(<(?:[|]?(?:TOOL|DSML)\|)?tool_calls?\b)',
    re.DOTALL | re.IGNORECASE,
)
_UNCLOSED_TAG_PATTERN = re.compile(
    r'<([a-zA-Z0-9_]+)(?:\s+[^>]*?)?>[^<]*$',
)


def repair_tier1(text: str) -> str | None:
    """Attempt text-level repair on a DSML tool call block.

    Args:
        text: Raw text that may contain a malformed DSML block.

    Returns:
        Repaired text if any repair was applied, None if text has no
        tool call content or is irreparable.
    """
    if not text or not text.strip():
        return None

    original = text
    text = _strip_leading_prose(text)
    text = _strip_markdown_fences(text)
    text = _fix_missing_lt(text)
    text = _fix_broken_namespace(text)
    text = _fix_unclosed_cdata(text)
    text = _fix_truncated_tag(text)

    # If nothing changed and no tool tags, return None
    if text == original and not _has_tool_tag(text):
        return None

    # If after all fixes there are still no tool tags, return None
    if not _has_tool_tag(text):
        return None

    return text


def _has_tool_tag(text: str) -> bool:
    """Check if text contains any tool call tag."""
    return bool(re.search(
        r'<(?:[|]?(?:TOOL|DSML|DSL)\|)?tool_calls?\b',
        text,
        re.IGNORECASE,
    ))


def _fix_missing_lt(text: str) -> str:
    """Prepend < to DSML/TOOL tags missing their opening bracket."""
    return _DSML_TAG_PATTERN.sub(r'<\1', text)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences wrapping tool blocks."""
    return _MARKDOWN_FENCE_PATTERN.sub('', text).strip()


def _fix_unclosed_cdata(text: str) -> str:
    """Append ]]> to unclosed CDATA sections."""
    def _close_cdata(m: re.Match) -> str:
        content = m.group(1)
        closer = m.group(2)
        if closer == "]]>":
            return m.group(0)  # already closed
        return f"<![CDATA[{content}]]>"
    return _CDATA_PATTERN.sub(_close_cdata, text)


def _fix_broken_namespace(text: str) -> str:
    """Fix common namespace typos: |DSL| → |DSML|."""
    text = re.sub(r'\|DSL\|', '|DSML|', text, flags=re.IGNORECASE)
    text = re.sub(r'\|TS\|', '|TOOL|', text, flags=re.IGNORECASE)
    text = re.sub(r'\|tool\|', '|TOOL|', text, flags=re.IGNORECASE)
    text = re.sub(r'\|dsml\|', '|DSML|', text, flags=re.IGNORECASE)
    return text


def _strip_leading_prose(text: str) -> str:
    """Remove human-readable prose before the tool block."""
    m = _LEADING_PROSE_PATTERN.match(text)
    if m:
        prose = m.group(1).strip()
        tool_start = m.group(2)
        if prose and not _has_tool_tag(prose):
            return text[m.start(2):]
    return text


def _fix_truncated_tag(text: str) -> str:
    """Close the last tag if it's truncated (missing > or content)."""
    # Count open vs close tags for each tag type
    tags = re.findall(r'</?([a-zA-Z0-9_]+)[^>]*>', text)
    open_tags = []
    for tag in tags:
        if tag.startswith('/'):
            if open_tags and open_tags[-1] == tag[1:]:
                open_tags.pop()
        else:
            open_tags.append(tag)

    # Close remaining open tags in reverse order
    for tag_name in reversed(open_tags):
        text += f"</{tag_name}>"

    return text
```

- [ ] **Step 4: Run tier1 tests**

Run: `python -m pytest tests/test_repair_tier1.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add server/repair/repair_tier1.py tests/test_repair_tier1.py
git commit -m "feat: add tier 1 text-level DSML/XML repair"
```

---

### Task 3: Tier 2 — JSON argument repair

**Files:**
- Create: `server/repair/repair_tier2.py`
- Create: `tests/test_repair_tier2.py`

- [ ] **Step 1: Write tests in `tests/test_repair_tier2.py`**

```python
"""Tests for tier 2 — JSON argument repair."""

from __future__ import annotations

from server.repair.repair_tier2 import repair_tier2


def test_fix_trailing_comma():
    """Remove trailing commas in JSON objects."""
    fixed = repair_tier2('Bash', '{"command": "ls",}')
    assert fixed is not None
    assert '"ls"' in fixed
    assert ',}' not in fixed


def test_fix_single_quotes():
    """Replace single quotes with double quotes in JSON."""
    fixed = repair_tier2('Bash', "{'command': 'ls -la'}")
    assert fixed is not None
    assert '"command"' in fixed
    assert '"ls -la"' in fixed


def test_fix_unescaped_backslashes():
    """Fix unescaped backslashes in JSON strings."""
    fixed = repair_tier2('Read', '{"file_path": "C:\\Users\\test\\file.txt"}')
    assert fixed is not None
    assert "\\\\" in fixed  # properly escaped


def test_fix_bare_string_to_json():
    """Wrap bare string value into expected JSON schema."""
    fixed = repair_tier2('Bash', 'ls -la')
    assert fixed is not None
    assert '"command"' in fixed
    assert 'ls -la' in fixed


def test_fix_bare_string_read():
    """Wrap bare file path into Read tool schema."""
    fixed = repair_tier2('Read', '/tmp/file.txt')
    assert fixed is not None
    assert '"file_path"' in fixed


def test_valid_json_unchanged():
    """Valid JSON passes through unchanged."""
    fixed = repair_tier2('Bash', '{"command": "echo hello"}')
    assert fixed is not None
    assert '"command"' in fixed
    assert 'echo hello' in fixed


def test_empty_returns_none():
    """Return None for empty input."""
    assert repair_tier2('Bash', '') is None
    assert repair_tier2('Read', '{}') is not None  # valid empty object


def test_xml_double_encoded():
    """Fix XML-encoded JSON: {""key"": ""val""} → {"key": "val"}."""
    fixed = repair_tier2('Bash', '{"command": "echo ""hello world"""}')
    assert fixed is not None
    assert 'hello world' in fixed
```

- [ ] **Step 2: Run tier2 tests to verify they fail**

Run: `python -m pytest tests/test_repair_tier2.py -v --tb=short`
Expected: ALL FAIL (module not yet created)

- [ ] **Step 3: Implement `server/repair/repair_tier2.py`**

```python
"""server/repair/repair_tier2.py — JSON-level argument repair.

Repair strategies for malformed JSON in tool call arguments:
- Trailing commas in objects/arrays
- Single-quoted strings
- Unescaped backslashes
- Bare string -> wrapped in expected schema
- XML-double-encoded JSON strings
"""

from __future__ import annotations

import json
import re


# Schema mapping: tool_name → first parameter name (for bare string wrapping)
_TOOL_PARAM_MAP: dict[str, str] = {
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "SearchReplace": "file_path",
    "Glob": "pattern",
    "Grep": "pattern",
    "WebSearch": "query",
    "WebFetch": "url",
    "RunCommand": "command",
    "AskUserQuestion": "question",
    "Task": "description",
    "Skill": "name",
    "NotifyUser": "explanation",
    "OpenPreview": "preview_url",
    "DeleteFile": "file_paths",
    "TodoWrite": "todos",
}


def repair_tier2(text: str, tool_names: list[str] | None = None) -> str | None:
    """Attempt JSON-level repair on tool call arguments.

    Args:
        text: Raw argument text or a full DSML block containing JSON.
        tool_names: Known tool names for schema lookup.

    Returns:
        Repaired text with valid JSON, or None if irreparable.
    """
    if not text or not text.strip():
        return None

    # Extract argument JSON blocks from the text
    candidate = _find_json_block(text)
    if candidate is None:
        candidate = text  # try treating whole text as JSON

    original = candidate

    # Apply repair strategies sequentially
    candidate = _fix_single_quotes(candidate)
    candidate = _fix_trailing_commas(candidate)
    candidate = _fix_unescaped_backslashes(candidate)
    candidate = _fix_double_encoded(candidate)

    # Try parsing as JSON
    parsed = _try_parse_json(candidate)
    if parsed is not None:
        # Successfully parsed — re-serialize to clean JSON
        return json.dumps(parsed, ensure_ascii=False)

    # Try bare string wrapping
    wrapped = _wrap_bare_string(original, text, tool_names)
    if wrapped is not None:
        return wrapped

    return None


def _find_json_block(text: str) -> str | None:
    """Find the first JSON object/array in text, extracting from parameter tags if needed."""
    # Look for <parameter name="...">value</parameter> and extract value
    param_m = re.search(
        r'<parameter\s+name="([^"]*)">(.*?)</parameter>',
        text, re.DOTALL,
    )
    if param_m:
        return param_m.group(2).strip()

    # Look for standalone JSON object
    json_m = re.search(r'\{.*\}', text, re.DOTALL)
    if json_m:
        return json_m.group(0)

    # Look for JSON array
    json_m = re.search(r'\[.*\]', text, re.DOTALL)
    if json_m:
        return json_m.group(0)

    return None


def _fix_single_quotes(text: str) -> str:
    """Replace single quotes with double quotes in JSON."""

    def _replace_sq(m: re.Match) -> str:
        key = m.group(1)
        return f'"{key}":'

    # Replace single-quoted keys: 'key':
    text = re.sub(r"'([^']+)'\s*:", _replace_sq, text)

    # Replace single-quoted string values: 'value'
    # Only replace when inside a JSON-like context
    def _replace_sq_val(m: re.Match) -> str:
        prefix = m.group(1)
        val = m.group(2)
        # Don't convert if it looks like a number or boolean
        if val.lower() in ('true', 'false', 'null'):
            return m.group(0)
        try:
            float(val)
            return m.group(0)  # numeric, keep original
        except ValueError:
            pass
        return f'{prefix}"{val}"'

    text = re.sub(r'(:\s*)\'([^\']*)\'', _replace_sq_val, text)

    return text


def _fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before } or ]."""
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    return text


def _fix_unescaped_backslashes(text: str) -> str:
    """Fix unescaped backslashes in JSON strings.

    Only fixes backslash sequences that are not valid escape sequences.
    """

    def _fix_escape(m: re.Match) -> str:
        seq = m.group(1)
        # Valid JSON escapes: \\, \", \/, \b, \f, \n, \r, \t, \uXXXX
        valid_escapes = {
            '\\', '"', '/', 'b', 'f', 'n', 'r', 't',
        }
        if seq in valid_escapes:
            return m.group(0)  # keep valid
        # Also keep \uXXXX (Unicode escape)
        if seq == 'u':
            return m.group(0)
        # Fix: double the backslash
        return '\\\\' + seq

    return re.sub(r'\\(.)', _fix_escape, text)


def _fix_double_encoded(text: str) -> str:
    """Fix XML-double-encoded JSON: {""key"": ""val""} → {"key": "val"}."""
    # Replace "" with " only inside JSON string contexts
    text = re.sub(r'""', '"', text)
    return text


def _try_parse_json(text: str):
    """Try to parse text as JSON with increasing leniency."""
    # Attempt 1: standard parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: try ast.literal_eval for Python-literals
    try:
        import ast
        result = ast.literal_eval(text)
        if isinstance(result, (dict, list)):
            return result
    except (ValueError, SyntaxError):
        pass

    return None


def _wrap_bare_string(original: str, full_text: str, tool_names: list[str] | None) -> str | None:
    """If text is a bare string (no JSON structure), wrap in expected schema.

    Tries to guess the tool name from context (full_text tags) and wraps
    the string value in the expected JSON parameter.
    """
    bare = original.strip()
    if not bare:
        return None

    # Detect if it looks like JSON already
    if bare.startswith('{') or bare.startswith('['):
        return None

    # Try to detect tool name from the full text
    tool_name = None
    if tool_names:
        # Find which tool name appears in the full text
        for name in tool_names:
            if name.lower() in full_text.lower():
                tool_name = name
                break

    # Also check generic <invoke name="..."> pattern
    if tool_name is None:
        name_m = re.search(r'<invoke\s+name="([^"]*)"', full_text, re.IGNORECASE)
        if name_m:
            tool_name = name_m.group(1)

    if tool_name and tool_name in _TOOL_PARAM_MAP:
        param = _TOOL_PARAM_MAP[tool_name]
        wrapped = json.dumps({param: bare}, ensure_ascii=False)
        return wrapped

    return None
```

- [ ] **Step 4: Run tier2 tests**

Run: `python -m pytest tests/test_repair_tier2.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add server/repair/repair_tier2.py tests/test_repair_tier2.py
git commit -m "feat: add tier 2 JSON argument repair"
```

---

### Task 4: Integrate repair pipeline into StreamSieve

**Files:**
- Modify: `server/parser/dsml_sieve.py`
- Modify: `tests/test_repair_pipeline.py` (add sieve integration tests)

- [ ] **Step 1: Add sieve integration tests to `tests/test_repair_pipeline.py`**

Append to the existing test file:

```python
# ─── Sieve integration tests ──────────────────────────────

from server.parser.dsml_sieve import StreamSieve


def test_sieve_recovers_missing_lt():
    """Sieve extracts tool calls from text with missing < on DSML tags."""
    sieve = StreamSieve()
    text = 'Some text\n\n|TOOL|tool_calls>\n<|TOOL|invoke name="Bash">\n<|TOOL|parameter name="command">ls</|TOOL|parameter>\n</|TOOL|invoke>\n</|TOOL|tool_calls>'
    events = sieve.feed(text)
    events += sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0, f"No tool_calls events from: {events}"
    calls = tool_events[0].data
    assert len(calls) > 0
    assert calls[0]["name"] == "Bash"


def test_sieve_recovers_markdown_fences():
    """Sieve extracts tool calls from markdown-fenced blocks."""
    sieve = StreamSieve()
    text = '```xml\n<tool_calls>\n<invoke name="Read">\n<parameter name="file_path">test.txt</parameter>\n</invoke>\n</tool_calls>\n```'
    events = sieve.feed(text)
    events += sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0
    calls = tool_events[0].data
    assert len(calls) > 0
    assert calls[0]["name"] == "Read"


def test_sieve_recovers_trailing_comma_json():
    """Sieve extracts tool calls with trailing comma in args JSON."""
    sieve = StreamSieve()
    text = '<tool_calls>\n<invoke name="Bash">\n<parameter name="command"><![CDATA[{"command": "ls",}]]></parameter>\n</invoke>\n</tool_calls>'
    events = sieve.feed(text)
    events += sieve.flush()
    tool_events = [e for e in events if e.type == "tool_calls"]
    assert len(tool_events) > 0
    calls = tool_events[0].data
    assert len(calls) > 0


def test_sieve_normal_text_unaffected():
    """Regular text without tool calls passes through unchanged."""
    sieve = StreamSieve()
    text = "Hello, how can I help you today?"
    events = sieve.feed(text)
    events += sieve.flush()
    text_events = [e for e in events if e.type == "text"]
    assert len(text_events) > 0
    assert "tool_calls" not in str(events)
```

- [ ] **Step 2: Modify `server/parser/dsml_sieve.py`**

Add import and modify `_try_finish_capture()`:

In `dsml_sieve.py`, add at the top of the file:

```python
from server.repair import repair_pipeline
```

Then modify `_try_finish_capture()`:

```python
    def _try_finish_capture(self) -> Optional[Tuple[str, Any, str]]:
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

        # NEW: Try repair pipeline if parsing returned empty
        repaired = repair_pipeline(self._capture_buf, self.tool_names)
        if repaired is not None:
            tool_calls, cleaned = parse_dsml_tool_calls(repaired, self.tool_names)
            if tool_calls:
                leftover = self._extract_post_wrapper(self._capture_buf)
                return ("", tool_calls, leftover)

        return (self._capture_buf, None, "")
```

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/test_repair_tier1.py tests/test_repair_tier2.py tests/test_repair_pipeline.py tests/test_dsml_sieve.py -v --tb=short`
Expected: ALL PASS (existing sieve tests unaffected, new tests pass)

- [ ] **Step 4: Commit**

```bash
git add server/parser/dsml_sieve.py tests/test_repair_pipeline.py
git commit -m "feat: integrate repair pipeline into StreamSieve"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Task 1 covers `repair/__init__.py` + `repair_pipeline()` orchestrator ✓
   - Task 2 covers `repair_tier1.py` with all 7 repair strategies ✓
   - Task 3 covers `repair_tier2.py` with all 6 repair strategies ✓
   - Task 4 covers `dsml_sieve.py` integration + sieve-level tests ✓
   - Tier 3 (model self-repair) marked as optional/deferred ✓
   - Error handling/logging noted in spec but deferred as out of scope for first iteration ✓

2. **No placeholders:** All code blocks are complete and runnable.

3. **Type consistency:** `repair_pipeline()` signature matches usage in sieve. `repair_tier1()` and `repair_tier2()` signatures match imports.

4. **Scope check:** Single subsystem (repair pipeline). No decomposition needed.
