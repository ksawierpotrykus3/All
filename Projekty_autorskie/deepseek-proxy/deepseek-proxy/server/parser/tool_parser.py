"""Tool call parsing utilities.

DEPRECATED: Replaced by dsml_sieve.py + dsml_parser.py
This module will be removed in a future cleanup.
"""
import json
import re
from collections import Counter

from server.logging import get_logger

logger = get_logger(__name__)


_CALL_MARKER = "<!-- PROXY_SID:"



def _fix_json_strings(json_str: str) -> str:
    """Helper to escape single backslashes in JSON string parameters (like Windows paths)
    while preserving already escaped characters or internal quotes.
    """
    def repl(m):
        content = m.group(1)
        normalized = content.replace('\\\\', '\\')
        escaped = re.sub(r'\\(?!")', r'\\\\', normalized)
        return f'"{escaped}"'
    return re.sub(r'"((?:[^"\\]|\\.)*)"', repl, json_str)


def _parse_param_value(raw: str):
    """Try to parse a tool param value as JSON; fall back to raw string."""
    s = raw.strip()
    if not s:
        return s
    first = s[0]
    # Only attempt JSON parse if value looks like a JSON literal
    # (starts with {, [, ", or is a number/bool/null).
    # This prevents json.loads from consuming backslashes in plain-text
    # content like 'print(\"hello\")' where \" would be treated as an escape.
    if first not in '{["-0123456789tfn':
        return s
    if first == 't' and s not in ('true',):
        return s
    if first == 'f' and s not in ('false',):
        return s
    if first == 'n' and s not in ('null',):
        return s
    try:
        val = json.loads(s)
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, ValueError):
                pass
        return val
    except (json.JSONDecodeError, ValueError):
        return s


def _get_param_type(tool_name: str, param_name: str, tools: list[dict] | None = None) -> str | None:
    if not tools:
        return None
    for t in tools:
        fn = t.get("function") or t
        if fn.get("name") == tool_name:
            params = fn.get("parameters", {})
            properties = params.get("properties", {})
            param_def = properties.get(param_name)
            if isinstance(param_def, dict):
                return param_def.get("type")
    return None


def _parse_xml_to_json_compatible(s: str, p_type: str):
    import xml.etree.ElementTree as ET

    # Wrap in root to handle multiple root elements or naked elements
    wrapped = f"<root>{s}</root>"
    try:
        root = ET.fromstring(wrapped)
    except Exception:
        # Fallback to returning raw string if XML parsing fails
        return s

    def _parse_elem(elem):
        children = list(elem)
        if not children:
            if elem.attrib:
                attribs = {}
                for k, v in elem.attrib.items():
                    if v.lower() == "true":
                        attribs[k] = True
                    elif v.lower() == "false":
                        attribs[k] = False
                    else:
                        try:
                            attribs[k] = int(v)
                        except ValueError:
                            try:
                                attribs[k] = float(v)
                            except ValueError:
                                attribs[k] = v
                return attribs
            text = (elem.text or "").strip()
            if text.lower() == "true":
                return True
            if text.lower() == "false":
                return False
            try:
                return int(text)
            except ValueError:
                try:
                    return float(text)
                except ValueError:
                    return text

        # Parse children
        res = {}
        for child in children:
            val = _parse_elem(child)
            ctag = child.tag
            if ctag in res:
                if not isinstance(res[ctag], list):
                    res[ctag] = [res[ctag]]
                res[ctag].append(val)
            else:
                res[ctag] = val

        # Handle plural container tag flattening
        tag_lower = elem.tag.lower()
        is_container = tag_lower.endswith('s') or tag_lower in ('options', 'todos', 'questions', 'items', 'list')
        if is_container:
            if len(res) == 1:
                key = list(res.keys())[0]
                val = res[key]
                if isinstance(val, list):
                    return val
                else:
                    return [val]
            elif not res:
                return []

        return res

    parsed = _parse_elem(root)
    # Since we wrapped in <root>, parsed will be a dict of the elements inside <root>.
    # If the target type is array:
    if p_type == "array":
        if isinstance(parsed, dict):
            if len(parsed) == 1:
                key = list(parsed.keys())[0]
                val = parsed[key]
                if isinstance(val, list):
                    return val
                else:
                    return [val]
            elif not parsed:
                return []
            else:
                return [parsed]
        elif isinstance(parsed, list):
            return parsed
        else:
            return [parsed]

    # If target type is object:
    if p_type == "object":
        if isinstance(parsed, dict):
            return parsed
        else:
            return {"value": parsed}

    return parsed


