# Align stealth with deepseek-free-api (Fly143) approach

**Date**: 2026-07-13
**Status**: Design approved, pending implementation
**Supersedes**: `2026-07-13-stealth-improvements-design.md`, `2026-07-13-prompt-stealth-half-width.md`

## Problem

DeepSeek blocks the proxy account for ~24h, detecting machine-generated prompts.
Root cause found during systematic debugging: the proxy's HTTP requests are easily
distinguishable from real browser traffic.

## Key discovery from reference implementation

[Fly143/deepseek-free-api](https://github.com/Fly143/deepseek-free-api) works reliably
without any stealth module. Its approach is simpler than ours:

| Aspect | Fly143 (working) | Our proxy (blocked) |
|--------|------------------|---------------------|
| Headers | Minimal DS_HEADERS dict | Custom x-app-version, x-client-locale added |
| User-Agent | Chrome/134.0.0.0 | Chrome/149.0.0.0 |
| x-client-version | 2.0.2 | 2.0.0 |
| Prompt format | DSML (`<|System|>`, `<|User|>`) | Stealth (`[System]:`, `[User]:`) |
| Stealth module | **None** | FingerprintCookies + BrowserTelemetry |
| Agentic instructions | **None** | `_get_agentic_instruction()` + emulated params |
| Impersonate | chrome134 (matches UA) | chrome120 (does NOT match UA) |

## Design: Approach A — Full alignment with Fly143

### 1. HTTP Headers

Simplify `_headers()` in `deepseek_client.py` to match Fly143's DS_HEADERS:

```python
# Current
"user-agent": "Chrome/149.0.0.0",
"x-app-version": "2.0.0",
"x-client-locale": "en_US",
"x-client-version": "2.0.0",

# Target
"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
"x-client-version": "2.0.2",
# Remove: x-app-version, x-client-locale
```

All `impersonate` calls: `"chrome120"` → `"chrome134"`.

### 2. Prompt Format — DSML

Replace stealth format (`[System]:`, `[User]:`, `[Assistant]:`) with DSML tokens:

```
<|begin_of_sentence|><|System|>system content<|end_of_instructions|>
<|User|>user message
<|Assistant|>assistant response<|end_of_sentence|>
<|User|>next message
<|Assistant|>
```

Changes:
- Delete `prompt_service.py` — all stealth formatting removed
- Delete `_get_agentic_instruction()` — not needed
- Delete `_build_emulated_params_instructions()` — not needed
- Update `dsml_prompt.py` as the sole prompt builder (remove `DeprecationWarning`)
- Tool definitions appended to system prompt (Fly143 pattern), not as separate block
- Tool results truncated to 500 chars (Fly143 pattern)
- Image compression notices removed from prompt

### 3. Stealth Module — Removed

Delete `stealth.py` entirely. Remove all references in `deepseek_client.py`:
- No `FingerprintCookies`
- No `BrowserTelemetry`
- No `augment_headers()`
- No `merge_cookies()`

## Files affected

| File | Action |
|------|--------|
| `server/core/deepseek_client.py` | Modify: headers, impersonate, remove stealth integration |
| `server/core/stealth.py` | **Delete** |
| `server/services/prompt_service.py` | **Delete** |
| `server/services/dsml_prompt.py` | Update: remove DeprecationWarning, refine DSML tokens, add tool truncation |
| `server/core/proxy.py` | Modify: update imports, use dsml_prompt instead of prompt_service |
| `server/config.py` | Optionally remove unused constants |
| `server/__init__.py` | Update imports if needed |

## Migration notes

1. Tool call XML format in `dsml_prompt.py` stays as-is (we use `<|TOOL|tool_calls>` which
   matches Fly143's approach)
2. `dsml_parser.py` stays as-is — it parses the same tool call XML coming back from model
3. Fly143 uses `build_dsml_tool_prompt()` for tool definitions — we should mirror that
   in `dsml_prompt.py`
4. Account pool / rate limiting / session management stays unchanged
