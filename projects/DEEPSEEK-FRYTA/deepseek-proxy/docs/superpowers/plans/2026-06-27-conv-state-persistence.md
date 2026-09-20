# Conv State Persistence & [new chat] Detection

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist DeepSeek session mapping across server restarts, detect `[new chat]` to force fresh sessions, and add retry on "Server is busy" errors.

**Architecture:** Single-file changes to `server.py`. Add `conv_state.json` for persistence near existing `session.json`. Add marker scanning in user messages before resume logic. Merge retry logic with existing rate-limit handler.

**Tech Stack:** Python 3.11+, standard library (json, hashlib, Path, re, time)

---

### Task 1: Conv State Load/Save helpers

**Files:**
- Modify: `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server.py` (new functions + load at module level)

- [ ] **Step 1: Find existing SESSION_FILE constant**

Read around line 12 in `server.py`:
```python
SESSION_FILE = Path(__file__).parent / "session.json"
```

- [ ] **Step 2: Add CONV_STATE_FILE constant**

After `SESSION_FILE`:
```python
CONV_STATE_FILE = Path(__file__).parent / "conv_state.json"
```

- [ ] **Step 3: Add load/save conv state functions**

After the existing `_save_tools` and `_load_tools` functions (around line 644), add:

```python
def _save_conv_state():
    try:
        CONV_STATE_FILE.write_text(json.dumps(_conv_state, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[CONV SAVE ERROR] {e}", flush=True)

def _load_conv_state() -> dict:
    try:
        if CONV_STATE_FILE.exists():
            data = json.loads(CONV_STATE_FILE.read_text())
            return data
    except Exception as e:
        print(f"[CONV LOAD ERROR] {e}", flush=True)
    return {}
```

- [ ] **Step 4: Initialize _conv_state from file**

Find `_conv_state: dict = {}` at line 621. Change to:

```python
_conv_state: dict = {}
```

Then BEFORE the first request handler (after the `_ensure_auth` function, around line 622), actually no - `_conv_state` is module-level. Change its initialization to:

```python
_conv_state: dict = _load_conv_state()
```

- [ ] **Step 5: Done check - verify file loads correctly**

Run: `python -c "exec(open('server.py').read().split('@app.get')[0]); print('loaded ok')"` from `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy`

No errors expected.

---

### Task 2: Save conv_state after every mutation

**Files:**
- Modify: `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server.py`

Find every place where `_conv_state[sys_hash]` is assigned/modified and add `_save_conv_state()` call.

- [ ] **Step 1: Save after new session creation**

Find:
```python
_conv_state[sys_hash] = state
```

Add after:
```python
_save_conv_state()
```

There are TWO places where this happens:
1. At line ~751 (inside the fresh session `else` branch): `_conv_state[sys_hash] = state`
2. At line ~754 (the assignment of `state["parent_id"]` and `state["msgs_len"]` happens after)

Wait, the state is mutated in-place. Let me find the exact locations.

Line ~751: `_conv_state[sys_hash] = state` after creating the new session state dict. Add `_save_conv_state()` after this.

Lines ~754-755:
```python
state["parent_id"] = resp_msg_id or state.get("parent_id")
state["msgs_len"] = len(req.messages)
```
Add `_save_conv_state()` after BOTH of these (or after the second one).

- [ ] **Step 2: Verify save paths**

Confirm the code saves after:
1. Fresh session creation (`_conv_state[sys_hash] = state`)
2. After parent_id and msgs_len updates:
```python
state["parent_id"] = resp_msg_id or state.get("parent_id")
state["msgs_len"] = len(req.messages)
```
3. After `_conv_state.pop(sys_hash, None)` (will be added in Task 3)

All three should call `_save_conv_state()` after the mutation.

---

### Task 3: `[new chat]` marker detection

**Files:**
- Modify: `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server.py`

- [ ] **Step 1: Add marker check before resume logic**

Find the resume decision code (around line ~707-708):
```python
resume = state and state.get("parent_id") is not None and len(req.messages) > state.get("msgs_len", 0)
```

Add BEFORE this line, the marker scan:

