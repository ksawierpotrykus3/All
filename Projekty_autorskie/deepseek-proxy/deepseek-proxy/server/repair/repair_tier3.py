from __future__ import annotations

import re
from typing import Optional


_TOOL_CALL_OPEN_RE = re.compile(
    r'<tool_call\s+name\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_PARAM_OPEN_RE = re.compile(
    r'<parameter\s+name\s*=\s*["\']([^"\']+)["\']\s*>',
    re.IGNORECASE,
)

_TOOL_TAGS_WITHIN = re.compile(
    r'(?i)<(tool_call|tool_called|invoke)\b[^>]*>',
)


def _contains_any_tool_tag(text: str, tool_names: list[str]) -> bool:
    if _TOOL_TAGS_WITHIN.search(text):
        return True
    for name in tool_names:
        if f'name="{name}"' in text or f"name='{name}'" in text:
            return True
    return False


def repair_tier3(text: str, tool_names: Optional[list[str]] = None) -> Optional[str]:
    """Reconstruct broken tool calls from partial text fragments.

    Handles:
    - Truncated opening tag: <tool_call name="X"><parameter...
    - Missing closing tags
    - Abandoned parameter values
    """
    if not text or not text.strip():
        return None

    tool_names = tool_names or []

    if not _contains_any_tool_tag(text, tool_names):
        return None

    raw = text

    # Close unclosed parameters first (innermost), then invoke, then tool_calls (outermost)
    param_opens = len(_PARAM_OPEN_RE.findall(raw)) + len(re.findall(r'<parameter\b[^>]*>', raw, re.I))
    param_closes = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?parameter>', raw, re.I))

    result = raw
    for _ in range(max(0, param_opens - param_closes)):
        result += "</parameter>"

    # Close unclosed invoke tags
    invoke_opens = len(re.findall(r'<(?:\|?(?:TOOL|DSML)\|?)?invoke\b[^>]*>', result, re.I))
    invoke_closes = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?invoke>', result, re.I))
    for _ in range(max(0, invoke_opens - invoke_closes)):
        result += "</invoke>"

    # Close unclosed tool_call (singular) tags
    tool_call_opens = len(re.findall(r'<(?:\|?(?:TOOL|DSML)\|?)?tool_call\b[^>]*>', result, re.I))
    tool_call_closes = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?tool_call>', result, re.I))
    for _ in range(max(0, tool_call_opens - tool_call_closes)):
        result += "</tool_call>"

    # Close unclosed tool_calls (plural) tags
    tool_calls_opens = len(re.findall(r'<(?:\|?(?:TOOL|DSML)\|?)?tool_calls\b[^>]*>', result, re.I))
    tool_calls_closes = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?tool_calls>', result, re.I))
    for _ in range(max(0, tool_calls_opens - tool_calls_closes)):
        result += "</tool_calls>"

    # Close unclosed tool_dispatch tags
    dispatch_opens = len(re.findall(r'<(?:\|?(?:TOOL|DSML)\|?)?tool_dispatch\b[^>]*>', result, re.I))
    dispatch_closes = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?tool_dispatch>', result, re.I))
    for _ in range(max(0, dispatch_opens - dispatch_closes)):
        result += "</tool_dispatch>"

    if result != raw:
        return result

    # Bare partial: <invoke name="X"> or <tool_call name="X"> without any param -> add empty close
    m_inv = re.match(r'<(?:\|?(?:TOOL|DSML)\|?)?invoke\s+name\s*=\s*["\']([^"\']+)["\']\s*>$', raw.strip(), re.I)
    if m_inv:
        return f"{raw.strip()}</invoke>"

    m_tc = re.match(r'<(?:\|?(?:TOOL|DSML)\|?)?tool_call\s+name\s*=\s*["\']([^"\']+)["\']\s*>$', raw.strip(), re.I)
    if m_tc:
        return f"{raw.strip()}</tool_call>"

    return None
