"""Tier 1 — text-level DSML/XML repair.

Fixes common textual issues in DSML/XML tool call blocks emitted by
DeepSeek V4 Pro web chat before attempting structural parsing.
"""

from __future__ import annotations

import json
import re

__all__ = ["repair_tier1"]

# ── Patterns ──────────────────────────────────────────────────────────────

# Matches DSML/TOOL namespace tags that are missing a leading <
_DSML_TAG_PATTERN = re.compile(
    r"(?<![<\w/])(\|(?:TOOL|DSML|DSL|TS|ts)\|(?:tool_calls?|invoke|parameter|tool_result))\b",
    re.IGNORECASE,
)

# Matches markdown code fences around tool blocks
_MARKDOWN_FENCE_PATTERN = re.compile(
    r"^```(?:xml|dsml|html)?\s*\n|```\s*$",
    re.MULTILINE,
)

# Matches CDATA sections (possibly unclosed)
_CDATA_PATTERN = re.compile(
    r"<!\[CDATA\[(.*?)(\]\]>|$)",
    re.DOTALL,
)

# Matches human-readable prose at start of text before the tool block
_LEADING_PROSE_PATTERN = re.compile(
    r"^(.*?)(<(?:[|]?(?:TOOL|DSML)\|)?(?:tool_calls?|tool_called)\b)",
    re.DOTALL | re.IGNORECASE,
)

# Matches a tool-call opener that lost its leading '<inv' prefix, so the
# model emits ``oke name="bash">`` instead of ``<invoke name="bash">``.
# The lookbehind avoids matching the ``oke`` inside a valid ``<invoke``
# (preceded by ``v``) or inside words like ``smoke``/``choke``.
_DAMAGED_INVOKE_OPENER_RE = re.compile(
    r'(?<![\w<])oke\s+name=["\']([^"\']+)["\']\s*>',
    re.IGNORECASE,
)


# ── Helper predicates ────────────────────────────────────────────────────


