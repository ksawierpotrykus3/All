
from mvp.bot.macro_engine import Macro, MacroStep, StepType
from mvp.config import MVPConfig

_ROI_SCROLL_LISTEN = {
    "left": 38.2,
    "top": 17.9,
    "right": 61.7,
    "bottom": 90.7,
    "anchor": "center",
}
_ROI_HELICOPTER_SELECT = {
    "left": 46.2,
    "top": 46.2,
    "right": 54.1,
    "bottom": 52.5,
}
_ROI_EXPLORE = {
    "left": 48.1,
    "top": 54.8,
    "right": 51.8,
    "bottom": 61.3,
}
_ROI_POST_EXPLORE = {
    "left": 43.8,
    "top": 71.2,
    "right": 52.0,
    "bottom": 75.6,
}
_ROI_TIMER = {
    "left": 45.0,
    "top": 16.5,
    "right": 55.0,
    "bottom": 22.5,
}

_ROI_CHAT_BAR = {
    "left": 65.7,
    "top": 93.1,
    "right": 94.0,
    "bottom": 98.7,
}
_ROI_ALLIANCE_TAB = {
    "left": 47.6,
    "top": 5.5,
    "right": 52.4,
    "bottom": 9.7,
    "anchor": "center",
}
_ROI_CAMERA_ZOOM = {
    "left": 43.8,
    "top": 71.2,
    "right": 52.0,
    "bottom": 75.6,
}
_ROI_CHAT_ARROW = {
    "left": 58.0,
    "top": 81.0,
    "right": 63.5,
    "bottom": 92.0,
    "anchor": "center",
}
_ROI_DETAILS_HEADER = {
    "left": 44.0,
    "top": 16.0,
    "right": 56.0,
    "bottom": 21.5,
    "anchor": "center",
}
_ROI_DETAILS_CLOSE = {
    "left": 58.5,
    "top": 16.5,
    "right": 61.5,
    "bottom": 21.0,
    "anchor": "center",
}
_ROI_DETAILS_BACKDROP = {
    "left": 48.0,
    "top": 8.0,
    "right": 52.0,
    "bottom": 12.0,
    "anchor": "center",
}


def build_helicopter_macro(config: MVPConfig) -> Macro:
    return Macro(
        name="helicopter",
        version=2,
        steps=[
            MacroStep(
                type=StepType.SCROLL_LISTEN_CHAT,
                label="Step 1: listen alliance chat for helicopter alert (with auto-arrow)",
                roi_pct=_ROI_SCROLL_LISTEN,
                threshold=0.85,
                timeout_s=0,
                check_interval_s=0.08,
                chat_bar_roi=_ROI_CHAT_BAR,
                alliance_tab_roi=_ROI_ALLIANCE_TAB,
                arrow_roi=_ROI_CHAT_ARROW,
                arrow_threshold=config.chat_arrow_threshold,
                arrow_click_delay_s=config.chat_arrow_delay_s,
                arrow_enabled=True,
                details_roi=_ROI_DETAILS_HEADER,
                details_close_roi=_ROI_DETAILS_CLOSE,
                details_recovery_enabled=config.details_recovery_enabled,
                details_dismiss_delay_s=config.details_dismiss_delay_s,
                post_detect_settle_s=0.3,
                post_detect_reconfirm=False,
                post_click_debounce=False,
                verify_alliance_open=True,
                max_open_retries=3,
                direct_click=True,
            ),

            MacroStep(
                type=StepType.CLICK,
                label="Step 2: click helicopter coords from chat",
                x="step_1_click_x",
                y="step_1_click_y",
                verify_chat_exit=True,
                alliance_tab_roi=_ROI_ALLIANCE_TAB,
                chat_exit_retry_step=1,
                exit_timeout_s=2.5,
            ),
            MacroStep(
                type=StepType.WAIT,
                label="Pause 3.0s - wait for camera stabilization",
                seconds=3.0,
            ),
            MacroStep(
                type=StepType.CLICK,
                label="Step 3: click helicopter (select it)",
                roi_pct=_ROI_HELICOPTER_SELECT,
            ),
            MacroStep(
                type=StepType.WAIT,
                label="Pause 1.0s - wait for Explore button",
                seconds=1.0,
            ),
            MacroStep(
                type=StepType.CLICK,
                label="Step 4: click Explore (send troops)",
                roi_pct=_ROI_EXPLORE,
            ),
            MacroStep(
                type=StepType.WAIT,
                label="Pause 1.0s - after pressing Explore",
                seconds=1.0,
            ),
            MacroStep(
                type=StepType.CLICK,
                label="Step 6: click center of ROI after Explore",
                roi_pct=_ROI_POST_EXPLORE,
                check_march_modal=True,
            ),
            MacroStep(
                type=StepType.WAIT,
                label="Pause 0.5s - wait for Explore UI dialog to close",
                seconds=0.5,
            ),
            MacroStep(
                type=StepType.SCROLL_ZOOM,
                label="Step 6b: scroll+zoom helicopter view to max",
                roi_pct=_ROI_CAMERA_ZOOM,
                scroll_direction="up",
                scroll_ticks=config.zoom_scroll_ticks,
                scroll_interval_s=config.zoom_scroll_interval_s,
            ),
            MacroStep(
                type=StepType.WAIT,
                label="Pause 1.0s - wait for camera smooth zoom animation to settle",
                seconds=1.0,
            ),
            MacroStep(
                type=StepType.WATCH_TIMER,
                label="Step 5: watch timer (HH:MM:SS), idle->fast->spam",
                roi_pct=_ROI_TIMER,
                click_x=50,
                click_y=50,
                timeout_s=getattr(config, "watch_timer_timeout_s", 1800.0),
                idle_check_interval_s=config.idle_check_interval_s,
                fast_check_interval_s=config.fast_check_interval_s,
                fast_threshold_s=config.fast_threshold_s,
                spam_threshold_s=config.spam_threshold_s,
                spam_duration_s=config.spam_duration_s,
                spam_clicks_per_sec=config.spam_clicks_per_sec,
                hysteresis_confirmations=config.hysteresis_confirmations,
                t0_lead_time_s=getattr(config, "t0_lead_time_s", 0.3),
            ),
        ],
    )
