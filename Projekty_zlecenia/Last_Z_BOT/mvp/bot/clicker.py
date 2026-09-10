from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import math
import random
import threading
import time
from logging import DEBUG

from mvp.bot.exceptions import ClickerError
from mvp.bot.input import InputBackend, initialize_backend

logger = logging.getLogger(__name__)

INPUT_FPS_MODES: tuple[str, ...] = ("60", "200")
DIG_HOLD_MS_200FPS = 3
DIG_HOLD_MS_60FPS = 18
MAX_CPS_60FPS = 38

# Bezpieczny pułap CPS w trybie 60 FPS. AGENTS.md §1 dopuszcza do 38.46 CPS,
# ale przy holdzie 18 ms przerwa UP wynosi wtedy tylko ~8.3 ms, co ryzykuje
# koalescencję zdarzeń i ReportFastClick. Pułap 35 CPS daje okres >= 28.6 ms
# i przerwę UP >= 10.6 ms (>= MIN_UP_GAP_HEADROOM_S).
MAX_CPS_60FPS_SAFE = 35
MIN_UP_GAP_HEADROOM_S = 0.010

SPIN_THRESHOLD_S = 0.0004
DEFAULT_FOCUS_CHECK_INTERVAL_S = 3.0


def _ts() -> str:
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _spin_until(target: float) -> None:
    """Busy-wait only for the final micro-window; yield for everything larger.

    AGENTS.md §12: with ``timeBeginPeriod(1)`` the sleep threshold is 1.5 ms. Above
    ~1.5 ms we release the CPU quantum via a real ``time.sleep``; the hard busy-wait
    spinlock is confined to the final <0.4 ms micro-window so the Unity PlayerLoop
    is not starved.
    """
    while True:
        rem = target - time.perf_counter()
        if rem <= 0:
            return
        if rem > 0.0015:
            time.sleep(rem - 0.001)
        elif rem > SPIN_THRESHOLD_S:
            # Micro-window above the busy-wait threshold: release the CPU quantum
            # via a plain yield. This matches AGENTS.md §12's intended pattern and
            # avoids the sub-ms ``time.sleep`` that Windows would round up to ~1 ms.
            time.sleep(0)
        else:
            # Hard busy-wait spinlock confined to the final <0.4ms micro-window.
            while time.perf_counter() < target:
                pass
            return


def precise_sleep(duration_s: float) -> None:
    if duration_s <= 0:
        return
    if getattr(time.sleep, "__name__", "") != "sleep":
        time.sleep(duration_s)
        return

    target = time.perf_counter() + duration_s
    rem = duration_s
    if rem > 0.0015:
        time.sleep(rem - 0.001)

    _spin_until(target)


def precise_sleep_until(target_time: float) -> None:
    rem = target_time - time.perf_counter()
    if rem <= 0:
        return
    if getattr(time.sleep, "__name__", "") != "sleep":
        time.sleep(rem)
        return

    if rem > 0.0015:
        time.sleep(rem - 0.001)

    _spin_until(target_time)



