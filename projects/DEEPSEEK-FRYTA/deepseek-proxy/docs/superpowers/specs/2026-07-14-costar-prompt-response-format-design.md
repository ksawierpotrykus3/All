# CO-STAR Prompt & Clean Response Format Redesign

**Date:** 2026-07-14
**Status:** Draft
**Author:** AI Agent (via brainstorming)

## Problem Statement

The DeepSeek V4 Pro proxy uses DSML tokens (`<｜begin▁of▁sentence｜>`, `<｜User｜>`, `<｜Assistant｜>`, `<｜end▁of▁sentence｜>`) in prompts sent to DeepSeek and suspicious watermarking (`<!-- PROXY_SID: conv-uuid -->`) in responses returned to clients. This makes both the prompt format and response format look machine-generated and detectable.

## Goals

1. Replace DSML tokens with natural, human-readable CO-STAR XML tags
2. Replace DSML tool call syntax with JSON code blocks (` ```tool_call `)
3. Remove watermark from response content, move SID to SSE metadata only
4. Remove `call_sid:conv-uuid` from tool call IDs
5. Maintain full backward compatibility with OpenAI-compatible API
6. Keep ability to detect tool calls and maintain context across conversations

## Non-Goals

- Changing the OpenAI-compatible SSE protocol
- Removing context tracking / conversation resume capability
- Refactoring the account/auth system
- Changing the DeepSeek V0 API integration

## Design

### 1. Prompt Format: CO-STAR XML Tags

**File:** `server/services/dsml_prompt.py`

Replace DSML token constants with CO-STAR template:

```python
# OLD — DSML tokens
DSML_BOS = "<｜begin▁of▁sentence｜>"
DSML_SYS = "<｜System｜>"
DSML_USER = "<｜User｜>"
DSML_ASST = "<｜Assistant｜>"
DSML_TOOL = "<｜Tool｜>"
DSML_EOS = "<｜end▁of▁sentence｜>"

# NEW — CO-STAR XML tags (zwykłe ASCII)
SYSTEM_TAG = "system"
USER_TAG = "user"
ASSISTANT_TAG = "assistant"
TOOL_TAG = "tool_result"
CHAT_HISTORY_TAG = "chat_history"
USER_INPUT_TAG = "user_input"
TOOLS_TAG = "tools"
RULES_TAG = "rules"
```

New prompt structure:

```
<system>
[system prompt content]
</system>

<tools>
[OpenAI-compatible JSON tool schemas]
</tools>

<chat_history>
<user>
[previous user message]
</user>
<assistant>
[previous assistant response]
</assistant>
<tool_result name="tool_name">
[tool execution result]
</tool_result>
</chat_history>

<user_input>
[current user question]
</user_input>

<rules>
[instructions for tool calling format, output rules]
</rules>
```

### 2. Tool Calling: JSON Code Blocks

**Files:** `server/parser/dsml_sieve.py`, `server/parser/dsml_parser.py`

Model is instructed to call tools using JSON code blocks instead of DSML XML:

````
```tool_call
{
  "name": "get_weather",
  "arguments": {
    "location": "Warsaw"
  }
}
```
````

#### New parser: `parse_json_tool_calls()`

```python
JSON_TOOL_CALL_PATTERN = re.compile(
    r'```tool_call\s*\n(.*?)```',
    re.DOTALL
)

def parse_json_tool_calls(text: str) -> Tuple[List[Dict], str]:
    """Parse ```tool_call JSON blocks from model output.
    Returns (tool_calls, cleaned_text).
    """
    tool_calls = []
    cleaned = text
    for match in JSON_TOOL_CALL_PATTERN.finditer(text):
        block = match.group(1).strip()
        try:
            parsed = json.loads(block)
            name = parsed.get("name", "")
            args = parsed.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            if name:
                tool_calls.append({
                    "name": name,
                    "arguments": json.dumps(args, ensure_ascii=False)
                })
        except json.JSONDecodeError:
            continue
    # Remove tool call blocks from text
    cleaned = JSON_TOOL_CALL_PATTERN.sub("", cleaned).strip()
    return tool_calls, cleaned
```

#### StreamSieve changes

`StreamSieve` will detect both DSML markers (fallback) and ` ```tool_call ` markers:

- New `TOOL_CALL_START_MARKER = "```tool_call"`
- When detected in the pending buffer, switch to capture mode
- Complete when closing ` ``` ` is found
- Parse captured block with `parse_json_tool_calls()`

#### Tool definitions in `<tools>` tag

```python
def build_costar_tool_prompt(tools: list[dict]) -> str:
    """Build tools section using JSON schema format (OpenAI-compatible)."""
    if not tools:
        return ""
    tools_section = json.dumps(tools, indent=2, ensure_ascii=False)
    return f"<tools>\n{tools_section}\n</tools>"
```

#### Tool calling rules

```python
TOOL_CALLING_RULES = """<rules>
When answering the user's query, you may use the following tools. To use a tool, output a JSON code block with this exact format:

```tool_call
{
  "name": "ToolName",
  "arguments": {
    "param1": "value1"
  }
}
```

RULES:
1. Use ```tool_call code fences — this is required.
2. The "name" field must match a tool name from the <tools> section exactly.
3. "arguments" must be a valid JSON object.
4. Output ONLY the code block when calling a tool — no extra text.
5. You may call multiple tools in sequence by outputting multiple ```tool_call blocks.
6. If you have text to say alongside a tool call, say it first, then output the tool call block.
</rules>"""
```

### 3. Response Format: Clean Watermark

**Files:** `server/services/stream_service.py`, `server/utils/helpers.py`

#### Remove inline watermark

```python
# OLD — suspicious HTML comment in content
yield _chunk({"content": f"<!-- PROXY_SID: {conv_uuid} -->"})

# NEW — SID only in finish chunk metadata
yield _chunk({}, fr="stop", sid=conv_uuid)
```

SID remains in `conv_state` for context tracking and is returned:
- In the finish SSE chunk as `sid` field
- Never embedded in `content` delta

#### Clean tool call IDs

```python
# OLD — exposes conv-uuid
def _tc_id(conv_uuid: str) -> str:
    return f"call_sid:{conv_uuid}_{uuid.uuid4().hex[:8]}"

# NEW — short random ID, no proxy signature
def _tc_id() -> str:
    return f"call_{uuid.uuid4().hex[:8]}"
```

The conversation context is tracked via:
- `conv_uuid` in the generator closure
- State saved before yielding `[DONE]`
- Client sends conv-id in the next request's authentication header

### 4. Migration & Compatibility

**Phase 1 — Backward compatible:**
- New `_build_costar_prompt()` alongside existing `_format_stealth()` / `build_dsml_prompt()`
- StreamSieve detects both DSML and JSON tool call formats
- Config flag `prompt_format: "costar" | "dsml"` in `server/config.py`

**Phase 2 — Default to CO-STAR:**
- Set `prompt_format = "costar"` as default
- Keep DSML parsing as fallback for stream detection

**Phase 3 — Cleanup:**
- Remove DSML-specific code (optional, only if stable)

### 5. Files Changed

| File | Changes |
|------|---------|
| `server/services/dsml_prompt.py` | Add `_build_costar_prompt()`, new CO-STAR template. Existing functions kept for compatibility |
| `server/parser/dsml_parser.py` | Add `parse_json_tool_calls()`, `build_costar_tool_prompt()` |
| `server/parser/dsml_sieve.py` | Add JSON tool call detection in `StreamSieve.feed()`. Detect both DSML and JSON markers |
| `server/services/stream_service.py` | Remove inline watermark in text responses. Change `_tc_id()` signature |
| `server/services/prompt_service.py` | Wire CO-STAR prompt builder as new default |
| `server/config.py` | Add `PROMPT_FORMAT = "costar"` config flag |
| `server/utils/helpers.py` | No changes needed — `_chunk()` already supports `sid` field |

### 6. Testing

- Unit tests for `parse_json_tool_calls()` — valid JSON, malformed, multiple calls, text mixed with calls
- Unit tests for `StreamSieve` with JSON markers
- Integration test: streaming response with tool calls parsed from JSON
- Regression: ensure DSML parsing still works during transition
- Verify no `<!-- PROXY_SID -->` appears in any response content
- Verify tool call IDs no longer contain `call_sid:`
