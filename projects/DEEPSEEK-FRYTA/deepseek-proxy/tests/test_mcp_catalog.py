"""tests/test_mcp_catalog.py — MCP catalog extraction, injection and rewrite"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from server.core.mcp_catalog import (
    build_mcp_catalog,
    mcp_rewrite_calls,
    parse_mcp_tools,
)

GIT_CATALOG = (
    '{"mode":"server","server":"user-git","serverStatus":"ready",'
    '"tools":[{"tool":"git_add","description":"Adds file contents to the staging area",'
    '"inputSchema":{"type":"object","properties":{"files":{"type":"array"}}}},'
    '{"tool":"git_status","description":"Shows the working tree status",'
    '"inputSchema":{"type":"object","properties":{"repo_path":{"type":"string"}}}}]}'
)


class TestParseMcpTools:
    def test_parses_single_server_catalog(self):
        parsed = parse_mcp_tools(GIT_CATALOG)
        assert "git_status" in parsed
        assert parsed["git_status"]["server"] == "user-git"
        assert parsed["git_status"]["description"] == "Shows the working tree status"
        assert (
            parsed["git_status"]["parameters"]["properties"]["repo_path"]["type"]
            == "string"
        )

    def test_parses_multiple_servers(self):
        content = (
            "["
            '{"mode":"server","server":"user-git","tools":[{"tool":"git_status"}]},'
            '{"mode":"server","server":"user-fetch","tools":[{"tool":"fetch_url"}]}'
            "]"
        )
        parsed = parse_mcp_tools(content)
        assert parsed["git_status"]["server"] == "user-git"
        assert parsed["fetch_url"]["server"] == "user-fetch"

    def test_tolerates_non_catalog_json(self):
        assert parse_mcp_tools('{"repo_path": "F:\\x"}') == {}

    def test_tolerates_invalid_json_text(self):
        assert parse_mcp_tools("git output line 1\nline 2") == {}


class TestBuildMcpCatalog:
    def test_aggregates_tool_messages(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": GIT_CATALOG},
            {
                "role": "tool",
                "content": (
                    '{"mode":"server","server":"user-fetch",'
                    '"tools":[{"tool":"fetch_url","description":"fetch"}]}'
                ),
            },
        ]
        cat = build_mcp_catalog(messages)
        assert cat["git_status"]["server"] == "user-git"
        assert cat["fetch_url"]["server"] == "user-fetch"

    def test_ignores_non_catalog_tool_results(self):
        messages = [
            {"role": "tool", "content": '{"files": ["a.txt"]}'},
            {"role": "assistant", "content": "hello"},
        ]
        assert build_mcp_catalog(messages) == {}


class TestMcpRewriteCalls:
    def test_rewrites_bare_mcp_name_to_call_mcp_tool(self):
        calls = [{"name": "git_status", "arguments": {"repo_path": "F:\\x"}}]
        catalog = {"git_status": {"server": "user-git", "description": "status"}}
        out = mcp_rewrite_calls(calls, catalog)
        assert len(out) == 1
        tc = out[0]
        assert tc["name"] == "CallMcpTool"
        assert tc["arguments"]["server"] == "user-git"
        assert tc["arguments"]["toolName"] == "git_status"
        assert tc["arguments"]["arguments"] == {"repo_path": "F:\\x"}

    def test_rewrites_with_json_string_arguments(self):
        calls = [{"name": "git_status", "arguments": '{"repo_path": "F:\\\\PROJEKTY"}'}]
        catalog = {"git_status": {"server": "user-git"}}
        out = mcp_rewrite_calls(calls, catalog)
        assert out[0]["arguments"]["arguments"] == {"repo_path": "F:\\PROJEKTY"}

    def test_preserves_id_on_rewrite(self):
        calls = [{"name": "git_status", "arguments": {}, "id": "call_123"}]
        catalog = {"git_status": {"server": "user-git"}}
        out = mcp_rewrite_calls(calls, catalog)
        assert out[0]["id"] == "call_123"

    def test_preserves_non_mcp_calls(self):
        calls = [{"name": "Read", "arguments": {"file_path": "/tmp/x"}}]
        out = mcp_rewrite_calls(calls, {"git_status": {"server": "user-git"}})
        assert out == calls

    def test_unknown_name_untouched(self):
        calls = [{"name": "FooBar", "arguments": "{}"}]
        out = mcp_rewrite_calls(calls, {"git_status": {"server": "user-git"}})
        assert out == calls

    def test_empty_input(self):
        assert mcp_rewrite_calls([], {}) == []
        assert mcp_rewrite_calls([], {"git_status": {"server": "s"}}) == []
