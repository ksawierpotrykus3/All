"""Input parser for DeepSeek proxy — validates and cleans messages, routes models."""

from __future__ import annotations



import re


class ParsedRequest:
    messages: list[dict]
    tools: list[dict]
    is_resume: bool = False
    is_vision: bool = False
    model_type: str = "default"
    chat_id: str | None = None
    stream: bool = True
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    tool_choice: str | dict | None = None
    parallel_tool_calls: bool = False
    thinking_enabled: bool = True
    search_enabled: bool = False

    def __init__(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


# Patterns that appear in volatile blocks — STABLE content preserved, VOLATILE stripped
_SYS_TAG_START_RE = re.compile(r"(^|\n)\s*<system-reminder>")

# Pattern to detect if tools schema is already embedded in system prompt
_TOOL_IN_SYSTEM_RE = re.compile(r"<tool_call|Available Tools:|function_name|tool_choice", re.IGNORECASE)

_MODEL_TYPE_MAP = {
    "deepseek-v4-pro": "expert",
    "deepseek-ai/deepseek-v4-pro": "expert",
    "deepseek-v4-flash": "default",
    "deepseek-ai/deepseek-v4-flash": "default",
    "deepseek-chat": "default",
    "deepseek-reasoner": "expert",
    "deepseek-vision": "default",
}

# Subagent routing rules: (pattern, override_model_type, thinking_enabled, search_enabled)
# When a system prompt matches one of these patterns, the request is routed to
# the specified model_type with the given thinking/search flags.
# Extend this list to add more subagent types.
_SUBAGENT_ROUTING: list[tuple[re.Pattern, str, bool, bool]] = [
    # Subagenty (search, coding) → flash with thinking + web search
    (re.compile(r"You are a file search specialist", re.IGNORECASE),
     "default", True, True),
    (re.compile(r"You are a \w+ search specialist", re.IGNORECASE),
     "default", True, True),
    (re.compile(r"You are a sub-agent in the Trae IDE executing a coding task", re.IGNORECASE),
     "default", True, True),
    # Generic/simple tasks → flash without search
    # Title generation, naming, short descriptions
    (re.compile(r"Generate a short.*descriptive name", re.IGNORECASE),
     "default", False, False),
    (re.compile(r"chat title|title case|2-6 words", re.IGNORECASE),
     "default", False, False),
    # Git commit message generation → flash without thinking/search (fast + simple)
    (re.compile(r"(Write|Generate).*commit message", re.IGNORECASE),
     "default", False, False),
    (re.compile(r"concise.*commit.*provided diff", re.IGNORECASE),
     "default", False, False),
]


class InputParser:
    @staticmethod
    def parse(raw: dict, state: dict | None = None) -> ParsedRequest:
        messages = list(raw.get("messages", []))
        tools = raw.get("tools")
        model = raw.get("model", "deepseek-v4-pro")

        # Detect if tools are already in system prompt
        has_tools = False
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content", "")
                if isinstance(content, str) and _TOOL_IN_SYSTEM_RE.search(content):
                    has_tools = True
                    break

        # Filter: keep last system-reminder, remove archived ones
        def _has_sys_reminder(msg: dict) -> bool:
            c = msg.get("content", "")
            if isinstance(c, str):
                return bool(_SYS_TAG_START_RE.search(c))
            if isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "text":
                        if _SYS_TAG_START_RE.search(part.get("text", "")):
                            return True
                    elif isinstance(part, str) and _SYS_TAG_START_RE.search(part):
                        return True
            return False

        seen_reminders = []
        cleaned = []
        for m in messages:
            if _has_sys_reminder(m):
                seen_reminders.append(m)
                continue
            cleaned.append(m)
        if seen_reminders:
            cleaned += seen_reminders[-1:]

        # Determine resume
        is_resume = state is not None and state.get("parent_id") is not None

        # Determine model_type, thinking_enabled, search_enabled
        # Priority: resume state > message detection > raw model map
        if state:
            # Resume: trust stored routing from previous turn
            model_type = state.get("model_type", _MODEL_TYPE_MAP.get(model, "default"))
            thinking_enabled = state.get("thinking_enabled")
            search_enabled = state.get("search_enabled")
            # Defensive: never pass None to DeepSeek API
            if model_type is None:
                model_type = _MODEL_TYPE_MAP.get(model, "default")
            if thinking_enabled is None:
                thinking_enabled = True
            if search_enabled is None:
                search_enabled = False
        else:
            # New session: respect user's model choice, but force flash for genuine subagents
            model_type = _MODEL_TYPE_MAP.get(model, "default")
            
            # Flash (default) ALWAYS gets thinking + search by default
            # Expert gets thinking only (no search)
            if model_type == "default":
                thinking_enabled = True
                search_enabled = True
            else:  # expert, vision
                thinking_enabled = True
                search_enabled = False
            
            # Check for subagent patterns — if matched, override model/flags
            for m in messages:
                if m.get("role") == "system":
                    content = m.get("content", "")
                    if isinstance(content, str):
                        for pattern, new_mt, t_ena, s_ena in _SUBAGENT_ROUTING:
                            if pattern.search(content):
                                model_type = new_mt
                                thinking_enabled = t_ena
                                search_enabled = s_ena
                                break
                    break  # only check first system message
        # Diagnostic: log model routing decision
        sys_prompt_preview = ""
        for m in messages:
            if m.get("role") == "system":
                c = m.get("content", "")
                if isinstance(c, str):
                    sys_prompt_preview = c[:120]
                break
        print(f"[ROUTE] model={model!r} model_type={model_type!r} "
              f"resume={is_resume} sys_prompt={sys_prompt_preview!r}", flush=True)

        return ParsedRequest(
            messages=cleaned,
            tools=tools,
            has_tools_in_system_prompt=has_tools,
            is_resume=is_resume,
            is_vision=model == "deepseek-vision",
            model_type=model_type,
            thinking_enabled=thinking_enabled,
            search_enabled=search_enabled,
            stream=raw.get("stream", True),
            max_tokens=max(16384, raw.get("max_completion_tokens") or raw.get("max_tokens", 65536)),
            temperature=raw.get("temperature", 1.0),
            top_p=raw.get("top_p", 1.0),
            reasoning_effort=raw.get("reasoning_effort"),
            tool_choice=raw.get("tool_choice"),
            parallel_tool_calls=raw.get("parallel_tool_calls", False),
        )


