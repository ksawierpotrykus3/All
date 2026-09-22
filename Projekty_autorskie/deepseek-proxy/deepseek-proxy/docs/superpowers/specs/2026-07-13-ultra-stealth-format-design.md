# Ultra Stealth Prompt Format — Design Spec

**Date:** 2026-07-13
**Status:** Draft
**Context:** deepseek-proxy server — evade DeepSeek anti-bot detection ("user is muted", biz_code=5/14)

---

## 1. Problem

DeepSeek web chat API detects proxy/automation clients via multiple signals:

1. **DSML BOS token** `<|begin▁of▁sentence|>` — strong automation signature
2. **Separate `<|System|>` block** with AI boilerplate (`Output Integrity Guard`, `You are an AI agent`)
3. **Over-structured prompt** with full role tagging on every message (including the first)
4. **Extra request body fields** (`action`, `preempt`, `max_tokens`, `temperature`, `top_p`) that the official web UI never sends
5. **Patterned session behaviour** (no explicit session creation, high session churn)

The official web UI and mobile app do none of these — they send minimal requests and let the DeepSeek backend handle formatting internally.

## 2. Goal

Transform the prompt format and request structure to be indistinguishable from the official web UI. Specifically:

- Eliminate all detectable DSML boilerplate
- Mirror the `messagesPrepare()` format from Fly143/deepseek-free-api (proven less detectable)
- Strip unnecessary request body fields
- Keep functional requirements: tool calls, multi-turn, system prompts, thinking/search flags

## 3. Prompt Format (Stealth DSML)

### 3.1 Core Rules

Rules for transforming messages into the prompt string:

1. **No BOS token** — never prepend `<|begin▁of▁sentence|>`
2. **System prompt → treated as User** — no separate `<|System|>` block. System content is merged into the message sequence as a User-role block.
3. **First message has NO tag** — the first block in the sequence (whether system, user, or tool schema) is rendered as raw text without any role marker
4. **Subsequent User/System messages** → `<|User|>{content}`
5. **Assistant messages** → `<|Assistant|>{content}<|end▁of▁sentence|>`
6. **Tool results** → `<|Tool|>{name}\n{content}` (no closing tag)
7. **Consecutive same-role messages** → merged into a single block with `\n\n` separator
8. **Image markdown** → removed via regex `/!\[.+\]\(.+\)/g`

### 3.2 Character Set

Use full-width vertical bar `|` (U+FF5C) for tags:
- `<|User|>`
- `<|Assistant|>`
- `<|Tool|>`
- `<|end▁of▁sentence|>`

### 3.3 Tool Schema Injection

Tool schemas are prepended **as natural text** (not DSML) and merged into the system prompt block:

```
# Available Tool Schemas

## get_weather
  Get current weather for a location.
  Parameters:
    - location (string) (required): City name

Call format — when you need to use a tool, output exactly:

<tool_call>
  <parameter name="param">value</parameter>
</tool_call>
```

### 3.4 Examples

**Plain chat (no tools):**
```
You are a helpful assistant.
<|User|>What is quantum computing?
<|Assistant|>Quantum computing uses quantum mechanics.<|end▁of▁sentence|>
<|User|>Tell me more about qubits.
```

**First message (no tag on the first block):**
```
What is the weather in Tokyo?
```

**With tool schemas (merged into system block):**
```
# Available Tool Schemas

## get_weather
  Get current weather.
  Parameters:
    - location (string) (required): City name

You are a helpful assistant with access to weather data.
<|User|>What is the weather in Tokyo?
```

## 4. Request Body Changes

### 4.1 `chat_completion` endpoint

**Before (current):**
```json
{
  "chat_session_id": "...",
  "parent_message_id": null,
  "model_type": "expert",
  "prompt": "<|begin▁of▁sentence|><|System|>...",
  "ref_file_ids": [],
  "thinking_enabled": true,
  "search_enabled": false,
  "action": null,
  "preempt": false,
  "max_tokens": 8192,
  "temperature": 1.0,
  "top_p": 1.0
}
```

**After (stealth):**
```json
{
  "chat_session_id": "...",
  "parent_message_id": null,
  "model_type": "expert",
  "prompt": "You are a helpful assistant.\n<|User|>Hello",
  "ref_file_ids": [],
  "thinking_enabled": true,
  "search_enabled": false
}
```

**Removed fields:** `action`, `preempt`, `max_tokens`, `temperature`, `top_p`

### 4.2 `stream_completion()` Python signature

**Before:**
```python
def stream_completion(self, slot, chat_session_id, prompt,
                      parent_message_id=None,
                      max_tokens=8192, temperature=1.0, top_p=1.0,
                      model_type="expert", ref_file_ids=None, _retry=0):
```

**After:**
```python
def stream_completion(self, slot, chat_session_id, prompt,
                      parent_message_id=None,
                      model_type="expert", ref_file_ids=None,
                      thinking_enabled=True, search_enabled=False,
                      _retry=0):
```

## 5. Files to Modify

### 5.1 `server/services/dsml_prompt.py` — Prompt builder rewrite

**Changes:**
- Remove `DSML_BOS`, `DSML_SYS`, `DSML_INSTR_END`, `DSML_TOOL_END` constants
- Keep `DSML_USER`, `DSML_ASST`, `DSML_TOOL`, `DSML_EOS` (still used for tagging)
- Add parameter `stealth=True` to `build_dsml_prompt()`
- In `_format_msgs()`:
  - Index 0 → no tag (raw content)
  - Index > 0 → `<|User|>{content}`
  - Assistant → `<|Assistant|>{content}<|end▁of▁sentence|>`
  - Tool → `<|Tool|>{name}\n{content}` (no closing)
- System prompt merged into block 0
- Consecutive same-role blocks merged with `\n\n`
- Image markdown stripped

### 5.2 `server/core/deepseek_client.py` — Request body cleanup

**Changes:**
- `stream_completion()`: remove `max_tokens`, `temperature`, `top_p` parameters
- Remove `action`, `preempt`, `max_tokens`, `temperature`, `top_p` from JSON body

### 5.3 `server/core/proxy.py` — Call site updates

**Changes:**
- Remove `max_tok`, `temperature`, `top_p` from `ds.stream_completion()` calls (3 call sites)
- Keep `model_type` (required for V4 Pro)

### 5.4 `server/services/stream_service.py` — Error recovery updates

**Changes:**
- In `generate()` error paths (lines ~404, ~436): remove `max_tok`, `temperature`, `top_p` from retry `stream_completion()` calls

### 5.5 `server/services/prompt_service.py` — Delegation update

**Changes:**
- Pass `stealth=True` to `build_dsml_prompt()`

## 6. Non-Goals

- **StreamSieve** (`dsml_sieve.py`) — unchanged. DeepSeek response format is the same; only the request prompt changes.
- **DSML parser** (`dsml_parser.py`) — unchanged. Response-side DSML tool call parsing stays.
- **State service** (`state_service.py`) — unchanged.
- **Auth/Acount services** — unchanged.
- **Session creation** — already done. `deepseek_client.create_session()` works.

## 7. Verification

After implementation, verify on a fresh (non-muted) DeepSeek account:

1. Send a plain chat message → expect normal response
2. Send with system prompt → system prompt correctly interpreted
3. Send with tool schemas → tool call detected and parsed by StreamSieve
4. Send multi-turn (resume with parent_message_id) → conversation continues correctly
5. Verify no `<|begin▁of▁sentence|>` in any logged prompt
6. Verify request body has no `action`/`preempt`/`max_tokens`/`temperature`/`top_p` fields
