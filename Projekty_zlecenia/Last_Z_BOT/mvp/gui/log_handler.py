
from __future__ import annotations

import logging
from typing import Protocol


class _LogQueueLike(Protocol):
    def push_log(self, message: str) -> None: ...


_NOISY_LOGGER_NAMES: frozenset[str] = frozenset(
    {
        "mvp.bot.capture",
        "mvp.bot.ocr",
        "PIL",
        "PIL.Image",
        "rapidocr_onnxruntime",
    }
)

_MAX_RECORD_LENGTH = 500


class GuiLogHandler(logging.Handler):

    def __init__(self, queue: _LogQueueLike, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        if not self.filter(record):
            return
        try:
            message = self.format(record)
            if len(message) > _MAX_RECORD_LENGTH:
                message = message[:_MAX_RECORD_LENGTH] + "…"
            self._queue.push_log(message)
        except Exception:
            pass

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name in _NOISY_LOGGER_NAMES and record.levelno < logging.WARNING:
            return False
        return super().filter(record)