def _clean_xml_string(s: str) -> str:
    if not isinstance(s, str):
        return s
    # Unescape HTML/XML entities that DeepSeek encodes in XML tag content.
    # E.g.: &gt; -> >, &lt; -> <, &amp; -> &, &quot; -> ", &apos; -> '
    # This is required because valid XML must encode these chars, but we want
    # the raw Python/text content when writing to files.
    # NOTE: xml_escape() in _format_msgs doubles encodes tool results
    # (e.g. &amp; -> &amp;amp;), so target unescaping here is symmetric and correct —
    # it decodes exactly one level, restoring the original value.
    def replace_entity(m):
        entity = m.group(1)
        if entity.startswith('#x'):
            try:
                return chr(int(entity[2:], 16))
            except ValueError:
                return m.group(0)
        elif entity.startswith('#'):
            try:
                return chr(int(entity[1:]))
            except ValueError:
                return m.group(0)
        else:
            xml_entities = {
                'lt': '<',
                'gt': '>',
                'amp': '&',
                'quot': '"',
                'apos': "'"
            }
            return xml_entities.get(entity, m.group(0))
            
    s = re.sub(r'&([a-zA-Z0-9#_]+);', replace_entity, s)
    # Unescape escaped triple quotes which models often output due to JSON bias in XML tags
    s = s.replace('\\"\\"\\"', '"""')
    s = s.replace("\\'\\'\\'", "'''")
    return s


def _parse_param(raw: str, tool_name: str, param_name: str, tools: list[dict] | None = None):
    p_type = _get_param_type(tool_name, param_name, tools)
    s = raw.strip()
    
    # If the schema explicitly says it is a string, keep it as a raw string.
    # BUT: DeepSeek (JSON-biased) often wraps XML content in a JSON-encoded string,
    # e.g. <content>"def foo():\n    \"\"\"Docstring.\"\"\"\n    pass"</content>
    # In that case we must json.loads() first to strip outer quotes and unescape
    # JSON escape sequences (\\n → newline, \\\" → "), then apply _clean_xml_string
    # for any residual backslash-escaped triple-quotes the model used in the raw text.
    if p_type == "string":
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            try:
                decoded = json.loads(s)
                if isinstance(decoded, str):
                    return _clean_xml_string(decoded)
            except (json.JSONDecodeError, ValueError):
                pass
        return _clean_xml_string(s)
        
    if p_type in ("integer", "number"):
        try:
            return int(s) if p_type == "integer" else float(s)
        except ValueError:
            return s
            
    if p_type == "boolean":
        if s.lower() in ("true", "1"):
            return True
        if s.lower() in ("false", "0"):
            return False
        return s
        
    if s.startswith("<") and (p_type in ("array", "object") or param_name.lower() in ("questions", "todos", "options")):
        return _parse_xml_to_json_compatible(s, p_type or "array")

    if p_type in ("array", "object"):
        try:
            return json.loads(s)
        except:
            return s

    # Heuristic fallback if schema is not found/not specified
    known_strings = {
        "content", "code", "text", "codecontent", "replacement", "target",
        "replacementcontent", "targetcontent", "patch", "query", "script",
        "command", "sql", "expression", "prompt", "input", "value", "path", "filepath",
        # File-operation parameter names (e.g. SearchReplace, Write, Read tools)
        "file_path", "old_str", "new_str", "diff", "filename", "file_name",
        "directory", "cwd", "url", "uri", "message", "description", "title",
        "name", "body", "pattern", "glob", "prefix", "suffix", "separator",
        "format", "template", "header", "footer", "reason", "explanation",
    }
    if param_name.lower().replace("-", "_") in known_strings:
        return s

    # Default fallback to original JSON/safe parsing
    return _parse_param_value(raw)


