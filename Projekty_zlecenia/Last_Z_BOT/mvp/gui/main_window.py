from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from mvp.bot.hwid import get_hwid
from mvp.bot.monitor_mapper import validate_environment
from mvp.bot.runner import BotRunner
from mvp.config import MVPConfig
from mvp.gui.state import GuiState
from mvp.license import check_license

PREVIEW_WIDTH = 960
PREVIEW_HEIGHT = 540


def bgr_to_rgba_texture(
    frame: np.ndarray,
    out: np.ndarray | None = None,
    u8_out: np.ndarray | None = None,
) -> np.ndarray:
    h, w = frame.shape[:2]
    if out is None or out.shape != (h, w, 4):
        out = np.empty((h, w, 4), dtype=np.float32)

    if u8_out is None or u8_out.shape != (h, w, 4):
        u8_out = np.empty((h, w, 4), dtype=np.uint8)

    if frame.shape[2] == 3:
        cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA, dst=u8_out)
        np.multiply(u8_out, np.float32(1.0 / 255.0), out=out, dtype=np.float32)
    elif frame.shape[2] == 4:
        cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA, dst=u8_out)
        np.multiply(u8_out, np.float32(1.0 / 255.0), out=out, dtype=np.float32)
    return out


logger = logging.getLogger(__name__)


