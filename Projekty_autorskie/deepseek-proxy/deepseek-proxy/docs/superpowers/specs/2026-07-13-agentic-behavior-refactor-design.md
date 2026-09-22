# Agentic Behavior Refactor — Zero-Tech-Debt Cleanup

**Date:** 2026-07-13
**Status:** Design (approved)
**Scope:** Single implementation plan — all fixes in one pass (Approach C)

## 1. Problem Summary

Audit identified **13 issues** preventing the DeepSeek proxy from operating in a
fully agentic manner. Key categories:

- **Prompt Engineering (B1, B5):** No agentic instruction in system prompt;
  `tool_choice="none"` does not block tool calls effectively.
- **Context Integrity (B2, B4, B6, B7, B9):** Aggressive truncation drops context,
  watermark in content confuses the model, text is lost before tool_calls,
  tool results lack attribution, no validation of tool call names.
- **Technical Debt (B3, B10, B11, B12, B13):** Dual prompt formats, mixed
  `parent_message_id` types, synchronous state saving in async generator,
  no drain timeout, duplicated constants.
- **Image Quality (B8):** JPEG compression at 75% loses detail for OCR/analysis.

### Priority Classification

| Priority | Issues | Impact |
|----------|--------|--------|
| P0 | B1, B5 | Model ignores instructions / calls wrong tools |
| P1 | B2, B4, B6, B9, B3 | Context loss, confusion, validation gaps |
| P2 | B7, B8, B10, B11, B12, B13 | Quality, maintainability, performance |

## 2. Architecture — Target State

```
server/
├── main.py                    # entry point (unchanged)
├── config.py                  # SINGLE source of truth for all constants
├── __init__.py                # simplified: from server.main import app
├── core/
│   ├── deepseek_client.py     # V0 API client (parent_message_id unified)
│   ├── models.py              # ChatRequest + new fields
│   └── proxy.py               # ProxyService (validation layer added)
├── services/
│   ├── prompt_service.py      # SINGLE prompt builder (stealth format, agentic instruction)
│   ├── state_service.py       # imports constants from config.py
│   ├── stream_service.py      # text-loss fix, drain timeout, watermark refactor
│   ├── dsml_prompt.py         # DEPRECATED — kept for reference only
│   ├── account_service.py     # unchanged
│   └── auth_service.py        # unchanged
├── parser/
│   ├── dsml_sieve.py          # unchanged
│   ├── dsml_parser.py         # unchanged
│   └── ... (rest unchanged)
└── utils/
    └── helpers.py             # unchanged (imports from config.py)
```

**Files to delete:** `_server_legacy.py`
**Files to create:** none (all changes are modifications)
**Files to deprecate:** `dsml_prompt.py` (add deprecation warning)

## 3. Prompt Builder — `prompt_service.py`

### 3.1 Agentic Instruction Block

Add to `_build_prompt_sync()`, appended to `combined_system`:

```
You are an AI agent. You MUST:
1. Carefully read and follow ALL user instructions exactly as written.
2. Use available tools when needed to complete the user's request.
3. If a user asks you to do something step by step, do exactly that.
4. Do NOT skip, rephrase, or ignore any part of the user's message.
5. If you cannot comply, explain why.
```

### 3.2 No System Message Mutation

**Before:** `system[0]["content"] += tool_block` — appends tool definitions to
the original system message dict on every request. On resume, system message
grows exponentially.

**After:** Extract original system content, build `combined_system` as a fresh
string, never mutate the input messages:

```python
def _build_prompt_sync(messages, tools=None, tool_choice=None, ...):
    # Extract original system content (read-only)
    system_parts = [m for m in messages if m.get("role") == "system"]
    system_content = "\n\n".join(m.get("content", "") for m in system_parts)

    # Build tool block separately
    tool_block = _format_tool_block(tools) if tools else ""

    # Combine WITHOUT mutating original messages
    combined_system = system_content
    if tool_block:
        combined_system = system_content.strip() + "\n\n" + tool_block if system_content.strip() else tool_block

    # Append agentic instruction
    combined_system += _get_agentic_instruction()

    # Format with stealth markers (the ONLY format sent to DeepSeek API)
    # [System]\n{combined_system}\n\n[User]\n...\n\n[Assistant]\n
```

