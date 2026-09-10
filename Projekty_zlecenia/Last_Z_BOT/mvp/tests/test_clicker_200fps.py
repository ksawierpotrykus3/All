"""P1-2: 200 FPS mode — DOWN hold time MUST be 3.0 ± 0.3 ms.

AGENTS.md §3 specifies that the patched 200 Hz client uses ``DIG_HOLD_MS_200FPS``
= 3.0 ms with a ±0.3 ms jitter — enough to evade Unity's ``ClickIntervalMonitor``
constant-hold detector. These tests pin down the hold range, jitter behaviour,
and timing arithmetic.

We mock ``_hold_delay_s`` to return controlled values and record the targets
passed to ``precise_sleep_until`` to verify timing math independently of
real elapsed time.
"""

from __future__ import annotations

import pytest

from mvp.bot import clicker as clicker_mod
from mvp.bot.clicker import (
    DIG_HOLD_MS_200FPS,
    INPUT_FPS_MODES,
    Clicker,
)


class _NoopBackend:
    """Stub backend that records each spam_* call. No real WinAPI."""

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
        pass

    def scroll(self, direction: str) -> None:
        pass

    def get_cursor_pos(self) -> tuple[int, int]:
        return (0, 0)

    def spam_down(self, x: int, y: int) -> None:
        self.events.append(("down", int(x), int(y)))

    def spam_up(self, x: int, y: int) -> None:
        self.events.append(("up", int(x), int(y)))

    def spam_move(self, x: int, y: int) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False


@pytest.fixture(autouse=True)
def _restore_backend():
    orig = clicker_mod.initialize_backend
    yield
    clicker_mod.initialize_backend = orig


def _make_clicker(*, input_fps_mode: str = "200",
                  click_jitter_ms: float = 0.5) -> Clicker:
    backend = _NoopBackend()
    clicker_mod.initialize_backend = lambda mode: backend  # type: ignore[assignment]
    clicker = Clicker(input_fps_mode=input_fps_mode, click_jitter_ms=click_jitter_ms)
    clicker.initialize()
    return clicker


def _make_clicker_no_jitter(*, input_fps_mode: str = "200") -> Clicker:
    return _make_clicker(input_fps_mode=input_fps_mode, click_jitter_ms=0.0)


# ────────────────────────────────────────────────────────────────────────
# Static / unit tests on the hold helper
# ────────────────────────────────────────────────────────────────────────


def test_200fps_constant_is_three_ms() -> None:
    """DIG_HOLD_MS_200FPS MUST equal 3 ms (AGENTS.md §3)."""
    assert DIG_HOLD_MS_200FPS == 3


def test_input_fps_modes_includes_200() -> None:
    """INPUT_FPS_MODES MUST include both '60' and '200'."""
    assert "200" in INPUT_FPS_MODES
    assert "60" in INPUT_FPS_MODES


def test_60fps_hold_is_18ms_constant() -> None:
    """60 FPS MUST hold for fixed 18 ms (no jitter)."""
    clicker = _make_clicker(input_fps_mode="60")
    for _ in range(20):
        assert clicker._hold_delay_s() == 0.018


def test_200fps_hold_is_in_range() -> None:
    """Each _hold_delay_s() call MUST return a value in [0.0027, 0.0033] s."""
    clicker = _make_clicker(input_fps_mode="200")
    samples = [clicker._hold_delay_s() for _ in range(50)]
    assert all(0.0027 <= s <= 0.0033 for s in samples), (
        f"holds outside [2.7, 3.3] ms range: min={min(samples)*1000}, "
        f"max={max(samples)*1000}"
    )


def test_200fps_jitter_introduces_variance() -> None:
    """Repeated calls MUST show some variance (jitter ≠ constant)."""
    clicker = _make_clicker(input_fps_mode="200")
    samples = [clicker._hold_delay_s() for _ in range(50)]
    assert min(samples) < max(samples), (
        f"all 200-FPS holds identical (no jitter applied): {samples[:5]}"
    )


def test_60fps_has_no_jitter() -> None:
    """60 FPS MUST NOT add random jitter to the hold time."""
    clicker = _make_clicker(input_fps_mode="60")
    samples = [clicker._hold_delay_s() for _ in range(20)]
    assert len(set(samples)) == 1, (
        f"60 FPS should have constant 18 ms hold, got variation: {set(samples)}"
    )


# ────────────────────────────────────────────────────────────────────────
# spam_click timing arithmetic
# ────────────────────────────────────────────────────────────────────────


