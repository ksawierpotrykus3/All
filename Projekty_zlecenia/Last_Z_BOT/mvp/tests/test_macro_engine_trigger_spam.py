"""P1-1: MacroEngine.trigger_spam (F1 hotkey path) — was 0% tested.

The global F1 hotkey arms spam-click sequences on the chest-spawn instant.
This is the most critical hot path in the bot — yet before this commit it
had no unit tests. These tests pin down:

- ``trigger_spam`` with no clicker → no-op (no exception).
- ``trigger_spam`` with no resolved target → no spam_click call.
- ``trigger_spam`` with resolved target → spam_click called with correct coords.
- ``trigger_spam`` skips when ``_spam_in_flight`` is already held (concurrency).
- ``trigger_spam`` falls back to window center when target is None.

The tests use lightweight ``_FakeClicker`` / ``_FakeCapture`` stand-ins
matching the existing pattern in ``test_macro_engine.py``.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np

from mvp.bot.coordinates import WindowContext
from mvp.bot.macro_engine import Macro, MacroEngine, MacroStep, StepType


class _FakeClicker:
    """Records every spam_click invocation. No real WinAPI."""

    def __init__(self) -> None:
        self.clicks: list[tuple[int, int]] = []
        self.spam_calls: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def click_at(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def spam_click(
        self,
        x: int,
        y: int,
        count: int,
        deadline: float | None = None,
        clicks_per_sec: int | None = None,
        direct_first: bool = False,
    ) -> int:
        with self.lock:
            self.spam_calls.append(
                {
                    "x": x,
                    "y": y,
                    "count": count,
                    "deadline": deadline,
                    "clicks_per_sec": clicks_per_sec,
                    "direct_first": direct_first,
                }
            )
        return count


class _FakeChatOCR:
    def __init__(self) -> None:
        self.alert = None
        self.calls = 0

    def find_helicopter_alert(self, image) -> dict | None:
        self.calls += 1
        return self.alert


class _FakeTimerOCR:
    def __init__(self) -> None:
        self.values: list[int | None] = []

    def read_timer(self, image) -> int | None:
        return self.values.pop(0) if self.values else None


class _FakeCapture:
    def __init__(self) -> None:
        self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def grab(self) -> np.ndarray | None:
        return self.frame


def _make_engine(
    clicker: _FakeClicker | None = None,
    window: WindowContext | None = None,
    macro: Macro | None = None,
) -> MacroEngine:
    """Construct a MacroEngine with all fakes wired up. No real backend I/O."""
    engine = MacroEngine(
        clicker=clicker if clicker is not None else _FakeClicker(),
        chat_ocr=_FakeChatOCR(),
        timer_ocr=_FakeTimerOCR(),
        capture=_FakeCapture(),
    )
    if macro is not None:
        engine._current_macro = macro
    if window is not None:
        engine._current_window = window
    return engine


def _join_background_threads(engine: MacroEngine, timeout: float = 1.0) -> None:
    """Drain any daemon threads triggered by ``trigger_spam`` for clean assertions."""
    deadline = time.monotonic() + timeout
    for thread in list(threading.enumerate()):
        if thread is threading.current_thread():
            continue
        if thread.daemon and thread.is_alive():
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)


# ────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────


def test_trigger_spam_with_no_clicker_is_noop() -> None:
    """AGENTS.md §8: when no clicker is wired, trigger_spam MUST NOT raise."""
    engine = MacroEngine(
        clicker=None,
        chat_ocr=_FakeChatOCR(),
        timer_ocr=_FakeTimerOCR(),
        capture=_FakeCapture(),
    )
    # No exception, no side effect.
    engine.trigger_spam()


def test_trigger_spam_with_no_window_and_no_explicit_target_is_noop() -> None:
    """Without a window + without explicit target, spam has nowhere to click."""
    clicker = _FakeClicker()
    engine = _make_engine(clicker=clicker)
    # _spam_target_x / _spam_target_y default to None → falls into _resolve_spam_target.
    # No macro / no window → returns None → spam_click not called.
    engine.trigger_spam()
    assert clicker.spam_calls == []
    assert clicker.clicks == []


def test_trigger_spam_with_explicit_target_invokes_spam_click() -> None:
    """When the engine has a known spam target, trigger_spam MUST invoke spam_click."""
    clicker = _FakeClicker()
    engine = _make_engine(clicker=clicker)
    engine._spam_target_x = 1234
    engine._spam_target_y = 567
    engine._spam_duration_s = 0.2  # tiny duration so the thread terminates fast
    engine._spam_cps = 38

    engine.trigger_spam()
    _join_background_threads(engine)

    assert len(clicker.spam_calls) == 1, clicker.spam_calls
    call = clicker.spam_calls[0]
    assert call["x"] == 1234
    assert call["y"] == 567
    assert call["clicks_per_sec"] == 38
    # count = int(duration * cps) = int(0.2 * 38) = 7
    assert call["count"] == 7
    assert call["direct_first"] is True


def test_trigger_spam_with_resolved_target_via_macro_invokes_spam_click() -> None:
    """When only the macro has a WATCH_TIMER step with click coords, resolve and spam."""
    clicker = _FakeClicker()
    window = WindowContext(left=0, top=0, width=1920, height=1080)
    macro = Macro(
        name="test",
        steps=[
            MacroStep(
                type=StepType.WATCH_TIMER,
                click_x=50.0,
                click_y=50.0,
                spam_duration_s=0.05,
                spam_clicks_per_sec=20,
            )
        ],
    )
    engine = _make_engine(clicker=clicker, window=window, macro=macro)
    engine._current_window = window
    engine._get_fresh_window = lambda w: window  # type: ignore[assignment]

    engine.trigger_spam()
    _join_background_threads(engine)

    assert len(clicker.spam_calls) == 1, clicker.spam_calls
    call = clicker.spam_calls[0]
    # click_x=50%, click_y=50% → center of 1920x1080 window
    assert call["x"] > 0 and call["x"] < 1920
    assert call["y"] > 0 and call["y"] < 1080
    assert call["clicks_per_sec"] == 20
    assert call["count"] == int(0.05 * 20)  # 1 click


def test_trigger_spam_skips_when_spam_in_flight() -> None:
    """If another spam is already running, the second trigger_spam MUST be a no-op."""
    clicker = _FakeClicker()
    engine = _make_engine(clicker=clicker)
    engine._spam_target_x = 100
    engine._spam_target_y = 200
    engine._spam_duration_s = 5.0  # long enough that the first is still "in flight"
    engine._spam_cps = 38

    # Simulate that a previous spam is in flight.
    engine._spam_in_flight = True

    engine.trigger_spam()
    # Second thread MUST NOT have been spawned.
    assert clicker.spam_calls == []


def test_trigger_spam_releases_lock_after_thread_completes() -> None:
    """After the spam thread completes, _spam_in_flight MUST be reset to False."""
    clicker = _FakeClicker()
    engine = _make_engine(clicker=clicker)
    engine._spam_target_x = 100
    engine._spam_target_y = 200
    engine._spam_duration_s = 0.05
    engine._spam_cps = 38

    engine.trigger_spam()
    _join_background_threads(engine)

    assert engine._spam_in_flight is False, (
        "_spam_in_flight must be released after the spam thread completes"
    )


def test_trigger_spam_default_params_when_none_set() -> None:
    """When neither macro nor explicit params are set, defaults (3.0 s @ 38 CPS) apply."""
    clicker = _FakeClicker()
    window = WindowContext(left=0, top=0, width=1920, height=1080)
    engine = _make_engine(clicker=clicker, window=window)
    engine._spam_target_x = 100
    engine._spam_target_y = 200
    # No macro, no explicit duration/cps → defaults from _resolve_spam_params.

    engine.trigger_spam()
    _join_background_threads(engine)

    assert len(clicker.spam_calls) == 1
    call = clicker.spam_calls[0]
    # Default 3.0 s @ 38 CPS = 114 clicks.
    assert call["clicks_per_sec"] == 38
    assert call["count"] == int(3.0 * 38)


def test_resolve_spam_target_returns_none_when_no_macro_or_window() -> None:
    """_resolve_spam_target MUST return None when macro and window are both None."""
    engine = _make_engine()
    assert engine._resolve_spam_target() is None


def test_resolve_spam_target_returns_none_when_macro_has_no_watch_timer() -> None:
    """A macro with no WATCH_TIMER step MUST NOT produce a target."""
    engine = _make_engine(window=WindowContext(0, 0, 1920, 1080))
    engine._current_macro = Macro(
        name="test",
        steps=[MacroStep(type=StepType.WAIT, seconds=1.0)],
    )
    assert engine._resolve_spam_target() is None


def test_resolve_spam_target_with_click_xy_uses_screen_coords() -> None:
    """click_x/click_y percentages MUST be converted to screen pixels."""
    window = WindowContext(left=0, top=0, width=1920, height=1080)
    engine = _make_engine(window=window)
    engine._get_fresh_window = lambda w: window  # type: ignore[assignment]
    engine._current_macro = Macro(
        name="test",
        steps=[
            MacroStep(
                type=StepType.WATCH_TIMER,
                click_x=50.0,
                click_y=50.0,
            )
        ],
    )
    target = engine._resolve_spam_target()
    assert target is not None
    x, y = target
    # Should be somewhere near the window center.
    assert 0 < x < 1920
    assert 0 < y < 1080


def test_resolve_spam_target_with_roi_pct_uses_roi_center() -> None:
    """roi_pct MUST yield the ROI center as the spam target."""
    window = WindowContext(left=0, top=0, width=1920, height=1080)
    engine = _make_engine(window=window)
    engine._get_fresh_window = lambda w: window  # type: ignore[assignment]
    engine._current_macro = Macro(
        name="test",
        steps=[
            MacroStep(
                type=StepType.WATCH_TIMER,
                roi_pct={"left": 25.0, "top": 25.0, "right": 75.0, "bottom": 75.0},
            )
        ],
    )
    target = engine._resolve_spam_target()
    assert target is not None
    x, y = target
    # ROI center 50%, 50% → near window center
    assert 0 < x < 1920
    assert 0 < y < 1080
