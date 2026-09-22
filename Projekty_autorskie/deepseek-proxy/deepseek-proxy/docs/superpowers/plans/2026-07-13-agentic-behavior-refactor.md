# Agentic Behavior Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all 13 identified issues preventing the DeepSeek proxy from operating agentically, with zero technical debt.

**Architecture:** 12 sequential tasks across 7 modules, each independently testable. Starts with config consolidation (no behavior change), then prompt agentic instructions, stream integrity fixes, state cleanup, file deletion, and finally test coverage.

**Tech Stack:** Python 3.11+, FastAPI, asyncio, pytest

---

### Task 1: Consolidate Constants into Single Source of Truth

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\config.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\state_service.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\deepseek_client.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\proxy.py`
- Test: confirm no duplicate constant definitions

- [ ] **Step 1: Read config.py current state**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
cat -n server/config.py
```

- [ ] **Step 2: Add watermark and dedup constants to config.py**

Add at the end of `server/config.py`:

```python
import re

# Watermark pattern — single source of truth
WM_PATTERN = re.compile(r'<!--\s*PROXY_SID:\s*([a-f0-9\-]{12})\s*-->')

# Deduplication TTL (seconds)
DEDUP_TTL = 60.0

# Session pool
MAX_SESSIONS_PER_ACCOUNT = 5
```

- [ ] **Step 3: Update state_service.py to import from config**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\state_service.py`:
- Remove local `WM_PATTERN` regex definition
- Remove local `_DEDUP_TTL` constant
- Add `from server.config import WM_PATTERN, DEDUP_TTL`

Verify `WM_PATTERN` is identical (same regex), `DEDUP_TTL` is same value.

- [ ] **Step 4: Update deepseek_client.py to import from config**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\deepseek_client.py`:
- Remove local `MAX_ACCOUNTS` and `MAX_PARALLEL_TOOL_CALLS` if they duplicate config
- Import from config if needed

- [ ] **Step 5: Update proxy.py to import from config**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\proxy.py`:
- Remove local `_MAX_SESSIONS_PER_ACCOUNT` if duplicate
- Import from config: `from server.config import MAX_SESSIONS_PER_ACCOUNT`

- [ ] **Step 6: Verify no duplicate constants remain**

```bash
grep -n "WM_PATTERN\|DEDUP_TTL\|MAX_SESSIONS_PER_ACCOUNT\|MAX_ACCOUNTS\|MAX_PARALLEL_TOOL_CALLS" server/config.py server/services/state_service.py server/core/deepseek_client.py server/core/proxy.py
```

Expected: each constant defined exactly once in config.py, imported elsewhere.

- [ ] **Step 7: Commit**

```bash
git add server/config.py server/services/state_service.py server/core/deepseek_client.py server/core/proxy.py
git commit -m "refactor: consolidate constants into config.py as single source of truth"
```

---

### Task 2: Add Input Validation to Proxy Service

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\proxy.py`
- Test: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_proxy_validation.py` (create)

- [ ] **Step 1: Write failing tests for input validation**

Create `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_proxy_validation.py`:

```python
import pytest
from fastapi import HTTPException
from server.core.proxy import _validate_messages, _validate_tools, _validate_params


class TestValidateMessages:
    def test_empty_messages_raises(self):
        with pytest.raises(HTTPException) as exc:
            _validate_messages([])
        assert exc.value.status_code == 400

    def test_valid_messages_pass(self):
        _validate_messages([{"role": "user", "content": "hello"}])
        _validate_messages([{"role": "system", "content": "be helpful"}, {"role": "user", "content": "hi"}])

    def test_invalid_role_raises(self):
        with pytest.raises(HTTPException):
            _validate_messages([{"role": "invalid_role", "content": "x"}])

    def test_tool_role_allowed(self):
        _validate_messages([{"role": "user", "content": "x"}, {"role": "tool", "content": "result", "tool_call_id": "t1"}])


class TestValidateTools:
    def test_none_tools_pass(self):
        _validate_tools(None)
        _validate_tools([])

    def test_tool_without_name_raises(self):
        with pytest.raises(HTTPException):
            _validate_tools([{"function": {"name": ""}}])

    def test_duplicate_tool_names_raises(self):
        with pytest.raises(HTTPException):
            _validate_tools([
                {"function": {"name": "search"}},
                {"function": {"name": "search"}},
            ])

    def test_valid_tools_pass(self):
        _validate_tools([
            {"function": {"name": "search", "description": "search tool", "parameters": {"type": "object", "properties": {}}}},
            {"function": {"name": "read", "description": "read tool", "parameters": {"type": "object", "properties": {}}}},
        ])


