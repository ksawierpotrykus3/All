
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

_user32 = ctypes.windll.user32


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


_CBFUNC = ctypes.WINFUNCTYPE(
    ctypes.c_bool,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(_RECT),
    wintypes.LPARAM,
)


def _enum_monitors() -> list[dict]:
    monitors: list[dict] = []

    def callback(h_monitor, hdc, rect, param) -> bool:
        mi = _MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(_MONITORINFOEXW)
        _user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi))
        monitors.append(
            {
                "left": mi.rcMonitor.left,
                "top": mi.rcMonitor.top,
                "width": mi.rcMonitor.right - mi.rcMonitor.left,
                "height": mi.rcMonitor.bottom - mi.rcMonitor.top,
                "primary": bool(mi.dwFlags & 1),
            }
        )
        return True

    _user32.EnumDisplayMonitors(None, None, _CBFUNC(callback), 0)
    return monitors


def _get_dpi_scale_percent() -> int | None:
    """Zwraca skalowanie DPI (w %) dla procesu, np. 100, 125, 150, lub None."""
    try:
        # GetDpiForSystem dostępny od Windows 10 1607; zwraca DPI w skali 96=100%.
        dpi = _user32.GetDpiForSystem()
        return int(round(dpi / 96.0 * 100.0))
    except Exception:
        return None


def validate_environment(window_width: int, window_height: int) -> list[str]:
    """Zwraca listę ostrzeżeń o konfiguracji monitorów, DPI i okna gry.

    Bot jest skalibrowany pod okno gry ~1920x1080 (proporcje 16:9) na jednym
    monitorze przy skalowaniu DPI = 100%. Nietypowe konfiguracje powodują
    kliknięcia obok celu, dlatego ostrzegamy użytkownika wprost.
    """
    warnings: list[str] = []

    # 1. Skalowanie DPI (najczęstsza przyczyna „klika obok" na laptopach).
    dpi = _get_dpi_scale_percent()
    if dpi is not None and dpi != 100:
        warnings.append(
            f"Skalowanie ekranu Windows wynosi {dpi}% (wymagane 100%). "
            "Ustaw skalowanie na 100%, inaczej bot może klikać obok celu."
        )

    # 2. Wiele monitorów — problemem jest sam fakt >1 monitora, bo wirtualny
    #    pulpit Windows przesuwa współrzędne SendInput o offset kolejnych ekranów.
    try:
        monitors = _enum_monitors()
    except Exception as exc:
        logger.warning("Nie udało się pobrać listy monitorów: %s", exc)
        monitors = []

    if len(monitors) > 1:
        dims = {(m["width"], m["height"]) for m in monitors}
        if len(dims) > 1:
            warnings.append(
                "Wykryto wiele monitorów o różnych rozdzielczościach. "
                "Zalecany jest jeden monitor 1920x1080 ze skalowaniem 100%."
            )
        else:
            warnings.append(
                "Wykryto wiele monitorów. Gra musi być na monitorze głównym, "
                "inaczej współrzędne kliknięć zostaną przesunięte."
            )

    # 3. Rozdzielczość/proporcje okna gry. Bot skalibrowany pod 1920x1080 (16:9).
    if window_width > 0 and window_height > 0:
        ratio = window_width / window_height
        if abs(ratio - 16.0 / 9.0) > 0.05:
            warnings.append(
                f"Okno gry ma nietypowe proporcje ({window_width}x{window_height}, "
                f"ratio {ratio:.2f}); oczekiwano ~16:9. "
                "Sprawdź ustawienia gry — pełny ekran (np. Alt+Enter)."
            )
        # Za mała rozdzielczość = okno niepełnoekranowe (pasek tytułu/pasek zadań).
        # Za duża (1440p/4K) = fizyczna rozdzielczość monitora wyższa od kalibracji.
        if window_width < 1920 - 8 or window_height < 1080 - 8:
            warnings.append(
                f"Okno gry ma rozdzielczość {window_width}x{window_height}; "
                "oczekiwano ~1920x1080. Wciśnij Alt+Enter w grze, aby przejść "
                "na pełny ekran."
            )
        elif window_width > 1920 + 8 or window_height > 1080 + 8:
            warnings.append(
                f"Okno gry ma rozdzielczość {window_width}x{window_height}; "
                "oczekiwano ~1920x1080. Przy innej rozdzielczości kliknięcia "
                "mogą być niedokładne."
            )

    return warnings


def get_primary_monitor_size() -> tuple[int, int] | None:
    try:
        monitors = _enum_monitors()
    except Exception as exc:
        logger.warning("EnumDisplayMonitors failed: %s", exc)
        return None
    for mon in monitors:
        if mon.get("primary"):
            return mon["width"], mon["height"]
    return None


def get_monitor_for_window(
    window_left: int,
    window_top: int,
    window_width: int,
    window_height: int,
) -> tuple[int, tuple[int, int, int, int]] | None:
    try:
        monitors = _enum_monitors()
    except Exception as exc:
        logger.warning("EnumDisplayMonitors failed: %s", exc)
        return None

    if not monitors:
        logger.warning("EnumDisplayMonitors returned empty list")
        return None

    center_x = window_left + window_width / 2
    center_y = window_top + window_height / 2

    for idx, info in enumerate(monitors):
        ml = info["left"]
        mt = info["top"]
        mw = info["width"]
        mh = info["height"]
        if ml <= center_x <= ml + mw and mt <= center_y <= mt + mh:
            left = max(window_left - ml, 0)
            top = max(window_top - mt, 0)
            right = min(window_left + window_width - ml, mw)
            bottom = min(window_top + window_height - mt, mh)
            adjusted_region = (left, top, right, bottom)
            return idx, adjusted_region

    logger.debug("Window center (%d,%d) not on any known monitor", center_x, center_y)
    return None
