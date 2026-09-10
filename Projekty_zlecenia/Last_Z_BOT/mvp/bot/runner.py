from __future__ import annotations

import contextlib
import logging
import os
import queue
import threading
import time
from pathlib import Path

import cv2

from mvp.bot.anti_detect import AntiDetect
from mvp.bot.anti_sleep import SleepGuard
from mvp.bot.capture import ScreenCapture
from mvp.bot.clicker import Clicker
from mvp.bot.coordinates import WindowContext
from mvp.bot.exceptions import AntiSleepError
from mvp.bot.macro_engine import MacroEngine
from mvp.bot.macro_step_logger import MacroStepLogger
from mvp.bot.monitor_mapper import get_monitor_for_window
from mvp.bot.verbose import VerboseController
from mvp.bot.window_finder import find_game_window
from mvp.bot.window_recovery import WindowRecoveryWatchdog
from mvp.config import MVPConfig
from mvp.macro_def import build_helicopter_macro

try:
    from mvp.bot.ocr import ChatOCR, TimerOCR
except ImportError:
    # In test environments, OCR modules may not be available
    ChatOCR = None  # type: ignore
    TimerOCR = None  # type: ignore

logger = logging.getLogger(__name__)


class FrameProducer:

    def __init__(
        self,
        capture: ScreenCapture,
        frame_queue: queue.Queue[object],
        target_fps: int = 30,
        scale: float = 1.0,
        health_check_every_n_frames: int = 30,
    ) -> None:
        self._capture = capture
        self._frame_queue = frame_queue
        self._target_fps = target_fps
        self._scale = scale
        self._health_check_every_n_frames = max(1, int(health_check_every_n_frames))
        self._frame_counter = 0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "FrameProducer started (target=%d FPS, scale=%.2f)", self._target_fps, self._scale
        )

    def stop(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            return
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._thread = None
        logger.info("FrameProducer stopped")

    def set_scale(self, scale: float) -> None:
        self._scale = scale

    def set_fps(self, fps: int) -> None:
        self._target_fps = max(1, min(60, int(fps)))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            # Pause during the spam phase so the frame grabber's GIL + OpenCV work
            # does not introduce timing jitter into the high-precision click loop.
            if self._pause_event.is_set():
                self._pause_event.wait(timeout=0.05)
                continue
            try:
                frame = self._capture.grab()
            except RuntimeError:
                time.sleep(0.5)
                continue
            if frame is not None:
                if self._scale < 1.0:
                    frame = cv2.resize(
                        frame, None, fx=self._scale, fy=self._scale, interpolation=cv2.INTER_AREA
                    )
                try:
                    self._frame_queue.put_nowait(frame)
                except queue.Full:
                    with contextlib.suppress(queue.Empty):
                        self._frame_queue.get_nowait()
                    with contextlib.suppress(queue.Full):
                        self._frame_queue.put_nowait(frame)

                self._frame_counter += 1
                if self._frame_counter % self._health_check_every_n_frames == 0:
                    self._capture.health_check()

            time.sleep(1.0 / self._target_fps)


class BotRunner:

    def __init__(self, config: MVPConfig, frame_queue: queue.Queue[object] | None = None) -> None:
        self.config = config
        self.capture = ScreenCapture()
        self.clicker = Clicker(
            min_delay_ms=config.click_min_delay_ms,
            max_delay_ms=config.click_max_delay_ms,
            spam_noise_px=config.spam_noise_px,
            click_jitter_ms=config.click_jitter_ms,
        )
        self.chat_ocr = ChatOCR()
        self.timer_ocr = TimerOCR()
        self.macro = build_helicopter_macro(config)
        self._listen_step = self.macro.steps[0]

        self.frame_queue = frame_queue if frame_queue is not None else queue.Queue(maxsize=2)
        self._frame_producer = FrameProducer(
            self.capture,
            self.frame_queue,
            target_fps=config.scan_fps,
            scale=config.preview_scale,
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ocr_prewarmed = False
        self._window_info_lock = threading.Lock()
        self.latest_window_info: object | None = None
        self._monitor_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None

        self.macro_engine = MacroEngine(
            clicker=self.clicker,
            chat_ocr=self.chat_ocr,
            timer_ocr=self.timer_ocr,
            capture=self.capture,
            window_context_refresher=self._refresh_window_context,
            checkpoint_path=Path(config.log_dir) / "checkpoint.json",
            config=config,
        )
        self.macro_engine._current_macro = self.macro

        # Pause the frame producer during the spam phase to eliminate GIL-induced
        # timing jitter in the click loop.
        self.macro_engine.on_spam_begin = self._pause_frame_producer
        self.macro_engine.on_spam_end = self._resume_frame_producer

        # Setup macro step logger for test orchestration (disabled in production
        # unless config.debug_macro_log is True).
        self._step_logger = MacroStepLogger(
            log_path=Path.cwd() / "bot_macro.log",  # Write to project root
            enabled=bool(getattr(config, "debug_macro_log", False)),
        )
        self.macro_engine.step_callback = self._step_logger.on_step_event

        self.sleep_guard = SleepGuard()
        self.anti_detect = AntiDetect(check_interval_s=config.anti_detect_check_interval_s)
        self.verbose_controller = VerboseController(disable_console=True)
        self._apply_verbose()

    def _pause_frame_producer(self) -> None:
        if self._frame_producer is not None:
            self._frame_producer.pause()

    def _resume_frame_producer(self) -> None:
        if self._frame_producer is not None:
            self._frame_producer.resume()

    def _refresh_window_context(self) -> WindowContext | None:
        info = find_game_window(self.config.process_name)
        if info is None:
            return None
        with self._window_info_lock:
            self.latest_window_info = info
        return WindowContext(
            left=info.left,
            top=info.top,
            width=info.width,
            height=info.height,
            title_bar_height=info.title_bar_height,
            hwnd=info.hwnd,
        )

    def start(self) -> None:
        if getattr(self, "_starting", False):
            return
        if self._thread is not None and self._thread.is_alive():
            if self._stop_event.is_set():
                logger.info("Previous runner thread is terminating, waiting for it to finish...")
                self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                raise RuntimeError(
                    "The bot is already running (or the previous session is still shutting down)."
                )
        self._starting = True
        try:
            logger.info("Initializing input engine (SendInput)...")
            self.clicker.initialize()
            self._apply_process_priority()
            self._start_ocr_prewarm()
            self._wait_for_window_on_start()
            if not self.clicker.is_initialized:
                raise RuntimeError(
                    "SendInput backend is not available."
                )

            if getattr(self.clicker, "_backend_mode", "") == "sendinput" or (
                self.clicker._backend is not None and self.clicker._backend.name == "sendinput"
            ):
                try:
                    from mvp.bot.window_finder import check_uipi_elevation_mismatch

                    if check_uipi_elevation_mismatch(self.config.process_name):
                        raise RuntimeError(
                            f"UIPI BLOCKED: game ({self.config.process_name}) runs as Administrator while the bot runs "
                            "as a standard user. Windows will silently discard SendInput clicks. "
                            "Run the bot as Administrator (or the game without Administrator "
                            "rights) and try again."
                        )
                except RuntimeError:
                    raise
                except Exception as uipi_exc:
                    logger.debug("UIPI check failed: %s", uipi_exc)

            self.capture.start()
            if self.config.preview_enabled:
                self._frame_producer.start()

            self._apply_anti_sleep()

            self._stop_event.clear()
            ocr_prewarm = getattr(self, "_ocr_prewarm_thread", None)
            if ocr_prewarm is not None and ocr_prewarm.is_alive():
                logger.info("Pre-warming fast OCR models (ONNX/WinOCR)...")
                ocr_prewarm.join(timeout=2.0)
            self._thread = threading.Thread(target=self._main_loop, daemon=True)
            self._thread.start()
            logger.info("BotRunner started successfully - macro loop active")
        finally:
            self._starting = False


    def prewarm_ocr(self) -> threading.Thread | None:
        return self._start_ocr_prewarm()

    def _start_ocr_prewarm(self) -> threading.Thread | None:
        if self._ocr_prewarmed:
            return None
        self._ocr_prewarmed = True

        def _prewarm() -> None:
            try:
                self.chat_ocr.initialize()
                self.timer_ocr.initialize()
                logger.info("Fast OCR pre-warmed in background")
            except Exception as exc:
                logger.warning("OCR pre-warm failed (lazy init will still work): %s", exc)

        thread = threading.Thread(target=_prewarm, daemon=True, name="ocr-prewarm")
        self._ocr_prewarm_thread = thread
        thread.start()
        return thread

    def _wait_for_window_on_start(self) -> None:
        try:
            watchdog = WindowRecoveryWatchdog(
                finder=lambda: find_game_window(self.config.process_name),
                max_attempts=5,
                retry_interval_s=2.0,
                backoff_multiplier=1.5,
                max_backoff_s=8.0,
                on_retry=self._on_window_retry_status,
            )
            watchdog.wait_for_window()
        except Exception as exc:
            logger.warning(
                "Window auto-recovery failed at startup (%s). "
                "The main loop will retry internally.",
                exc,
            )

    def _on_window_retry_status(self, attempt: int, max_attempts: int, next_sleep_s: float) -> None:
        logger.debug(
            "Window recovery: attempt %d/%d, next in %.1fs",
            attempt,
            max_attempts,
            next_sleep_s,
        )

    def _apply_process_priority(self) -> None:
        priority = getattr(self.config, "process_priority", "normal")
        if priority == "normal":
            return
        try:
            import psutil

            proc = psutil.Process()
            if os.name == "nt":
                if priority == "below_normal":
                    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                elif priority == "idle":
                    proc.nice(psutil.IDLE_PRIORITY_CLASS)
            else:
                proc.nice(10 if priority == "below_normal" else 19)
            logger.info("Process priority set to %s", priority)
        except Exception as exc:
            logger.debug("process priority setup failed: %s", exc)

    def _apply_anti_sleep(self) -> None:
        try:
            if self.config.prevent_sleep or self.config.prevent_display_off:
                self.sleep_guard.enable(
                    display=self.config.prevent_display_off,
                    system=self.config.prevent_sleep,
                    away_mode=self.config.anti_sleep_away_mode,
                )
            else:
                self.sleep_guard.disable()
        except AntiSleepError as exc:
            logger.warning("Anti-sleep request failed: %s", exc)

    def _apply_anti_detect(self) -> None:
        try:
            status = self.anti_detect.check_and_harden_on_startup()
            if status.get("debugger_detected"):
                logger.warning(
                    "Anti-detect: a debugger was detected at startup (hardened=%s).",
                    status.get("hardened"),
                )
            if self.config.anti_detect_enabled:
                self.anti_detect.check_interval_s = self.config.anti_detect_check_interval_s
                self.anti_detect.start_periodic_check(callback=self._on_debugger_detected)
            else:
                self.anti_detect.stop()
        except Exception as exc:
            logger.debug("Anti-detect setup failed: %s", exc)

    def _apply_verbose(self) -> None:
        try:
            level = "DEBUG" if self.config.log_verbose else "INFO"
            self.verbose_controller.set_level(level)
            if self.config.log_to_file:
                log_path = Path(self.config.log_dir) / "verbose.log"
                self.verbose_controller.enable_file_output(str(log_path))
            else:
                self.verbose_controller.disable_file_output()
        except Exception as exc:
            logger.debug("Verbose setup failed: %s", exc)

    def _on_debugger_detected(self, detected: bool) -> None:
        if detected:
            logger.warning(
                "Anti-detect: a debugger attached to the process was detected (runtime). "
                "The bot may be analyzed."
            )

    def start_window_monitor(self) -> None:
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._window_monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Window monitor started")

    def stop_window_monitor(self) -> None:
        self._monitor_stop.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)

    def _window_monitor_loop(self) -> None:
        while not self._monitor_stop.is_set():
            info = find_game_window(self.config.process_name)
            with self._window_info_lock:
                self.latest_window_info = info
            if info is not None:
                self.set_region(info.left, info.top, info.width, info.height)
                self.macro_engine._current_window = WindowContext(
                    left=info.left,
                    top=info.top,
                    width=info.width,
                    height=info.height,
                    title_bar_height=info.title_bar_height,
                    hwnd=info.hwnd,
                )
                if self.config.preview_enabled:
                    self.start_frame_producer()
            else:
                self.stop_frame_producer()
            self._monitor_stop.wait(1.0)

    def stop(self, timeout: float = 2.5) -> None:
        self._stop_event.set()
        self.macro_engine.stop()
        if (
            self._thread is not None
            and self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("BotRunner worker thread did not terminate within %.1fs", timeout)


    def shutdown(self) -> None:
        self.stop()
        self.stop_window_monitor()
        self._frame_producer.stop()
        self.anti_detect.stop()
        with contextlib.suppress(OSError):
            self.capture.stop()
        self.clicker.shutdown()
        self.sleep_guard.shutdown()
        step_logger = getattr(self, "_step_logger", None)
        if step_logger is not None and hasattr(step_logger, "close"):
            with contextlib.suppress(OSError):
                step_logger.close()
        logger.info("BotRunner shut down")

    def set_region(
        self, window_left: int, window_top: int, window_width: int, window_height: int
    ) -> None:
        result = get_monitor_for_window(window_left, window_top, window_width, window_height)
        if result is not None:
            output_idx, monitor_region = result
            self.capture.set_output(output_idx)
            self.capture.region = monitor_region
        else:
            self.capture.set_output(0)
            self.capture.region = (
                window_left,
                window_top,
                window_left + window_width,
                window_top + window_height,
            )

    def start_frame_producer(self) -> None:
        if self.capture.region is None:
            logger.debug("Skipping frame producer start: no capture region set")
            return
        self.capture.start()
        self._frame_producer.start()

    def stop_frame_producer(self) -> None:
        self._frame_producer.stop()

    def set_preview_enabled(self, enabled: bool) -> None:
        if enabled:
            self.start_frame_producer()
        else:
            self.stop_frame_producer()

    def set_preview_scale(self, scale: float) -> None:
        self._frame_producer.set_scale(scale)

    def apply_config(self) -> None:
        self.macro = build_helicopter_macro(self.config)
        self._listen_step = self.macro.steps[0]
        self.clicker.min_delay_ms = self.config.click_min_delay_ms
        self.clicker.max_delay_ms = self.config.click_max_delay_ms
        self.clicker.spam_noise_px = self.config.spam_noise_px
        self.clicker.click_jitter_ms = self.config.click_jitter_ms
        self.macro_engine._current_macro = self.macro

        self._frame_producer.set_fps(self.config.scan_fps)
        self._frame_producer.set_scale(self.config.preview_scale)

        self._apply_anti_sleep()
        self._apply_anti_detect()
        self._apply_verbose()

        self.clicker.process_name = self.config.process_name

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    MAX_CONSECUTIVE_FAILURES = 20

    def _main_loop(self) -> None:
        consecutive_failures = 0
        iterations = 0
        session_start = time.monotonic()

        while not self._stop_event.is_set():
            iterations += 1
            if self.config.max_iterations > 0 and iterations > self.config.max_iterations:
                logger.info(
                    "Bot session iteration limit reached: %d",
                    self.config.max_iterations,
                )
                break
            if (
                self.config.max_runtime_s > 0
                and (time.monotonic() - session_start) >= self.config.max_runtime_s
            ):
                logger.info(
                    "Bot session runtime limit reached: %.1fs",
                    self.config.max_runtime_s,
                )
                break

            window_info = find_game_window(self.config.process_name)
            if window_info is None:
                with self._window_info_lock:
                    self.latest_window_info = None
                logger.warning("Game window not found; retrying in 3s")
                if self._stop_event.wait(3.0):
                    break
                continue

            with self._window_info_lock:
                self.latest_window_info = window_info
            self.set_region(
                window_info.left, window_info.top, window_info.width, window_info.height
            )
            window = WindowContext(
                left=window_info.left,
                top=window_info.top,
                width=window_info.width,
                height=window_info.height,
                title_bar_height=window_info.title_bar_height,
                hwnd=window_info.hwnd,
            )
            logger.info(
                "Running macro on window '%s' (%dx%d)",
                window_info.title,
                window_info.width,
                window_info.height,
            )

            try:
                result = self.macro_engine.run(self.macro, window)
            except Exception as exc:
                consecutive_failures += 1
                logger.warning(
                    "Macro iteration failed (%d/%d): %s",
                    consecutive_failures,
                    self.MAX_CONSECUTIVE_FAILURES,
                    exc,
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    logger.error(
                        "Bot aborted: %d consecutive macro failures — "
                        "check the game window, drivers and logs.",
                        consecutive_failures,
                    )
                    break
                if self._stop_event.wait(1.0):
                    break
                wait_time = min(1.0 * (1.5 ** min(consecutive_failures, 6)), 10.0)
                if self._stop_event.wait(wait_time):
                    break
                continue

            if result.success:
                logger.info("Macro completed successfully")
                consecutive_failures = 0
            else:
                logger.warning("Macro finished with error: %s", result.error)

            self.macro_engine.reset()
            if self._stop_event.wait(1.0):
                break