class TestValidateParams:
    def test_temperature_below_zero_raises(self):
        with pytest.raises(HTTPException):
            _validate_params(temperature=-0.1, top_p=1.0, max_tokens=100)

    def test_temperature_above_2_raises(self):
        with pytest.raises(HTTPException):
            _validate_params(temperature=2.1, top_p=1.0, max_tokens=100)

    def test_top_p_out_of_range_raises(self):
        with pytest.raises(HTTPException):
            _validate_params(temperature=1.0, top_p=1.1, max_tokens=100)

    def test_max_tokens_below_1_raises(self):
        with pytest.raises(HTTPException):
            _validate_params(temperature=1.0, top_p=1.0, max_tokens=0)

    def test_valid_params_pass(self):
        _validate_params(temperature=0.7, top_p=0.9, max_tokens=4096)
        _validate_params(temperature=None, top_p=None, max_tokens=None)
```

```bash
mkdir -p tests
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_proxy_validation.py -v
```

Expected: ImportError — functions not defined yet.

- [ ] **Step 3: Add validation functions to proxy.py**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\proxy.py`, add after imports:

```python
from fastapi import HTTPException


def _validate_messages(messages: list[dict]) -> None:
    if not messages:
        raise HTTPException(400, "messages cannot be empty")
    for m in messages:
        role = m.get("role", "")
        if role not in ("system", "user", "assistant", "tool"):
            raise HTTPException(400, f"Invalid role: {role}")


def _validate_tools(tools: list[dict] | None) -> None:
    if not tools:
        return
    names = set()
    for t in tools:
        fn = t.get("function", t)
        name = fn.get("name", "")
        if not name:
            raise HTTPException(400, "Tool without name")
        if name in names:
            raise HTTPException(400, f"Duplicate tool name: {name}")
        names.add(name)


def _validate_params(temperature=None, top_p=None, max_tokens=None) -> None:
    if temperature is not None and not (0 <= temperature <= 2):
        raise HTTPException(400, "temperature must be in [0, 2]")
    if top_p is not None and not (0 <= top_p <= 1):
        raise HTTPException(400, "top_p must be in [0, 1]")
    if max_tokens is not None and max_tokens < 1:
        raise HTTPException(400, "max_tokens must be >= 1")
```

If `HTTPException` is already imported in proxy.py (via FastAPI), use the existing import.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_proxy_validation.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Wire validation into existing endpoint**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\proxy.py`, find the chat completion endpoint and add calls before prompt building:

```python
# In the chat handler, before building the prompt:
_validate_messages(body.get("messages", []))
_validate_tools(body.get("tools"))
_validate_params(
    temperature=body.get("temperature"),
    top_p=body.get("top_p"),
    max_tokens=body.get("max_tokens"),
)
```

- [ ] **Step 6: Verify existing tests still pass**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1 | head -80
```

Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
git add tests/test_proxy_validation.py server/core/proxy.py
git commit -m "feat: add input validation for messages, tools, and params"
```

---

### Task 3: Add Agentic Instruction and Tool Choice Enforcement

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\prompt_service.py`
- Test: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_prompt_agentic.py` (create)

- [ ] **Step 1: Write failing tests for agentic instruction**

Create `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_prompt_agentic.py`:

```python
import pytest
from server.services.prompt_service import _build_prompt_sync, _get_agentic_instruction


class TestAgenticInstruction:
    def test_agentic_instruction_present(self):
        """Verify that the agentic instruction block exists."""
        prompt = _get_agentic_instruction()
        assert "You are an AI agent" in prompt
        assert "follow ALL user instructions" in prompt
        assert "Do NOT skip" in prompt
        assert "explain why" in prompt

    def test_prompt_includes_agentic_block(self):
        """Verify _build_prompt_sync includes the instruction for any request."""
        messages = [{"role": "user", "content": "hello"}]
        prompt = _build_prompt_sync(messages)
        assert "You are an AI agent" in prompt

    def test_tool_choice_none_blocks_tools(self):
        """Verify tool_choice='none' adds block instruction."""
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="none")
        assert "Do NOT use any tools" in prompt
        assert "search" not in prompt  # tool definitions should not be included

    def test_tool_choice_auto_includes_tools(self):
        """Verify tool_choice='auto' includes tool definitions."""
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="auto")
        assert "Do NOT use any tools" not in prompt
        assert "search" in prompt

    def test_tool_choice_required_forces_tools(self):
        """Verify tool_choice='required' adds must-use instruction."""
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="required")
        assert "You MUST use one of the available tools" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_prompt_agentic.py -v
