"""ChaoticTimerModel — unpredictable, non-linear countdown for the helka state.

Simulates the treasure box countdown: starts at 10:00 (600s), quickly drops to
~30s, then jumps chaotically (sometimes down 1-4s, sometimes up 3-15s). Despite
the chaotic *displayed* value, a monotonic deadline guarantees the timer always
reaches 0 so the bot's WATCH_TIMER step fires its spam and the loop iteration
completes.

The macro engine tolerates this behaviour by design:
- upward jumps > 2s (`_JUMP_DETECTION_THRESHOLD_S`) re-anchor its T0 estimate,
- downward jumps > 2s between OCR reads are filtered out of `calculate_avg_delta`,
- the countdown lock (<=3.5s) and CPU pause window (<1s) disable OCR entirely, so
  late jumps are invisible to the bot.
"""

import random
import time

# Phase 1: fast ramp-down from the initial 10:00 to the chaotic working range.
_RAMP_DURATION_S = 3.0
_RAMP_TARGET_MIN_S = 28.0
_RAMP_TARGET_MAX_S = 35.0

# Phase 2: chaotic jumps every 2-5s. 60% accelerate (-1..-4s), 40% extend (+3..+15s).
_JUMP_INTERVAL_MIN_S = 2.0
_JUMP_INTERVAL_MAX_S = 5.0
_JUMP_UP_PROBABILITY = 0.4
_JUMP_DOWN_RANGE = (-4.0, -1.0)
_JUMP_UP_RANGE = (3.0, 15.0)

# Hard clamp around the real time-to-deadline: the displayed value may lead the
# real remaining time by at most this much, or lag it by at most this much. Keeps
# the timer bounded so the macro always converges on the true deadline.
_CLAMP_AHEAD_S = 20.0
_CLAMP_BEHIND_S = 8.0

# Convergence window: in the final seconds before the deadline upward jumps are
# disabled and the display is pulled to the real remaining time, so the value
# never bounces back above the bot's 5s spam threshold once it has entered it.
_CONVERGE_WINDOW_S = 8.0

# Deadline is chosen randomly in this range after the start (seconds).
_DEADLINE_MIN_S = 40.0
_DEADLINE_MAX_S = 60.0

_INITIAL_SECONDS = 600.0  # 10:00


class ChaoticTimerModel:
    """Deadline-based timer with a chaotic displayed value.

    The real deadline is monotonic (now >= deadline => 0), but the displayed
    value jitters around the true remaining time within a hard clamp.
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self.start_mono: float | None = None
        self.deadline_mono: float | None = None
        self.display_seconds: float = _INITIAL_SECONDS
        self._next_jump_mono: float | None = None

    @property
    def running(self) -> bool:
        return self.start_mono is not None

    def start(self, now: float | None = None) -> None:
        """Start a fresh countdown: 10:00 with a new random deadline."""
        now = time.monotonic() if now is None else now
        self.start_mono = now
        self.deadline_mono = now + self._rng.uniform(_DEADLINE_MIN_S, _DEADLINE_MAX_S)
        self.display_seconds = _INITIAL_SECONDS
        self._next_jump_mono = None
        self._last_update_mono = None

    def reset(self) -> None:
        """Stop the timer; the next start() begins a fresh randomized cycle."""
        self.start_mono = None
        self.deadline_mono = None
        self.display_seconds = _INITIAL_SECONDS
        self._next_jump_mono = None
        self._last_update_mono = None

    def update(self, now: float | None = None) -> float:
        """Advance the model and return the currently displayed seconds."""
        if self.start_mono is None or self.deadline_mono is None:
            return self.display_seconds
        now = time.monotonic() if now is None else now

        seconds_to_deadline = self.deadline_mono - now
        if seconds_to_deadline <= 0:
            self.display_seconds = 0.0
            return self.display_seconds

        elapsed = now - self.start_mono
        if elapsed < _RAMP_DURATION_S:
            # Fast ramp 600 -> ~30s, anchored to the clamp band.
            ramp_target = self._clamp_bounds_target(seconds_to_deadline)
            progress = elapsed / _RAMP_DURATION_S
            self.display_seconds = _INITIAL_SECONDS + (ramp_target - _INITIAL_SECONDS) * progress
            return self.display_seconds

        if self._next_jump_mono is None:
            self._next_jump_mono = now + self._rng.uniform(
                _JUMP_INTERVAL_MIN_S, _JUMP_INTERVAL_MAX_S
            )

        if now >= self._next_jump_mono:
            if self._rng.random() < _JUMP_UP_PROBABILITY and seconds_to_deadline > _CONVERGE_WINDOW_S:
                self.display_seconds += self._rng.uniform(*_JUMP_UP_RANGE)
            else:
                self.display_seconds += self._rng.uniform(*_JUMP_DOWN_RANGE)
            self._next_jump_mono = now + self._rng.uniform(
                _JUMP_INTERVAL_MIN_S, _JUMP_INTERVAL_MAX_S
            )

        # Natural 1s/s decay since the previous poll keeps the display ticking.
        if self._last_update_mono is not None:
            self.display_seconds -= max(0.0, now - self._last_update_mono)

        if seconds_to_deadline <= _CONVERGE_WINDOW_S:
            # Final approach: converge to the real remaining time, no up-jumps.
            self.display_seconds = min(self.display_seconds, seconds_to_deadline)

        # Hard clamp around the true remaining time.
        self.display_seconds = min(
            max(self.display_seconds, seconds_to_deadline - _CLAMP_BEHIND_S),
            seconds_to_deadline + _CLAMP_AHEAD_S,
        )
        self._last_update_mono = now
        return max(self.display_seconds, 0.0)

    def _clamp_bounds_target(self, seconds_to_deadline: float) -> float:
        """Pick the ramp target inside the clamp band around the deadline."""
        target = self._rng.uniform(_RAMP_TARGET_MIN_S, _RAMP_TARGET_MAX_S)
        return min(
            max(target, seconds_to_deadline - _CLAMP_BEHIND_S),
            seconds_to_deadline + _CLAMP_AHEAD_S,
        )