def _parse_tool_calls(text: str, tools: list[dict] | None = None) -> list[tuple[int, int, str, str]]:
    """Parse all tool call formats. Returns [(start, end, name, args_json), ...]
    
    Primary format: {"action":"tool_call","tool_calls":[{"name":"X","arguments":{...}}]}
    Falls back to legacy XML-based formats for backward compatibility.
    """
    def extract_params(body_text, tool_name):
        p = {}
        for pm in re.finditer(r'''<parameter\s*name\s*=\s*(["'])([^"']+?)\1[^>]*>(.*?)</parameter>''', body_text, re.DOTALL):
            p[pm.group(2)] = _parse_param(pm.group(3), tool_name, pm.group(2), tools)
        for pm in re.finditer(r'''<parameter\s*name\s*=\s*(["'])([^"']+?)\1\s*value\s*=\s*(["'])(.*?)\3\s*/?>''', body_text, re.DOTALL):
            p[pm.group(2)] = _parse_param(pm.group(4), tool_name, pm.group(2), tools)
        
        # If no standard <parameter name="..."> tags were found, try matching direct parameter tags like <file_path>value</file_path>
        if not p:
            for pm in re.finditer(r'''<([a-z_][a-zA-Z0-9_]*)\b[^>]*>(.*?)</\1>''', body_text, re.DOTALL):
                p[pm.group(1)] = _parse_param(pm.group(2), tool_name, pm.group(1), tools)
            for pm in re.finditer(r'''<([a-z_][a-zA-Z0-9_]*)\b\s*value\s*=\s*(["'])(.*?)\2\s*/?>''', body_text, re.DOTALL):
                p[pm.group(1)] = _parse_param(pm.group(3), tool_name, pm.group(1), tools)
        # Fallback: nested <invoke name="key">value</invoke> as parameters
        # DeepSeek sometimes uses <invoke> for both tool call wrapper and param values
        if not p:
            for pm in re.finditer(
                r'''<invoke\s+name\s*=\s*(["'])([^"']+?)\1\s*>(.*?)</invoke>''',
                body_text, re.DOTALL,
            ):
                p[pm.group(2)] = _parse_param(pm.group(3).strip(), tool_name, pm.group(2), tools)
        return p

    results = []
    # Support tool_call and tooltool_call (with parameters either as body tags or tag attributes)
    for m in re.finditer(r'''<(?:tool_calls?|toolcall|tooltool_calls?)\b\s*[^>]*?name\s*=\s*(["'])([^"']*?)\1[^>]*>(.*?)</(?:tool_calls?|toolcall|tooltool_calls?)>''', text, re.DOTALL | re.IGNORECASE):
        name = m.group(2)
        body = m.group(3).strip()
        
        # Extract attributes from the opening tag (e.g. command="...")
        tag_content = text[m.start():text.find('>', m.start())]
        params = {}
        for am in re.finditer(r'''([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(["'])(.*?)\2''', tag_content):
            if am.group(1) != "name":
                params[am.group(1)] = _parse_param(am.group(3), name, am.group(1), tools)
                
        # Combine with body parameters (e.g. <parameter name="...">)
        body_params = extract_params(body, name)
        params.update(body_params)
        
        results.append((m.start(), m.end(), name, json.dumps(params) if params else body))
    # Support attempt_completion tags from agents
    for m in re.finditer(r'''<attempt_completion\b[^>]*>(.*?)</attempt_completion>''', text, re.DOTALL | re.IGNORECASE):
        # Translate to standard tool call format
        results.append((m.start(), m.end(), "attempt_completion", json.dumps({"result": m.group(1).strip()})))
    for m in re.finditer(r'''<tool_capability\s*name\s*=\s*(["'])([^"']*?)\1\s*>(.*?)</tool_capability>''', text, re.DOTALL):
        name = m.group(2)
        params = extract_params(m.group(3), name)
        results.append((m.start(), m.end(), name, json.dumps(params) if params else "{}"))
    for m in re.finditer(r"<mcp_file_system>(.*?)</mcp_file_system>", text, re.DOTALL):
        tn = re.search(r"<tool_name>(.*?)</tool_name>", m.group(1), re.DOTALL)
        tp = re.search(r"<tool_parameters>(.*?)</tool_parameters>", m.group(1), re.DOTALL)
        results.append((m.start(), m.end(), tn.group(1).strip() if tn else "mcp_tool", tp.group(1).strip() if tp else "{}"))
    # DeepSeek native format: <tool_use_json>{"tool_name":"...","arguments":{...}}</tool_use_json>
    for m in re.finditer(r"<tool_use_json>(.*?)</tool_use_json>", text, re.DOTALL):
        try:
            payload = json.loads(m.group(1))
            if isinstance(payload, dict):
                name = payload.get("tool_name", "unknown")
                args = json.dumps(payload.get("arguments", {}))
                results.append((m.start(), m.end(), name, args))
        except json.JSONDecodeError:
            pass
    # Build list of known tool names + snake_case aliases (e.g. AskUserQuestion -> ask_user_question)
    known_tool_names: set[str] = set()
    _snake_to_canonical: dict[str, str] = {}  # ask_user_question -> AskUserQuestion
    if tools:
        for t in tools:
            fn = t.get("function") or t
            if isinstance(fn, dict) and "name" in fn:
                n = fn["name"]
                known_tool_names.add(n)
                # Compute snake_case alias
                snake = re.sub(r'(?<!^)(?=[A-Z])', '_', n).lower()
                if snake != n:
                    _snake_to_canonical[snake] = n
                    known_tool_names.add(snake)  # also recognize snake_case in the set

    # New JSON-based format: <function_call>{"name":"...","arguments":{...}}</function_call>
    # This matches what we now inject in the system prompt — more natural for DeepSeek.
    for m in re.finditer(r"<function_call>(.*?)</function_call>", text, re.DOTALL):
        try:
            payload = json.loads(m.group(1))
            if isinstance(payload, dict):
                name = payload.get("name", "unknown")
                args = json.dumps(payload.get("arguments", {}))
                results.append((m.start(), m.end(), name, args))
        except json.JSONDecodeError:
            # Fallback: model may output bare tool name instead of JSON inside <function_call>
            # e.g. <function_call>LS</function_call> or nested <function_call>\n<function_call>LS\n<function_call>
            inner = m.group(1).strip()
            bare_text = re.sub(r'<[^>]*>', '', inner).strip()
            canonical = _snake_to_canonical.get(bare_text, bare_text)
            if canonical in known_tool_names:
                results.append((m.start(), m.end(), canonical, "{}"))
    # Multiple function calls: <function_calls>[{"name":..., "arguments":{...}},...]</function_calls>
    for m in re.finditer(r"<function_calls>(.*?)</function_calls>", text, re.DOTALL):
        try:
            payload = json.loads(m.group(1))
            if isinstance(payload, list):
                for fc in payload:
                    if isinstance(fc, dict):
                        name = fc.get("name", "unknown")
                        args = json.dumps(fc.get("arguments", {}))
                        results.append((m.start(), m.end(), name, args))
        except json.JSONDecodeError:
            pass
    # Claude/Trae invoke format: <invoke name="ToolName"><parameter name="x">v</parameter>...</invoke>
    # Use balanced matching to handle DeepSeek's nested <invoke> for parameter values
    _invoke_open_re = re.compile(r'''<invoke\s*name\s*=\s*(["'])([^"']*?)\1\s*>''', re.DOTALL)
    _invoke_close_re = re.compile(r'</invoke\s*>', re.DOTALL)
    _ipos = 0
    while _ipos < len(text):
        _im = _invoke_open_re.search(text, _ipos)
        if not _im:
            break
        _name = _im.group(2)
        _content_start = _im.end()
        _idepth = 1
        _scan = _content_start
        while _idepth > 0 and _scan < len(text):
            _icm = _invoke_close_re.search(text, _scan)
            if not _icm:
                break
            _iom = _invoke_open_re.search(text, _scan, _icm.start())
            if _iom:
                _idepth += 1
                _scan = _iom.end()
            else:
                _idepth -= 1
                if _idepth == 0:
                    _body = text[_content_start:_icm.start()].strip()
                    _params = extract_params(_body, _name)
                    results.append((_im.start(), _icm.end(), _name, json.dumps(_params) if _params else "{}"))
                    _scan = _icm.end()
                else:
                    _scan = _icm.end()
        if _idepth > 0:
            break
        _ipos = _scan
    # Trae MCP tool call format: <use_mcp_tool name="ToolName" server="MCP_Server" arguments='{"param": "val"}'>content</use_mcp_tool>
    for m in re.finditer(r'''<use_mcp_tool\b\s*([^>]*?)>(?:.*?)</use_mcp_tool>''', text, re.DOTALL):
        attrs = m.group(1).strip()
        name_match = re.search(r'''name\s*=\s*(["'])([^"']*?)\1''', attrs)
        if not name_match:
            continue
        tool_name = name_match.group(2)
        args_match = re.search(r'''arguments\s*=\s*(["'])(.*?)\1''', attrs, re.DOTALL)
        if args_match:
            args_str = args_match.group(2)
            try:
                args_parsed = json.loads(args_str)
                results.append((m.start(), m.end(), tool_name, json.dumps(args_parsed)))
            except json.JSONDecodeError:
                results.append((m.start(), m.end(), tool_name, args_str))
        else:
            results.append((m.start(), m.end(), tool_name, "{}"))
    reserved_tags = {"parameter", "tool_call", "tool_calls", "toolcall", "tool_capability", "tool_use_json", "invoke", "mcp_file_system", "tool_result", "root", "thinking", "thought", "function_call", "function_calls", "use_mcp_tool"}

    # Match any XML tag whose name is a known tool name (CamelCase or snake_case) OR starts with a capital letter
    for m in re.finditer(r'''<([a-zA-Z0-9_]+)\b\s*([^>]*?)>(.*?)</\1>''', text, re.DOTALL):
        name = m.group(1)
        if name in reserved_tags:
            continue
        # Normalize snake_case -> CamelCase (e.g. ask_user_question -> AskUserQuestion)
        canonical_name = _snake_to_canonical.get(name, name)
        # Accept if known, or starts with uppercase, or is a valid lowercase identifier (like run_mcp)
        if not (canonical_name in known_tool_names or 
                (canonical_name[0].isupper() and canonical_name[0].isalpha()) or 
                (canonical_name[0].islower() and re.match(r'^[a-z_][a-z0-9_]*$', canonical_name))):
            continue
        name = canonical_name  # use canonical name for the emitted tool call
            
        attrs = m.group(2).strip()
        body = m.group(3).strip()
        params = {}
        
        # Parse attributes (e.g. name="value")
        for am in re.finditer(r'''([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(["'])(.*?)\2''', attrs):
            params[am.group(1)] = _parse_param(am.group(3), name, am.group(1), tools)
            
        # Parse child elements in body
        for pm in re.finditer(r'''<([a-z_][a-zA-Z0-9_]*)\b[^>]*>(.*?)</\1>''', body, re.DOTALL):
            params[pm.group(1)] = _parse_param(pm.group(2), name, pm.group(1), tools)
        for pm in re.finditer(r'''<([a-z_][a-zA-Z0-9_]*)\b\s*value\s*=\s*(["'])(.*?)\2\s*/?>''', body, re.DOTALL):
            params[pm.group(1)] = _parse_param(pm.group(3), name, pm.group(1), tools)
            
        if params:
            results.append((m.start(), m.end(), name, json.dumps(params)))

    # Self-closing tags
    for m in re.finditer(r'''<([a-zA-Z0-9_]+)\b\s*([^>]*?)/\s*>''', text):
        name = m.group(1)
        if name in reserved_tags:
            continue
        canonical_name = _snake_to_canonical.get(name, name)
        # Accept if known, or starts with uppercase, or is a valid lowercase identifier (like run_mcp)
        if not (canonical_name in known_tool_names or 
                (canonical_name[0].isupper() and canonical_name[0].isalpha()) or 
                (canonical_name[0].islower() and re.match(r'^[a-z_][a-z0-9_]*$', canonical_name))):
            continue
        name = canonical_name
            
        attrs = m.group(2).strip()
        params = {}
        for am in re.finditer(r'''([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(["'])(.*?)\2''', attrs):
            params[am.group(1)] = _parse_param(am.group(3), name, am.group(1), tools)
        if params:
            results.append((m.start(), m.end(), name, json.dumps(params)))
    # Pattern: [调用ToolName]{json}
    for m in re.finditer(rf"\[{_CALL_MARKER}\s*(\w+)\]\s*(\{{)", text):
        brace_start = m.start(2)
        depth = 0
        i = brace_start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    body = text[brace_start:i+1]
                    try:
                        fixed_body = _fix_json_strings(body)
                        parsed = json.loads(fixed_body)
                        if isinstance(parsed, dict):
                            results.append((m.start(), i+1, m.group(1), fixed_body))
                    except:
                        pass
                    break
            i += 1
    # Raw JSON tool call format: {"tool_name": "...", "arguments": {...}} or {"tool": "...", "arguments": {...}} or {"function": "...", "arguments": {...}}
    # Matches JSON objects that contain a tool indicator key
    for m in re.finditer(r'\{\s*"(?:tool_name|tool|function)"\s*:', text):
        brace_start = m.start()
        depth = 0
        i = brace_start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    body = text[brace_start:i+1]
                    try:
                        payload = json.loads(body)
                        if isinstance(payload, dict):
                            # Normalize tool name keys
                            name = payload.get("tool_name") or payload.get("tool") or payload.get("function")
                            # Normalize arguments keys
                            args_payload = payload.get("arguments") or payload.get("parameters") or {}
                            if name and isinstance(name, str):
                                args = json.dumps(args_payload) if isinstance(args_payload, dict) else str(args_payload)
                                results.append((brace_start, i+1, name, args))
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
            i += 1
    results.sort(key=lambda x: (x[0], x[2]))  # sort by start pos, then name
    # Content-array format: [{"type": "text", "text": "{...JSON with tool params...}"}]
    # DeepSeek sometimes hallucinates the OpenAI message content-array format instead of
    # emitting XML tool call tags. We detect this and try to extract the tool call from
    # the embedded JSON string.
    for m in re.finditer(r'\[\s*\{\s*"type"\s*:\s*"text"\s*,\s*"text"\s*:\s*("(?:[^"\\]|\\.)*")\s*\}\s*\]', text, re.DOTALL):
        try:
            inner_text = json.loads(m.group(1))  # unescape the "text" value
            inner_obj = json.loads(inner_text)    # parse the tool-params JSON inside
            if isinstance(inner_obj, dict):
                # Try to find a tool name from context (the JSON keys are the params)
                # e.g. {"command": "...", "cwd": "...", "blocking": true} → RunCommand
                # We can't reliably guess tool name from params alone, but we can check
                # against known tool schemas.
                if tools:
                    param_keys = set(inner_obj.keys())
                    best_match = None
                    best_score = 0
                    for t in tools:
                        fn = t.get("function") or t
                        if not isinstance(fn, dict):
                            continue
                        t_name = fn.get("name", "")
                        t_params_schema = fn.get("parameters", {}).get("properties", {})
                        t_params = set(t_params_schema.keys())
                        if not t_params:
                            continue
                        overlap = len(param_keys & t_params)
                        if overlap > best_score:
                            best_score = overlap
                            best_match = t_name
                    if best_match and best_score >= 1:
                        logger.info(f"[DETECT_TOOL] content-array format detected, matched tool='{best_match}' (overlap={best_score} params)")
                        results.append((m.start(), m.end(), best_match, json.dumps(inner_obj)))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    unique = []
    for r in results:
        if not unique:
            unique.append(r)
        elif r[0] >= unique[-1][1]:
            # Non-overlapping: starts after or at previous end
            unique.append(r)
        elif r[0] == unique[-1][0]:
            # Same start position, different name (e.g., function_calls with multiple calls)
            # Allow if different name and not overlapping previous entries at same pos
            already_at_pos = [x for x in unique if x[0] == r[0]]
            if all(x[2] != r[2] for x in already_at_pos):
                unique.append(r)
    return unique


