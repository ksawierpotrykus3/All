"""Tests for _repair_empty_tc_args — dropping malformed (empty-args) tool calls.

Regression for the dominant failure mode observed in server_stdout.log:
the model emits ``<invoke name="Write">`` with no ``<parameter>`` blocks, the
parser returns ``arguments: "{}"``, and the IDE rejects the call with
``Invalid arguments: path: Required``. Such calls must be removed (with a loud
debug log) instead of being forwarded to a hard-rejecting IDE.
"""

import json

import pytest

from server.services.proxy_service import _repair_empty_tc_args


def _call(name="Write", args="{}", wrap=False):
    args_raw = json.dumps(args) if isinstance(args, dict) else args
    if wrap:
        return {"function": {"name": name, "arguments": args_raw}}
    return {"name": name, "arguments": args_raw}


class TestRepairEmptyTcArgs:
    def test_valid_call_is_kept_unchanged(self):
        calls = [_call("Read", {"file_path": "a.txt"})]
        result = _repair_empty_tc_args(calls, None)
        assert len(result) == 1
        assert json.loads(result[0]["arguments"]) == {"file_path": "a.txt"}

    def test_empty_dict_args_call_is_dropped(self):
        calls = [_call("Write", {})]
        result = _repair_empty_tc_args(calls, None)
        assert result == []

    def test_empty_string_args_call_is_dropped(self):
        calls = [_call("Write", "")]
        result = _repair_empty_tc_args(calls, None)
        assert result == []

    def test_mixed_valid_and_empty_keeps_only_valid(self):
        calls = [
            _call("Read", {"file_path": "a.txt"}),
            _call("Write", {}),
            _call("Glob", {"pattern": "**/*.py"}),
        ]
        result = _repair_empty_tc_args(calls, None)
        assert len(result) == 2
        names = [c["name"] for c in result]
        assert names == ["Read", "Glob"]

    def test_function_wrapped_empty_args_is_dropped(self):
        calls = [_call("Write", {}, wrap=True)]
        result = _repair_empty_tc_args(calls, None)
        assert result == []

    def test_non_dict_args_is_kept(self):
        # Scalar/raw args (e.g. from _ensure_valid_json {"value": ...}) are not
        # empty-object and must be forwarded as-is.
        calls = [_call("Shell", '{"value": "ls"}')]
        result = _repair_empty_tc_args(calls, None)
        assert len(result) == 1

    def test_schema_aware_required_args_not_guessed(self):
        # Even if we have a schema, we must NOT fabricate path/contents. The
        # call is still dropped; this proves we don't invent dangerous defaults.
        tools = [
            {
                "function": {
                    "name": "Write",
                    "parameters": {
                        "type": "object",
                        "required": ["path", "contents"],
                        "properties": {
                            "path": {"type": "string"},
                            "contents": {"type": "string"},
                        },
                    },
                }
            }
        ]
        calls = [_call("Write", {})]
        result = _repair_empty_tc_args(calls, tools)
        assert result == []

    def test_missing_arguments_key_is_dropped_as_empty(self):
        calls = [{"name": "Write"}]
        result = _repair_empty_tc_args(calls, None)
        assert result == []

    def test_exception_inside_call_is_safe(self):
        # A malformed entry that raises during inspection must not crash the
        # whole stream generator; it is simply kept.
        calls = [_call("Read", {"file_path": "a.txt"}), object()]
        result = _repair_empty_tc_args(calls, None)
        # The valid one survives; the un-inspectable one is kept safe.
        assert any(isinstance(c, dict) and c.get("name") == "Read" for c in result)

    def test_empty_calls_list_returns_empty(self):
        assert _repair_empty_tc_args([], None) == []

    def test_none_calls_list_returns_empty(self):
        assert _repair_empty_tc_args(None, None) == []

    def test_function_dict_without_args_falls_back_to_toplevel(self):
        """ToolMgr.validate adds function={name} without arguments.

        The parser puts arguments at top-level ({"name":..., "arguments":...}).
        When validate adds function={}, _repair_empty_tc_args must fall back
        to tc["arguments"] and NOT drop the call as empty.
        """
        calls = [
            {
                "name": "Shell",
                "arguments": '{"command": "ls"}',
                "function": {"name": "Shell"},
            }
        ]
        result = _repair_empty_tc_args(calls, None)
        assert len(result) == 1
        assert result[0]["name"] == "Shell"

    def test_function_dict_with_args_in_function_is_kept(self):
        """Standard OpenAI format: arguments inside function dict."""
        calls = [
            {
                "function": {
                    "name": "Shell",
                    "arguments": '{"command": "ls"}',
                }
            }
        ]
        result = _repair_empty_tc_args(calls, None)
        assert len(result) == 1

    def test_function_dict_empty_args_both_levels_is_dropped(self):
        """Both function.arguments and tc.arguments empty → drop."""
        calls = [
            {
                "name": "Shell",
                "function": {"name": "Shell"},
            }
        ]
        result = _repair_empty_tc_args(calls, None)
        assert result == []
