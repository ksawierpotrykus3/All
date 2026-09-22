# CO-STAR Prompt & Clean Response Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace suspicious DSML tokens with natural CO-STAR XML tags in prompts sent to DeepSeek, and remove watermark/suspicious IDs from responses returned to clients.

**Architecture:** Three-phase migration: (1) add new CO-STAR prompt builder and JSON tool call parser alongside existing DSML code, (2) make CO-STAR the default, (3) optionally remove DSML code. StreamSieve detects both formats during transition.

**Tech Stack:** Python 3.12+, FastAPI, regex, JSON parsing

---

### Task 1: Config — add PROMPT_FORMAT flag

**Files:**
- Modify: `server/config.py`

- [ ] **Step 1: Add PROMPT_FORMAT and WATERMARK_ENABLED settings**

```python
# --- Format Selection ---
# "costar" = CO-STAR XML tags (natural, no DSML tokens)
# "dsml" = legacy DSML format (Fly143 tokens)
PROMPT_FORMAT = "costar"

# --- Watermark ---
# When False, SID is NOT embedded in response content (only in SSE metadata)
WATERMARK_ENABLED = False
WATERMARK_MARKER = "<!-- PROXY_SID:"
```

Add these after line 21 (`_NEW_SESSION_MSG_LIMIT = 25`) and before `# --- Tool Call Patterns ---`.

- [ ] **Step 2: Run a quick Python syntax check**

Run: `python -c "import server.config; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

---

### Task 2: dsml_parser.py — add JSON tool call parser

**Files:**
- Modify: `server/parser/dsml_parser.py`

- [ ] **Step 1: Add JSON_TOOL_CALL_PATTERN and parse_json_tool_calls()**

After line 31 (`PARAM_PATTERN = ...`), add:

```python
# ─── JSON tool call format (CO-STAR mode) ────────────────────
JSON_TOOL_CALL_PATTERN = re.compile(
    r'```tool_call\s*\n(.*?)```',
    re.DOTALL
)
```

After the `format_tool_calls_for_prompt()` function (before `_format_params_dsml`), add:

```python
def parse_json_tool_calls(text: str, tool_names: list[str] | None = None) -> tuple[list[dict], str]:
    """Parse ```tool_call JSON blocks from model output.

    Returns (tool_calls, cleaned_text) where cleaned_text has the
    code blocks removed. Also handles ```json blocks as fallback.
    """
    if not text:
        return [], text

    tool_names = tool_names or []
    cleaned = text
    tool_calls: list[dict] = []

    # Try ```tool_call first, then fallback to ```json
    for pattern in [JSON_TOOL_CALL_PATTERN, re.compile(r'```json\s*\n(.*?)```', re.DOTALL)]:
        for match in pattern.finditer(text):
            block = match.group(1).strip()
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue

            # Support both {"name": ..., "arguments": ...} and {"tool": ..., "arguments": ...}
            name = parsed.get("name") or parsed.get("tool", "")
            if not name:
                continue

            args_raw = parsed.get("arguments", {})
            if isinstance(args_raw, str):
                try:
                    args_raw = json.loads(args_raw)
                except json.JSONDecodeError:
                    args_raw = {"value": args_raw}

            tool_calls.append({
                "name": name,
                "arguments": json.dumps(args_raw, ensure_ascii=False),
            })

        # If we found tool calls in this pattern, don't double-parse
        if tool_calls:
            break

    # Remove all ```tool_call and ```json blocks from text
    cleaned = re.sub(
        r'```(?:tool_call|json)\s*\n.*?```',
        '',
        cleaned,
        flags=re.DOTALL,
    ).strip()
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return tool_calls, cleaned


def build_costar_tool_prompt(tools: list[dict]) -> str:
    """Build <tools> section using JSON schema format."""
    if not tools:
        return ""
    return f"<tools>\n{json.dumps(tools, indent=2, ensure_ascii=False)}\n</tools>"
