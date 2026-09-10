"""Tests for GUI integration with the modules.

Tests the integration points in MainWindow:
- #22: SplashController shown in setup()
- #24: CrashHandler installed at startup
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from mvp.config import MVPConfig
from mvp.gui.main_window import MainWindow
from mvp.gui.state import GuiState


class FakeBotRunner:
    """Minimal BotRunner stub for GUI tests."""

    def __init__(self, config: MVPConfig) -> None:
        self.config = config
        self.macro_engine = MagicMock()
        self.macro_engine.total_steps = 5
        self.macro_engine.current_step_index = 0
        self.macro_engine.last_timer_value = 120
        self.macro_engine.stats_start_time = 0.0
        self.macro_engine.stats_end_time = None
        self.macro_engine.step_callback = None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def apply_config(self) -> None:
        pass

    def set_preview_scale(self, scale: float) -> None:
        pass

    def set_preview_enabled(self, enabled: bool) -> None:
        pass

    def start_frame_producer(self) -> None:
        pass

    def stop_frame_producer(self) -> None:
        pass

    @property
    def is_running(self) -> bool:
        return False

    @property
    def latest_window_info(self):
        return None


class FakeWindowInfo:
    """Stub WindowInfo."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.width = width
        self.height = height


def _gui_patches() -> contextlib.ExitStack:
    """Patches native DPG calls + heavy MainWindow methods.

    ``setup()`` touches native DearPyGui (create_context,
    get_viewport_width…) and starts global hotkeys (WinAPI threads).
    Without these patches the test dies from an access violation. ExitStack
    reverses everything after exiting ``with``.
    """
    stack = contextlib.ExitStack()

    # UI building and hotkeys are not needed in these tests.
    for method in (
        "_load_fonts",
        "_create_themes",
        "_register_textures",
        "_build_ui",
        "_populate_gui_from_config",
        "_register_hotkeys",
    ):
        stack.enter_context(patch.object(MainWindow, method))

    # Native DearPyGui functions used in setup()/set_game_status().
    for name in (
        "create_context",
        "create_viewport",
        "setup_dearpygui",
        "set_viewport_pos",
        "maximize_viewport",
        "set_value",
        "get_value",
        "configure_item",
        "set_exit_callback",
        "show_viewport",
        "destroy_context",
    ):
        stack.enter_context(patch(f"dearpygui.dearpygui.{name}"))
    stack.enter_context(patch("dearpygui.dearpygui.get_viewport_width", return_value=1920))
    stack.enter_context(patch("dearpygui.dearpygui.get_viewport_height", return_value=1080))
    stack.enter_context(patch("dearpygui.dearpygui.get_viewport_pos", return_value=(100, 100)))
    return stack


class _GuiTestBase:
    """Shared fixture state for MainWindow GUI integration tests."""

    def setup_method(self) -> None:
        self.config = MVPConfig.default()
        self.config.log_dir = "logs"
        self.config.log_to_file = False
        self.state = GuiState()
        self.bot_runner = FakeBotRunner(self.config)
        self.window_info = FakeWindowInfo()


class TestMainWindowGuiIntegration(_GuiTestBase):
    def test_viewport_saved_on_close(self) -> None:
        with (
            _gui_patches(),
            patch("mvp.gui.viewport_state.save_viewport_state") as mock_save,
        ):
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win.setup()
            win.shutdown()
            assert mock_save.called

    def test_crash_handler_installed(self) -> None:
        from mvp.bot.crash import CrashHandler

        with _gui_patches(), patch.object(CrashHandler, "install") as mock_install:
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win.setup()
            assert mock_install.called

    def test_crash_handler_uninstalled_on_close(self) -> None:
        from mvp.bot.crash import CrashHandler

        with (
            _gui_patches(),
            patch.object(CrashHandler, "install"),
            patch.object(CrashHandler, "uninstall") as mock_uninstall,
        ):
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win.setup()
            win._on_close()
            assert mock_uninstall.called

    def test_viewport_pos_restored_with_list(self) -> None:
        """dpg.set_viewport_pos must be called with a list [x, y], not two separate arguments."""
        with (
            _gui_patches(),
            patch("mvp.gui.viewport_state.load_viewport_state") as mock_load,
            patch("dearpygui.dearpygui.set_viewport_pos") as mock_set_pos,
        ):
            from mvp.gui.viewport_state import ViewportState

            mock_load.return_value = ViewportState(
                x=100, y=100, width=1280, height=720, maximized=False
            )
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win.setup()
            mock_set_pos.assert_called_once_with([100, 100])

    def test_game_status_and_resolution_separated(self) -> None:
        """The game window status ('Connected') and resolution are separated."""
        with _gui_patches(), patch("dearpygui.dearpygui.set_value") as mock_set_value:
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win.set_game_status(True, "1920x1080")
            mock_set_value.assert_any_call("game_status_text", "Connected")
            mock_set_value.assert_any_call("game_res_text", "1920x1080")


class _FakeStep:
    label = "spam"

    def __eq__(self, other):
        return isinstance(other, _FakeStep) and other.label == self.label

    def __hash__(self):
        return hash(self.label)


class TestUiQueueIntegration(_GuiTestBase):
    def test_step_event_pushes_to_ui_queue_not_direct_dpg(self) -> None:
        with (
            _gui_patches(),
            patch("dearpygui.dearpygui.set_value") as mock_set_value,
        ):
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win._event_logger = MagicMock()
            win._on_step_event("phase_transition", 0, _FakeStep(), phase="spam")

            # Callback must route through the UI queue, not DPG directly.
            assert not self.state.ui_queue.empty()
            item = self.state.ui_queue.get_nowait()
            assert item == ("phase_transition", (0, _FakeStep()), {"phase": "spam"})
            assert mock_set_value.call_count == 0