```

Expected: ImportError / AssertionError.

- [ ] **Step 3: Add agentic instruction and tool_choice logic to prompt_service.py**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\prompt_service.py`:

Add `_get_agentic_instruction()`:

```python
def _get_agentic_instruction() -> str:
    return (
        "\n\n## Agentic Behavior\n"
        "You are an AI agent. You MUST:\n"
        "1. Carefully read and follow ALL user instructions exactly as written.\n"
        "2. Use the available tools when needed to complete the user's request.\n"
        "3. If a user asks you to do something step by step, do exactly that.\n"
        "4. Do NOT skip, rephrase, or ignore any part of the user's message.\n"
        "5. If you cannot comply or don't understand, explain why."
    )
```

Modify `_build_prompt_sync` to:
1. Append `_get_agentic_instruction()` to `combined_system`
2. When `tool_choice == "none"` and tools are provided, omit tool definitions and add block instruction
3. When `tool_choice == "required"`, append enforcement line to tool_block

The updated `_build_prompt_sync` signature:
```python
def _build_prompt_sync(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
) -> str:
```

Key logic changes:
```python
# After building combined_system, append agentic instruction
combined_system += _get_agentic_instruction()

# Tool choice enforcement
if tool_choice == "none":
    tool_block = ""  # no tool definitions sent
    combined_system += "\n\nDo NOT use any tools. Respond directly."
elif tools:
    if tool_choice == "required":
        tool_block = _format_tool_block(tools)
        tool_block += "\n\nYou MUST use one of the available tools to complete the user's request."
    elif tool_choice == "auto" or tool_choice is None:
        tool_block = _format_tool_block(tools)
    elif isinstance(tool_choice, dict):
        # filter to specific tool
        name = tool_choice.get("function", {}).get("name", "")
        filtered = [t for t in tools if t.get("function", t).get("name") == name]
        tool_block = _format_tool_block(filtered) if filtered else ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_prompt_agentic.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services/prompt_service.py tests/test_prompt_agentic.py
git commit -m "feat: add agentic instruction and tool_choice enforcement to prompt builder"
```

---

### Task 4: Add Tool Result Attribution

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\prompt_service.py`
- Modify (if needed for context): reference tool result formatting in the existing codebase

- [ ] **Step 1: Find current tool result formatting in prompt_service.py**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
grep -n "Tool:" server/services/prompt_service.py
```

- [ ] **Step 2: Change tool result format**

Find the section that formats tool role messages. Change from:
```python
f"[Tool: {tool_call_id}]\n{content}"
```

To:
```python
tool_name = msg.get("name", "")
if tool_name:
    f"[Tool Result: {tool_name} (call_id: {tool_call_id})]\n{content}"
else:
    f"[Tool Result (call_id: {tool_call_id})]\n{content}"
```

- [ ] **Step 3: Verify existing tests still pass**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1 | head -50
```

- [ ] **Step 4: Commit**

```bash
git add server/services/prompt_service.py
git commit -m "fix: add tool name to tool result attribution in prompt"
```

---

### Task 5: Adjust Context Trimming Limits

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\prompt_service.py`

- [ ] **Step 1: Read current trimming logic**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
grep -n -A5 "MAX_PROMPT_LEN\|truncat\|len(rest)\|dropping" server/services/prompt_service.py
```

- [ ] **Step 2: Change message history limit from 20 to 40**

Find the line that keeps only the last N non-system messages. Change:
```python
if len(rest) > 20:
    rest = rest[-20:]
```
To:
```python
if len(rest) > 40:
    rest = rest[-40:]
```

- [ ] **Step 3: Change tool result truncation from 8000 to 50000**

Find the line that truncates tool content. Change:
```python
if len(content) > 8000:
    ...
