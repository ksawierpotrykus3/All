# Stealth Align Fly143 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align proxy's HTTP headers, impersonation, prompt format, and stealth approach with the working deepseek-free-api (Fly143) reference implementation.

**Architecture:** The current proxy has an over-engineered stealth module (FingerprintCookies, BrowserTelemetry, augment_headers) and uses stealth prompt format (`[System]:`, `[User]:`). Fly143 works without any stealth module using DSML format directly. We simplify: remove stealth module, use DSML prompt format, fix headers/impersonate mismatch.

**Tech Stack:** Python, curl_cffi, FastAPI, DSML prompt tokens

---

### Task 1: Simplify HTTP headers in DeepSeek client

**Files:**
- Modify: `server/core/deepseek_client.py:149-184`

- [ ] **Step 1: Update default session headers**

Replace the current custom headers with Fly143-style DS_HEADERS:

```python
# Current (line 150-159)
self._http.headers.update({
    "accept": "*/*",
    "content-type": "application/json",
    "origin": "https://chat.deepseek.com",
    "referer": "https://chat.deepseek.com/",
    "x-app-version": "2.0.0",
    "x-client-locale": "en_US",
    "x-client-platform": "web",
    "x-client-version": "2.0.0",
})

# Target
self._http.headers.update({
    "content-type": "application/json",
    "origin": "https://chat.deepseek.com",
    "referer": "https://chat.deepseek.com/",
    "x-client-platform": "web",
    "x-client-version": "2.0.2",
})
```

- [ ] **Step 2: Update per-request headers function**

```python
# Current (line 168-184)
def _headers(self, slot: int, pow_resp: str | None = None) -> dict:
    s = self._ses(slot)
    h = {
        "accept": "*/*",
        "authorization": f"Bearer {s.auth_token}",
        "content-type": "application/json",
        "origin": "https://chat.deepseek.com",
        "referer": "https://chat.deepseek.com/",
        "user-agent": s.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "x-app-version": "2.0.0",
        "x-client-locale": "en_US",
        "x-client-platform": "web",
        "x-client-version": "2.0.0",
    }
    if pow_resp:
        h["x-ds-pow-response"] = pow_resp
    return h

# Target
def _headers(self, slot: int, pow_resp: str | None = None) -> dict:
    s = self._ses(slot)
    h = {
        "accept": "*/*",
        "authorization": f"Bearer {s.auth_token}",
        "content-type": "application/json",
        "origin": "https://chat.deepseek.com",
        "referer": "https://chat.deepseek.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
        "x-client-platform": "web",
        "x-client-version": "2.0.2",
    }
    if pow_resp:
        h["x-ds-pow-response"] = pow_resp
    return h
```

**Changes:**
- UA: `Chrome/149.0.0.0` → `Chrome/134.0.0.0`
- `x-client-version`: `2.0.0` → `2.0.2`
- Remove: `x-app-version`, `x-client-locale`
- Remove fallback to `s.user_agent` (always use hardcoded Chrome/134)

- [ ] **Step 3: Verify no other references**

Run: `Get-ChildItem -Recurse -Filter "*.py" | Select-String "x-app-version|x-client-locale" | Select-String -NotMatch "\.git"` — should find zero matches.

- [ ] **Step 4: Commit**

```bash
git add server/core/deepseek_client.py
git commit -m "fix: simplify HTTP headers to match Fly143 DS_HEADERS"
```

### Task 2: Change impersonate from chrome120 to chrome134

**Files:**
- Modify: `server/core/deepseek_client.py:195,243,289`

- [ ] **Step 1: Replace all `impersonate="chrome120"` with `impersonate="chrome134"`**

Three occurrences in `deepseek_client.py`:
```python
# Line ~195 (_get_challenge)
impersonate="chrome134",

# Line ~243 (create_session)
impersonate="chrome134",

# Line ~289 (stream_completion)
impersonate="chrome134",
```

- [ ] **Step 2: Commit**

```bash
git add server/core/deepseek_client.py
git commit -m "fix: impersonate chrome134 to match User-Agent"
```

### Task 3: Remove stealth.py and all references

**Files:**
- Delete: `server/core/stealth.py`
- Modify: `server/core/__init__.py`

- [ ] **Step 1: Delete stealth.py**

Delete `server/core/stealth.py`.

- [ ] **Step 2: Update __init__.py**

```python
# Current (line 1-2)
"""Server core package."""
from .stealth import StealthEngine

# Target
"""Server core package."""
```

- [ ] **Step 3: Verify no stealth imports remain**

Run: `Get-ChildItem -Recurse -Filter "*.py" | Select-String "from.*stealth|import.*stealth" | Select-String -NotMatch "\.git"` — should find zero matches.

- [ ] **Step 4: Commit**

```bash
git add server/core/stealth.py server/core/__init__.py
git commit -m "fix: remove stealth module (FingerprintCookies, BrowserTelemetry, augment_headers)"
```

### Task 4: Update dsml_prompt.py — remove deprecation, align with Fly143

**Files:**
- Modify: `server/services/dsml_prompt.py`

- [ ] **Step 1: Remove DeprecationWarning**

Remove lines 10-15:
```python
import warnings

warnings.warn(
    "dsml_prompt.py is DEPRECATED. Use prompt_service.py instead. "
    "This module is kept for reference only and will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)
```

- [ ] **Step 2: Align `build_dsml_prompt()` with Fly143's `convert_messages_for_deepseek()`**

