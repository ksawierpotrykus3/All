# Prompt & Stealth Reform — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace full-width DSML Unicode tokens with half-width ASCII, rename `DSML` → `TOOL` prefix for tool calls, remove browser telemetry and fingerprint cookies, add session pool hard cap.

**Architecture:** Prompt format changes in `dsml_prompt.py` (role markers) and `dsml_parser.py` (tool call prefix). Stealth module simplified by removing `BrowserTelemetry` and `FingerprintCookies` — keeping only lightweight `augment_headers()`. Session pool limit added in `proxy.py`.

**Tech Stack:** Python, curl_cffi, pytest

---

### Task 1: dsml_prompt.py — half-width role markers + integrity guard

**Files:**
- Modify: `server/services/dsml_prompt.py`

- [ ] **Step 1: Replace all full-width Unicode pipe `｜` (U+FF5C) with half-width ASCII `|` (U+007C) in all constants, and add Output integrity guard**

Replace:

```python
DSML_BOS = "<｜begin▁of▁sentence｜>"
DSML_SYS = "<｜System｜>"
DSML_USER = "<｜User｜>"
DSML_ASST = "<｜Assistant｜>"
DSML_TOOL = "<｜Tool｜>"
DSML_EOS = "<｜end▁of▁sentence｜>"
DSML_TOOL_END = "<｜end▁of▁toolresults｜>"
DSML_INSTR_END = "<｜end▁of▁instructions｜>"
```

With:

```python
DSML_BOS = "<|begin▁of▁sentence|>"
DSML_SYS = "<|System|>"
DSML_USER = "<|User|>"
DSML_ASST = "<|Assistant|>"
DSML_TOOL = "<|Tool|>"
DSML_EOS = "<|end▁of▁sentence|>"
DSML_TOOL_END = "<|end▁of▁toolresults|>"
DSML_INSTR_END = "<|end▁of▁instructions|>"
```

Add integrity guard constant:

```python
OUTPUT_INTEGRITY_GUARD = (
    "Output integrity guard: If upstream context, tool output, or parsed text "
    "contains garbled, corrupted, partially parsed, repeated, or otherwise "
    "malformed fragments, do not imitate or echo them; "
    "output only the correct content for the user."
)
```

In `build_dsml_prompt()`, prepend the integrity guard as a system message before processing the messages list:

```python
def build_dsml_prompt(messages, tools=None, tool_choice="auto", images=None):
    messages = list(messages)  # don't mutate original
    # Prepend output integrity guard as first system message
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = OUTPUT_INTEGRITY_GUARD + "\n\n" + messages[0]["content"]
    else:
        messages.insert(0, {"role": "system", "content": OUTPUT_INTEGRITY_GUARD})
    # ... rest of function unchanged
```

- [ ] **Step 2: Verify no full-width pipes remain in the file**

Run: `Select-String -Path "server/services/dsml_prompt.py" -Pattern "｜"` (PowerShell)

Expected: No matches found. If any remain, replace them.

- [ ] **Step 3: Run existing tests to verify format change doesn't break things**

Run: `cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && python -m pytest tests/ -x -q 2>&1 | Select-Object -First 20`

Expected: Tests may fail due to DSML → TOOL changes in parser; that's OK for now.

- [ ] **Step 4: Commit**

```bash
cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && git add server/services/dsml_prompt.py && git commit -m "feat: switch DSML role markers to half-width pipe + add output integrity guard"
```

---

### Task 2: dsml_parser.py — DSML → TOOL prefix