```
To:
```python
if len(content) > 50000:
    rest[i]["content"] = content[:50000] + "...[truncated]"
```

- [ ] **Step 4: Add last-resort 150k char protection (if not already present)**

If there's no MAX_PROMPT_LEN check already, add one:
```python
MAX_PROMPT_LEN = 150_000
# ... after building prompt string ...
if len(prompt_str) > MAX_PROMPT_LEN:
    # Keep system parts, last user message, and last 15 messages total
    system_parts = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    if non_system:
        # Keep last user message + last 14 before it
        non_system = non_system[-(15):]
    messages = system_parts + non_system
    prompt_str = _build_prompt_sync(messages, tools, tool_choice)
```

- [ ] **Step 5: Verify existing tests still pass**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1 | head -50
```

- [ ] **Step 6: Commit**

```bash
git add server/services/prompt_service.py
git commit -m "fix: increase context limits from 20 to 40 messages, 8k to 50k chars for tool results"
```

---

### Task 6: Fix Stream Text Loss Before Tool Calls

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`
- Test: create or extend test file

- [ ] **Step 1: Write failing test for text loss**

Extend `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_stream_service_flow.py`:

```python
class TestTextLossBeforeToolCalls:
    def test_short_text_before_tool_calls_is_not_lost(self):
        """Verify text shorter than 50 chars before tool_calls is yielded."""
        from server.services.stream_service import StreamSieve
        
        sieve = StreamSieve(tools=[{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}])
        
        # Simulate: short text followed by tool_call
        chunks = []
        for event_type, data, text in [
            ("text", "", "Hello"),
            ("done", {}, ""),
        ]:
            for chunk in sieve.process(event_type, data, text):
                chunks.append(chunk)
        
        # Check that "Hello" appears in yielded chunks
        yielded_text = "".join(c.get("content", "") for c in chunks)
        assert "Hello" in yielded_text, f"Short text 'Hello' was lost! Got: {repr(yielded_text)}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_stream_service_flow.py::TestTextLossBeforeToolCalls -v
```

Expected: FAIL — text is lost because yield_buffer only flushes at >=50 chars.

- [ ] **Step 3: Fix text loss in StreamSieve**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`, in the stream sieve processing logic:

Find where `yield_buffer` is flushed (condition `len(text_buffer) >= 50`). Add an additional flush trigger:

```python
# Before processing tool_calls, flush any pending buffer
if yield_buffer and (event_type == "tool_calls" or (event_type == "text" and text)):
    yield _chunk({"content": yield_buffer})
    yield_buffer = ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_stream_service_flow.py::TestTextLossBeforeToolCalls -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services/stream_service.py tests/test_stream_service_flow.py
git commit -m "fix: flush yield_buffer immediately before tool_calls to prevent text loss"
```

---

### Task 7: Add Drain Timeout and Tool Call Name Validation

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`
- Test: add to `tests/test_stream_service_flow.py`

- [ ] **Step 1: Write failing test for tool call validation**

```python
class TestToolCallValidation:
    def test_unknown_tool_name_is_filtered(self):
        """Verify unknown tool names are filtered out."""
        from server.services.stream_service import StreamSieve
        
        sieve = StreamSieve(tools=[{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}])
        
        # Simulate a tool_call with unknown name
        found = sieve._validate_tool_calls([{"name": "unknown_tool", "arguments": "{}"}])
        assert len(found) == 0, f"Unknown tool should be filtered, got: {found}"
    
    def test_known_tool_name_passes(self):
        """Verify known tool names pass through."""
        from server.services.stream_service import StreamSieve
        
        sieve = StreamSieve(tools=[{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}])
        
        found = sieve._validate_tool_calls([{"name": "search", "arguments": "{}"}])
        assert len(found) == 1
        assert found[0]["name"] == "search"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_stream_service_flow.py::TestToolCallValidation -v
```

Expected: AttributeError — `_validate_tool_calls` doesn't exist.

- [ ] **Step 3: Add drain timeout and tool call validation**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`:

