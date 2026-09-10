"""Tests for the HWID module (mvp.bot.hwid)."""

import pytest

from mvp.bot.hwid import get_hwid


@pytest.fixture(autouse=True)
def _clear_hwid_cache():
    """get_hwid is lru_cached - reset between tests so monkeypatches apply."""
    get_hwid.cache_clear()
    yield
    get_hwid.cache_clear()


def test_get_hwid_returns_64_hex(monkeypatch):
    monkeypatch.setattr("mvp.bot.hwid._machine_guid", lambda: "guid-123")
    monkeypatch.setattr("mvp.bot.hwid._smbios_uuid", lambda: "uuid-456")
    monkeypatch.setattr("platform.node", lambda: "host-789")
    hwid = get_hwid()
    assert len(hwid) == 64
    assert all(c in "0123456789abcdef" for c in hwid)


def test_get_hwid_deterministic(monkeypatch):
    monkeypatch.setattr("mvp.bot.hwid._machine_guid", lambda: "g")
    monkeypatch.setattr("mvp.bot.hwid._smbios_uuid", lambda: "u")
    monkeypatch.setattr("platform.node", lambda: "n")
    assert get_hwid() == get_hwid()


def test_get_hwid_raises_when_all_sources_empty(monkeypatch):
    monkeypatch.setattr("mvp.bot.hwid._machine_guid", lambda: "")
    monkeypatch.setattr("mvp.bot.hwid._smbios_uuid", lambda: "")
    monkeypatch.setattr("platform.node", lambda: "")
    with pytest.raises(RuntimeError):
        get_hwid()


def test_get_hwid_partial_failure_uses_smbios(monkeypatch):
    monkeypatch.setattr("mvp.bot.hwid._machine_guid", lambda: "")
    monkeypatch.setattr("mvp.bot.hwid._smbios_uuid", lambda: "uuid-456")
    monkeypatch.setattr("platform.node", lambda: "host-789")
    hwid = get_hwid()
    assert len(hwid) == 64
    assert all(c in "0123456789abcdef" for c in hwid)


def test_get_hwid_hostname_only_fallback(monkeypatch):
    monkeypatch.setattr("mvp.bot.hwid._machine_guid", lambda: "")
    monkeypatch.setattr("mvp.bot.hwid._smbios_uuid", lambda: "")
    monkeypatch.setattr("platform.node", lambda: "host-789")
    hwid = get_hwid()
    assert len(hwid) == 64
    assert all(c in "0123456789abcdef" for c in hwid)
    assert get_hwid() == hwid  # deterministic


def test_get_hwid_hostname_change_does_not_affect_hwid(monkeypatch):
    monkeypatch.setattr("mvp.bot.hwid._machine_guid", lambda: "guid-123")
    monkeypatch.setattr("mvp.bot.hwid._smbios_uuid", lambda: "uuid-456")
    monkeypatch.setattr("platform.node", lambda: "host-789")
    hwid = get_hwid()
    monkeypatch.setattr("platform.node", lambda: "renamed-host")
    get_hwid.cache_clear()  # force recomputation with the new hostname
    assert get_hwid() == hwid
