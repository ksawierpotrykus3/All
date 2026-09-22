from __future__ import annotations
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from server.logging import get_logger

logger = get_logger(__name__)


_CDATA_OPEN = "<![CDATA["
_CDATA_CLOSE = "]]>"
_DSML_NS: set[str] = set("| \t\r\n")
_DSML_NS.add(chr(0xFF5C))  # full-width pipe

TOOL_CALLS_PATTERN = re.compile(
    r"<(?:\|?(?:TOOL|DSML)\|?)?\s*tool_?calls?[^>]*>(.*?)</(?:\|?(?:TOOL|DSML)\|?)?\s*tool_?calls?\s*>",
    re.DOTALL | re.IGNORECASE,
)

# ─── JSON tool call format (CO-STAR mode) ────────────────────
JSON_TOOL_CALL_PATTERN = re.compile(r"```tool_call\s*\n?(.*?)```", re.DOTALL)


_TAG_START_RE = re.compile(
    r"^/?(?:[|｜\s]*(?:TOOL|DSML|tool|dsml|TS|ts)[|｜\s]*$|[|｜\s]*(?:(?:TOOL|DSML|tool|dsml|TS|ts)[|｜\s]*)?([a-zA-Z_][a-zA-Z0-9_-]*))",
    re.IGNORECASE,
)


def strip_dsml_markup(text: str) -> str:
    """Remove DSML namespace prefixes and normalize tags."""
    if not text:
        return ""
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i:].startswith(_CDATA_OPEN):
            cl = text.find(_CDATA_CLOSE, i + len(_CDATA_OPEN))
            if cl == -1:
                result.append(text[i:])
                break
            result.append(text[i : cl + len(_CDATA_CLOSE)])
            i = cl + len(_CDATA_CLOSE)
            continue
        if text[i] != "<":
            result.append(text[i])
            i += 1
            continue
        end = text.find(">", i)
        if end == -1:
            result.append(text[i:])
            break
        # If there's another '<' before '>', the current '<' is not closing with this '>'
        # (e.g. relational operator '<' in python code: 'if (x < 10): ...')
        next_lt = text.find("<", i + 1)
        if next_lt != -1 and next_lt < end:
            result.append(text[i])
            i += 1
            continue
        inner = text[i + 1 : end]
        # Validate that inner conforms to a valid tag name or DSML marker
        if not _TAG_START_RE.match(inner):
            result.append(text[i])
            i += 1
            continue
        is_close = inner.startswith("/")
        tag = inner[1:] if is_close else inner
        # Strip DSML prefix noise: <|DSML|tag> -> <tag>
        cleaned = _strip_dsml_noise(tag)
        if cleaned != tag:
            prefix = "</" if is_close else "<"
            result.append(prefix + cleaned + ">")
            i = end + 1
        else:
            result.append(text[i : end + 1])
            i = end + 1
    return "".join(result)


