from __future__ import annotations

import json
from typing import Optional


_TOOL_FORMAT_INSTRUCTION = """
IMPORTANT: When you need to call a tool, you MUST output it in EXACTLY this XML format:

<tool_calls>
  <invoke name="ToolName">
    <parameter name="param1">value1</parameter>
    <parameter name="param2">value2</parameter>
  </invoke>
</tool_calls>

Rules:
1. Always wrap ALL tool calls inside <tool_calls>...</tool_calls>
2. Each tool call is an <invoke name="ToolName"> block
3. Each argument is a <parameter name="key">value</parameter>
4. NEVER use bracket call formats like [调用 ToolName] or [call ToolName]
5. NEVER put tool calls inside markdown code blocks (```...```)
6. NEVER put tool calls inside thinking tags
7. NEVER explain what you're about to do --- just output the tool call directly
8. After receiving tool results, continue working until the task is complete
9. When you have COMPLETED the entire task, start your final response with FINAL ANSWER:"""


# Agentic forcing block — always injected right before [Assistant] to ensure
# the model acts as an agent (uses tools) instead of just describing actions.
# Placed at the END of the prompt (recency effect) so it overrides any
# conflicting instructions buried in the middle of a long system prompt.
_AGENTIC_FORCING_BLOCK = """<system-reminder>
CRITICAL: You are an AUTONOMOUS AGENT with tools.
ABSOLUTNY NAKAZ: Każda twoja tura (dopóki zadanie nie jest w 100% ukończone i nie rozpoczyna się od 'FINAL ANSWER:') MUSI zawierać wywołanie narzędzia w bloku <tool_calls>!
ZAKAZ CHATTERU I STATUS UPDATES: NIGDY nie wypisuj samego tekstu z komentarzem, odkryciem lub zapowiedzią (np. 'Znalazłem coś...', 'Kopię głębiej...', 'Widzę że...', 'I found...', 'Let me dig in...', 'Naprawiam...', 'Sprawdzam...', 'Deleguję...').
Jeśli dokonałeś odkrycia, znalazłeś przyczynę lub masz hipotezę do zbadania — NIE PISZ O TYM SAMEGO TEKSTU! Twoja odpowiedź MUSI NATYCHMIAST zawierać wywołanie narzędzia (<tool_calls><invoke name="...">...</invoke></tool_calls>), aby sprawdzić plik, uruchomić skrypt lub zbadać kod!
NIGDY nie używaj [调用 Tool] ani bloków markdown. Po otrzymaniu wyniku narzędzia kontynuuj pracę. Dopiero po pełnym ukończeniu zadania zacznij odpowiedź od 'FINAL ANSWER:'.
</system-reminder>"""