```

- [ ] **Step 2: Run test to verify JSON parsing works**

Run: `python -c "
from server.parser.dsml_parser import parse_json_tool_calls
# Test basic
tc, cleaned = parse_json_tool_calls('Hello \`\`\`tool_call\n{\"name\":\"get_weather\",\"arguments\":{\"loc\":\"Warsaw\"}}\n\`\`\` world')
assert len(tc) == 1, f'Expected 1 tool call, got {len(tc)}'
assert tc[0]['name'] == 'get_weather'
assert 'Hello' in cleaned and 'world' in cleaned, 'Cleaned text lost content'
print(f'OK: {len(tc)} tool call(s), cleaned={repr(cleaned[:50])}')
# Test multiple
tc2, _ = parse_json_tool_calls('\`\`\`tool_call\n{\"name\":\"a\",\"arguments\":{}}\n\`\`\`\n\`\`\`tool_call\n{\"name\":\"b\",\"arguments\":{}}\n\`\`\`')
assert len(tc2) == 2, f'Expected 2, got {len(tc2)}'
print(f'OK: multiple calls: {len(tc2)}')
# Test malformed
tc3, _ = parse_json_tool_calls('some text \`\`\`tool_call\nnot json\n\`\`\` more text')
assert len(tc3) == 0, f'Expected 0 for malformed, got {len(tc3)}'
print('OK: malformed JSON ignored')
"
`

- [ ] **Step 3: Add clean_tool_call_markers() helper for stream cleaning**

After `sanitize_leaked_output()` (before `build_dsml_tool_prompt()`), add:

```python
def clean_tool_call_markers(text: str) -> str:
    """Remove partial ```tool_call markers from stream text fragments.

    In streaming mode, the model may emit partial markers like
    `` ```too `` before the full marker is detected. This removes
    any partial markers from text chunks.
    """
    if not text:
        return ""
    # Remove ```tool_call, ```json, and partial markers
    text = re.sub(r'```(?:tool_call|json)\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    return text.strip()
```

- [ ] **Step 4: Commit**

---

### Task 3: dsml_sieve.py — add JSON tool call detection

**Files:**
- Modify: `server/parser/dsml_sieve.py`

- [ ] **Step 1: Add JSON tool call markers and detection logic**

After line 36 (TOOL_STARTS list), add:

```python
# JSON format markers (CO-STAR mode)
JSON_TOOL_START = "```tool_call"
JSON_TOOL_END = "```"
```

In `StreamSieve.__init__()`, add attribute:

```python
self._json_capturing = False
self._json_capture_buf = ""
```

In `StreamSieve.feed()`, add JSON detection before DSML detection. After `self._pending += chunk`, add:

```python
# JSON tool call detection (CO-STAR mode)
if not self._capturing:
    if self._json_capturing:
        self._json_capture_buf += chunk
        if JSON_TOOL_END in self._json_capture_buf and len(self._json_capture_buf) > len(JSON_TOOL_START):
            # Complete JSON block found
            from server.parser.dsml_parser import parse_json_tool_calls
            jtc, _ = parse_json_tool_calls(self._json_capture_buf)
            if jtc:
                events.append(SieveEvent("tool_calls", jtc))
            self._json_capturing = False
            self._json_capture_buf = ""
        return events

    # Check for JSON tool call start
    js_pos = self._pending.find(JSON_TOOL_START)
    if js_pos >= 0:
        prefix = self._pending[:js_pos]
        if prefix:
            events.append(SieveEvent("text", prefix))
        self._json_capturing = True
        self._json_capture_buf = self._pending[js_pos:]
        self._pending = ""
        return events
```

In `StreamSieve.flush()`, add JSON cleanup:

```python
if self._json_capturing and self._json_capture_buf:
    from server.parser.dsml_parser import parse_json_tool_calls, clean_tool_call_markers
    jtc, cleaned = parse_json_tool_calls(self._json_capture_buf)
    if jtc:
        events.append(SieveEvent("tool_calls", jtc))
    elif cleaned:
        events.append(SieveEvent("text", clean_tool_call_markers(cleaned)))
    self._json_capturing = False
    self._json_capture_buf = ""
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `python -c "
from server.parser.dsml_sieve import StreamSieve
s = StreamSieve()
events = s.feed('Hello')
assert len(events) == 0 or events[0].type == 'text'
print('OK: basic text stream')
"`

- [ ] **Step 3: Commit**

---

### Task 4: dsml_prompt.py — add CO-STAR prompt builder

**Files:**
- Modify: `server/services/dsml_prompt.py`

- [ ] **Step 1: Add CO-STAR prompt builder function**

After `_format_stealth()` (before `build_dsml_prompt()`), add:

```python
COSTAR_TOOL_CALLING_RULES = """<rules>
When you need to call a tool, output a JSON code block with this exact format:

```tool_call
{
  "name": "ToolName",
  "arguments": {
    "param1": "value1"
  }
}
```

RULES:
1. Use ```tool_call code fences — this is required and non-negotiable.
2. The "name" field must match a tool name from the <tools> section exactly.
3. "arguments" must be a valid JSON object with the required parameters.
4. Output ONLY the code block when calling a tool — no explanatory text before or after.
5. You may call multiple tools by outputting multiple ```tool_call blocks in sequence.
6. If you have text to say, say it first, then output the tool call block.
</rules>"""


def _build_costar(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
) -> str:
    """Build prompt using CO-STAR XML tag format (no DSML tokens).

    Uses natural XML tags: <system>, <chat_history>, <user>,
    <assistant>, <tool_result>, <user_input>, <tools>, <rules>.
    """
    messages = list(messages)

    # ── Build tool_call_id -> function name mapping ──────────────
    tc_id_to_name: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tc_id = tc.get("id", "")
                if tc_id:
                    fn = tc.get("function", {})
                    name = tc.get("name") or fn.get("name", "")
                    tc_id_to_name[tc_id] = name

    # ── Extract system content ───────────────────────────────────
    system_content = ""
    non_system_msgs: list[dict] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_content = str(msg.get("content", "")) if msg.get("content") else ""
        else:
            non_system_msgs.append(msg)

    parts: list[str] = []

    # System block
    if system_content.strip():
        parts.append(f"<system>\n{system_content.strip()}\n</system>")

    # Tool definitions
    if tools:
        from server.parser.dsml_parser import build_costar_tool_prompt
        tool_section = build_costar_tool_prompt(tools)
        if tool_section:
            parts.append(tool_section)
        if tool_choice:
            parts.append(f"<tool_choice>\n{tool_choice}\n</tool_choice>")

    # Chat history (all messages except the last user message)
    history_msgs = list(non_system_msgs)
    last_is_user = history_msgs and history_msgs[-1].get("role") == "user"
    if last_is_user:
        last_user = history_msgs.pop()
    else:
        last_user = None

    if history_msgs:
        history_parts: list[str] = []
        for msg in history_msgs:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = "\n".join(texts)
            content_str = str(content) if content else ""

            if role == "user":
                history_parts.append(f"<user>\n{content_str}\n</user>")
            elif role == "assistant":
                segs = []
                if content_str.strip():
                    segs.append(content_str.strip())
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    tc_json = json.dumps([
                        {
                            "name": tc.get("function", tc).get("name", tc.get("name", "")),
                            "arguments": tc.get("function", tc).get("arguments", "{}"),
                        }
                        for tc in tool_calls
                    ], indent=2, ensure_ascii=False)
                    segs.append(f"```tool_call\n{tc_json}\n```")
                if segs:
                    history_parts.append(f"<assistant>\n{'\n\n'.join(segs)}\n</assistant>")
            elif role == "tool":
                tool_content = str(content) if content else ""
                if len(tool_content) > 500:
                    tool_content = tool_content[:500] + "...(truncated)"
                tc_id = msg.get("tool_call_id", "")
                tool_name = tc_id_to_name.get(tc_id, "unknown")
                history_parts.append(f"<tool_result name=\"{tool_name}\">\n{tool_content}\n</tool_result>")

        if history_parts:
            parts.append("<chat_history>\n" + "\n\n".join(history_parts) + "\n</chat_history>")

    # Current user input
    if last_user is not None:
        content = last_user.get("content", "")
        if isinstance(content, list):
            texts = [
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            content = "\n".join(texts)
        parts.append(f"<user_input>\n{str(content)}\n</user_input>")

    # Tool calling rules
    if tools:
        parts.append(COSTAR_TOOL_CALLING_RULES)

    # Final assembly
    prompt = "\n\n".join(parts)

    # Cap at MAX_PROMPT_LEN
    from server.config import MAX_PROMPT_LEN
    if len(prompt) > MAX_PROMPT_LEN:
        prompt = prompt[:MAX_PROMPT_LEN]

    return prompt
```

- [ ] **Step 2: Update `build_dsml_prompt()` to support costar mode**

Modify `build_dsml_prompt()` to accept and respect a prompt format flag. Change the function signature and add an early dispatch:

```python
def build_dsml_prompt(
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    tool_choice: Optional[str] = None,
    images: Optional[List[str]] = None,
    max_history_len: Optional[int] = None,
    stealth: bool = True,
    prompt_format: str = "costar",  # NEW: "costar" or "dsml"
) -> str:
    """Build prompt for DeepSeek V4 Pro.

    When *prompt_format* is "costar", uses CO-STAR XML tags (no DSML tokens).
    When *prompt_format* is "dsml", uses Fly143 DSML token format.
    """
    # NEW: CO-STAR dispatch
    if prompt_format == "costar":
        return _build_costar(messages, tools=tools, tool_choice=tool_choice)

    # Existing DSML logic below...
    messages = list(messages)
    # ... (rest of existing function unchanged)
```

- [ ] **Step 3: Run sanity check**

Run: `python -c "
from server.services.dsml_prompt import build_dsml_prompt
# Test CO-STAR mode
prompt = build_dsml_prompt(
    [{'role': 'system', 'content': 'You are a helpful assistant.'},
     {'role': 'user', 'content': 'Hello'}],
    prompt_format='costar'
)
assert '<system>' in prompt, 'Missing system tag'
assert '<user_input>' in prompt, 'Missing user_input tag'
assert '<｜' not in prompt, 'DSML tokens leaked into CO-STAR prompt'
print(f'OK: CO-STAR prompt ({len(prompt)} chars)')
print(prompt[:200])
"`

- [ ] **Step 4: Commit**

---

### Task 5: prompt_service.py — wire CO-STAR as default

**Files:**
- Modify: `server/services/prompt_service.py`

- [ ] **Step 1: Update `_build_prompt()` and `build_prompt()` to use PROMPT_FORMAT config**

Modify `_build_prompt()` module-level helper (line 35-47):

```python
def _build_prompt(
    messages: list[dict], tools: list | None = None,
    images: list | None = None, tool_choice: str | None = None,
    max_history_len: int | None = None,
    stealth: bool = True,
    prompt_format: str | None = None,
) -> str:
    """Build prompt delegating to dsml_prompt module."""
    from server.services.dsml_prompt import build_dsml_prompt
    from server.config import PROMPT_FORMAT as _cfg_format
    fmt = prompt_format or _cfg_format
    return build_dsml_prompt(
        messages, tools=tools, tool_choice=tool_choice,
        max_history_len=max_history_len,
        stealth=stealth,
        prompt_format=fmt,
    )
```

Modify `PromptService.build_prompt()` method to pass prompt_format:

```python
async def build_prompt(
    self,
    messages: list[dict],
    tools: list[dict] | None = None,
    images: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    max_history_len: int | None = None,
    response_format: dict | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
) -> str:
    """Build DSML prompt delegating to dsml_prompt module."""
    from server.services.dsml_prompt import build_dsml_prompt
    from server.config import PROMPT_FORMAT
    return build_dsml_prompt(
        messages, tools=tools, tool_choice=tool_choice,
        max_history_len=max_history_len,
        stealth=True,
        prompt_format=PROMPT_FORMAT,
    )
```

Also update `server/services/state_service.py` if it calls `_build_prompt` (check with grep).

- [ ] **Step 2: Verify the prompt_service works end-to-end**

Run: `python -c "
import sys; sys.path.insert(0, 'f:\\PROJEKTY\\DEEPSEEK_FRYTA\\deepseek-proxy')
from server.services.prompt_service import _build_prompt
p = _build_prompt([{'role':'user','content':'hi'}])
assert '<system>' not in p  # no system msg
assert '<user_input>' in p
print('OK: prompt_service uses CO-STAR by default')
"`

- [ ] **Step 3: Commit**

---

### Task 6: stream_service.py — remove watermark, clean tool call IDs

**Files:**
- Modify: `server/services/stream_service.py`

- [ ] **Step 1: Change `_tc_id()` to remove conv-uuid from tool call IDs**

Change line 31-33:

```python
def _tc_id() -> str:
    """Generate a clean tool-call ID with no embedded session info."""
    return f"call_{uuid.uuid4().hex[:8]}"
```

Update all callers of `_tc_id(conv_uuid)` to `_tc_id()` (lines 204, 217, 225, 289, 332).

- [ ] **Step 2: Remove inline watermark from text response**

Remove line 380:
```python
yield _chunk({"content": f"<!-- PROXY_SID: {conv_uuid} -->"})
```

The SID is already passed in the finish chunk below (line 381):
```python
yield _chunk({}, fr="stop", sid=conv_uuid)
```

That line stays unchanged.

- [ ] **Step 3: Add JSON tool call parsing in flush/thinking_fallback**

In the end-of-stream section (around line 258-363), add JSON parsing fallback.

After the existing thinking_fallback logic (before line 366), add:

```python
# JSON tool call fallback (CO-STAR mode)
if not end_tool_calls and not thinking_fallback:
    from server.parser.dsml_parser import parse_json_tool_calls
    json_tc, json_cleaned = parse_json_tool_calls(text_buffer, tool_names)
    if json_tc:
        json_tc = _validate_tool_calls(json_tc, tool_names)
        if json_tc:
            print(f"[DETECT_TOOL] end-of-stream JSON parse found {len(json_tc)} tool call(s)", flush=True)
            json_tool_list = []
            for idx, tc in enumerate(json_tc[:10]):
                valid_args = _ensure_valid_json(tc.get("arguments", "{}"))
                json_tool_list.append({
                    "index": idx,
                    "id": _tc_id(),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": valid_args,
                    },
                })
            _json_parent_id = stream_meta.get("resp_msg_id") or parent_id
            with conv_lock:
                state["parent_id"] = _json_parent_id
                state["msgs_len"] = len(req.messages)
                state["raw_msgs_len"] = _raw_msg_count
                state["_last_user_hash"] = _hash_last_user_message_sync(req.messages)
                state["_last_user_hash_full"] = _hash_last_user_message_sync(req.messages, full=True)
                conv_state[conv_uuid] = state
                _save_full()
                _log_conv_sync(conv_uuid, chat_id=state.get("ds_session", ""), response=text_buffer)
            if json_tool_list:
                yield _chunk({"tool_calls": json_tool_list})
            yield _chunk({}, fr="tool_calls")
            yield "data: [DONE]\n\n"
            return
```

- [ ] **Step 4: Run syntax check**

Run: `python -c "import sys; sys.path.insert(0, 'f:\\PROJEKTY\\DEEPSEEK_FRYTA\\deepseek-proxy'); from server.services.stream_service import StreamService; print('OK: imports fine')"`

- [ ] **Step 5: Commit**

---

### Task 7: update state_service references if needed

**Files:**
- Check: `server/services/state_service.py`

- [ ] **Step 1: Search for calls to `_build_prompt` or `build_dsml_prompt`**

Run: `grep -n "_build_prompt\|build_dsml_prompt\|_tc_id" server/services/state_service.py`

If state_service.py calls `_build_prompt`, update the call to pass `prompt_format` from config. If it calls `_tc_id`, update to the new no-arg version.

- [ ] **Step 2: Commit if changes were needed**

---

### Task 8: Tests for JSON tool call parsing

**Files:**
- Create: `tests/test_json_tool_parser.py`

- [ ] **Step 1: Write comprehensive test**

```python
"""Tests for JSON tool call parsing (CO-STAR format)."""

import json
from server.parser.dsml_parser import parse_json_tool_calls, clean_tool_call_markers


class TestParseJsonToolCalls:
    def test_single_tool_call(self):
        text = 'Hello ```tool_call\n{"name": "get_weather", "arguments": {"location": "Warsaw"}}\n``` world'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "get_weather"
        args = json.loads(tc[0]["arguments"])
        assert args["location"] == "Warsaw"
        assert "Hello" in cleaned
        assert "world" in cleaned

    def test_multiple_tool_calls(self):
        text = (
            '```tool_call\n{"name": "tool_a", "arguments": {"x": 1}}\n```\n'
            '```tool_call\n{"name": "tool_b", "arguments": {"y": 2}}\n```'
        )
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 2
        assert tc[0]["name"] == "tool_a"
        assert tc[1]["name"] == "tool_b"

    def test_malformed_json_ignored(self):
        text = 'some text ```tool_call\nnot valid json\n``` more text'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 0
        assert "some text" in cleaned
        assert "more text" in cleaned

    def test_no_tool_call_markers(self):
        text = "Just a regular response without any tool calls."
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 0
        assert cleaned == text.strip()

    def test_empty_text(self):
        tc, cleaned = parse_json_tool_calls("")
        assert len(tc) == 0
        assert cleaned == ""

    def test_tool_call_with_no_arguments(self):
        text = '```tool_call\n{"name": "simple_tool", "arguments": {}}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "simple_tool"
        assert json.loads(tc[0]["arguments"]) == {}

    def test_json_fallback_format(self):
        text = '```json\n{"name": "json_tool", "arguments": {"key": "val"}}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "json_tool"

    def test_string_arguments_parsed(self):
        text = '```tool_call\n{"name": "test", "arguments": "{\\"a\\": 1}"}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        args = json.loads(tc[0]["arguments"])
        assert args["a"] == 1

    def test_tool_name_variants(self):
        # Support both "name" and "tool" keys
        text = '```tool_call\n{"tool": "alt_name", "arguments": {}}\n```'
        tc, cleaned = parse_json_tool_calls(text)
        assert len(tc) == 1
        assert tc[0]["name"] == "alt_name"


class TestCleanToolCallMarkers:
    def test_removes_partial_markers(self):
        assert clean_tool_call_markers("```tool_call\nsomething") == ""
        assert clean_tool_call_markers("pre ```tool_call") == "pre"
        assert clean_tool_call_markers("text ```") == "text"
        assert clean_tool_call_markers("no markers") == "no markers"
        assert clean_tool_call_markers("") == ""
```

- [ ] **Step 2: Run tests**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -m pytest tests/test_json_tool_parser.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

---

### Task 9: update proxy.py to use JSON parsing in non-stream mode

**Files:**
- Read: `server/core/proxy.py`
- Modify: `server/core/proxy.py` (if needed)

- [ ] **Step 1: Check if proxy.py needs changes for non-stream JSON parsing**

Run: `grep -n "parse_dsml_tool_calls\|tool_calls_accum\|content_accum" server/core/proxy.py`

If the non-stream path in proxy.py accumulates tool calls, add JSON fallback parsing there too.

- [ ] **Step 2: Make changes if needed**

```python
# After existing DSML parsing, add:
from server.parser.dsml_parser import parse_json_tool_calls
if not tool_calls_accum and content_accum:
    json_tc, json_clean = parse_json_tool_calls(content_accum)
    if json_tc:
        tool_calls_accum = [
            {
                "id": _tc_id(),
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": _ensure_valid_json(tc.get("arguments", "{}")),
                },
            }
            for tc in json_tc
        ]
        content_accum = json_clean
