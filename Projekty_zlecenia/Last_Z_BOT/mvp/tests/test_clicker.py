"""L1: MVP Clicker must enable the 1ms Windows timer on init and release it on shutdown.

L2: spam_click gains ``direct_first`` — the first click skips the bezier
approach and lands at δ≈0 via the raw stroke's MOUSE_MOVE_ABSOLUTE.
"""

import pytest

from mvp.bot import clicker as clicker_mod
from mvp.bot.clicker import Clicker


def _patch_backend(monkeypatch):
    """Patch ``initialize_backend`` so Clicker initializes without real WinAPI (SendInput stub)."""
    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: _FakeBackend())


class _FakeBackend:
    """No-op backend that records low-level mouse events."""

    name = "sendinput"

    def __init__(self) -> None:
        self._initialized = True
        self.events: list[tuple[str, int, int]] = []

    def available(self) -> bool:
        return True

    def initialize(self) -> bool:
        return True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def mouse_down_left(self) -> None:
        pass

    def mouse_up_left(self) -> None:
        pass

    def move_to(self, x: int, y: int) -> None:
        self.events.append(("move", int(x), int(y)))

    def scroll(self, direction: str) -> None:
        pass

    def get_cursor_pos(self) -> tuple[int, int]:
        return (0, 0)

    def spam_down(self, x: int, y: int) -> None:
        self.events.append(("down", int(x), int(y)))

    def spam_up(self, x: int, y: int) -> None:
        self.events.append(("up", int(x), int(y)))

    def spam_move(self, x: int, y: int) -> None:
        self.events.append(("move", int(x), int(y)))

    def shutdown(self) -> None:
        self._initialized = False


def test_initialize_enables_timebeginperiod_1(monkeypatch):
    calls: list[tuple[str, int]] = []

    class FakeWinmm:
        def timeBeginPeriod(self, ms: int) -> None:
            calls.append(("begin", ms))

        def timeEndPeriod(self, ms: int) -> None:
            calls.append(("end", ms))

    class FakeWindll:
        winmm = FakeWinmm()

    _patch_backend(monkeypatch)
    monkeypatch.setattr(clicker_mod.ctypes, "windll", FakeWindll())

    clicker = Clicker()
    clicker.initialize()

    assert calls == [("begin", 1)]


def test_shutdown_releases_timeendperiod_1(monkeypatch):
    calls: list[tuple[str, int]] = []

    class FakeWinmm:
        def timeBeginPeriod(self, ms: int) -> None:
            calls.append(("begin", ms))

        def timeEndPeriod(self, ms: int) -> None:
            calls.append(("end", ms))

    class FakeWindll:
        winmm = FakeWinmm()

    _patch_backend(monkeypatch)
    monkeypatch.setattr(clicker_mod.ctypes, "windll", FakeWindll())

    clicker = Clicker()
    clicker.initialize()
    clicker.shutdown()

    assert calls == [("begin", 1), ("end", 1)]


def test_initialize_twice_does_not_begin_twice(monkeypatch):
    calls: list[tuple[str, int]] = []

    class FakeWinmm:
        def timeBeginPeriod(self, ms: int) -> None:
            calls.append(("begin", ms))

        def timeEndPeriod(self, ms: int) -> None:
            calls.append(("end", ms))

    class FakeWindll:
        winmm = FakeWinmm()

    _patch_backend(monkeypatch)
    monkeypatch.setattr(clicker_mod.ctypes, "windll", FakeWindll())

    clicker = Clicker()
    clicker.initialize()
    clicker.initialize()

    assert calls == [("begin", 1)]


def test_direct_first_skips_bezier_for_first_click(monkeypatch):
    backend = _FakeBackend()

    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: backend)
    monkeypatch.setattr(Clicker, "_get_cursor_pos", lambda self: (100, 100))

    clicker = Clicker()
    clicker.initialize()

    clicker.spam_click(960, 520, count=1, direct_first=True)

    kinds = [e[0] for e in backend.events]
    assert kinds == ["move", "down", "up"], kinds