class MainWindow:
    def __init__(
        self,
        config: MVPConfig,
        state: GuiState,
        bot_runner: BotRunner | None = None,
        window_info: object | None = None,
    ) -> None:
        self.config = config
        self.state = state
        self.bot_runner = bot_runner
        self.window_info = window_info
        self._running = False
        self._phase: str = ""
        self._preview_w = PREVIEW_WIDTH
        self._preview_h = PREVIEW_HEIGHT
        self._tex_w = PREVIEW_WIDTH
        self._tex_h = PREVIEW_HEIGHT
        self._preview_dirty = False
        self._preview_last_change = 0.0
        self._last_texture_update = 0.0
        self._rgba_buffer: np.ndarray | None = None
        self._u8_buffer: np.ndarray | None = None
        self._is_starting_bot: bool = False
        self._is_stopping_bot: bool = False
        self._start_abort_event: threading.Event = threading.Event()
        self._hotkeys: list = []
        self._log_history: deque[str] = deque(maxlen=500)
        self._log_text: str = ""
        self._last_log_update = 0.0
        self._log_dirty = False
        self._cached_game_status: tuple[bool, str] | None = None
        self._cached_env_window_size: tuple[int, int] | None = None
        self._cached_status_state: str | None = None
        self._cached_dash_stats: tuple | None = None
        self._cached_time_str: str | None = None
        self._last_dash_update = 0.0

        from mvp.bot.event_log import EventLogger

        self._event_logger = EventLogger(config.log_dir, config.log_to_file)
        self._event_log_last_flush = 0.0
        self._event_log_flush_in_progress: bool = False

        from mvp.gui.viewport_state import ViewportState, load_viewport_state

        self._viewport_state_path = self._default_viewport_state_path()
        loaded_vp = load_viewport_state(self._viewport_state_path)
        self._initial_viewport_state = loaded_vp or ViewportState(
            width=1920, height=1080, maximized=False
        )

        from mvp.bot.crash import CrashHandler

        self._crash_handler = CrashHandler(app_version=self.config.app_version)

    def setup(self) -> None:
        dpg.create_context()
        dpg.create_viewport(
            title="Last Z Bot",
            width=self._initial_viewport_state.width,
            height=self._initial_viewport_state.height,
            min_width=1600,
            min_height=950,
            clear_color=(24, 24, 27),
        )
        dpg.setup_dearpygui()

        from mvp.gui.viewport_state import validate_viewport_state as _validate_vp

        vp = self._initial_viewport_state
        if _validate_vp(vp, dpg.get_viewport_width(), dpg.get_viewport_height()):
            if vp.x is not None and vp.y is not None:
                with contextlib.suppress(Exception):
                    dpg.set_viewport_pos([vp.x, vp.y])
            if vp.maximized:
                with contextlib.suppress(Exception):
                    dpg.maximize_viewport()

        self._load_fonts()
        self._create_themes()
        self._register_textures()
        self._build_ui()
        self._populate_gui_from_config()

        if self.bot_runner is not None:
            self.bot_runner.macro_engine.step_callback = self._on_step_event

        from mvp.gui.log_handler import GuiLogHandler

        gui_handler = GuiLogHandler(
            self.state, level=logging.DEBUG if self.config.log_verbose else logging.INFO
        )
        gui_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", "%H:%M:%S")
        )
        logging.getLogger().addHandler(gui_handler)
        self._gui_log_handler = gui_handler

        self._crash_handler.install()

        if self.window_info is not None:
            self.set_game_status(True, f"{self.window_info.width}x{self.window_info.height}")

        dpg.set_exit_callback(self._on_close)

        dpg.show_viewport()
        self._register_hotkeys()

    def _default_viewport_state_path(self) -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "LastZBot" / "viewport.json"
        return Path.cwd() / "viewport.json"


    def _build_ui(self) -> None:
        with dpg.window(
            tag="main_window",
            no_title_bar=False,
            no_collapse=True,
            no_close=True,
            no_scrollbar=True,
            no_resize=True,
        ):
            dpg.set_primary_window("main_window", True)
            dpg.bind_item_theme("main_window", "global_theme")
            with (
                dpg.child_window(height=-34, no_scrollbar=True, border=False),
                dpg.tab_bar(tag="main_tab_bar"),
            ):
                self._build_dashboard_tab()
                self._build_config_tab()
                self._build_logs_tab()
            self._build_status_bar()

    def _build_dashboard_tab(self) -> None:
        with dpg.tab(label="DASHBOARD", tag="tab_dashboard"), dpg.group(horizontal=True):
            with dpg.child_window(
                width=280,
                height=-1,
                border=True,
                no_scrollbar=True,
                tag="dash_left_panel",
            ):
                dpg.add_spacer(height=8)
                dpg.add_button(
                    label="START",
                    tag="start_btn",
                    width=220,
                    height=48,
                    callback=self._on_start_stop,
                )
                dpg.bind_item_theme("start_btn", "btn_primary_theme")
                dpg.add_spacer(height=16)

                dpg.add_text("Game", color=(250, 250, 250))
                dpg.add_separator()
                dpg.add_spacer(height=4)
                dpg.add_text("Status:", color=(161, 161, 170))
                dpg.add_text("No game window", tag="game_status_text", color=(239, 68, 68))
                dpg.add_text("Resolution:", color=(161, 161, 170))
                dpg.add_text("-", tag="game_res_text", color=(161, 161, 170))
                dpg.add_spacer(height=8)

                dpg.add_text("Środowisko:", color=(250, 250, 250))
                dpg.add_separator()
                dpg.add_text(
                    "OK",
                    tag="env_status_text",
                    color=(34, 197, 94),
                    wrap=250,
                )
                dpg.add_spacer(height=12)

                dpg.add_text("Macro progress", color=(250, 250, 250))
                dpg.add_separator()
                dpg.add_spacer(height=4)
                dpg.add_progress_bar(
                    tag="macro_progress_bar", default_value=0.0, width=220, overlay="0/0"
                )
                dpg.add_text("-", tag="step_value_text", color=(245, 158, 11))
                dpg.add_spacer(height=12)

                dpg.add_text("Timer phase", color=(250, 250, 250))
                dpg.add_separator()
                dpg.add_spacer(height=4)
                dpg.add_text("-", tag="phase_text", color=(245, 158, 11))
                dpg.add_text("Timer:", color=(161, 161, 170))
                dpg.add_text("-", tag="timer_value_text", color=(161, 161, 170))
                dpg.add_spacer(height=12)

                dpg.add_text("Session stats", color=(250, 250, 250))
                dpg.add_separator()
                dpg.add_spacer(height=4)
                dpg.add_text("Clicks:", color=(161, 161, 170))
                dpg.add_text("0", tag="stats_clicks_text", color=(161, 161, 170))
                dpg.add_text("Alerts:", color=(161, 161, 170))
                dpg.add_text("0", tag="stats_alerts_text", color=(161, 161, 170))
                dpg.add_text("Errors:", color=(161, 161, 170))
                dpg.add_text("0", tag="stats_errors_text", color=(161, 161, 170))
                dpg.add_text("Session time:", color=(161, 161, 170))
                dpg.add_text("00:00", tag="stats_time_text", color=(161, 161, 170))
                dpg.add_spacer(height=12)

            with dpg.child_window(
                width=-1,
                height=-1,
                border=True,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
                tag="dash_main_panel",
            ):
                dpg.add_spacer(height=8)
                dpg.add_text("Game preview", color=(250, 250, 250))
                dpg.add_separator()
                dpg.add_image(
                    "frame_texture",
                    width=self._preview_w,
                    height=self._preview_h,
                    tag="dash_preview_image",
                )
                dpg.add_spacer(height=8)
                dpg.add_checkbox(
                    label="Enable game preview",
                    default_value=self.config.preview_enabled,
                    tag="preview_enabled",
                    callback=self._on_preview_settings_changed,
                )
                dpg.add_slider_float(
                    label="Preview scale",
                    default_value=self.config.preview_scale,
                    min_value=0.1,
                    max_value=1.0,
                    tag="preview_scale",
                    width=300,
                    callback=self._on_preview_settings_changed,
                )

    def _build_config_tab(self) -> None:
        with (
            dpg.tab(label="CONFIGURATION", tag="tab_config"),
            dpg.child_window(border=True, no_scrollbar=False, tag="tab_config_pane"),
        ):
            dpg.add_spacer(height=8)

            with dpg.collapsing_header(label="Game & capture", default_open=True) as h1:
                dpg.bind_item_theme(h1, "collapsing_section_theme")
                self._add_config_input_int(
                    "Scan FPS", self.config.scan_fps, 1, 60, "scan_fps", 300
                )
                self._add_config_tooltip(
                    "scan_fps",
                    "How many times per second the bot reads the game window image. "
                    "Higher value = faster response, but higher CPU load.",
                )

            with dpg.collapsing_header(label="Clicking", default_open=True) as h2:
                dpg.bind_item_theme(h2, "collapsing_section_theme")
                self._add_config_input_int(
                    "Min delay (ms)",
                    self.config.click_min_delay_ms,
                    0,
                    5000,
                    "click_min_delay",
                    300,
                )
                self._add_config_tooltip(
                    "click_min_delay",
                    "Minimum delay between consecutive single clicks (e.g. menu/chat navigation). "
                    "Does not apply to the spam phase (controlled by CPS).",
                )
                self._add_config_input_int(
                    "Max delay (ms)",
                    self.config.click_max_delay_ms,
                    0,
                    5000,
                    "click_max_delay",
                    300,
                )
                self._add_config_tooltip(
                    "click_max_delay",
                    "Maximum delay between general clicks. The actual value "
                    "is randomized within the min–max range so movement looks natural.",
                )
                self._add_config_input_float(
                    "Click jitter (ms)",
                    self.config.click_jitter_ms,
                    0.0,
                    50.0,
                    "click_jitter",
                    300,
                )
                self._add_config_input_float(
                    "Spam noise (px)",
                    self.config.spam_noise_px,
                    0.0,
                    20.0,
                    "spam_noise",
                    300,
                )
                self._add_config_tooltip(
                    "spam_noise",
                    "Click separation amplitude during the spam phase. Consecutive clicks "
                    "are offset by ~2.83x this value to keep them >5 px apart so the game "
                    "does not merge them into a double-click. Keep it low enough to stay "
                    "inside the box collider.",
                )

            with dpg.collapsing_header(label="Countdown phase (timer)", default_open=True) as h3:
                dpg.bind_item_theme(h3, "collapsing_section_theme")
                self._add_config_input_int(
                    "CPS in spam phase (clicks/s)",
                    self.config.spam_clicks_per_sec,
                    1,
                    35,
                    "spam_clicks_per_sec",
                    300,
                )
                self._add_config_tooltip(
                    "spam_clicks_per_sec",
                    "Click rate during the final countdown phase (maximum 35 clicks/s at 60 FPS).",
                )
                self._add_config_input_int(
                    "Spam phase threshold (s)",
                    self.config.spam_threshold_s,
                    1,
                    3600,
                    "spam_threshold",
                    300,
                )
                self._add_config_tooltip(
                    "spam_threshold",
                    "When the counter drops below this many seconds, the bot enters "
                    "the rapid-click (spam) phase.",
                )
                self._add_config_input_float(
                    "Spam duration (s)",
                    self.config.spam_duration_s,
                    0.1,
                    60.0,
                    "spam_duration",
                    300,
                )
                self._add_config_tooltip(
                    "spam_duration",
                    "How long the bot clicks during the spam phase (in seconds).",
                )
                self._add_config_input_int(
                    "Fast phase threshold (s)",
                    self.config.fast_threshold_s,
                    1,
                    3600,
                    "fast_threshold",
                    300,
                )
                self._add_config_tooltip(
                    "fast_threshold",
                    "When the counter drops below this value, the bot speeds up "
                    "timer checks (fast phase).",
                )
                self._add_config_input_float(
                    "Normal OCR scan (s)",
                    self.config.idle_check_interval_s,
                    0.05,
                    60.0,
                    "idle_check_interval",
                    300,
                )
                self._add_config_tooltip(
                    "idle_check_interval",
                    "Interval between timer reads when the counter is far from the end (idle phase).",
                )
                self._add_config_input_float(
                    "Fast OCR scan (s)",
                    self.config.fast_check_interval_s,
                    0.05,
                    5.0,
                    "fast_check_interval",
                    300,
                )
                self._add_config_tooltip(
                    "fast_check_interval",
                    "Interval between timer reads in the fast phase (shorter = faster response).",
                )
                self._add_config_input_float(
                    "Helicopter wait timeout (s)",
                    self.config.watch_timer_timeout_s,
                    10.0,
                    3600.0,
                    "watch_timer_timeout_s",
                    300,
                )
                self._add_config_tooltip(
                    "watch_timer_timeout_s",
                    "Maximum idle time — no counter or a stuck counter (in seconds, default 1800s = 30 min). An active countdown is not interrupted.",
                )

            with dpg.collapsing_header(
                label="Camera zoom (Helicopter)", default_open=True
            ) as h_zoom:
                dpg.bind_item_theme(h_zoom, "collapsing_section_theme")
                self._add_config_input_int(
                    "Mouse wheel ticks (zoom)",
                    self.config.zoom_scroll_ticks,
                    1,
                    100,
                    "zoom_scroll_ticks",
                    300,
                )
                self._add_config_tooltip(
                    "zoom_scroll_ticks",
                    "How many mouse wheel ticks the bot sends to fully "
                    "zoom the camera on the helicopter (Step 6b). Default 25.",
                )
                self._add_config_input_float(
                    "Wheel interval (s)",
                    self.config.zoom_scroll_interval_s,
                    0.005,
                    1.0,
                    "zoom_scroll_interval_s",
                    300,
                )
                self._add_config_tooltip(
                    "zoom_scroll_interval_s",
                    "Time gap between consecutive mouse wheel ticks.",
                )

            with dpg.collapsing_header(
                label="Chat scanning (Auto-arrow)", default_open=True
            ) as h_scroll:
                dpg.bind_item_theme(h_scroll, "collapsing_section_theme")
                self._add_config_input_float(
                    "Arrow detection threshold",
                    self.config.chat_arrow_threshold,
                    0.1,
                    1.0,
                    "chat_arrow_threshold",
                    300,
                )
                self._add_config_tooltip(
                    "chat_arrow_threshold",
                    "Minimal match coefficient for the chat arrow template (0.1 - 1.0).",
                )
                self._add_config_input_float(
                    "Pause after arrow click (s)",
                    self.config.chat_arrow_delay_s,
                    0.05,
                    2.0,
                    "chat_arrow_delay_s",
                    300,
                )
                self._add_config_tooltip(
                    "chat_arrow_delay_s",
                    "Time to wait for the view to scroll after clicking the arrow.",
                )

            with dpg.collapsing_header(label="Keyboard shortcuts", default_open=True) as h_hotkeys:
                dpg.bind_item_theme(h_hotkeys, "collapsing_section_theme")
                self._add_config_input_text(
                    "Hotkey spam (F1)", self.config.hotkey_spam, "hotkey_spam", 300
                )
                self._add_config_tooltip(
                    "hotkey_spam",
                    "Hotkey to instantly trigger click spam. Supported: F1-F12 and single letters A-Z.",
                )
                self._add_config_input_text(
                    "Hotkey START/STOP", self.config.hotkey_start_stop, "hotkey_start_stop", 300
                )
                self._add_config_tooltip(
                    "hotkey_start_stop",
                    "Hotkey to start/stop the bot. Supported: F1-F12 and single letters A-Z.",
                )
                self._add_config_input_text(
                    "Hotkey emergency", self.config.hotkey_emergency, "hotkey_emergency", 300
                )
                self._add_config_tooltip(
                    "hotkey_emergency",
                    "Emergency instant stop of the bot. Supported: F1-F12 and single letters A-Z.",
                )

            with dpg.collapsing_header(label="Notifications", default_open=True) as h_notify:
                dpg.bind_item_theme(h_notify, "collapsing_section_theme")
                dpg.add_checkbox(
                    label="Play sound on helicopter alert",
                    default_value=self.config.notify_enabled,
                    tag="notify_enabled",
                )
                self._add_config_input_text(
                    "Sound path (empty=beep)",
                    self.config.notify_sound_path,
                    "notify_sound_path",
                    300,
                )

            with dpg.collapsing_header(label="Power protection (Anti-sleep)", default_open=False) as h_sleep:
                dpg.bind_item_theme(h_sleep, "collapsing_section_theme")
                dpg.add_checkbox(
                    label="Block system sleep",
                    default_value=self.config.prevent_sleep,
                    tag="prevent_sleep",
                )
                dpg.add_checkbox(
                    label="Block display turn-off",
                    default_value=self.config.prevent_display_off,
                    tag="prevent_display_off",
                )

            with dpg.collapsing_header(label="Anti-detect", default_open=False) as h_antidetect:
                dpg.bind_item_theme(h_antidetect, "collapsing_section_theme")
                dpg.add_checkbox(
                    label="Debugger detection",
                    default_value=self.config.anti_detect_enabled,
                    tag="anti_detect_enabled",
                )
                self._add_config_input_float(
                    "Check interval (s)",
                    self.config.anti_detect_check_interval_s,
                    1.0,
                    300.0,
                    "anti_detect_check_interval_s",
                    300,
                )

            with dpg.collapsing_header(label="Details window recovery", default_open=False) as h_details:
                dpg.bind_item_theme(h_details, "collapsing_section_theme")
                dpg.add_checkbox(
                    label="Auto-close Details window",
                    default_value=self.config.details_recovery_enabled,
                    tag="details_recovery_enabled",
                )
                self._add_config_input_float(
                    "Shutdown delay (s)",
                    self.config.details_dismiss_delay_s,
                    0.0,
                    60.0,
                    "details_dismiss_delay_s",
                    300,
                )

            with dpg.collapsing_header(label="Session limits", default_open=False) as h_limits:
                dpg.bind_item_theme(h_limits, "collapsing_section_theme")
                self._add_config_input_int(
                    "Max iterations (0=none)",
                    self.config.max_iterations,
                    0,
                    100000,
                    "max_iterations",
                    300,
                )
                self._add_config_input_float(
                    "Max runtime (s, 0=none)",
                    self.config.max_runtime_s,
                    0.0,
                    864000.0,
                    "max_runtime_s",
                    300,
                )

            with dpg.collapsing_header(label="Event logging", default_open=False) as h_log:
                dpg.bind_item_theme(h_log, "collapsing_section_theme")
                dpg.add_checkbox(
                    label="Save events to file",
                    default_value=self.config.log_to_file,
                    tag="log_to_file",
                )
                dpg.add_checkbox(
                    label="Verbose DEBUG logs",
                    default_value=self.config.log_verbose,
                    tag="log_verbose",
                )
                self._add_config_input_text("Log directory", self.config.log_dir, "log_dir", 300)

            with dpg.collapsing_header(label="License (PROD)", default_open=False) as h_license:
                dpg.bind_item_theme(h_license, "collapsing_section_theme")
                self._add_config_input_text(
                    "Backend URL", self.config.backend_url, "backend_url", 400
                )
                self._add_config_input_text(
                    "License key", self.config.license_key, "license_key", 400
                )
                dpg.add_button(
                    label="Activate",
                    tag="license_activate_btn",
                    width=140,
                    callback=self._on_activate_license,
                )
                dpg.add_text("", tag="license_status_text", color=(161, 161, 170))

            dpg.add_spacer(height=12)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save", tag="config_save_btn", width=120, callback=self._on_save_config
                )
                dpg.add_button(
                    label="Restore defaults",
                    tag="config_reset_btn",
                    width=160,
                    callback=self._on_reset_config,
                )
            dpg.add_text("", tag="config_status_text", color=(161, 161, 170))


    def _add_config_input_text(self, label: str, default: str, tag: str, width: int) -> None:
        dpg.add_input_text(label=label, default_value=default, tag=tag, width=width)

    def _add_config_input_int(
        self, label: str, default: int, lo: int, hi: int, tag: str, width: int
    ) -> None:
        dpg.add_input_int(
            label=label, default_value=default, min_value=lo, max_value=hi, tag=tag, width=width
        )

    def _add_config_input_float(
        self, label: str, default: float, lo: float, hi: float, tag: str, width: int
    ) -> None:
        dpg.add_input_float(
            label=label, default_value=default, min_value=lo, max_value=hi, tag=tag, width=width
        )

    def _add_config_tooltip(self, parent_tag: str, text: str) -> None:
        with dpg.tooltip(parent_tag):
            dpg.add_text(text, wrap=320)

    def _build_logs_tab(self) -> None:
        with (
            dpg.tab(label="LOGS", tag="tab_logs"),
            dpg.child_window(border=False, no_scrollbar=True, tag="tab_logs_panel"),
        ):
            dpg.add_text("Log console:")
            log = dpg.add_input_text(
                tag="log_output",
                multiline=True,
                readonly=True,
                width=-1,
                height=-1,
            )
            dpg.bind_item_theme(log, "log_console_theme")

    def _build_status_bar(self) -> None:
        with dpg.child_window(height=30, no_scrollbar=True, border=False, tag="status_bar"):
            dpg.bind_item_theme("status_bar", "statusbar_theme")
            with dpg.group(horizontal=True):
                dpg.add_text("●", tag="statusbar_dot", color=(239, 68, 68))
                dpg.add_text("STOPPED", tag="statusbar_bot_state", color=(239, 68, 68))
                dpg.add_spacer(width=24)
                dpg.add_text("Game:", color=(161, 161, 170))
                dpg.add_text("Searching...", tag="statusbar_game", color=(245, 158, 11))


    def _register_hotkeys(self) -> None:
        from mvp.gui.global_hotkey import GlobalHotkey, parse_key

        for hotkey in self._hotkeys:
            hotkey.stop()
        self._hotkeys = []
        bindings = [
            (self.config.hotkey_spam, self._on_global_spam_hotkey, 1),
            (self.config.hotkey_start_stop, self._on_start_stop_hotkey, 2),
            (self.config.hotkey_emergency, self._on_emergency_stop_hotkey, 3),
        ]
        for name, callback, hotkey_id in bindings:
            try:
                vk = parse_key(name)
            except ValueError as exc:
                logger.warning("Invalid hotkey %s: %s", name, exc)
                continue
            hotkey = GlobalHotkey(vk=vk, callback=callback, hotkey_id=hotkey_id)
            hotkey.start()
            self._hotkeys.append(hotkey)

    def _on_global_spam_hotkey(self) -> None:
        if self.bot_runner is None:
            return
        engine = self.bot_runner.macro_engine
        if hasattr(engine, "trigger_spam"):
            engine.trigger_spam()

    def _on_emergency_stop_hotkey(self) -> None:
        """Hotkey entry point (fires on the GlobalHotkey thread); defer to GUI loop."""
        self.state.push_ui("command_emergency_stop")

    def _on_emergency_stop(self) -> None:
        if self.bot_runner is not None:
            self.bot_runner.stop()
        self.state.running = False
        self._phase = ""
        # Reset the start button and phase text so the UI does not stay stuck on
        # "STOP"/"SPAM" after an emergency stop (mirrors the stop_done event path).
        dpg.set_value("phase_text", "-")
        dpg.configure_item("start_btn", label="START")
        dpg.bind_item_theme("start_btn", "btn_primary_theme")
        logger.info("Emergency stop triggered via hotkey")

    def _on_start_stop_hotkey(self) -> None:
        """Hotkey entry point (fires on the GlobalHotkey thread); defer to GUI loop."""
        self.state.push_ui("command_start_stop")

    def _on_start_stop(self) -> None:
        if self.bot_runner is None:
            logger.error("BotRunner not initialized")
            return

        if self._is_starting_bot and not self._is_stopping_bot:
            logger.info("[GUI] Aborting bot startup...")
            self._start_abort_event.set()
            self.state.push_ui("start_abort")
            return

        if not self.bot_runner.is_running and not self._is_starting_bot and not self._is_stopping_bot:
            self.config.backend_url = str(dpg.get_value("backend_url")).strip()
            self.config.license_key = str(dpg.get_value("license_key")).strip()
            if not self._license_ok():
                return

            self._is_starting_bot = True
            self._start_abort_event.clear()
            self.state.push_ui("start_begin")

            def _start_worker() -> None:
                try:
                    logger.info("[GUI] Starting bot...")
                    self.bot_runner.start()
                    if self._start_abort_event.is_set():
                        logger.info("[GUI] Startup aborted by user — stopping bot immediately...")
                        self.bot_runner.stop()
                        return
                    self.bot_runner.macro_engine.reset_session_stats()
                    self.state.push_ui("start_success")
                except Exception as exc:
                    logger.error("Failed to start bot: %s", exc, exc_info=True)
                    self.state.push_ui("start_error", error=str(exc))
                finally:
                    self._is_starting_bot = False

            threading.Thread(target=_start_worker, daemon=True, name="bot-starter").start()
        elif self.bot_runner.is_running and not self._is_stopping_bot:
            self._start_abort_event.set()
            self._is_starting_bot = False
            self._is_stopping_bot = True
            self.state.push_ui("stop_begin")

            def _stop_worker() -> None:
                try:
                    logger.info("[GUI] Stopping bot...")
                    self.bot_runner.stop()
                except Exception as exc:
                    logger.error("Failed to stop bot: %s", exc, exc_info=True)
                finally:
                    self._is_stopping_bot = False
                    self.state.push_ui("stop_done")

            threading.Thread(target=_stop_worker, daemon=True, name="bot-stopper").start()


    def _on_preview_settings_changed(self, *args) -> None:
        self.config.preview_enabled = bool(dpg.get_value("preview_enabled"))
        self.config.preview_scale = float(dpg.get_value("preview_scale"))
        if self.bot_runner is not None:
            self.bot_runner.set_preview_scale(self.config.preview_scale)
            self.bot_runner.set_preview_enabled(self.config.preview_enabled)
        self._preview_dirty = True
        self._preview_last_change = time.monotonic()

    def _on_save_config(self) -> None:
        self._collect_config_from_gui()
        valid, errors = self.config.validate()
        if not valid:
            for err in errors:
                logger.warning("Config validation error: %s", err)
            self._set_config_status("Error: " + errors[0], (239, 68, 68))
            return
        self.config.save(Path("config.json"))
        if self.bot_runner is not None:
            self.bot_runner.config = self.config
            self.bot_runner.set_preview_scale(self.config.preview_scale)
            if self.config.preview_enabled:
                self.bot_runner.start_frame_producer()
            else:
                self.bot_runner.stop_frame_producer()
            self.bot_runner.apply_config()
        if getattr(self, "_gui_log_handler", None) is not None:
            self._gui_log_handler.setLevel(
                logging.DEBUG if self.config.log_verbose else logging.INFO
            )
        self._register_hotkeys()
        self._set_config_status("Saved successfully", (34, 197, 94))
        logger.info("Config saved to config.json")

    def _license_ok(self) -> bool:
        try:
            check_license(self.config.backend_url, self.config.license_key, get_hwid())
            dpg.set_value("license_status_text", "License active")
            dpg.configure_item("license_status_text", color=(34, 197, 94))
            return True
        except Exception as exc:
            logger.error("License check failed: %s", exc)
            with contextlib.suppress(Exception):
                dpg.set_value("license_status_text", f"Error: {exc}")
                dpg.configure_item("license_status_text", color=(239, 68, 68))
            return False

    def _on_activate_license(self) -> None:
        self._collect_config_from_gui()
        if not self._license_ok():
            return
        self.config.save(Path("config.json"))
        logger.info("License activated and saved to config.json")

    def _on_reset_config(self) -> None:
        self.config = MVPConfig.default()
        self._populate_gui_from_config()
        self.config.save(Path("config.json"))
        if self.bot_runner is not None:
            self.bot_runner.config = self.config
            self.bot_runner.set_preview_scale(self.config.preview_scale)
            self.bot_runner.set_preview_enabled(self.config.preview_enabled)
            self.bot_runner.apply_config()
        if getattr(self, "_gui_log_handler", None) is not None:
            self._gui_log_handler.setLevel(
                logging.DEBUG if self.config.log_verbose else logging.INFO
            )
        self._register_hotkeys()
        self._set_config_status("Restored defaults", (34, 197, 94))
        logger.info("Config reset to defaults")

    def _set_config_status(self, text: str, color: tuple) -> None:
        dpg.set_value("config_status_text", text)
        dpg.configure_item("config_status_text", color=color)

    def _on_step_event(self, event: str, step_num: int, step, **kwargs) -> None:
        self._event_logger.log(event, {"step": step_num, "label": getattr(step, "label", "")})
        self.state.push_ui(event, step_num, step, **kwargs)

    def _apply_ui_event(self, event: str, step_num=None, step=None, **kwargs) -> None:
        if event == "command_start_stop":
            self._on_start_stop()
            return
        if event == "command_emergency_stop":
            self._on_emergency_stop()
            return
        if event == "running":
            dpg.set_value("step_value_text", step.label)
        elif event == "phase_transition":
            self._phase = kwargs.get("phase", "")
            dpg.set_value("phase_text", self._phase.upper())
            if self._phase == "spam":
                dpg.configure_item("phase_text", color=(34, 197, 94))
                from mvp.gui.notify import notify_alert

                notify_alert(self.config.notify_enabled, self.config.notify_sound_path)
            elif self._phase == "fast":
                dpg.configure_item("phase_text", color=(245, 158, 11))
            else:
                dpg.configure_item("phase_text", color=(245, 158, 11))
        elif event == "start_begin":
            dpg.configure_item("start_btn", label="STARTING...")
            dpg.bind_item_theme("start_btn", "btn_primary_theme")
        elif event == "start_abort":
            dpg.configure_item("start_btn", label="ABORTING...")
        elif event == "start_success":
            self.state.running = True
            self._reset_dashboard_stats()
            dpg.configure_item("start_btn", label="STOP")
            dpg.bind_item_theme("start_btn", "btn_success_theme")
        elif event == "start_error":
            dpg.set_value("step_value_text", f"Error: {kwargs.get('error', '')}")
            dpg.configure_item("step_value_text", color=(239, 68, 68))
            dpg.configure_item("start_btn", label="START")
            dpg.bind_item_theme("start_btn", "btn_primary_theme")
        elif event == "stop_begin":
            dpg.configure_item("start_btn", label="STOPPING...")
            dpg.bind_item_theme("start_btn", "btn_primary_theme")
        elif event == "stop_done":
            self.state.running = False
            self._phase = ""
            dpg.set_value("phase_text", "-")
            dpg.configure_item("start_btn", label="START")
            dpg.bind_item_theme("start_btn", "btn_primary_theme")

    def _on_close(self) -> None:
        self._running = False
        self.state.running = False
        self._crash_handler.uninstall()
        if self.bot_runner is not None and self.bot_runner.is_running:
            self.bot_runner.stop()

    def _save_viewport_state(self) -> None:
        try:
            from mvp.bot.monitor_mapper import get_primary_monitor_size
            from mvp.gui.viewport_state import ViewportState, save_viewport_state

            pos = dpg.get_viewport_pos()
            w = dpg.get_viewport_width()
            h = dpg.get_viewport_height()
            if w > 0 and h > 0:
                mon_size = get_primary_monitor_size()
                maximized = (
                    mon_size is not None
                    and int(w) == mon_size[0]
                    and int(h) == mon_size[1]
                )
                state = ViewportState(
                    x=int(pos[0]),
                    y=int(pos[1]),
                    width=int(w),
                    height=int(h),
                    maximized=maximized,
                )
                save_viewport_state(self._viewport_state_path, state)
        except Exception as exc:
            logger.debug("Failed to save viewport state: %s", exc)


    def _populate_gui_from_config(self) -> None:
        dpg.set_value("scan_fps", self.config.scan_fps)
        dpg.set_value("click_min_delay", self.config.click_min_delay_ms)
        dpg.set_value("click_max_delay", self.config.click_max_delay_ms)
        dpg.set_value("click_jitter", self.config.click_jitter_ms)
        dpg.set_value("spam_clicks_per_sec", self.config.spam_clicks_per_sec)
        dpg.set_value("spam_threshold", self.config.spam_threshold_s)
        dpg.set_value("spam_duration", self.config.spam_duration_s)
        dpg.set_value("idle_check_interval", self.config.idle_check_interval_s)
        dpg.set_value("fast_check_interval", self.config.fast_check_interval_s)
        dpg.set_value("fast_threshold", self.config.fast_threshold_s)
        dpg.set_value("watch_timer_timeout_s", self.config.watch_timer_timeout_s)
        dpg.set_value("chat_arrow_threshold", self.config.chat_arrow_threshold)
        dpg.set_value("chat_arrow_delay_s", self.config.chat_arrow_delay_s)
        dpg.set_value("zoom_scroll_ticks", self.config.zoom_scroll_ticks)
        dpg.set_value("zoom_scroll_interval_s", self.config.zoom_scroll_interval_s)
        dpg.set_value("preview_enabled", self.config.preview_enabled)
        dpg.set_value("preview_scale", self.config.preview_scale)
        dpg.set_value("hotkey_spam", self.config.hotkey_spam)
        dpg.set_value("hotkey_start_stop", self.config.hotkey_start_stop)
        dpg.set_value("hotkey_emergency", self.config.hotkey_emergency)
        dpg.set_value("notify_enabled", self.config.notify_enabled)
        dpg.set_value("notify_sound_path", self.config.notify_sound_path)
        dpg.set_value("prevent_sleep", self.config.prevent_sleep)
        dpg.set_value("prevent_display_off", self.config.prevent_display_off)
        dpg.set_value("anti_detect_enabled", self.config.anti_detect_enabled)
        dpg.set_value("anti_detect_check_interval_s", self.config.anti_detect_check_interval_s)
        dpg.set_value("details_recovery_enabled", self.config.details_recovery_enabled)
        dpg.set_value("details_dismiss_delay_s", self.config.details_dismiss_delay_s)
        dpg.set_value("max_iterations", self.config.max_iterations)
        dpg.set_value("max_runtime_s", self.config.max_runtime_s)
        dpg.set_value("log_to_file", self.config.log_to_file)
        dpg.set_value("log_verbose", self.config.log_verbose)
        dpg.set_value("log_dir", self.config.log_dir)
        dpg.set_value("backend_url", self.config.backend_url)
        dpg.set_value("license_key", self.config.license_key)

    def _collect_config_from_gui(self) -> None:
        self.config.scan_fps = int(dpg.get_value("scan_fps"))
        self.config.click_min_delay_ms = int(dpg.get_value("click_min_delay"))
        self.config.click_max_delay_ms = int(dpg.get_value("click_max_delay"))
        self.config.click_jitter_ms = float(dpg.get_value("click_jitter"))
        self.config.spam_noise_px = float(dpg.get_value("spam_noise"))
        self.config.spam_clicks_per_sec = int(dpg.get_value("spam_clicks_per_sec"))
        self.config.spam_threshold_s = int(dpg.get_value("spam_threshold"))
        self.config.spam_duration_s = float(dpg.get_value("spam_duration"))
        self.config.idle_check_interval_s = float(dpg.get_value("idle_check_interval"))
        self.config.fast_check_interval_s = float(dpg.get_value("fast_check_interval"))
        self.config.fast_threshold_s = int(dpg.get_value("fast_threshold"))
        self.config.watch_timer_timeout_s = float(dpg.get_value("watch_timer_timeout_s"))
        self.config.chat_arrow_threshold = float(dpg.get_value("chat_arrow_threshold"))
        self.config.chat_arrow_delay_s = float(dpg.get_value("chat_arrow_delay_s"))
        self.config.zoom_scroll_ticks = int(dpg.get_value("zoom_scroll_ticks"))
        self.config.zoom_scroll_interval_s = float(dpg.get_value("zoom_scroll_interval_s"))
        self.config.preview_enabled = bool(dpg.get_value("preview_enabled"))
        self.config.preview_scale = float(dpg.get_value("preview_scale"))
        self.config.hotkey_spam = str(dpg.get_value("hotkey_spam"))
        self.config.hotkey_start_stop = str(dpg.get_value("hotkey_start_stop"))
        self.config.hotkey_emergency = str(dpg.get_value("hotkey_emergency"))
        self.config.notify_enabled = bool(dpg.get_value("notify_enabled"))
        self.config.notify_sound_path = str(dpg.get_value("notify_sound_path"))
        self.config.prevent_sleep = bool(dpg.get_value("prevent_sleep"))
        self.config.prevent_display_off = bool(dpg.get_value("prevent_display_off"))
        self.config.anti_detect_enabled = bool(dpg.get_value("anti_detect_enabled"))
        self.config.anti_detect_check_interval_s = float(dpg.get_value("anti_detect_check_interval_s"))
        self.config.details_recovery_enabled = bool(dpg.get_value("details_recovery_enabled"))
        self.config.details_dismiss_delay_s = float(dpg.get_value("details_dismiss_delay_s"))
        self.config.max_iterations = int(dpg.get_value("max_iterations"))
        self.config.max_runtime_s = float(dpg.get_value("max_runtime_s"))
        self.config.log_to_file = bool(dpg.get_value("log_to_file"))
        self.config.log_verbose = bool(dpg.get_value("log_verbose"))
        self.config.log_dir = str(dpg.get_value("log_dir"))
        self.config.backend_url = str(dpg.get_value("backend_url")).strip()
        self.config.license_key = str(dpg.get_value("license_key")).strip()


    def set_env_warnings(self, warnings: list[str]) -> None:
        """Wyświetla ostrzeżenia o środowisku (DPI, monitory, rozdzielczość) w GUI."""
        key = tuple(warnings)
        if getattr(self, "_cached_env_warnings", None) == key:
            return
        self._cached_env_warnings = key
        if not warnings:
            dpg.set_value("env_status_text", "OK")
            dpg.configure_item("env_status_text", color=(34, 197, 94))
            return
        text = "Uwaga:\n" + "\n".join(f"• {w}" for w in warnings)
        dpg.set_value("env_status_text", text)
        dpg.configure_item("env_status_text", color=(245, 158, 11))


    def set_game_status(self, found: bool, label: str) -> None:
        key = (found, label)
        if getattr(self, "_cached_game_status", None) == key:
            return
        self._cached_game_status = key
        if found:
            dpg.set_value("game_status_text", "Connected")
            dpg.configure_item("game_status_text", color=(34, 197, 94))
            dpg.set_value("game_res_text", label)
            dpg.configure_item("game_res_text", color=(250, 250, 250))
            dpg.set_value("statusbar_game", label)
            dpg.configure_item("statusbar_game", color=(34, 197, 94))
        else:
            dpg.set_value("game_status_text", "No game window")
            dpg.configure_item("game_status_text", color=(239, 68, 68))
            dpg.set_value("game_res_text", "-")
            dpg.configure_item("game_res_text", color=(161, 161, 170))
            dpg.set_value("statusbar_game", "Searching...")
            dpg.configure_item("statusbar_game", color=(245, 158, 11))


    def run(self) -> None:
        self._running = True
        while dpg.is_dearpygui_running() and self._running:
            self._render_loop()
            dpg.render_dearpygui_frame()
            time.sleep(0.016)

    def shutdown(self) -> None:
        self._running = False
        self._save_viewport_state()
        for hotkey in self._hotkeys:
            hotkey.stop()
        self._hotkeys = []
        if self.bot_runner:
            self.bot_runner.shutdown()
        self._crash_handler.uninstall()
        dpg.destroy_context()

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                event, args, kwargs = self.state.ui_queue.get_nowait()
            except Exception:
                break
            try:
                self._apply_ui_event(event, *args, **kwargs)
            except Exception:
                logger.error("UI event %s failed", event, exc_info=True)

    def _render_loop(self) -> None:
        self._drain_ui_queue()
        self._update_logs()
        self._update_frame_texture()
        self._update_status_bar()
        self._update_dashboard()
        self._update_game_detection()
        self._resize_dashboard_preview()
        self._flush_preview_config_if_needed()
        now = time.monotonic()
        if (
            now - self._event_log_last_flush > 5.0
            and not self._event_log_flush_in_progress
            and getattr(self._event_logger, "_buffer", None)
        ):
            self._event_log_last_flush = now
            self._event_log_flush_in_progress = True

            def _flush_worker() -> None:
                try:
                    self._event_logger.flush()
                finally:
                    self._event_log_flush_in_progress = False

            threading.Thread(target=_flush_worker, daemon=True, name="event-log-flush").start()

    def _flush_preview_config_if_needed(self) -> None:
        if not self._preview_dirty:
            return
        if time.monotonic() - self._preview_last_change < 0.5:
            return
        self._preview_dirty = False
        try:
            cfg_path = Path("config.json")
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                data["preview_enabled"] = self.config.preview_enabled
                data["preview_scale"] = self.config.preview_scale
                tmp_path = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
                tmp_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                os.replace(tmp_path, cfg_path)
            else:
                self.config.save(cfg_path)
        except Exception as exc:
            logger.debug("Failed to flush preview config: %s", exc)

    def _update_game_detection(self) -> None:
        if self.bot_runner is None:
            return
        info = self.bot_runner.latest_window_info
        if info is not None:
            label = f"{info.width}x{info.height}"
            self.set_game_status(True, label)
            # Re-waliduj środowisko tylko, gdy rozmiar okna faktycznie się zmienił
            # (np. użytkownik przeskalował okno gry lub przełączył fullscreen).
            size = (info.width, info.height)
            if size != self._cached_env_window_size:
                self._cached_env_window_size = size
                try:
                    warnings = validate_environment(info.width, info.height)
                except Exception:
                    warnings = []
                self.set_env_warnings(warnings)
        else:
            self.set_game_status(False, "-")

    def _update_logs(self) -> None:
        new_lines: list[str] = []
        while not self.state.log_queue.empty():
            try:
                msg = self.state.log_queue.get_nowait()
                self._log_history.append(msg)
                new_lines.append(msg)
            except Exception:
                break
        if new_lines:
            self._log_text = "\n".join(self._log_history) + ("\n" if self._log_history else "")
            self._log_dirty = True

        now = time.monotonic()
        if self._log_dirty and (now - self._last_log_update >= 0.25):
            self._last_log_update = now
            self._log_dirty = False
            dpg.set_value("log_output", self._log_text)


    def _update_status_bar(self) -> None:
        actual_running = self.bot_runner.is_running if self.bot_runner is not None else False

        if self._is_starting_bot:
            if getattr(self, "_cached_status_state", None) != "STARTING":
                self._cached_status_state = "STARTING"
                dpg.set_value("statusbar_bot_state", "STARTING")
                dpg.configure_item("statusbar_bot_state", color=(245, 158, 11))
                dpg.configure_item("statusbar_dot", color=(245, 158, 11))
                dpg.configure_item("start_btn", label="STARTING...")
                dpg.bind_item_theme("start_btn", "btn_primary_theme")
            return

        if self._is_stopping_bot:
            if getattr(self, "_cached_status_state", None) != "STOPPING":
                self._cached_status_state = "STOPPING"
                dpg.set_value("statusbar_bot_state", "STOPPING")
                dpg.configure_item("statusbar_bot_state", color=(245, 158, 11))
                dpg.configure_item("statusbar_dot", color=(245, 158, 11))
                dpg.configure_item("start_btn", label="STOPPING...")
                dpg.bind_item_theme("start_btn", "btn_primary_theme")
            return

        # Detect an external stop (e.g. crash) not driven by our own workers: if the
        # bot thread is no longer running but we still think it is, reflect that once.
        if self.state.running and not actual_running:
            self.state.running = False
            self._phase = ""
            dpg.set_value("phase_text", "-")
            dpg.configure_item("start_btn", label="START")
            dpg.bind_item_theme("start_btn", "btn_primary_theme")

        state_label = "RUNNING" if self.state.running else "STOPPED"
        if getattr(self, "_cached_status_state", None) != state_label:
            self._cached_status_state = state_label
            if self.state.running:
                dpg.set_value("statusbar_bot_state", "RUNNING")
                dpg.configure_item("statusbar_bot_state", color=(34, 197, 94))
                dpg.configure_item("statusbar_dot", color=(34, 197, 94))
            else:
                dpg.set_value("statusbar_bot_state", "STOPPED")
                dpg.configure_item("statusbar_bot_state", color=(239, 68, 68))
                dpg.configure_item("statusbar_dot", color=(239, 68, 68))


    def _update_dashboard(self) -> None:
        if self.bot_runner is None:
            return

        now = time.monotonic()
        if now - self._last_dash_update < 0.1:
            return
        self._last_dash_update = now

        engine = self.bot_runner.macro_engine
        snap = engine.stats_snapshot()
        total = snap["total_steps"]
        current = snap["current_step_index"] + 1
        clicks = self.bot_runner.clicker.get_total_clicks()
        timer_val = snap["last_timer_value"]
        alerts = snap["stats_alerts"]
        errors = snap["stats_errors"]

        key = (current, total, clicks, timer_val, alerts, errors)
        if self._cached_dash_stats != key:
            self._cached_dash_stats = key
            if total > 0:
                progress = current / total
                dpg.set_value("macro_progress_bar", progress)
                dpg.configure_item("macro_progress_bar", overlay=f"{current}/{total}")
            else:
                dpg.set_value("macro_progress_bar", 0.0)
                dpg.configure_item("macro_progress_bar", overlay="0/0")

            if timer_val is not None:
                dpg.set_value("timer_value_text", f"{timer_val} s")

            dpg.set_value("stats_clicks_text", str(clicks))
            dpg.set_value("stats_alerts_text", str(alerts))
            dpg.set_value("stats_errors_text", str(errors))

        if snap["stats_start_time"] is not None:
            end = snap["stats_end_time"] or now
            elapsed = max(0.0, end - snap["stats_start_time"])
            mm = int(elapsed // 60)
            ss = int(elapsed % 60)
            time_str = f"{mm:02d}:{ss:02d}"
            if self._cached_time_str != time_str:
                self._cached_time_str = time_str
                dpg.set_value("stats_time_text", time_str)

    def _reset_dashboard_stats(self) -> None:
        dpg.set_value("step_value_text", "-")
        dpg.set_value("phase_text", "-")
        dpg.set_value("timer_value_text", "-")
        dpg.set_value("stats_clicks_text", "0")
        dpg.set_value("stats_alerts_text", "0")
        dpg.set_value("stats_errors_text", "0")
        dpg.set_value("stats_time_text", "00:00")
        dpg.set_value("macro_progress_bar", 0.0)
        dpg.configure_item("macro_progress_bar", overlay="0/0")

    def _register_textures(self) -> None:
        dpg.add_texture_registry(tag="frame_texture_registry")
        dpg.add_raw_texture(
            width=self._tex_w,
            height=self._tex_h,
            default_value=np.zeros((self._tex_h, self._tex_w, 4), dtype=np.float32),
            format=dpg.mvFormat_Float_rgba,
            tag="frame_texture",
            parent="frame_texture_registry",
        )

    def _update_frame_texture(self) -> None:
        if not self.config.preview_enabled:
            # Drain queue when preview is disabled to prevent memory buildup
            while not self.state.frame_queue.empty():
                with contextlib.suppress(Exception):
                    self.state.frame_queue.get_nowait()
            if not getattr(self, "_preview_cleared", False):
                dpg.set_value(
                    "frame_texture",
                    np.zeros((self._tex_h, self._tex_w, 4), dtype=np.float32).ravel(),
                )
                self.state.latest_frame = None
                self._preview_cleared = True
            return

        self._preview_cleared = False
        now = time.monotonic()
        if now - self._last_texture_update < 0.066:
            return

        try:
            frame = self.state.frame_queue.get_nowait()
        except Exception:
            return

        self._last_texture_update = now
        if frame.shape[0] != self._tex_h or frame.shape[1] != self._tex_w:
            frame = cv2.resize(frame, (self._tex_w, self._tex_h), interpolation=cv2.INTER_AREA)

        if self._rgba_buffer is None or self._rgba_buffer.shape != (self._tex_h, self._tex_w, 4):
            self._rgba_buffer = np.empty((self._tex_h, self._tex_w, 4), dtype=np.float32)

        if self._u8_buffer is None or self._u8_buffer.shape != (self._tex_h, self._tex_w, 4):
            self._u8_buffer = np.empty((self._tex_h, self._tex_w, 4), dtype=np.uint8)

        rgba = bgr_to_rgba_texture(frame, out=self._rgba_buffer, u8_out=self._u8_buffer)
        dpg.set_value("frame_texture", rgba.ravel())

    def _resize_dashboard_preview(self) -> None:
        count = getattr(self, "_dash_resize_counter", 0) + 1
        self._dash_resize_counter = count
        if count % 10 != 0:
            return
        try:
            if not dpg.does_item_exist("dash_main_panel"):
                return
            if not dpg.does_item_exist("dash_preview_image"):
                return
            avail = dpg.get_item_state("dash_main_panel").get("content_region_avail")
            if not avail or avail[0] <= 0 or avail[1] <= 0:
                return
            avail_w = int(avail[0])
            avail_h = int(avail[1])
            avail_h = max(0, avail_h - 150)
            if avail_h <= 0:
                return
            # Preserve the fixed 16:9 texture aspect ratio: pick the largest
            # 16:9 rectangle that fits avail_w x avail_h (letterbox/pillarbox),
            # so the 960x540 texture is never stretched.
            aspect = PREVIEW_WIDTH / PREVIEW_HEIGHT
            fit_w = int(avail_h * aspect)
            if fit_w <= avail_w:
                target_w = fit_w
                target_h = avail_h
            else:
                target_w = avail_w
                target_h = int(avail_w / aspect)
            cur = dpg.get_item_configuration("dash_preview_image")
            if cur.get("width") == target_w and cur.get("height") == target_h:
                return
            dpg.configure_item("dash_preview_image", width=target_w, height=target_h)
        except Exception:
            pass


    def _load_fonts(self) -> None:
        font_path = Path(r"C:\Windows\Fonts\segoeui.ttf")
        if not font_path.exists():
            font_path = Path(r"C:\Windows\Fonts\arial.ttf")
        if font_path.exists():
            with dpg.font_registry(), dpg.font(str(font_path), 16) as font:
                dpg.bind_font(font)
        else:
            logger.warning("System font not found. Fallback to default font.")

    def _create_themes(self) -> None:
        for tag in (
            "global_theme",
            "btn_primary_theme",
            "btn_success_theme",
            "collapsing_section_theme",
            "log_console_theme",
            "statusbar_theme",
        ):
            with contextlib.suppress(Exception):
                dpg.delete_item(tag)
        with dpg.theme(tag="global_theme"), dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (24, 24, 27))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (82, 82, 91))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (24, 24, 27))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (24, 24, 27))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, (82, 82, 91))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, (249, 115, 22))
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (249, 115, 22))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (249, 115, 22))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (251, 146, 60))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (82, 82, 91))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (28, 28, 31))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_Separator, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_Tab, (39, 39, 42))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, (249, 115, 22))
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, (24, 24, 27))
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, (68, 64, 60))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (228, 228, 231))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (161, 161, 170))

            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 8, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 4, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 12)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 4)

        with dpg.theme(tag="btn_primary_theme"), dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (249, 115, 22))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (251, 146, 60))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (234, 88, 12))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (250, 250, 250))

        with dpg.theme(tag="btn_success_theme"), dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (34, 197, 94))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (22, 163, 74))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (21, 128, 61))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (24, 24, 27))

        with dpg.theme(tag="collapsing_section_theme"), dpg.theme_component(dpg.mvCollapsingHeader):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (212, 212, 216))

        with dpg.theme(tag="log_console_theme"), dpg.theme_component(dpg.mvInputText):
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (63, 63, 70))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (228, 228, 231))

        with dpg.theme(tag="statusbar_theme"), dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (28, 28, 31))
