"""Tests for #8 — game window auto-recovery.

Scenarios:
- Window found immediately (happy path).
- Window found after several retries.
- Window not found after exhausting the limit (WindowNotFoundError).
- Cache invalidation when the window disappears (IsWindow=False → reset, retry).
- Backoff (intervals grow up to max_backoff_s).
- Reset after a successful find (counter resets).
- is_recovering predicate — whether the watchdog is active.
- Event hook (on_recovery_attempt callback) for UI logs.
"""

from __future__ import annotations

import pytest

from mvp.bot.window_recovery import (
    WindowNotFoundError,
    WindowRecoveryWatchdog,
)


class FakeWindowInfo:
    """Minimal WindowInfo stub for tests."""

    def __init__(self, hwnd: int = 12345):
        self.hwnd = hwnd


class FakeFinder:
    """Stub for ``find_game_window`` — configurable result sequence.

    ``results`` is a list of:
    - object with .hwnd → success, returned to the watchdog
    - None → not found, next attempt
    - raise exception → propagate
    """

    def __init__(self, results: list, sleep_mock=None):
        self._results = list(results)
        self._sleep_mock = sleep_mock
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if not self._results:
            return None
        return self._results.pop(0)


class TestWindowRecoveryWatchdogBasics:
    def test_finds_on_first_attempt(self):
        sleep_calls = []
        finder = FakeFinder([FakeWindowInfo(111)], sleep_mock=sleep_calls.append)

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=5,
            retry_interval_s=1.0,
            sleep=sleep_calls.append,
        )

        result = w.wait_for_window()

        assert result is not None
        assert result.hwnd == 111
        assert finder.call_count == 1
        # No sleep → found immediately
        assert len(sleep_calls) == 0

    def test_finds_after_three_failed_attempts(self):
        sleep_calls = []
        finder = FakeFinder(
            [None, None, None, FakeWindowInfo(222)],
            sleep_mock=sleep_calls.append,
        )

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=10,
            retry_interval_s=0.5,
            sleep=sleep_calls.append,
        )

        result = w.wait_for_window()

        assert result is not None
        assert result.hwnd == 222
        assert finder.call_count == 4
        # 3 retries → 3 sleeps before the final attempt
        assert len(sleep_calls) == 3

    def test_raises_after_max_attempts_exhausted(self):
        sleep_calls = []
        finder = FakeFinder([None] * 10, sleep_mock=sleep_calls.append)

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=3,
            retry_interval_s=0.1,
            sleep=sleep_calls.append,
        )

        with pytest.raises(WindowNotFoundError) as exc:
            w.wait_for_window()

        assert "3" in str(exc.value) or "not found" in str(exc.value).lower()
        assert finder.call_count == 3

    def test_raises_message_contains_english_keywords(self):
        """The exception message uses English keywords regardless of GUI locale."""
        sleep_calls = []
        finder = FakeFinder([None] * 10, sleep_mock=sleep_calls.append)

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=2,
            retry_interval_s=0.01,
            sleep=sleep_calls.append,
        )

        with pytest.raises(WindowNotFoundError) as exc:
            w.wait_for_window()

        msg = str(exc.value).lower()
        assert any(word in msg for word in ("window", "not found", "attempt"))


class TestWindowRecoveryWatchdogBackoff:
    def test_sleep_called_with_retry_interval(self):
        """Sleep called with ``retry_interval_s`` — constant when multiplier is 1.0."""
        sleep_calls = []
        finder = FakeFinder([None, None, FakeWindowInfo()], sleep_mock=sleep_calls.append)

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=10,
            retry_interval_s=2.5,
            backoff_multiplier=1.0,  # constant retry, no growth
            sleep=sleep_calls.append,
        )
        w.wait_for_window()

        assert all(d == 2.5 for d in sleep_calls)

    def test_backoff_grows_exponentially(self):
        sleep_calls = []
        finder = FakeFinder([None] * 10, sleep_mock=sleep_calls.append)

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=5,
            retry_interval_s=1.0,
            backoff_multiplier=2.0,
            max_backoff_s=10.0,
            sleep=sleep_calls.append,
        )
        with pytest.raises(WindowNotFoundError):
            w.wait_for_window()

        # 4 retries → 4 sleeps: 1.0, 2.0, 4.0, 8.0
        assert sleep_calls == [1.0, 2.0, 4.0, 8.0]

    def test_backoff_capped_at_max_backoff_s(self):
        sleep_calls = []
        finder = FakeFinder([None] * 10, sleep_mock=sleep_calls.append)

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=6,
            retry_interval_s=1.0,
            backoff_multiplier=2.0,
            max_backoff_s=4.0,
            sleep=sleep_calls.append,
        )
        with pytest.raises(WindowNotFoundError):
            w.wait_for_window()

        # sleeps: 1.0, 2.0, 4.0 (cap), 4.0, 4.0
        assert all(d <= 4.0 for d in sleep_calls)
        assert sleep_calls[0] == 1.0
        assert sleep_calls[-1] == 4.0