def test_direct_first_stabilization_sleep(monkeypatch):
    sleeps: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)
    _patch_backend(monkeypatch)

    clicker = Clicker()
    clicker.initialize()
    clicker.spam_click(960, 520, count=1, direct_first=True)

    assert len(sleeps) >= 2, sleeps
    assert sleeps[0] == 0.025, sleeps
    assert sleeps[1] == 0.018, sleeps


def test_default_keeps_bezier_first_click(monkeypatch):
    backend = _FakeBackend()

    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: backend)
    monkeypatch.setattr(Clicker, "_get_cursor_pos", lambda self: (100, 100))

    clicker = Clicker()
    clicker.initialize()

    clicker.spam_click(960, 520, count=1)

    kinds = [e[0] for e in backend.events]
    assert "move" in kinds
    assert kinds[-1] == "up"


def test_default_hold_is_18ms(monkeypatch):
    sleeps: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)
    _patch_backend(monkeypatch)

    clicker = Clicker()
    clicker.initialize()
    clicker.spam_click(960, 520, count=1, direct_first=True)

    assert 0.018 in sleeps, sleeps
    assert sleeps[-1] == 0.018, sleeps


def test_click_at_uses_18ms_hold(monkeypatch):
    sleeps: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)
    _patch_backend(monkeypatch)
    monkeypatch.setattr(Clicker, "_get_cursor_pos", lambda self: (100, 100))

    clicker = Clicker()
    clicker.initialize()
    clicker.click_at(960, 520, times=1)

    settle, hold = sleeps[-2], sleeps[-1]
    assert 0.005 <= settle <= 0.015
    assert hold == 0.018


def test_mode_60_inter_click_delay_respects_cps(monkeypatch):
    sleeps: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)
    _patch_backend(monkeypatch)

    clicker = Clicker(
        input_fps_mode="60",
        click_jitter_ms=0.0,
    )
    clicker.initialize()
    clicker.spam_click(960, 520, count=2, clicks_per_sec=30, direct_first=True)

    stabilization, hold1, delay, hold2 = sleeps
    assert stabilization == 0.025
    assert hold1 == 0.018
    # 30 CPS is below the 35 CPS safe cap, so period = 1/30 = 33.3ms,
    # delay = 33.3 - 18 = 15.3ms.
    assert 0.014 <= delay <= 0.017, delay
    assert hold2 == 0.018


def test_click_jitter_introduces_uniformity(monkeypatch):
    monkeypatch.setattr(clicker_mod.time, "sleep", lambda s: None)
    _patch_backend(monkeypatch)

    clicker = Clicker(
        input_fps_mode="60",
        click_jitter_ms=0.5,
    )
    clicker.initialize()
    delays = {round(clicker._cycle_delay_s(30) + clicker._hold_delay_s(), 4) for _ in range(10)}
    assert len(delays) > 1


def test_spam_click_inter_click_delay_uses_time_sleep(monkeypatch):
    sleeps: list[float] = []

    def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)
    _patch_backend(monkeypatch)

    clicker = Clicker(
        input_fps_mode="60",
        click_jitter_ms=0.0,
    )
    clicker.initialize()
    clicker.spam_click(960, 520, count=2, clicks_per_sec=30, direct_first=True)

    assert sleeps[0] == 0.025
    inter_click_sleeps = [s for s in sleeps[1:] if s >= 0.003 and s != 0.018]
    assert len(inter_click_sleeps) >= 1, (
        f"inter-click delay must use time.sleep for GIL release, "
        f"got sleeps={sleeps} (only 0.018ms holds + 0.001ms micro-moves, "
        f"no inter-click delay sleep -> busy-wait regression)"
    )
    total_delay = sum(inter_click_sleeps)
    assert 0.012 <= total_delay <= 0.018, (
        f"inter-click delay sum={total_delay:.4f}s, expected ~15ms"
    )