```python
import time

_DRAIN_TIMEOUT = 30.0

class StreamSieve:
    # ... existing code ...
    
    def _validate_tool_calls(self, found_calls: list[dict]) -> list[dict]:
        """Filter out tool calls for tools that don't exist."""
        if not self.tools or not found_calls:
            return found_calls
        
        valid_tool_names = {t.get("function", t).get("name", "") for t in self.tools}
        valid = [tc for tc in found_calls if tc.get("name", "") in valid_tool_names or "function" in tc]
        
        filtered_count = len(found_calls) - len(valid)
        if filtered_count > 0:
            print(f"[TOOL_VALIDATION] Filtered {filtered_count} unknown tool call(s)", flush=True)
        
        return valid
```

In the stream drain loop, add timeout guard:
```python
_drain_start = time.time()
for remaining_chunk in stream_gen:
    if time.time() - _drain_start > _DRAIN_TIMEOUT:
        print(f"[DRAIN TIMEOUT] exceeded {_DRAIN_TIMEOUT}s", flush=True)
        break
    # ... existing processing ...
```

Wire the validation where tool_calls are discovered:
```python
# After finding tool_calls, before yielding:
found_calls = self._validate_tool_calls(found_calls)
if not found_calls:
    continue  # skip invalid tool calls
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/test_stream_service_flow.py::TestToolCallValidation -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/services/stream_service.py tests/test_stream_service_flow.py
git commit -m "feat: add drain timeout and tool call name validation in stream service"
```

---

### Task 8: Refactor Watermark from Content to Finish Reason

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\state_service.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\proxy.py`

- [ ] **Step 1: Read current watermark code**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
grep -rn "PROXY_SID\|watermark\|_extract_watermark" server/
```

- [ ] **Step 2: Change watermark emission in stream_service.py**

Find where `chunk({"content": f"\n<!-- PROXY_SID:{conv_uuid} -->"})` is yielded.

Change the `_chunk` helper (or the yield call) to accept an optional `sid` parameter:

```python
def _chunk(
    delta: dict | None = None,
    finish_reason: str | None = None,
    sid: str | None = None,
) -> str:
    chunk_dict = {}
    if delta:
        chunk_dict["choices"] = [{"delta": delta}]
    if finish_reason:
        chunk_dict["choices"][0]["finish_reason"] = finish_reason
    if sid:
        chunk_dict["sid"] = sid  # Custom field for session tracking
    return f"data: {json.dumps(chunk_dict)}\n\n"
```

Update the watermark yield from:
```python
yield _chunk({"content": f"\n\n<!-- PROXY_SID:{conv_uuid} -->"})
```
To:
```python
yield _chunk({"content": response_text}, fr="stop", sid=conv_uuid)
```

- [ ] **Step 3: Update state_service.py to parse new watermark format**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\state_service.py`, update `_extract_watermark` to handle both the old format (content-based) and new format (sid field):

```python
def _extract_watermark(chunk: dict) -> str | None:
    """Extract PROXY_SID from chunk metadata (new) or fallback to content regex (old)."""
    # New format: sid in chunk metadata
    sid = chunk.get("sid")
    if sid:
        return sid
    
    # Legacy format: look in content
    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
    match = WM_PATTERN.search(content)
    return match.group(1) if match else None
```

- [ ] **Step 4: Verify existing tests still pass**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1 | head -50
```

- [ ] **Step 5: Commit**

```bash
git add server/services/stream_service.py server/services/state_service.py server/core/proxy.py
git commit -m "refactor: move watermark from response content to chunk metadata field 'sid'"
```

---

### Task 9: Unify parent_message_id and Bump JPEG Quality

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\deepseek_client.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\utils\helpers.py`

- [ ] **Step 1: Find parent_message_id type usages**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
grep -rn "parent_message_id\|parent_msg_id" server/
```

- [ ] **Step 2: Unify to int | None**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\core\deepseek_client.py`, wherever `parent_message_id` is assigned from API response, cast to `int`:

```python
# Before:
parent_message_id = response.get("parent_message_id")

# After:
raw = response.get("parent_message_id")
parent_message_id = int(raw) if raw is not None else None
```

Update type hints in affected function signatures from `int | str | None` to `int | None`.

- [ ] **Step 3: Bump JPEG quality in helpers.py**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\utils\helpers.py`:

```python
# Before:
image.save(buf, format="JPEG", quality=75)

# After:
image.save(buf, format="JPEG", quality=90)
```