### 3.3 Tool Choice Enforcement

| `tool_choice` value | Behavior |
|---|---|
| `"auto"` | Default — model may call tools |
| `"required"` | Append `"You MUST use one of the available tools."` to tool_block |
| `"none"` | tools set to None, no tool definitions sent; add `"Do NOT use any tools. Respond directly."` |
| `{"function": {"name": "X"}}` | Filter tools list to only include X |

### 3.4 Tool Result Attribution

Change format from generic `[Tool: {id}]` to descriptive:

```
[Tool Result: {name} (call_id: {id})]
\n{content}
```

This lets the model associate results with specific tool invocations.

### 3.5 Context Trimming Rules

1. **Never drop system messages** — always preserve all `[System]` blocks
2. **Never drop the last user message** — it carries the current instruction
3. **Message history limit:** 20 → **40** messages (more context for agents)
4. **Tool result truncation:** 8000 → **50000** characters
5. **Oldest non-system, non-last messages** dropped first when over `MAX_PROMPT_LEN`
6. **Last resort** (over 150k chars): keep last 15 messages

## 4. Stream Service — `stream_service.py`

### 4.1 Fix Text Loss Before Tool Calls

**Before:** `yield_buffer` is flushed only when `len(text_buffer) >= 50`.

**After:** Flush yield_buffer **immediately** when a `tool_calls` event arrives,
regardless of buffer size. Also flush on any non-empty `text` event.

```python
if yield_buffer and event.type in ("tool_calls", "text"):
    yield _chunk({"content": yield_buffer})
    yield_buffer = ""
```

### 4.2 Drain Timeout

Add 30-second timeout to the tool_calls drain loop:

```python
_drain_start = time.time()
_DRAIN_TIMEOUT = 30.0
for remaining_chunk in stream_gen:
    if time.time() - _drain_start > _DRAIN_TIMEOUT:
        print(f"[DRAIN TIMEOUT] exceeded {_DRAIN_TIMEOUT}s", flush=True)
        break
    ...
```

### 4.3 Tool Call Name Validation

Before yielding tool_calls to the proxy, verify each tool name exists in the
available tools list. Log and skip unknown tool calls.

```python
valid_tool_names = {t.get("function", t).get("name", "") for t in (tools or [])}
found_calls = [tc for tc in found_calls if tc.get("name", "") in valid_tool_names or "function" in tc]
```

### 4.4 Watermark Refactoring

**Before:** `yield _chunk({"content": f"\n\n<!-- PROXY_SID:{conv_uuid} -->"})`
— watermark is embedded in response content, visible to the model.

**After:** Use custom `finish_reason` to carry the session ID:

```python
yield _chunk({"content": response_text}, fr="stop", sid=conv_uuid)
```

Session resume reads SID from the last chunk's metadata, not from content text.
Existing watermarks in stored conversations are still parsed for backwards
compatibility (the regex-based `_extract_watermark` stays).

## 5. State and Constants Cleanup

### 5.1 Single Source — `server/config.py`

All constants move to `config.py`. Other files import from there.

**Additions to `config.py`:**
```python
WM_PATTERN = re.compile(r'<!--\s*PROXY_SID:\s*([a-f0-9\-]{12})\s*-->')
DEDUP_TTL = 60.0
MAX_SESSIONS_PER_ACCOUNT = 5
```

**Removals from other files:**
- `state_service.py`: remove local `WM_PATTERN`, `_DEDUP_TTL`, `_CONV_STATE_TTL` — import from config
- `deepseek_client.py`: remove `MAX_ACCOUNTS`, `MAX_PARALLEL_TOOL_CALLS` — import from config
- `proxy.py`: remove local `_MAX_SESSIONS_PER_ACCOUNT` — import from config

### 5.2 Asynchronous State Saving

