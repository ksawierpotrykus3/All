
from __future__ import annotations

import contextlib
import ctypes
import ctypes.wintypes as wt
import logging
import threading

from mvp.config import parse_key

__all__ = [
    "GlobalHotkey",
    "parse_key",
    "WM_HOTKEY",
    "WM_QUIT",
    "MOD_NOREPEAT",
    "VK_F1",
]

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
VK_F1 = 0x70

_user32 = ctypes.windll.user32


class GlobalHotkey:

    def __init__(self, vk: int = VK_F1, callback=None, hotkey_id: int = 1) -> None:
        self._vk = vk
        self._callback = callback
        self._hotkey_id = hotkey_id
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return True
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name=f"global-hotkey-{self._vk:#x}", daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        thread = self._thread
        thread_id = thread.ident if thread is not None else None
        if thread_id is not None:
            try:
                _user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            except Exception:
                logger.debug("GlobalHotkey: PostThreadMessageW failed", exc_info=True)
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
            if thread.is_alive():
                with contextlib.suppress(Exception):
                    _user32.UnregisterHotKey(None, self._hotkey_id)
        self._thread = None

    def _get_message(self, msg: wt.MSG) -> int:
        return _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)

    def _run(self) -> None:
        msg = wt.MSG()
        _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        if not _user32.RegisterHotKey(None, self._hotkey_id, MOD_NOREPEAT, self._vk):
            err = ctypes.GetLastError()
            logger.warning(
                "GlobalHotkey: RegisterHotKey failed for %#x (Win32 Error: %d). "
                "Another process (or previous bot instance in background) is already using this key.",
                self._vk,
                err,
            )
            return

        logger.info("GlobalHotkey: %#x registered globally", self._vk)
        try:
            while self._running:
                result = self._get_message(msg)
                if result <= 0:
                    break
                if (
                    msg.message == WM_HOTKEY
                    and msg.wParam == self._hotkey_id
                    and self._callback is not None
                ):
                    try:
                        self._callback()
                    except Exception:
                        logger.exception("GlobalHotkey: callback raised")
        finally:
            _user32.UnregisterHotKey(None, self._hotkey_id)
            logger.info("GlobalHotkey: unregistered")
