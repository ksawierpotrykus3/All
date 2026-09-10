"""Tests for #14 — Verbose mode (DEBUG/INFO/WARNING).

Architecture:
- ``VerboseController`` — class controlling the runtime logging level.
- ``set_level("DEBUG" / "INFO" / "WARNING")`` — changes the global level.
- ``enable_file_output(path)`` / ``disable_file_output()`` — file handler.
- ``get_current_level()`` — returns the active level (for GUI status).
- ``enable_console()`` / ``disable_console()`` — logs to stderr.

Test strategy:
- FakeLogger passed as ``root_logger=`` via the constructor —
  do NOT monkeypatch ``logging.root`` (breaks pytest internals).
"""

from __future__ import annotations

import logging

import pytest

from mvp.bot.verbose import (
    ValidLevels,
    VerboseController,
    VerboseError,
)


class FakeLogger:
    """Stub ``logging.Logger`` recording calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self._level = logging.WARNING
        self.handlers: list = []

    def setLevel(self, level) -> None:
        self.calls.append(("setLevel", (level,)))
        if isinstance(level, str):
            level = logging.getLevelName(level.upper())
        self._level = level

    def getEffectiveLevel(self) -> int:
        return self._level

    def addHandler(self, handler) -> None:
        self.calls.append(("addHandler", (handler,)))
        self.handlers.append(handler)

    def removeHandler(self, handler) -> None:
        self.calls.append(("removeHandler", (handler,)))
        if handler in self.handlers:
            self.handlers.remove(handler)

    def debug(self, *a, **kw):
        self.calls.append(("debug", a))

    def info(self, *a, **kw):
        self.calls.append(("info", a))

    def warning(self, *a, **kw):
        self.calls.append(("warning", a))


class TestVerboseControllerBasics:
    def test_default_level_is_info(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        assert vc.get_current_level() == "INFO"

    def test_set_level_debug(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("DEBUG")
        assert ("setLevel", (logging.DEBUG,)) in fake.calls
        assert vc.get_current_level() == "DEBUG"

    def test_set_level_info(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("INFO")
        assert ("setLevel", (logging.INFO,)) in fake.calls

    def test_set_level_warning(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("WARNING")
        assert ("setLevel", (logging.WARNING,)) in fake.calls

    def test_get_current_level_returns_set_value(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("DEBUG")
        assert vc.get_current_level() == "DEBUG"

    def test_invalid_level_raises(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        with pytest.raises(VerboseError):
            vc.set_level("UNKNOWN")

    def test_case_insensitive_level(self):
        """Level names are normalized to uppercase."""
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("debug")
        assert vc.get_current_level() == "DEBUG"


class TestVerboseControllerFileOutput:
    def test_enable_file_output_creates_handler(self, tmp_path):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        log_path = tmp_path / "test.log"
        vc.enable_file_output(str(log_path))
        assert any(isinstance(h, logging.FileHandler) for h in fake.handlers)

    def test_disable_file_output_removes_handler(self, tmp_path):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        log_path = tmp_path / "test.log"
        vc.enable_file_output(str(log_path))
        assert any(isinstance(h, logging.FileHandler) for h in fake.handlers)

        vc.disable_file_output()
        assert not any(isinstance(h, logging.FileHandler) for h in fake.handlers)

    def test_enable_file_output_creates_parent_dirs(self, tmp_path):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        log_path = tmp_path / "subdir" / "nested" / "test.log"
        vc.enable_file_output(str(log_path))
        assert log_path.parent.exists()

    def test_double_enable_file_output_replaces(self, tmp_path):
        """A second call replaces the previous handler rather than stacking."""
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.enable_file_output(str(tmp_path / "first.log"))
        vc.enable_file_output(str(tmp_path / "second.log"))
        file_handlers = [h for h in fake.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1


class TestVerboseControllerConsoleOutput:
    def test_console_disabled_when_requested(self):
        fake = FakeLogger()
        VerboseController(root_logger=fake, disable_console=True)
        stream_handlers = [h for h in fake.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 0

    def test_console_enabled_by_default(self):
        fake = FakeLogger()
        VerboseController(root_logger=fake)
        stream_handlers = [h for h in fake.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1

    def test_disable_console_removes_streamhandler(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake)
        vc.disable_console()
        stream_handlers = [h for h in fake.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 0

    def test_enable_console_adds_streamhandler(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.enable_console()
        stream_handlers = [h for h in fake.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1


class TestVerboseControllerValidLevels:
    def test_valid_levels_defined(self):
        assert hasattr(ValidLevels, "DEBUG")
        assert hasattr(ValidLevels, "INFO")
        assert hasattr(ValidLevels, "WARNING")

    def test_valid_levels_values(self):
        assert ValidLevels.DEBUG == "DEBUG"
        assert ValidLevels.INFO == "INFO"
        assert ValidLevels.WARNING == "WARNING"


class TestVerboseControllerReset:
    def test_reset_to_defaults(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("DEBUG")
        vc.reset()
        assert vc.get_current_level() == "INFO"


class TestVerboseControllerSnapshot:
    def test_save_restore_level(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("DEBUG")
        vc.save_level()
        vc.set_level("WARNING")
        vc.restore_level()
        assert vc.get_current_level() == "DEBUG"

    def test_restore_without_save_is_noop(self):
        """Restoring without a prior save leaves the current level untouched."""
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("DEBUG")
        vc.restore_level()
        assert vc.get_current_level() == "DEBUG"


class TestVerboseControllerIdempotence:
    def test_set_level_same_value_twice_safe(self):
        fake = FakeLogger()
        vc = VerboseController(root_logger=fake, disable_console=True)
        vc.set_level("INFO")
        vc.set_level("INFO")


class TestVerboseError:
    def test_verbose_error_is_exception(self):
        assert issubclass(VerboseError, Exception)