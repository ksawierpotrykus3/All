# Ultra Stealth Prompt Format — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform DeepSeek proxy prompt format and request body to evade anti-bot detection.

**Architecture:** Add `stealth=True` parameter to `build_dsml_prompt()` that removes DSML BOS/System/instr_end markers, uses first-message-no-tag rule, and merges system into user. Strip `action`/`preempt`/`max_tokens`/`temperature`/`top_p` from request body.

**Tech Stack:** Python 3.11+, DeepSeek V4 Pro web chat API, full-width pipe `|` (U+FF5C) DSML tokens.

**Spec:** [2026-07-13-ultra-stealth-format-design.md](../specs/2026-07-13-ultra-stealth-format-design.md)

---

### Task 1: Add `stealth=True` mode to `dsml_prompt.py`

**Files:**
- Modify: `server/services/dsml_prompt.py` — add stealth format logic

- [ ] **Step 1: Add `stealth` parameter to `build_dsml_prompt()`**

Change the function signature from:
```python
def build_dsml_prompt(
    messages: list,
    tools: list | None = None,
    tool_choice: str = "auto",
    max_history_len: int | None = None,
) -> str:
```
To:
```python
def build_dsml_prompt(
    messages: list,
    tools: list | None = None,
    tool_choice: str = "auto",
    max_history_len: int | None = None,
    stealth: bool = True,
) -> str:
```

- [ ] **Step 2: Create `_format_msgs_stealth()` helper**

Add a new private function that implements the stealth format rules:

```python
def _format_msgs_stealth(messages: list[dict]) -> str:
    """Format messages into stealth DSML (first msg no tag, no BOS, system as user).
    
    Rules:
    1. Consecutive same-role messages are merged with \\n\\n
    2. First block (index=0) has NO tag — raw text
    3. Subsequent user/system → <｜User｜>{text}
    4. Assistant → <｜Assistant｜>{text}<｜end▁of▁sentence｜>
    5. Tool → <｜Tool｜>{name}\\n{text} (no closing tag)
    """
    from .dsml_prompt import DSML_USER, DSML_ASST, DSML_TOOL, DSML_EOS
    
    # Merge consecutive same-role
    merged: list[dict] = []
    current = dict(messages[0]) if messages else None
    if current is None:
        return ""
    for msg in messages[1:]:
        if msg["role"] == current["role"]:
            current["content"] += "\n\n" + str(msg.get("content", ""))
        else:
            merged.append(current)
            current = dict(msg)
    merged.append(current)

    # Tag insertion
    parts: list[str] = []
    for i, block in enumerate(merged):
        role = block["role"]
        text = str(block.get("content", ""))
        if i == 0:
            parts.append(text)  # ← NO TAG
        elif role in ("user", "system"):
            parts.append(f"{DSML_USER}{text}")
        elif role == "assistant":
            parts.append(f"{DSML_ASST}{text}{DSML_EOS}")
        elif role == "tool":
            # Find the tool name from the preceding assistant's tool_calls
            name = _find_tool_name(messages, block)
            parts.append(f"{DSML_TOOL}{name}\n{text}")
        else:
            parts.append(text)
    return "".join(parts)
```

- [ ] **Step 3: Create `_find_tool_name()` helper**

```python
def _find_tool_name(messages: list[dict], tool_block: dict) -> str:
    """Find tool name for a tool result by matching tool_call_id."""
    tool_call_id = tool_block.get("tool_call_id", "")
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if tc.get("id") == tool_call_id or tc.get("function", {}).get("name", ""):
                    return tc.get("function", {}).get("name", "unknown")
    return "unknown"
```

- [ ] **Step 4: Update `build_dsml_prompt()` to branch on `stealth`**

```python
def build_dsml_prompt(...):
    if stealth:
        return _format_msgs_stealth(messages)
    # ... existing DSML logic unchanged ...
```

For the stealth branch, the function should:
1. Merge tool schemas with system prompt (if tools provided)
2. Call `_format_msgs_stealth()` with the merged messages
3. NOT prepend DSML_BOS
4. NOT add DSML_ASST trailing marker
5. NOT use DSML_INSTR_END or DSML_TOOL_END

- [ ] **Step 5: Commit**

```bash
git add server/services/dsml_prompt.py
git commit -m "feat: add stealth=True mode to build_dsml_prompt"
```

---

### Task 2: Update `prompt_service.py` to use stealth mode

**Files:**
- Modify: `server/services/prompt_service.py:65-75` — pass `stealth=True`

- [ ] **Step 1: Change `build_dsml_prompt()` call to pass `stealth=True`**

