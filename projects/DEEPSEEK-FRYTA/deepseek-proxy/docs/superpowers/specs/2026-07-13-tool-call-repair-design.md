# 3-Tier Tool Call Repair Pipeline — Design Spec

**Date:** 2026-07-13
**Project:** deepseek-proxy (DeepSeek V4 Pro Web Chat API proxy)
**Status:** Approved design, pending implementation

---

## Problem

DeepSeek V4 Pro accessed via `chat.deepseek.com` web chat API frequently produces malformed DSML/XML tool call blocks. The existing `StreamSieve` + `DSML Parser` silently drops unparseable blocks, causing the model to degrade to chatbot behavior — tool calls are lost, and the agent loop breaks.

The web chat anti-bot system also restricts usage of proper DSML tokens (`<|System|>`, etc.), so we must keep the stealth prompt format (`[System]`, `[User]`, `[Assistant]`) and fix tool calls at the **output parsing layer** instead.

## Solution Overview

A 3-tier repair pipeline inserted between `StreamSieve` and tool call emission. When the DSML parser fails to extract tool calls from a detected DSML block, the pipeline attempts increasingly aggressive repair strategies before falling back to treating the block as plain text.

```
StreamSieve detects DSML block
  → DSML Parser tries to parse
  → SUCCESS → emit tool_calls event (no change)
  → FAILURE → TIER 1: Text-level XML/DSML repair
    → SUCCESS → re-parse → emit
    → FAILURE → TIER 2: JSON-level argument repair
      → SUCCESS → re-parse → emit
      → FAILURE → TIER 3: Model self-repair fallback (optional)
        → emit buffered text (tool call lost, but gracefully)
```

## Architecture

### New module: `server/repair/`

```
server/repair/
  __init__.py
  repair_tier1.py      — Text-level DSML/XML repair
  repair_tier2.py      — JSON-level argument repair
  repair_pipeline.py   — Orchestrator: tier1 → tier2 → (optional) tier3
```

### Modified modules

- `server/parser/dsml_sieve.py` — `_try_finish_capture()` calls repair pipeline when `parse_dsml_tool_calls()` returns empty
- `server/services/stream_service.py` — (Tier 3 only) provides a callback to the DeepSeek client for model self-repair

### Pipeline orchestrator interface (`repair_pipeline.py`)

```python
def repair_pipeline(
    capture_buf: str,
    tool_names: list[str],
    tier3_callback: Optional[Callable[[str], str]] = None,
) -> str | None:
    """Run tier1 → tier2 repair sequentially.
    
    Args:
        capture_buf: Raw capture buffer containing unparseable DSML block.
        tool_names: Known tool names for name resolution.
        tier3_callback: Optional callback for model self-repair (Tier 3).
            Signature: (malformed_text) → repaired_text or empty string.
    
    Returns:
        Repaired text if any tier succeeded, None if all tiers failed.
    """
    # 1. Run tier1 text repair
    # 2. If tier1 succeeded, re-parse; if tool calls found, return
    # 3. Run tier2 JSON repair on remaining arguments
    # 4. If tier2 succeeded, re-parse; if tool calls found, return
    # 5. (optional) Run tier3 callback
    # 6. Return None
```

---



## Tier 1 — Text-Level DSML/XML Repair (`repair_tier1.py`)

Migrate and extend existing functions from `tool_parser.py`:

### Existing code to migrate
- `_fix_missing_lt()` — prepend `<` to DSML tags that lost their opening bracket
- `_auto_close_tags()` — close unclosed XML tags in reverse order

### New repair strategies