- [ ] **Step 4: Verify existing tests still pass**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1 | head -50
```

- [ ] **Step 5: Commit**

```bash
git add server/core/deepseek_client.py server/utils/helpers.py
git commit -m "refactor: unify parent_message_id to int|None, bump JPEG quality to 90"
```

---

### Task 10: Async State Saving and File Cleanup

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\state_service.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\dsml_prompt.py`
- Delete: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\_server_legacy.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\__init__.py`

- [ ] **Step 1: Make state saving async in stream_service.py**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\stream_service.py`:

Replace `_save_conv_state_sync()` with async version. In generator code, use:

```python
import asyncio

# In the generator function:
async def _save_state_async(state_service, conv_uuid, messages):
    await state_service.save_conv_state(conv_uuid, messages)

# Usage in generator:
# Since we're in a sync generator, dispatch to executor:
loop = asyncio.get_event_loop()
loop.run_in_executor(None, state_service.save_conv_state_sync, conv_uuid, messages)
```

Add `save_conv_state_sync` to `state_service.py` if it doesn't already exist:
```python
def save_conv_state_sync(self, conv_uuid: str, messages: list) -> None:
    """Synchronous version for use in generators."""
    # ... existing save logic ...
```

- [ ] **Step 2: Add deprecation warning to dsml_prompt.py**

Add at the top of `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\services\dsml_prompt.py`:

```python
import warnings
warnings.warn(
    "dsml_prompt.py is DEPRECATED. Use prompt_service.py instead. "
    "This module is kept for reference only and will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

# Original code continues below...
```

- [ ] **Step 3: Delete _server_legacy.py**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
git rm _server_legacy.py
```

- [ ] **Step 4: Update server/__init__.py**

Read current `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\__init__.py`. Simplify to:

```python
from server.main import app

__all__ = ["app"]
```

- [ ] **Step 5: Verify imports still work**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -c "from server.main import app; print('OK')"
python -c "from server import app; print('OK')"
```

Expected: both print "OK".

- [ ] **Step 6: Run full test suite**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1 | tail -30
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add server/services/stream_service.py server/services/state_service.py server/services/dsml_prompt.py server/__init__.py
git add -A  # captures the deletion
git commit -m "refactor: async state saving, deprecate dsml_prompt.py, delete _server_legacy.py, simplify __init__"
```

---

### Task 11: Add Global Error Handler Middleware

**Files:**
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\main.py`

- [ ] **Step 1: Read current main.py**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
cat -n server/main.py
```

- [ ] **Step 2: Add error handler**

In `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server\main.py`, after the `app = FastAPI()` line:

```python
from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    print(f"[UNHANDLED] {type(exc).__name__}: {exc}", flush=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
            }
        }
    )
```

- [ ] **Step 3: Verify server starts**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
timeout 5 python -m server.main || true
```