Find the call site (around line 65-75 in `prompt_service.py`):
```python
prompt = build_dsml_prompt(
    msg_list,
    tools=tools_list,
    tool_choice=tool_choice,
    max_history_len=max_history,
)
```
Change to:
```python
prompt = build_dsml_prompt(
    msg_list,
    tools=tools_list,
    tool_choice=tool_choice,
    max_history_len=max_history,
    stealth=True,
)
```

- [ ] **Step 2: Commit**

```bash
git add server/services/prompt_service.py
git commit -m "feat: enable stealth prompt format in prompt_service"
```

---

### Task 3: Clean up request body in `deepseek_client.py`

**Files:**
- Modify: `server/core/deepseek_client.py` — remove extra fields from `stream_completion()`

- [ ] **Step 1: Simplify `stream_completion()` signature**

Change from:
```python
async def stream_completion(
    self, slot, chat_session_id, prompt,
    parent_message_id=None,
    max_tokens=8192, temperature=1.0, top_p=1.0,
    model_type="expert", ref_file_ids=None, _retry=0,
):
```
To:
```python
async def stream_completion(
    self, slot, chat_session_id, prompt,
    parent_message_id=None,
    model_type="expert", ref_file_ids=None,
    thinking_enabled=True, search_enabled=False,
    _retry=0,
):
```

- [ ] **Step 2: Clean up JSON body in `stream_completion()`**

Change the `json={...}` dict in the POST request (around lines 269-281):
```python
# BEFORE:
json={
    "chat_session_id": chat_session_id,
    "parent_message_id": parent_msg_id,
    "model_type": model_type,
    "prompt": prompt,
    "ref_file_ids": ref_file_ids or [],
    "thinking_enabled": True,
    "search_enabled": False,
    "action": None,
    "preempt": False,
    "max_tokens": max_tokens,
    "temperature": temperature,
    "top_p": top_p,
}
```
```python
# AFTER:
json={
    "chat_session_id": chat_session_id,
    "parent_message_id": parent_msg_id,
    "model_type": model_type,
    "prompt": prompt,
    "ref_file_ids": ref_file_ids or [],
    "thinking_enabled": thinking_enabled,
    "search_enabled": search_enabled,
}
```

- [ ] **Step 3: Commit**

```bash
git add server/core/deepseek_client.py
git commit -m "refactor: remove extra fields from stream_completion body"
```

---

### Task 4: Update `proxy.py` call sites

**Files:**
- Modify: `server/core/proxy.py` — remove extra params from `stream_completion()` calls

- [ ] **Step 1: Update call sites in `proxy.py`**

Find all `ds.stream_completion()` calls (approx 3 sites around lines 407-410, 483-486).

Change each from:
```python
ds.stream_completion(idx, chat_session_id, prompt, parent_id,
                     max_tok, temp, top_p,
                     model_type=mt, ref_file_ids=ref_ids)
```
To:
```python
ds.stream_completion(idx, chat_session_id, prompt, parent_id,
                     model_type=mt, ref_file_ids=ref_ids)
```

Verify there's no unused `max_tok`, `temp`, `top_p` local variables after the changes.

- [ ] **Step 2: Commit**

```bash
git add server/core/proxy.py
git commit -m "refactor: remove extra params from stream_completion calls in proxy"
```

---

### Task 5: Update `stream_service.py` retry calls

**Files:**
- Modify: `server/services/stream_service.py` — update error recovery calls

- [ ] **Step 1: Update retry calls in `stream_service.py`**

Find the error recovery `stream_completion()` calls (around lines 404, 436).

Change each from:
```python
ds.stream_completion(new_acct, new_chat_id, p, None,
                     max_tok, temp, top_p, model_type=model_type)
```
To:
```python
ds.stream_completion(new_acct, new_chat_id, p, None,
                     model_type=model_type)
```

Verify `max_tok`, `temp`, `top_p` aren't passed elsewhere.

- [ ] **Step 2: Commit**

```bash
git add server/services/stream_service.py
git commit -m "refactor: remove extra params from stream_completion retry calls"
```

---

### Task 6: Update tests for stealth format

**Files:**
- Modify: `tests/test_dsml_prompt.py` — add stealth-specific tests
- Modify: `tests/test_stealth_dsml.py` — add stealth format tests

- [ ] **Step 1: Add stealth tests to `test_dsml_prompt.py`**

Add these test functions (or a `TestStealthMode` class):

