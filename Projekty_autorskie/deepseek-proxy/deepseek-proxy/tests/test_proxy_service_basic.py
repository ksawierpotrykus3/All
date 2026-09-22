"""Basic unit tests for ProxyService."""

import pytest
from server.services.proxy_service import ProxyService
from server.services.session_manager import session_manager


class TestSessionManager:
    def test_acquire_release_slot(self):
        slot = 999
        assert session_manager.acquire_slot(slot)
        session_manager.release_slot(slot)

    def test_acquire_twice_release_once(self):
        slot = 998
        assert session_manager.acquire_slot(slot)
        assert session_manager.acquire_slot(slot)
        session_manager.release_slot(slot)
        session_manager.release_slot(slot)

    def test_release_unknown_slot(self):
        session_manager.release_slot(12345)


class TestProxyServiceInit:
    def test_can_instantiate(self):
        svc = ProxyService()
        assert svc is not None

    def test_validate_messages_empty(self):
        with pytest.raises(Exception):
            ProxyService._validate_messages([])

    def test_validate_messages_invalid_role(self):
        with pytest.raises(Exception):
            ProxyService._validate_messages([{"role": "invalid", "content": "test"}])

    def test_validate_messages_valid(self):
        ProxyService._validate_messages([{"role": "user", "content": "hello"}])

    def test_validate_tools_duplicate(self):
        with pytest.raises(Exception):
            ProxyService._validate_tools([
                {"function": {"name": "tool_a"}},
                {"function": {"name": "tool_a"}},
            ])

    def test_validate_tools_empty(self):
        ProxyService._validate_tools([])

    def test_validate_params_temperature_out_of_range(self):
        with pytest.raises(Exception):
            ProxyService._validate_params(3.0, None, None)

    def test_validate_params_top_p_out_of_range(self):
        with pytest.raises(Exception):
            ProxyService._validate_params(None, 1.5, None)

    def test_validate_params_max_tokens_too_low(self):
        with pytest.raises(Exception):
            ProxyService._validate_params(None, None, 0)

    def test_validate_params_valid(self):
        ProxyService._validate_params(0.5, 0.8, 100)


class TestBuildTcList:
    def test_build_tc_list_from_items(self):
        from server.services.proxy_service import _build_tc_list
        calls = [{"name": "test_tool", "arguments": '{"key": "value"}'}]
        result = _build_tc_list(calls, "test-uuid")
        assert len(result) == 1
        assert result[0]["function"]["name"] == "test_tool"

    def test_build_tc_list_function_format(self):
        from server.services.proxy_service import _build_tc_list
        calls = [{"function": {"name": "fn_tool", "arguments": '{}'}}]
        result = _build_tc_list(calls, "test-uuid")
        assert len(result) == 1
        assert result[0]["function"]["name"] == "fn_tool"
