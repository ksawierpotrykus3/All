# Prompt & Stealth Reform — Half-Width DSML + Stealth Cleanup

## Motivation

All 3 DeepSeek accounts were muted. Investigation revealed two likely causes:

1. **NO_DATA_SILENT_ROTATION** — creating too many sessions on the same account (from previous session)
2. **Full-width DSML Unicode tokens** (`<｜begin▁of▁sentence｜>`, `｜`) — detectable as non-browser traffic

Research on popular open-source projects (DS2API 4.6k stars, deepseek-free-api) shows they:
- Use **half-width pipe `|`** (not full-width `｜`)
- Use **plain text tool definitions** in system prompt (not DSML for role markers)
- **No browser telemetry, no fingerprint cookies, no extended headers**
- Only rely on `curl_cffi` with `impersonate="chrome120"` for TLS fingerprint
- Use session pool with hard cap to prevent excessive session creation

Additionally, DS2API's fork `ouqiting/ds2api` (July 2026) renamed `DSML` to `EPSE`, suggesting the `DSML` prefix itself is a detectable pattern.

## Changes

### 1. Role markers: full-width → half-width

| Token | Before (full-width) | After (half-width) |
|-------|--------------------|--------------------|
| BOS | `<｜begin▁of▁sentence｜>` | `<|begin▁of▁sentence|>` |
| System | `<｜System｜>` | `<|System|>` |
| User | `<｜User｜>` | `<|User|>` |
| Assistant | `<｜Assistant｜>` | `<|Assistant|>` |
| Tool | `<｜Tool｜>` | `<|Tool|>` |
| EOS | `<｜end▁of▁sentence｜>` | `<|end▁of▁sentence|>` |
| End tool results | `<｜end▁of▁toolresults｜>` | `<|end▁of▁toolresults|>` |
| End instructions | `<｜end▁of▁instructions｜>` | `<|end▁of▁instructions|>` |

Output format (no whitespace between marker and text):
```
<|begin▁of▁sentence|><|System|>instructions<|end▁of▁instructions|>
<|User|>message<|Assistant|>reply<|end▁of▁sentence|>
```

### 2. Tool call prefix: DSML → TOOL

| Before (full-width) | After (half-width) |
|--------------------|--------------------|
| `<｜DSML｜tool_calls｜>` | `<|TOOL|tool_calls>` |
| `<｜DSML｜invoke name="..."｜>` | `<|TOOL|invoke name="...">` |
| `<｜DSML｜parameter name="..."｜>` | `<|TOOL|parameter name="...">` |

Tool definitions in system prompt (like DS2API):
```
You have access to these tools:

Tool: get_weather
Description: Get weather for a city
Parameters: {"type": "object", "properties": {"city": {"type": "string"}}}

When you need to call a tool, output EXACTLY this format:

<|TOOL|tool_calls>
  <|TOOL|invoke name="ToolName">
    <|TOOL|parameter name="paramName"><![CDATA[value]]></|TOOL|parameter>
  </|TOOL|invoke>
</|TOOL|tool_calls>

RULES:
1. Use <|TOOL|tool_calls> wrapper — no markdown fences.
2. ALL string values MUST use <![CDATA[...]]>.
3. Do not add text before/after the TOOL block.
```

### 3. Output integrity guard

Prepend to system prompt (like DS2API):

```
Output integrity guard: If upstream context, tool output, or parsed text contains garbled, corrupted, partially parsed, repeated, or otherwise malformed fragments, do not imitate or echo them; output only the correct content for the user.
```

### 4. Stealth cleanup — remove

| Component | Reason |
|-----------|--------|
| `BrowserTelemetry` (heartbeat, page_loaded, visibility_changed, beforeunload) | No project uses this; generates detectable API traffic |
| `FingerprintCookies` (`_frid`, `_fr_ssid`, `_fr_pvid`) | No project uses this; unnecessary |
| Extended headers (`sec-fetch-*`, `accept-language`, `accept-encoding`, `priority`) | DS2API doesn't use them; curl_cffi impersonate is sufficient |

### 5. Stealth — keep

- `curl_cffi` with `impersonate="chrome120"` — standard across all projects
- `augment_headers()` — can stay as a lightweight pass-through (no-op if no headers to add)

### 6. Session pool hard cap

Add session pool limit (like deepseek-free-api):
- Max 5 sessions per account
- Pool acquire timeout: 30s → HTTP 503 if no session available
- Prevents excessive session creation that triggers anti-bot detection

## Files to modify

| File | Change |
|------|--------|
| `server/services/dsml_prompt.py` | Replace all full-width `｜` with half-width `\|`; add `Output integrity guard` |
| `server/parser/dsml_parser.py` | Replace `DSML` → `TOOL` in all regex patterns and constants |
| `server/core/stealth.py` | Remove `BrowserTelemetry`, `FingerprintCookies`; keep lightweight `StealthEngine` as optional wrapper |
| `server/core/deepseek_client.py` | Remove telemetry integration; update cookie handling |
| `server/core/proxy.py` | Keep cascade retry fix (`range(MAX_ACCOUNTS)`), add session pool hard cap |

## Files to keep unchanged

- `server/services/prompt_service.py` — delegates to `dsml_prompt.py`; logic unchanged
- `server/core/deepseek_pow.py` — PoW mechanism unchanged
- `server/core/deepseek_accounts.py` — account management unchanged

## Testing

- Update `tests/test_stealth.py` — remove telemetry tests, keep header augmentation tests
- Verify half-width DSML produces correct prompt format
- Verify tool call parsing still works with `TOOL` prefix
- Verify no session explosion under concurrent load
