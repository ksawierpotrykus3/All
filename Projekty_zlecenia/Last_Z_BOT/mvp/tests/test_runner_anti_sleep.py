"""L1: BotRunner must enable SleepGuard on start() and disable on stop()/shutdown().

Verifies the integration between BotRunner lifecycle and the keep-awake
helper so users running hour-long sessions do not lose the game window to a
display-off timer or sleep transition.
"""

from __future__ import annotations

from mvp.bot.runner import BotRunner
from mvp.config import MVPConfig


class _RecordingSleepGuard:
    """Drop-in fake for SleepGuard that records every call."""

    def __init__(self) -> None:
        self.enables: list[dict] = []
        self.disables: int = 0
        self.shutdowns: int = 0

    def enable(self, display: bool = True, system: bool = True, away_mode: bool = False) -> None:
        self.enables.append({"display": display, "system": system, "away_mode": away_mode})

    def disable(self) -> None:
        self.disables += 1

    def shutdown(self) -> None:
        self.shutdowns += 1


def _patch_sleep_guard(monkeypatch, guard: _RecordingSleepGuard) -> None:
    """Patch BotRunner so it uses ``guard`` instead of the real SleepGuard."""
    from mvp.bot import runner as runner_mod

    monkeypatch.setattr(runner_mod, "SleepGuard", lambda: guard)


def test_botrunner_creates_sleep_guard(monkeypatch) -> None:
    guard = _RecordingSleepGuard()
    _patch_sleep_guard(monkeypatch, guard)

    runner = BotRunner(MVPConfig.default(), frame_queue=None)

    assert runner.sleep_guard is guard


def test_botrunner_enable_calls_sleep_guard(monkeypatch) -> None:
    """A normal start() must request keep-awake with the configured flags."""
    guard = _RecordingSleepGuard()
    _patch_sleep_guard(monkeypatch, guard)

    cfg = MVPConfig.default()
    cfg.prevent_sleep = True
    cfg.prevent_display_off = True
    cfg.anti_sleep_away_mode = False
    runner = BotRunner(cfg, frame_queue=None)

    # We don't actually start the bot thread — just exercise the sleep guard
    # enable path. Simulate by calling the lifecycle method directly.
    runner._apply_anti_sleep()

    assert guard.enables == [{"display": True, "system": True, "away_mode": False}]


def test_botrunner_disable_when_prevent_sleep_false(monkeypatch) -> None:
    """If both flags are off, the guard must be told to disable (idempotent)."""
    guard = _RecordingSleepGuard()
    _patch_sleep_guard(monkeypatch, guard)

    cfg = MVPConfig.default()
    cfg.prevent_sleep = False
    cfg.prevent_display_off = False
    runner = BotRunner(cfg, frame_queue=None)

    runner._apply_anti_sleep()

    # First call always disables (clear previous state, if any).
    assert guard.disables == 1


def test_botrunner_away_mode_propagated(monkeypatch) -> None:
    guard = _RecordingSleepGuard()
    _patch_sleep_guard(monkeypatch, guard)

    cfg = MVPConfig.default()
    cfg.prevent_sleep = True
    cfg.prevent_display_off = False
    cfg.anti_sleep_away_mode = True
    runner = BotRunner(cfg, frame_queue=None)

    runner._apply_anti_sleep()

    assert guard.enables == [{"display": False, "system": True, "away_mode": True}]


def test_botrunner_shutdown_clears_sleep_guard(monkeypatch) -> None:
    """The shutdown path must release the keep-awake request even on a clean exit."""
    guard = _RecordingSleepGuard()
    _patch_sleep_guard(monkeypatch, guard)

    runner = BotRunner(MVPConfig.default(), frame_queue=None)
    runner._apply_anti_sleep()  # simulate start

    # Wipe enable count so we can isolate the shutdown call.
    guard.enables.clear()
    runner.shutdown()

    # BotRunner.shutdown() delegates to SleepGuard.shutdown() — in the real
    # implementation this calls disable() internally. We assert the call was
    # made so the OS state is restored on exit.
    assert guard.shutdowns >= 1
