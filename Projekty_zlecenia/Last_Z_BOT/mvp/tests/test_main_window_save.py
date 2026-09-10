"""P1-6, P1-9: MainWindow GUI helpers — save config + global hotkey.

These tests pin down two critical GUI entry points:

- ``MainWindow._on_save_config`` (line ~765) — must write config.json
  under the user-selected path AND validate the config before writing.

- ``MainWindow._on_global_spam_hotkey`` (line ~696) — must invoke
  ``engine.trigger_spam`` and gracefully handle ``bot_runner is None``.

Uses the existing ``_gui_patches`` context manager pattern from
``test_main_window_integration.py`` to stub DearPyGui + heavy UI methods.

NOTE on sandbox: ``tmp_path`` and ``tmp_path_factory`` fail with
``PermissionError: [WinError 5]`` on this sandbox (see
``docs/testing/sandbox_permissions.md``). Tests use a workspace-local
``scratch_dir`` fixture instead.
"""

from __future__ import annotations

import contextlib
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mvp.config import MVPConfig
from mvp.gui.main_window import MainWindow
from mvp.gui.state import GuiState


class _FakeBotRunner:
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


class _FakeWindowInfo:
    """Stub WindowInfo."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.width = width
        self.height = height


def _gui_patches() -> contextlib.ExitStack:
    """Patch DearPyGui + heavy MainWindow methods (lifted from test_main_window_integration)."""
    stack = contextlib.ExitStack()
    for method in (
        "_load_fonts",
        "_create_themes",
        "_register_textures",
        "_build_ui",
        "_populate_gui_from_config",
        "_register_hotkeys",
        "_collect_config_from_gui",
    ):
        stack.enter_context(patch.object(MainWindow, method))
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


@pytest.fixture
def scratch_dir():
    """Workspace-local scratch dir (avoids the sandbox-wide ``tmp_path`` PermissionError).

    Creates ``.pytest_scratch/test_main_window_save`` under the workspace
    root and cleans it up afterwards.
    """
    root = Path(__file__).resolve().parent.parent.parent / ".pytest_scratch" / "test_main_window_save"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def window_setup():
    """Construct a MainWindow with all GUI building patched out.

    The patches remain ACTIVE for the lifetime of the test (the
    ``_gui_patches`` context manager is yielded, not entered/exited inside
    the fixture). Tests that need a ``bot_runner=None`` should use the
    ``window_setup_no_runner`` fixture instead.
    """
    config = MVPConfig.default()
    config.log_dir = "logs"
    config.log_to_file = False
    state = GuiState()
    bot_runner = _FakeBotRunner(config)
    window_info = _FakeWindowInfo()

    stack = _gui_patches()
    try:
        win = MainWindow(config, state, bot_runner, window_info)
        win.setup()
        yield win, config, bot_runner
    finally:
        stack.close()


@pytest.fixture
def window_setup_no_runner():
    """Same as ``window_setup`` but with ``bot_runner=None``."""
    config = MVPConfig.default()
    config.log_dir = "logs"
    config.log_to_file = False
    state = GuiState()
    window_info = _FakeWindowInfo()

    stack = _gui_patches()
    try:
        win = MainWindow(config, state, bot_runner=None, window_info=window_info)
        win.setup()
        yield win, config
    finally:
        stack.close()


# ────────────────────────────────────────────────────────────────────────
# _on_save_config tests (P1-6)
# ────────────────────────────────────────────────────────────────────────


def test_on_save_config_writes_to_user_path(window_setup, scratch_dir, monkeypatch) -> None:
    """P1-6: _on_save_config MUST write config.json to the user-selected path."""
    win, _config, _bot_runner = window_setup

    monkeypatch.chdir(scratch_dir)

    # The config is currently valid → saving MUST succeed.
    win._on_save_config()

    out = scratch_dir / "config.json"
    assert out.exists(), "config.json was not created"
    data = json.loads(out.read_text(encoding="utf-8"))
    # Spot-check: at least one field is present.
    assert "process_name" in data or "backend_url" in data


def test_on_save_config_creates_config_in_cwd(window_setup, scratch_dir, monkeypatch) -> None:
    """P1-6: verify the file lands in the current working directory."""
    win, _config, _bot = window_setup
    monkeypatch.chdir(scratch_dir)
    win._on_save_config()
    assert (scratch_dir / "config.json").exists()


def test_on_save_config_validates_before_writing(window_setup, scratch_dir, monkeypatch) -> None:
    """P1-9: if validation fails, the file MUST NOT be written."""
    win, config, _bot = window_setup
    monkeypatch.chdir(scratch_dir)

    # Make validation fail: spam_clicks_per_sec must be 1..38 per config.py.
    config.spam_clicks_per_sec = 999  # invalid
    win._on_save_config()

    out = scratch_dir / "config.json"
    assert not out.exists(), (
        "config.json MUST NOT be written when validation fails "
        "(AGENTS.md §P1-9: validate before write)"
    )


def test_on_save_config_validation_reports_error(window_setup, scratch_dir, monkeypatch) -> None:
    """P1-9: a validation error MUST be reported (via _set_config_status or dpg.set_value)."""
    win, config, _bot = window_setup
    monkeypatch.chdir(scratch_dir)
    config.spam_clicks_per_sec = 999  # invalid

    with patch.object(MainWindow, "_set_config_status") as mock_status:
        win._on_save_config()
        # Either _set_config_status was called OR dpg.set_value was called with "Error:".
        # The mocked _set_config_status should have been invoked.
        assert mock_status.called, (
            "validation failure must surface via _set_config_status"
        )


def test_on_save_config_negative_cps_rejected(window_setup, scratch_dir, monkeypatch) -> None:
    """P1-9: negative CPS MUST be rejected."""
    win, config, _bot = window_setup
    monkeypatch.chdir(scratch_dir)
    config.spam_clicks_per_sec = -5

    win._on_save_config()
    assert not (scratch_dir / "config.json").exists()


# ────────────────────────────────────────────────────────────────────────
# _on_global_spam_hotkey tests (P1-9)
# ────────────────────────────────────────────────────────────────────────


def test_on_global_spam_hotkey_invokes_engine_trigger_spam(window_setup) -> None:
    """P1-9: hotkey MUST invoke engine.trigger_spam."""
    win, _config, bot_runner = window_setup
    assert bot_runner.macro_engine.trigger_spam is not None

    win._on_global_spam_hotkey()
    bot_runner.macro_engine.trigger_spam.assert_called_once()


def test_on_global_spam_hotkey_no_engine_no_op(window_setup_no_runner) -> None:
    """P1-9: with bot_runner=None, the hotkey MUST be a no-op (no exception)."""
    win, _config = window_setup_no_runner
    # Should NOT raise AttributeError.
    win._on_global_spam_hotkey()


def test_on_global_spam_hotkey_engine_without_trigger_spam_no_op(window_setup) -> None:
    """P1-9: if the engine lacks ``trigger_spam``, MUST not raise."""
    win, _config, bot_runner = window_setup
    # Replace trigger_spam attribute entirely so hasattr() returns False.
    del bot_runner.macro_engine.trigger_spam

    # Must not raise.
    win._on_global_spam_hotkey()


# ────────────────────────────────────────────────────────────────────────
# Smoke / regression
# ────────────────────────────────────────────────────────────────────────


def test_main_window_setup_smoke() -> None:
    """A fresh MainWindow + setup() MUST NOT raise under patched DPG."""
    config = MVPConfig.default()
    config.log_dir = "logs"
    config.log_to_file = False
    state = GuiState()
    bot_runner = _FakeBotRunner(config)
    window_info = _FakeWindowInfo()

    with _gui_patches():
        win = MainWindow(config, state, bot_runner, window_info)
        win.setup()
        # Sanity: config attribute is preserved.
        assert win.config is config
        assert win.bot_runner is bot_runner


def test_save_status_after_success(window_setup, scratch_dir, monkeypatch) -> None:
    """Successful save MUST update the status to a positive colour."""
    win, _config, _bot = window_setup
    monkeypatch.chdir(scratch_dir)
    with patch.object(MainWindow, "_set_config_status") as mock_status:
        win._on_save_config()
        assert mock_status.called
        # The success message MUST mention 'Saved'.
        args = mock_status.call_args[0]
        assert "Saved" in args[0] or "saved" in args[0].lower()
