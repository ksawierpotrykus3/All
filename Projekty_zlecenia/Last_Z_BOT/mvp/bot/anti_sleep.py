
from __future__ import annotations

import ctypes
import logging
import threading
from typing import Final

from mvp.bot.exceptions import AntiSleepError

logger = logging.getLogger(__name__)

ES_CONTINUOUS: Final[int] = 0x80000000
ES_SYSTEM_REQUIRED: Final[int] = 0x00000001
ES_DISPLAY_REQUIRED: Final[int] = 0x00000002
ES_AWAYMODE_REQUIRED: Final[int] = 0x00000040

DEFAULT_HEARTBEAT_S: Final[float] = 30.0


class SleepGuard:

    def __init__(self, heartbeat_s: float = DEFAULT_HEARTBEAT_S) -> None:
        self._heartbeat_s = max(1.0, float(heartbeat_s))
        self._lock = threading.Lock()
        self._current_flags: int = 0
        self._kernel32 = ctypes.windll.kernel32
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop: threading.Event = threading.Event()

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._current_flags != 0

    def enable(
        self,
        display: bool = True,
        system: bool = True,
        away_mode: bool = False,
    ) -> None:
        flags = ES_CONTINUOUS
        if display:
            flags |= ES_DISPLAY_REQUIRED
        if system:
            flags |= ES_SYSTEM_REQUIRED
        if away_mode:
            flags |= ES_AWAYMODE_REQUIRED

        with self._lock:
            if flags == self._current_flags and self._heartbeat_thread is not None:
                return
            self._apply_flags(flags)
            self._current_flags = flags
            self._start_heartbeat_if_needed()

    def disable(self) -> None:
        with self._lock:
            if self._current_flags == 0 and self._heartbeat_thread is None:
                return
            self._apply_flags(ES_CONTINUOUS)
            self._current_flags = 0
            self._stop_heartbeat()

    def shutdown(self) -> None:
        self.disable()


    def _apply_flags(self, flags: int) -> None:
        result = self._kernel32.SetThreadExecutionState(flags)
        if not result:
            logger.error(
                "SleepGuard: SetThreadExecutionState(%#x) returned 0 — keep-awake rejected",
                flags,
            )
            raise AntiSleepError(
                f"SetThreadExecutionState({flags:#x}) returned 0 — the system rejected "
                f"the keep-awake request."
            )
        logger.debug("SleepGuard: SetThreadExecutionState(%#x) ok", flags)

    def _start_heartbeat_if_needed(self) -> None:
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="sleep-guard-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        stop = self._heartbeat_stop
        thread = self._heartbeat_thread
        if thread is None:
            return
        stop.set()
        thread.join(timeout=self._heartbeat_s + 1.0)
        self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_s):
            with self._lock:
                flags = self._current_flags
            if flags == 0:
                return
            try:
                self._kernel32.SetThreadExecutionState(flags)
            except AntiSleepError as exc:
                logger.warning("SleepGuard heartbeat failed: %s", exc)
            except Exception as exc:
                logger.debug("SleepGuard heartbeat unexpected error: %s", exc)