```python
class TestStealthMode:
    """Tests for stealth=True mode (ultra stealth format)."""

    def test_no_bos_token(self):
        """Stealth mode should NOT contain BOS token."""
        result = build_dsml_prompt([
            {"role": "user", "content": "Hello"}
        ], stealth=True)
        assert DSML_BOS not in result
        assert not result.startswith(DSML_BOS)

    def test_no_system_block(self):
        """Stealth mode should NOT contain separate <｜System｜> block."""
        result = build_dsml_prompt([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ], stealth=True)
        assert DSML_SYS not in result
        assert "You are helpful." in result

    def test_first_msg_no_tag(self):
        """First message in stealth mode should have NO tag prefix."""
        result = build_dsml_prompt([
            {"role": "user", "content": "First message"}
        ], stealth=True)
        # Should start with raw text, not <｜User｜>
        assert result.startswith("First message")
        assert not result.startswith(DSML_USER)

    def test_second_user_has_tag(self):
        """Second user message should have <｜User｜> tag."""
        result = build_dsml_prompt([
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second"},
        ], stealth=True)
        assert "First" in result
        assert f"{DSML_USER}Second" in result

    def test_assistant_has_tag_and_eos(self):
        """Assistant messages should have <｜Assistant｜> and <｜end▁of▁sentence｜>."""
        result = build_dsml_prompt([
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ], stealth=True)
        assert f"{DSML_ASST}Hello!" in result
        assert result.endswith(DSML_EOS) or f"Hello!{DSML_EOS}" in result

    def test_no_agentic_preamble(self):
        """Stealth mode should NOT add 'You are an AI agent'."""
        result = build_dsml_prompt([
            {"role": "user", "content": "Hi"}
        ], stealth=True)
        assert "You are an AI agent" not in result

    def test_no_output_integrity_guard(self):
        """Stealth mode should NOT add 'Output integrity guard'."""
        result = build_dsml_prompt([
            {"role": "user", "content": "Hi"}
        ], stealth=True)
        assert "Output integrity guard" not in result

    def test_no_instr_end(self):
        """Stealth mode should NOT contain <｜end▁of▁instructions｜>."""
        result = build_dsml_prompt([
            {"role": "user", "content": "Hi"}
        ], stealth=True)
        assert DSML_INSTR_END not in result

    def test_tool_result_no_tool_end(self):
        """Tool results should NOT have <｜end▁of▁toolresults｜>."""
        result = build_dsml_prompt([
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "Read", "arguments": '{"x": "y"}'}}]},
            {"role": "tool", "content": "file data", "tool_call_id": "c1"},
            {"role": "user", "content": "Thanks"},
        ], stealth=True)
        assert DSML_TOOL in result
        assert "file data" in result
        assert DSML_TOOL_END not in result

    def test_consecutive_same_role_merged(self):
        """Consecutive same-role messages should be merged with \\n\\n."""
        result = build_dsml_prompt([
            {"role": "user", "content": "First"},
            {"role": "user", "content": "Second"},
            {"role": "assistant", "content": "Response"},
        ], stealth=True)
        # Both user messages should be in a single block (no tag between them)
        assert "First\n\nSecond" in result
        # Only one DSML_USER should appear for the merged block
        assert result.count(DSML_USER) >= 0  # first block has no tag

    def test_system_treated_as_user(self):
        """System message should be treated as user (no <｜System｜>)."""
        result = build_dsml_prompt([
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ], stealth=True)
        assert DSML_SYS not in result
        # The system message is the first block → no tag
        assert "Be helpful." in result
```

- [ ] **Step 2: Run stealth tests to verify they pass**

Run: `python -m pytest tests/test_dsml_prompt.py::TestStealthMode -v`
Expected: All tests PASS

- [ ] **Step 3: Run existing non-stealth tests to verify backward compatibility**

Run: `python -m pytest tests/test_dsml_prompt.py -v --ignore-glob='*Stealth*'`
OR run all tests excluding the stealth class:
Run: `python -m pytest tests/test_dsml_prompt.py -v -k "not Stealth"`
Expected: Existing tests still PASS (they use `stealth=False` by default)

Note: The default for `stealth` is `True`, so existing importers of `build_dsml_prompt` without explicit `stealth=` will get stealth mode. The tests that check for `DSML_BOS`, `DSML_SYS`, etc. with `stealth=True` (the new default) will need to either:
- Explicitly pass `stealth=False` in those test calls, OR
- Be updated to test stealth-specific assertions

The cleanest approach: update existing tests to explicitly pass `stealth=False` for backward-compat assertions.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dsml_prompt.py
git commit -m "test: add stealth mode tests to test_dsml_prompt"
```

---

### Task 7: Run full test suite and fix regressions

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

If any existing tests fail because they rely on `stealth=False` behavior:
- Add `stealth=False` to the `build_dsml_prompt()` call in those tests

- [ ] **Step 2: Final commit with all test fixes**

```bash
git add -A
git commit -m "test: fix test regressions from stealth mode changes"
```
