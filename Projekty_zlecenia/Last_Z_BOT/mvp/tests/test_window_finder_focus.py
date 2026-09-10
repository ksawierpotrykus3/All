"""Tests for AGENTS.md §5 window-focus invariants in window_finder.force_foreground.

The rule: never call ShowWindow(hwnd, SW_RESTORE) unconditionally — only when
the window is actually minimized (IsIconic). Otherwise use ShowWindow(hwnd, SW_SHOW=5)
to avoid resetting window geometry on every focus call.
"""

import time

import pytest

from mvp.bot import window_finder as wf

# Synthetic identifiers (no real window is created or scanned for)
_TEST_HWND = 12345
_TEST_PID = 9999
_TEST_PROCESS = "Survival.exe"


@pytest.fixture
def fake_user32(monkeypatch):
    """Stub wf.user32 functions used by force_foreground and record all calls."""
    calls = {
        "ShowWindow": [],
        "IsIconic": [],
        "SetForegroundWindow": [],
        "BringWindowToTop": [],
        "SetActiveWindow": [],
        "AttachThreadInput": [],
        "GetForegroundWindow": [],
    }
    user32 = wf.user32

    def fake_show(hwnd, cmd):
        calls["ShowWindow"].append((hwnd, cmd))
        return True

    def fake_is_iconic(hwnd):
        calls["IsIconic"].append(hwnd)
        # Configurable via `fake_is_iconic.result`; default 0 (not iconic).
        return getattr(fake_is_iconic, "result", 0)

    def fake_get_fg():
        calls["GetForegroundWindow"].append(None)
        return _TEST_HWND

    def fake_get_thread_process_id(hwnd, out_pid):
        # force_foreground only compares the returned tid against our_tid.
        return 1

    monkeypatch.setattr(user32, "ShowWindow", fake_show)
    monkeypatch.setattr(user32, "IsIconic", fake_is_iconic)
    monkeypatch.setattr(user32, "GetForegroundWindow", fake_get_fg)
    monkeypatch.setattr(user32, "GetWindowThreadProcessId", fake_get_thread_process_id)
    monkeypatch.setattr(
        user32, "BringWindowToTop", lambda h: calls["BringWindowToTop"].append(h) or True
    )
    monkeypatch.setattr(
        user32, "SetForegroundWindow",
        lambda h: calls["SetForegroundWindow"].append(h) or True,
    )
    monkeypatch.setattr(
        user32, "SetActiveWindow", lambda h: calls["SetActiveWindow"].append(h) or True
    )
    monkeypatch.setattr(
        user32, "AttachThreadInput",
        lambda a, b, c: calls["AttachThreadInput"].append((a, b, c)) or True,
    )
    return calls


@pytest.fixture
def stubbed_window(monkeypatch):
    """Bypass find_game_window + psutil by returning a synthetic WindowInfo.

    Pre-populate _hwnd_cache so the post-call verification path returns True.
    """
    info = wf.WindowInfo(
        hwnd=_TEST_HWND, left=0, top=0, right=1920, bottom=1080, title="Survival"
    )
    monkeypatch.setattr(wf, "find_game_window", lambda _name=None: info)
    monkeypatch.setattr(wf, "_find_process_pids", lambda _name: {_TEST_PID})
    wf._hwnd_cache.clear()
    wf._hwnd_cache[_TEST_PROCESS] = (_TEST_PID, time.monotonic(), info)
    try:
        yield info
    finally:
        wf._hwnd_cache.clear()


def test_force_foreground_when_minimized_uses_sw_restore(fake_user32, stubbed_window):
    """AGENTS.md §5: IsIconic=True → ShowWindow(hwnd, SW_RESTORE=9)."""
    wf.user32.IsIconic.result = 1
    result = wf.force_foreground(_TEST_PROCESS)
    assert result is True
    cmds = [cmd for _, cmd in fake_user32["ShowWindow"]]
    assert 9 in cmds, (
        f"AGENTS.md §5: SW_RESTORE must be used when minimized; got cmds={cmds}"
    )
    assert 5 not in cmds, (
        f"AGENTS.md §5: SW_SHOW must NOT be used when minimized; got cmds={cmds}"
    )


def test_force_foreground_when_visible_uses_sw_show(fake_user32, stubbed_window):
    """AGENTS.md §5: IsIconic=False → ShowWindow(hwnd, SW_SHOW=5); SW_RESTORE is forbidden."""
    wf.user32.IsIconic.result = 0
    result = wf.force_foreground(_TEST_PROCESS)
    assert result is True
    cmds = [cmd for _, cmd in fake_user32["ShowWindow"]]
    assert 5 in cmds, (
        f"AGENTS.md §5: SW_SHOW must be used when not minimized; got cmds={cmds}"
    )
    assert 9 not in cmds, (
        f"AGENTS.md §5: SW_RESTORE must NOT be used when not minimized; got cmds={cmds}"
    )


def test_force_foreground_calls_set_foreground_window(fake_user32, stubbed_window):
    """force_foreground must always invoke SetForegroundWindow with the target hwnd."""
    wf.user32.IsIconic.result = 0
    wf.force_foreground(_TEST_PROCESS)
    assert _TEST_HWND in fake_user32["SetForegroundWindow"]


def test_force_foreground_returns_false_on_show_exception(
    fake_user32, stubbed_window, monkeypatch
):
    """Any exception during the ShowWindow / focus sequence must surface as False."""

    def boom(_hwnd, _cmd):
        raise OSError("ShowWindow failed")

    monkeypatch.setattr(wf.user32, "ShowWindow", boom)
    wf.user32.IsIconic.result = 0
    result = wf.force_foreground(_TEST_PROCESS)
    assert result is False