class Clicker:
    def __init__(
        self,
        min_delay_ms: int = 280,
        max_delay_ms: int = 350,
        spam_noise_px: float = 3.0,
        input_fps_mode: str = "60",
        click_jitter_ms: float = 0.5,
        dig_hold_ms_60fps: int = DIG_HOLD_MS_60FPS,
        dig_hold_ms_200fps: int = DIG_HOLD_MS_200FPS,
        max_cps_60fps: int = MAX_CPS_60FPS,
        input_backend: str = "sendinput",
        process_name: str = "Survival.exe",
        focus_watchdog_enabled: bool = True,
        focus_check_interval: int = 5,
        focus_check_interval_s: float = DEFAULT_FOCUS_CHECK_INTERVAL_S,
    ) -> None:
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.spam_noise_px = spam_noise_px
        self.process_name = process_name
        self._timer_active = False
        self.total_clicks = 0
        self._clicks_lock = threading.Lock()
        self._abort_event = threading.Event()

        self.focus_watchdog_enabled = bool(focus_watchdog_enabled)
        self.focus_check_interval = max(1, int(focus_check_interval))
        self.focus_check_interval_s = max(0.0, float(focus_check_interval_s))
        self._last_focus_check = 0.0
        self._focus_refocus_warned = False
        self._focus_refocus_pending = False
        self._focus_refocus_done = False
        self._noise_sign = 1

        self._dig_hold_ms_60fps = int(dig_hold_ms_60fps)
        self._dig_hold_ms_200fps = int(dig_hold_ms_200fps)
        self._max_cps_60fps = int(max_cps_60fps)

        if self.min_delay_ms > self.max_delay_ms:
            logger.warning(
                "min_delay_ms (%d) > max_delay_ms (%d), swapping",
                self.min_delay_ms,
                self.max_delay_ms,
            )
            self.min_delay_ms, self.max_delay_ms = self.max_delay_ms, self.min_delay_ms

        if input_fps_mode not in INPUT_FPS_MODES:
            logger.warning("unknown input_fps_mode %r, falling back to '200'", input_fps_mode)
            input_fps_mode = "200"
        self._input_fps_mode = input_fps_mode
        self.click_jitter_ms = click_jitter_ms

        self._backend_mode = (
            input_backend if input_backend in ("auto", "sendinput") else "sendinput"
        )
        self._backend: InputBackend | None = None

    def _resolve_backend(self) -> InputBackend | None:
        if self._backend is not None and self._backend.is_initialized:
            return self._backend
        return None

    def initialize(self) -> None:
        if self.is_initialized:
            return
        backend = initialize_backend(self._backend_mode)
        if backend is None:
            logger.error(
                "No input backend available (mode=%s, SendInput failed)",
                self._backend_mode,
            )
            return
        self._backend = backend
        self._enable_high_res_timer()
        import os

        if os.name == "nt":
            try:
                if (
                    hasattr(ctypes.windll, "shell32")
                    and hasattr(ctypes.windll.shell32, "IsUserAnAdmin")
                    and not ctypes.windll.shell32.IsUserAnAdmin()
                ):
                    logger.warning(
                        "Bot running without Administrator privileges. If %s runs as Administrator, "
                        "SendInput will be blocked by Windows UIPI (ERROR_ACCESS_DENIED / Error 5).",
                        self.process_name,
                    )
            except Exception as exc:
                logger.debug("IsUserAnAdmin check failed: %s", exc)

        logger.info("Clicker initialized (backend=%s)", backend.name)


    def _require_backend(self) -> InputBackend:
        self.initialize()
        backend = self._resolve_backend()
        if backend is None:
            raise ClickerError(
                "SendInput backend is not available."
            )
        return backend

    def set_backend_mode(self, mode: str) -> None:
        if mode not in ("auto", "sendinput"):
            logger.warning("unknown input_backend %r, falling back to 'sendinput'", mode)
            mode = "sendinput"
        if (
            mode == self._backend_mode
            and self._backend is not None
            and self._backend.is_initialized
        ):
            return
        if self._backend is not None:
            self._backend.shutdown()
        self._backend = None
        self._backend_mode = mode
        logger.info("Clicker backend mode switched to %r", mode)

    def _enable_high_res_timer(self) -> None:
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
            self._timer_active = True
        except Exception as exc:
            self._timer_active = False
            logger.debug("timeBeginPeriod(1) unavailable: %s", exc)

    def _disable_high_res_timer(self) -> None:
        if self._timer_active:
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception as exc:
                logger.debug("timeEndPeriod(1) unavailable: %s", exc)
            finally:
                self._timer_active = False

    def click_at(self, x: int, y: int, times: int = 1) -> None:
        backend = self._require_backend()

        if self.focus_watchdog_enabled:
            try:
                from mvp.bot.window_finder import force_foreground, is_foreground

                if not is_foreground(self.process_name):
                    force_foreground(self.process_name)
                    time.sleep(0.04)
            except Exception:
                logger.debug("click_at force_foreground failed", exc_info=True)

        with self._clicks_lock:
            self.total_clicks += times
        for i in range(times):
            tx = int(x)
            ty = int(y)

            self._move_bezier_to(tx, ty)
            time.sleep(random.uniform(0.005, 0.015))

            if logger.isEnabledFor(DEBUG):
                logger.debug("%s DOWN @(%d,%d) click %d/%d", _ts(), tx, ty, i + 1, times)
            backend.mouse_down_left()
            time.sleep(self._hold_delay_s())
            if logger.isEnabledFor(DEBUG):
                logger.debug("%s UP   @(%d,%d) click %d/%d", _ts(), tx, ty, i + 1, times)
            backend.mouse_up_left()

            if i < times - 1:
                delay = self._gaussian_delay() / 1000.0
                time.sleep(delay)

    def spam_click(
        self,
        x: int,
        y: int,
        count: int,
        deadline: float | None = None,
        clicks_per_sec: int | None = None,
        direct_first: bool = False,
    ) -> int:
        backend = self._require_backend()
        self._abort_event.clear()
        self._focus_refocus_warned = False
        self._focus_refocus_pending = False
        self._focus_refocus_done = False
        self._last_refocus_time = 0.0
        self._last_focus_check = 0.0

        begin_session = getattr(backend, "begin_spam_session", None)
        if begin_session is not None:
            begin_session()
        try:
            return self._spam_click_inner(
                backend, x, y, count, deadline, clicks_per_sec, direct_first
            )
        finally:
            end_session = getattr(backend, "end_spam_session", None)
            if end_session is not None:
                end_session()

    def _spam_click_inner(
        self,
        backend,
        x: int,
        y: int,
        count: int,
        deadline: float | None,
        clicks_per_sec: int | None,
        direct_first: bool,
    ) -> int:
        delivered = 0
        curr_x, curr_y = int(x), int(y)
        ox, oy = self._noise_offset()
        tx = int(curr_x + ox)
        ty = int(curr_y + oy)
        hold_s = self._hold_delay_s()
        is_mocked = getattr(time.sleep, "__name__", "") != "sleep"

        if is_mocked:
            if direct_first:
                backend.spam_move(tx, ty)
                time.sleep(0.025)
            for i in range(count):
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                if self._abort_event.is_set():
                    break
                if i == 0 and not direct_first:
                    self._move_bezier_to(tx, ty)

                self._apply_pending_refocus()

                try:
                    backend.spam_down(tx, ty)
                    precise_sleep(hold_s)
                    backend.spam_up(tx, ty)
                    delivered += 1
                    with self._clicks_lock:
                        self.total_clicks += 1
                except ClickerError as exc:
                    logger.debug("spam_click: transient SendInput error at click %d: %s", delivered + 1, exc)

                if self._should_check_focus():
                    self._check_focus()

                if i < count - 1 and (deadline is None or time.perf_counter() < deadline):
                    delay = self._cycle_delay_s(clicks_per_sec)
                    if deadline is not None:
                        delay = min(delay, max(0.0, deadline - time.perf_counter()))
                    half_1 = 0 if (i == 0 and direct_first) else delay * 0.4
                    half_2 = delay - half_1
                    if half_1 > 0:
                        precise_sleep(half_1)
                    ox, oy = self._noise_offset()
                    tx = int(x + ox)
                    ty = int(y + oy)
                    backend.spam_move(tx, ty)
                    if half_2 > 0:
                        precise_sleep(half_2)
            return delivered



        if not direct_first:
            self._move_bezier_to(tx, ty)
        else:
            backend.spam_move(tx, ty)
            time.sleep(0.025)

        t_spam_start = time.perf_counter()
        t_curr_down = t_spam_start
        base_cps = self._target_cps(clicks_per_sec)
        base_period = 1.0 / base_cps

        for i in range(count):
            if deadline is not None and time.perf_counter() >= deadline:
                break
            if self._abort_event.is_set():
                break

            self._apply_pending_refocus()

            now_before_down = time.perf_counter()
            if t_curr_down < now_before_down:
                t_curr_down = now_before_down

            precise_sleep_until(t_curr_down)

            try:
                backend.spam_down(tx, ty)
                t_down_actual = time.perf_counter()

                t_up = t_down_actual + hold_s
                precise_sleep_until(t_up)

                backend.spam_up(tx, ty)
                delivered += 1
                with self._clicks_lock:
                    self.total_clicks += 1
            except ClickerError as exc:
                logger.debug("spam_click: transient SendInput error at click %d: %s", delivered + 1, exc)

            if self._should_check_focus():
                self._check_focus()

            if i < count - 1 and (deadline is None or time.perf_counter() < deadline):
                jitter = (
                    random.uniform(-self.click_jitter_ms / 1000, self.click_jitter_ms / 1000)
                    if self.click_jitter_ms > 0
                    else 0.0
                )
                period = base_period + jitter
                if self._input_fps_mode == "60":
                    period = max(0.026, period)

                t_next_down = t_curr_down + period
                now_after_up = time.perf_counter()
                min_up_time = MIN_UP_GAP_HEADROOM_S if self._input_fps_mode == "60" else 0.002
                if t_next_down < now_after_up + min_up_time:
                    t_up = now_after_up
                    t_next_down = now_after_up + min_up_time

                # AGENTS.md Rule 2: 40% / 60% pause split.
                # Move happens strictly mid-UP while button is 100% released (state=0).
                t_move = t_up + (t_next_down - t_up) * 0.4
                precise_sleep_until(t_move)

                ox, oy = self._noise_offset()
                tx = int(x + ox)
                ty = int(y + oy)
                backend.spam_move(tx, ty)

                t_curr_down = t_next_down



        t_elapsed = time.perf_counter() - t_spam_start
        actual_cps = delivered / t_elapsed if t_elapsed > 0 else 0.0
        logger.debug(
            "spam_click completed: %d/%d delivered in %.3fs (%.1f CPS)",
            delivered,
            count,
            t_elapsed,
            actual_cps,
        )
        return delivered

    def _apply_pending_refocus(self) -> None:
        """Re-acquire focus at most once per spam run, never between down/up.

        The refocus is deferred out of the click loop (see _check_focus): when a
        focus loss is detected the pending flag is set, and it is consumed here at
        the very start of an iteration — before spam_down but safely outside any
        down/up pair.
        """
        if not self._focus_refocus_pending or self._focus_refocus_done:
            return
        self._focus_refocus_done = True
        self._focus_refocus_pending = False
        try:
            from mvp.bot.window_finder import force_foreground

            force_foreground(self.process_name)
        except Exception as exc:
            logger.debug("Focus re-acquisition failed: %s", exc)

    def scroll_window(
        self,
        hwnd: int,
        screen_x: int,
        screen_y: int,
        direction: str = "down",
        ticks: int = 1,
    ) -> bool:
        if not hwnd:
            return False
        if direction not in ("up", "down"):
            return False
        WM_MOUSEWHEEL = 0x020A
        WHEEL_DELTA = 120
        delta = -WHEEL_DELTA if direction == "down" else WHEEL_DELTA
        w_param = (delta & 0xFFFF) << 16
        l_param = ((int(screen_y) & 0xFFFF) << 16) | (int(screen_x) & 0xFFFF)
        try:
            for _ in range(max(1, int(ticks))):
                ctypes.windll.user32.PostMessageW(hwnd, WM_MOUSEWHEEL, w_param, l_param)
            return True
        except Exception as exc:
            logger.debug("scroll_window PostMessageW failed: %s", exc)
            return False

    def scroll_at(
        self,
        x: int,
        y: int,
        direction: str = "up",
        ticks: int = 1,
        interval_s: float = 0.0,
        restore_cursor: bool = False,
    ) -> None:
        backend = self._require_backend()
        if direction not in ("up", "down"):
            raise ClickerError(f"Invalid scroll direction: {direction!r} (expected 'up' or 'down')")

        try:
            from mvp.bot.window_finder import force_foreground

            force_foreground(self.process_name)
        except Exception:
            logger.debug("scroll_at force_foreground failed", exc_info=True)

        orig_x, orig_y = self._get_cursor_pos() if restore_cursor else (0, 0)

        if restore_cursor:
            backend.move_to(int(x), int(y))
            time.sleep(0.008)
        else:
            self._move_bezier_to(int(x), int(y))
            time.sleep(random.uniform(0.04, 0.06))

        for _ in range(max(1, int(ticks))):
            backend.scroll(direction)
            if interval_s > 0:
                time.sleep(float(interval_s))

        if restore_cursor:
            time.sleep(0.008)
            backend.move_to(orig_x, orig_y)

    def _get_cursor_pos(self) -> tuple[int, int]:
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    def _move_bezier_to(self, target_x: int, target_y: int) -> None:
        backend = self._require_backend()

        start_x, start_y = self._get_cursor_pos()

        mid_x = (start_x + target_x) / 2
        mid_y = (start_y + target_y) / 2
        dist = math.hypot(target_x - start_x, target_y - start_y)
        offset = (
            min(random.randint(50, 150), int(dist * 0.25)) if dist > 0 else random.randint(10, 50)
        )

        if dist > 0:
            dx = (target_y - start_y) / dist
            dy = (start_x - target_x) / dist
            if random.random() < 0.5:
                dx, dy = -dx, -dy
            control_x = int(mid_x + dx * offset)
            control_y = int(mid_y + dy * offset)
        else:
            control_x = int(mid_x + random.randint(-offset, offset))
            control_y = int(mid_y + random.randint(-offset, offset))

        n_points = random.randint(15, 25)
        for i in range(n_points + 1):
            t = i / n_points
            inv_t = 1 - t
            bx = int(inv_t * inv_t * start_x + 2 * inv_t * t * control_x + t * t * target_x)
            by = int(inv_t * inv_t * start_y + 2 * inv_t * t * control_y + t * t * target_y)
            backend.move_to(bx, by)
            time.sleep(random.uniform(0.001, 0.003))

    def _gaussian_delay(self) -> float:
        mu = (self.min_delay_ms + self.max_delay_ms) / 2
        sigma = (self.max_delay_ms - self.min_delay_ms) / 4
        delay = random.gauss(mu, sigma)
        return max(self.min_delay_ms, min(delay, self.max_delay_ms))

    def _noise_offset(self) -> tuple[float, float]:
        self._noise_sign *= -1
        # Consecutive clicks alternate sign on BOTH axes, so the distance between two
        # clicks is 2 * sqrt(2) * amp (~2.83 * amp). Unity's ClickDetector merges clicks
        # closer than ~5 px (within 300 ms) into a single gesture, so amp must stay strictly
        # above 1.77 px (we enforce min_safe_amp = 1.80 px). This gives Euclidean separation
        # >= 5.09 px, completely preventing double-click suppression while keeping cursor jitter minimal.
        min_safe_amp = 1.80
        max_amp = max(min_safe_amp + 0.05, self.spam_noise_px)
        min_amp = max(min_safe_amp, max_amp - 0.4)
        amp = random.uniform(min_amp, max_amp)
        off = self._noise_sign * amp
        return off, off

    def _hold_delay_s(self) -> float:
        if self._input_fps_mode == "60":
            return self._dig_hold_ms_60fps / 1000
        return self._dig_hold_ms_200fps / 1000 + random.uniform(-0.0003, 0.0003)

    def _should_check_focus(self) -> bool:
        if not self.focus_watchdog_enabled:
            return False
        now = time.monotonic()
        if now - self._last_focus_check >= self.focus_check_interval_s:
            self._last_focus_check = now
            return True
        return False

    def _check_focus(self) -> None:
        if not self.focus_watchdog_enabled:
            return
        try:
            from mvp.bot import window_finder

            if window_finder.is_foreground(self.process_name):
                return
            # Defer the actual re-focus out of the click loop. The pending flag is
            # consumed by _apply_pending_refocus at the start of the next iteration,
            # so SetForegroundWindow never happens between a down/up pair.
            self._focus_refocus_pending = True
            if not self._focus_refocus_warned:
                logger.warning(
                    "Game window lost focus — forcing foreground again (%s). "
                    "Further losses in this series will not be logged.",
                    self.process_name,
                )
                self._focus_refocus_warned = True
        except Exception as exc:
            logger.debug("Focus check failed: %s", exc)

    def _target_cps(self, clicks_per_sec: int | None) -> float:
        was_explicit = bool(clicks_per_sec and clicks_per_sec > 0)
        cps = float(clicks_per_sec) if was_explicit else 30.0
        if self._input_fps_mode == "60":
            capped = min(cps, self._max_cps_60fps, MAX_CPS_60FPS_SAFE)
            if was_explicit and capped < cps:
                logger.warning(
                    "Configured %.1f CPS exceeds the 60 FPS safe cap (%d); capping to %.1f CPS",
                    cps,
                    MAX_CPS_60FPS_SAFE,
                    capped,
                )
            cps = capped
        return cps

    def _cycle_delay_s(self, clicks_per_sec: int | None) -> float:
        hold = self._hold_delay_s()
        base = (1.0 / self._target_cps(clicks_per_sec)) - hold
        delay = max(0.003, base)
        if self.click_jitter_ms > 0:
            delay += random.uniform(-self.click_jitter_ms / 1000, self.click_jitter_ms / 1000)
        if self._input_fps_mode == "60":
            min_period = 0.026
            if hold + delay < min_period:
                delay = max(0.003, min_period - hold)
        return max(0.003, delay)

    @property
    def is_initialized(self) -> bool:
        return self._backend is not None and self._backend.is_initialized

    def get_total_clicks(self) -> int:
        with self._clicks_lock:
            return self.total_clicks

    def abort_spam(self) -> None:
        self._abort_event.set()

    def shutdown(self) -> None:
        self.abort_spam()
        if self._backend is not None:
            self._backend.shutdown()
        self._backend = None
        self._disable_high_res_timer()
        logger.info("Clicker shutdown")