class TestCrashReporterIntegration:
    def test_crash_report_fields(self) -> None:
        from mvp.bot.crash import CrashReport

        r = CrashReport(
            timestamp="2025-01-15T12:00:00",
            app_version="1.0",
            platform="win32",
            exc_type="ValueError",
            exc_value="test",
            traceback="Traceback...",
            context={},
        )
        assert r.exc_type == "ValueError"
        d = r.to_dict()
        assert d["exc_type"] == "ValueError"

    def test_crash_handler_captures(self) -> None:
        from mvp.bot.crash import CrashHandler

        h = CrashHandler(app_version="1.0")
        try:
            raise ValueError("test error")
        except ValueError as e:
            r = h.capture_exception(e)
        assert r.exc_type == "ValueError"
        assert "test error" in r.exc_value


class TestFullGuiIntegration(_GuiTestBase):
    def test_full_setup_runs_without_errors(self) -> None:
        """A smoke test: setup() + shutdown() without exceptions."""
        with _gui_patches():
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
            win.setup()
            win.shutdown()


class TestLicenseGate:
    def setup_method(self) -> None:
        self.config = MVPConfig.default()
        self.config.backend_url = "http://localhost:8000"
        self.config.license_key = "LZ-TEST"
        self.state = GuiState()
        self.bot_runner = FakeBotRunner(self.config)
        self.window_info = FakeWindowInfo()

    def _make_window(self):
        with (
            _gui_patches(),
            patch.object(MainWindow, "_collect_config_from_gui"),
        ):
            win = MainWindow(self.config, self.state, self.bot_runner, self.window_info)
        return win

    def test_license_ok_true_when_valid(self, monkeypatch):
        monkeypatch.setattr("mvp.gui.main_window.check_license", lambda *a, **k: None)
        monkeypatch.setattr("mvp.gui.main_window.get_hwid", lambda: "hwid")
        win = self._make_window()
        with patch("dearpygui.dearpygui.set_value"), patch("dearpygui.dearpygui.configure_item"):
            assert win._license_ok() is True

    def test_license_ok_false_when_invalid(self, monkeypatch):
        from mvp.license import LicenseError

        def _reject(*a, **k):
            raise LicenseError("license expired")

        monkeypatch.setattr("mvp.gui.main_window.check_license", _reject)
        monkeypatch.setattr("mvp.gui.main_window.get_hwid", lambda: "hwid")
        win = self._make_window()
        with patch("dearpygui.dearpygui.set_value"), patch("dearpygui.dearpygui.configure_item"):
            assert win._license_ok() is False

    def test_on_activate_license_saves_on_success(self, monkeypatch):
        monkeypatch.setattr("mvp.gui.main_window.check_license", lambda *a, **k: None)
        monkeypatch.setattr("mvp.gui.main_window.get_hwid", lambda: "hwid")
        win = self._make_window()
        with (
            patch("dearpygui.dearpygui.set_value"),
            patch("dearpygui.dearpygui.configure_item"),
            patch.object(MainWindow, "_collect_config_from_gui"),
            patch.object(win.config, "save") as mock_save,
        ):
            win._on_activate_license()
            assert mock_save.called

    def test_license_ok_never_raises_when_dpg_fails(self, monkeypatch):
        monkeypatch.setattr("mvp.gui.main_window.check_license", lambda *a, **k: None)
        monkeypatch.setattr("mvp.gui.main_window.get_hwid", lambda: "hwid")
        win = self._make_window()
        with patch("dearpygui.dearpygui.set_value", side_effect=Exception("boom")):
            assert win._license_ok() is False

    def test_start_stop_picks_up_license_fields_from_gui(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            "mvp.gui.main_window.check_license",
            lambda u, k, h: seen.update(url=u, key=k) or None,
        )
        monkeypatch.setattr("mvp.gui.main_window.get_hwid", lambda: "hwid")

        def _fake_get_value(name):
            return {"backend_url": " http://new:8000 ", "license_key": " LZ-NEW "}.get(name, "")

        class _NoopThread:
            def __init__(self, *a, **k):
                pass

            def start(self):
                pass

        monkeypatch.setattr("threading.Thread", _NoopThread)
        win = self._make_window()
        with (
            _gui_patches(),
            patch("dearpygui.dearpygui.get_value", side_effect=_fake_get_value),
        ):
            win._on_start_stop()
        assert seen == {"url": "http://new:8000", "key": "LZ-NEW"}
        assert win.config.backend_url == "http://new:8000"
        assert win.config.license_key == "LZ-NEW"

    def test_update_frame_texture_throttles_fps(self, monkeypatch):
        import numpy as np

        win = self._make_window()
        win.config.preview_enabled = True
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        win.state.frame_queue.put(frame)

        dpg_set_values = []
        monkeypatch.setattr(
            "dearpygui.dearpygui.set_value",
            lambda tag, val: dpg_set_values.append((tag, val)),
        )

        import time

        curr_time = 1000.0
        monkeypatch.setattr(time, "monotonic", lambda: curr_time)

        # First update processes frame
        win._update_frame_texture()
        assert len(dpg_set_values) == 1

        # Rapid second call within 0.05s should be throttled
        win.state.frame_queue.put(frame)
        curr_time += 0.02
        win._update_frame_texture()
        assert len(dpg_set_values) == 1  # Not called again

        # Call after throttle window (>0.066s) should process next frame
        curr_time += 0.08
        win._update_frame_texture()
        assert len(dpg_set_values) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])