def _has_tool_tag(text: str, tool_names: list[str] | None = None) -> bool:
    """Check if *text* contains any tool-call DSML/XML tag."""
    if _DSML_TAG_PATTERN.search(text):
        return True
    # Plain XML tool tags (e.g. <tool_calls>, <invoke>, <parameter>)
    if re.search(
        r"<(?:tool_calls?|tool_called|invoke|parameter|tool_result)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    # DSML tags that already have their leading < after fixing (e.g. <|TOOL|tool_calls>)
    if re.search(
        r"<\|(?:TOOL|DSML)\|(?:tool_calls?|invoke|parameter|tool_result)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    # Direct tool name tags: <Read>, <Write>, <Bash>, etc.
    if tool_names:
        for name in tool_names:
            if re.search(rf"<{re.escape(name)}\b[^>]*>", text):
                return True
    # Bracket tool calls: [调用 Tool], [call Tool], etc.
    if re.search(
        r"(?:\[|【)\s*(?:调用|call|invoke)[:：]?\s*[a-zA-Z0-9_\-\.]+\s*(?:\]|】)",
        text,
        re.IGNORECASE,
    ):
        return True
    return False


# ── Individual fix functions ─────────────────────────────────────────────


def _fix_broken_namespace(text: str) -> str:
    """Fix common namespace typos.

    - |DSL|  → |DSML|
    - |TS|   → |TOOL|
    """
    text = re.sub(r"\|DSL\|", "|DSML|", text)
    text = re.sub(r"(?<!\w)\|TS\|(?!\w)", "|TOOL|", text, flags=re.IGNORECASE)
    return text


def _fix_missing_lt(text: str) -> str:
    """Prepend ``<`` to DSML/TOOL tags that lost their opening bracket."""
    return _DSML_TAG_PATTERN.sub(r"<\1", text)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences wrapping tool blocks."""
    return _MARKDOWN_FENCE_PATTERN.sub("", text)


def _fix_unclosed_cdata(text: str) -> str:
    """Append ``]]>`` to any CDATA section that is missing its closing marker."""

    def _replacer(m: re.Match) -> str:
        content = m.group(1)
        closer = m.group(2)
        if not closer:
            return f"<![CDATA[{content}]]>"
        return m.group(0)

    return _CDATA_PATTERN.sub(_replacer, text)


def _strip_leading_prose(text: str) -> str:
    """Remove human-readable prose before the first tool-call tag."""
    return _LEADING_PROSE_PATTERN.sub(r"\2", text)


def _fix_truncated_tag(text: str) -> str:
    """Gracefully handle a truncated tag at the very end of *text*.

    Cases handled:
    - ``<`` or ``</`` at end → removed
    - ``</tagname`` at end → completed to ``</tagname>``
    - ``<tagname`` or ``<tagname attr=...`` at end → completed to ``<tagname>``
    """
    stripped = text.rstrip()

    # Bare < or </ at end → remove
    if stripped.endswith("<"):
        return stripped[:-1].rstrip()
    if stripped.endswith("</"):
        return stripped[:-2].rstrip()

    # Incomplete closing tag: </tagname (no >)
    m = re.search(r"</([a-zA-Z0-9_]+)\s*$", stripped)
    if m:
        return stripped[: m.start()] + f"</{m.group(1)}>"

    # Incomplete opening tag: <tagname or <tagname attrs... (no >)
    m = re.search(r"<([a-zA-Z0-9_]+)(?:\s+[^>]*)?$", stripped)
    if m:
        return stripped[: m.start()] + f"<{m.group(1)}>"

    return text


def _fix_tool_called_format(text: str) -> str:
    r"""Convert ``<tool_called name="X">`` to DSML ``<tool_calls><invoke name="X">`` format.

    The model sometimes emits function calls using the past-tense form
    ``<tool_called name="ToolName">...<parameter ...>...</tool_called>`` instead
    of the canonical DSML structure::

        <tool_calls>
          <invoke name="ToolName">
            <parameter name="p">...</parameter>
          </invoke>
        </tool_calls>

    This function does the structural rename so the downstream DSML parser
    can understand it.
    """
    # Opening tag: <tool_called name="X"> → <tool_calls><invoke name="X">
    text = re.sub(
        r'<tool_called\s+name="([^"]*)"\s*>',
        r'<tool_calls>\n<invoke name="\1">',
        text,
        flags=re.IGNORECASE,
    )
    # Closing tag: </tool_called> → </invoke></tool_calls>
    text = re.sub(
        r"</tool_called\s*>",
        "</invoke>\n</tool_calls>",
        text,
        flags=re.IGNORECASE,
    )
    # Also handle <tool_called name='X'> (single-quoted)
    text = re.sub(
        r"<tool_called\s+name='([^']*)'\s*>",
        r'<tool_calls>\n<invoke name="\1">',
        text,
        flags=re.IGNORECASE,
    )
    return text


def _fix_nested_invoke_mismatch(text: str) -> str:
    """Fix nested invoke tag mismatches where model outputs <invoke name="param"> but closes with </parameter>.

    DeepSeek sometimes makes a structural error like:
    <invoke name="TodoWrite"> <invoke name="todos" string="true">[...]</parameter> ... </invoke>
    This detects <invoke name="..."> followed by </parameter> within the same block and converts the opener to <parameter name="...">.
    """
    # We find '<invoke name="' and replace it with '<parameter name="' ONLY if it is nested
    # inside another '<invoke'.
    # A tag <invoke name="..."> is nested if the count of '<invoke' before it is greater than the count of '</invoke>'.
    pattern = re.compile(r'<invoke(\s+name=["\'][^"\']+["\'][^>]*?)>', re.IGNORECASE)

    def replacer(match: re.Match) -> str:
        start_idx = match.start()
        preceding = text[:start_idx].lower()

        # Count preceding <invoke tags vs </invoke> closing tags
        open_count = len(re.findall(r"<invoke\b", preceding))
        close_count = preceding.count("</invoke>")

        if open_count > close_count:
            # Check if there is a new tool container (<tool_calls>) between previous invoke and this one
            last_invoke = preceding.rfind("<invoke")
            last_container = max(
                preceding.rfind("<tool_calls"),
                preceding.rfind("<tool_dispatch"),
                preceding.rfind("<|dsml|tool_calls"),
                preceding.rfind("<|tool|tool_calls"),
            )
            if last_container > last_invoke:
                return match.group(0)

            remaining = text[match.end() :]
            next_invoke = remaining.lower().find("<invoke")
            next_param_close = remaining.lower().find("</parameter>")
            next_param_open = remaining.lower().find("<parameter")

            # If this invoke contains its own <parameter> tags before any </parameter>,
            # it is a real invoke, NOT a parameter!
            if next_param_open != -1 and (
                next_param_close == -1 or next_param_open < next_param_close
            ):
                return match.group(0)

            if next_param_close != -1 and (
                next_invoke == -1 or next_param_close < next_invoke
            ):
                return f"<parameter{match.group(1)}>"

        return match.group(0)  # Keep as-is

    return pattern.sub(replacer, text)


def _fix_damaged_invoke_opener(text: str) -> str:
    """Restore the opener of a tool block that lost its ``<inv`` prefix.

    DeepSeek Pro occasionally streams a complete, well-formed tool block
    whose opening tag is missing its leading ``<inv``, so ``<invoke name="bash">``
    arrives as ``oke name="bash">``.  The rest of the block (``<parameter>``
    elements and ``</invoke>``) is intact, so the opener can be restored
    safely.  To avoid rewriting tool-argument content, only the first damaged
    opener *before* the first ``<parameter`` is touched, and only when the
    text also contains a closing ``</invoke>``.
    """
    if "<parameter" not in text or "</invoke>" not in text:
        return text
    first_param = text.find("<parameter")
    head, tail = text[:first_param], text[first_param:]
    m = _DAMAGED_INVOKE_OPENER_RE.search(head)
    if not m:
        return text
    return head[: m.start()] + f'<invoke name="{m.group(1)}">' + head[m.end() :] + tail


# ── New format: <tool_name>/<tool_args> children ─────────────────────────

# Matches <tool_called> blocks using <tool_name> and <tool_args> child elements
_TOOL_CALLED_CHILD_PATTERN = re.compile(
    r"<tool_called\s*>\s*"
    r"<tool_name>([^<]+)</tool_name>\s*"
    r"<tool_args\s*>(.*?)</tool_args\s*>\s*"
    r"</tool_called\s*>",
    re.DOTALL | re.IGNORECASE,
)


def _fix_tool_called_child_format(text: str) -> str:
    r"""Convert ``<tool_called>`` with ``<tool_name>``/``<tool_args>`` children to DSML.

    The model sometimes emits calls using this nested-element format::

        <tool_called>
        <tool_name>Skill</tool_name>
        <tool_args>
        {"name": "using-superpowers"}
        </tool_args>
        </tool_called>

    This converts it to the standard DSML structure::

        <tool_calls>
          <invoke name="Skill">
            <parameter name="name"><![CDATA[using-superpowers]]></parameter>
          </invoke>
        </tool_calls>
    """

    def _replacer(m: re.Match) -> str:
        name = m.group(1).strip()
        args_json = m.group(2).strip()

        # Try to parse as JSON and build <parameter> elements
        try:
            args_dict = json.loads(args_json)
        except json.JSONDecodeError:
            # Not valid JSON — wrap entire content as single parameter
            return (
                f'<tool_calls>\n<invoke name="{name}">\n'
                f'<parameter name="content"><![CDATA[{args_json}]]></parameter>\n'
                f"</invoke>\n</tool_calls>"
            )

        params: list[str] = []
        for key, value in args_dict.items():
            if isinstance(value, str):
                params.append(
                    f'<parameter name="{key}"><![CDATA[{value}]]></parameter>'
                )
            elif isinstance(value, bool):
                params.append(
                    f'<parameter name="{key}">{str(value).lower()}</parameter>'
                )
            elif isinstance(value, (int, float)):
                params.append(f'<parameter name="{key}">{value}</parameter>')
            elif isinstance(value, (dict, list)):
                params.append(
                    f'<parameter name="{key}"><![CDATA['
                    f"{json.dumps(value, ensure_ascii=False)}]]></parameter>"
                )
            elif value is None:
                params.append(f'<parameter name="{key}"></parameter>')
            else:
                params.append(
                    f'<parameter name="{key}"><![CDATA[{str(value)}]]></parameter>'
                )

        params_str = "\n".join(params)
        return (
            f'<tool_calls>\n<invoke name="{name}">\n'
            f"{params_str}\n"
            f"</invoke>\n</tool_calls>"
        )

    return _TOOL_CALLED_CHILD_PATTERN.sub(_replacer, text)


def _fix_bracket_call_format(text: str) -> str:
    r"""Convert bracket calls like ``[调用 Read] {"path": "..."}`` to DSML XML.

    Converts:
        [调用 Read] {"path": "F:/test.md"}
    To:
        <tool_calls>
        <invoke name="Read">
        <parameter name="path"><![CDATA[F:/test.md]]></parameter>
        </invoke>
        </tool_calls>
    """
    decoder = json.JSONDecoder()
    pattern = re.compile(
        r"(?:\[|【)\s*(?:调用|call|invoke)[:：]?\s*([a-zA-Z0-9_\-\.]+)\s*(?:\]|】)",
        re.IGNORECASE,
    )
    while True:
        m = pattern.search(text)
        if not m:
            break
        name = m.group(1).strip()
        after = text[m.end() :]
        brace_offset = after.find("{")
        if brace_offset == -1 or after[:brace_offset].strip() != "":
            break
        json_start = m.end() + brace_offset
        try:
            args, end_offset = decoder.raw_decode(text[json_start:])
        except json.JSONDecodeError:
            break

        full_end = json_start + end_offset
        params: list[str] = []
        if isinstance(args, dict):
            for k, v in args.items():
                if isinstance(v, str):
                    params.append(f'<parameter name="{k}"><![CDATA[{v}]]></parameter>')
                elif isinstance(v, bool):
                    params.append(f'<parameter name="{k}">{str(v).lower()}</parameter>')
                elif isinstance(v, (int, float)):
                    params.append(f'<parameter name="{k}">{v}</parameter>')
                elif isinstance(v, (dict, list)):
                    params.append(
                        f'<parameter name="{k}"><![CDATA['
                        f"{json.dumps(v, ensure_ascii=False)}]]></parameter>"
                    )
                elif v is None:
                    params.append(f'<parameter name="{k}"></parameter>')
                else:
                    params.append(f'<parameter name="{k}"><![CDATA[{str(v)}]]></parameter>')
        else:
            params.append(f'<parameter name="value"><![CDATA[{str(args)}]]></parameter>')

        xml_block = (
            f'<tool_calls>\n<invoke name="{name}">\n'
            + "\n".join(params)
            + f"\n</invoke>\n</tool_calls>"
        )
        text = text[: m.start()] + xml_block + text[full_end:]

    return text


# ── Public API ───────────────────────────────────────────────────────────



def _normalize_bare_dsml_wrapper(text: str) -> str:
    """Normalize standalone <|DSML|> / </|DSML|> tags to <tool_calls> / </tool_calls>."""
    text = re.sub(r'<[|｜]+(?:DSML|TOOL)[|｜]+\s*>', '<tool_calls>', text, flags=re.IGNORECASE)
    text = re.sub(r'</[|｜]+(?:DSML|TOOL)[|｜]+\s*>', '</tool_calls>', text, flags=re.IGNORECASE)
    return text


def _fix_unclosed_invoke_before_tool_calls_close(text: str) -> str:
    """Add missing </parameter> and </invoke> before </tool_calls> when tags were not closed."""
    def _repl(m: re.Match) -> str:
        body = m.group(0)
        popens = len(re.findall(r'<(?:\|?(?:TOOL|DSML)\|?)?parameter\b', body, re.IGNORECASE))
        pcloses = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?parameter\s*>', body, re.IGNORECASE))
        iopens = len(re.findall(r'<(?:\|?(?:TOOL|DSML)\|?)?invoke\b', body, re.IGNORECASE))
        icloses = len(re.findall(r'</(?:\|?(?:TOOL|DSML)\|?)?invoke\s*>', body, re.IGNORECASE))

        insert = ""
        if popens > pcloses:
            insert += ('</parameter>\n' * (popens - pcloses))
        if iopens > icloses:
            insert += ('</invoke>\n' * (iopens - icloses))

        if insert:
            cm = re.search(r'</(?:\|?(?:TOOL|DSML)\|?)?tool_calls\s*>', body, re.IGNORECASE)
            if cm:
                idx = cm.start()
                return body[:idx] + insert + body[idx:]
        return body

    return re.sub(
        r'<(?:\|?(?:TOOL|DSML)\|?)?tool_calls\b[^>]*>.*?</(?:\|?(?:TOOL|DSML)\|?)?tool_calls\s*>',
        _repl,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def _fix_orphaned_tool_calls_close(text: str) -> str:
    r"""Add missing <tool_calls> opening tag when only closing tag exists.
    
    Fixes: <invoke>...</invoke></tool_calls> (missing opening <tool_calls>)
    """
    has_close = re.search(r'</(?:\|?(?:TOOL|DSML)\|)?tool_calls?\s*>', text, re.IGNORECASE)
    has_open = re.search(r'<(?:\|?(?:TOOL|DSML)\|)?tool_calls?\s*>', text, re.IGNORECASE)
    
    if has_close and not has_open:
        invoke_match = re.search(r'<(?:\|?(?:TOOL|DSML)\|)?invoke\s', text, re.IGNORECASE)
        if invoke_match:
            insert_pos = invoke_match.start()
            text = text[:insert_pos] + '<tool_calls>\n' + text[insert_pos:]
    return text

def _fix_direct_tool_tags(text: str, tool_names: list[str] | None = None) -> str:
    """Convert direct <ToolName>...</ToolName> into <invoke name="ToolName">...</invoke>.

    When the model uses tool names directly as tags (e.g. <Shell><command>...</command></Shell>),
    this wraps or converts them into standard DSML invoke elements.
    """
    if not tool_names:
        return text

    for name in tool_names:
        # 1. Handle self-closing tags: <ToolName attr="val" ... />
        self_closing_pattern = re.compile(rf"<({re.escape(name)})(\s+[^>]*?)\s*/>", re.IGNORECASE)
        def _self_repl(m: re.Match) -> str:
            tname = name
            attrs = m.group(2) or ""
            attr_dict = dict(re.findall(r'(\w+)=["\']([^"\']*)["\']', attrs))
            param_xml = "".join(f'<parameter name="{k}">{v}</parameter>' for k, v in attr_dict.items())
            return f'<invoke name="{tname}">{param_xml}</invoke>'

        text = self_closing_pattern.sub(_self_repl, text)

        # 2. Handle standard open/close pairs: <ToolName ...>...</ToolName>
        pattern = re.compile(rf"<({re.escape(name)})(\s+[^>]*)?>(.*?)</\1\s*>", re.DOTALL | re.IGNORECASE)
        def _repl(m: re.Match) -> str:
            tname = name
            attrs = m.group(2) or ""
            inner = m.group(3)
            if "<parameter" not in inner:
                attr_dict = dict(re.findall(r'(\w+)=["\']([^"\']*)["\']', attrs))
                if attr_dict:
                    param_xml = "".join(f'<parameter name="{k}">{v}</parameter>' for k, v in attr_dict.items())
                    return f'<invoke name="{tname}">{param_xml}</invoke>'
                child_tags = re.findall(r'<([a-zA-Z_][a-zA-Z0-9_]*)>(.*?)</\1>', inner, re.DOTALL)
                if child_tags:
                    param_xml = "".join(f'<parameter name="{k}">{v}</parameter>' for k, v in child_tags)
                    return f'<invoke name="{tname}">{param_xml}</invoke>'
            return f'<invoke name="{tname}">{inner}</invoke>'

        text = pattern.sub(_repl, text)

    return text


def repair_tier1(text: str, tool_names: list[str] | None = None) -> str | None:
    """Run text-level DSML/XML repair on *text*.

    Applies all known fixes in sequence and returns the repaired text,
    or ``None`` if the text contains no tool-call content (or is empty).
    """
    if not text or not text.strip():
        return None

    original = text

    # Normalize full-width pipes ｜ (U+FF5C) to ASCII |
    text = text.replace("\uff5c", "|")

    # Apply fixes in order
    text = _normalize_bare_dsml_wrapper(text)
    text = _fix_broken_namespace(text)
    text = _fix_missing_lt(text)
    text = _strip_markdown_fences(text)
    text = _fix_unclosed_cdata(text)
    text = _strip_leading_prose(text)
    text = _fix_tool_called_child_format(text)
    text = _fix_tool_called_format(text)
    text = _fix_direct_tool_tags(text, tool_names)
    text = _fix_bracket_call_format(text)
    text = _fix_orphaned_tool_calls_close(text)
    text = _fix_nested_invoke_mismatch(text)
    text = _fix_damaged_invoke_opener(text)
    text = _fix_unclosed_invoke_before_tool_calls_close(text)
    text = _fix_truncated_tag(text)

    text = text.strip()

    if not text:
        return None

    if not _has_tool_tag(text, tool_names):
        return None

    return text

