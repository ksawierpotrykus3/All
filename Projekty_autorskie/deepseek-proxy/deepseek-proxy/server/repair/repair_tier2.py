"""Tier 2 — JSON argument repair.

Fixes common JSON structural issues in tool call arguments
extracted from DSML/XML blocks by Tier 1.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Optional

__all__ = ["repair_tier2"]

# ── Schema mapping for bare string wrapping ──────────────────────────────

_TOOL_PARAM_MAP: dict[str, str] = {
    "Shell": "command",
    "AwaitShell": "shell_id",
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "SearchReplace": "file_path",
    "Glob": "pattern",
    "Grep": "pattern",
    "WebSearch": "query",
    "WebFetch": "url",
    "RunCommand": "command",
    "AskUserQuestion": "question",
    "Task": "description",
    "Skill": "name",
    "NotifyUser": "explanation",
    "OpenPreview": "preview_url",
    "DeleteFile": "file_paths",
    "TodoWrite": "todos",
}

# Valid JSON escape characters (after a backslash)
_VALID_JSON_ESCAPES = {'"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'}

# ── Internal fix functions ───────────────────────────────────────────────


def _find_json_block(text: str) -> str | None:
    """Find the first JSON object/array in *text*, or content from ``<parameter>`` tags.

    Priority:
    1. Content inside ``<parameter>...</parameter>`` tags
    2. Standalone JSON object ``{...}`` or array ``[...]``
    3. Bare string (no JSON structure detected)
    """
    # Try <parameter> content first
    m = re.search(r'<parameter[^>]*>(.*?)</parameter>', text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        if content:
            return content

    # Try standalone JSON object or array
    m = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if m:
        return m.group(1)

    # Try bare string (no JSON structure at all)
    text = text.strip()
    if text:
        return text

    return None


def _fix_single_quotes(text: str) -> str:
    """Replace single quotes with double quotes in JSON-like content.

    Handles:
    - ``'key':`` → ``"key":``
    - ``: 'value'`` → ``: "value"``
    """
    text = re.sub(r"'([^']+)':", r'"\1":', text)
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
    return text


def _fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before ``}`` or ``]``."""
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*\]', ']', text)
    return text


def _fix_unescaped_backslashes(text: str) -> str:
    """Fix unescaped backslashes that aren't valid JSON escapes.

    Valid JSON escapes: ``\\\\``, ``\\"``, ``\\/``, ``\\b``, ``\\f``,
    ``\\n``, ``\\r``, ``\\t``, ``\\uXXXX``.

    Any ``\\X`` where *X* is not one of the above is replaced with
    ``\\\\X`` (i.e. the backslash is doubled).
    """
    result: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char in _VALID_JSON_ESCAPES:
                if next_char == 'u':
                    # Check if \u is followed by exactly 4 hex digits
                    hex_part = text[i + 2 : i + 6]
                    if len(hex_part) == 4 and all(
                        c in '0123456789abcdefABCDEF' for c in hex_part
                    ):
                        # Valid \uXXXX — keep as-is
                        result.append(text[i : i + 6])
                        i += 6
                        continue
                    # Invalid \u — double the backslash
                    result.append('\\\\')
                    result.append(next_char)
                    i += 2
                    continue
                # Valid escape (e.g. \n, \t, \\, \") — keep as-is
                result.append(text[i])
                result.append(next_char)
                i += 2
                continue
            # Invalid escape — double the backslash
            result.append('\\\\')
            result.append(next_char)
            i += 2
            continue
        # Regular character
        result.append(text[i])
        i += 1
    return ''.join(result)


def _fix_double_encoded(text: str) -> str:
    """Fix XML-double-encoded JSON: replace ````""```` with escaped quotes.

    When JSON is embedded in XML, inner double quotes may be encoded as
    ``&quot;`` which can appear as ````""````. This replaces them with
    ``\"`` (properly escaped JSON quotes).
    """
    return re.sub(r'""', r'\\"', text)


def _try_parse_json(text: str) -> str | None:
    """Try to parse *text* as JSON with increasing leniency.

    Strategies tried in order:
    1. ``json.loads``
    2. ``ast.literal_eval`` (handles Python-style literals, e.g. single-quoted keys)
    """
    # Standard json.loads
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        pass

    # ast.literal_eval (handles Python dicts/lists with single-quoted keys)
    try:
        obj = ast.literal_eval(text)
        return json.dumps(obj, ensure_ascii=False)
    except (ValueError, SyntaxError):
        pass

    return None


def _wrap_bare_string(text: str, tool_name: str | None) -> str | None:
    """Wrap a bare string in the expected JSON schema for the given tool.

    Uses ``_TOOL_PARAM_MAP`` to determine the parameter name for the tool.
    """
    if not tool_name:
        return None

    param = _TOOL_PARAM_MAP.get(tool_name)
    if not param:
        return None

    wrapped = {param: text}
    return json.dumps(wrapped, ensure_ascii=False)


# ── Public API ───────────────────────────────────────────────────────────


def repair_tier2(
    text: str, tool_names: Optional[list[str]] = None
) -> str | None:
    """Run JSON-level repair on tool call arguments.

    Supports two calling conventions:

    **Orchestrator convention** (``tool_names`` is a list or ``None``):
        ``repair_tier2(raw_text, ['Bash', ...])`` — ``text`` is the raw
        text to repair, ``tool_names`` provides the tool name.

    **Test convention** (``tool_names`` is a plain string):
        ``repair_tier2('Bash', '{"command": ...}')`` — ``text`` is the
        tool name, ``tool_names`` is the JSON text to repair.

    The repair flow:
    1. Return ``None`` if input text is empty
    2. Extract JSON block (parameter tag content, or standalone JSON)
    3. Apply sequential fixes: single quotes → trailing commas →
       unescaped backslashes → double-encoded quotes
    4. Try to parse as JSON; re-serialize on success
    5. If parsing fails, try bare string wrapping in tool-specific schema
    6. Return ``None`` if all strategies fail

    Args:
        text: The input text or tool name (depending on convention).
        tool_names: List of tool names, or a JSON string (test
            convention), or ``None``.

    Returns:
        Repaired JSON string, or ``None`` if repair failed.
    """
    # ── Detect calling convention ────────────────────────────────────
    if isinstance(tool_names, str):
        # Test convention: (tool_name, json_text)
        json_text = tool_names
        tool_name: str | None = text
    else:
        # Orchestrator convention: (raw_text, tool_names_list | None)
        json_text = text
        tool_name = tool_names[0] if tool_names else None

    if not json_text or not json_text.strip():
        return None

    original = json_text.strip()

    # Step 1: Extract JSON block
    json_block = _find_json_block(original)
    if json_block is None:
        return None

    # Step 2: Apply sequential fixes
    fixed = _fix_single_quotes(json_block)
    fixed = _fix_trailing_commas(fixed)
    fixed = _fix_unescaped_backslashes(fixed)
    fixed = _fix_double_encoded(fixed)

    # Step 3: Try to parse as JSON
    parsed = _try_parse_json(fixed)
    if parsed is not None:
        return parsed

    # Step 4: Try bare string wrapping
    wrapped = _wrap_bare_string(original, tool_name)
    if wrapped is not None:
        return wrapped

    return None