```

- [ ] **Step 3: Commit**

---

### Task 10: integration smoke test

- [ ] **Step 1: Start the server in test mode**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -c "
import asyncio
from server.services.dsml_prompt import build_dsml_prompt

# Full integration test of the prompt builder
messages = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': 'What is the weather in Warsaw?'},
]
tools = [
    {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'description': 'Get weather for a location',
            'parameters': {
                'type': 'object',
                'properties': {
                    'location': {'type': 'string', 'description': 'City name'}
                },
                'required': ['location']
            }
        }
    }
]

prompt = build_dsml_prompt(messages, tools=tools, prompt_format='costar')
print('=== CO-STAR PROMPT ===')
print(prompt)
print('=== END ===')

# Verify no DSML tokens
assert '<｜' not in prompt, 'DSML tokens found!'
assert '<system>' in prompt
assert '<user_input>' in prompt
assert '<tools>' in prompt
assert '<rules>' in prompt
print('ALL CHECKS PASSED')
"
`

- [ ] **Step 2: Verify tool call parser works end-to-end**

Run: `cd f:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy && python -c "
from server.parser.dsml_parser import parse_json_tool_calls, parse_dsml_tool_calls
# Both should work (backward compatible)
# JSON format
tc1, _ = parse_json_tool_calls('\`\`\`tool_call\n{\"name\":\"x\",\"arguments\":{\"y\":1}}\n\`\`\`')
assert len(tc1) == 1
# DSML format (still works via existing parser)
tc2, _ = parse_dsml_tool_calls('<|DSML|tool_calls><|DSML|invoke name=\"x\"><|DSML|parameter name=\"y\"><![CDATA[1]]></|DSML|parameter></|DSML|invoke></|DSML|tool_calls>')
assert len(tc2) == 1
print('OK: Both JSON and DSML parsers work')
"
`

- [ ] **Step 3: No commit for verification step**