def test_200fps_spam_click_holds_for_3ms(monkeypatch) -> None:
    """spam_click in 200 FPS mode MUST call precise_sleep_until with up - hold = 3 ms.

    We patch ``_hold_delay_s`` to return exactly 3 ms (no jitter) and
    ``precise_sleep_until`` to record the target time. The gap between the
    ``down`` and ``up`` targets MUST be exactly 3 ms.
    """
    clicker = _make_clicker(input_fps_mode="200")
    monkeypatch.setattr(clicker, "_hold_delay_s", lambda: 0.003)

    targets: list[tuple[str, float]] = []

    def fake_sleep_until(target: float) -> None:
        # Track which "phase" we're in — down or up.
        kind = "down" if len(targets) % 2 == 0 else "up"
        targets.append((kind, float(target)))

    monkeypatch.setattr(clicker_mod, "precise_sleep_until", fake_sleep_until)
    # Lock perf_counter to a constant so t_curr_down = t_spam_start.
    monkeypatch.setattr(clicker_mod.time, "perf_counter", lambda: 1000.0)

    clicker.spam_click(960, 520, count=1, clicks_per_sec=50, direct_first=True)

    assert len(targets) >= 2
    down_target = targets[0][1]
    up_target = targets[1][1]
    hold_ms = (up_target - down_target) * 1000
    assert abs(hold_ms - 3.0) < 1e-9, f"hold {hold_ms} ms ≠ 3.0 ms"


def test_200fps_jitter_propagates_to_hold(monkeypatch) -> None:
    """When _hold_delay_s returns 0.0027, the recorded hold gap MUST be 2.7 ms."""
    clicker = _make_clicker(input_fps_mode="200")
    monkeypatch.setattr(clicker, "_hold_delay_s", lambda: 0.0027)

    targets: list[tuple[str, float]] = []

    def fake_sleep_until(target: float) -> None:
        kind = "down" if len(targets) % 2 == 0 else "up"
        targets.append((kind, float(target)))

    monkeypatch.setattr(clicker_mod, "precise_sleep_until", fake_sleep_until)
    monkeypatch.setattr(clicker_mod.time, "perf_counter", lambda: 1000.0)

    clicker.spam_click(960, 520, count=1, clicks_per_sec=50, direct_first=True)

    down_target = targets[0][1]
    up_target = targets[1][1]
    hold_ms = (up_target - down_target) * 1000
    assert abs(hold_ms - 2.7) < 1e-9, f"hold {hold_ms} ms ≠ 2.7 ms (jitter not applied)"


def test_200fps_period_at_50cps_is_20ms(monkeypatch) -> None:
    """At 50 CPS (period 20 ms), the inter-click period MUST be 20 ms.

    With hold=3 ms and period=20 ms, gap=17 ms. We verify the gap between
    successive ``t_curr_down`` targets is 20 ms.

    Per click, spam_click calls precise_sleep_until three times: t_curr_down,
    t_up (=t_curr_down+hold), and t_move (40% into the gap, skipped for the
    last click). For 3 clicks we expect 3 * 3 - 1 = 8 calls.
    """
    clicker = _make_clicker_no_jitter(input_fps_mode="200")
    monkeypatch.setattr(clicker, "_hold_delay_s", lambda: 0.003)

    targets: list[tuple[str, float]] = []

    def fake_sleep_until(target: float) -> None:
        targets.append(("x", float(target)))

    monkeypatch.setattr(clicker_mod, "precise_sleep_until", fake_sleep_until)
    monkeypatch.setattr(clicker_mod.time, "perf_counter", lambda: 1000.0)

    # 3 clicks @ 50 CPS.
    clicker.spam_click(960, 520, count=3, clicks_per_sec=50, direct_first=True)

    # Per-click triplet: (down, up, move). The last move is skipped.
    assert len(targets) == 8, f"unexpected target count: {targets}"
    # t_curr_down is at index 0, 3, 6.
    down_0 = targets[0][1]
    down_1 = targets[3][1]
    down_2 = targets[6][1]
    period_ms_01 = (down_1 - down_0) * 1000
    period_ms_12 = (down_2 - down_1) * 1000
    assert abs(period_ms_01 - 20.0) < 1e-9, (
        f"period 0→1 is {period_ms_01} ms ≠ 20 ms (50 CPS)"
    )
    assert abs(period_ms_12 - 20.0) < 1e-9, (
        f"period 1→2 is {period_ms_12} ms ≠ 20 ms (50 CPS)"
    )