def test_target_cps_clamps_to_35_in_60fps_mode():
    clicker = Clicker(input_fps_mode="60")
    assert clicker._target_cps(100) == 35.0
    assert clicker._target_cps(60) == 35.0
    assert clicker._target_cps(38) == 35.0
    assert clicker._target_cps(30) == 30.0
    assert clicker._target_cps(None) == 30.0


def test_cycle_delay_guarantees_up_gap_headroom():
    clicker = Clicker(input_fps_mode="60", click_jitter_ms=0.0)
    for cps in (30, 35, 38, 60, 100):
        delay = clicker._cycle_delay_s(cps)
        hold = clicker._hold_delay_s()
        # UP gap must always be >= the headroom so events are never coalesced.
        assert hold + delay >= 0.026, (cps, delay)


def test_min_up_gap_never_below_10ms_60fps():
    clicker = Clicker(input_fps_mode="60", click_jitter_ms=0.0)
    hold = clicker._hold_delay_s()
    for cps in (30, 35, 38, 60, 100):
        target = clicker._target_cps(cps)
        period = 1.0 / target
        up_gap = period - hold
        assert up_gap >= 0.010, (cps, target, up_gap)


# ---------------------------------------------------------------------------
# #4: Watchdog fokusu okna gry podczas spam_click
# ---------------------------------------------------------------------------


class _FakeWindowFinder:
    """Fake ``mvp.bot.window_finder`` for the focus-watchdog tests."""

    def __init__(
        self,
        *,
        is_foreground_seq: list[bool] | None = None,
        force_foreground_succeeds: bool = True,
    ) -> None:
        self.is_foreground_calls = 0
        self.force_foreground_calls = 0
        self._is_foreground_seq = list(is_foreground_seq or [])
        self._force_foreground_succeeds = force_foreground_succeeds

    def is_foreground(self, process_name: str) -> bool:
        self.is_foreground_calls += 1
        if self._is_foreground_seq:
            return self._is_foreground_seq.pop(0)
        return True

    def force_foreground(self, process_name: str = "Survival.exe") -> bool:
        self.force_foreground_calls += 1
        return self._force_foreground_succeeds


def _patch_focus_watchdog(monkeypatch, fake: _FakeWindowFinder) -> None:
    import mvp.bot.window_finder as wf_mod

    monkeypatch.setattr(wf_mod, "is_foreground", fake.is_foreground)
    monkeypatch.setattr(wf_mod, "force_foreground", fake.force_foreground)


def test_focus_check_default_interval_is_5():
    clicker = Clicker()
    assert clicker.focus_check_interval == 5
    assert clicker.focus_watchdog_enabled is True


def test_focus_check_can_be_disabled(monkeypatch):
    fake = _FakeWindowFinder()
    _patch_backend(monkeypatch)
    _patch_focus_watchdog(monkeypatch, fake)

    clicker = Clicker(focus_watchdog_enabled=False)
    clicker.initialize()
    clicker.spam_click(960, 520, count=20)

    assert fake.is_foreground_calls == 0
    assert fake.force_foreground_calls == 0


def test_focus_check_calls_is_foreground_time_based(monkeypatch):
    fake = _FakeWindowFinder()  # always in foreground → no refocus
    _patch_backend(monkeypatch)
    _patch_focus_watchdog(monkeypatch, fake)

    clicker = Clicker(
        focus_check_interval=3,
        focus_check_interval_s=0.0,  # every click triggers a focus check
    )
    clicker.initialize()
    clicker.spam_click(960, 520, count=10)

    assert fake.is_foreground_calls == 10
    assert fake.force_foreground_calls == 0


def test_focus_check_refocuses_when_focus_lost(monkeypatch, caplog):
    import logging

    fake = _FakeWindowFinder(is_foreground_seq=[True, False, False, False])
    _patch_backend(monkeypatch)
    _patch_focus_watchdog(monkeypatch, fake)

    clicker = Clicker(
        focus_check_interval=3,
        focus_check_interval_s=0.0,
    )
    clicker.initialize()
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="mvp.bot.clicker"):
        delivered = clicker.spam_click(960, 520, count=12)

    assert delivered == 12
    # Re-focus is deferred and applied at most once per spam run.
    assert fake.force_foreground_calls == 1
    warn_msgs = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warn_msgs) == 1, [r.message for r in warn_msgs]


