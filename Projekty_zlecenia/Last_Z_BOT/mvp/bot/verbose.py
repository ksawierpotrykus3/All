
from __future__ import annotations

import contextlib
import logging
import sys
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class VerboseError(Exception):
    pass


class ValidLevels(StrEnum):

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"


_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
}


def _normalize_level(level: str | int) -> tuple[str, int]:
    normalized = level.upper() if isinstance(level, str) else logging.getLevelName(level)
    if normalized not in _LEVEL_MAP:
        raise VerboseError(
            f"Unknown log level: {level!r}. Expected: DEBUG / INFO / WARNING."
        )
    return normalized, _LEVEL_MAP[normalized]


class VerboseController:

    def __init__(
        self,
        *,
        root_logger: logging.Logger | None = None,
        disable_console: bool = False,
    ) -> None:
        self._logger = root_logger if root_logger is not None else logging.root
        self._file_handler: logging.FileHandler | None = None
        self._stream_handler: logging.StreamHandler | None = None
        self._saved_level: tuple[str, int] | None = None
        self._current_level = "INFO"
        self._logger.setLevel(logging.INFO)
        if not disable_console:
            self._ensure_console_handler()


    def set_level(self, level: str | int) -> None:
        name, num = _normalize_level(level)
        self._logger.setLevel(num)
        self._current_level = name
        logger.debug("VerboseController: level=%s (%d)", name, num)

    def get_current_level(self) -> str:
        return self._current_level

    def save_level(self) -> None:
        self._saved_level = (
            self._current_level,
            _LEVEL_MAP[self._current_level],
        )

    def restore_level(self) -> None:
        if self._saved_level is None:
            return
        name, num = self._saved_level
        self._logger.setLevel(num)
        self._current_level = name
        self._saved_level = None

    def reset(self) -> None:
        self.set_level("INFO")
        self.disable_file_output()


    def enable_file_output(self, path: str | Path) -> None:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(p, encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "VerboseController: cannot open log file %s (%s). "
                "Staying with stream handler.",
                p,
                exc,
            )
            raise VerboseError(f"Cannot open {p}: {exc}") from exc
        if self._file_handler is not None:
            self._logger.removeHandler(self._file_handler)
            with contextlib.suppress(Exception):
                self._file_handler.close()
        self._file_handler = handler
        self._logger.addHandler(handler)

    def disable_file_output(self) -> None:
        if self._file_handler is None:
            return
        self._logger.removeHandler(self._file_handler)
        with contextlib.suppress(Exception):
            self._file_handler.close()
        self._file_handler = None


    def _ensure_console_handler(self) -> None:
        if self._stream_handler is not None:
            return
        for handler in self._logger.handlers:
            if type(handler) is logging.StreamHandler:
                self._stream_handler = handler
                return
        handler = logging.StreamHandler(stream=sys.stderr)
        self._stream_handler = handler
        self._logger.addHandler(handler)

    def enable_console(self) -> None:
        self._ensure_console_handler()

    def disable_console(self) -> None:
        if self._stream_handler is None:
            return
        self._logger.removeHandler(self._stream_handler)
        self._stream_handler = None


__all__ = ["VerboseController", "VerboseError", "ValidLevels"]
