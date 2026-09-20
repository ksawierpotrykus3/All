"""Tests for configuration module."""

import pytest

from server.config.settings import Settings, settings
from server.config import (
    MAX_ACCOUNTS,
    MAX_PARALLEL_TOOL_CALLS,
    MAX_SESSIONS_PER_ACCOUNT,
    WATERMARK_ENABLED,
    DEDUP_TTL,
    WM_PATTERN,
)


class TestSettings:
    def test_settings_is_instance(self):
        assert isinstance(settings, Settings)

    def test_settings_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("MAX_ACCOUNTS", "5")
        monkeypatch.setenv("MIN_BASE_DELAY", "10.0")
        monkeypatch.setenv("MAX_CAPTURE_BUF_SIZE", "1000000")

        s = Settings()
        assert s.max_accounts == 5
        assert s.min_base_delay == 10.0
        assert s.max_capture_buf_size == 1_000_000

    def test_settings_defaults(self):
        s = Settings()
        assert s.max_accounts == 3
        assert s.min_base_delay == 8.0
        assert s.max_capture_buf_size == 500_000
        assert s.ttl == 86400
        assert s.max_sessions_per_account == 5
        assert s.max_parallel_tool_calls == 20
        assert s.watermark_enabled is False
        assert s.dedup_ttl == 60.0
        assert s.max_prompt_len == 150_000
        assert s.tool_result_max_chars == 10_000
        assert s.max_jitter == 5.0
        assert s.stream_backoff_delays == [3, 6, 12, 20]
        assert s.rate_backoff_delays == [3, 6, 12, 25]
        assert s.drain_timeout == 30.0
        assert s.dashboard_db_path == "dashboard.db"
        assert s.log_level == "INFO"
        assert s.log_format == "json"

    def test_env_override_max_accounts(self, monkeypatch):
        monkeypatch.setenv("MAX_ACCOUNTS", "7")
        s = Settings()
        assert s.max_accounts == 7

    def test_env_override_watermark(self, monkeypatch):
        monkeypatch.setenv("WATERMARK_ENABLED", "true")
        s = Settings()
        assert s.watermark_enabled is True

    def test_config_reexports_match_settings(self):
        assert MAX_ACCOUNTS == settings.max_accounts
        assert MAX_PARALLEL_TOOL_CALLS == settings.max_parallel_tool_calls
        assert MAX_SESSIONS_PER_ACCOUNT == settings.max_sessions_per_account
        assert WATERMARK_ENABLED == settings.watermark_enabled
        assert DEDUP_TTL == settings.dedup_ttl

    def test_wm_pattern_matches(self):
        import re

        match = WM_PATTERN.search("<!-- PROXY_SID:abc-123 -->")
        assert match is not None
        assert match.group(1) == "abc-123"

    def test_wm_pattern_case_insensitive(self):
        match = WM_PATTERN.search("<!-- proxy_sid:abc-123 -->")
        assert match is not None


class TestConfigModule:
    def test_max_accounts_is_int(self):
        assert isinstance(MAX_ACCOUNTS, int)
        assert MAX_ACCOUNTS > 0

    def test_max_parallel_tool_calls_is_int(self):
        assert isinstance(MAX_PARALLEL_TOOL_CALLS, int)
        assert MAX_PARALLEL_TOOL_CALLS > 0

    def test_watermark_enabled_is_bool(self):
        assert isinstance(WATERMARK_ENABLED, bool)

    def test_dedup_ttl_is_float(self):
        assert isinstance(DEDUP_TTL, float)

    def test_wm_pattern_is_compiled_regex(self):
        assert hasattr(WM_PATTERN, "search")
        assert hasattr(WM_PATTERN, "match")