Key changes to `build_dsml_prompt()`:
- Remove `OUTPUT_INTEGRITY_GUARD` — Fly143 doesn't use this
- Truncate tool results to **500 chars** (currently 1000): change line 109-110 from `tool_content[:1000]` to `tool_content[:500]`
- Ensure tool definitions appended to system prompt block match Fly143 format (already close)
- Keep `build_dsml_tool_prompt()` for tool definitions — already matches Fly143

```python
# Target — updated build_dsml_prompt
def build_dsml_prompt(
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    tool_choice: Optional[str] = None,
    images: Optional[List[str]] = None,
    max_history_len: Optional[int] = None,
) -> str:
    messages = list(messages)
    if max_history_len and len(messages) > max_history_len:
        messages = messages[-max_history_len:]

    parts: list[str] = [DSML_BOS]
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
            if len(tool_content) > 500:  # Fly143 truncates to 500
                tool_content = tool_content[:500] + "...(truncated)"
            parts.append(DSML_TOOL + tool_content + DSML_TOOL_END)

        last_role = role

    if last_role != "assistant" and not parts[-1].endswith(DSML_EOS):
        parts.append(DSML_ASST)

    return "".join(parts)
```

- [ ] **Step 3: Add async wrapper for PromptService compatibility**

Add at the end of `dsml_prompt.py`:
```python
async def build_prompt_async(
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    images: Optional[List[str]] = None,
    tool_choice: Optional[str] = None,
    max_history_len: Optional[int] = None,
    response_format: Optional[dict] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
) -> str:
    """Async wrapper for PromptService compatibility."""
    return build_dsml_prompt(
        messages, tools=tools, tool_choice=tool_choice,
        images=images, max_history_len=max_history_len,
    )
```

- [ ] **Step 4: Commit**

```bash
git add server/services/dsml_prompt.py
git commit -m "fix: update dsml_prompt.py — remove deprecation, align tool truncation with Fly143"
```

### Task 5: Refactor prompt_service.py — replace stealth with DSML delegation

**Files:**
- Modify: `server/services/prompt_service.py`

- [ ] **Step 1: Remove stealth format functions**

Delete these functions entirely from `prompt_service.py`:
- `_format_msgs()` (lines ~55-106)
- `_format_tool_calls_stealth()` (lines ~109-141)
- `_format_params_stealth()` (lines ~144-197+) 
- `_get_agentic_instruction()` (lines ~200-209)
- `_build_emulated_params_instructions()` (lines ~212-281)
- `_build_prompt_sync()` (lines ~288-433)

- [ ] **Step 2: Replace `PromptService.build_prompt()` to call dsml_prompt.py**

Change `build_prompt()` to delegate to `build_dsml_prompt()`:

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
    """Build DSML prompt delegating to dsml_prompt."""
    return build_dsml_prompt(
        messages, tools=tools, tool_choice=tool_choice,
        images=images, max_history_len=max_history_len,
    )
```

Add import at top:
```python
from server.services.dsml_prompt import build_dsml_prompt
```

- [ ] **Step 3: Keep existing helper methods**

Keep these methods — they handle context management, not prompt format:
- `_trim_context()` / `trim_context()`
- `_cascade_compress_tool_results()` / `cascade_compress_tool_results()`
- `_reconstruct_resume_messages()` / `reconstruct_resume_messages()`
- `_clean_user_content()`

- [ ] **Step 4: Commit**

```bash
git add server/services/prompt_service.py
git commit -m "fix: replace stealth prompt format with DSML delegation in PromptService"
```

### Task 6: Update stream_service.py and helpers.py imports

**Files:**
- Modify: `server/services/stream_service.py:28`
- Modify: `server/utils/helpers.py:60`

- [ ] **Step 1: Update stream_service.py**

```python
# Current (line 28)
from server.services.prompt_service import _build_prompt_sync

# Target — _build_prompt_sync no longer exists, use dsml_prompt.build_dsml_prompt instead
from server.services.dsml_prompt import build_dsml_prompt as _build_prompt_sync
```

- [ ] **Step 2: Update helpers.py**

```python
# Current (line 60)
from server.services.prompt_service import _build_prompt_sync

# Target
from server.services.dsml_prompt import build_dsml_prompt as _build_prompt_sync
```

- [ ] **Step 3: Commit**

```bash
git add server/services/stream_service.py server/utils/helpers.py
git commit -m "fix: update imports to use dsml_prompt.build_dsml_prompt"
```

### Task 7: Update tests

**Files:**
- Modify: All test files referencing `_build_prompt_sync` or stealth format

- [ ] **Step 1: Find and update test imports**

Run: `Select-String -Path tests\* -Pattern "_build_prompt_sync|prompt_service|stealth"`

For each test file:
- Replace `from server.services.prompt_service import _build_prompt_sync` with `from server.services.dsml_prompt import build_dsml_prompt as _build_prompt_sync`
- Replace `from server.services.prompt_service import PromptService` with `from server.services.dsml_prompt import build_dsml_prompt as _build_prompt_sync`

- [ ] **Step 2: Run existing tests to verify fix**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "fix: update test imports to use dsml_prompt"
```

### Task 8: Full verification

**Files:**
- All modified files

- [ ] **Step 1: Verify all imports resolve**

```bash
python -c "from server.core.deepseek_client import ap, ds; from server.services.dsml_prompt import build_dsml_prompt; print('OK')"
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1
```

- [ ] **Step 3: Check for any remaining stealth references**

```bash
Get-ChildItem -Recurse -Filter "*.py" | Select-String "stealth|x-app-version|x-client-locale|chrome120|chrome149|_get_agentic_instruction|_build_emulated_params|_format_tool_calls_stealth|_build_prompt_sync" | Select-String -NotMatch "\.git|stealth-align"
```
