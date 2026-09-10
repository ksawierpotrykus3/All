"""Tests for SleepGuard — SetThreadExecutionState wrapper.

Verifies that the bot can prevent Windows from sleeping / turning off the
display while a session runs, and that the OS state is restored on shutdown.

Behaviour under test:
  * ``enable(display=True, system=True)`` sets both flags + ES_CONTINUOUS
  * ``disable()`` clears flags (re-applies ES_CONTINUOUS alone)
  * Calls are idempotent (a second enable with the same flags does NOT
    re-issue the syscall; we rely on the heartbeat thread instead).
  * Calls with different flags ARE re-issued (the user toggled display).
  * The heartbeat thread re-applies the state every ``heartbeat_s`` seconds
    so newer Windows builds (which ignore stale ES_CONTINUOUS after ~60s)
    keep the screen/system awake for the whole session.
  * ``disable()`` joins the heartbeat thread cleanly even when enable() was
    never called.
  * ``is_enabled`` reports the last successful enable/disable.
"""

from __future__ import annotations

import threading
import time

import pytest

from mvp.bot.anti_sleep import (
    ES_AWAYMODE_REQUIRED,
    ES_CONTINUOUS,
    ES_DISPLAY_REQUIRED,
    ES_SYSTEM_REQUIRED,
    SleepGuard,
)


class FakeKernel32:
    """Records every SetThreadExecutionState call (and exposes a return code)."""

    def __init__(self, return_value: int = 1) -> None:
        self.calls: list[int] = []
        self.return_value = return_value

    def SetThreadExecutionState(self, state: int) -> int:  # noqa: N802 - WinAPI naming
        self.calls.append(state)
        return self.return_value


@pytest.fixture
def fake_kernel32() -> FakeKernel32:
    return FakeKernel32()


@pytest.fixture
def guard(monkeypatch, fake_kernel32: FakeKernel32) -> SleepGuard:
    """Build a SleepGuard whose kernel32 calls land in fake_kernel32.

    The heartbeat interval is forced short so we can drive it manually in
    tests instead of waiting 30 seconds. ``monkeypatch`` is used so the test
    never touches the real kernel32.
    """
    from mvp.bot import anti_sleep as anti_sleep_mod

    monkeypatch.setattr(
        anti_sleep_mod.ctypes, "windll", type("W", (), {"kernel32": fake_kernel32})()
    )
    guard = SleepGuard(heartbeat_s=0.05)
    yield guard
    guard.shutdown()  # cleanup if a test forgot


def _drive_heartbeat(guard: SleepGuard, ticks: int = 1) -> None:
    """Manually advance the heartbeat ``ticks`` times (sleep + let the thread run)."""
    for _ in range(ticks):
        time.sleep(guard._heartbeat_s + 0.02)


def test_enable_sets_display_and_system_flags(
    guard: SleepGuard, fake_kernel32: FakeKernel32
) -> None:
    guard.enable(display=True, system=True)
    assert fake_kernel32.calls == [ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED]
    assert guard.is_enabled is True


def test_enable_display_only(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=True, system=False)
    assert fake_kernel32.calls == [ES_CONTINUOUS | ES_DISPLAY_REQUIRED]


def test_enable_system_only(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=False, system=True)
    assert fake_kernel32.calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED]


def test_disable_clears_flags(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=True, system=True)
    guard.disable()
    # ES_CONTINUOUS alone = "allow sleep / display off" again.
    assert fake_kernel32.calls[-1] == ES_CONTINUOUS
    assert guard.is_enabled is False


def test_enable_is_idempotent(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=True, system=True)
    guard.enable(display=True, system=True)
    # Second call with the SAME flags must NOT re-invoke the syscall — the
    # heartbeat is responsible for keeping the state alive.
    assert len(fake_kernel32.calls) == 1


def test_enable_with_different_flags_re_issues(
    guard: SleepGuard, fake_kernel32: FakeKernel32
) -> None:
    guard.enable(display=True, system=True)
    guard.enable(display=False, system=True)  # user toggled display off
    assert fake_kernel32.calls == [
        ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED,
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED,
    ]


def test_disable_without_enable_is_noop(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.disable()
    # A clean shutdown must NOT issue any syscall — we only clear state when
    # we previously set it.
    assert fake_kernel32.calls == []


def test_disable_is_idempotent(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=True, system=True)
    guard.disable()
    guard.disable()
    # The second disable is a no-op: the state is already cleared.
    assert fake_kernel32.calls.count(ES_CONTINUOUS) == 1


def test_heartbeat_reapplies_state(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=True, system=True)
    initial_call_count = len(fake_kernel32.calls)
    _drive_heartbeat(guard, ticks=3)
    # Each heartbeat must re-issue the FULL state with ES_CONTINUOUS, otherwise
    # newer Windows builds forget the request after ~60s.
    heartbeats = fake_kernel32.calls[initial_call_count:]
    expected = ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
    assert heartbeats == [expected] * 3


def test_disable_stops_heartbeat(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    guard.enable(display=True, system=True)
    assert guard._heartbeat_thread is not None
    assert guard._heartbeat_thread.is_alive()

    guard.disable()
    # Heartbeat thread must have exited (or be in the process of exiting).
    assert guard._heartbeat_thread is None or not guard._heartbeat_thread.is_alive()
    # No more heartbeats should fire after disable().
    count_after_disable = len(fake_kernel32.calls)
    _drive_heartbeat(guard, ticks=3)
    assert len(fake_kernel32.calls) == count_after_disable


def test_heartbeat_thread_does_not_leak(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    threads_before = {t.ident for t in threading.enumerate()}

    guard.enable(display=True, system=True)
    _drive_heartbeat(guard, ticks=2)
    guard.disable()

    threads_after = {t.ident for t in threading.enumerate()}
    leaked = threads_after - threads_before
    assert leaked == set(), f"heartbeat thread leaked: {leaked}"


def test_enable_handles_kernel32_failure(monkeypatch, fake_kernel32: FakeKernel32) -> None:
    """If kernel32 returns 0 the guard must raise and not start the heartbeat."""
    from mvp.bot import anti_sleep as anti_sleep_mod
    from mvp.bot.exceptions import AntiSleepError

    fake_kernel32.return_value = 0
    monkeypatch.setattr(
        anti_sleep_mod.ctypes,
        "windll",
        type("W", (), {"kernel32": fake_kernel32})(),
    )
    guard = SleepGuard(heartbeat_s=0.05)

    with pytest.raises(AntiSleepError):
        guard.enable(display=True, system=True)

    assert guard.is_enabled is False
    assert guard._heartbeat_thread is None


def test_shutdown_when_never_enabled(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    """shutdown() must be safe to call even if enable() was never invoked."""
    guard.shutdown()
    assert fake_kernel32.calls == []


def test_constants_values() -> None:
    """Lock down WinAPI constant values used in the guard.

    If Microsoft ever renumbers these the test catches it immediately.
    """
    assert ES_CONTINUOUS == 0x80000000
    assert ES_DISPLAY_REQUIRED == 0x00000002
    assert ES_SYSTEM_REQUIRED == 0x00000001
    assert ES_AWAYMODE_REQUIRED == 0x00000040


def test_enable_with_away_mode(guard: SleepGuard, fake_kernel32: FakeKernel32) -> None:
    """away_mode allows the display to turn off but keeps the CPU/network alive.

    Useful for a long-running session where the user has walked away from the
    screen but the bot must keep clicking.
    """
    guard.enable(display=True, system=True, away_mode=True)
    expected = ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    assert fake_kernel32.calls == [expected]
