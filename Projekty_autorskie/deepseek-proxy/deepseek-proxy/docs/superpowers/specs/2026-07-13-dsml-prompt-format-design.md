# DSML Prompt Format Design

**Date:** 2026-07-13
**Project:** deepseek-proxy
**Status:** Approved design — ready for implementation planning

## Overview

Replace the current custom flat-text prompt format with the **DSML (DeepSeek Model Language)** format used by the reference implementation [Fly143/deepseek-free-api](https://github.com/Fly143/deepseek-free-api). This fixes tool call detection and execution by using the native token format DeepSeek V4 Pro was trained on.

## Prompt Format

### Message tokens (ds2api style)

| Token | Usage |
|-------|-------|
| `<｜begin▁of▁sentence｜>` | Beginning of sequence |
| `<｜System｜>` | System message prefix |
| `<｜end▁of▁instructions｜>` | End of system instructions |
| `<｜User｜>` | User message prefix |
| `<｜Assistant｜>` | Assistant message prefix |
| `<｜end▁of▁sentence｜>` | End of assistant response |
| `<｜Tool｜>` | Tool result prefix |
| `<｜end▁of▁toolresults｜>` | End of tool results |

### Full prompt structure

```
<｜begin▁of▁sentence｜><｜System｜>{system_content}
{DSML tool definitions}
<｜end▁of▁instructions｜>
<｜User｜>{user_message}
<｜Assistant｜>{assistant_response}<｜end▁of▁sentence｜>
<｜Tool｜>{tool_result}<｜end▁of▁toolresults｜>
<｜User｜>{next_user_message}
```

- No `<｜begin▁of▁sentence｜>` before non-system messages
- Tool results use `<｜Tool｜>` prefix and `<｜end▁of▁toolresults｜>` suffix
- Assistant messages end with `<｜end▁of▁sentence｜>`
- System block ends with `<｜end▁of▁instructions｜>`
- Tool definitions are embedded inside the system block (before `｜end▁of▁instructions｜`)

## Tool Call Format (DSML with CDATA)

### Tool definitions in system prompt

```xml
<|DSML|tool_calls>
  <|DSML|invoke name="Read">
    <|DSML|parameter name="file_path"><![CDATA[string - Path to the file to read]]></|DSML|parameter>
  </|DSML|invoke>
</|DSML|tool_calls>
```

Each tool gets its own `<|DSML|tool_calls>` block.

### Tool call response (model output)

```xml
<|DSML|tool_calls>
  <|DSML|invoke name="Read">
    <|DSML|parameter name="file_path"><![CDATA[/path/to/file.txt]]></|DSML|parameter>
  </|DSML|invoke>
</|DSML|tool_calls>
```

Rules embedded in system prompt:
- No markdown fences around tool calls
- No extra text before/after the DSML block when calling a tool
- All string values use `<![CDATA[...]]>`
- Parameters match the tool schema exactly

### History reconstruction for tool calls

When the model called a tool in a previous turn, the conversation history stores:

```
<｜Assistant｜>
Some assistant text
<|DSML|tool_calls>
  <|DSML|invoke name="Read">
    <|DSML|parameter name="file_path"><![CDATA[/path/to/file.txt]]></|DSML|parameter>
  </|DSML|invoke>
</|DSML|tool_calls>
<｜end▁of▁sentence｜>
<｜Tool｜>File contents here<｜end▁of▁toolresults｜>
```

## Stream Detection (StreamSieve)

### Behavior

1. Process streaming chunks character by character
2. Look for DSML/XML tool call opening tags: `<|DSML|tool_calls>`, `<tool_calls>`, `<tool_call>`, `<invoke `
3. Buffer everything from the opening tag
4. When closing tag `</|DSML|tool_calls>` is found, parse and emit tool call events
5. Emit safe text before/after tool calls as content events
6. At stream end, flush any remaining buffer

### Detection priority

1. `<|DSML|tool_calls>` — canonical format
2. `<tool_calls>`, `<tool_call>` — fallback (model may drop DSML prefix)
3. `<invoke `, `<|DSML|invoke ` — bare invoke (model may drop outer wrapper)
4. Generic DSML prefix detection: any tag starting with `<|DSML|`, `|DSML|`, etc.

### Safe text split

When a `<` or `|` could be the start of a tool tag, hold that character back until the next chunk confirms or denies it. This prevents emitting partial tags as text.

## DSML Parser

### Input/output

- **Input:** Raw DSML/XML text block containing `<|DSML|tool_calls>` ... `</|DSML|tool_calls>`
- **Output:** `list[dict]` with standardized OpenAI-compatible structure: `[{"name": "...", "arguments": "{...}"}]`

### Processing steps

1. Strip DSML markup normalization (`strip_dsml_markup`) — handles noise tolerance, fence skipping
2. Find `<tool_calls>` or `<tool_call>` wrapper blocks
3. Extract `<invoke name="...">...</invoke>` entries
4. Parse `<parameter name="..."><![CDATA[...]]></parameter>` into key-value pairs
5. Auto-type values (int, float, bool, null, string) with CDATA fallback
6. Format as OpenAI-compatible tool call dicts

### CDATA handling

- Extract content between `<![CDATA[` and `]]>`
- Support nested `]]]]><![CDATA[>` escaping (CDATA termination inside content)
- Fallback to raw text parsing if CDATA is malformed
- HTML entity unescaping for XML entities (`&amp;`, `&lt;`, etc.)

## File Changes

### New files

| File | Purpose | Source |
|------|---------|--------|
| `server/parser/dsml_sieve.py` | StreamSieve — real-time DSML detection in streaming chunks | Adapted from Fly143 `tool_sieve.py` |
| `server/parser/dsml_parser.py` | DSML parser — parse tool calls from DSML/XML, format history | Adapted from Fly143 `tool_dsml.py` + `tool_call.py` |
| `server/services/dsml_prompt.py` | DSML prompt builder — construct flat text with DSML tokens | New, custom |

### Modified files

| File | Changes |
|------|---------|
| `server/services/prompt_service.py` | `build_prompt()` delegates to `dsml_prompt.build_dsml_prompt()`. Remove `_format_msgs`, `_build_prompt_sync`, `_inject_tools_as_system`. Keep `trim_context`, `cascade_compress_tool_results` |
| `server/services/stream_service.py` | Replace `StructuredResponseStreamParser` with `StreamSieve` + `dsml_parser.parse_dsml_tool_calls()`. Remove `_parse_tool_calls` import. Keep `_auto_close_tags` as fallback |

### Removed files (optional, can archive)

| File | Reason |
|------|--------|
| `server/parser/stream_parser.py` | Replaced by `dsml_sieve.py` |
| `server/parser/tool_parser.py` | Replaced by `dsml_parser.py` |

## Integration Points

### PromptService.build_prompt()

```python
async def build_prompt(self, messages, tools, tool_choice, images, max_history_len):
    return build_dsml_prompt(messages, tools, tool_choice)
```

### StreamService.generate()

```python
sieve = StreamSieve()
# In the loop:
events = sieve.feed(text_chunk)
for event in events:
    if event.type == "text": yield _chunk({"content": event.data})
    elif event.type == "tool_calls": # emit tool_calls SSE, save state, return

# After loop:
events = sieve.flush()
# Handle remaining text/tool calls
```

### ProxyService

No changes — the interface to `prompt.build_prompt()` and `stream.generate()` stays the same.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Malformed DSML (missing tags, broken XML) | StreamSieve falls back to emitting text as-is |
| Partial CDATA at chunk boundary | Buffer until `]]>` is found; if EOF, append `]]>` and parse |
| Empty tool call block (no `<invoke>` elements) | Ignore block, continue streaming |
| Unknown tool name | Pass through — will be handled by caller |
| StreamSieve false positive (text looks like DSML) | `_split_safe` holds partial match until next chunk confirms/denies |
| Model outputs mixed DSML + text | Text before tool calls emitted as content; tool calls parsed separately |

## Backward Compatibility

- `conv_state.json` — no changes needed (keys are UUIDs, not format-dependent)
- `tools_cache.json` — tools were cached by system hash; DSML format is different, so old cache will be ignored on first request after deploy (cache miss → rebuild)
- Client (Trae IDE) — no changes needed; OpenAI-compatible SSE output format is preserved
- Existing sessions — active DeepSeek sessions continue to work; new prompts use DSML format

## Testing

- Unit test for `dsml_parser.py`: parse DSML blocks, verify arguments, test CDATA edge cases
- Unit test for `dsml_sieve.py`: feed chunks character by character, verify event sequence
- Unit test for `dsml_prompt.py`: build prompts with/without tools, verify token structure
- Integration test: full streaming cycle with DSML tool call detection