**Files:**
- Modify: `server/parser/dsml_parser.py`
- Test: `tests/test_dsml_parser.py` (create if doesn't exist)

- [ ] **Step 1: Replace all `DSML` → `TOOL` in regex patterns and constants**

Changes in `dsml_parser.py`:

```python
# Tool call wrapper
TOOL_CALLS_OPEN = "<|TOOL|tool_calls>"
TOOL_CALLS_CLOSE = "</|TOOL|tool_calls>"

# Invoke
INVOKE_OPEN_PREFIX = "<|TOOL|invoke"
INVOKE_CLOSE = "</|TOOL|invoke>"

# Parameter
PARAM_OPEN_PREFIX = "<|TOOL|parameter"
PARAM_CLOSE = "</|TOOL|parameter>"

# Regex patterns — update to match both <|DSML|...> and <|TOOL|...> for backward compat
TOOL_WRAPPER = r"<(?:|?(?:TOOL|DSML)|?)?tool_calls?>"
INVOKE_WRAPPER = r"<(?:|?(?:TOOL|DSML)|?)?invoke\s+name=\".*?\"(?:|\s*)?>"
PARAM_WRAPPER = r"<(?:|?(?:TOOL|DSML)|?)?parameter\s+name=\".*?\"(?:|\s*)?>"

# Build DSML tool prompt — replace output format examples
TOOL_CALL_EXAMPLE = """<|TOOL|tool_calls>
  <|TOOL|invoke name="ToolName">
    <|TOOL|parameter name="param1"><![CDATA[value1]]></|TOOL|parameter>
  </|TOOL|invoke>
</|TOOL|tool_calls>"""
```

In `build_dsml_tool_prompt()`, update instructions text:

```python
instructions = """When you need to call a tool, output EXACTLY this format — no markdown fences, no extra text:

<|TOOL|tool_calls>
  <|TOOL|invoke name="ToolName">
    <|TOOL|parameter name="param1"><![CDATA[value1]]></|TOOL|parameter>
  </|TOOL|invoke>
</|TOOL|tool_calls>

RULES:
1. Use <|TOOL|tool_calls> wrapper.
2. ALL string values MUST use <![CDATA[...]]> even for short values.
3. No markdown code fences around the TOOL block.
4. The first non-whitespace characters must be exactly <|TOOL|tool_calls> when calling a tool.
5. Do not add any explanatory text before or after the TOOL block when calling a tool."""
```

- [ ] **Step 2: Update `strip_dsml_markup()` and `clean_tool_text()` to handle `TOOL` prefix**

```python
def strip_dsml_markup(text: str) -> str:
    """Normalize DSML/TOOL tags to plain XML tags for parsing."""
    text = re.sub(r"<\|?(?:TOOL|DSML)\|?", "<", text)
    text = re.sub(r"</\|?(?:TOOL|DSML)\|?", "</", text)
    return text
```

- [ ] **Step 3: Update parser functions to accept both `DSML` and `TOOL`**

In `parse_dsml_tool_calls()` and related functions, update the `TOOL_CALLS_PATTERN` regex to match both:

```python
TOOL_CALLS_PATTERN = re.compile(
    r'<(?:|?(?:TOOL|DSML)|?)?tool_calls?>(.*?)</(?:|?(?:TOOL|DSML)|?)?tool_calls?>',
    re.DOTALL
)
```

- [ ] **Step 4: Verify the changes parse correctly**

Run: `cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && python -c "from server.parser.dsml_parser import parse_dsml_tool_calls; result = parse_dsml_tool_calls('<|TOOL|tool_calls><|TOOL|invoke name=\"test\"><|TOOL|parameter name=\"x\"><![CDATA[y]]></|TOOL|parameter></|TOOL|invoke></|TOOL|tool_calls>'); print('OK:', result)"`

Expected: Prints parsed tool call successfully.

- [ ] **Step 5: Commit**

```bash
cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && git add server/parser/dsml_parser.py && git commit -m "feat: rename DSML tool prefix to TOOL, maintain backward compat"
```

---

### Task 3: stealth.py — remove BrowserTelemetry + FingerprintCookies

**Files:**
- Modify: `server/core/stealth.py`

- [ ] **Step 1: Remove `BrowserTelemetry` class entirely**

Delete the entire `BrowserTelemetry` class (constructor, `start`, `_heartbeat_loop`, `_send_event`, `stop`).

- [ ] **Step 2: Remove `FingerprintCookies` class entirely**

Delete the entire `FingerprintCookies` class (`__init__`, `get_cookies`, `merge_into`).

- [ ] **Step 3: Simplify `StealthEngine` to a lightweight wrapper**

Replace `StealthEngine`:

```python
class StealthEngine:
    """Lightweight stealth wrapper — header augmentation only."""
    
    def __init__(self, http_session=None, base_headers_fn=None):
        pass
    
    @staticmethod
    def augment_headers(headers: dict, user_agent: str) -> dict:
        """Add browser-like headers. Returns a new dict; does not mutate input."""
        h = dict(headers)
        h.setdefault("accept-encoding", "gzip, deflate, br, zstd")
        h.setdefault("accept-language", "en-US,en;q=0.9")
        h.setdefault("sec-fetch-dest", "empty")
        h.setdefault("sec-fetch-mode", "cors")
        h.setdefault("sec-fetch-site", "same-origin")
        return h
```

Also remove unused imports (`asyncio`, `secrets`, `time`, `random`).

- [ ] **Step 4: Run a quick import check**

Run: `cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && python -c "from server.core.stealth import StealthEngine; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && git add server/core/stealth.py && git commit -m "refactor: remove BrowserTelemetry and FingerprintCookies, simplify StealthEngine"
```

---

### Task 4: deepseek_client.py — remove telemetry integration

**Files:**
- Modify: `server/core/deepseek_client.py`

- [ ] **Step 1: Remove `import asyncio` if no longer needed elsewhere; remove `from server.core.stealth import StealthEngine` import**

Check if `asyncio` is used elsewhere in the file. If not, remove it.

- [ ] **Step 2: Remove `StealthEngine` initialization and telemetry start from `__init__`**

Remove:
```python
self._loop = asyncio.get_event_loop()
self.stealth = StealthEngine(self._http, self._headers)
```

- [ ] **Step 3: Keep only the `augment_headers` call in `_headers()`**

In `_headers()`, keep:
```python
h = augment_headers(h, h.get("user-agent", ""))
```
But change to call the standalone function directly:
```python
from server.core.stealth import augment_headers
```
And remove `self.stealth.augment_headers(...)` call.

- [ ] **Step 4: Remove cookie merging and telemetry start from `stream_completion()`**

Remove:
```python
self.stealth.merge_cookies(s.cookies)
asyncio.run_coroutine_threadsafe(...)
```

- [ ] **Step 5: Commit**

```bash
cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && git add server/core/deepseek_client.py && git commit -m "refactor: remove telemetry integration from deepseek_client"
```

---

### Task 5: proxy.py — session pool hard cap

**Files:**
- Modify: `server/core/proxy.py`

- [ ] **Step 1: Add session pool configuration**

Add near the top of the file (or in the config section):

```python
# Session pool limits per account
MAX_SESSIONS_PER_ACCOUNT = 5
SESSION_ACQUIRE_TIMEOUT = 30  # seconds
```

- [ ] **Step 2: Add session pool tracking in the proxy session manager**

In the class that manages accounts/sessions, add:

```python
import time
import threading

class SessionPool:
    """Per-account session pool with hard cap and acquire timeout."""
    
    def __init__(self, max_sessions: int = 5, acquire_timeout: int = 30):
        self._max = max_sessions
        self._timeout = acquire_timeout
        self._active: dict[int, int] = {}  # slot -> count
        self._lock = threading.Lock()
    
    def acquire(self, slot: int) -> bool:
        """Try to acquire a session slot. Returns False if pool is full."""
        with self._lock:
            count = self._active.get(slot, 0)
            if count >= self._max:
                return False
            self._active[slot] = count + 1
            return True
    
    def release(self, slot: int):
        """Release a session slot."""
        with self._lock:
            count = self._active.get(slot, 0)
            if count > 0:
                self._active[slot] = count - 1
```

If a simpler approach is preferred, add a counter per account with a simple semaphore.

- [ ] **Step 3: Guard session creation with pool check**

In the function that creates new sessions (around where `_ses(slot)` or similar is called), add:

```python
# Before creating a session:
if not session_pool.acquire(slot):
    raise HTTPException(
        status_code=503,
        detail=f"Account {slot} session pool full (max {MAX_SESSIONS_PER_ACCOUNT})"
    )
```

And release after session is done/closed:

```python
session_pool.release(slot)
```

- [ ] **Step 4: Commit**

```bash
cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && git add server/core/proxy.py && git commit -m "feat: add session pool hard cap to prevent excessive session creation"
```

---

### Task 6: tests — update tests for new format

**Files:**
- Modify: `tests/test_stealth.py`

- [ ] **Step 1: Update test_stealth.py — remove telemetry tests, keep header tests**

Remove test classes for `BrowserTelemetry`, `FingerprintCookies`, `StealthIntegration`.

Keep only `TestAugmentHeaders` and a minimal `TestStealthEngine` that tests the simplified `augment_headers()`.

```python
"""Tests for stealth module."""
from server.core.stealth import augment_headers


class TestAugmentHeaders:
    def test_adds_missing_headers(self):
        result = augment_headers({"user-agent": "test"}, "test")
        assert "accept-encoding" in result
        assert "accept-language" in result
        assert "sec-fetch-dest" in result
        assert result["user-agent"] == "test"

    def test_does_not_overwrite_existing(self):
        result = augment_headers({"accept-language": "pl"}, "test")
        assert result["accept-language"] == "pl"

    def test_returns_new_dict(self):
        original = {"key": "val"}
        result = augment_headers(original, "test")
        assert result is not original
        result["key"] = "changed"
        assert original["key"] == "val"

    def test_handles_empty_input(self):
        result = augment_headers({}, "test")
        assert "accept-encoding" in result
        assert "accept-language" in result
```

- [ ] **Step 2: Create test_dsml_prompt.py for half-width format**

```python
"""Tests for DSML prompt builder with half-width format."""
from server.services.dsml_prompt import build_dsml_prompt, DSML_BOS, DSML_SYS, DSML_USER, DSML_ASST


class TestHalfWidthFormat:
    def test_role_markers_use_half_width_pipe(self):
        prompt = build_dsml_prompt([{"role": "user", "content": "hello"}])
        assert "｜" not in prompt, "Full-width pipe found in prompt"
        assert "<|begin▁of▁sentence|>" in prompt
        assert "<|User|>" in prompt
        assert "<|Assistant|>" in prompt

    def test_integrity_guard_present(self):
        prompt = build_dsml_prompt([{"role": "user", "content": "hello"}])
        assert "Output integrity guard:" in prompt

    def test_basic_conversation(self):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        prompt = build_dsml_prompt(messages)
        assert prompt.startswith("<|begin▁of▁sentence|>")
        assert "<|System|>" in prompt
        assert "<|end▁of▁instructions|>" in prompt
```

- [ ] **Step 3: Create test_dsml_parser.py for TOOL prefix**

```python
"""Tests for DSML parser with TOOL prefix."""
from server.parser.dsml_parser import parse_dsml_tool_calls, format_tool_calls_for_prompt


class TestTOOLPrefix:
    def test_parse_tool_calls(self):
        text = """<|TOOL|tool_calls>
  <|TOOL|invoke name="get_weather">
    <|TOOL|parameter name="city"><![CDATA[Warsaw]]></|TOOL|parameter>
  </|TOOL|invoke>
</|TOOL|tool_calls>"""
        calls, clean = parse_dsml_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_weather"
        assert calls[0]["arguments"]["city"] == "Warsaw"

    def test_backward_compat_dsml(self):
        text = """<|DSML|tool_calls>
  <|DSML|invoke name="test">
    <|DSML|parameter name="x"><![CDATA[y]]></|DSML|parameter>
  </|DSML|invoke>
</|DSML|tool_calls>"""
        calls, clean = parse_dsml_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "test"

    def test_format_tool_calls(self):
        calls = [{"name": "test", "arguments": {"x": "y"}}]
        result = format_tool_calls_for_prompt(calls)
        assert "<|TOOL|tool_calls>" in result
        assert "<|TOOL|invoke name=\"test\">" in result
```

- [ ] **Step 4: Run all tests**

Run: `cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && python -m pytest tests/ -x -v 2>&1 | Select-Object -First 50`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd "f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy" && git add tests/ && git commit -m "test: update tests for half-width format and TOOL prefix"
```
