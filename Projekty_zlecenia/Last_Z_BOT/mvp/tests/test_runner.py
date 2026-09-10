"""Tests for the MVP bot runner."""

import queue

from mvp.bot.runner import BotRunner, FrameProducer
from mvp.config import MVPConfig


class _DummyCapture:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def grab(self):
        return None

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_bot_runner_start_without_backend_raises(monkeypatch) -> None:
    runner = BotRunner(MVPConfig.default())
    monkeypatch.setattr(runner.clicker, "initialize", lambda: None)
    monkeypatch.setattr(runner, "_wait_for_window_on_start", lambda: None)
    try:
        runner.start()
    except RuntimeError as exc:
        assert "SendInput backend is not available" in str(exc)
    else:
        raise AssertionError("RuntimeError not raised")


def test_frame_producer_constructs() -> None:
    capture = _DummyCapture()
    frame_queue = queue.Queue(maxsize=2)
    producer = FrameProducer(capture, frame_queue, target_fps=30)
    assert producer._target_fps == 30
    assert producer._thread is None


def test_runner_initializes_clicker_and_timing() -> None:
    cfg = MVPConfig.default()
    cfg.click_jitter_ms = 1.2
    runner = BotRunner(cfg)
    assert runner.clicker.click_jitter_ms == 1.2
    assert runner.clicker._backend_mode == "sendinput"


def test_apply_config_propagates_process_name() -> None:
    cfg = MVPConfig.default()
    runner = BotRunner(cfg)

    cfg.process_name = "OtherGame.exe"

    runner.apply_config()

    assert runner.clicker.process_name == "OtherGame.exe"


def test_runner_steps_disabled_in_production() -> None:
    """By default (debug_macro_log=False) the MacroStepLogger must be disabled."""
    cfg = MVPConfig.default()
    assert cfg.debug_macro_log is False
    runner = BotRunner(cfg)
    assert runner._step_logger.enabled is False


def test_runner_shutdown_closes_step_logger(monkeypatch) -> None:
    """BotRunner.shutdown() must close the step logger if it has a close() method."""
    cfg = MVPConfig.default()
    runner = BotRunner(cfg)
    closed = {"n": 0}
    monkeypatch.setattr(runner._step_logger, "close", lambda: closed.__setitem__("n", 1))
    monkeypatch.setattr(runner.capture, "stop", lambda: None)
    monkeypatch.setattr(runner.clicker, "shutdown", lambda: None)
    monkeypatch.setattr(runner.sleep_guard, "shutdown", lambda: None)
    monkeypatch.setattr(runner.anti_detect, "stop", lambda: None)
    runner.shutdown()
    assert closed["n"] == 1


def test_ocr_prewarm_initializes_both_readers_in_background() -> None:
    cfg = MVPConfig.default()
    runner = BotRunner(cfg)
    calls = {"chat": 0, "timer": 0}
    runner.chat_ocr.initialize = lambda: calls.__setitem__("chat", calls["chat"] + 1)
    runner.timer_ocr.initialize = lambda: calls.__setitem__("timer", calls["timer"] + 1)

    thread = runner._start_ocr_prewarm()
    assert thread is not None
    thread.join(timeout=5)
    assert calls == {"chat": 1, "timer": 1}

    # Idempotent per instance: second call must not spawn another prewarm.
    assert runner._start_ocr_prewarm() is None
    assert calls == {"chat": 1, "timer": 1}


def test_apply_config_rebuilds_listen_step_reference() -> None:
    """apply_config rebuilds self.macro — _listen_step must be re-pointed at
    the NEW steps[0], otherwise pre/post-run dispatch keeps using stale step
    values (e.g. arrow_threshold changed in the GUI would never take effect)."""
    cfg = MVPConfig.default()
    runner = BotRunner(cfg)
    old_step = runner._listen_step

    cfg.chat_arrow_threshold = 0.95
    runner.apply_config()

    assert runner._listen_step is not old_step
    assert runner._listen_step is runner.macro.steps[0]
    assert runner._listen_step.arrow_threshold == 0.95


class _StubMacroResult:
    """Minimal stub for MacroResult with ``success`` and ``error`` attributes."""

    def __init__(self, success: bool = True, error: str | None = None) -> None:
        self.success = success
        self.error = error


