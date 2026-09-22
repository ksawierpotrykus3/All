"""server/core/mcp_catalog.py — MCP tool catalog extraction and rewrite.

The IDE (Trae/opencode) exposes MCP servers through two proxy tools:
``GetMcpTools`` (returns a JSON catalog of all MCP servers and their tools)
and ``CallMcpTool`` (executes a tool on a specific server).  When the model
reads the catalog from a ``role: tool`` message it sometimes responds with a
bare ``<invoke name="git_status">`` instead of ``<invoke name="CallMcpTool">``.
That bare name is not in the upstream tool list, so ``ToolMgr.validate`` drops
it and the IDE never receives the call (observable as a "stuck" stream).

This module:
  * parses catalog content into ``{tool_name: {server, description, parameters}}``
  * aggregates catalogs from tool messages in the conversation
  * rewrites bare MCP tool calls into proper ``CallMcpTool`` invocations.
"""

from __future__ import annotations

import json
from typing import Any, Iterable


def parse_mcp_tools(content: str) -> dict[str, dict[str, Any]]:
    """Parse one catalog payload into ``{tool_name: {server, description, parameters}}``.

    Tolerant parser: handles a single server object, a list of server objects,
    and arbitrary non-catalog text (returns {} for anything that does not look
    like an MCP catalog).
    """
    if not isinstance(content, str) or not content.strip():
        return {}
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        # Tolerate text with an embedded JSON object (e.g. catalog narrated by model).
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            data = json.loads(content[start : end + 1])
        except (ValueError, TypeError):
            return {}

    entries: list[dict] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                entries.append(item)
    elif isinstance(data, dict):
        if isinstance(data.get("servers"), list):
            # {"mode":"catalog","servers":[{server, tools:[...]}, ...]}
            entries.extend(s for s in data["servers"] if isinstance(s, dict))
        else:
            entries.append(data)

    catalog: dict[str, dict[str, Any]] = {}
    for entry in entries:
        server = entry.get("server")
        tools = entry.get("tools")
        if not isinstance(server, str) or not isinstance(tools, list):
            continue
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = tool.get("tool") or tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            catalog[name] = {
                "server": server,
                "description": tool.get("description", "") or "",
                "parameters": tool.get("inputSchema") or {"type": "object"},
            }
    return catalog


def build_mcp_catalog(messages: Iterable[dict]) -> dict[str, dict[str, Any]]:
    """Aggregate MCP tool catalogs from ``role: tool`` messages in the conversation.

    Only messages whose content parses as an MCP catalog contribute entries;
    ordinary tool results (e.g. git output, file listings) are ignored.
    """
    catalog: dict[str, dict[str, Any]] = {}
    for msg in messages or []:
        if not isinstance(msg, dict) or msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        try:
            parsed = parse_mcp_tools(content)
        except Exception:  # pragma: no cover - defensive
            continue
        if parsed:
            catalog.update(parsed)
    return catalog


_CALL_MCP_TOOL = "CallMcpTool"


def _normalize_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except (ValueError, TypeError):
            parsed = None
        arguments = parsed
    if not isinstance(arguments, dict):
        return {} if arguments in (None, "") else {"value": arguments}
    return arguments


def mcp_rewrite_calls(
    calls: Iterable[dict], catalog: dict[str, dict[str, Any]]
) -> list[dict]:
    """Rewrite bare MCP tool calls into ``CallMcpTool`` invocations.

    Every call whose name appears in ``catalog`` is rewritten to
    ``{name: "CallMcpTool", arguments: {server, toolName, description, arguments}}``.
    Calls with unknown names (or no catalog) pass through unchanged, so this is
    a no-op whenever no MCP catalog is present.
    """
    if not catalog or not calls:
        return list(calls)
    out: list[dict] = []
    for tc in calls:
        if not isinstance(tc, dict):
            out.append(tc)
            continue
        name = tc.get("name", "")
        if not isinstance(name, str):
            fn = tc.get("function")
            name = fn.get("name", "") if isinstance(fn, dict) else ""
        if name not in catalog:
            out.append(tc)
            continue
        entry = catalog[name]
        description = entry.get("description", "") or ""
        if len(description) > 200:
            description = description[:200]
        rewritten: dict[str, Any] = {
            "name": _CALL_MCP_TOOL,
            "arguments": {
                "server": entry.get("server", ""),
                "toolName": name,
                "description": description,
                "arguments": _normalize_arguments(tc.get("arguments")),
            },
        }
        if "id" in tc:
            rewritten["id"] = tc["id"]
        out.append(rewritten)
    return out
