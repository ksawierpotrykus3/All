import ctypes
import logging
import time
from ctypes import wintypes
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_hwnd_cache: dict[str, tuple[int, float, "WindowInfo | None"]] = {}
_NEG_TTL_S = 2.0
_POS_TTL_S = 30.0

ASFW_ANY = 0x0000FFFF


# Toolhelp32 snapshot API (fast process enumeration without psutil.process_iter).
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


if hasattr(kernel32, "CreateToolhelp32Snapshot"):
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = wintypes.BOOL


@dataclass
class WindowInfo:

    hwnd: int
    left: int
    top: int
    right: int
    bottom: int
    title: str
    title_bar_height: int = 0

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)


def _refresh_window_geometry(hwnd: int, pid: int) -> WindowInfo | None:
    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return None
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if process_id.value != pid:
        return None
    if user32.IsIconic(hwnd):
        return None
    client_rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    cwidth = client_rect.right - client_rect.left
    cheight = client_rect.bottom - client_rect.top
    if cwidth <= 0 or cheight <= 0:
        return None
    window_rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
    title_bar_h = max(0, origin.y - window_rect.top)
    return WindowInfo(
        hwnd=hwnd,
        left=origin.x,
        top=origin.y,
        right=origin.x + cwidth,
        bottom=origin.y + cheight,
        title=_get_window_title(hwnd),
        title_bar_height=title_bar_h,
    )


def find_game_window(process_name: str = "Survival.exe") -> WindowInfo | None:
    cached = _hwnd_cache.get(process_name)
    if cached is not None:
        pid, ts, info = cached
        now = time.monotonic()
        if info is not None:
            if now - ts <= _POS_TTL_S:
                refreshed = _refresh_window_geometry(info.hwnd, pid)
                if refreshed is not None:
                    if (refreshed.left, refreshed.top, refreshed.right, refreshed.bottom) != (
                        info.left,
                        info.top,
                        info.right,
                        info.bottom,
                    ):
                        _hwnd_cache[process_name] = (pid, now, refreshed)
                    return refreshed
        else:
            if now - ts <= _NEG_TTL_S:
                return None
        _hwnd_cache.pop(process_name, None)

    pids = _find_process_pids(process_name)
    if not pids:
        # No matching game process is running. Do NOT fall back to a simulator
        # window by title: a simulator window that is not owned by the target
        # process would be a false positive that wrongly routes the caller into
        # the "abort spam" branch instead of the safe "proceed-when-absent" branch.
        _hwnd_cache[process_name] = (0, time.monotonic(), None)
        return None

    result: WindowInfo | None = None
    result_pid: int = 0
    first_info: WindowInfo | None = None
    first_pid: int = 0

    def enum_callback(hwnd: int, lparam: int) -> bool:
        nonlocal result, result_pid, first_info, first_pid
        if not user32.IsWindowVisible(hwnd):
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value in pids:
            client_rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client_rect))
            origin = wintypes.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(origin))
            cwidth = client_rect.right - client_rect.left
            cheight = client_rect.bottom - client_rect.top

            window_rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
            title_bar_h = max(0, origin.y - window_rect.top)

            title = _get_window_title(hwnd)
            if not user32.IsIconic(hwnd) and cwidth > 0 and cheight > 0:
                info = WindowInfo(
                    hwnd=hwnd,
                    left=origin.x,
                    top=origin.y,
                    right=origin.x + cwidth,
                    bottom=origin.y + cheight,
                    title=title,
                    title_bar_height=title_bar_h,
                )
                if first_info is None:
                    first_info = info
                    first_pid = process_id.value
                # Multiple windows can share the process (e.g. the dev bot runs
                # in python.exe next to the simulator window). Always prefer the
                # simulator window over the first arbitrary match.
                if title and _SIMULATOR_WINDOW_TITLE.lower() in title.lower():
                    result = info
                    result_pid = process_id.value
                    return False
        return True

    user32.EnumWindows(_WNDENUMPROC(enum_callback), 0)
    if result is None and first_info is not None:
        result = first_info
        result_pid = first_pid
    if result is None:
        logger.debug("Game window not found for process %s", process_name)
    else:
        _hwnd_cache[process_name] = (result_pid, time.monotonic(), result)
        _warn_if_calibration_mismatch(result)
    return result


_CALIBRATED_CLIENT_H = 1080


def _warn_if_calibration_mismatch(info: WindowInfo) -> None:
    if info.height > 0 and abs(info.height - _CALIBRATED_CLIENT_H) > 8:
        logger.debug(
            "Game window is %d px tall (base calibration = %d px). "
            "Client area scaling is handled linearly.",
            info.height,
            _CALIBRATED_CLIENT_H,
        )


