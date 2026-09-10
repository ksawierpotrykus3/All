from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from mvp.bot.arrow_detector import ROI_CHAT_ARROW, ChatArrowDetector
from mvp.bot.exceptions import ClickerError, MacroStepError, OCRError
from mvp.bot.modal_detector import find_march_confirm_modal

logger = logging.getLogger(__name__)

# AGENTS.md §9: timer jumps |delta| > 2.0s are skipped (OCR misreads, refunds, heli exit).
# Both _handle_watch_timer and calculate_avg_delta must use this constant.
_JUMP_DETECTION_THRESHOLD_S = 2.0


class StepType(Enum):
    WAIT_FOR_CHAT = "wait_for_chat"
    CLICK = "click"
    WAIT = "wait"
    WATCH_TIMER = "watch_timer"
    SCROLL_ZOOM = "scroll_zoom"
    SCROLL_LISTEN_CHAT = "scroll_listen_chat"


@dataclass
class MacroStep:
    type: StepType = StepType.WAIT
    label: str = ""
    roi_pct: dict | None = None
    threshold: float = 0.85
    timeout_s: float = 30.0
    check_interval_s: float = 0.5
    x: int | str | None = None
    y: int | str | None = None
    click_x: int | None = None
    click_y: int | None = None
    seconds: float | None = None
    idle_check_interval_s: float = 10.0
    fast_check_interval_s: float = 0.2
    fast_threshold_s: int = 300
    spam_threshold_s: int = 5
    spam_duration_s: float = 7.0
    spam_clicks_per_sec: int = 30
    hysteresis_confirmations: int = 1
    t0_lead_time_s: float = 0.3
    scroll_direction: str = "up"
    scroll_ticks: int = 1
    scroll_interval_s: float = 0.08
    chat_bar_roi: dict | None = None
    alliance_tab_roi: dict | None = None
    scroll_center_roi: dict | None = None
    scroll_settle_s: float = 0.2
    post_detect_settle_s: float = 0.3
    post_detect_reconfirm: bool = True
    scan_between_scroll: int = 1
    post_click_debounce: bool = False
    restore_cursor: bool = True
    scroll_enabled: bool = True
    arrow_roi: dict | None = None
    arrow_threshold: float = 0.88
    arrow_click_delay_s: float = 0.35
    arrow_enabled: bool = True
    details_roi: dict | None = None

    details_close_roi: dict | None = None
    details_recovery_enabled: bool = False
    details_dismiss_delay_s: float = 5.0
    verify_alliance_open: bool = False
    max_open_retries: int = 3
    verify_chat_exit: bool = False
    chat_exit_retry_step: int = 1
    exit_timeout_s: float = 2.5
    direct_click: bool = False
    check_march_modal: bool = False
    ocr_dynamic_interval_config: dict[str, float] | None = None

    def get_ocr_interval_config(self) -> dict[str, float]:
        """Helper: Get OCR interval config with defaults."""
        if self.ocr_dynamic_interval_config is None:
            return {
                "initial_interval": 1.0,
                "accel_threshold": 10.0,
                "min_interval": 0.2,
                "cpu_pause_window": 1.0,
            }
        return self.ocr_dynamic_interval_config


def should_trigger_spam(
    ocr_timer_value: int | None,
    estimated_t0_mono: float | None,
    confirmed_count: int,
    hysteresis_confirmations: int,
    spam_threshold: int,
    t0_lead_time_s: float = 0.3,
) -> bool:
    """
    Determine if spam should be triggered NOW.

    Priority order (first match wins):
    1. Monotonic T0 estimate reached (current_time >= estimated_t0_mono - t0_lead_time_s)
    2. OCR confirms low timer (timer <= spam_threshold) AND hysteresis satisfied → fallback
    3. Otherwise: NOT yet

    This prioritization ensures:
    - Monotonic T0 estimate with lead_time provides proactive trigger before exact T0
    - OCR + hysteresis provide fallback if T0 estimate not yet locked (robustness)

    Args:
        ocr_timer_value: Current OCR-read timer value (or None if OCR failed)
        estimated_t0_mono: Extrapolated T0 time (from monotonic), or None
        confirmed_count: Number of OCR confirmations that timer <= spam_threshold
        hysteresis_confirmations: Required number of confirmations (e.g., 2)
        spam_threshold: Timer value threshold for "low timer" (e.g., 5s)
        t0_lead_time_s: Lead time before T0 to trigger spam (e.g., 0.3s before arrival)

    Returns:
        bool: True if spam should be triggered now, False otherwise
    """
    import time

    # PRIORITY 1: Monotonic T0 estimate with lead_time
    if estimated_t0_mono is not None:
        now = time.monotonic()
        if now >= (estimated_t0_mono - t0_lead_time_s):
            return True

    # PRIORITY 2: OCR confirms low timer (timer <= spam_threshold) AND hysteresis satisfied
    return (
        ocr_timer_value is not None
        and ocr_timer_value <= spam_threshold
        and confirmed_count >= hysteresis_confirmations
    )


def calculate_avg_delta(timer_history: list) -> float:
    """
    Calculate average time-delta between consecutive timer readings.

    Used to extrapolate T0 (when will timer reach 0).

    Logic:
    - Filter valid entries (skip None values and jumps |delta|>2.0s)
    - Calculate deltas between consecutive readings: [(t2-t1), (t3-t2), ...]
    - Return average of valid deltas
    - If no valid deltas, return 1.0 (safe default: 1 second per reading)

    Example:
    - History: [100s@t=0, 99s@t=1, 98s@t=2] → deltas=[1.0, 1.0] → avg=1.0
    - History: [100s, 98.5s, 97.1s] @ intervals [1.0s, 1.5s] → avg≈1.25s
    - History: [100s, 95s] (jump) → skip jump, avg=default 1.0s

    Args:
        timer_history: List of dicts: [{"value": timer_value, "time": timestamp}, ...]
                       Last 3-5 entries typically used for averaging

    Returns:
        Average time-delta (seconds per 1 second timer drop), or 1.0 if cannot compute
    """
    if not timer_history or len(timer_history) < 2:
        return 1.0

    deltas = []

    # Calculate time deltas between consecutive readings
    for i in range(len(timer_history) - 1):
        curr_val = timer_history[i].get("value")
        next_val = timer_history[i + 1].get("value")
        curr_time = timer_history[i].get("time")
        next_time = timer_history[i + 1].get("time")

        # Skip entries with None values
        if curr_val is None or next_val is None or curr_time is None or next_time is None:
            continue

        # Skip jumps: timer_delta > _JUMP_DETECTION_THRESHOLD_S indicates anomaly or refund event
        # Note: We filter aggressively to skip both OCR misreads and legitimate refunds (player pickup).
        # This is safe because if a jump occurs during hysteresis phase, confirmed_count resets anyway (line ~1343).
        # If a jump occurs after T0 is locked, the estimate is frozen and won't be recalculated.
        timer_delta = curr_val - next_val  # Should be positive (countdown)
        if timer_delta <= 0 or timer_delta > _JUMP_DETECTION_THRESHOLD_S:  # Jump detected
            continue

        time_delta = next_time - curr_time
        if time_delta <= 0:  # Invalid time order
            continue

        # Delta = seconds per 1-second timer drop
        delta = time_delta / timer_delta
        deltas.append(delta)

    # Return average or safe default
    if not deltas:
        return 1.0  # Safe default: 1 second per timer second

    return sum(deltas) / len(deltas)


def calculate_adaptive_interval(
    time_remaining: float,
    initial_interval: float,
    accel_threshold: float,
    min_interval: float,
) -> float:
    """
    Calculate adaptive OCR interval based on remaining time.

    Logic:
    - If time_remaining >= accel_threshold: return initial_interval (1.0s)
    - If time_remaining < accel_threshold: return linear interpolation toward min_interval
    - Formula: min_interval + (initial_interval - min_interval) * (time_remaining / accel_threshold)
    - Clamped between min_interval and initial_interval

    Example:
    - time_remaining=300s, accel_threshold=10s: returns 1.0s (initial)
    - time_remaining=5s, accel_threshold=10s: returns ~0.6s (interpolated)
    - time_remaining=0s: returns 0.2s (min)

    Args:
        time_remaining: Seconds from now to estimated T0
        initial_interval: Starting interval (e.g., 1.0s)
        accel_threshold: Seconds remaining to start acceleration (e.g., 10.0s)
        min_interval: Minimum interval floor (e.g., 0.2s)

    Returns:
        Adaptive interval in seconds, clamped to [min_interval, initial_interval]
    """
    # Handle invalid accel_threshold first
    if accel_threshold <= 0:
        return min_interval

    if time_remaining >= accel_threshold:
        return initial_interval

    # Linear interpolation: as time_remaining → 0, interval → min_interval
    interpolated = min_interval + (initial_interval - min_interval) * (
        time_remaining / accel_threshold
    )

    # Clamp to valid range
    return max(min_interval, min(initial_interval, interpolated))


