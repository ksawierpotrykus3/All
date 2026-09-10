
from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class AntiDetectError(Exception):
    pass


_kernel32: object | None = None




class _Backend:

    name: str = "unknown"

    def detect_debugger(self) -> bool:
        return False

    def harden(self) -> bool:
        return False


class _WindowsBackend(_Backend):

    name = "win32"

    def __init__(self) -> None:
        self._resolved = False
        self._ready = False
        self._proc_handle: int | None = None

    def _resolve(self) -> bool:
        if self._resolved:
            return self._ready
        self._resolved = True
        try:
            import ctypes

            self._k32 = _kernel32 if _kernel32 is not None else ctypes.windll.kernel32
            self._proc_handle = self._k32.GetCurrentProcess()
            self._CheckRemoteDebuggerPresent = self._k32.CheckRemoteDebuggerPresent
            try:
                self._CheckRemoteDebuggerPresent.restype = ctypes.c_int
                self._CheckRemoteDebuggerPresent.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_int),
                ]
            except AttributeError:
                pass
            self._ready = True
        except Exception as exc:
            logger.debug("AntiDetect: Windows backend init failed: %s", exc)
            self._ready = False
        return self._ready

    def detect_debugger(self) -> bool:
        if not self._resolve():
            return False
        try:
            import ctypes

            is_debugged = ctypes.c_int(0)
            logger.debug(
                "[ANTI_DETECT] calling fn=%s, is_debugged=%s",
                self._CheckRemoteDebuggerPresent,
                is_debugged.value,
            )
            ret = self._CheckRemoteDebuggerPresent(self._proc_handle, ctypes.byref(is_debugged))
            logger.debug("[ANTI_DETECT] ret=%s, is_debugged=%s", ret, is_debugged.value)
            if ret == 0:
                return False
            return bool(is_debugged.value)
        except Exception as exc:
            logger.debug("[ANTI_DETECT] exception: %s", exc)
            return False

    def harden(self) -> bool:
        return True


class _LinuxBackend(_Backend):

    name = "linux"

    PR_SET_DUMPABLE = 4

    def __init__(self) -> None:
        self._libc = None
        try:
            import ctypes

            self._libc = ctypes.CDLL("libc.so.6", use_errno=True)
        except Exception as exc:
            logger.debug("AntiDetect: libc unavailable: %s", exc)

    def detect_debugger(self) -> bool:
        try:
            with open("/proc/self/status", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("TracerPid:"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            try:
                                pid = int(parts[1].strip())
                                return pid != 0
                            except ValueError:
                                return False
            return False
        except OSError as exc:
            logger.debug("AntiDetect: /proc/self/status unreadable: %s", exc)
            return False
        except Exception as exc:
            logger.debug("AntiDetect: parse /proc failed: %s", exc)
            return False

    def harden(self) -> bool:
        if self._libc is None:
            return False
        try:
            import ctypes

            self._libc.prctl(self.PR_SET_DUMPABLE, ctypes.c_int(0))
            return True
        except Exception as exc:
            logger.debug("AntiDetect: prctl failed: %s", exc)
            return False


class _DarwinBackend(_Backend):

    name = "darwin"

    def detect_debugger(self) -> bool:
        return False

    def harden(self) -> bool:
        return False


def _make_backend() -> _Backend:
    if sys.platform.startswith("win"):
        return _WindowsBackend()
    if sys.platform.startswith("linux"):
        return _LinuxBackend()
    return _DarwinBackend()




class AntiDetect:

    def __init__(self, *, check_interval_s: float = 30.0) -> None:
        if check_interval_s < 0:
            raise ValueError(f"check_interval_s must be >= 0, got {check_interval_s}")
        self.check_interval_s = check_interval_s
        self._backend = _make_backend()
        self.platform = self._backend.name
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._callback: Callable[[bool], None] | None = None


    def detect_debugger(self) -> bool:
        try:
            return self._backend.detect_debugger()
        except Exception as exc:
            logger.debug("AntiDetect: backend.detect_debugger raised: %s", exc)
            return False


    def harden_process(self) -> bool:
        try:
            return self._backend.harden()
        except Exception as exc:
            logger.debug("AntiDetect: harden failed: %s", exc)
            return False


    def check_and_harden_on_startup(self) -> dict:
        detected = self.detect_debugger()
        hardened = self.harden_process()
        if detected:
            logger.warning(
                "AntiDetect: a debugger attached to this process was detected — the bot may be analyzed."
            )
        if hardened:
            logger.debug("AntiDetect: harden applied (%s)", self.platform)
        return {"debugger_detected": detected, "hardened": hardened}


    def start_periodic_check(self, callback: Callable[[bool], None]) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._callback = callback
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._periodic_loop,
            name="AntiDetect",
            daemon=True,
        )
        self._thread.start()

    def _periodic_loop(self) -> None:
        while not self._stop_event.is_set():
            detected = self.detect_debugger()
            if detected and self._callback is not None:
                try:
                    self._callback(True)
                except Exception:
                    logger.exception("AntiDetect callback raised")
            if self._stop_event.wait(self.check_interval_s):
                return

    def stop(self) -> None:
        self._stop_event.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)


__all__ = ["AntiDetect", "AntiDetectError"]