_pid_cache: dict[str, tuple[float, set[int]]] = {}
_PID_CACHE_TTL_S = 10.0


def _find_process_pids_toolhelp(process_name: str) -> set[int]:
    """Enumerate PIDs via CreateToolhelp32Snapshot (fast, no psutil.process_iter)."""
    target = process_name.lower()
    pids: set[int] = set()
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return pids
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return pids
        while True:
            if entry.szExeFile and entry.szExeFile.lower() == target:
                pids.add(int(entry.th32ProcessID))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return pids


def _find_process_pids(process_name: str) -> set[int]:
    now = time.monotonic()
    cached = _pid_cache.get(process_name)
    if cached is not None:
        ts, pids = cached
        if now - ts <= _PID_CACHE_TTL_S:
            alive_pids = {pid for pid in pids if psutil.pid_exists(pid)}
            if alive_pids:
                return alive_pids

    pids: set[int] = set()
    try:
        if hasattr(kernel32, "CreateToolhelp32Snapshot") and hasattr(
            kernel32, "Process32FirstW"
        ):
            pids = _find_process_pids_toolhelp(process_name)
        else:
            raise AttributeError("Toolhelp32Snapshot unavailable")
    except Exception as exc:
        logger.debug(
            "Toolhelp32Snapshot enumeration failed (%s); falling back to psutil", exc
        )
        pids = set()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                    pids.add(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    _pid_cache[process_name] = (now, pids)
    return pids


_SIMULATOR_WINDOW_TITLE = "LastZ Simulator"


def _find_window_by_title(title: str) -> "WindowInfo | None":
    result: WindowInfo | None = None

    def enum_callback(hwnd: int, lparam: int) -> bool:
        nonlocal result
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
        except Exception:
            return True
        try:
            if _get_window_title(hwnd) != title:
                return True
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            refreshed = _refresh_window_geometry(hwnd, process_id.value)
        except Exception:
            refreshed = None
        if refreshed is not None:
            result = refreshed
            return False
        return True

    user32.EnumWindows(_WNDENUMPROC(enum_callback), 0)
    return result


def _get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def force_foreground(process_name: str = "Survival.exe") -> bool:
    info = find_game_window(process_name)
    if info is None:
        return False
    hwnd = info.hwnd
    fg = user32.GetForegroundWindow()

    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    _kernel32 = ctypes.windll.kernel32
    our_tid = _kernel32.GetCurrentThreadId()

    try:
        # AllowSetForegroundWindow relaxes the Windows foreground-lock for our
        # process so a background thread can legitimately take focus.
        if hasattr(user32, "AllowSetForegroundWindow"):
            try:
                user32.AllowSetForegroundWindow(ASFW_ANY)
            except Exception:
                pass

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        else:
            user32.ShowWindow(hwnd, 5)

        attached = False
        if fg_tid != our_tid:
            attached = bool(user32.AttachThreadInput(our_tid, fg_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        if attached:
            user32.AttachThreadInput(our_tid, fg_tid, False)
    except Exception:
        return False

    new_fg = user32.GetForegroundWindow()
    if not new_fg:
        return False
    cached = _hwnd_cache.get(process_name)
    if cached is not None and cached[2] is not None and cached[2].hwnd == new_fg:
        return True
    fg_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(new_fg, ctypes.byref(fg_pid))
    try:
        return fg_pid.value in _find_process_pids(process_name)
    except Exception:
        return False


def is_foreground(process_name: str = "Survival.exe") -> bool:
    try:
        fg = user32.GetForegroundWindow()
        if not fg:
            return False
        # Fast path: if the cached game hwnd equals the foreground hwnd, the window
        # is foreground without any enumeration.
        cached = _hwnd_cache.get(process_name)
        if cached is not None and cached[2] is not None and fg == cached[2].hwnd:
            return True
        info = find_game_window(process_name)
        if info is not None and fg == info.hwnd:
            return True
        # Weryfikacja PID: jeśli aktywne okno (np. modal, popup) należy do procesu gry, okno jest w fokusie
        fg_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fg, ctypes.byref(fg_pid))
        return fg_pid.value in _find_process_pids(process_name)
    except Exception:
        return False


def is_bot_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def check_uipi_elevation_mismatch(process_name: str = "Survival.exe") -> bool:
    if is_bot_admin():
        return False
    pids = _find_process_pids(process_name)
    if not pids:
        return False
    PROCESS_QUERY_INFORMATION = 0x0400
    for pid in pids:
        h_proc = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if not h_proc:
            err = kernel32.GetLastError()
            if err == 5:
                return True
        else:
            kernel32.CloseHandle(h_proc)
    return False