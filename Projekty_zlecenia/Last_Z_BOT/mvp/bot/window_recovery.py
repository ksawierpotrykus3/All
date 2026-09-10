
from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class WindowNotFoundError(RuntimeError):
    pass


RetryHook = Callable[[int, int, float], None]


class WindowRecoveryWatchdog:

    def __init__(
        self,
        *,
        finder: Callable[..., object | None],
        max_attempts: int = 30,
        retry_interval_s: float = 2.0,
        backoff_multiplier: float = 1.5,
        max_backoff_s: float = 30.0,
        on_retry: RetryHook | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
        self._finder = finder
        self.max_attempts = max_attempts
        self.retry_interval_s = retry_interval_s
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff_s = max_backoff_s
        self._on_retry = on_retry
        self._sleep = sleep
        self._is_recovering = False

    @property
    def is_recovering(self) -> bool:
        return self._is_recovering

    def _compute_backoff_s(self, attempt: int) -> float:
        raw = self.retry_interval_s * (self.backoff_multiplier ** (attempt - 1))
        return min(raw, self.max_backoff_s)

    def wait_for_window(self, *args, **kwargs) -> object | None:
        self._is_recovering = True
        try:
            for attempt in range(1, self.max_attempts + 1):
                info = self._finder(*args, **kwargs)
                if info is not None and getattr(info, "hwnd", None):
                    if attempt > 1:
                        logger.info(
                            "Game window found after %d attempts (hwnd=%s).",
                            attempt,
                            info.hwnd,
                        )
                    return info

                next_sleep_s = self._compute_backoff_s(attempt)
                logger.warning(
                    "Game window not found (attempt %d/%d). Next attempt in %.1fs.",
                    attempt,
                    self.max_attempts,
                    next_sleep_s,
                )
                if self._on_retry is not None:
                    try:
                        self._on_retry(attempt, self.max_attempts, next_sleep_s)
                    except Exception:
                        logger.exception("on_retry hook raised")

                if attempt < self.max_attempts:
                    self._sleep(next_sleep_s)

            msg = (
                f"Game window not found after {self.max_attempts} attempts. "
                f"Start the game and try again."
            )
            logger.error(msg)
            raise WindowNotFoundError(msg)
        finally:
            self._is_recovering = False