1. **Strip markdown fences**: Remove ` ```xml`, ` ```dsml`, ` ``` ` blocks wrapping tool calls
2. **Fix unclosed CDATA**: Append `]]>` if `![CDATA[` is unclosed
3. **Fix broken namespace prefixes**: `|DSL|` → `|DSML|`, `|TOOL|toolcal` → `|TOOL|tool_calls`, etc.
4. **Fix mismatched quotes**: `name='foo"` → normalize to consistent quotes
5. **Strip trailing garbage**: Remove non-tag content after closing `</|TOOL|tool_calls>`
6. **Fix truncated tags**: If buffer ends with partial tag, close it gracefully
7. **Strip leading/trailing text**: Remove human-readable prose before/after the tool block

### Interface

```python
def repair_tier1(text: str) -> str | None:
    """Attempt text-level repair. Returns repaired text or None if irreparable."""
```

---

## Tier 2 — JSON Argument Repair (`repair_tier2.py`)

Tool call arguments embedded in `<parameter>` tags are frequently malformed JSON. Repair strategies:

1. **Unescape backslashes**: `"path\to\file"` → `"path\\to\\file"` (smart escape — only fix invalid escape sequences)
2. **Strip trailing commas**: `{"a":1,"b":2,}` → `{"a":1,"b":2}`
3. **Normalize single quotes**: `{'key': 'val'}` → `{"key": "val"}`
4. **Fix bare string parameters**: If argument should be `{"command": "ls"}` but model outputs just `ls`, wrap in expected schema
5. **Fix XML-encoded JSON**: `"{""key"": ""val""}"` (double-encoded in XML) → decode outer layer
6. **Lenient JSON parsing**: Use `json.loads()` with pre-processing regexes, fall back to `ast.literal_eval()` for Python-literals, fall back to manual extraction

### Interface

```python
def repair_tier2(tool_name: str, args_text: str) -> str | None:
    """Attempt JSON-level repair on arguments. Returns fixed JSON string or None."""
```

---

## Tier 3 — Model Self-Repair Fallback (Optional)

When both tier 1 and 2 fail, inject a follow-up message to the DeepSeek session asking the model to re-output the tool call in correct format.

### Mechanism

1. Buffer the last user message context
2. When a DSML block is detected but unparseable after tier 1+2:
   - Append a conversational message: *"I notice the formatting of your last tool call didn't come through correctly. Could you please output it again using the proper format?"*
   - Re-send to the existing DeepSeek session (non-streaming, one-shot)
   - Parse the response for tool calls
   - Emit the corrected tool calls if found

### Constraints

- Requires access to `DeepSeekClient` from `stream_service.py`
- Only fires once per conversation turn (prevent infinite loops)
- Must use stealth/conversational framing to avoid anti-bot detection
- Implementation deferred if complexity is too high — Tier 1+2 handle 90%+ of cases

---

## Integration Points

### `dsml_sieve.py` changes

In `_try_finish_capture()`:

```python
def _try_finish_capture(self) -> Optional[Tuple[str, Any, str]]:
    if not self._capture_buf:
        return None
    if not self._is_capture_complete():
        return None
    
    tool_calls, cleaned = parse_dsml_tool_calls(self._capture_buf, self.tool_names)
    if tool_calls:
        leftover = self._extract_post_wrapper(self._capture_buf)
        return ("", tool_calls, leftover)
    
    # --- NEW: Repair pipeline ---
    repaired = repair_pipeline(self._capture_buf, self.tool_names)
    if repaired:
        tool_calls, cleaned = parse_dsml_tool_calls(repaired, self.tool_names)
        if tool_calls:
            leftover = self._extract_post_wrapper(self._capture_buf)
            return ("", tool_calls, leftover)
    # --- END NEW ---
    
    return (self._capture_buf, None, "")
```

### `StreamSieve.__init__` changes

Add optional `repair_callback` parameter for Tier 3 fallback.

---

## Error Handling

- Each tier is independent: tier 2 runs even if tier 1 returns `None`
- All tiers are idempotent: running the same text through repair twice produces the same result
- Logging at each tier level: `[REPAIR] tier1: fixed missing CDATA closure`
- Metrics: count repairs per tier, track success rate

## Testing Strategy

1. **Unit tests**: Pre-collected corpus of real-world malformed tool call examples
2. **Integration test**: Simulate streaming chunks with known-bad DSML, verify tool calls are extracted
3. **E2E**: Run against actual DeepSeek web chat, compare tool call extraction rate before/after

## Out of Scope

- Changes to prompt format (`[System]` → DSML) — causes account bans
- Modifications to the deepseek_client.py authentication/session layer
- Changes to how Trae IDE sends its system prompt