Expected: Server starts without errors (may fail on port conflict, that's fine — no traceback).

- [ ] **Step 4: Commit**

```bash
git add server/main.py
git commit -m "feat: add global error handler middleware for unhandled exceptions"
```

---

### Task 12: Add Agent Integration Tests

**Files:**
- Create: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_agent_integration.py`
- Modify: `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_stream_service_flow.py`

- [ ] **Step 1: Write comprehensive agent integration tests**

Create `f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\tests\test_agent_integration.py`:

```python
"""Integration tests for agentic behavior of the DeepSeek proxy prompt builder."""

import pytest
from server.services.prompt_service import _build_prompt_sync


class TestMultiStepInstructions:
    def test_all_steps_preserved_in_prompt(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Step 1: Find file X. Step 2: Read it. Step 3: Summarize."},
        ]
        tools = [
            {"function": {"name": "search_files", "description": "Search files", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
            {"function": {"name": "read_file", "description": "Read file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        ]
        
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="auto")
        
        # All steps must be present in prompt
        assert "Step 1" in prompt
        assert "Step 2" in prompt
        assert "Step 3" in prompt
        # Agentic instruction must be present
        assert "You are an AI agent" in prompt
        # Tool definitions must be present
        assert "search_files" in prompt
        assert "read_file" in prompt

    def test_tool_choice_none_no_tools_in_prompt(self):
        messages = [{"role": "user", "content": "Tell me a joke."}]
        tools = [
            {"function": {"name": "search_files", "parameters": {"type": "object", "properties": {}}}},
        ]
        
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="none")
        
        # Tools should not be defined in prompt
        assert "search_files" not in prompt
        # Block instruction must be present
        assert "Do NOT use any tools" in prompt

    def test_context_preserved_after_truncation(self):
        """System and last user message survive truncation."""
        messages = [{"role": "system", "content": "You are a coding agent."}]
        for i in range(50):
            messages.append({"role": "user", "content": f"Message {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})
        
        prompt = _build_prompt_sync(messages)
        
        # System message must be present
        assert "You are a coding agent" in prompt
        # Last user message must be present
        assert "Message 49" in prompt
        # Earliest user messages may be truncated
        # (not asserting on truncation since it depends on exact limits)
        assert "Message 0" not in prompt  # should be truncated


class TestAgenticInstruction:
    def test_instruction_count_rules(self):
        instruction = _get_agentic_instruction()
        assert instruction.count("MUST") == 2  # "You are an AI agent. You MUST:" + rule items
        assert "follow ALL user instructions" in instruction
        assert "Do NOT skip" in instruction
        assert "explain why" in instruction

    def test_injected_only_once(self):
        messages = [{"role": "user", "content": "hello"}]
        prompt = _build_prompt_sync(messages)
        # Instruction should appear exactly once
        assert prompt.count("You are an AI agent") == 1


class TestToolChoiceMapping:
    @pytest.mark.parametrize("tool_choice", ["auto", None])
    def test_auto_or_none_includes_tools(self, tool_choice):
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice=tool_choice)
        assert "search" in prompt
        assert "Do NOT use any tools" not in prompt

    def test_required_forces_tool_use(self):
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="required")
        assert "MUST use one of the available tools" in prompt

    def test_none_blocks_tools(self):
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]
        prompt = _build_prompt_sync(messages, tools=tools, tool_choice="none")
        assert "Do NOT use any tools" in prompt
        assert "search" not in prompt
```

- [ ] **Step 2: Add watermark regression test to test_stream_service_flow.py**

```python
class TestWatermarkRegression:
    def test_watermark_not_in_content(self):
        """Verify watermark no longer appears in response content."""
        from server.services.stream_service import _chunk
        
        chunk = _chunk({"content": "Hello"}, fr="stop", sid="test-uuid-123")
        assert "<!-- PROXY_SID:" not in chunk
        assert '"sid"' in chunk
        assert "test-uuid-123" in chunk
```

- [ ] **Step 3: Run all tests**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1
```

Expected: All tests pass, including new agent integration tests.

- [ ] **Step 4: Commit**

```bash
git add tests/test_agent_integration.py tests/test_stream_service_flow.py
git commit -m "test: add agent integration tests and watermark regression tests"
```

---

### Task 13: Full Verification and Smoke Test

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -m pytest tests/ -v --timeout=30 2>&1
```

Expected: All tests PASS. Note any failures and fix before proceeding.

- [ ] **Step 2: Verify server starts and responds**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
timeout 10 python -m server.main &
sleep 3
# Health check
curl -s http://localhost:8080/health 2>/dev/null || curl -s http://localhost:8000/health 2>/dev/null || echo "Health endpoint check (adjust port as needed)"
```

- [ ] **Step 3: Manual smoke test — send a chat request**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Say hello in exactly 3 words."}],
    "stream": false,
    "max_tokens": 50
  }' | python -m json.tool 2>&1 | head -20
```

Expected: Valid JSON response with model output (3 words).

- [ ] **Step 4: Verify no deprecation warnings in production use**

```bash
cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy
python -W all -c "from server.main import app; print('No warnings')"
```

Expected: "No warnings" — `dsml_prompt.py` deprecation warning should not fire since it's not imported.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: verification fixes from full test suite"
```

- [ ] **Step 6: Mark plan complete**

All 13 tasks implemented. Success criteria from spec:
1. ✅ Model follows multi-step instructions (tested in test_agent_integration)
2. ✅ Model respects tool_choice="none" (tested in test_prompt_agentic)
3. ✅ No text loss before tool_calls (tested in test_stream_service_flow)
4. ✅ Unknown tool names rejected (tested in test_stream_service_flow)
5. ✅ Watermark in chunk metadata (tested in test_stream_service_flow)
6. ✅ Constants in one place (config.py)
7. ✅ _server_legacy.py removed, dsml_prompt.py deprecated
8. ✅ All tests pass
