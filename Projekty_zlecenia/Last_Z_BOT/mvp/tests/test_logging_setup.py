"""Tests for MVP logging setup and GUI log handler."""

import logging
import sys

from mvp.gui.log_handler import GuiLogHandler
from mvp.logging_setup import setup_logging


class _FakeState:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def push_log(self, message: str) -> None:
        self.messages.append(message)


def test_setup_logging_adds_file_and_stream_handlers(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", None, raising=False)
    monkeypatch.setattr(setup_logging, "_installed", False, raising=False)
    root = logging.getLogger()
    # Remove previously attached handlers to make the test deterministic.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    setup_logging(debug=False)

    handlers = root.handlers
    assert any(isinstance(h, logging.StreamHandler) for h in handlers)
    assert any(isinstance(h, logging.FileHandler) for h in handlers)


def test_gui_handler_filters_noisy_info() -> None:
    state = _FakeState()
    handler = GuiLogHandler(state, level=logging.INFO)
    record = logging.LogRecord(
        name="mvp.bot.capture",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="polling",
        args=(),
        exc_info=None,
    )
    assert handler.filter(record) is False


def test_gui_handler_passes_error_from_noisy_logger() -> None:
    state = _FakeState()
    handler = GuiLogHandler(state, level=logging.INFO)
    record = logging.LogRecord(
        name="mvp.bot.capture",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="failure",
        args=(),
        exc_info=None,
    )
    assert handler.filter(record) is True


def test_gui_handler_passes_info_from_non_noisy_logger() -> None:
    state = _FakeState()
    handler = GuiLogHandler(state, level=logging.INFO)
    record = logging.LogRecord(
        name="mvp.config",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="loaded",
        args=(),
        exc_info=None,
    )
    assert handler.filter(record) is True