def _auto_close_tags(text: str) -> str:
    """Finds all unclosed XML tags in the text and appends corresponding closing tags
    in reverse order to fix truncated tool call chunks on stream end.
    Handles truncated tag openers (missing >) and partial attribute assignments gracefully.
    """
    # 1. Handle truncated tag opener (missing '>' bracket at the end)
    last_open = text.rfind('<')
    if last_open != -1:
        suffix = text[last_open:]
        if '>' not in suffix:
            tag_name_match = re.match(r'^<([a-zA-Z0-9_]+)', suffix)
            if tag_name_match:
                tag_name = tag_name_match.group(1)
                # Strip incomplete attribute assignments at the end (e.g. key= or key="val)
                cleaned_suffix = re.sub(r'\s*[a-zA-Z0-9_]+=\s*(?:"[^"]*|\'[^\']*|)$', '', suffix)
                text = text[:last_open] + cleaned_suffix + '>' + f"</{tag_name}>"
                return text

    # 2. Standard auto-close for complete tags
    opened_tags = []
    for m in re.finditer(r'<([a-zA-Z0-9_]+)(?:\s+[^>]*?)?>', text):
        tag_name = m.group(1)
        if text[m.start():m.end()].endswith('/>'):
            continue
        opened_tags.append((tag_name, m.start()))

    opened_counts: Counter[str] = Counter(tag_name for tag_name, _ in opened_tags)
    closed_counts: Counter[str] = Counter()
    for m in re.finditer(r'</([a-zA-Z0-9_]+)>', text):
        closed_counts[m.group(1)] += 1

    to_append = ""
    for tag_name, _ in reversed(opened_tags):
        if closed_counts[tag_name] < opened_counts[tag_name]:
            to_append += f"</{tag_name}>"
            closed_counts[tag_name] += 1

    return text + to_append


# Public API for Tier 4 fallback — parses legacy/native formats
# that dsml_sieve + repair_tier3 may miss.


def legacy_fallback(text: str, tool_names: list[str] | None = None) -> list[dict]:
    """Parse tool calls using legacy formats (function_call, tool_use_json, raw XML, etc.).

    Returns list of dicts with "name" and "arguments" keys, or [] if none found.
    """
    tools = None
    if tool_names:
        tools = [{"function": {"name": n}} for n in tool_names]
    found = _parse_tool_calls(text, tools)
    if not found:
        return []
    results = []
    seen = set()
    for _, _, name, args_json in found:
        key = f"{name}:{args_json}"
        if key not in seen:
            seen.add(key)
            results.append({"name": name, "arguments": args_json})
    return results