def test_focus_check_warns_only_once_per_spam_run(monkeypatch, caplog):
    import logging

    fake = _FakeWindowFinder(is_foreground_seq=[False] * 100)
    _patch_backend(monkeypatch)
    _patch_focus_watchdog(monkeypatch, fake)

    clicker = Clicker(
        focus_check_interval=2,
        focus_check_interval_s=0.0,
    )
    clicker.initialize()
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="mvp.bot.clicker"):
        clicker.spam_click(960, 520, count=6)
        clicker.spam_click(960, 520, count=6)

    warns = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warns) == 2, [r.message for r in warns]


def test_focus_check_swallow_force_foreground_failure(monkeypatch):
    fake = _FakeWindowFinder(
        is_foreground_seq=[False] * 100,
        force_foreground_succeeds=False,
    )

    def boom(process_name: str = "Survival.exe") -> bool:
        fake.force_foreground_calls += 1
        raise OSError("simulated SetForegroundWindow failure")

    import mvp.bot.window_finder as wf_mod

    monkeypatch.setattr(wf_mod, "is_foreground", fake.is_foreground)
    monkeypatch.setattr(wf_mod, "force_foreground", boom)

    _patch_backend(monkeypatch)

    clicker = Clicker(
        focus_check_interval=2,
        focus_check_interval_s=0.0,
    )
    clicker.initialize()

    delivered = clicker.spam_click(960, 520, count=6)
    assert delivered == 6
    assert fake.force_foreground_calls >= 1


def test_focus_check_aborts_cleanly_when_already_not_initialized(monkeypatch):
    from mvp.bot.exceptions import ClickerError

    monkeypatch.setattr(Clicker, "initialize", lambda self: None)

    clicker = Clicker(focus_check_interval=2)
    clicker._initialized = False

    with pytest.raises(ClickerError):
        clicker.spam_click(960, 520, count=4)
    assert clicker._focus_refocus_warned is False


def test_scroll_window_posts_wm_mousewheel(monkeypatch):
    posted = []

    class FakeUser32:
        def PostMessageW(self, hwnd, msg, w_param, l_param):
            posted.append((hwnd, msg, w_param, l_param))
            return 1

    class FakeWindll:
        user32 = FakeUser32()

    monkeypatch.setattr(clicker_mod.ctypes, "windll", FakeWindll())

    clicker = Clicker()
    res = clicker.scroll_window(hwnd=1234, screen_x=500, screen_y=300, direction="down", ticks=2)
    assert res is True
    assert len(posted) == 2
    assert posted[0][0] == 1234
    assert posted[0][1] == 0x020A

    posted.clear()
    res_up = clicker.scroll_window(hwnd=1234, screen_x=500, screen_y=300, direction="up", ticks=1)
    assert res_up is True
    assert len(posted) == 1
    assert posted[0][1] == 0x020A

    assert clicker.scroll_window(hwnd=0, screen_x=500, screen_y=300) is False
    assert clicker.scroll_window(hwnd=1234, screen_x=500, screen_y=300, direction="left") is False


def test_precise_sleep_accuracy():
    import ctypes
    import os
    import time

    from mvp.bot.clicker import precise_sleep

    if os.name == "nt":
        ctypes.windll.winmm.timeBeginPeriod(1)
    try:
        start = time.perf_counter()
        precise_sleep(0.010)  # 10ms
        elapsed = time.perf_counter() - start
        assert 0.0095 <= elapsed <= 0.200
    finally:
        if os.name == "nt":
            ctypes.windll.winmm.timeEndPeriod(1)


