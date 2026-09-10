"""Smoke tests for GUI module imports (no viewport creation)."""


def test_gui_modules_importable() -> None:
    from mvp.gui import log_handler, main_window, state  # noqa: F401

    assert main_window.MainWindow is not None
    assert state.GuiState is not None
    assert log_handler.GuiLogHandler is not None


def test_gui_state_push_log() -> None:
    from mvp.gui.state import GuiState

    state = GuiState()
    state.push_log("hello")
    assert state.log_queue.get() == "hello"


def test_bgr_to_rgba_texture_buffer_reuse() -> None:
    import numpy as np
    from mvp.gui.main_window import bgr_to_rgba_texture

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :] = (255, 128, 64)  # BGR

    out_float = np.empty((100, 100, 4), dtype=np.float32)
    u8_buf = np.empty((100, 100, 4), dtype=np.uint8)

    res = bgr_to_rgba_texture(frame, out=out_float, u8_out=u8_buf)

    assert res is out_float
    # Check RGBA conversion
    assert u8_buf[0, 0, 0] == 64   # R
    assert u8_buf[0, 0, 1] == 128  # G
    assert u8_buf[0, 0, 2] == 255  # B
    assert u8_buf[0, 0, 3] == 255  # A

    np.testing.assert_allclose(res[0, 0, 0], 64 / 255.0, atol=1e-4)
    np.testing.assert_allclose(res[0, 0, 2], 1.0, atol=1e-4)


def _make_main_window(monkeypatch):
    from mvp.config import MVPConfig
    from mvp.gui.main_window import MainWindow
    from mvp.gui.state import GuiState

    config = MVPConfig.default()
    config.log_to_file = False
    state = GuiState()
    win = MainWindow(config, state)
    monkeypatch.setattr(win, "_event_logger", _DummyEventLogger())
    return win, state


class _DummyEventLogger:
    def __init__(self):
        self._buffer = []

    def log(self, event, data):
        pass


def test_log_history_respects_500_cap(monkeypatch) -> None:
    """log_history deque must stay capped at 500 entries (AGENTS.md §13)."""
    import mvp.gui.main_window as mw_mod

    win, state = _make_main_window(monkeypatch)
    monkeypatch.setattr(mw_mod.dpg, "set_value", lambda tag, val: None)

    for i in range(600):
        state.push_log(f"line {i}")

    # Drain everything in one pass.
    win._update_logs()

    # The deque must be capped at 500 entries, keeping the NEWEST 500 messages
    # (drop-oldest on overflow) so recent logs are never lost.
    assert len(win._log_history) == 500
    assert win._log_history[-1] == "line 599"
    assert win._log_history[0] == "line 100"


def test_update_logs_incremental_not_full_join(monkeypatch) -> None:
    """_update_logs must append new log lines incrementally and only call
    dpg.set_value when there are new entries AND >=250ms elapsed since last update."""
    import time

    import mvp.gui.main_window as mw_mod

    win, state = _make_main_window(monkeypatch)

    dpg_calls = []

    monkeypatch.setattr(
        mw_mod.dpg, "set_value", lambda tag, val: dpg_calls.append((tag, val))
    )

    now = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: now["t"])

    # First batch: two new logs.
    state.push_log("a")
    state.push_log("b")
    win._update_logs()
    # 250ms not yet elapsed since first call, but _last_log_update starts at 0,
    # so the first flush happens immediately (1000 - 0 >= 0.25).
    assert len(dpg_calls) == 1
    assert win._log_text == "a\nb\n"

    # Second batch within throttle window: set_value must NOT be called again.
    state.push_log("c")
    now["t"] += 0.1
    win._update_logs()
    assert len(dpg_calls) == 1, "set_value must be throttled to 4 Hz"

    # After the throttle window: set_value called once with the accumulated text.
    now["t"] += 0.2
    win._update_logs()
    assert len(dpg_calls) == 2
    assert dpg_calls[-1][1] == "a\nb\nc\n"

    # No new log lines: set_value must not be called.
    now["t"] += 0.3
    win._update_logs()
    assert len(dpg_calls) == 2
