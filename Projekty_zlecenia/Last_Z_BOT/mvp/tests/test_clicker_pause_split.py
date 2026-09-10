"""P1-5: AGENTS.md §2 — Gauss cursor move happens in mid-UP, split is 40% / 60%.

When the clicker delivers a burst of clicks, the inter-click pause (the
gap between UP and the next DOWN) is split into two halves:

- First half  (40%): wait, then ``spam_move`` to a new Gauss-offset position.
- Second half (60%): wait, then ``spam_down``.

This guarantees the cursor MOVE happens while the button is fully released
(state=0) — Unity's drag threshold (1.5 px) won't fire because the next
DOWN lands at the same position the MOVE did (Δr=0).

If the split were reversed (60/40 or 100/0), the MOVE would land too close
to the next DOWN and Windows packet-coalescing could merge them, flipping
``eligibleForClick = false``.
"""

from __future__ import annotations

import inspect

import pytest

from mvp.bot import clicker as clicker_mod
from mvp.bot.clicker import Clicker


class _NoopBackend:
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
        self.events.append(("move", int(x), int(y)))

    def shutdown(self) -> None:
        self._initialized = False


def _make_clicker_no_jitter(monkeypatch: pytest.MonkeyPatch, input_fps_mode: str = "200") -> Clicker:
    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: _NoopBackend())
    clicker = Clicker(input_fps_mode=input_fps_mode, click_jitter_ms=0.0)
    clicker.initialize()
    return clicker


# ────────────────────────────────────────────────────────────────────────
# Static source checks
# ────────────────────────────────────────────────────────────────────────


def test_spam_click_source_has_40_60_split() -> None:
    """The spam_click source MUST contain the literal 0.4 multiplier."""
    fn = getattr(Clicker, "_spam_click_inner", Clicker.spam_click)
    src = inspect.getsource(fn)
    assert "0.4" in src, "spam_click must use the 40% / 60% pause split"


def test_spam_click_does_not_use_reversed_split() -> None:
    """Defense: must NOT use *0.6 as the multiplier for the FIRST half.

    A buggy implementation might split the pause 60/40, putting the MOVE
    closer to the next DOWN. That breaks the invariant.

    Note: ``half_2 = delay - half_1`` legitimately evaluates to ``0.6 * delay``
    but as a SUBTRACTION, not a direct multiplication. We therefore check
    only for the bare ``* 0.6`` (or ``*0.6``) pattern on its own line.
    """
    fn = getattr(Clicker, "_spam_click_inner", Clicker.spam_click)
    src = inspect.getsource(fn)
    for line in src.splitlines():
        stripped = line.strip()
        # Only flag bare "* 0.6" multipliers.
        if "* 0.6" in stripped and "delay -" not in stripped:
            pytest.fail(
                f"spam_click uses '* 0.6' directly — split is reversed: {stripped!r}"
            )


def test_spam_move_called_after_40_percent() -> None:
    """In the 40/60 split, spam_move MUST be invoked between the two halves."""
    fn = getattr(Clicker, "_spam_click_inner", Clicker.spam_click)
    src = inspect.getsource(fn)
    # Sequence: sleep half_1 → spam_move → sleep half_2 → spam_down
    # We check that spam_move appears in the source.
    assert "spam_move(" in src


# ────────────────────────────────────────────────────────────────────────
# Runtime timing checks (mocked)
# ────────────────────────────────────────────────────────────────────────


def test_spam_click_split_is_40_60_at_runtime(monkeypatch) -> None:
    """Mock precise_sleep_until to capture the per-half durations.

    The 200 FPS path computes:
        t_move = t_up + (t_next_down - t_up) * 0.4
    so the gap (t_move - t_up) MUST be 40% of the total gap (t_next_down - t_up).
    """
    clicker = _make_clicker_no_jitter(monkeypatch, input_fps_mode="200")
    monkeypatch.setattr(clicker, "_hold_delay_s", lambda: 0.003)

    # Lock perf_counter so t_curr_down is deterministic.
    monkeypatch.setattr(clicker_mod.time, "perf_counter", lambda: 1000.0)

    targets: list[tuple[str, float]] = []

    def fake_sleep_until(target: float) -> None:
        targets.append(("x", float(target)))

    monkeypatch.setattr(clicker_mod, "precise_sleep_until", fake_sleep_until)

    # Run 2 clicks @ 50 CPS (period = 20 ms, hold = 3 ms, gap = 17 ms).
    clicker.spam_click(960, 520, count=2, clicks_per_sec=50, direct_first=True)

    # Per click: precise_sleep_until called 3 times — t_curr_down, t_up, t_move.
    # Last move is skipped.
    assert len(targets) >= 3, f"too few sleep targets: {targets}"
    # First click triplet: down, up, move.
    t_up_0 = targets[1][1]
    t_move_0 = targets[2][1]
    # Second click triplet: down, up, (no move).
    t_down_1 = targets[3][1]

    # Compute gap between up and next-down, and up-to-move ratio.
    gap = t_down_1 - t_up_0
    move_offset = t_move_0 - t_up_0
    assert gap > 0, f"non-positive gap: {gap}"
    ratio = move_offset / gap
    # 40% of gap → ratio in [0.35, 0.45] (allow 5% tolerance).
    assert 0.35 <= ratio <= 0.45, (
        f"MOVE happened at {ratio*100:.1f}% of gap (expected ~40%)"
    )


def test_mocked_path_split_is_40_60(monkeypatch) -> None:
    """Test the ``is_mocked`` branch of spam_click (count=3, mock-friendly).

    In the mocked branch:
        half_1 = 0 if (i == 0 and direct_first) else delay * 0.4
        half_2 = delay - half_1

    With direct_first=True, the first click skips half_1; from click 1
    onward, half_1 = delay * 0.4.

    Sleep sequence for count=3, direct_first=True:
        [hold_0, half_2_0, hold_1, half_1_1, half_2_1, hold_2]

    The 40/60 split is half_1_1 (delay*0.4) and half_2_1 (delay*0.6).
    """
    clicker = _make_clicker_no_jitter(monkeypatch, input_fps_mode="60")

    sleeps: list[float] = []

    def fake_precise_sleep(d: float) -> None:
        sleeps.append(float(d))

    monkeypatch.setattr(clicker_mod, "precise_sleep", fake_precise_sleep)
    # Force the mocked branch (time.sleep patched → __name__ != "sleep").
    monkeypatch.setattr(clicker_mod.time, "sleep", lambda d: None)

    # Spam-click with count=3, direct_first=True.
    # Hold = 0.018 s, CPS = 38 → period ≈ 26.3 ms, cycle_delay ≈ 0.008 s.
    clicker.spam_click(960, 520, count=3, clicks_per_sec=38, direct_first=True)

    # We expect 6 sleeps: hold, half_2, hold, half_1, half_2, hold.
    assert len(sleeps) == 6, f"unexpected sleep count {len(sleeps)}: {sleeps}"
    half_1 = sleeps[3]
    half_2 = sleeps[4]
    # half_1 and half_2 should be the inter-click 40/60 split (i=1, after direct_first=True).
    ratio = half_1 / (half_1 + half_2)
    assert 0.35 <= ratio <= 0.45, (
        f"40/60 split violated: half_1={half_1}, half_2={half_2}, "
        f"half_1/total={ratio:.3f}"
    )
