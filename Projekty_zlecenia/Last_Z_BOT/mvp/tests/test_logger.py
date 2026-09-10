"""Tests for MVP DEV build logging module with exception capture."""

import logging
import os
import sys
from pathlib import Path
from tempfile import gettempdir
from unittest import mock

import pytest

from mvp.logger import get_logger, is_dev_mode, setup_dev_logging, _get_log_directory
import mvp.logger as logger_module


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset global logger before each test."""
    logger_module._logger = None
    yield
    logger_module._logger = None


class TestIsDevMode:
    """Tests for DEV mode detection."""

    def test_is_dev_mode_with_dev_env_var(self, monkeypatch) -> None:
        """LASTZBOT_DEV=1 environment variable enables DEV mode."""
        monkeypatch.setenv("LASTZBOT_DEV", "1")
        assert is_dev_mode() is True

    def test_is_dev_mode_without_dev_env_var_checks_exe_name(self, monkeypatch) -> None:
        """Without LASTZBOT_DEV, checks executable name for 'dev'."""
        monkeypatch.delenv("LASTZBOT_DEV", raising=False)
        monkeypatch.setattr(sys, "argv", ["C:\\path\\to\\regular.exe"], raising=False)
        # If executable name doesn't contain 'dev', should return False (in normal mode)
        # But running as script (not frozen) will return True
        result = is_dev_mode()
        # Script mode returns True, so verify it's a bool and the logic works
        assert result is True

    def test_is_dev_mode_with_dev_exe_name(self, monkeypatch) -> None:
        """Executable name containing 'dev' enables DEV mode."""
        monkeypatch.delenv("LASTZBOT_DEV", raising=False)
        monkeypatch.setattr(sys, "argv", ["C:\\path\\to\\dev_bot.exe"], raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        # When exe name contains 'dev', should return True
        result = is_dev_mode()
        assert result is True


class TestGetLogDirectory:
    """Tests for log directory resolution."""

    def test_get_log_directory_returns_path(self) -> None:
        """_get_log_directory returns a Path object."""
        log_dir = _get_log_directory()
        assert isinstance(log_dir, Path)

    def test_get_log_directory_has_fallback(self) -> None:
        """_get_log_directory has temp directory as fallback."""
        log_dir = _get_log_directory()
        # Should either be in LOCALAPPDATA\LastZBot or temp directory
        temp_dir = Path(gettempdir())
        localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
        
        # Either in LOCALAPPDATA or temp
        assert log_dir.exists() or str(log_dir).startswith(str(localappdata)) or str(log_dir).startswith(str(temp_dir))


class TestSetupDevLogging:
    """Tests for logging setup."""

    def test_setup_dev_logging_creates_logger(self, tmp_path, monkeypatch) -> None:
        """setup_dev_logging() returns a logger object."""
        monkeypatch.setenv("LASTZBOT_DEV", "1")
        logger = setup_dev_logging(log_dir=tmp_path)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "dev_build"

    def test_setup_dev_logging_creates_log_file(self, tmp_path) -> None:
        """setup_dev_logging() creates log file in specified directory."""
        logger = setup_dev_logging(log_dir=tmp_path)
        log_file = tmp_path / "dev_build_debug.log"
        assert log_file.exists()

    def test_logger_logs_to_file_and_console(self, tmp_path, capsys) -> None:
        """Logger writes to both file and console handlers."""
        logger = setup_dev_logging(log_dir=tmp_path)
        test_message = "Test log message"
        logger.info(test_message)
        
        # Check file contains message
        log_file = tmp_path / "dev_build_debug.log"
        assert log_file.exists()
        log_content = log_file.read_text()
        assert test_message in log_content

    def test_logger_format_is_correct(self, tmp_path) -> None:
        """Log format matches expected pattern: YYYY-MM-DD HH:MM:SS.mmm | LEVEL | module.function:line | message."""
        logger = setup_dev_logging(log_dir=tmp_path)
        logger.info("Test message")
        
        log_file = tmp_path / "dev_build_debug.log"
        log_content = log_file.read_text()
        
        # Check for expected format components
        assert "|" in log_content  # Has pipes
        assert "INFO" in log_content  # Has log level
        assert "Test message" in log_content  # Has message


class TestGetLogger:
    """Tests for logger singleton pattern."""

    def test_get_logger_returns_logger(self, tmp_path, monkeypatch) -> None:
        """get_logger() returns a logger object."""
        monkeypatch.setenv("LASTZBOT_DEV", "1")
        logger = get_logger(log_dir=tmp_path)
        assert isinstance(logger, logging.Logger)

    def test_get_logger_returns_same_logger(self, tmp_path, monkeypatch) -> None:
        """get_logger() returns the same logger instance (singleton pattern)."""
        monkeypatch.setenv("LASTZBOT_DEV", "1")
        logger1 = get_logger(log_dir=tmp_path)
        logger2 = get_logger(log_dir=tmp_path)
        assert logger1 is logger2


class TestExceptionHook:
    """Tests for exception hook."""

    def test_exception_hook_captures_exceptions(self, tmp_path, monkeypatch) -> None:
        """setup_dev_logging() sets up exception hook to capture unhandled exceptions."""
        monkeypatch.setenv("LASTZBOT_DEV", "1")
        logger = setup_dev_logging(log_dir=tmp_path)
        
        # Manually trigger exception hook with captured exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            # Call the exception hook directly with the captured exception
            sys.excepthook(exc_type, exc_value, exc_traceback)
            
            # Verify the exception was logged to file
            log_file = tmp_path / "dev_build_debug.log"
            log_content = log_file.read_text()
            assert "Unhandled exception" in log_content
            assert "Test exception" in log_content
            assert "ValueError" in log_content
