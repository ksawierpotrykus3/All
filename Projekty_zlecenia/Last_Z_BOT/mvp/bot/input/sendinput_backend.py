from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import time

from mvp.bot.exceptions import ClickerError
from mvp.bot.input.backend import InputBackend

logger = logging.getLogger(__name__)

INPUT_MOUSE = 0

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

WHEEL_DELTA = 120

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


class SendInputBackend(InputBackend):
    name = "sendinput"

    def __init__(self) -> None:
        self._initialized = False
        self._user32 = None
        self._cached_input = _INPUT()
        self._cached_input.type = INPUT_MOUSE
        self._cached_arr = (_INPUT * 1)(self._cached_input)
        self._input_size = ctypes.sizeof(_INPUT)
        self._screen_metrics: tuple[int, int, int, int] | None = None
        self._screen_metrics_ts: float = 0.0
        self._screen_metrics_ttl_s: float = 2.0
        self._in_spam_session = False

    def available(self) -> bool:
        if os.name != "nt":
            return False
        try:
            user32 = ctypes.windll.user32
            return bool(getattr(user32, "SendInput", None))
        except Exception:
            return False

    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            user32 = ctypes.windll.user32
            user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
            user32.SendInput.restype = wintypes.UINT
            if hasattr(user32, "GetSystemMetrics"):
                user32.GetSystemMetrics.argtypes = [ctypes.c_int]
                user32.GetSystemMetrics.restype = ctypes.c_int
            self._user32 = user32
            self._initialized = True
            self._screen_metrics = None
            logger.info("SendInput backend initialized")
            return True
        except Exception as exc:
            logger.error("SendInput backend initialization failed: %s", exc)
            self._initialized = False
            return False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def begin_spam_session(self) -> None:
        """Cache screen metrics for the whole spam series.

        During a spam series we refresh GetSystemMetrics once and reuse the cached
        values, avoiding a TTL check + WinAPI round-trips on every down/up/move.
        """
        self._in_spam_session = True
        # Force a fresh metric read at session start (covers monitor geometry changes).
        self._screen_metrics = None

    def end_spam_session(self) -> None:
        self._in_spam_session = False

    def _to_normalized_coords(self, x: int, y: int) -> tuple[int, int]:
        now = time.monotonic()
        expired = (now - self._screen_metrics_ts) > self._screen_metrics_ttl_s
        if self._screen_metrics is None or (not self._in_spam_session and expired):
            try:
                v_left = int(self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
                v_top = int(self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
                v_width = int(self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
                v_height = int(self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
            except Exception:
                v_left, v_top, v_width, v_height = 0, 0, 0, 0

            if v_width <= 0 or v_height <= 0:
                v_left, v_top, v_width, v_height = 0, 0, 1920, 1080

            self._screen_metrics = (v_left, v_top, v_width, v_height)
            self._screen_metrics_ts = now
        else:
            v_left, v_top, v_width, v_height = self._screen_metrics

        nx = int(((int(x) - v_left) * 65536) / v_width)
        ny = int(((int(y) - v_top) * 65536) / v_height)
        return max(0, min(nx, 65535)), max(0, min(ny, 65535))

    def _send_fast(self, flags: int, dx: int = 0, dy: int = 0, mouse_data: int = 0) -> None:
        if getattr(self._send, "__name__", "") != "_send":
            self._send([self._mouse_input(flags, dx=dx, dy=dy, mouse_data=mouse_data)])
            return

        mi = self._cached_arr[0].union.mi
        mi.dx = dx
        mi.dy = dy
        mi.mouseData = mouse_data
        mi.dwFlags = flags
        mi.time = 0
        mi.dwExtraInfo = 0
        sent = self._user32.SendInput(1, self._cached_arr, self._input_size)
        if sent != 1:
            err = ctypes.GetLastError()
            if err == 5:
                logger.debug("SendInput blocked by UIPI or locked desktop (Error 5: ERROR_ACCESS_DENIED)")
            raise ClickerError(f"SendInput delivered {sent}/1 events (error={err})")

    def _send(self, inputs: list[_INPUT]) -> None:
        n = len(inputs)
        arr = (_INPUT * n)(*inputs)
        sent = self._user32.SendInput(n, arr, ctypes.sizeof(_INPUT))
        if sent != n:
            err = ctypes.GetLastError()
            if err == 5:
                logger.debug("SendInput blocked by UIPI or locked desktop (Error 5: ERROR_ACCESS_DENIED)")
            raise ClickerError(f"SendInput delivered {sent}/{n} events (error={err})")

    def _mouse_input(self, flags: int, dx: int = 0, dy: int = 0, mouse_data: int = 0) -> _INPUT:
        inp = _INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi = _MOUSEINPUT(dx, dy, mouse_data, flags, 0, 0)
        return inp

    def mouse_down_left(self) -> None:
        self._send_fast(MOUSEEVENTF_LEFTDOWN)

    def mouse_up_left(self) -> None:
        self._send_fast(MOUSEEVENTF_LEFTUP)

    def move_to(self, x: int, y: int) -> None:
        nx, ny = self._to_normalized_coords(x, y)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_fast(flags, dx=nx, dy=ny)

    def scroll(self, direction: str) -> None:
        if direction not in ("up", "down"):
            raise ClickerError(f"Invalid scroll direction: {direction!r}")
        mouse_data = WHEEL_DELTA if direction == "up" else -WHEEL_DELTA
        self._send_fast(MOUSEEVENTF_WHEEL, mouse_data=mouse_data)

    def get_cursor_pos(self) -> tuple[int, int]:
        point = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    def spam_down(self, x: int, y: int) -> None:
        nx, ny = self._to_normalized_coords(x, y)
        # No MOUSEEVENTF_MOVE: DOWN must land at the exact same coords as UP (Delta r = 0).
        # Moving during the press would flip eligibleForClick to false in Unity (camera drag).
        flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTDOWN
        self._send_fast(flags, dx=nx, dy=ny)

    def spam_up(self, x: int, y: int) -> None:
        nx, ny = self._to_normalized_coords(x, y)
        flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTUP
        self._send_fast(flags, dx=nx, dy=ny)

    def spam_move(self, x: int, y: int) -> None:
        nx, ny = self._to_normalized_coords(x, y)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_fast(flags, dx=nx, dy=ny)

    def shutdown(self) -> None:
        self._initialized = False
        self._in_spam_session = False
        logger.info("SendInput backend shutdown")