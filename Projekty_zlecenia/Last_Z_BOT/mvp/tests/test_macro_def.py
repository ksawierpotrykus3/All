"""Tests for the hardcoded helicopter macro definition."""

from mvp.bot.macro_engine import StepType
from mvp.config import MVPConfig
from mvp.macro_def import build_helicopter_macro


def test_macro_version_is_2() -> None:
    macro = build_helicopter_macro(MVPConfig.default())
    assert macro.version == 2


def test_macro_has_expected_step_count() -> None:
    """v2: old 14 steps -> 12 steps (removed kroki 11/12 chat bar + alliance
    tab at the end; replaced the leading WAIT_FOR_CHAT with SCROLL_LISTEN_CHAT)."""
    macro = build_helicopter_macro(MVPConfig.default())
    assert len(macro.steps) == 12


def test_macro_step_type_sequence() -> None:
    macro = build_helicopter_macro(MVPConfig.default())
    expected = [
        StepType.SCROLL_LISTEN_CHAT,  # 0:  NEW scroll-listen (replaces WAIT_FOR_CHAT)
        StepType.CLICK,  # 1:  click helicopter coords from chat
        StepType.WAIT,
        StepType.CLICK,  # select helicopter
        StepType.WAIT,
        StepType.CLICK,  # click Explore
        StepType.WAIT,
        StepType.CLICK,  # click center after Explore
        StepType.WAIT,
        StepType.SCROLL_ZOOM,  # zoom camera
        StepType.WAIT,
        StepType.WATCH_TIMER,  # spam-clicks
    ]
    assert [s.type for s in macro.steps] == expected


def test_first_step_is_scroll_listen_chat_with_rois() -> None:
    step = build_helicopter_macro(MVPConfig.default()).steps[0]
    assert step.type == StepType.SCROLL_LISTEN_CHAT
    assert step.roi_pct == {
        "left": 38.2,
        "top": 17.9,
        "right": 61.7,
        "bottom": 90.7,
        "anchor": "center",
    }
    assert step.chat_bar_roi == {
        "left": 65.7,
        "top": 93.1,
        "right": 94.0,
        "bottom": 98.7,
    }
    assert step.alliance_tab_roi == {
        "left": 47.6,
        "top": 5.5,
        "right": 52.4,
        "bottom": 9.7,
        "anchor": "center",
    }
    assert step.arrow_roi == {
        "left": 58.0,
        "top": 81.0,
        "right": 63.5,
        "bottom": 92.0,
        "anchor": "center",
    }
    assert step.arrow_threshold == 0.92
    assert step.arrow_click_delay_s == 0.35
    assert step.arrow_enabled is True
    # Fallback: keep threshold/timeout/interval for safety-net parity.
    assert step.threshold == 0.85
    assert step.timeout_s == 0
    assert step.check_interval_s == 0.08
    assert step.direct_click is True


def test_arrow_threshold_reads_config() -> None:
    cfg = MVPConfig.default()
    cfg.chat_arrow_threshold = 0.95
    cfg.chat_arrow_delay_s = 0.5
    step = build_helicopter_macro(cfg).steps[0]
    assert step.arrow_threshold == 0.95
    assert step.arrow_click_delay_s == 0.5


def test_listen_step_clicks_on_first_detection() -> None:
    """Latency fix: post_detect_reconfirm and post_click_debounce are disabled.
    Direct click is enabled on first detection."""
    step = build_helicopter_macro(MVPConfig.default()).steps[0]
    assert step.post_detect_reconfirm is False
    assert step.post_click_debounce is False
    assert step.verify_alliance_open is True
    assert step.max_open_retries == 3
    assert step.direct_click is True


def test_second_step_uses_chat_coordinates() -> None:
    step = build_helicopter_macro(MVPConfig.default()).steps[1]
    assert step.x == "step_1_click_x"
    assert step.y == "step_1_click_y"
    assert step.roi_pct is None
    assert step.verify_chat_exit is True
    assert step.alliance_tab_roi is not None
    assert step.chat_exit_retry_step == 1
    assert step.exit_timeout_s == 2.5


def test_watch_timer_step_reads_config_values() -> None:
    cfg = MVPConfig.default()
    cfg.spam_clicks_per_sec = 77
    cfg.idle_check_interval_s = 12.5
    cfg.fast_check_interval_s = 0.3
    cfg.fast_threshold_s = 240
    cfg.spam_threshold_s = 6
    cfg.spam_duration_s = 8.0
    # WATCH_TIMER is now the last step (index 11) in the 12-step v2 macro.
    step = build_helicopter_macro(cfg).steps[11]

    assert step.type == StepType.WATCH_TIMER
    assert step.fast_threshold_s == 240
    assert step.spam_clicks_per_sec == 77
    assert step.idle_check_interval_s == 12.5
    assert step.fast_check_interval_s == 0.3
    assert step.spam_threshold_s == 6
    assert step.spam_duration_s == 8.0


def test_scroll_zoom_step_reads_config_values() -> None:
    cfg = MVPConfig.default()
    cfg.zoom_scroll_ticks = 30
    cfg.zoom_scroll_interval_s = 0.05
    # SCROLL_ZOOM is step index 9
    step = build_helicopter_macro(cfg).steps[9]
    assert step.type == StepType.SCROLL_ZOOM
    assert step.scroll_ticks == 30
    assert step.scroll_interval_s == 0.05


def test_post_explore_step_has_check_march_modal_enabled() -> None:
    step = build_helicopter_macro(MVPConfig.default()).steps[7]
    assert step.type == StepType.CLICK
    assert step.check_march_modal is True