@dataclass
class Macro:
    name: str
    version: int = 1
    steps: list[MacroStep] = field(default_factory=list)


@dataclass
class MacroResult:
    success: bool
    completed_steps: int
    total_steps: int
    error: str | None = None


class MacroEngine:
    def __init__(
        self,
        clicker,
        chat_ocr,
        timer_ocr,
        capture,
        window_context_refresher=None,
        arrow_detector=None,
        process_name: str = "Survival.exe",
        checkpoint_path: Path | None = None,
        config=None,
    ) -> None:
        self.clicker = clicker
        self.chat_ocr = chat_ocr
        self.timer_ocr = timer_ocr
        self.capture = capture
        self.arrow_detector = arrow_detector or ChatArrowDetector()
        self.process_name = process_name
        self.window_context_refresher = window_context_refresher
        self.step_callback = None
        self.config = config

        self.memory: dict[str, object] = {}
        self._step_results: dict[int, dict] = {}
        self._stop_requested = threading.Event()
        self._current_step_index: int = -1

        self._spam_lock = threading.Lock()
        self._spam_in_flight = False
        # Single lock guarding ALL GUI-facing stats (counters, timer value, and the
        # current step index). Lock ordering: only this lock is used for stats; it is
        # never acquired while holding _spam_lock or _checkpoint_lock, so there is no
        # nesting and therefore no deadlock risk.
        self._stats_lock = threading.Lock()

        self.stats_alerts = 0
        self.stats_errors = 0
        self.stats_start_time: float | None = None
        self.stats_end_time: float | None = None
        self.last_timer_value: int | None = None
        self.total_steps = 0

        self.stale_jump_threshold_s: float = 30.0

        self._spam_target_x: int | None = None
        self._spam_target_y: int | None = None
        self._spam_duration_s: float | None = None
        self._spam_cps: int | None = None

        self._current_macro: Macro | None = None
        self._current_window = None

        self.checkpoint_path: Path | None = checkpoint_path
        self._checkpoint_lock = threading.Lock()
        self._last_saved_checkpoint_state: tuple | None = None

        self.on_spam_begin = None
        self.on_spam_end = None
        self._spam_focus_warned = False

    def _ensure_foreground(self) -> bool:
        """Ensure the game window is foreground; skip the costly refocus if already.

        Returns True if the window is (or was successfully brought to) foreground.
        If the game window does not even exist (e.g. unit tests, transient startup),
        there is nothing to focus-block, so we proceed rather than abort the spam.
        """
        from mvp.bot.window_finder import (
            check_uipi_elevation_mismatch,
            find_game_window,
            force_foreground,
            is_foreground,
        )

        if is_foreground(self.process_name):
            return True

        # Foreground acquisition can fail transiently (Windows foreground-lock
        # contention, a busy UI thread). Retry a few times with a short, CPU-yielding
        # backoff before declaring failure.
        for attempt in range(3):
            if force_foreground(self.process_name):
                time.sleep(0.035)
                return True
            time.sleep(0.05 + 0.05 * attempt)

        # If the game window does not exist at all (headless/test), there is nothing
        # to focus-block — proceed rather than abort.
        try:
            if find_game_window(self.process_name) is None:
                return True
        except Exception:
            pass

        # Classify the failure: a UIPI elevation mismatch is actionable and common,
        # and warrants a distinct diagnostic instead of the generic message.
        try:
            if check_uipi_elevation_mismatch(self.process_name):
                if not self._spam_focus_warned:
                    logger.warning(
                        "Could not bring game window to foreground (%s): the game appears to "
                        "run with higher integrity (as Administrator) than the bot. Run the bot "
                        "as Administrator to match the game's integrity level — aborting spam.",
                        self.process_name,
                    )
                    self._spam_focus_warned = True
                return False
        except Exception:
            logger.debug("UIPI check failed during foreground fallback", exc_info=True)

        if not self._spam_focus_warned:
            logger.warning(
                "Could not bring game window to foreground (%s) — aborting spam.",
                self.process_name,
            )
            self._spam_focus_warned = True
        return False

    def _call_spam_hooks(self, hook_name: str) -> None:
        hook = getattr(self, hook_name, None)
        if hook is not None:
            try:
                hook()
            except Exception:
                logger.debug("%s failed", hook_name, exc_info=True)

    def trigger_spam(self) -> None:
        if self.clicker is None:
            return
        x = self._spam_target_x
        y = self._spam_target_y
        if x is None or y is None:
            target = self._resolve_spam_target()
            if target is None:
                if self._current_window is None:
                    logger.info("trigger_spam: no game window — nothing to click")
                else:
                    logger.info(
                        "trigger_spam: no click target available (macro not in watch_timer phase)"
                    )
                return
            x, y = target
        duration, cps = self._resolve_spam_params()
        if not self._try_begin_spam():
            logger.info("trigger_spam: another spam already in flight — skip")
            return
        logger.info("trigger_spam: clicking @(%d,%d) for %.1fs @%d/s", x, y, duration, cps)
        threading.Thread(
            target=self._run_hotkey_spam,
            args=(x, y, int(duration * cps), duration, cps),
            daemon=True,
        ).start()

    def _run_hotkey_spam(self, x: int, y: int, count: int, duration: float, cps: int) -> None:
        try:
            if not self._ensure_foreground():
                return
            self._call_spam_hooks("on_spam_begin")
            try:
                self.clicker.spam_click(
                    x,
                    y,
                    count=count,
                    deadline=time.perf_counter() + duration,
                    clicks_per_sec=cps,
                    direct_first=True,
                )
            finally:
                self._call_spam_hooks("on_spam_end")
        except Exception as exc:
            with self._stats_lock:
                self.stats_errors += 1
            logger.error("hotkey spam failed: %s", exc, exc_info=True)
        finally:
            self._end_spam()

    def _try_begin_spam(self) -> bool:
        with self._spam_lock:
            if self._spam_in_flight:
                return False
            self._spam_in_flight = True
            return True

    def _end_spam(self) -> None:
        with self._spam_lock:
            self._spam_in_flight = False

    def _resolve_spam_target(self) -> tuple[int, int] | None:
        from mvp.bot.coordinates import GamePercent

        macro = self._current_macro
        window = self._get_fresh_window(self._current_window)
        if macro is None or window is None:
            return None
        for step in macro.steps:
            if step.type != StepType.WATCH_TIMER:
                continue
            if step.click_x is not None and step.click_y is not None:
                try:
                    cx = float(self._interpolate(step.click_x))
                    cy = float(self._interpolate(step.click_y))
                except (TypeError, ValueError):
                    cx, cy = 50.0, 50.0
                coord = window.to_screen(GamePercent(cx, cy))
                return (coord.x, coord.y)
            if step.roi_pct is not None:
                roi = _roi_from_dict(step.roi_pct)
                coord = window.roi_center_to_screen(roi)
                return (coord.x, coord.y)
        return None

    def _resolve_spam_params(self) -> tuple[float, int]:
        if self._spam_duration_s is not None and self._spam_cps is not None:
            return self._spam_duration_s, self._spam_cps

        macro = self._current_macro
        default_cps = getattr(self.config, "spam_clicks_per_sec", 30) if hasattr(self, "config") and self.config else 38
        default_duration = getattr(self.config, "spam_duration_s", 3.0) if hasattr(self, "config") and self.config else 3.0
        if macro is not None:
            for step in macro.steps:
                if step.type != StepType.WATCH_TIMER:
                    continue
                duration = step.spam_duration_s or default_duration
                cps = int(step.spam_clicks_per_sec or default_cps)
                return duration, cps
        return default_duration, default_cps

    def stop(self) -> None:
        self._stop_requested.set()
        abort_clicker = getattr(self.clicker, "abort_spam", None)
        if abort_clicker is not None:
            try:
                abort_clicker()
            except Exception:
                logger.debug("clicker.abort_spam failed", exc_info=True)

    def reset(self) -> None:
        self.memory.clear()
        self._step_results.clear()
        self._stop_requested.clear()
        with self._stats_lock:
            self._current_step_index = -1
            self.stats_alerts = 0
            self.stats_errors = 0
            self.stats_start_time = None
            self.stats_end_time = None
            self.last_timer_value = None
            self.total_steps = 0
        self._spam_focus_warned = False

    def reset_session_stats(self) -> None:
        self.reset()

    @property
    def current_step_index(self) -> int:
        with self._stats_lock:
            return self._current_step_index

    def stats_snapshot(self) -> dict:
        """Return a consistent snapshot of counters for GUI display."""
        with self._stats_lock:
            return {
                "total_steps": self.total_steps,
                "current_step_index": self._current_step_index,
                "last_timer_value": self.last_timer_value,
                "stats_alerts": self.stats_alerts,
                "stats_errors": self.stats_errors,
                "stats_start_time": self.stats_start_time,
                "stats_end_time": self.stats_end_time,
            }

    def run(self, macro: Macro, window) -> MacroResult:
        self.reset()
        self.memory.pop("step_1_click_x", None)
        self.memory.pop("step_1_click_y", None)
        self._current_macro = macro
        self._current_window = window
        with self._stats_lock:
            self.stats_start_time = time.monotonic()
            self.stats_end_time = None
            self.total_steps = len(macro.steps)
        logger.info("Macro start: %s (%d steps)", macro.name, len(macro.steps))
        if macro.steps:
            self._emit("phase_transition", 0, macro.steps[0], phase="init")

        step_idx = 0
        while step_idx < len(macro.steps):
            if self._stop_requested.is_set():
                with self._stats_lock:
                    self.stats_end_time = time.monotonic()
                return MacroResult(
                    success=False,
                    completed_steps=step_idx,
                    total_steps=len(macro.steps),
                    error="Stopped",
                )

            i = step_idx + 1
            step = macro.steps[step_idx]

            window = self._get_fresh_window(window)

            with self._stats_lock:
                self._current_step_index = step_idx

            self._emit("running", i, step)
            try:
                self.dispatch_step(i, step, window)

                if step.verify_chat_exit and not self._stop_requested.is_set():
                    timeout = step.exit_timeout_s if step.exit_timeout_s > 0 else 2.5
                    exit_deadline = time.monotonic() + timeout
                    chat_closed = False
                    while time.monotonic() < exit_deadline and not self._stop_requested.is_set():
                        if not self._is_alliance_chat_open(window, step.alliance_tab_roi):
                            chat_closed = True
                            break
                        if self._stop_requested.wait(0.15):
                            break

                    if not chat_closed and not self._stop_requested.is_set():
                        retry_step = max(1, step.chat_exit_retry_step)
                        logger.warning(
                            "Step %d (%s): Chat still open after click (timeout %.1fs); retrying from step %d...",
                            i,
                            step.label,
                            timeout,
                            retry_step,
                        )
                        self.memory.pop("step_1_click_x", None)
                        self.memory.pop("step_1_click_y", None)
                        step_idx = retry_step - 1
                        continue

                self._save_checkpoint(i)
                self._emit("success", i, step)
                step_idx += 1
            except (ClickerError, OCRError, MacroStepError) as exc:
                with self._stats_lock:
                    self.stats_errors += 1
                    self.stats_end_time = time.monotonic()
                logger.error(
                    "Step %d (%s) failed: %s",
                    i,
                    step.label,
                    exc,
                    exc_info=True,
                )
                self._emit("error", i, step, error=str(exc))
                return MacroResult(
                    success=False,
                    completed_steps=step_idx,
                    total_steps=len(macro.steps),
                    error=str(exc),
                )

        self._clear_checkpoint()

        with self._stats_lock:
            self.stats_end_time = time.monotonic()
        return MacroResult(
            success=True,
            completed_steps=len(macro.steps),
            total_steps=len(macro.steps),
        )

    def _save_checkpoint(self, completed_step: int) -> None:
        if self.checkpoint_path is None:
            return
        current_state_key = (
            completed_step,
            self.total_steps,
            self.last_timer_value,
            self.memory.get("step_1_click_x"),
            self.memory.get("step_1_click_y"),
        )
        with self._checkpoint_lock:
            if self._last_saved_checkpoint_state == current_state_key:
                return
            try:
                state = {
                    "completed_steps": completed_step,
                    "total_steps": self.total_steps,
                    "last_timer_value": self.last_timer_value,
                    "step_1_click_x": self.memory.get("step_1_click_x"),
                    "step_1_click_y": self.memory.get("step_1_click_y"),
                    "ts": time.time(),
                }
                self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
                tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.checkpoint_path)
                self._last_saved_checkpoint_state = current_state_key
            except (OSError, TypeError, ValueError):
                logger.debug("checkpoint save failed", exc_info=True)

    def _clear_checkpoint(self) -> None:
        self._last_saved_checkpoint_state = None
        if self.checkpoint_path is None:
            return
        with contextlib.suppress(OSError):
            self.checkpoint_path.unlink(missing_ok=True)

    def load_checkpoint(self) -> dict | None:
        if self.checkpoint_path is None or not self.checkpoint_path.exists():
            return None
        try:
            return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def _emit(self, event: str, step_num: int, step: MacroStep, **kwargs) -> None:
        if self.step_callback is not None:
            try:
                self.step_callback(event, step_num, step, **kwargs)
            except Exception:
                logger.debug("step_callback failed for %s", event, exc_info=True)

    def dispatch_step(self, step_num: int, step: MacroStep, window) -> None:
        window = self._get_fresh_window(window)
        if step.type == StepType.WAIT:
            self._handle_wait(step)
        elif step.type == StepType.CLICK:
            self._handle_click(step, window)
        elif step.type == StepType.WAIT_FOR_CHAT:
            self._handle_wait_for_chat(step_num, step, window)
        elif step.type == StepType.WATCH_TIMER:
            self._handle_watch_timer(step_num, step, window)
        elif step.type == StepType.SCROLL_ZOOM:
            self._handle_scroll_zoom(step, window)
        elif step.type == StepType.SCROLL_LISTEN_CHAT:
            self._handle_scroll_listen_chat(step_num, step, window)
        else:
            raise MacroStepError(step.label, f"Unsupported step type: {step.type}")

    def _handle_wait(self, step: MacroStep) -> None:
        self._stop_requested.wait(step.seconds or 0.0)

    def _handle_click(self, step: MacroStep, window) -> None:
        if self.clicker is None:
            raise ClickerError("Clicker not configured")

        window = self._get_fresh_window(window)
        raw_x = self._interpolate(step.x)
        raw_y = self._interpolate(step.y)
        x = self._resolve_value(raw_x)
        y = self._resolve_value(raw_y)

        if step.verify_chat_exit and self.memory.pop("step_1_direct_clicked", False):
            logger.info("click: step 1 already executed direct click — skipping redundant second click and verifying chat exit")
            return

        if step.roi_pct:
            roi = _roi_from_dict(step.roi_pct)
            center = window.roi_center_to_screen(roi)
            if x is None or y is None:
                self.clicker.click_at(center.x, center.y)
            else:
                self.clicker.click_at(center.x + int(float(x)), center.y + int(float(y)))
        else:
            if x is None or y is None:
                raise MacroStepError(
                    step.label, f"Cannot resolve click target: ({step.x}, {step.y})"
                )
            gp = _to_game_percent(x, y)
            coord = window.to_screen(gp)
            self.clicker.click_at(coord.x, coord.y)

        if step.check_march_modal and not self._stop_requested.wait(0.35):
            self._check_and_dismiss_march_modal(window)

    def _handle_scroll_zoom(self, step: MacroStep, window) -> None:
        if self.clicker is None or not hasattr(self.clicker, "scroll_at"):
            raise ClickerError("Clicker does not support wheel scrolling")
        if step.roi_pct is None:
            raise MacroStepError(step.label, "roi_pct is required")

        window = self._get_fresh_window(window)
        coord = window.roi_center_to_screen(_roi_from_dict(step.roi_pct))
        direction = step.scroll_direction or "up"
        if direction not in ("up", "down"):
            raise MacroStepError(
                step.label, f"invalid scroll_direction: {direction!r} (expected 'up' or 'down')"
            )
        logger.info(
            "scroll_zoom: scrolling %s x%d @(%d,%d) (interval=%.3fs)",
            direction,
            max(1, int(step.scroll_ticks or 1)),
            coord.x,
            coord.y,
            float(step.scroll_interval_s or 0.0),
        )
        self.clicker.scroll_at(
            coord.x,
            coord.y,
            direction=direction,
            ticks=max(1, int(step.scroll_ticks)),
            interval_s=max(0.0, float(step.scroll_interval_s or 0.0)),
        )

    def _check_and_click_chat_arrow(
        self,
        frame: np.ndarray,
        window,
        arrow_roi_pct: dict | None = None,
        threshold: float | None = None,
    ) -> bool:
        if self.arrow_detector is None or self.clicker is None:
            return False

        window = self._get_fresh_window(window)
        h, w = frame.shape[:2]
        roi_dict = arrow_roi_pct or ROI_CHAT_ARROW
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, right, bottom = window.roi_to_frame_pixels(_roi_from_dict(roi_dict), w, h)
        else:
            left, top, right, bottom = _roi_from_dict(roi_dict).to_pixels(w, h)

        found = self.arrow_detector.find_arrow(
            frame, roi_rect=(left, top, right, bottom), threshold=threshold
        )
        if found is not None:
            arrow_frame_x, arrow_frame_y, score = found
            if hasattr(window, "left") and hasattr(window, "top"):
                click_x = window.left + arrow_frame_x
                click_y = window.top + arrow_frame_y
            else:
                click_x, click_y = arrow_frame_x, arrow_frame_y

            logger.info(
                "Chat arrow detected (score=%.3f), clicking at (%d, %d)", score, click_x, click_y
            )
            self.clicker.click_at(click_x, click_y)
            return True
        return False

    def _check_and_dismiss_march_modal(
        self, window, frame: np.ndarray | None = None
    ) -> bool:
        """Sprawdza i zamyka modalne okno potwierdzenia długiego marszu ('Tips').

        Jeśli okno występuje: zaznacza checkbox 'Don't remind me again' oraz klika 'Confirm'.
        Jeśli okno nie występuje: natychmiast zwraca False (trwa ~2ms, zero fałszywych kliknięć).
        """
        if self.clicker is None:
            return False
        if frame is None:
            if self.capture is None:
                return False
            frame = self.capture.grab()
        if frame is None or frame.size == 0:
            return False

        coords = find_march_confirm_modal(frame)
        if coords is None:
            return False

        confirm_x, confirm_y, cb_x, cb_y = coords
        window = self._get_fresh_window(window)
        if hasattr(window, "left") and hasattr(window, "top"):
            click_confirm_x, click_confirm_y = window.left + confirm_x, window.top + confirm_y
            click_cb_x, click_cb_y = window.left + cb_x, window.top + cb_y
        else:
            click_confirm_x, click_confirm_y = confirm_x, confirm_y
            click_cb_x, click_cb_y = cb_x, cb_y

        logger.info(
            "Wykryto okno potwierdzenia marszu (Tips)! Zaznaczam checkbox (%d, %d) i klikam Confirm (%d, %d)",
            click_cb_x,
            click_cb_y,
            click_confirm_x,
            click_confirm_y,
        )
        self.clicker.click_at(click_cb_x, click_cb_y)
        self._stop_requested.wait(0.15)
        if not self._stop_requested.is_set():
            self.clicker.click_at(click_confirm_x, click_confirm_y)
            self._stop_requested.wait(0.35)
        return True

    def _is_alliance_chat_open(
        self, window, alliance_tab_roi: dict | None = None, frame: np.ndarray | None = None
    ) -> bool:
        if self.chat_ocr is None:
            return False
        if frame is None:
            if self.capture is None:
                return False
            frame = self.capture.grab()
            if frame is None:
                return False

        h, w = frame.shape[:2]
        roi_dict = alliance_tab_roi or {
            "left": 47.6,
            "top": 5.5,
            "right": 52.4,
            "bottom": 9.7,
            "anchor": "center",
        }
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, right, bottom = window.roi_to_frame_pixels(_roi_from_dict(roi_dict), w, h)
        else:
            left, top, right, bottom = _roi_from_dict(roi_dict).to_pixels(w, h)

        if right <= left or bottom <= top:
            return False
        cropped = frame[top:bottom, left:right]
        check_fn = getattr(self.chat_ocr, "is_alliance_chat_open", None)
        if check_fn is not None:
            return check_fn(cropped)
        return False

    def _is_chat_window_open(
        self, window, chat_tab_bar_roi: dict | None = None, frame: np.ndarray | None = None
    ) -> bool:
        if self.chat_ocr is None:
            return False
        if frame is None:
            if self.capture is None:
                return False
            frame = self.capture.grab()
            if frame is None:
                return False

        h, w = frame.shape[:2]
        roi_dict = chat_tab_bar_roi or {
            "left": 38.0,
            "top": 7.0,
            "right": 62.0,
            "bottom": 13.0,
            "anchor": "center",
        }
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, right, bottom = window.roi_to_frame_pixels(_roi_from_dict(roi_dict), w, h)
        else:
            left, top, right, bottom = _roi_from_dict(roi_dict).to_pixels(w, h)

        if right <= left or bottom <= top:
            return False
        cropped = frame[top:bottom, left:right]
        check_fn = getattr(self.chat_ocr, "is_chat_window_open", None)
        if check_fn is not None:
            return check_fn(cropped)
        return False

    def _is_details_dialog_open(self, window, details_roi_pct: dict | None = None) -> bool:
        if self.capture is None or self.chat_ocr is None:
            return False
        frame = self.capture.grab()
        if frame is None:
            return False
        h, w = frame.shape[:2]
        roi_dict = details_roi_pct or {
            "left": 44.0,
            "top": 16.0,
            "right": 56.0,
            "bottom": 21.5,
        }
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, right, bottom = window.roi_to_frame_pixels(_roi_from_dict(roi_dict), w, h)
        else:
            left, top, right, bottom = _roi_from_dict(roi_dict).to_pixels(w, h)

        if right <= left or bottom <= top:
            return False
        cropped = frame[top:bottom, left:right]
        check_fn = getattr(self.chat_ocr, "is_details_dialog_open", None)
        if check_fn is not None:
            return check_fn(cropped)
        return False

    def _handle_scroll_listen_chat(self, step_num: int, step: MacroStep, window) -> None:
        if self._stop_requested.is_set():
            self._step_results[step_num] = {"detected": False}
            return

        if self.clicker is None or self.chat_ocr is None or self.capture is None:
            raise OCRError("Clicker/ChatOCR/Capture not configured")
        if step.roi_pct is None or step.chat_bar_roi is None or step.alliance_tab_roi is None:
            raise MacroStepError(
                step.label,
                "roi_pct, chat_bar_roi and alliance_tab_roi are required for SCROLL_LISTEN_CHAT",
            )

        if "step_1_click_x" in self.memory and "step_1_click_y" in self.memory:
            logger.info(
                "scroll_listen_chat: skipping — memory already has coords (%s, %s)",
                self.memory["step_1_click_x"],
                self.memory["step_1_click_y"],
            )
            self._step_results[step_num] = {
                "detected": True,
                "fast_path": True,
                "click_x": self.memory["step_1_click_x"],
                "click_y": self.memory["step_1_click_y"],
                "debounce_clear": False,
            }
            return

        if self._stop_requested.is_set():
            self._step_results[step_num] = {"detected": False}
            return

        try:
            from mvp.bot.window_finder import force_foreground

            force_foreground(self.process_name)
        except Exception:
            logger.debug("scroll_listen_chat: force_foreground failed", exc_info=True)

        if self._stop_requested.wait(0.1):
            self._step_results[step_num] = {"detected": False}
            return

        if step.verify_alliance_open:
            max_retries = max(1, step.max_open_retries or 3)
            chat_ready = False
            for attempt in range(1, max_retries + 1):
                if self._is_alliance_chat_open(window, step.alliance_tab_roi):
                    chat_ready = True
                    break

                if (
                    step.details_recovery_enabled
                    and step.details_roi is not None
                    and self._is_details_dialog_open(window, step.details_roi)
                ):
                    logger.info(
                        "scroll_listen_chat: Details/Reward modal blocking screen — dismissing..."
                    )
                    close_roi = step.details_close_roi or step.details_roi
                    self._click_chat_roi(window, close_roi, "close blocking modal")
                    if self._stop_requested.wait(0.4):
                        self._step_results[step_num] = {"detected": False}
                        return

                if self._is_chat_window_open(window):
                    logger.info(
                        "scroll_listen_chat: Chat open on different tab (attempt %d/%d), switching to Alliance tab",
                        attempt,
                        max_retries,
                    )
                    self._click_chat_roi(window, step.alliance_tab_roi, step.label)
                    if self._stop_requested.wait(0.5):
                        self._step_results[step_num] = {"detected": False}
                        return
                else:
                    logger.info(
                        "scroll_listen_chat: Alliance chat not open (attempt %d/%d), opening chat bar and tab",
                        attempt,
                        max_retries,
                    )
                    self._click_chat_roi(window, step.chat_bar_roi, step.label)
                    if self._stop_requested.wait(0.4):
                        self._step_results[step_num] = {"detected": False}
                        return
                    self._click_chat_roi(window, step.alliance_tab_roi, step.label)
                    if self._stop_requested.wait(0.5):
                        self._step_results[step_num] = {"detected": False}
                        return

                if self._is_alliance_chat_open(
                    window, step.alliance_tab_roi
                ) or self._is_chat_window_open(window):
                    chat_ready = True
                    break

            if not chat_ready:
                logger.warning(
                    "scroll_listen_chat: Could not verify chat open after %d attempts", max_retries
                )
        else:
            self._click_chat_roi(window, step.chat_bar_roi, step.label)
            if self._stop_requested.wait(0.4):
                self._step_results[step_num] = {"detected": False}
                return
            self._click_chat_roi(window, step.alliance_tab_roi, step.label)
            if self._stop_requested.wait(0.5):
                self._step_results[step_num] = {"detected": False}
                return

        deadline = float("inf") if step.timeout_s == 0 else time.monotonic() + step.timeout_s
        interval = step.check_interval_s or 2.0
        last_details_check = 0.0
        last_chat_keepalive_check = time.monotonic()

        logger.info(
            "scroll_listen_chat: listening with arrow detection (interval=%.1fs, timeout=%s)",
            interval,
            "inf" if step.timeout_s == 0 else f"{step.timeout_s}s",
        )

        while time.monotonic() < deadline and not self._stop_requested.is_set():
            scan_started = time.monotonic()
            frame = self.capture.grab()
            if frame is None:
                if interval > 0:
                    self._sleep_with_budget(interval, scan_started, min_sleep=0.50)
                continue

            h, w = frame.shape[:2]
            if hasattr(window, "roi_to_frame_pixels"):
                left, top, right, bottom = window.roi_to_frame_pixels(
                    _roi_from_dict(step.roi_pct), w, h
                )
            else:
                left, top, right, bottom = _roi_from_dict(step.roi_pct).to_pixels(w, h)

            if right <= left or bottom <= top:
                if interval > 0:
                    self._sleep_with_budget(interval, scan_started, min_sleep=0.50)
                continue

            cropped = frame[top:bottom, left:right]
            alert = self.chat_ocr.find_helicopter_alert(cropped)

            if alert is None:
                now_mono = time.monotonic()

                if (
                    step.details_recovery_enabled
                    and step.details_roi is not None
                    and (now_mono - last_details_check >= 5.0)
                ):
                    last_details_check = now_mono
                    if self._is_details_dialog_open(window, step.details_roi):
                        delay = (
                            step.details_dismiss_delay_s
                            if step.details_dismiss_delay_s is not None
                            else 5.0
                        )
                        logger.info(
                            "scroll_listen_chat: Details popup detected! Waiting %.1fs before auto-closing...",
                            delay,
                        )

                        if delay > 0 and self._stop_requested.wait(delay):
                            self._step_results[step_num] = {"detected": False}
                            return
                        close_roi = step.details_close_roi or step.details_roi
                        self._click_chat_roi(window, close_roi, "close details popup")
                        if self._stop_requested.wait(0.4):
                            self._step_results[step_num] = {"detected": False}
                            return
                        if interval > 0:
                            self._sleep_with_budget(interval, scan_started, min_sleep=0.50)
                        continue

                if (
                    step.verify_alliance_open
                    and step.alliance_tab_roi is not None
                    and (now_mono - last_chat_keepalive_check >= 15.0)
                ):
                    last_chat_keepalive_check = now_mono
                    if not self._is_alliance_chat_open(window, step.alliance_tab_roi):
                        if self._is_chat_window_open(window):
                            logger.warning(
                                "scroll_listen_chat: Chat open on different tab — restoring Alliance tab view"
                            )
                            self._click_chat_roi(
                                window, step.alliance_tab_roi, "restore alliance tab"
                            )
                            if self._stop_requested.wait(0.4):
                                self._step_results[step_num] = {"detected": False}
                                return
                        else:
                            if (
                                not self._stop_requested.wait(0.5)
                                and not self._is_alliance_chat_open(window, step.alliance_tab_roi)
                                and not self._is_chat_window_open(window)
                            ):
                                logger.warning(
                                    "scroll_listen_chat: Chat closed or lost during active listening — restoring Alliance chat view"
                                )
                                self._click_chat_roi(window, step.chat_bar_roi, "restore chat bar")
                                if self._stop_requested.wait(0.4):
                                    self._step_results[step_num] = {"detected": False}
                                    return
                                self._click_chat_roi(
                                    window, step.alliance_tab_roi, "restore alliance tab"
                                )
                                if self._stop_requested.wait(0.4):
                                    self._step_results[step_num] = {"detected": False}
                                    return

                if step.arrow_enabled:
                    arrow_clicked = self._check_and_click_chat_arrow(
                        frame,
                        window,
                        arrow_roi_pct=step.arrow_roi,
                        threshold=step.arrow_threshold,
                    )
                    if arrow_clicked and step.arrow_click_delay_s > 0:
                        self._stop_requested.wait(step.arrow_click_delay_s)

                if interval > 0:
                    self._sleep_with_budget(interval, scan_started, min_sleep=0.50)
                continue

            if step.post_detect_reconfirm:
                if step.post_detect_settle_s > 0:
                    self._stop_requested.wait(step.post_detect_settle_s)
                reconfirm = self._read_chat_alert(step.roi_pct, window)
                if reconfirm is not None:
                    alert = reconfirm

            debounce_clear = False
            if step.post_click_debounce:
                if step.post_detect_settle_s > 0:
                    self._stop_requested.wait(step.post_detect_settle_s)
                post = self._read_chat_alert(step.roi_pct, window)
                debounce_clear = post is None

            game_pct_x, game_pct_y = self._alert_to_game_pct(alert, left, top, w, h)
            logger.info(
                "scroll_listen_chat: alert detected at (%.1f%%, %.1f%%) — triggering zero-latency direct click",
                game_pct_x,
                game_pct_y,
            )
            if step.direct_click and self.clicker is not None:
                try:
                    gp = _to_game_percent(game_pct_x, game_pct_y)
                    coord = window.to_screen(gp)
                    self.clicker.click_at(coord.x, coord.y)
                    self.memory["step_1_direct_clicked"] = True
                except Exception as exc:
                    logger.debug("scroll_listen_chat: direct click failed: %s", exc)

            with self._stats_lock:
                self.stats_alerts += 1
            self.memory["step_1_click_x"] = game_pct_x
            self.memory["step_1_click_y"] = game_pct_y
            self._step_results[step_num] = {
                "detected": True,
                "fast_path": False,
                "click_x": game_pct_x,
                "click_y": game_pct_y,
                "debounce_clear": debounce_clear,
            }
            return

        logger.info("scroll_listen_chat: timeout or stopped")
        self._step_results[step_num] = {"detected": False}

    def _click_chat_roi(self, window, roi_pct: dict, label: str = "") -> None:
        window = self._get_fresh_window(window)
        roi = _roi_from_dict(roi_pct)
        center = window.roi_center_to_screen(roi)
        logger.debug("scroll_listen_chat: click chat @(%d,%d) [%s]", center.x, center.y, label)
        self.clicker.click_at(center.x, center.y)

    def _roi_origin_in_frame(
        self, roi_pct: dict, frame_w: int, frame_h: int, window
    ) -> tuple[int, int]:
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, _r, _b = window.roi_to_frame_pixels(
                _roi_from_dict(roi_pct), frame_w, frame_h
            )
        else:
            left, top, _r, _b = _roi_from_dict(roi_pct).to_pixels(frame_w, frame_h)
        return left, top

    def _handle_wait_for_chat(self, step_num: int, step: MacroStep, window) -> None:
        if "step_1_click_x" in self.memory and "step_1_click_y" in self.memory:
            logger.info("wait_for_chat: skipping — pre-run scroll-listen already detected alert")
            self._step_results[step_num] = {"detected": True, "fast_path": True}
            return
        if self.chat_ocr is None or self.capture is None:
            raise OCRError("ChatOCR/Capture not configured")
        if step.roi_pct is None:
            raise MacroStepError(step.label, "roi_pct is required")

        deadline = float("inf") if step.timeout_s == 0 else time.monotonic() + step.timeout_s
        interval = step.check_interval_s or 15.0
        logger.info("wait_for_chat: waiting for helicopter alert (interval=%.1fs)", interval)

        while time.monotonic() < deadline and not self._stop_requested.is_set():
            frame = self.capture.grab()
            if frame is None:
                self._stop_requested.wait(interval)
                continue

            h, w = frame.shape[:2]
            if hasattr(window, "roi_to_frame_pixels"):
                left, top, right, bottom = window.roi_to_frame_pixels(
                    _roi_from_dict(step.roi_pct), w, h
                )
            else:
                left, top, right, bottom = _roi_from_dict(step.roi_pct).to_pixels(w, h)
            if right <= left or bottom <= top:
                self._stop_requested.wait(interval)
                continue

            cropped = frame[top:bottom, left:right]
            alert = self.chat_ocr.find_helicopter_alert(cropped)
            if alert is not None:
                game_pct_x, game_pct_y = self._alert_to_game_pct(alert, left, top, w, h)
                logger.info(
                    "wait_for_chat: helicopter alert detected at (%.1f%%, %.1f%%)",
                    game_pct_x,
                    game_pct_y,
                )
                with self._stats_lock:
                    self.stats_alerts += 1
                self.memory["step_1_click_x"] = game_pct_x
                self.memory["step_1_click_y"] = game_pct_y
                self._step_results[step_num] = {
                    "detected": True,
                    "click_x": game_pct_x,
                    "click_y": game_pct_y,
                }
                return

            if step.arrow_enabled:
                arrow_clicked = self._check_and_click_chat_arrow(
                    frame,
                    window,
                    arrow_roi_pct=step.arrow_roi,
                    threshold=step.arrow_threshold,
                )
                if arrow_clicked and step.arrow_click_delay_s > 0:
                    self._stop_requested.wait(step.arrow_click_delay_s)

            self._stop_requested.wait(interval)

        logger.info("wait_for_chat: timeout or stopped")
        self._step_results[step_num] = {"detected": False}

    def _handle_watch_timer(self, step_num: int, step: MacroStep, window) -> None:
        if self.clicker is None:
            raise ClickerError("Clicker not configured")
        if step.roi_pct is None:
            raise MacroStepError(step.label, "roi_pct is required")

        cfg = self.config if hasattr(self, "config") and self.config else None
        idle_interval = (
            step.idle_check_interval_s
            if step.idle_check_interval_s is not None
            else (getattr(cfg, "idle_check_interval_s", 3.0) if cfg else 3.0)
        )
        fast_interval = (
            step.fast_check_interval_s
            if step.fast_check_interval_s is not None
            else (getattr(cfg, "fast_check_interval_s", 0.2) if cfg else 0.2)
        )
        fast_threshold = (
            step.fast_threshold_s
            if step.fast_threshold_s is not None
            else (getattr(cfg, "fast_threshold_s", 60) if cfg else 60)
        )
        spam_threshold = step.spam_threshold_s or 5
        spam_duration = step.spam_duration_s or 7.0
        default_cps = getattr(self.config, "spam_clicks_per_sec", 30) if hasattr(self, "config") and self.config else 30
        clicks_per_sec = step.spam_clicks_per_sec or default_cps
        hysteresis_required = max(1, step.hysteresis_confirmations or 1)

        if step.click_x is not None and step.click_y is not None:
            from mvp.bot.coordinates import GamePercent

            cx_pct = self._interpolate(step.click_x)
            cy_pct = self._interpolate(step.click_y)
            try:
                cx_pct = float(cx_pct)
                cy_pct = float(cy_pct)
            except (TypeError, ValueError):
                cx_pct, cy_pct = 50.0, 50.0
            click_target = window.to_screen(GamePercent(cx_pct, cy_pct))
        else:
            roi = _roi_from_dict(step.roi_pct)
            click_target = window.roi_center_to_screen(roi)

        t0_lead_time = step.t0_lead_time_s if step.t0_lead_time_s is not None else 0.3

        timeout_s = float(step.timeout_s) if step.timeout_s else 1800.0
        phase = "idle"
        self._emit("phase_transition", step_num, step, phase=phase)
        last_known_value: int | None = None
        estimated_t0_mono: float | None = None
        last_progress_mono = time.monotonic()
        last_progress_value: int | None = None

        # NEW: State tracking for adaptive interval and proactive spam prep (Requirements 2.1, 2.2, 2.3)
        config = step.get_ocr_interval_config()

        ocr_interval_state = {
            "current_interval": config["initial_interval"],  # Start at 1.0s (adaptive)
            "last_query_time": time.monotonic() - config["initial_interval"],  # Ensure first OCR query happens immediately
            "timer_history": [],  # List of {"value": timer_value, "time": timestamp}
        }

        spam_prep_state = {
            "confirmed_count": 0,  # Number of consecutive timer <= spam_threshold reads
            "estimated_t0_mono": None,  # Extrapolated T0 time (locked after hysteresis)
            "spam_prepared": False,
        }

        cpu_pause_state = {
            "active": False,
            "start_time": None,
        }

        logger.info(
            "watch_timer: starting (idle=%.1fs, fast=%.1fs, fast_th=%ds, spam_th=%ds, "
            "duration=%.1fs, t0_lead=%.2fs, hysteresis=%d, inactivity_timeout=%.0fs, "
            "adaptive_ocr_enabled=True, initial_ocr_interval=%.1fs, accel_threshold=%.1fs)",
            idle_interval,
            fast_interval,
            fast_threshold,
            spam_threshold,
            spam_duration,
            t0_lead_time,
            hysteresis_required,
            timeout_s,
            config["initial_interval"],
            config["accel_threshold"],
        )

        march_modal_checked = False
        # Sprawdź i zamknij okno potwierdzenia marszu, jeśli jest nadal obecne
        if self._check_and_dismiss_march_modal(window):
            march_modal_checked = True

        while not self._stop_requested.is_set():
            poll_started = time.monotonic()

            if (
                phase == "fast"
                and spam_prep_state["estimated_t0_mono"] is not None
                and poll_started >= (spam_prep_state["estimated_t0_mono"] - t0_lead_time)
            ):
                logger.info(
                    "watch_timer: estimated T0 reached via monotonic clock (target_mono=%.2f, now=%.2f, timer=%ds, lead=%.2fs) -> triggering spam",
                    spam_prep_state["estimated_t0_mono"],
                    poll_started,
                    last_known_value or 0,
                    t0_lead_time,
                )
                phase = "spam"
                self._emit("phase_transition", step_num, step, phase=phase)

            # NEW: For IDLE phase, still read timer periodically (unchanged behavior)
            if phase == "idle":
                max_passes = 2 if phase == "fast" else 4
                raw_res = self._read_timer_value(step, window, max_passes=max_passes)
                if isinstance(raw_res, tuple):
                    value, grab_time = raw_res
                else:
                    value, grab_time = raw_res, poll_started

                if value is not None:
                    with self._stats_lock:
                        self.last_timer_value = value

                    if last_progress_value is None or value != last_progress_value:
                        last_progress_value = value
                        last_progress_mono = poll_started

                    if last_known_value is not None and (value > last_known_value or value - last_known_value > _JUMP_DETECTION_THRESHOLD_S):
                        logger.info(
                            "watch_timer: timer increased from %ds to %ds (e.g. player left helicopter) — updating T0 estimate",
                            last_known_value,
                            value,
                        )
                        spam_prep_state["confirmed_count"] = 0
                        spam_prep_state["estimated_t0_mono"] = None
                        spam_prep_state["spam_prepared"] = False
                        estimated_t0_mono = grab_time + value
                        if value > fast_threshold and phase == "fast":
                            phase = "idle"
                            self._emit("phase_transition", step_num, step, phase=phase)
                    else:
                        new_t0 = grab_time + value
                        if (
                            estimated_t0_mono is None
                            or last_known_value is None
                            or value != last_known_value
                        ):
                            estimated_t0_mono = new_t0
                    last_known_value = value
            else:
                value = None

            now = time.monotonic()

            if timeout_s > 0 and (now - last_progress_mono) >= timeout_s:
                logger.warning(
                    "watch_timer: inactivity timeout (%.0fs with no timer or stuck timer) — returning to chat",
                    timeout_s,
                )
                self._step_results[step_num] = {"triggered": False, "reason": "inactivity_timeout"}
                return

            if phase == "idle":
                if value is None:
                    if not march_modal_checked and last_known_value is None:
                        march_modal_checked = True
                        self._check_and_dismiss_march_modal(window)
                    self._sleep_with_budget(idle_interval, poll_started, min_sleep=0.10)
                    continue
                if value <= fast_threshold:
                    phase = "fast"
                    self._emit("phase_transition", step_num, step, phase=phase)
                    logger.info("watch_timer: phase -> fast (timer=%ds)", value)
                    ocr_interval_state["last_query_time"] = grab_time
                    ocr_interval_state["timer_history"].append({"value": value, "time": grab_time})
                    if value <= spam_threshold:
                        spam_prep_state["confirmed_count"] += 1
                        if (
                            spam_prep_state["estimated_t0_mono"] is None
                            and spam_prep_state["confirmed_count"] >= hysteresis_required
                        ):
                            avg_delta = calculate_avg_delta(ocr_interval_state["timer_history"])
                            spam_prep_state["estimated_t0_mono"] = grab_time + (value * avg_delta)
                            spam_prep_state["spam_prepared"] = True
                            logger.info(
                                "watch_timer: T0 estimate locked (value=%ds, avg_delta=%.3f, estimated_t0=%.2f)",
                                value,
                                avg_delta,
                                spam_prep_state["estimated_t0_mono"],
                            )
                            remaining_to_lead = (
                                spam_prep_state["estimated_t0_mono"] - t0_lead_time
                            ) - time.monotonic()
                            if remaining_to_lead <= 3.5:
                                if remaining_to_lead > 0:
                                    self._sleep_with_budget(
                                        remaining_to_lead, poll_started, min_sleep=0.001
                                    )
                                if time.monotonic() >= (
                                    spam_prep_state["estimated_t0_mono"] - t0_lead_time
                                ):
                                    phase = "spam"
                                    self._emit("phase_transition", step_num, step, phase=phase)
                                    logger.info(
                                        "watch_timer: phase -> spam (countdown locked: slept to T0 lead)",
                                    )
                                continue
                else:
                    self._sleep_with_budget(idle_interval, poll_started, min_sleep=0.10)
                    continue

            if phase == "fast":
                now = time.monotonic()

                # Countdown Lock: If T0 is locked and remaining time to lead is <= 3.5s,
                # DO NOT run blocking OCR again — sleep directly to T0-lead!
                if spam_prep_state["estimated_t0_mono"] is not None:
                    remaining_to_lead = (spam_prep_state["estimated_t0_mono"] - t0_lead_time) - now
                    if remaining_to_lead <= 3.5:
                        if remaining_to_lead > 0:
                            self._sleep_with_budget(remaining_to_lead, poll_started, min_sleep=0.001)
                        if time.monotonic() >= (spam_prep_state["estimated_t0_mono"] - t0_lead_time):
                            phase = "spam"
                            self._emit("phase_transition", step_num, step, phase=phase)
                            logger.info("watch_timer: phase -> spam (countdown locked: slept to T0 lead)")
                        continue

                # NEW: Adaptive interval logic (Requirements 2.1, 2.2, 2.3)
                time_since_last_query = now - ocr_interval_state["last_query_time"]
                ocr_was_run = False  # Track if OCR was actually executed

                # Determine if we should run OCR query based on adaptive interval (with small float tolerance)
                if time_since_last_query >= (ocr_interval_state["current_interval"] - 0.002):
                    ocr_was_run = True
                    # Update adaptive interval based on remaining time
                    time_remaining = max(0, last_known_value or spam_threshold)
                    new_interval = calculate_adaptive_interval(
                        time_remaining=time_remaining,
                        initial_interval=config["initial_interval"],
                        accel_threshold=config["accel_threshold"],
                        min_interval=config["min_interval"],
                    )
                    ocr_interval_state["current_interval"] = new_interval

                    # Run OCR (with skip_ocr flag if in CPU pause window) (Requirement 2.2)
                    max_passes = 2 if phase == "fast" else 4
                    raw_res = self._read_timer_value(
                        step,
                        window,
                        max_passes=max_passes,
                        skip_ocr=cpu_pause_state["active"],  # <-- NEW: skip OCR during CPU pause
                    )
                    if isinstance(raw_res, tuple):
                        value, grab_time = raw_res
                    else:
                        value, grab_time = raw_res, now

                    # Track reading in history
                    ocr_interval_state["timer_history"].append(
                        {
                            "value": value,
                            "time": grab_time,
                        }
                    )

                    # Keep only last 5 readings to avoid memory bloat
                    if len(ocr_interval_state["timer_history"]) > 5:
                        ocr_interval_state["timer_history"] = ocr_interval_state["timer_history"][
                            -5:
                        ]

                    # Only update last_query_time if real OCR was executed (not skipped during CPU pause)
                    if not cpu_pause_state["active"]:
                        ocr_interval_state["last_query_time"] = time.monotonic()

                    if value is not None:
                        with self._stats_lock:
                            self.last_timer_value = value

                        if last_progress_value is None or value != last_progress_value:
                            last_progress_value = value
                            last_progress_mono = poll_started

                        # Handle timer jump (timer increased)
                        if last_known_value is not None and (value > last_known_value or value - last_known_value > _JUMP_DETECTION_THRESHOLD_S):
                            logger.info(
                                "watch_timer: timer increased from %ds to %ds (e.g. player left helicopter) — resetting spam state",
                                last_known_value,
                                value,
                            )
                            spam_prep_state["confirmed_count"] = 0
                            spam_prep_state["estimated_t0_mono"] = None
                            spam_prep_state["spam_prepared"] = False
                            estimated_t0_mono = grab_time + value
                            if value > fast_threshold and phase == "fast":
                                phase = "idle"
                                self._emit("phase_transition", step_num, step, phase=phase)
                        else:
                            new_t0 = grab_time + value
                            if (
                                estimated_t0_mono is None
                                or last_known_value is None
                                or value != last_known_value
                            ):
                                estimated_t0_mono = new_t0
                        last_known_value = value

                        # Update spam_prep_state based on low timer reading (Requirement 2.3)
                        if value <= spam_threshold:
                            spam_prep_state["confirmed_count"] += 1

                            # Respect a locked T0 estimate: only short-circuit to spam when the
                            # monotonic estimate is not yet locked or its lead-time has already
                            # been reached. Otherwise defer to the countdown-lock path above.
                            locked_t0 = spam_prep_state["estimated_t0_mono"]
                            t0_reached = (
                                locked_t0 is None
                                or now >= (locked_t0 - t0_lead_time)
                            )
                            if (
                                spam_prep_state["confirmed_count"] >= hysteresis_required
                                and t0_reached
                            ):
                                phase = "spam"
                                self._emit("phase_transition", step_num, step, phase=phase)
                                logger.info(
                                    "watch_timer: timer <= spam_threshold (%ds <= %ds) -> starting spam phase immediately",
                                    value,
                                    spam_threshold,
                                )
                                continue
                        else:
                            spam_prep_state["confirmed_count"] = 0

                    # Check if CPU pause window should be active (Requirement 2.2)
                    if spam_prep_state["estimated_t0_mono"] is not None:
                        time_to_t0 = spam_prep_state["estimated_t0_mono"] - now
                        if time_to_t0 < config["cpu_pause_window"] and time_to_t0 > 0:
                            if not cpu_pause_state["active"]:
                                cpu_pause_state["active"] = True
                                cpu_pause_state["start_time"] = now
                                logger.info(
                                    "watch_timer: CPU pause window ACTIVE (%.2f seconds to T0)",
                                    time_to_t0,
                                )
                        elif time_to_t0 <= 0:
                            cpu_pause_state["active"] = False
                else:
                    # Not yet time for next OCR query — don't update value
                    value = None
                    ocr_was_run = False
                    # Still need to sleep until next OCR interval (minimum 50ms floor to prevent busy-loop)
                    remaining = ocr_interval_state["current_interval"] - time_since_last_query
                    min_floor = 0.02 if (last_known_value is not None and last_known_value <= 3) else 0.05
                    self._sleep_with_budget(max(min_floor, remaining), now, min_sleep=min_floor)
                    continue  # Skip the normal sleep logic below, already slept

                # NEW: Check spam trigger conditions using helper function (Requirement 2.3, 3.4, 3.5)
                if should_trigger_spam(
                    ocr_timer_value=value,
                    estimated_t0_mono=spam_prep_state["estimated_t0_mono"],
                    confirmed_count=spam_prep_state["confirmed_count"],
                    hysteresis_confirmations=hysteresis_required,
                    spam_threshold=spam_threshold,
                    t0_lead_time_s=step.t0_lead_time_s,
                ):
                    phase = "spam"
                    self._emit("phase_transition", step_num, step, phase=phase)
                    logger.info(
                        "watch_timer: phase -> spam (via should_trigger_spam)",
                    )
                    continue

                # Handle case when timer disappeared at low value (existing logic)
                if (
                    ocr_was_run
                    and value is None
                    and last_known_value is not None
                    and last_known_value <= spam_threshold
                ):
                    logger.info(
                        "watch_timer: timer disappeared at low value (%ds) — box just spawned! Phase -> spam",
                        last_known_value,
                    )
                    phase = "spam"
                    self._emit("phase_transition", step_num, step, phase=phase)
                    continue

                # If CPU pause is active, sleep directly until target T0 - lead_time
                if cpu_pause_state["active"] and spam_prep_state["estimated_t0_mono"] is not None:
                    target_mono = spam_prep_state["estimated_t0_mono"] - t0_lead_time
                    remaining_to_t0 = target_mono - now
                    if remaining_to_t0 > 0:
                        self._sleep_with_budget(remaining_to_t0, now, min_sleep=0.001)
                    continue

                # Sleep until next scheduled OCR time with min_sleep floor to prevent CPU busy-loop
                now = time.monotonic()
                next_ocr_scheduled = ocr_interval_state["last_query_time"] + ocr_interval_state["current_interval"]
                time_to_t0 = (
                    (spam_prep_state["estimated_t0_mono"] - now)
                    if spam_prep_state["estimated_t0_mono"] is not None
                    else None
                )
                min_sleep_floor = 0.02 if (time_to_t0 is not None and time_to_t0 <= 3.0) else 0.05
                remaining = max(min_sleep_floor, next_ocr_scheduled - now)
                self._sleep_with_budget(remaining, now, min_sleep=min_sleep_floor)

                continue

            if phase == "spam":
                if not self._ensure_foreground():
                    self._step_results[step_num] = {"triggered": False, "reason": "focus_failed"}
                    raise MacroStepError(
                        step.label,
                        f"Could not bring game window to foreground ({self.process_name}); "
                        "spam aborted",
                    )

                logger.info(
                    "watch_timer: spam clicking @(%d,%d) for %.1fs @%d/s",
                    click_target.x,
                    click_target.y,
                    spam_duration,
                    clicks_per_sec,
                )
                self._spam_target_x = click_target.x
                self._spam_target_y = click_target.y
                self._spam_duration_s = spam_duration
                self._spam_cps = clicks_per_sec
                if not self._try_begin_spam():
                    logger.info("watch_timer: another spam already in flight — skip OCR spam")
                    self._step_results[step_num] = {"triggered": True}
                    return
                self._call_spam_hooks("on_spam_begin")
                try:
                    self.clicker.spam_click(
                        click_target.x,
                        click_target.y,
                        count=int(spam_duration * clicks_per_sec),
                        deadline=time.perf_counter() + spam_duration,
                        clicks_per_sec=clicks_per_sec,
                        direct_first=True,
                    )
                except Exception as exc:
                    logger.warning(
                        "watch_timer: spam_click encountered error: %s",
                        exc,
                        exc_info=True,
                    )
                finally:
                    self._call_spam_hooks("on_spam_end")
                    self._end_spam()
                self._step_results[step_num] = {"triggered": True}
                return

        self._step_results[step_num] = {"triggered": False}

    def _read_timer_value(
        self, step: MacroStep, window, max_passes: int = 1, skip_ocr: bool = False
    ) -> tuple[int | None, float]:
        """Read timer value via OCR, with optional skip for CPU pause window.

        Args:
            step: MacroStep configuration
            window: WindowContext for coordinate conversion
            max_passes: Number of OCR passes (RapidOCR recognition/detection fallback)
            skip_ocr: If True, return last_known_value without executing OCR (CPU pause window)

        Returns:
            Tuple of (timer_value, grab_time)
        """
        grab_mono = time.monotonic()

        # NEW: If skip_ocr is True (during CPU pause window), return cached value
        if skip_ocr:
            if self.last_timer_value is not None:
                logger.debug(
                    "watch_timer: Skipping OCR (CPU pause window active), using cached value %ds",
                    self.last_timer_value,
                )
                return (self.last_timer_value, grab_mono)
            else:
                # If no cached value, must run OCR anyway
                logger.debug(
                    "watch_timer: skip_ocr requested but no cached value available, running OCR"
                )

        # Rest of method unchanged — grab frame, process, run OCR
        frame = self.capture.grab() if self.capture is not None else None
        grab_mono = time.monotonic()
        if frame is None:
            return None, grab_mono
        h, w = frame.shape[:2]
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, right, bottom = window.roi_to_frame_pixels(
                _roi_from_dict(step.roi_pct), w, h
            )
        else:
            left, top, right, bottom = _roi_from_dict(step.roi_pct).to_pixels(w, h)
        if right <= left or bottom <= top:
            return None, grab_mono
        cropped = frame[top:bottom, left:right]
        if hasattr(self.timer_ocr, "read_timer_robust"):
            val = self.timer_ocr.read_timer_robust(cropped, max_passes=max_passes)
        else:
            try:
                val = self.timer_ocr.read_timer(cropped, max_passes=max_passes)
            except TypeError:
                val = self.timer_ocr.read_timer(cropped)
        return val, grab_mono

    def _get_fresh_window(self, window):
        if self.window_context_refresher is not None:
            try:
                geo = self.window_context_refresher()
                if geo is not None:
                    if hasattr(geo, "to_screen"):
                        return geo
                    if isinstance(geo, (tuple, list)):
                        return type(window)(*geo)
                    return geo
            except Exception:
                logger.debug("window_context_refresher failed", exc_info=True)
        return window

    def _alert_to_game_pct(
        self,
        alert: dict,
        left: float,
        top: float,
        frame_w: int,
        frame_h: int,
    ) -> tuple[float, float]:
        px_x = left + alert.get("click_x", 0)
        px_y = top + alert.get("click_y", 0)
        game_pct_x = (px_x / frame_w * 100.0) if frame_w > 0 else 0.0
        game_pct_y = (px_y / frame_h * 100.0) if frame_h > 0 else 0.0
        return game_pct_x, game_pct_y

    def _read_chat_alert(self, roi_pct: dict, window) -> dict | None:
        frame = self.capture.grab()
        if frame is None:
            return None
        h, w = frame.shape[:2]
        if hasattr(window, "roi_to_frame_pixels"):
            left, top, right, bottom = window.roi_to_frame_pixels(_roi_from_dict(roi_pct), w, h)
        else:
            left, top, right, bottom = _roi_from_dict(roi_pct).to_pixels(w, h)
        if right <= left or bottom <= top:
            return None
        cropped = frame[top:bottom, left:right]
        return self.chat_ocr.find_helicopter_alert(cropped)

    def _sleep_with_budget(
        self, interval: float, started_mono: float, min_sleep: float = 0.0
    ) -> None:
        elapsed = time.monotonic() - started_mono
        # AGENTS.md §8: floor at 1ms to prevent infinite-loop on interval <= 0 (busy-spinning
        # the Event.wait with 0 would still yield to the scheduler, but it is wasteful).
        duration = max(0.001, max(min_sleep, interval - elapsed))
        self._stop_requested.wait(duration)

    def _interpolate(self, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value in self.memory:
            return self.memory[value]
        if "$$" in value:

            def _replacer(match: re.Match) -> str:
                key = match.group(1)
                raw = self.memory.get(key)
                if raw is None:
                    return match.group(0)
                return str(raw)

            return re.sub(r"\$\$(\w+)\$\$", _replacer, value)
        return value

    def _resolve_value(self, value: object) -> int | float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return None
        return None


def _roi_from_dict(roi_pct: dict):
    from mvp.bot.coordinates import GameROI

    return GameROI(
        left=roi_pct.get("left", 0),
        top=roi_pct.get("top", 0),
        right=roi_pct.get("right", 100),
        bottom=roi_pct.get("bottom", 100),
        anchor=roi_pct.get("anchor", "stretch"),
    )


def _to_game_percent(x, y):
    from mvp.bot.coordinates import GamePercent

    return GamePercent(float(x), float(y))