Replace `_save_conv_state_sync()` in the streaming generator with async
`state.save_conv_state()`. For synchronous generator sections, use
`asyncio.get_event_loop().run_in_executor()` to avoid blocking.

### 5.3 `parent_message_id` Type Unification

Change type from `int | str | None` to `int | None` across all modules.
DeepSeek V0 API always returns integer IDs. Convert at parse boundary.

### 5.4 File Cleanup

- **`_server_legacy.py`** — delete (all symbols already migrated to proper modules)
- **`dsml_prompt.py`** — add `# DEPRECATED — use prompt_service.py instead` header
  with `warnings.warn("...", DeprecationWarning)` on import
- **`server/__init__.py`** — simplify to `from server.main import app`

## 6. Input Validation

Added in `proxy.py` before prompt building:

```python
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

def _validate_params(temperature, top_p, max_tokens) -> None:
    if temperature is not None and not (0 <= temperature <= 2):
        raise HTTPException(400, "temperature must be in [0, 2]")
    if top_p is not None and not (0 <= top_p <= 1):
        raise HTTPException(400, "top_p must be in [0, 1]")
    if max_tokens is not None and max_tokens < 1:
        raise HTTPException(400, "max_tokens must be >= 1")
```

## 7. Image Quality

In `helpers.py`, change JPEG quality from 75 to **90** for better OCR/analysis
results. If original size is a concern, add a note that format can be changed
to PNG when text fidelity is critical.

## 8. Error Handling — Global Middleware

```python
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

## 9. Tests

### 9.1 New Files / Extensions

- **`tests/test_agent_integration.py`** — add multi-step instruction test,
  tool_choice="none" test, context preservation test
- **`tests/test_stream_service_flow.py`** — add text-loss-before-tool-calls
  regression test, drain timeout test, unknown tool name rejection test

### 9.2 Key Test Cases

1. **Agentic prompt contains all instructions** — verify `_build_prompt_sync`
   output includes "You are an AI agent" + all 5 rules
2. **Tool choice "none" injects "Do NOT use any tools"** — verify prompt text
3. **No text loss before tool_calls** — simulate tool_calls with <50 chars text,
   verify all text is yielded
4. **Unknown tool names rejected** — stream service filters out nonexistent tools
5. **Watermark not in content** — verify `<!-- PROXY_SID:... -->` does not appear
   in response text chunks
6. **Context preserved after truncation** — send 50 messages, verify the last
   user message and system message are always present

## 10. Implementation Order

| Step | File(s) | Description | Risk |
|------|---------|-------------|------|
| 1 | `config.py`, various | Consolidate constants, single source of truth | Low |
| 2 | `proxy.py` | Add `_validate_messages`, `_validate_tools`, `_validate_params` | Low |
| 3 | `prompt_service.py` | Add agentic instruction, tool_choice enforcement, tool result attribution | Medium |
| 4 | `stream_service.py` | Fix text loss, add drain timeout, tool call validation, watermark refactor | Medium |
| 5 | `state_service.py` | Import constants from config, async save | Low |
| 6 | `deepseek_client.py` | Unify `parent_message_id` to `int \| None` | Low |
| 7 | `helpers.py` | Bump JPEG quality to 90 | Low |
| 8 | `dsml_prompt.py` | Add deprecation warning | Low |
| 9 | `_server_legacy.py` | Delete file | Low |
| 10 | `server/__init__.py` | Simplify import | Low |
| 11 | `main.py` | Add global error handler middleware | Low |
| 12 | `tests/` | New + extended tests | Medium |
| 13 | Full verification | Run all tests, manual smoke test | High |

## 11. Success Criteria

After implementing all changes:

1. Model follows multi-step instructions without skipping steps
2. Model respects `tool_choice="none"` — never calls tools when disabled
3. No text is lost between model response text and tool_calls
4. Unknown tool names are rejected gracefully
5. Watermark `PROXY_SID` does not appear in model-visible content
6. All constants defined in exactly one place (`config.py`)
7. `_server_legacy.py` removed, `dsml_prompt.py` deprecated
8. All tests pass, including new agent behavior regression tests