```python
# Check for [new chat] or [new] marker in user's last message
for i in range(len(req.messages) - 1, -1, -1):
    m = req.messages[i]
    if m.get("role") == "user":
        user_content = m.get("content", "")
        if isinstance(user_content, list):
            user_content = " ".join(p.get("text", "") for p in user_content if isinstance(p, dict) and p.get("type") == "text")
        if isinstance(user_content, str) and re.search(r'\[new(?:\s+chat)?\]', user_content, re.IGNORECASE):
            print(f"[NEW CHAT] marker detected in message {i}, clearing conv state for {sys_hash[:8]}...", flush=True)
            _conv_state.pop(sys_hash, None)
            _save_conv_state()
            state = None
            break
```

- [ ] **Step 2: Verify `re` is already imported**

Check line 1 of server.py:
```python
import json, time, uuid, re, hashlib, threading, os
```
`re` is already imported. Good.

- [ ] **Step 3: Done check - restart server and test**

Restart server, send a message with `[new chat]` from Trae, verify in log:
```
[NEW CHAT] marker detected in message X, clearing conv state for 0cbf427e...
```

---

### Task 4: "Server is busy" retry

**Files:**
- Modify: `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server.py`

- [ ] **Step 1: Extend rate-limit retry to also handle "Server is busy"**

Find the existing rate-limit retry in `_stream()` (around line ~214-220):
```python
if data.get("type") == "error":
    err_msg = data.get("content", "Unknown error")
    print(f"[ERROR] DeepSeek error: {err_msg}", flush=True)
    if "too frequent" in err_msg.lower():
        wait = 8
        print(f"[RETRY] Rate limited, waiting {wait}s then retrying...", flush=True)
        time.sleep(wait)
        return self.stream_completion(chat_session_id, prompt, parent_message_id)
    raise RuntimeError(f"DeepSeek error: {err_msg}")
```

Change the condition from `if "too frequent" in err_msg.lower():` to also catch "server is busy":
```python
if "too frequent" in err_msg.lower() or "server is busy" in err_msg.lower():
    wait = 12
    print(f"[RETRY] DeepSeek busy/rate-limited, waiting {wait}s then retrying...", flush=True)
    time.sleep(wait)
    return self.stream_completion(chat_session_id, prompt, parent_message_id)
```

Also apply the same fix to the pre-loop rate limit handler (around line ~185-190) if it has a similar pattern.

- [ ] **Step 2: Verify no duplicate retry logic**

Check that the pre-loop retry (lines ~185-190) also handles "Server is busy". If applicable, merge conditions.

---

### Task 5: (Optional) Decode `acl-token` JWT header

**Files:**
- Modify: `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server.py`

- [ ] **Step 1: Decode and log acl-token payload**

In the header logging section (around line ~692), after printing all headers, add:

```python
# Decode acl-token JWT to check for conversation IDs
acl_token = raw_request.headers.get("acl-token", "")
if acl_token and acl_token.count(".") == 2:
    try:
        # JWT payload is the second base64 segment
        payload_b64 = acl_token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)  # pad
        payload = json.loads(base64.b64decode(payload_b64))
        print(f"[ACL TOKEN] payload keys: {list(payload.keys())}", flush=True)
        for pk in ["sub", "session", "conv", "chat", "jid", "sid"]:
            if pk in payload:
                print(f"[ACL TOKEN] {pk}: {payload[pk]}", flush=True)
    except Exception as e:
        print(f"[ACL TOKEN] decode error: {e}", flush=True)
```

- [ ] **Step 2: Add base64 import**

Add `base64` to the imports at line 1:
```python
import json, time, uuid, re, hashlib, threading, os, base64
```

- [ ] **Step 3: Restart and check**

Restart server, send a Trae request, check log for `[ACL TOKEN]` lines.

---

### Task 6: Cleanup - remove temporary header logging

**Files:**
- Modify: `F:\PROJEKTY\DEEPSEEK_FRYTA\deepseek-proxy\server.py`

- [ ] **Step 1: Remove all-headers logging**

After confirming no conv ID in Token, remove the temporary `[HEADERS] all headers:` loop (the one that prints EVERY header).

Keep only the `acl-token` decoder (Task 5) which gives us useful JWT info.

- [ ] **Step 2: Remove message metadata search**

Remove the loop searching for `metadata`/`extra`/`custom`/`tags` in messages (added in earlier brainstorm edit) since it found nothing.

- [ ] **Step 3: Final verification**

Run: `python -c "import py_compile; py_compile.compile('server.py', doraise=True)"`
Expected: no output (success)