class TestWindowRecoveryWatchdogRetryInterval:
    def test_retry_interval_s_default(self):
        w = WindowRecoveryWatchdog(finder=lambda: None)
        assert w.retry_interval_s == 2.0

    def test_max_attempts_default(self):
        w = WindowRecoveryWatchdog(finder=lambda: None)
        assert w.max_attempts == 30

    def test_negative_max_attempts_raises(self):
        with pytest.raises(ValueError):
            WindowRecoveryWatchdog(finder=lambda: None, max_attempts=0)


class TestWindowRecoveryWatchdogCallbacks:
    def test_on_retry_callback_invoked(self):
        """Hook called on every failed attempt, including the last one before the exception."""
        attempts_seen = []

        def finder():
            attempts_seen.append("find")
            return None

        def on_retry(attempt: int, max_attempts: int, next_sleep_s: float) -> None:
            attempts_seen.append(("retry", attempt, next_sleep_s))

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=3,
            retry_interval_s=0.01,
            on_retry=on_retry,
            sleep=lambda _: None,
        )
        with pytest.raises(WindowNotFoundError):
            w.wait_for_window()

        retry_events = [e for e in attempts_seen if isinstance(e, tuple)]
        assert len(retry_events) == 3

    def test_on_retry_attempt_numbers_correct(self):
        seen_attempts = []

        w = WindowRecoveryWatchdog(
            finder=lambda: None,
            max_attempts=4,
            retry_interval_s=0.01,
            on_retry=lambda att, mx, sl: seen_attempts.append(att),
            sleep=lambda _: None,
        )
        with pytest.raises(WindowNotFoundError):
            w.wait_for_window()

        assert seen_attempts == [1, 2, 3, 4]


class TestWindowRecoveryWatchdogIsRecovering:
    def test_is_recovering_false_initially(self):
        w = WindowRecoveryWatchdog(finder=lambda: FakeWindowInfo())
        assert w.is_recovering is False

    def test_is_recovering_true_during_wait(self):
        """The flag is set while ``wait_for_window`` is running."""
        flag_during_wait = []

        def finder():
            flag_during_wait.append(w.is_recovering)
            return FakeWindowInfo()

        w = WindowRecoveryWatchdog(
            finder=finder,
            max_attempts=3,
            retry_interval_s=0.01,
            sleep=lambda _: None,
        )
        w.wait_for_window()

        assert any(flag_during_wait)

    def test_is_recovering_reset_after_success(self):
        w = WindowRecoveryWatchdog(finder=lambda: FakeWindowInfo())
        w.wait_for_window()
        assert w.is_recovering is False

    def test_is_recovering_reset_after_failure(self):
        w = WindowRecoveryWatchdog(finder=lambda: None, max_attempts=2, retry_interval_s=0.01)
        with pytest.raises(WindowNotFoundError):
            w.wait_for_window()
        assert w.is_recovering is False


class TestWindowRecoveryWatchdogInheritFromFinder:
    def test_accepts_find_game_window_like_callable(self):
        """Accepts a callable with the same signature as find_game_window."""
        captured_args = {}

        def finder_like(process_name="LastZ", title_substring=None):
            captured_args["pn"] = process_name
            captured_args["ts"] = title_substring
            return FakeWindowInfo()

        w = WindowRecoveryWatchdog(finder=finder_like)
        w.wait_for_window(process_name="LastZ", title_substring="Game")
        assert captured_args == {"pn": "LastZ", "ts": "Game"}