class PromptBuilder:
    SYSTEM_PREFIX = "[System]:"
    USER_PREFIX = "[User]:"
    ASSISTANT_PREFIX = "[Assistant]:"
    TOOL_RESULT_PREFIX = "[Tool Result]:"

    @staticmethod
    def build(
        user_message: str,
        *,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
        tools_schema: Optional[list[dict]] = None,
    ) -> str:
        parts = []

        if system_prompt:
            parts.append(f"{PromptBuilder.SYSTEM_PREFIX}\n{system_prompt}")

        # FIX: Always add tools_schema when provided by IDE
        # IDE explicitly sends tools in request → proxy must include them
        # even if system_prompt contains tool-related keywords in examples/docs
        if tools_schema:
            tool_block = PromptBuilder._build_tool_section(tools_schema)
            if tool_block:
                parts.append(tool_block)

        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    parts.append(f"{PromptBuilder.USER_PREFIX}\n{content}")
                elif role == "assistant":
                    # Detect tool_result content and use separate prefix
                    if content and content.lstrip().startswith("<tool_result>"):
                        parts.append(f"{PromptBuilder.TOOL_RESULT_PREFIX}\n{content}")
                    else:
                        asst_content = content
                        tool_calls = msg.get("tool_calls")
                        if tool_calls:
                            tc_xml = PromptBuilder._tool_calls_to_xml(tool_calls)
                            if tc_xml:
                                asst_content = content + "\n" + tc_xml if content else tc_xml
                        parts.append(f"{PromptBuilder.ASSISTANT_PREFIX}\n{asst_content}")

        user_msg = (user_message or "").strip()
        if not user_msg and not history:
            user_msg = "Continue"

        if user_msg:
            parts.append(f"{PromptBuilder.USER_PREFIX}\n{user_msg}")
        # Agentic forcing block — always present, right before [Assistant]
        # to leverage recency effect. Critical for the model to actually
        # emit tool calls instead of describing them.
        parts.append(_AGENTIC_FORCING_BLOCK)
        parts.append(f"{PromptBuilder.ASSISTANT_PREFIX}\n")

        return "\n\n".join(parts)

    @staticmethod
    def _build_tool_section(tools_schema: list[dict]) -> str:
        """Build complete tool section: tool list + format instruction."""
        lines = []
        for tool in tools_schema:
            fn = tool.get("function", tool)
            name = fn.get("name", "")
            if not name:
                continue
            desc = fn.get("description", "")
            params = fn.get("parameters", {}).get("properties", {})
            required = set(fn.get("parameters", {}).get("required", []))
            if params:
                param_strs = []
                for pname, pinfo in params.items():
                    ptype = pinfo.get("type", "any")
                    enum_vals = pinfo.get("enum")
                    if enum_vals:
                        ptype = f"{ptype}[{','.join(str(e) for e in enum_vals)}]"
                    marker = " (required)" if pname in required else ""
                    param_strs.append(f"{pname}: {ptype}{marker}")
                sig = f"({', '.join(param_strs)})"
            else:
                sig = "()"
            if desc:
                lines.append(f"[Available Tool]: {name}{sig} - {desc}")
            else:
                lines.append(f"[Available Tool]: {name}{sig}")

        if not lines:
            return ""

        return "\n".join(lines) + "\n" + _TOOL_FORMAT_INSTRUCTION.strip()

    @staticmethod
    def _escape_xml_attr(text: str) -> str:
        """Escape XML special characters in attribute values."""
        return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _cdata(text: str) -> str:
        """Wrap text in CDATA section, escaping ]]> if present."""
        if "]]>" in text:
            text = text.replace("]]>", "]]]]><![CDATA[>")
        return f"<![CDATA[{text}]]>"

    @staticmethod
    def _tool_calls_to_xml(tool_calls: list[dict]) -> str:
        """Reconstruct tool calls as DSML XML for in-context examples."""
        blocks = []
        for tc in tool_calls:
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

            if isinstance(args, dict) and args:
                param_lines = []
                for k, v in sorted(args.items()):
                    escaped_key = PromptBuilder._escape_xml_attr(k)
                    if isinstance(v, str):
                        param_lines.append(f'      <parameter name="{escaped_key}">{PromptBuilder._cdata(v)}</parameter>')
                    elif v is None:
                        param_lines.append(f'      <parameter name="{escaped_key}"></parameter>')
                    elif isinstance(v, (bool, int, float)):
                        param_lines.append(f'      <parameter name="{escaped_key}">{str(v).lower() if isinstance(v, bool) else str(v)}</parameter>')
                    else:
                        # dict/list — serialize as JSON in CDATA
                        param_lines.append(f'      <parameter name="{escaped_key}">{PromptBuilder._cdata(json.dumps(v, ensure_ascii=False))}</parameter>')
                blocks.append(f'    <invoke name="{PromptBuilder._escape_xml_attr(name)}">\n' + "\n".join(param_lines) + '\n    </invoke>')
            else:
                blocks.append(f'    <invoke name="{PromptBuilder._escape_xml_attr(name)}"></invoke>')

        if not blocks:
            return ""
        return "<tool_calls>\n" + "\n".join(blocks) + "\n</tool_calls>"