def _make_runner_with_stubbed_window(monkeypatch, *, window_seq, macro_results, max_iterations=20):
    """Build a BotRunner with ``find_game_window`` and ``macro_engine.run`` stubbed."""
    from mvp.bot import runner as runner_mod

    runner = BotRunner(MVPConfig.default())

    def fake_find_window(name: str = "Survival.exe"):
        if not window_seq:
            runner._stop_event.set()
            return None
        val = window_seq.pop(0) if isinstance(window_seq, list) else next(window_seq)
        return val

    monkeypatch.setattr(runner_mod, "find_game_window", fake_find_window)

    call_idx = {"i": 0}
    call_counter = [0]

    def fake_run(macro, window):
        i = call_idx["i"]
        call_idx["i"] += 1
        call_counter[0] += 1
        if call_counter[0] >= max_iterations:
            runner._stop_event.set()
            return _StubMacroResult(success=True, error=None)
        item = macro_results[i % len(macro_results)]
        if isinstance(item, BaseException):
            raise item
        return _StubMacroResult(success=item[0], error=item[1])

    monkeypatch.setattr(runner.macro_engine, "run", fake_run)
    monkeypatch.setattr(runner.macro_engine, "reset", lambda: None)
    monkeypatch.setattr(runner_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(
        runner._stop_event, "wait", lambda timeout=None: runner._stop_event.is_set()
    )
    dispatch_calls = []

    def fake_dispatch(step_num, step, window):
        dispatch_calls.append((step_num, step.type))

    monkeypatch.setattr(runner.macro_engine, "dispatch_step", fake_dispatch)
    runner._dispatch_calls = dispatch_calls  # type: ignore[attr-defined]
    return runner, call_counter


def test_main_loop_returns_cleanly_after_macro_engine_exception(monkeypatch):
    """A single exception from macro_engine.run does NOT kill the thread — the loop continues."""
    from mvp.bot.window_finder import WindowInfo

    info = WindowInfo(
        hwnd=42,
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        title="Survival",
        title_bar_height=31,
    )
    macro_results = [
        RuntimeError("OCR thread crashed"),
        (True, None),
        (True, None),
    ]
    runner, call_counter = _make_runner_with_stubbed_window(
        monkeypatch,
        window_seq=[info] * 10,
        macro_results=macro_results,
    )

    runner._main_loop()


def test_main_loop_retries_three_transient_exceptions(monkeypatch, caplog):
    """Three consecutive exceptions: the loop should make 4 calls (3 retries + 1 success)."""
    import logging

    from mvp.bot.window_finder import WindowInfo

    info = WindowInfo(
        hwnd=42,
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        title="Survival",
        title_bar_height=31,
    )
    macro_results = [
        ConnectionError("network connection lost"),
        RuntimeError("dig engine boom"),
        OSError("DXGI access lost"),
        (True, None),  # success
    ]
    runner, call_counter = _make_runner_with_stubbed_window(
        monkeypatch,
        window_seq=[info] * 10,
        macro_results=macro_results,
        max_iterations=4,
    )

    with caplog.at_level(logging.WARNING, logger="mvp.bot.runner"):
        runner._main_loop()

    warns = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warns) >= 3, [r.message for r in caplog.records]
    assert call_counter[0] == 4, call_counter[0]


def test_main_loop_logs_fatal_after_max_retries(monkeypatch, caplog):
    """After ``max_retries`` consecutive exceptions the loop stops and logs ERROR."""
    import logging

    from mvp.bot.window_finder import WindowInfo

    info = WindowInfo(
        hwnd=42,
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        title="Survival",
        title_bar_height=31,
    )
    macro_results = [RuntimeError("persistent failure")] * 21
    runner, call_counter = _make_runner_with_stubbed_window(
        monkeypatch,
        window_seq=[info] * 25,
        macro_results=macro_results,
        max_iterations=30,
    )

    with caplog.at_level(logging.ERROR, logger="mvp.bot.runner"):
        runner._main_loop()

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) >= 1, [r.message for r in errors]


def test_main_loop_no_window_is_logged_and_retried(monkeypatch, caplog):
    """Brak okna gry: WARNING + sleep + retry — pętla NIE wychodzi."""
    import logging

    runner, call_counter = _make_runner_with_stubbed_window(
        monkeypatch,
        window_seq=[None] * 5,
        macro_results=[(True, None)],
    )

    with caplog.at_level(logging.WARNING, logger="mvp.bot.runner"):
        runner._main_loop()

    warns = [r for r in caplog.records if "Game window not found" in r.message]
    assert len(warns) >= 2


def test_main_loop_retry_counter_resets_after_success(monkeypatch, caplog):
    """After a successful macro the retry counter resets — the next exception counts from zero."""
    import logging

    from mvp.bot.window_finder import WindowInfo

    info = WindowInfo(
        hwnd=42,
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        title="Survival",
        title_bar_height=31,
    )
    macro_results = [
        RuntimeError("e1"),
        RuntimeError("e2"),
        (True, None),
        RuntimeError("e3"),
        RuntimeError("e4"),
        (True, None),
    ]
    runner, call_counter = _make_runner_with_stubbed_window(
        monkeypatch,
        window_seq=[info] * 25,
        macro_results=macro_results,
        max_iterations=6,
    )

    with caplog.at_level(logging.ERROR, logger="mvp.bot.runner"):
        runner._main_loop()

    errors = [
        r for r in caplog.records if r.levelno >= logging.ERROR and r.name == "mvp.bot.runner"
    ]
    assert len(errors) == 0, [r.message for r in errors]


