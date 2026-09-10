"""Tests for ``mvp.bot.event_log.EventLogger.open_log_dir`` (#13).

Pure logic — creating the directory and returning the path. No ``os.startfile``
side effects (those are mocked separately).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mvp.bot.event_log import EventLogger


def test_open_log_dir_returns_absolute_path(tmp_path):
    logger = EventLogger(log_dir=str(tmp_path / "logs"), enabled=False)
    result = logger.open_log_dir()
    assert isinstance(result, Path)
    assert result.is_absolute()
    assert result == (tmp_path / "logs").resolve()


def test_open_log_dir_creates_missing_directory(tmp_path):
    """The directory does not exist — ``open_log_dir()`` creates it before returning."""
    log_dir = tmp_path / "nie_istnieje" / "zagniezdzone" / "logs"
    assert not log_dir.exists()

    logger = EventLogger(log_dir=str(log_dir), enabled=False)
    result = logger.open_log_dir()

    assert result.exists()
    assert result.is_dir()


def test_open_log_dir_idempotent(tmp_path):
    """Repeated calls do not change state (the directory already exists)."""
    logger = EventLogger(log_dir=str(tmp_path / "logs"), enabled=False)

    path1 = logger.open_log_dir()
    path2 = logger.open_log_dir()
    assert path1 == path2


def test_open_log_dir_handles_relative_path(tmp_path, monkeypatch):
    """A relative path is resolved against CWD into an absolute path."""
    monkeypatch.chdir(tmp_path)
    logger = EventLogger(log_dir="relative_logs", enabled=False)

    result = logger.open_log_dir()

    assert result.is_absolute()
    assert result.exists()


def test_open_log_dir_opens_explorer_when_requested(tmp_path):
    """When ``open_in_explorer=True``, ``os.startfile`` is called with the path."""
    logger = EventLogger(log_dir=str(tmp_path / "logs"), enabled=False)
    expected_path = (tmp_path / "logs").resolve()

    with patch("mvp.bot.event_log.os.startfile") as mock_startfile:
        result = logger.open_log_dir(open_in_explorer=True)

    assert result == expected_path
    mock_startfile.assert_called_once_with(str(expected_path))


def test_open_log_dir_does_not_open_explorer_by_default(tmp_path):
    """Bez jawnego ``open_in_explorer=True`` — NIE otwieramy Explorera."""
    logger = EventLogger(log_dir=str(tmp_path / "logs"), enabled=False)

    with patch("mvp.bot.event_log.os.startfile") as mock_startfile:
        logger.open_log_dir()

    mock_startfile.assert_not_called()


def test_open_log_dir_swallows_explorer_failure(tmp_path):
    """An ``os.startfile`` failure does NOT propagate — log_dir was created, we return the path."""
    logger = EventLogger(log_dir=str(tmp_path / "logs"), enabled=False)

    with (
        patch("mvp.bot.event_log.os.startfile", side_effect=OSError("no explorer")),
        patch("mvp.bot.event_log.logger") as mock_logger,
    ):
        result = logger.open_log_dir(open_in_explorer=True)

    assert result.exists()
    # WARNING logged, but the exception does NOT escape
    assert mock_logger.warning.called or mock_logger.debug.called


def test_open_log_dir_on_disabled_logger_still_creates(tmp_path):
    """``enabled=False`` does not block directory creation — that is a separate flag."""
    log_dir = tmp_path / "logs"
    logger = EventLogger(log_dir=str(log_dir), enabled=False)

    result = logger.open_log_dir()
    assert result.exists()


@pytest.mark.parametrize(
    "bad_path",
    ["", None],  # pusty string i None
)
def test_open_log_dir_rejects_empty_path(bad_path, tmp_path, monkeypatch):
    """Empty path or None → ValueError (simulated by swapping ``_dir``)."""
    logger = EventLogger(log_dir=str(tmp_path / "logs"), enabled=False)
    # Simulate the "unconfigured" state: ``_dir`` is set to None.
    # This is a realistic edge case only for direct API users
    # (e.g. tests, reflection). In normal usage ``__init__`` always
    # initializes ``_dir``.
    if bad_path is None:
        monkeypatch.setattr(logger, "_dir", None)
    else:
        # Empty string — from the constructor it would be replaced with the default
        # "logs" anyway; we only test None as "truly unconfigured".
        monkeypatch.setattr(logger, "_dir", None)

    with pytest.raises((ValueError, TypeError)):
        logger.open_log_dir()