def _strip_dsml_noise(tag: str) -> str:
    """Strip DSML namespace noise from a tag name.

    Handles ASCII (``|``) and full-width (``｜``) pipes, with or without a
    TOOL/DSML marker: ``<|DSML|invoke>`` -> ``<invoke>`` and ``<｜invoke>``
    -> ``<invoke>``.
    """
    m = re.match(
        "^(?:["
        + _PIPES_CLASS
        + r"]+\s*(?:TOOL|DSML|tool|dsml|TS|ts)\s*["
        + _PIPES_CLASS
        + r"]+\s*)?(.+)$",
        tag,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(_PIPES_CLASS)
    return tag


def clean_tool_text(text: str) -> str:
    """Remove all DSML/XML tool call tags from text, leaving only content."""
    if not text:
        return ""
    # Normalize missing < and delimiters before stripping tags so bare <|DSML|> becomes <tool_calls>
    text = _fix_missing_lt(text)
    text = _normalize_tag_delimiters(text)
    text = TOOL_CALLS_PATTERN.sub("", text)
    # Defense in depth: strip any leftover bare DSML/TOOL wrapper markers
    text = re.sub(
        r"</?[|｜]+(?:DSML|TOOL)[|｜]+>[ \t]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Strip bare <tool_call name="..."> (no prefix, no <tool_calls> wrapper)
    text = re.sub(
        r'<tool_call\s+name=["\'][^"\']*["\'][^>]*>.*?</tool_call\s*>',
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip bare <toolcall>...</toolcall> (no underscore) — model sometimes drops underscore
    text = re.sub(
        r"<toolcall[^>]*>.*?</toolcall\s*>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<(?:\|?(?:TOOL|DSML)\|?)?invoke[^>]*>.*?</(?:\|?(?:TOOL|DSML)\|?)?invoke\s*>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<(?:\|?(?:TOOL|DSML)\|?)?parameter[^>]*>.*?</(?:\|?(?:TOOL|DSML)\|?)?parameter\s*>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<!\[CDATA\[.*?\]\]>", "", text, flags=re.DOTALL)
    # Strip <argument key="..." value="..."> (model's trained fallback format)
    text = re.sub(
        r"<argument\s+[^>]+>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Strip bare closing tags (when <invoke>/<parameter> are already removed
    # but </tool_calls> survives because no opener matched).
    # This prevents e.g. "</tool_calls>" or "</|DSML|tool_calls>" from appearing
    # as visible text in the IDE when a tool call XML block was not captured
    # by StreamSieve and went through clean_tool_text() as raw text.
    text = re.sub(
        r"</(?:\|?(?:TOOL|DSML)\|?)?(?:tool_calls?|tool_dispatch|tool_call|toolcall|tool_called|invoke|parameter|tool_result)[^>]*>[ \t]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Strip incomplete tool call blocks (truncated by stream end — missing final ">").
    # E.g. "<invoke name="Edit">...lots of code...</invoke" without trailing ">".
    _before_trunc = text
    text = re.sub(
        r"<(?:\|?(?:TOOL|DSML)\|?)?invoke[^>]*>.*?(?:</(?:\|?(?:TOOL|DSML)\|?)?invoke)?[ \t]*$",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if text != _before_trunc:
        logger.warning(
            "[TOOL_TRUNC] stripped an incomplete <invoke> block (stream ended before "
            "closing tag) — this tool call was NOT delivered to the IDE"
        )
    # Also strip any remaining incomplete <tool_calls> blocks
    _before_trunc2 = text
    text = re.sub(
        r"<(?:\|?(?:TOOL|DSML)\|?)?tool_?calls?[^>]*>.*?(?:</(?:\|?(?:TOOL|DSML)\|?)?tool_?calls?\s*)?[ \t]*$",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if text != _before_trunc2:
        logger.warning(
            "[TOOL_TRUNC] stripped an incomplete <tool_calls> block (stream ended "
            "before closing tag) — calls were NOT delivered to the IDE"
        )
    return text


def _auto_type(val: str) -> Any:
    if not val:
        return val
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() in ("null", "none"):
        return None
    # Try parsing as JSON (handles arrays, objects, numbers, booleans, null)
    stripped = val.strip()
    if stripped and (stripped[0] in ("{", "[") or stripped[0] in ('"',)):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _extract_cdata(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith(_CDATA_OPEN) and raw.endswith(_CDATA_CLOSE):
        inner = raw[len(_CDATA_OPEN) : -len(_CDATA_CLOSE)]
        inner = inner.replace("]]]]><![CDATA[>", "]]>")
        return inner
    return raw


def _resolve_tool_name(name: str, tool_names: list[str]) -> str:
    if not tool_names:
        return name
    if name in tool_names:
        return name
    for tn in tool_names:
        if tn.lower() == name.lower():
            return tn
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()
    if snake in tool_names:
        return snake
    logger.debug(
        f"[TOOL_NAME_RESOLVE] name={name!r} not resolved against {len(tool_names)} "
        f"known tool(s); forwarding unresolved (IDE may reject/drop)"
    )
    return name


def _fix_missing_lt(text: str) -> str:
    """Prepend < to |TOOL|/|DSML| tags that lost their opening < during streaming.

    The model sometimes drops the opening < on DSML tags like |TOOL|tool_calls>,
    |TOOL|invoke, |TOOL|parameter. This restores them so the regex patterns match.
    Also handles close-tag fragments that lost their opening < (e.g., /|DSML|...>).
    """
    # Character class for both ASCII pipe (|) and full-width pipe (U+FF5C)
    _PIPE = r"[|" + chr(0xFF5C) + r"]"
    # Double pipe (model uses double full-width pipes as delimiters)
    _DPIPE = _PIPE + _PIPE
    _TAG_SUFFIX = r"(?:tool_calls?|invoke|parameter|tool_result)"

    # First handle open-tag fragments: |TOOL|... or |DSML|... (not preceded by <, /, or word char)
    # Matches both ASCII and full-width pipes, single or double
    text = re.sub(
        rf"(?<![<\w/])({_DPIPE}(?:TOOL|DSML){_DPIPE}{_TAG_SUFFIX})\b",
        r"<\1",
        text,
        flags=re.IGNORECASE,
    )
    # Also handle single-pipe variants
    text = re.sub(
        rf"(?<![<\w/])({_PIPE}(?:TOOL|DSML){_PIPE}{_TAG_SUFFIX})\b",
        r"<\1",
        text,
        flags=re.IGNORECASE,
    )

    # Then handle close-tag fragments: /|TOOL|... or /|DSML|... (at start of string or after whitespace)
    # These appear when a close tag like </|DSML|tool_calls> is split across chunks
    # and the second chunk starts with /|DSML|...>
    # Handle both single and double pipe variants
    def _repl_close(m):
        return m.group(1) + "</" + m.group(2)

    # Double pipe close-tag fragment: /||DSML||...>
    text = re.sub(
        rf"(^|\s)/({_DPIPE}(?:TOOL|DSML){_DPIPE}{_TAG_SUFFIX})\b",
        lambda m: m.group(1) + "</" + m.group(2),
        text,
        flags=re.IGNORECASE,
    )
    # Single pipe close-tag fragment: /|DSML|...>
    text = re.sub(
        rf"(^|\s)/({_PIPE}(?:TOOL|DSML){_PIPE}{_TAG_SUFFIX})\b",
        lambda m: m.group(1) + "</" + m.group(2),
        text,
        flags=re.IGNORECASE,
    )
    return text


def _fix_inverted_dsml_close(text: str) -> str:
    """Reorder slash-before/after-marker for DSML/TOOL closing tags.

      DeepSeek Pro sometimes emits closing tags with the slash AFTER the
      DSML/TOOL marker instead of BEFORE it.  For example::

          <|DSML|/invoke>   (model emits this)
    </|DSML|invoke>     (parser expects this)

      Similarly for ``|TOOL|/invoke``, and for ``<parameter>``, ``<tool_calls>``,
      ``<tool_result>``. All existing regex patterns in this module expect
      the slash BEFORE the marker, so we normalise up-front.
    """
    _LT = chr(60)
    _SL = chr(47)
    _GT = chr(62)
    # Accept both ASCII pipe (|) and full-width pipe (U+FF5C) on either side
    # of the marker name (TOOL/DSML).  We CAPTURE both pipes (groups 1 & 2)
    # so the substitution can preserve whatever pipe width the model used.
    _PIPE_CLASS = "[" + "|" + chr(0xFF5C) + "]"
    pattern = (
        _LT
        + "("
        + _PIPE_CLASS
        + ")"
        + "(TOOL|DSML)"
        + "("
        + _PIPE_CLASS
        + ")"
        + _SL
        + "(tool_calls?|invoke|parameter|tool_result)"
        + "\\s*"
        + _GT
    )
    return re.sub(
        pattern,
        lambda m: _LT + _SL + m.group(1) + m.group(2) + m.group(3) + m.group(4) + _GT,
        text,
        flags=re.IGNORECASE,
    )


_DOUBLE_PIPE_RE = re.compile(
    "("
    + chr(0xFF5C)
    + "){2,}"  # 2+ full-width pipes
    + "|"
    + r"\|{2,}"  # 2+ ASCII pipes
)


def _collapse_double_pipes(text: str) -> str:
    """Collapse repeated pipe runs (full-width or ASCII) to a single pipe.

    DeepSeek Pro emits DOUBLE full-width pipes around the DSML/TOOL marker
    (``<｜｜DSML｜｜invoke>``) instead of the canonical single pipe
    (``<｜DSML｜invoke>``).  Every regex in this module expects a single
    pipe, so we collapse repeated pipe runs up-front.
    """
    if not text:
        return text
    return _DOUBLE_PIPE_RE.sub(_pipe_single, text)


def _pipe_single(m: "re.Match[str]") -> str:
    """Return a single pipe matching the *width* of the matched run."""
    if m.group(0)[0] == chr(0xFF5C):
        return chr(0xFF5C)
    return "|"


_FW_PIPE = chr(0xFF5C)
_PIPES_CLASS = "|" + _FW_PIPE  # ASCII | and full-width ｜

# ``_calls`` wrapper (DeepSeek Pro) -> canonical ``tool_calls``.  Matches
# ``<｜_calls｜>`` / ``<｜DSML｜_calls｜>`` regardless of pipe width, with or
# without a TOOL/DSML marker, preserving the ``<``/``</`` prefix and the pipe
# runs.  ``<tool_calls>`` itself is NOT matched (the marker alternative
# requires a trailing pipe run, and a bare tag has no leading pipe run), so
# canonical tags pass through untouched.
_UNDERSCORE_CALLS_TAG_RE = re.compile(
    "<"
    + r"(?P<slash>/?)(?:(?P<fw>["
    + _PIPES_CLASS
    + r"]+)(?P<marker>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+)?|(?P<marker2>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+))\s*"
    + r"_calls(?P<post>[^>]*)>",
    re.IGNORECASE,
)

# ``_dispatch`` wrapper (DeepSeek Pro) -> canonical ``tool_dispatch``.
_UNDERSCORE_DISPATCH_TAG_RE = re.compile(
    "<"
    + r"(?P<slash>/?)(?:(?P<fw>["
    + _PIPES_CLASS
    + r"]+)(?P<marker>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+)?|(?P<marker2>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+))\s*"
    + r"_dispatch(?P<post>[^>]*)>",
    re.IGNORECASE,
)

# ``dispatch`` wrapper (no underscore, DeepSeek Pro) -> canonical ``tool_dispatch``.
_BARE_DISPATCH_TAG_RE = re.compile(
    "<"
    + r"(?P<slash>/?)(?:(?P<fw>["
    + _PIPES_CLASS
    + r"]+)(?P<marker>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+)?|(?P<marker2>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+))\s*"
    + r"dispatch(?P<post>[^>]*)>",
    re.IGNORECASE,
)

# ``calls`` wrapper (no underscore, DeepSeek Pro) -> canonical ``tool_calls``.
_BARE_CALLS_TAG_RE = re.compile(
    "<"
    + r"(?P<slash>/?)(?:(?P<fw>["
    + _PIPES_CLASS
    + r"]+)(?P<marker>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+)?|(?P<marker2>(?:TOOL|DSML)["
    + _PIPES_CLASS
    + r"]+))\s*"
    + r"calls(?P<post>[^>]*)>",
    re.IGNORECASE,
)


def _rename_underscore_dispatch_wrapper(text: str) -> str:
    """Rename the ``_dispatch`` wrapper tag to ``tool_dispatch``.

    DeepSeek Pro emits ``<..._dispatch>`` instead of the canonical
    ``<...tool_dispatch>`` wrapper.  The parser only recognises ``tool_dispatch``,
    so we rewrite the tag name while preserving the ``<``/``</`` prefix.
    """
    if not text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        return (
            "<"
            + (m.group("slash") or "")
            + (m.group("fw") or "")
            + (m.group("marker") or m.group("marker2") or "")
            + "tool_dispatch"
            + (m.group("post") or "").rstrip()
            + ">"
        )

    return _UNDERSCORE_DISPATCH_TAG_RE.sub(_repl, text)


def _rename_bare_dispatch_wrapper(text: str) -> str:
    """Rename the ``dispatch`` wrapper tag to ``tool_dispatch``.

    DeepSeek Pro sometimes emits ``<DSML|dispatch>`` without the leading
    underscore.  Rename to canonical ``<DSML|tool_dispatch>``.
    """
    if not text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        return (
            "<"
            + (m.group("slash") or "")
            + (m.group("fw") or "")
            + (m.group("marker") or m.group("marker2") or "")
            + "tool_dispatch"
            + (m.group("post") or "").rstrip()
            + ">"
        )

    return _BARE_DISPATCH_TAG_RE.sub(_repl, text)


def _rename_bare_calls_wrapper(text: str) -> str:
    """Rename the ``calls`` wrapper tag to ``tool_calls``.

    DeepSeek Pro sometimes emits ``<DSML|calls>`` without the leading
    underscore.  Rename to canonical ``<DSML|tool_calls>``.
    """
    if not text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        return (
            "<"
            + (m.group("slash") or "")
            + (m.group("fw") or "")
            + (m.group("marker") or m.group("marker2") or "")
            + "tool_calls"
            + (m.group("post") or "").rstrip()
            + ">"
        )

    return _BARE_CALLS_TAG_RE.sub(_repl, text)


def _rename_underscore_calls_wrapper(text: str) -> str:
    """Rename the ``_calls`` wrapper tag to ``tool_calls``.

    DeepSeek Pro emits ``<..._calls>`` instead of the canonical
    ``<...tool_calls>`` wrapper.  The parser only recognises ``tool_calls``,
    so we rewrite the tag name while preserving the ``<`` / ``</`` prefix.
    """
    if not text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        return (
            "<"
            + (m.group("slash") or "")
            + (m.group("fw") or "")
            + (m.group("marker") or m.group("marker2") or "")
            + "tool_calls"
            + (m.group("post") or "").rstrip()
            + ">"
        )

    return _UNDERSCORE_CALLS_TAG_RE.sub(_repl, text)


def _rename_underscore_calls_inner(inner: str) -> str:
    """Rename ``_calls`` -> ``tool_calls`` inside a tag body (no brackets)."""
    wrapped = "<" + inner + ">"
    out = _rename_underscore_calls_wrapper(wrapped)
    return out[1:-1] if out.startswith("<") and out.endswith(">") else inner


def _rename_underscore_dispatch_inner(inner: str) -> str:
    """Rename ``_dispatch`` -> ``tool_dispatch`` inside a tag body (no brackets)."""
    wrapped = "<" + inner + ">"
    out = _rename_underscore_dispatch_wrapper(wrapped)
    return out[1:-1] if out.startswith("<") and out.endswith(">") else inner


def _rename_bare_dispatch_inner(inner: str) -> str:
    """Rename ``dispatch`` -> ``tool_dispatch`` inside a tag body (no brackets)."""
    wrapped = "<" + inner + ">"
    out = _rename_bare_dispatch_wrapper(wrapped)
    return out[1:-1] if out.startswith("<") and out.endswith(">") else inner


def _rename_bare_calls_inner(inner: str) -> str:
    """Rename ``calls`` -> ``tool_calls`` inside a tag body (no brackets)."""
    wrapped = "<" + inner + ">"
    out = _rename_bare_calls_wrapper(wrapped)
    return out[1:-1] if out.startswith("<") and out.endswith(">") else inner


def _strip_lone_tag_pipes(inner: str) -> str:
    """Drop lone pipes wrapping a bare tag name (``<|invoke>`` -> ``<invoke>``).

    Marker-prefixed tags are kept in canonical ``|DSML|tag`` form.  Used on
    the tag body (the text between ``<`` and ``>``).
    Bare marker tags without a tag name (e.g. ``<|DSML|>`` / ``</|DSML|>``)
    act as tool call block wrappers and are normalized to ``tool_calls`` / ``/tool_calls``.
    """
    is_close = inner.startswith("/")
    rest = inner[1:] if is_close else inner
    marker = re.match(
        r"\|+\s*((?:TOOL|DSML|tool|dsml|TS|ts))\s*\|+", rest, re.IGNORECASE
    )
    if marker:
        after = rest[marker.end() :].lstrip()
        if not after:
            return "/tool_calls" if is_close else "tool_calls"
        if re.match(r"^tool_?calls?\b", after, re.IGNORECASE):
            after = re.sub(r"^tool_?calls?\b", "tool_calls", after, count=1, flags=re.IGNORECASE)
        elif re.match(r"^calls?\b", after, re.IGNORECASE):
            after = re.sub(r"^calls?\b", "tool_calls", after, count=1, flags=re.IGNORECASE)
        elif re.match(r"^tool_?dispatch\b", after, re.IGNORECASE):
            after = re.sub(r"^tool_?dispatch\b", "tool_dispatch", after, count=1, flags=re.IGNORECASE)
        elif re.match(r"^dispatch\b", after, re.IGNORECASE):
            after = re.sub(r"^dispatch\b", "tool_dispatch", after, count=1, flags=re.IGNORECASE)
        rebuilt = "|" + marker.group(1) + "|" + after
        return ("/" if is_close else "") + rebuilt
    stripped = rest.lstrip("|").strip("|").lstrip()
    stripped = re.sub(r"^([A-Za-z_][A-Za-z0-9_]*)\|+", r"\1", stripped)
    return ("/" if is_close else "") + stripped


_TAG_REGION_RE = re.compile(r"<[^>]*>")


def _normalize_tag_delimiters(text: str) -> str:
    """Normalize DSML delimiters strictly inside ``<...>`` regions.

    Converts full-width pipes to ASCII, collapses double pipes, renames a
    ``_calls`` wrapper to ``tool_calls`` and drops lone pipes around bare tag
    names (``<|invoke>`` -> ``<invoke>``).  Marker-prefixed tags are kept in
    canonical ``<|DSML|tag>`` form.  Text outside ``<...>`` is left alone, so
    full-width pipe characters in regular prose are never corrupted.

    Used by StreamSieve so its (ASCII, case-sensitive) TOOL_STARTS /
    CLOSE_TAGS detection sees one canonical form per chunk.
    """
    if not text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        inner = m.group(0)[1:-1]
        if not inner:
            return m.group(0)
        inner = inner.replace(_FW_PIPE, "|")
        inner = _DOUBLE_PIPE_RE.sub(_pipe_single, inner)
        inner = _rename_underscore_calls_inner(inner)
        inner = _rename_underscore_dispatch_inner(inner)
        inner = _rename_bare_dispatch_inner(inner)
        inner = _rename_bare_calls_inner(inner)
        inner = _strip_lone_tag_pipes(inner)
        return "<" + inner + ">"

    return _TAG_REGION_RE.sub(_repl, text)


def _fix_unclosed_invoke_before_tool_calls_close(text: str) -> str:
    """If an <invoke> inside <tool_calls> is missing its </invoke> before </tool_calls>, close it."""
    def _repl(m: re.Match) -> str:
        body = m.group(0)
        opens = len(re.findall(r'<invoke\b', body, re.IGNORECASE))
        closes = len(re.findall(r'</invoke\s*>', body, re.IGNORECASE))
        if opens > closes:
            diff = opens - closes
            idx = body.rfind('</tool_calls>')
            if idx != -1:
                return body[:idx] + ('</invoke>\n' * diff) + body[idx:]
        return body

    return re.sub(
        r'<tool_calls\b[^>]*>.*?</tool_calls\s*>',
        _repl,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def _normalize_bare_dsml_wrapper(text: str) -> str:
    """Normalize standalone <|DSML|> / </|DSML|> tags to <tool_calls> / </tool_calls>."""
    text = re.sub(r'<[|｜]+(?:DSML|TOOL)[|｜]+\s*>', '<tool_calls>', text, flags=re.IGNORECASE)
    text = re.sub(r'</[|｜]+(?:DSML|TOOL)[|｜]+\s*>', '</tool_calls>', text, flags=re.IGNORECASE)
    return text


def _normalize_dsml(text: str) -> str:
    """Run all DSML input normalisations (cheap order-sensitive passes).

    Callers should run this before any DSML/tool-call parsing so that
    regex patterns downstream see a canonical form.
    """
    if not text:
        return text
    text = _fix_missing_lt(text)
    text = _collapse_double_pipes(text)
    text = _normalize_bare_dsml_wrapper(text)
    text = _rename_underscore_calls_wrapper(text)
    text = _rename_underscore_dispatch_wrapper(text)
    text = _rename_bare_dispatch_wrapper(text)
    text = _rename_bare_calls_wrapper(text)
    text = _fix_inverted_dsml_close(text)
    text = _fix_unclosed_invoke_before_tool_calls_close(text)
    return text


def _inside_parameter_block(text: str, pos: int) -> bool:
    """Check if *pos* is inside a ``<parameter name="...">...</parameter>`` block.

    DeepSeek may nest DSML-like content inside parameter values (e.g. Write tool call
    writing code that contains ``<invoke name="Read">``).  This helper detects whether
    a given character position lies inside a parameter block so that invoke-detection
    logic can skip it.

    Uses depth-counting so that DSML-like strings inside parameter values
    (e.g. ``</parameter>`` in the code being written) do not confuse detection.
    """
    param_open_re = re.compile(
        r'<(?:\|?(?:TOOL|DSML)\|?)?\s*parameter\s+name=["\'][^"\']*["\'][^>]*>',
        re.IGNORECASE,
    )
    param_close_re = re.compile(
        r"</(?:\|?(?:TOOL|DSML)\|?)?\s*parameter\s*>",
        re.IGNORECASE,
    )
    boundary_re = re.compile(
        r"</(?:\|?(?:TOOL|DSML)\|?)?\s*(?:invoke|tool_?calls?)[^>]*>|<(?:\|?(?:TOOL|DSML)\|?)?\s*tool_?calls?[^>]*>",
        re.IGNORECASE,
    )
    depth = 0
    scan = 0
    while scan < pos:
        om = param_open_re.search(text, scan, pos)
        cm = param_close_re.search(text, scan, pos)
        bm = boundary_re.search(text, scan, pos)

        next_events = []
        if om:
            next_events.append((om.start(), "open", om))
        if cm:
            next_events.append((cm.start(), "close", cm))
        if bm:
            next_events.append((bm.start(), "boundary", bm))

        if not next_events:
            break

        next_events.sort(key=lambda x: x[0])
        _, event_type, m = next_events[0]

        if event_type == "open":
            depth += 1
            scan = m.end()
        elif event_type == "close":
            depth = max(0, depth - 1)
            scan = m.end()
        elif event_type == "boundary":
            # Parameter cannot span outside its enclosing invoke or tool_calls block
            depth = 0
            scan = m.end()

    return depth > 0


def _find_balanced_invokes(
    text: str,
    is_container_body: bool = False,
) -> list[tuple[int, int, str, str]]:
    """Find balanced <invoke name="...">...</invoke> blocks handling nested <invoke> tags.

    Standard regex with .*? (non-greedy) fails when DeepSeek uses nested <invoke>
    for parameter values (e.g. <invoke name="Read"><invoke name="file_path">val</invoke>).
    This function manually tracks tag depth for correct nesting.

    **Sanitisation**: invoke tags that appear inside ``<parameter>…</parameter>``
    blocks are skipped so that DSML-like content in tool arguments (e.g. code
    containing ``<invoke name="Read">``) does not confuse the parser.

    Returns [(start_pos, end_pos, tool_name, inner_text), ...]
    """
    results: list[tuple[int, int, str, str]] = []
    open_tag_re = re.compile(
        r'<(?:\|?(?:TOOL|DSML)\|?)?\s*invoke\s+name=["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    close_tag_re = re.compile(
        r"</(?:\|?(?:TOOL|DSML)\|?)?\s*invoke\s*>",
        re.IGNORECASE,
    )
    container_close_re = re.compile(
        r"</(?:\|?(?:TOOL|DSML)\|?)?(?:tool_?calls?|toolcall|tool_dispatch)[^>]*>|<[|｜]+(?:DSML|TOOL)[|｜]+>|/[|｜]+(?:DSML|TOOL)[|｜]+>",
        re.IGNORECASE,
    )

    pos = 0
    while pos < len(text):
        om = open_tag_re.search(text, pos)
        if not om:
            break

        # Skip invoke tags that are inside a <parameter> block — they belong to
        # tool-argument content, not the structural DSML tree.
        if _inside_parameter_block(text, om.start()):
            pos = om.end()
            continue

        name = om.group(1).strip()
        # Find closing > of the opening tag
        gt = text.find(">", om.end())
        if gt == -1:
            break

        content_start = gt + 1
        depth = 1
        scan_pos = content_start

        while depth > 0 and scan_pos < len(text):
            cm = close_tag_re.search(text, scan_pos)
            if not cm:
                # Unclosed invoke: find container closing tag or next invoke opener
                nom = open_tag_re.search(text, content_start)
                ccm = container_close_re.search(text, content_start)

                cutoffs = []
                if is_container_body:
                    cutoffs.append(len(text))
                if nom:
                    cutoffs.append(nom.start())
                if ccm:
                    cutoffs.append(ccm.start())

                if not cutoffs:
                    # Incomplete/truncated stream without closing tag or next invoke
                    depth = 0
                    break

                end_pos = min(cutoffs)
                inner = text[content_start:end_pos]
                results.append((om.start(), end_pos, name, inner.strip()))
                scan_pos = end_pos
                depth = 0
                break

            # Skip close tags that are inside a <parameter> block — they belong
            # to tool-argument content (e.g. </invoke> in code being written).
            if _inside_parameter_block(text, cm.start()):
                scan_pos = cm.end()
                continue

            # Is there a nested opening tag between scan_pos and cm.start()?
            nom = open_tag_re.search(text, scan_pos, cm.start())
            if nom:
                # Skip nested invokes inside <parameter> blocks — they belong
                # to tool-argument content (e.g. <invoke name="Read"> in code
                # being written). Advance past the false open and re-check the
                # same close tag.
                if _inside_parameter_block(text, nom.start()):
                    ngt = text.find(">", nom.end())
                    scan_pos = ngt + 1 if ngt != -1 else cm.end()
                    continue
                depth += 1
                # Advance past this nested opening tag's >
                ngt = text.find(">", nom.end())
                scan_pos = ngt + 1 if ngt != -1 else cm.end()
            else:
                depth -= 1
                if depth == 0:
                    inner = text[content_start : cm.start()]
                    results.append((om.start(), cm.end(), name, inner.strip()))
                    scan_pos = cm.end()
                else:
                    scan_pos = cm.end()

        pos = scan_pos

    return results


def parse_dsml_tool_calls(
    text: str,
    tool_names: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    if not text:
        return [], text

    tool_names = tool_names or []
    # Fix missing < on DSML/TOOL tags AND normalise inverted close tags
    # (``<|DSML|/invoke>`` -> ``</|DSML|invoke>``) before further parsing.
    text = _normalize_dsml(text)
    normalized = strip_dsml_markup(text)

    blocks: list[str] = []
    block_spans: list[tuple[int, int]] = []
    for m in TOOL_CALLS_PATTERN.finditer(normalized):
        blocks.append(m.group(1))
        block_spans.append((m.start(), m.end()))

    tool_calls: list[dict] = []
    seen_keys: set[str] = set()

    def _add_tc(tc: dict | None) -> None:
        if tc is None:
            return
        key = f"{tc.get('name', '')}:{tc.get('arguments', '')}"
        if key not in seen_keys:
            seen_keys.add(key)
            tool_calls.append(tc)

    # Use balanced matching instead of regex .*? to handle nested <invoke> tags
    for block_text in blocks:
        for _start, _end, name, inner in _find_balanced_invokes(block_text, is_container_body=True):
            resolved = _resolve_tool_name(name, tool_names)
            args = _parse_parameters(inner)
            _add_tc(_format_tool_call(resolved, args))

    # Also parse standalone <invoke> tags without <tool_calls> wrapper
    for _start, _end, name, inner in _find_balanced_invokes(normalized):
        # Skip invokes that are inside a <tool_calls> block (already parsed above)
        if any(bs <= _start < be for bs, be in block_spans):
            continue
        resolved = _resolve_tool_name(name, tool_names)
        args = _parse_parameters(inner)
        _add_tc(_format_tool_call(resolved, args))

    # Also parse legacy <tool_call name="..."> (no <tool_calls> wrapper)
    for tc in _parse_legacy_tool_calls(normalized, tool_names):
        _add_tc(tc)

    # Filter out empty stutter calls (e.g. model emitted <invoke name="X"> followed by another <invoke name="X"> with real args)
    non_empty_tools = {
        tc.get("name")
        for tc in tool_calls
        if tc.get("arguments") and tc["arguments"] not in ("{}", '{"command": ""}', '{"command":""}')
    }
    if non_empty_tools:
        tool_calls = [
            tc for tc in tool_calls
            if not (tc.get("name") in non_empty_tools and tc.get("arguments") in ("{}", '{"command": ""}', '{"command":""}'))
        ]

    # Fallback to bracket tool calls: [调用 ToolName] {json}
    if not tool_calls:
        b_calls, b_cleaned = parse_bracket_tool_calls(text, tool_names)
        if b_calls:
            return b_calls, b_cleaned

    cleaned = clean_tool_text(text) if len(text) < 200_000 else ""
    return tool_calls, cleaned


LEGACY_TOOL_CALL_PATTERN = re.compile(
    r'<tool_call\s+name=["\']([^"\']+)["\'][^>]*>(.*?)</tool_call\s*>',
    re.DOTALL | re.IGNORECASE,
)

# Fallback: <argument key="..." value="..."> (model's trained format when DSML ignored)
ARGUMENT_ATTR_PATTERN = re.compile(
    r'<argument\s+key=["\']([^"\']+)["\']\s+value=["\']([^"\']*)["\']\s*/?\s*>',
    re.DOTALL | re.IGNORECASE,
)


def _parse_legacy_tool_calls(
    text: str,
    tool_names: list[str],
) -> list[dict]:
    """Parse legacy ``<tool_call name="ToolName">`` (no ``<tool_calls>`` wrapper)."""
    calls: list[dict] = []
    for m in LEGACY_TOOL_CALL_PATTERN.finditer(text):
        name = m.group(1).strip()
        inner = m.group(2)
        resolved = _resolve_tool_name(name, tool_names)
        args = _parse_parameters(inner)
        tc = _format_tool_call(resolved, args)
        if tc:
            calls.append(tc)
    return calls


def _parse_parameters(inner_text: str) -> Dict[str, Any]:
    """Parse ``<parameter name="key">value</parameter>`` blocks.

    Uses depth-counting instead of non-greedy regex so that DSML-like strings
    inside parameter values (e.g. ``</parameter>`` in code being written) do not
    cause premature truncation.
    """
    args: dict[str, Any] = {}

    param_open_re = re.compile(
        r'<(?:\|?(?:TOOL|DSML)\|?)?parameter(?:\s+[^>]*?)?\s+name=["\']([^"\']+)["\'](?:\s+[^>]*?)?>',
        re.IGNORECASE,
    )
    param_close_re = re.compile(
        r"</(?:\|?(?:TOOL|DSML)\|?)?parameter\s*>",
        re.IGNORECASE,
    )

    pos = 0
    while pos < len(inner_text):
        om = param_open_re.search(inner_text, pos)
        if not om:
            break
        key = om.group(1).strip()

        gt = om.end()  # param_open_re includes the closing >, so end() is past it
        content_start = gt

        depth = 1
        scan_pos = content_start
        value = ""

        while depth > 0 and scan_pos < len(inner_text):
            cm = param_close_re.search(inner_text, scan_pos)
            if not cm:
                value = inner_text[content_start:]
                scan_pos = len(inner_text)
                break

            # Check for nested parameter opens (e.g. DSML content inside values)
            nom = param_open_re.search(inner_text, scan_pos, cm.start())
            if nom:
                # Skip if this nested open is inside the current parameter's
                # value — there is content before it within the value, so it
                # is not a structural parameter but part of the content text.
                _pre = inner_text[content_start : nom.start()].strip()
                if _pre:
                    # Fake nested open inside value; skip past it and continue
                    ngt = inner_text.find(">", nom.end())
                    scan_pos = ngt + 1 if ngt != -1 else cm.end()
                    continue
                depth += 1
                ngt = inner_text.find(">", nom.end())
                scan_pos = ngt + 1 if ngt != -1 else cm.end()
            else:
                # Check if this close might be a fake </parameter> inside the
                # current parameter's value (e.g. code being written contains
                # literal </parameter>). Heuristic: if what follows is non-XML raw text
                # (does not start with '<'), it is likely a fake close inside code.
                _after = inner_text[cm.end() :].lstrip()
                if _after and not _after.startswith("<"):
                    scan_pos = cm.end()
                    continue
                depth -= 1
                if depth == 0:
                    value = inner_text[content_start : cm.start()]
                scan_pos = cm.end()

        val = _extract_cdata(value.strip())
        # Unescape triple quotes that came through JSON encoding in XML tool calls
        val = val.replace('\\"\\"\\"', '"""').replace("\\'\\'\\'", "'''")
        typed_val = _auto_type(val)
        if key in args:
            existing = args[key]
            if isinstance(existing, list):
                existing.append(typed_val)
            else:
                args[key] = [existing, typed_val]
        else:
            args[key] = typed_val
        pos = scan_pos

    # Fallback 1: Parse standard XML child nodes like <parameter_name>value</parameter_name> or <description string="true">value</description>
    xml_nodes = re.finditer(
        r"<([a-zA-Z0-9_-]+)(?:\s+[^>]*?)?>(.*?)</\1>", inner_text, re.DOTALL
    )
    for m in xml_nodes:
        key = m.group(1).strip()
        if key in ("tool_call", "tool_calls", "invoke", "parameter", "argument"):
            continue
        val = _auto_type(
            m.group(2)
            .strip()
            .replace('\\"\\"\\"', '"""')
            .replace("\\'\\'\\'", "'''")
        )
        if key not in args:
            args[key] = val
        elif isinstance(args[key], list):
            args[key].append(val)

    # Fallback 1b: nested <invoke name="key">value</invoke> as parameters
    # DeepSeek sometimes uses <invoke> for both the tool call wrapper AND parameter values,
    # e.g. <invoke name="Read"><invoke name="file_path">val</invoke>...</invoke>
    # Always runs (even if args exists from <parameter> tags) to catch mixed formats.
    for m in re.finditer(
        r'<(?:\|?(?:TOOL|DSML)\|?)?invoke\s+name=["\']([^"\']+)["\'][^>]*>(.*?)</(?:\|?(?:TOOL|DSML)\|?)?invoke\s*>',
        inner_text,
        re.DOTALL | re.IGNORECASE,
    ):
        key = m.group(1).strip()
        val = _auto_type(
            m.group(2).strip().replace('\\"\\"\\"', '"""').replace("\\'\\'\\'", "'''")
        )
        if key in ("tool_call", "tool_calls", "invoke", "parameter"):
            continue  # skip structural tags
        if key not in args:  # don't overwrite existing <parameter> values
            args[key] = val

    # Fallback 2: <argument key="..." value="..."> (model's own trained format)
    if not args:
        for m in ARGUMENT_ATTR_PATTERN.finditer(inner_text):
            key = m.group(1).strip()
            val = _auto_type(
                m.group(2).replace('\\"\\"\\"', '"""').replace("\\'\\'\\'", "'''")
            )
            if key in args:
                existing = args[key]
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    args[key] = [existing, val]
            else:
                args[key] = val

    return args


def _format_tool_call(name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    return {
        "name": name,
        "arguments": json.dumps(args, ensure_ascii=False),
    }


def format_tool_calls_for_prompt(tool_calls_raw: Any) -> str:
    if isinstance(tool_calls_raw, str):
        try:
            tool_calls_raw = json.loads(tool_calls_raw)
        except (json.JSONDecodeError, ValueError):
            return ""
    if not isinstance(tool_calls_raw, list) or not tool_calls_raw:
        return ""

    blocks: list[str] = []
    for tc in tool_calls_raw:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function", {})
        name = tc.get("name") or fn.get("name", "")
        if not name:
            continue
        args_raw = tc.get("arguments") or fn.get("arguments") or "{}"
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except (json.JSONDecodeError, ValueError):
                args = {"content": args_raw}
        else:
            args = args_raw

        params = _format_params_dsml(args)
        if params.strip():
            block = f'  <|DSML|invoke name="{name}">\n{params}\n  </|DSML|invoke>'
        else:
            block = f'  <|DSML|invoke name="{name}"></|DSML|invoke>'
        blocks.append(block)

    if not blocks:
        return ""

    return "<|DSML|tool_calls>\n" + "\n".join(blocks) + "\n</|DSML|tool_calls>"


def parse_json_tool_calls(text: str) -> tuple[list[dict], str]:
    """Parse ```tool_call JSON blocks from model output.

    Returns (tool_calls, cleaned_text) where cleaned_text has the
    code blocks removed. Also handles ```json blocks as fallback.
    """
    if not text:
        return [], text

    cleaned = text
    tool_calls: list[dict] = []

    # Try ```tool_call first, then fallback to ```json, then plain ``` fences (must have newline after backticks)
    for pattern in [
        JSON_TOOL_CALL_PATTERN,
        re.compile(r"```json\s*\n?(.*?)```", re.DOTALL),
        re.compile(r"```[ \t]*\n(.*?)```", re.DOTALL),
        re.compile(r"<tool_call>\s*\n?(.*?)\n?</tool_call>", re.DOTALL),
        re.compile(r"<toolcall>\s*\n?(.*?)\n?</toolcall>", re.DOTALL),
    ]:
        for match in pattern.finditer(text):
            block = match.group(1).strip()
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                # Model sometimes outputs arguments as a JSON string with literal
                # newlines (e.g. "arguments": "{\n    \"key\": \"val\"\n  }" instead
                # of "{\\n    \\"key\\": \\"val\\"\\n  }"). Standard json.loads
                # rejects control characters inside strings, so try regex fallback.
                name_m = re.search(r'"name":\s*"([^"]+)"', block)
                tool_m = re.search(r'"tool":\s*"([^"]+)"', block)
                args_m = re.search(
                    r'"arguments":\s*"(.+)"\s*\}',
                    block,
                    re.DOTALL,
                )
                if (name_m or tool_m) and args_m:
                    name = (name_m or tool_m).group(1)
                    args_str = args_m.group(1).strip()
                    try:
                        args_raw = json.loads(args_str)
                    except json.JSONDecodeError:
                        args_raw = {"value": args_str}
                    tool_calls.append(
                        {
                            "name": name,
                            "arguments": json.dumps(args_raw, ensure_ascii=False),
                        }
                    )
                continue

            # Support both {"name": ..., "arguments": ...} and {"tool": ..., "arguments": ...}
            if not isinstance(parsed, dict):
                # Model sometimes outputs a JSON array instead of a single object
                # e.g. [{"name": "Read", "arguments": {...}}] — skip gracefully
                continue
            name = parsed.get("name") or parsed.get("tool", "")
            if not name:
                continue

            args_raw = parsed.get("arguments", {})
            if isinstance(args_raw, str):
                try:
                    args_raw = json.loads(args_raw)
                except json.JSONDecodeError:
                    args_raw = {"value": args_raw}

            tool_calls.append(
                {
                    "name": name,
                    "arguments": json.dumps(args_raw, ensure_ascii=False),
                }
            )

        # If we found tool calls in this pattern, don't double-parse
        if tool_calls:
            break

    if not tool_calls:
        return [], text

    # Remove all ```tool_call, ```json, ``` (plain with newline), and <tool_call>/<toolcall> blocks from text
    cleaned = re.sub(
        r"```(?:tool_call|json|[ \t]*\n).*?```",
        "",
        cleaned,
        flags=re.DOTALL,
    ).strip()
    cleaned = re.sub(
        r"<tool_call>\s*\n?.*?\n?</tool_call>",
        "",
        cleaned,
        flags=re.DOTALL,
    ).strip()
    cleaned = re.sub(
        r"<toolcall>\s*\n?.*?\n?</toolcall>",
        "",
        cleaned,
        flags=re.DOTALL,
    ).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return tool_calls, cleaned


def _format_params_dsml(args: Any, indent: str = "    ") -> str:
    if isinstance(args, dict):
        if not args:
            return ""
        return "\n".join(
            _format_param_node(k, v, indent) for k, v in sorted(args.items())
        )
    elif isinstance(args, list):
        return "\n".join(_format_param_node("item", item, indent) for item in args)
    else:
        return f'{indent}<|DSML|parameter name="content">{_cdata(str(args))}</|DSML|parameter>'


def _format_param_node(name: str, value: Any, indent: str) -> str:
    open_tag = f'<|DSML|parameter name="{_escape_xml(name)}">'
    close = "</|DSML|parameter>"
    if value is None:
        return f"{indent}{open_tag}{close}"
    elif isinstance(value, (bool, int, float)):
        return f"{indent}{open_tag}{str(value).lower() if isinstance(value, bool) else str(value)}{close}"
    elif isinstance(value, (dict, list)):
        inner = json.dumps(value, ensure_ascii=False)
        return f"{indent}{open_tag}{_cdata(inner)}{close}"
    elif isinstance(value, str):
        return f"{indent}{open_tag}{_cdata(value)}{close}"
    else:
        return f"{indent}{open_tag}{_cdata(str(value))}{close}"


def _cdata(text: str) -> str:
    if "]]>" in text:
        text = text.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{text}]]>"


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ─── Leaked output sanitizer ──────────────────────────────
# DeepSeek sometimes leaks BOS/EOS/role tokens into the model's output text.
# These must be stripped before returning to the client.

_LEAKED_MARKERS_RE = re.compile(
    r"(?i)<[｜\|]\s*(?:"
    r"begin[▁_]of[▁_]sentence|"
    r"end[▁_]of[▁_]sentence|"
    r"end[▁_]of[▁_]thinking|"
    r"end[▁_]of[▁_]toolresults|"
    r"end[▁_]of[▁_]instructions|"
    r"System|User|Assistant|Tool"
    r")\s*[｜\|]>"
)


def sanitize_leaked_output(text: str) -> str:
    """Strip leaked DSML markers (BOS, EOS, role tokens) from model output.

    DeepSeek sometimes leaks ``<｜begin▁of▁sentence｜>``,
    ``<｜end▁of▁sentence｜>``, ``<｜Assistant｜>`` etc. into the response stream.
    This removes them cleanly.
    """
    if not text:
        return text
    text = _LEAKED_MARKERS_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_tool_call_markers(text: str) -> str:
    """Remove partial ```tool_call markers from stream text fragments.

    In streaming mode, the model may emit partial markers like
    `` ```too `` before the full marker is detected. This removes
    any partial markers from text chunks.
    """
    if not text:
        return ""
    # Only remove trailing backticks if we actually matched/removed a leading tool_call/json marker
    has_tool_marker = bool(re.match(r"^\s*```(?:tool_call|json)", text))
    if has_tool_marker:
        text = re.sub(r"```(?:tool_call|json)\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
    else:
        # First, prevent trailing partial markers (requires at least one character 't' or 'j' after backticks)
        text = re.sub(
            r"```(?:t(?:o(?:o(?:l(?:_?(?:c(?:a(?:l(?:l)?)?)?)?)?)?)?)?|j(?:s(?:o(?:n)?)?)?)\s*$",
            "",
            text,
        )

        # Then, count remaining ``` fences. If odd, the trailing one is unclosed/partial, so strip it.
        # Otherwise, keep it as it closes a code block.
        fence_count = text.count("```")
        if fence_count % 2 == 1:
            text = re.sub(r"```\s*$", "", text)
    return text.strip(" \t")


_BRACKET_OPENER_RE = re.compile(
    r'(?:\[|【)\s*(?:调用|call|invoke)[:：]?\s*([a-zA-Z0-9_\-\.]+)\s*(?:\]|】)',
    re.IGNORECASE,
)


def parse_bracket_tool_calls(
    text: str,
    tool_names: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Parse bracket tool call syntax: [调用 ToolName] {"arg": "val"}.

    Supports:
    - [调用 Read] {"path": "..."}
    - [调用: Read] {"path": "..."}
    - 【调用 Read】 {"path": "..."}
    - [call Read] {"path": "..."}
    - [invoke Read] {"path": "..."}

    Returns (tool_calls, cleaned_text).
    """
    if not text:
        return [], text

    tool_names = tool_names or []
    tool_calls: list[dict] = []
    decoder = json.JSONDecoder()
    spans_to_remove: list[tuple[int, int]] = []

    for m in _BRACKET_OPENER_RE.finditer(text):
        raw_name = m.group(1).strip()
        resolved = _resolve_tool_name(raw_name, tool_names) if tool_names else raw_name

        header_end = m.end()
        after = text[header_end:]
        brace_offset = after.find("{")
        if brace_offset == -1:
            continue
        if after[:brace_offset].strip() != "":
            continue

        json_start = header_end + brace_offset
        try:
            args, end_offset = decoder.raw_decode(text[json_start:])
        except json.JSONDecodeError:
            continue

        if not isinstance(args, dict):
            args = {"value": args}

        formatted = _format_tool_call(resolved, args)
        if formatted:
            tool_calls.append(formatted)
            spans_to_remove.append((m.start(), json_start + end_offset))

    if not spans_to_remove:
        return [], text

    cleaned_parts = []
    last_idx = 0
    for s_start, s_end in spans_to_remove:
        cleaned_parts.append(text[last_idx:s_start])
        last_idx = s_end
    cleaned_parts.append(text[last_idx:])
    cleaned_text = "".join(cleaned_parts).strip(" \t\r\n")

    return tool_calls, cleaned_text