def test_precise_sleep_spins_only_micro_window(monkeypatch):
    """The spin/yield phase must be bounded: a large remainder is handled by a
    real (positive) time.sleep, not a tight zero-yield loop."""
    from mvp.bot.clicker import precise_sleep

    clock = {"t": 0.0}

    def fake_perf_counter():
        clock["t"] += 0.00005
        return clock["t"]

    monkeypatch.setattr(clicker_mod.time, "perf_counter", fake_perf_counter)

    zero_yields = {"n": 0}
    positive_sleeps = {"n": 0}

    def fake_sleep(d):
        if d <= 0:
            zero_yields["n"] += 1
        else:
            positive_sleeps["n"] += 1
            clock["t"] += d

    fake_sleep.__name__ = "sleep"
    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)

    precise_sleep(0.5)

    assert positive_sleeps["n"] >= 1, "large remainder must use a real positive sleep"
    assert zero_yields["n"] < 100, zero_yields["n"]


def test_precise_sleep_no_zero_loop_for_large_rem(monkeypatch):
    """For a large remainder the code must issue one dominant real sleep (~0.249s),
    never a burst of time.sleep(0) busy-yields."""
    from mvp.bot.clicker import precise_sleep

    clock = {"t": 0.0}

    def fake_perf_counter():
        clock["t"] += 0.00005
        return clock["t"]

    monkeypatch.setattr(clicker_mod.time, "perf_counter", fake_perf_counter)
    sleeps = []

    def fake_sleep(d):
        sleeps.append(d)
        if d > 0:
            clock["t"] += d

    fake_sleep.__name__ = "sleep"
    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)

    precise_sleep(0.25)

    assert any(s >= 0.24 for s in sleeps), sleeps


def test_spin_until_busy_waits_within_micro_window(monkeypatch):
    """For a remainder within PRECISE_SPIN_WINDOW_S the code must busy-wait."""
    from mvp.bot.clicker import _spin_until

    target = 0.0002
    slept = []
    calls = {"n": 0}

    def fake_perf_counter():
        calls["n"] += 1
        # Within the spin window the loop busy-waits; after a few iterations the
        # clock advances past the target so the spin terminates.
        if calls["n"] >= 3:
            return target + 0.001
        return 0.0

    def fake_sleep(d):
        slept.append(d)

    fake_sleep.__name__ = "sleep"
    monkeypatch.setattr(clicker_mod.time, "perf_counter", fake_perf_counter)
    monkeypatch.setattr(clicker_mod.time, "sleep", fake_sleep)

    _spin_until(target)
    # The function must NOT have used time.sleep for this micro-window.
    assert len(slept) == 0, slept


def test_check_focus_time_based(monkeypatch):
    """Focus checks are gated by elapsed wall-clock time, not click count."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(clicker_mod.time, "monotonic", lambda: clock["t"])

    clicker = Clicker(focus_check_interval=5, focus_check_interval_s=2.0)
    clicker._last_focus_check = 0.0

    assert clicker._should_check_focus() is True   # 1000 - 0 >= 2
    clock["t"] = 1001.0
    assert clicker._should_check_focus() is False  # 1s elapsed < 2s
    clock["t"] = 1002.5
    assert clicker._should_check_focus() is True   # 2.5s elapsed >= 2s


def test_approach_b_noise_separation():
    import math

    clicker = Clicker(spam_noise_px=3.0)
    for _ in range(50):
        ox1, oy1 = clicker._noise_offset()
        ox2, oy2 = clicker._noise_offset()
        dist = math.hypot(ox2 - ox1, oy2 - oy1)
        assert dist >= 5.0, f"Distance {dist} must be >= 5.0 px to bypass ClickDetector"
        assert dist <= 8.5, f"Distance {dist} must stay <= 8.5 px inside chest collider"


def test_uipi_admin_warning_on_initialize(monkeypatch):
    clicker = Clicker()
    _patch_backend(monkeypatch)
    clicker.initialize()
    assert clicker.is_initialized
    clicker.shutdown()