def test_main_loop_runs_macro_cleanly_without_external_dispatch(monkeypatch) -> None:
    """The macro execution is fully self-contained in macro_engine.run without external dispatch."""
    from mvp.bot.window_finder import WindowInfo

    info = WindowInfo(
        hwnd=42,
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        title="Survival",
        title_bar_height=31,
    )
    runner, call_counter = _make_runner_with_stubbed_window(
        monkeypatch,
        window_seq=[info] * 10,
        macro_results=[(True, None)],
        max_iterations=2,
    )

    call_log = []

    def fake_dispatch(step_num, step, window):
        call_log.append(("dispatch", step_num, step.type))

    iter_count = {"i": 0}

    def run_and_maybe_stop(macro, window):
        iter_count["i"] += 1
        call_log.append(("run",))
        if iter_count["i"] >= 2:
            runner._stop_event.set()
        return _StubMacroResult(success=True, error=None)

    monkeypatch.setattr(runner.macro_engine, "dispatch_step", fake_dispatch)
    monkeypatch.setattr(runner.macro_engine, "run", run_and_maybe_stop)

    runner._main_loop()

    run_indices = [i for i, e in enumerate(call_log) if e[0] == "run"]
    assert len(run_indices) == 2
    dispatch_events = [e for e in call_log if e[0] == "dispatch"]
    assert len(dispatch_events) == 0, f"Expected 0 external dispatches, got {len(dispatch_events)}"


def test_bot_runner_stop_joins_thread(monkeypatch) -> None:
    runner = BotRunner(MVPConfig.default())
    monkeypatch.setattr(runner.clicker, "initialize", lambda: None)
    monkeypatch.setattr(runner.clicker, "_backend", type("B", (), {"name": "mock", "is_initialized": True})())
    monkeypatch.setattr(runner, "_wait_for_window_on_start", lambda: None)
    monkeypatch.setattr(runner.capture, "start", lambda: None)
    monkeypatch.setattr(runner.capture, "stop", lambda: None)

    def fake_loop():
        while not runner._stop_event.wait(0.01):
            pass

    monkeypatch.setattr(runner, "_main_loop", fake_loop)

    runner.start()
    assert runner.is_running is True
    runner.stop(timeout=1.0)
    assert runner.is_running is False
    assert runner._thread is None or not runner._thread.is_alive()


def test_start_raises_on_uipi_mismatch(monkeypatch) -> None:
    import pytest

    runner = BotRunner(MVPConfig.default())
    monkeypatch.setattr(runner.clicker, "initialize", lambda: None)
    monkeypatch.setattr(
        runner.clicker,
        "_backend",
        type("B", (), {"name": "sendinput", "is_initialized": True})(),
    )
    monkeypatch.setattr(runner, "_wait_for_window_on_start", lambda: None)
    monkeypatch.setattr(runner.capture, "start", lambda: None)
    monkeypatch.setattr(runner, "_apply_anti_sleep", lambda: None)
    monkeypatch.setattr(runner, "_main_loop", lambda: None)
    monkeypatch.setattr(
        "mvp.bot.window_finder.check_uipi_elevation_mismatch", lambda _: True
    )

    with pytest.raises(RuntimeError, match="UIPI"):
        runner.start()


def test_bot_runner_rapid_stop_start(monkeypatch) -> None:
    runner = BotRunner(MVPConfig.default())
    monkeypatch.setattr(runner.clicker, "initialize", lambda: None)
    monkeypatch.setattr(runner.clicker, "_backend", type("B", (), {"name": "mock", "is_initialized": True})())
    monkeypatch.setattr(runner, "_wait_for_window_on_start", lambda: None)
    monkeypatch.setattr(runner.capture, "start", lambda: None)
    monkeypatch.setattr(runner.capture, "stop", lambda: None)

    def fake_loop():
        while not runner._stop_event.wait(0.01):
            pass

    monkeypatch.setattr(runner, "_main_loop", fake_loop)

    runner.start()
    assert runner.is_running is True
    runner.stop(timeout=1.0)
    assert runner.is_running is False

    # Immediate start must succeed cleanly
    runner.start()
    assert runner.is_running is True
    runner.stop(timeout=1.0)
    assert runner.is_running is False