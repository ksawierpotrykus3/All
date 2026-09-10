"""Tests for MVP exceptions, coordinates, clicker, and macro engine."""

import time

import numpy as np

from mvp.bot.clicker import Clicker
from mvp.bot.coordinates import GamePercent, GameROI, ScreenCoord, WindowContext
from mvp.bot.exceptions import ClickerError, MacroStepError
from mvp.bot.macro_engine import (
    Macro,
    MacroEngine,
    MacroStep,
    StepType,
    calculate_adaptive_interval,
    calculate_avg_delta,
    should_trigger_spam,
)


def test_macro_step_error_str_contains_label_and_message() -> None:
    err = MacroStepError("click", "cannot resolve target")
    assert "[click]" in str(err)
    assert "cannot resolve target" in str(err)


def test_game_roi_to_pixels_converts_percentages() -> None:
    roi = GameROI(left=25.0, top=50.0, right=75.0, bottom=100.0)
    assert roi.to_pixels(1920, 1080) == (480, 540, 1440, 1080)


def test_window_context_roi_center_to_screen() -> None:
    win = WindowContext(left=100, top=200, width=1920, height=1080)
    roi = GameROI(left=0.0, top=0.0, right=50.0, bottom=50.0)
    coord = win.roi_center_to_screen(roi)
    assert isinstance(coord, ScreenCoord)
    # center of ROI is (25%, 25%) in client space
    # x = 100 + int(1920 * 0.25) = 100 + 480 = 580
    # y = 200 + int(1080 * 0.25) = 200 + 270 = 470
    assert coord == ScreenCoord(100 + 480, 200 + 270)


def test_game_percent_and_screen_coord_values() -> None:
    gp = GamePercent(10.0, 20.0)
    # in client space: y = int(500 * 0.20) = 100
    sc = WindowContext(0, 0, 1000, 500).to_screen(gp)
    assert sc == ScreenCoord(100, 100)


def test_clicker_swaps_min_max_delays() -> None:
    clicker = Clicker(min_delay_ms=400, max_delay_ms=100)
    assert clicker.min_delay_ms == 100
    assert clicker.max_delay_ms == 400


def test_click_at_without_backend_raises(monkeypatch) -> None:
    clicker = Clicker(input_backend="sendinput")
    # Simulate a backend that never becomes available.
    monkeypatch.setattr(clicker, "initialize", lambda: None)
    try:
        clicker.click_at(100, 100)
    except ClickerError as exc:
        assert "SendInput backend is not available" in str(exc)
    else:
        raise AssertionError("ClickerError not raised")


# ── MacroEngine tests ───────────────────────────────────────────────


class _FakeClicker:
    def __init__(self) -> None:
        self.clicks: list[tuple[int, int]] = []
        self.spam_calls: list[dict] = []

    def click_at(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def spam_click(
        self,
        x: int,
        y: int,
        count: int,
        deadline=None,
        clicks_per_sec=None,
        direct_first: bool = False,
    ) -> int:
        self.spam_calls.append(
            {
                "x": x,
                "y": y,
                "count": count,
                "deadline": deadline,
                "clicks_per_sec": clicks_per_sec,
                "direct_first": direct_first,
            }
        )
        return count


class _FakeChatOCR:
    def __init__(self) -> None:
        self.alert = {
            "click_x": 100,
            "click_y": 200,
            "coords_x": 1,
            "coords_y": 2,
            "text": "State 1: 2",
        }
        self.calls = 0

    def find_helicopter_alert(self, image) -> dict | None:
        self.calls += 1
        return self.alert


class _FakeChatOCRSeq:
    """ChatOCR returning a programmed sequence of alerts (one per call)."""

    def __init__(self, alerts: list) -> None:
        self._alerts = alerts
        self.calls = 0

    def find_helicopter_alert(self, image) -> dict | None:
        if self.calls >= len(self._alerts):
            return None
        a = self._alerts[self.calls]
        self.calls += 1
        return a


class _FakeTimerOCR:
    def __init__(self) -> None:
        self.values: list[int | None] = []

    def read_timer(self, image) -> int | None:
        return self.values.pop(0) if self.values else None


class _FakeCapture:
    def __init__(self) -> None:
        self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def grab(self) -> np.ndarray | None:
        return self.frame


def _make_engine() -> MacroEngine:
    return MacroEngine(
        clicker=_FakeClicker(),
        chat_ocr=_FakeChatOCR(),
        timer_ocr=_FakeTimerOCR(),
        capture=_FakeCapture(),
    )


def test_handle_wait_sleeps(monkeypatch) -> None:
    waits: list[float] = []
    engine = _make_engine()
    monkeypatch.setattr(engine._stop_requested, "wait", lambda timeout=None: waits.append(timeout))
    engine._handle_wait(MacroStep(type=StepType.WAIT, seconds=3.0))
    assert waits == [3.0]


def test_handle_click_with_roi_uses_center() -> None:
    clicker = _FakeClicker()
    engine = MacroEngine(clicker=clicker, chat_ocr=None, timer_ocr=None, capture=None)
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.CLICK,
        roi_pct={"left": 25.0, "top": 25.0, "right": 50.0, "bottom": 50.0},
    )
    engine._handle_click(step, win)
    # ROI center in client space: x=37.5%, y=37.5%
    # x = 0 + int(1920 * 0.375) = 720
    # y = 0 + int(1080 * 0.375) = 405
    assert clicker.clicks == [(720, 405)]


def test_handle_wait_for_chat_stores_coordinates() -> None:
    engine = _make_engine()
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WAIT_FOR_CHAT,
        roi_pct={"left": 0.0, "top": 0.0, "right": 100.0, "bottom": 100.0},
        timeout_s=0,
        check_interval_s=0.5,
    )
    engine._handle_wait_for_chat(1, step, win)
    assert engine.memory["step_1_click_x"] > 0
    assert engine.memory["step_1_click_y"] > 0


def test_handle_watch_timer_spam_phase(monkeypatch) -> None:
    engine = _make_engine()
    engine.timer_ocr.values = [100, 10, 5, 3]  # idle→fast→fast(spam)
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 0.0, "top": 0.0, "right": 100.0, "bottom": 100.0},
        timeout_s=5.0,
        idle_check_interval_s=0.01,
        fast_check_interval_s=0.01,
        fast_threshold_s=60,
        spam_threshold_s=5,
        spam_duration_s=0.05,
        spam_clicks_per_sec=100,
        hysteresis_confirmations=2,
    )
    engine._handle_watch_timer(1, step, win)
    assert len(engine.clicker.spam_calls) == 1
    assert engine.clicker.spam_calls[0]["clicks_per_sec"] == 100


def test_run_catches_step_error() -> None:
    class _FailingClicker:
        def click_at(self, x, y):
            raise ClickerError("boom")

    engine = MacroEngine(clicker=_FailingClicker(), chat_ocr=None, timer_ocr=None, capture=None)
    macro = Macro(name="test", steps=[MacroStep(type=StepType.CLICK, x=1, y=1)])
    result = engine.run(macro, WindowContext(0, 0, 1920, 1080))
    assert result.success is False
    assert result.error is not None
    # NEW (audit P0-9): engine must record the error in its stats counter.
    assert engine.stats_errors >= 1


def test_resolve_spam_params_falls_back_to_macro_step() -> None:
    """F1 must use the macro's WATCH_TIMER params (2s @ 60 CPS), not a stale
    hardcoded default (7s @ 100 CPS)."""
    engine = _make_engine()
    engine._current_macro = Macro(
        name="test",
        steps=[MacroStep(type=StepType.WATCH_TIMER, spam_duration_s=2.0, spam_clicks_per_sec=60)],
    )
    duration, cps = engine._resolve_spam_params()
    assert duration == 2.0
    assert cps == 60


def test_resolve_spam_params_prefers_recorded_phase() -> None:
    """Once the watch_timer spam phase ran, F1 reuses those recorded params."""
    engine = _make_engine()
    engine._spam_duration_s = 3.5
    engine._spam_cps = 90
    engine._current_macro = Macro(
        name="test",
        steps=[MacroStep(type=StepType.WATCH_TIMER, spam_duration_s=2.0, spam_clicks_per_sec=60)],
    )
    duration, cps = engine._resolve_spam_params()
    assert duration == 3.5
    assert cps == 90


def test_macro_engine_has_no_spam_lock_param() -> None:
    import inspect

    sig = inspect.signature(MacroEngine.__init__)
    assert "spam_lock" not in sig.parameters


def test_sleep_with_budget_subtracts_elapsed_time(monkeypatch) -> None:
    waits: list[float] = []
    engine = _make_engine()
    monkeypatch.setattr(engine._stop_requested, "wait", lambda timeout=None: waits.append(timeout))
    engine._sleep_with_budget(0.2, time.monotonic() - 0.15)
    assert len(waits) == 1
    assert 0.04 <= waits[0] <= 0.06


def test_step_type_enum_has_scroll_listen_chat() -> None:
    """SCROLL_LISTEN_CHAT is a new StepType used by the scroll-listen pre/post-run step."""
    assert StepType.SCROLL_LISTEN_CHAT.value == "scroll_listen_chat"


def test_macro_step_has_scroll_listen_chat_fields() -> None:
    step = MacroStep(type=StepType.SCROLL_LISTEN_CHAT)
    assert step.chat_bar_roi is None
    assert step.alliance_tab_roi is None
    assert step.scroll_center_roi is None
    assert step.scroll_settle_s == 0.2
    assert step.post_detect_settle_s == 0.3
    assert step.post_detect_reconfirm is True


def test_macro_step_scroll_direction_defaults_for_scroll_listen() -> None:
    step = MacroStep(type=StepType.SCROLL_LISTEN_CHAT)
    assert step.scroll_direction == "up"


def test_alert_to_game_pct_converts_frame_pixels_to_calibration_space() -> None:
    """Refactored helper maps cropped-frame pixel coords to calibration-space %.

    Mirrors the original inline logic in _handle_wait_for_chat (lines 486-488
    of the pre-refactor file): the ROI origin (left, top — already converted to
    frame pixels via roi_to_frame_pixels) is added to the alert click, then
    x is % of frame width and y is % of (frame_h + _CALIBRATION_TB_PX).
    """
    engine = _make_engine()
    # alert click position in *cropped* frame pixels
    alert = {"click_x": 100, "click_y": 200, "text": "State 1: 2"}
    # left/top are the ROI origin in frame-pixel space (after roi_to_frame_pixels)
    left, top = 192, 270  # e.g. left=10%*1920=192, top=25%*1080=270
    frame_w = 1920
    frame_h = 1080

    gx, gy = engine._alert_to_game_pct(alert, left, top, frame_w, frame_h)

    expected_x = (left + alert["click_x"]) / frame_w * 100.0
    expected_y = (top + alert["click_y"]) / frame_h * 100.0
    assert abs(gx - expected_x) < 0.01
    assert abs(gy - expected_y) < 0.01


def test_scroll_listen_chat_detects_alert_stops_scroll(monkeypatch) -> None:
    """SCROLL_LISTEN_CHAT scroll+OCR loop detects alert on first iteration."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCR()  # alert with click_x=100, click_y=200
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=ocr,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.SCROLL_LISTEN_CHAT,
        label="scroll-listen",
        roi_pct={"left": 38.2, "top": 20.2, "right": 61.7, "bottom": 91.0},
        chat_bar_roi={"left": 65.7, "top": 93.1, "right": 94.0, "bottom": 98.7},
        alliance_tab_roi={"left": 48.0, "top": 7.9, "right": 51.8, "bottom": 11.9},
        scroll_center_roi={"left": 42.0, "top": 40.0, "right": 58.0, "bottom": 70.0},
        timeout_s=10.0,
        check_interval_s=0.5,
        scroll_settle_s=0.0,
        post_detect_settle_s=0.0,
        post_detect_reconfirm=False,
    )
    monkeypatch.setattr(time, "sleep", lambda s: None)

    engine._handle_scroll_listen_chat(1, step, win)

    # Chat bar + alliance tab clicked first (2 clicks)
    assert len(clicker.clicks) == 2
    # Alert found on the first in-gap scan BEFORE any wheel scroll fires
    # (scan-then-scroll order: scroll only happens after a clean scan gap).
    assert len(clicker.scrolls) == 0
    assert clicker.scrolls[0]["direction"] == "down" if clicker.scrolls else True
    # Memory set
    assert "step_1_click_x" in engine.memory
    assert "step_1_click_y" in engine.memory
    assert engine._step_results[1]["detected"] is True


class _FakeScrollClicker:
    """Clicker that supports scroll_at. Used by SCROLL_LISTEN_CHAT tests."""

    def __init__(self) -> None:
        self.clicks: list[tuple[int, int]] = []
        self.scrolls: list[dict] = []

    def click_at(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

    def scroll_at(
        self, x, y, direction="up", ticks=1, interval_s=0.0, restore_cursor=False
    ) -> None:
        self.scrolls.append(
            {
                "x": x,
                "y": y,
                "direction": direction,
                "ticks": ticks,
                "interval_s": interval_s,
                "restore_cursor": restore_cursor,
            }
        )


def _make_listen_step(**overrides) -> MacroStep:
    """Build a SCROLL_LISTEN_CHAT step with the standard test ROIs."""
    defaults: dict = {
        "type": StepType.SCROLL_LISTEN_CHAT,
        "label": "scroll-listen",
        "roi_pct": {"left": 38.2, "top": 20.2, "right": 61.7, "bottom": 91.0},
        "chat_bar_roi": {"left": 65.7, "top": 93.1, "right": 94.0, "bottom": 98.7},
        "alliance_tab_roi": {"left": 48.0, "top": 7.9, "right": 51.8, "bottom": 11.9},
        "scroll_center_roi": {"left": 42.0, "top": 40.0, "right": 58.0, "bottom": 70.0},
        "timeout_s": 10.0,
        "check_interval_s": 0.5,
        "scroll_settle_s": 0.0,
        "post_detect_settle_s": 0.0,
        "post_detect_reconfirm": False,
        "scan_between_scroll": 1,
        "post_click_debounce": False,
    }
    defaults.update(overrides)
    return MacroStep(**defaults)


def test_scroll_listen_chat_drift_reconfirm_uses_second_alert(monkeypatch) -> None:
    """With post_detect_reconfirm=True, the second OCR call (after settle) wins."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCRSeq(
        [
            {"click_x": 100, "click_y": 200, "text": "State 1: 2"},
            {"click_x": 120, "click_y": 215, "text": "State 1: 3"},  # drifted
        ]
    )
    engine = MacroEngine(clicker=clicker, chat_ocr=ocr, timer_ocr=None, capture=_FakeCapture())
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(
        post_detect_settle_s=0.0,
        post_detect_reconfirm=True,
    )
    monkeypatch.setattr(time, "sleep", lambda s: None)
    engine._handle_scroll_listen_chat(1, step, win)
    # 2 OCR calls: first detects, second reconfirms with drifted position
    assert ocr.calls == 2
    assert "step_1_click_x" in engine.memory


def test_scroll_listen_chat_post_detect_settle_off(monkeypatch) -> None:
    """With post_detect_reconfirm=False, only one OCR call."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCRSeq([{"click_x": 100, "click_y": 200, "text": "State 1: 2"}])
    engine = MacroEngine(clicker=clicker, chat_ocr=ocr, timer_ocr=None, capture=_FakeCapture())
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(post_detect_reconfirm=False)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    engine._handle_scroll_listen_chat(1, step, win)
    assert ocr.calls == 1


def test_scroll_listen_chat_timeout_no_alert(monkeypatch) -> None:
    """When OCR always returns None, handler exits via timeout with detected=False."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCRSeq([])  # always None
    engine = MacroEngine(clicker=clicker, chat_ocr=ocr, timer_ocr=None, capture=_FakeCapture())
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(timeout_s=0.2, check_interval_s=0.0, scroll_settle_s=0.0)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    fake_now = [0.0]

    def fake_monotonic():
        fake_now[0] += 0.3
        return fake_now[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    engine._handle_scroll_listen_chat(1, step, win)
    assert engine._step_results[1]["detected"] is False


def test_scroll_listen_chat_stops_on_macro_stop(monkeypatch) -> None:
    """stop_requested set before the loop exits without detecting an alert."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCRSeq([])
    engine = MacroEngine(clicker=clicker, chat_ocr=ocr, timer_ocr=None, capture=_FakeCapture())
    engine._stop_requested.set()  # stop BEFORE entering
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step()
    monkeypatch.setattr(time, "sleep", lambda s: None)
    engine._handle_scroll_listen_chat(1, step, win)
    assert engine._step_results[1]["detected"] is False


def test_handle_wait_for_chat_fast_path_when_memory_set(monkeypatch) -> None:
    """If memory['step_1_click_*'] is set (by pre-run scroll-listen),
    WAIT_FOR_CHAT skips its OCR loop entirely and returns immediately.
    """
    engine = _make_engine()
    engine.memory["step_1_click_x"] = 12.34
    engine.memory["step_1_click_y"] = 56.78
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WAIT_FOR_CHAT,
        roi_pct={"left": 0.0, "top": 0.0, "right": 100.0, "bottom": 100.0},
        timeout_s=10.0,
        check_interval_s=0.1,
    )

    # capture.grab must NOT be called on the fast-path
    def _grab_must_not_be_called():
        raise AssertionError("capture.grab should not be called on the fast-path")

    engine.capture.grab = _grab_must_not_be_called  # type: ignore
    monkeypatch.setattr(time, "sleep", lambda s: None)
    engine._handle_wait_for_chat(1, step, win)
    assert engine._step_results[1]["detected"] is True
    assert engine._step_results[1]["fast_path"] is True


# ---------------------------------------------------------------------------
# Enhancement: scan_between_scroll + post_click_debounce
# ---------------------------------------------------------------------------


def test_scroll_listen_chat_detects_arrow_when_no_alert(monkeypatch) -> None:
    """When no helicopter alert is present, chat listening detects and clicks the arrow."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCRSeq([None, {"click_x": 100, "click_y": 200, "text": "State 1: 2"}])

    class FakeArrowDetector:
        def __init__(self):
            self.calls = 0

        def find_arrow(self, frame, roi_rect=None, threshold=None):
            self.calls += 1
            # Return center_x=1176, center_y=937 on first call
            return (1176, 937, 0.98) if self.calls == 1 else None

    arrow_det = FakeArrowDetector()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=ocr,
        timer_ocr=None,
        capture=_FakeCapture(),
        arrow_detector=arrow_det,
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(
        post_detect_reconfirm=False,
        post_click_debounce=False,
    )
    monkeypatch.setattr(time, "sleep", lambda s: None)

    engine._handle_scroll_listen_chat(1, step, win)

    # Click sequence:
    # 1) chat bar
    # 2) alliance tab
    # 3) arrow click (because alert was None on 1st scan)
    assert len(clicker.clicks) == 3
    assert arrow_det.calls >= 1
    assert engine._step_results[1]["detected"] is True


def test_listen_chat_skips_when_memory_already_set(monkeypatch) -> None:
    """SCROLL_LISTEN_CHAT fast-path: if memory already has coords, skip open-chat + scan entirely."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCR()
    engine = MacroEngine(clicker=clicker, chat_ocr=ocr, timer_ocr=None, capture=_FakeCapture())
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step()

    # Simulate previous detection (post-run dispatch set memory)
    engine.memory["step_1_click_x"] = 47.8
    engine.memory["step_1_click_y"] = 58.0

    monkeypatch.setattr(time, "sleep", lambda s: None)
    engine._handle_scroll_listen_chat(1, step, win)

    # No clicks at all (chat bar + alliance tab NOT opened)
    assert len(clicker.clicks) == 0
    # No OCR calls
    assert ocr.calls == 0
    # Memory preserved with original coords
    assert engine.memory["step_1_click_x"] == 47.8
    assert engine.memory["step_1_click_y"] == 58.0
    assert engine._step_results[1]["detected"] is True
    assert engine._step_results[1]["fast_path"] is True


def test_scroll_listen_chat_arrow_click_uses_sendinput_backend(monkeypatch) -> None:
    """When input_backend='sendinput' is configured, arrow clicks use SendInputBackend."""
    from mvp.bot.clicker import Clicker
    from mvp.bot.input.sendinput_backend import SendInputBackend

    clicker = Clicker(input_backend="sendinput")
    clicker.initialize()
    assert isinstance(clicker._backend, SendInputBackend)

    send_events = []
    move_events = []
    monkeypatch.setattr(clicker._backend, "_send", lambda inputs: send_events.append(inputs))
    monkeypatch.setattr(clicker._backend, "move_to", lambda x, y: move_events.append((x, y)))
    monkeypatch.setattr(time, "sleep", lambda s: None)

    class FakeArrowDetector:
        def find_arrow(self, frame, roi_rect=None, threshold=None):
            return (1176, 937, 0.98)

    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=_FakeChatOCRSeq([None]),
        timer_ocr=None,
        capture=_FakeCapture(),
        arrow_detector=FakeArrowDetector(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(timeout_s=0.01, post_detect_reconfirm=False)

    engine._handle_scroll_listen_chat(1, step, win)

    # Move calls occurred via SendInputBackend.move_to (SetCursorPos)
    assert len(move_events) > 0
    # Clicks occurred via SendInputBackend._send (user32.SendInput)
    assert len(send_events) >= 2  # DOWN and UP events delivered via SendInput


def test_scroll_listen_chat_aborts_immediately_when_stop_requested(monkeypatch) -> None:
    """If stop is requested before/during scroll_listen_chat, no chat UI clicks occur."""
    clicker = _FakeScrollClicker()
    engine = MacroEngine(clicker=clicker, chat_ocr=None, timer_ocr=None, capture=None)
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step()

    engine._stop_requested.set()
    engine._handle_scroll_listen_chat(1, step, win)

    assert len(clicker.clicks) == 0
    assert engine._step_results[1]["detected"] is False


def test_scroll_listen_chat_opens_when_not_verified(monkeypatch) -> None:
    """When verify_alliance_open=True and chat is not open -> performs 2 open clicks (chat bar + tab)."""
    clicker = _FakeScrollClicker()
    ocr_responses = [False, True]

    class _MockChatOCR:
        def __init__(self):
            self.calls = 0

        def is_alliance_chat_open(self, image):
            ans = ocr_responses.pop(0) if ocr_responses else True
            return ans

        def find_helicopter_alert(self, image):
            return {
                "click_x": 100,
                "click_y": 200,
                "coords_x": 10,
                "coords_y": 20,
                "text": "State 1: 2",
            }

    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=_MockChatOCR(),
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(verify_alliance_open=True, max_open_retries=3)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    engine._handle_scroll_listen_chat(1, step, win)

    # Clean opening: 2 clicks total (chat bar + tab)
    assert len(clicker.clicks) == 2
    assert "step_1_click_x" in engine.memory
    assert engine._step_results[1]["detected"] is True


def test_scroll_listen_chat_switches_tab_without_clicking_bar_when_window_open(monkeypatch) -> None:
    """When chat window is open on a different tab, only the Alliance tab is clicked (1 click, no bar click)."""
    clicker = _FakeScrollClicker()

    class _MockChatOCR:
        def is_alliance_chat_open(self, image):
            return False

        def is_chat_window_open(self, image):
            return True

        def find_helicopter_alert(self, image):
            return {
                "click_x": 100,
                "click_y": 200,
                "coords_x": 10,
                "coords_y": 20,
                "text": "State 1: 2",
            }

    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=_MockChatOCR(),
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(verify_alliance_open=True)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    engine._handle_scroll_listen_chat(1, step, win)

    # Only 1 click to switch tab (alliance tab), chat_bar_roi was NOT clicked
    assert len(clicker.clicks) == 1
    assert "step_1_click_x" in engine.memory
    assert engine._step_results[1]["detected"] is True


def test_macro_run_retries_helicopter_scan_when_chat_fails_to_close(monkeypatch) -> None:
    """When step 2 clicks alert but chat remains open, macro rewinds to step 1 and rescans."""
    clicker = _FakeScrollClicker()
    # Chat remains open during first run of step 2 (closed_after_rewind becomes True after first scan)
    scans_done = {"count": 0}

    class _MockChatOCR:
        def __init__(self):
            self.find_calls = 0

        def is_alliance_chat_open(self, image):
            # If scan 1 has run but scan 2 hasn't, chat is still open (exit fails)
            # Once scan 2 runs, chat closes successfully
            return scans_done["count"] < 2

        def find_helicopter_alert(self, image):
            self.find_calls += 1
            scans_done["count"] = self.find_calls
            return {
                "click_x": 100,
                "click_y": 200 + self.find_calls * 10,
                "coords_x": 10,
                "coords_y": 20,
                "text": "State 10: 20",
            }

    ocr = _MockChatOCR()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=ocr,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    macro = Macro(
        name="test_retry_macro",
        steps=[
            MacroStep(
                type=StepType.SCROLL_LISTEN_CHAT,
                label="step 1 listen",
                roi_pct={"left": 38.2, "top": 20.2, "right": 61.7, "bottom": 91.0},
                chat_bar_roi={"left": 65.7, "top": 93.1, "right": 94.0, "bottom": 98.7},
                alliance_tab_roi={"left": 48.0, "top": 7.9, "right": 51.8, "bottom": 11.9},
                timeout_s=1.0,
                post_detect_reconfirm=False,
            ),
            MacroStep(
                type=StepType.CLICK,
                label="step 2 click helicopter",
                x="step_1_click_x",
                y="step_1_click_y",
                verify_chat_exit=True,
                alliance_tab_roi={"left": 48.0, "top": 7.9, "right": 51.8, "bottom": 11.9},
                chat_exit_retry_step=1,
            ),
            MacroStep(
                type=StepType.WAIT,
                label="step 3 wait",
                seconds=0.01,
            ),
        ],
    )
    monkeypatch.setattr(time, "sleep", lambda s: None)

    result = engine.run(macro, win)

    assert result.success is True
    assert result.completed_steps == 3
    # Step 1 was executed twice due to rewind
    assert ocr.find_calls == 2


def test_scroll_listen_chat_skips_opening_clicks_if_already_open(monkeypatch) -> None:
    """When verify_alliance_open=True and chat is already open, opening clicks are skipped."""
    clicker = _FakeScrollClicker()

    class _MockChatOCR:
        def is_alliance_chat_open(self, image):
            return True

        def find_helicopter_alert(self, image):
            return {
                "click_x": 100,
                "click_y": 200,
                "coords_x": 10,
                "coords_y": 20,
                "text": "State 1: 2",
            }

    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=_MockChatOCR(),
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(verify_alliance_open=True)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    engine._handle_scroll_listen_chat(1, step, win)

    # 0 opening clicks because chat was already open
    assert len(clicker.clicks) == 0
    assert "step_1_click_x" in engine.memory
    assert engine._step_results[1]["detected"] is True


def test_scroll_listen_chat_recovers_from_details_dialog(monkeypatch) -> None:
    """When a Details dialog is detected, it is closed before resuming chat listening."""
    clicker = _FakeScrollClicker()

    class _MockChatOCR:
        def __init__(self):
            self.details_calls = 0
            self.find_calls = 0

        def is_alliance_chat_open(self, image):
            return True

        def is_details_dialog_open(self, image):
            self.details_calls += 1
            # First frame: Details modal is open. Second frame: closed.
            return self.details_calls == 1

        def find_helicopter_alert(self, image):
            self.find_calls += 1
            if self.find_calls == 1:
                return None  # Dialog is blocking, no alert seen
            return {
                "click_x": 100,
                "click_y": 200,
                "coords_x": 528,
                "coords_y": 482,
                "text": "State 742 X:528 Y:482",
            }

    ocr = _MockChatOCR()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=ocr,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(
        verify_alliance_open=True,
        details_recovery_enabled=True,
        details_roi={"left": 44.0, "top": 16.0, "right": 56.0, "bottom": 21.5},
        details_close_roi={"left": 58.5, "top": 16.5, "right": 61.5, "bottom": 21.0},
        details_dismiss_delay_s=0.0,
        check_interval_s=0.0,
    )
    monkeypatch.setattr(time, "sleep", lambda s: None)

    engine._handle_scroll_listen_chat(1, step, win)

    assert ocr.details_calls >= 1
    # Clicker should have clicked close details popup
    assert len(clicker.clicks) >= 1
    assert "step_1_click_x" in engine.memory
    assert engine._step_results[1]["detected"] is True


def test_scroll_listen_chat_details_delay_honored(monkeypatch) -> None:
    """The configured details_dismiss_delay_s is waited before closing the Details dialog."""
    clicker = _FakeScrollClicker()
    waited_delays: list[float] = []

    class _MockChatOCR:
        def __init__(self):
            self.call = 0

        def is_alliance_chat_open(self, image):
            return True

        def is_details_dialog_open(self, image):
            self.call += 1
            return self.call == 1

        def find_helicopter_alert(self, image):
            if self.call == 0:
                return None
            return {"click_x": 100, "click_y": 200, "coords_x": 1, "coords_y": 2, "text": "State 1"}

    ocr = _MockChatOCR()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=ocr,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    orig_wait = engine._stop_requested.wait

    def mock_wait(timeout=None):
        if timeout is not None and timeout > 0:
            waited_delays.append(timeout)
        return orig_wait(0.001)

    monkeypatch.setattr(engine._stop_requested, "wait", mock_wait)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = _make_listen_step(
        verify_alliance_open=True,
        details_recovery_enabled=True,
        details_roi={"left": 44.0, "top": 16.0, "right": 56.0, "bottom": 21.5},
        details_close_roi={"left": 58.5, "top": 16.5, "right": 61.5, "bottom": 21.0},
        details_dismiss_delay_s=5.0,
        check_interval_s=0.0,
    )

    engine._handle_scroll_listen_chat(1, step, win)

    assert 5.0 in waited_delays
    assert engine._step_results[1]["detected"] is True


def test_watch_timer_inactivity_timeout_when_no_timer(monkeypatch) -> None:
    """When no timer is detected for timeout_s, watch_timer aborts with inactivity_timeout."""
    clicker = _FakeScrollClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        timeout_s=30.0,
    )

    cur_time = [0.0]

    def mock_monotonic():
        cur_time[0] += 5.0
        return cur_time[0]

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(engine, "_read_timer_value", lambda *args, **kwargs: None)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is False
    assert engine._step_results[1]["reason"] == "inactivity_timeout"


def test_watch_timer_inactivity_timeout_when_timer_stuck(monkeypatch) -> None:
    """When timer is stuck on the exact same value for timeout_s, watch_timer aborts with inactivity_timeout."""
    clicker = _FakeScrollClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        timeout_s=30.0,
    )

    cur_time = [0.0]

    def mock_monotonic():
        cur_time[0] += 5.0
        return cur_time[0]

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(engine, "_read_timer_value", lambda *args, **kwargs: 500)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is False
    assert engine._step_results[1]["reason"] == "inactivity_timeout"


def test_watch_timer_keeps_running_while_timer_active(monkeypatch) -> None:
    """While timer is actively counting down, inactivity timeout is continuously reset."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        timeout_s=30.0,
        spam_threshold_s=5,
        fast_threshold_s=300,
        spam_duration_s=1.0,
    )

    # NEW: Better timer sequence without abrupt jumps, longer countdown
    # Test that inactivity timeout is continuously reset while timer is actively ticking down
    cur_time = [0.0]
    timer_seq = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3]

    def mock_monotonic():
        cur_time[0] += 0.1  # Small increment per call (100ms)
        return cur_time[0]

    def mock_read(*args, **kwargs):
        if timer_seq:
            timer_val = timer_seq.pop(0)
            return (timer_val, time.monotonic()) if isinstance(timer_val, int) else timer_val
        return (0, time.monotonic())

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(engine, "_read_timer_value", mock_read)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True


def test_watch_timer_fast_trigger_on_timer_disappearance(monkeypatch) -> None:
    """When timer is low (e.g. 4s) and suddenly disappears (None), trigger spam immediately."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=1200.0,
    )

    read_results = [4, None]

    def mock_read_timer_for_disappearance(*args, **kwargs):
        result = read_results.pop(0) if read_results else None
        if result is None:
            return (None, time.monotonic())
        return (result, time.monotonic())

    monkeypatch.setattr(engine, "_read_timer_value", mock_read_timer_for_disappearance)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True
    assert len(clicker.spam_calls) == 1


def test_watch_timer_handles_player_exit_time_increase_from_6s_to_36s(monkeypatch) -> None:
    """When timer jumps from 6s to 36s (player left heli), bot resets T0 estimate, does NOT spam at 6s, and spams only at 36s."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=1200.0,
    )

    # Sequence of timer readings:
    # 1. 6s (in fast phase, target ~ +6s)
    # 2. Player leaves: jumps to 36s (should NOT trigger spam at 6s, updates target ~ +36s)
    # 3. 20s later: countdown is now 4s
    # 4. Timer disappears (None) -> now spam triggers!
    readings = [6, 36, 4, None]

    def mock_read_timer_for_jump(*args, **kwargs):
        result = readings.pop(0) if readings else None
        if result is None:
            return (None, time.monotonic())
        return (result, time.monotonic())

    monkeypatch.setattr(engine, "_read_timer_value", mock_read_timer_for_jump)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True
    assert len(clicker.spam_calls) == 1
    assert engine.last_timer_value == 4


def test_watch_timer_triggers_at_t0_lead_time(monkeypatch) -> None:
    """When timer is 3s, spam triggers when monotonic clock reaches T0 - t0_lead_time."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=1200.0,
        t0_lead_time_s=0.3,
    )

    current_time = [100.0]
    iteration_count = [0]
    max_iterations = [1000]  # Safety limit to prevent infinite loops

    def mock_monotonic():
        return current_time[0]

    def mock_sleep_with_budget(duration, poll_started, min_sleep=0.0):
        # Advance monotonic time by duration, with a small floor to prevent infinite loops on floating-point errors
        iteration_count[0] += 1
        if iteration_count[0] > max_iterations[0]:
            print(f"Infinite loop detected at iteration {iteration_count[0]}: duration={duration}, current_time={current_time[0]}")
            raise RuntimeError(f"Exceeded max iterations ({max_iterations[0]}), likely infinite loop in sleep logic")
        # Ensure we advance time by at least the minimum sleep + tolerance for floating-point errors
        min_advance = max(0.001, min_sleep)  # Minimum 1ms advance to prevent floating-point loops
        if duration > min_advance / 2:  # If duration is more than half the minimum, use it
            current_time[0] += duration
        else:
            # Otherwise advance by the minimum to make progress
            current_time[0] += min_advance

    # Initial T0 target is 103.0 (3s from start t=100.0)

    def mock_read(*args, **kwargs):
        # Static timer: 3s until t=102.1, then 1s
        timer_value = 3 if current_time[0] < 102.1 else 1
        return (timer_value, current_time[0])

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(engine, "_read_timer_value", mock_read)
    monkeypatch.setattr(engine, "_sleep_with_budget", mock_sleep_with_budget)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True
    assert len(clicker.spam_calls) == 1
    # Spam should have triggered at or after 102.7 (T0 - 0.3s)
    assert current_time[0] >= 102.7


def test_watch_timer_countdown_lock_prevents_ocr_at_low_timer(monkeypatch) -> None:
    """When timer is <= 3.5s to lead, OCR is not called again and engine sleeps directly to T0-lead."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=1200.0,
        t0_lead_time_s=0.3,
        hysteresis_confirmations=1,
    )

    current_time = [100.0]
    ocr_calls = []

    def mock_monotonic():
        return current_time[0]

    def mock_sleep_with_budget(duration, poll_started, min_sleep=0.0):
        current_time[0] += duration

    def mock_read(*args, **kwargs):
        ocr_calls.append(current_time[0])
        # Return 3s at t=100.0 (T0=103.0, lead target=102.7)
        return (3, current_time[0])

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(engine, "_read_timer_value", mock_read)
    monkeypatch.setattr(engine, "_sleep_with_budget", mock_sleep_with_budget)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True
    assert len(clicker.spam_calls) == 1
    # Exactly 1 OCR call was made because Countdown Lock prevented further 3-second OCR calls!
    assert len(ocr_calls) == 1
    # Time jumped directly to 102.7s (T0 - 0.3s)
    assert current_time[0] >= 102.7


def test_watch_timer_uses_grab_timestamp_not_ocr_finish_time(monkeypatch) -> None:
    """T0 estimate must be computed as grab_time + value, even if OCR finished 3 seconds later."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=1200.0,
        t0_lead_time_s=0.3,
    )

    current_time = [100.0]

    def mock_monotonic():
        return current_time[0]

    def mock_sleep_with_budget(duration, poll_started, min_sleep=0.0):
        current_time[0] += duration

    def mock_read(*args, **kwargs):
        # Frame was grabbed at t=100.0 with 5s timer (T0 should be 105.0)
        grab_t = current_time[0]
        # Simulate 3.0s OCR delay
        current_time[0] += 3.0
        return (5, grab_t)

    monkeypatch.setattr(time, "monotonic", mock_monotonic)
    monkeypatch.setattr(engine, "_read_timer_value", mock_read)
    monkeypatch.setattr(engine, "_sleep_with_budget", mock_sleep_with_budget)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True
    assert len(clicker.spam_calls) == 1
    # T0 is 100.0 + 5 = 105.0. Target lead is 105.0 - 0.3 = 104.7.
    assert 104.7 <= current_time[0] <= 105.0


# NOTE: test_bug_condition_ocr_bottleneck_unfixed_behavior removed — was a
# "characterization log" (log-only counterexample documentation) that
# duplicated coverage provided by the surrounding behavioral watch_timer tests.
# See Phase 3, item P0-4 of the audit.


# ── Tests for Sub-task 3.1: MacroStep.ocr_dynamic_interval_config ───────────


def test_macrostep_ocr_dynamic_interval_config_defaults() -> None:
    """MacroStep.get_ocr_interval_config() returns defaults when field is None."""
    step = MacroStep(type=StepType.WATCH_TIMER)
    config = step.get_ocr_interval_config()
    assert config == {
        "initial_interval": 1.0,
        "accel_threshold": 10.0,
        "min_interval": 0.2,
        "cpu_pause_window": 1.0,
    }


def test_macrostep_ocr_dynamic_interval_config_custom() -> None:
    """MacroStep.get_ocr_interval_config() returns custom config when set."""
    custom_config = {
        "initial_interval": 0.5,
        "accel_threshold": 5.0,
        "min_interval": 0.1,
        "cpu_pause_window": 0.5,
    }
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        ocr_dynamic_interval_config=custom_config,
    )
    assert step.get_ocr_interval_config() == custom_config


# ── Tests for Sub-task 3.2: calculate_adaptive_interval() ─────────────────


def test_calculate_adaptive_interval_well_above_threshold() -> None:
    """When time_remaining >= accel_threshold, return initial_interval."""
    result = calculate_adaptive_interval(
        time_remaining=300.0,
        initial_interval=1.0,
        accel_threshold=10.0,
        min_interval=0.2,
    )
    assert result == 1.0


def test_calculate_adaptive_interval_linear_interpolation() -> None:
    """When time_remaining < accel_threshold, interpolate toward min_interval."""
    result = calculate_adaptive_interval(
        time_remaining=5.0,
        initial_interval=1.0,
        accel_threshold=10.0,
        min_interval=0.2,
    )
    # Expected: 0.2 + (1.0 - 0.2) * (5.0 / 10.0) = 0.2 + 0.8 * 0.5 = 0.6
    assert abs(result - 0.6) < 0.001


def test_calculate_adaptive_interval_at_zero_remaining() -> None:
    """When time_remaining = 0, return min_interval."""
    result = calculate_adaptive_interval(
        time_remaining=0.0,
        initial_interval=1.0,
        accel_threshold=10.0,
        min_interval=0.2,
    )
    assert result == 0.2


def test_calculate_adaptive_interval_zero_accel_threshold() -> None:
    """When accel_threshold <= 0, return min_interval (edge case)."""
    result = calculate_adaptive_interval(
        time_remaining=5.0,
        initial_interval=1.0,
        accel_threshold=0.0,
        min_interval=0.2,
    )
    assert result == 0.2


def test_calculate_adaptive_interval_clamping() -> None:
    """Result is clamped between min_interval and initial_interval."""
    result = calculate_adaptive_interval(
        time_remaining=15.0,  # > accel_threshold, should clamp to initial
        initial_interval=1.0,
        accel_threshold=10.0,
        min_interval=0.2,
    )
    assert result == 1.0


# ── Tests for Sub-task 3.3: calculate_avg_delta() ───────────────────────


def test_calculate_avg_delta_smooth_descent() -> None:
    """Smooth countdown: uniform time intervals produce avg_delta ≈ 1.0."""
    timer_history = [
        {"value": 100, "time": 0.0},
        {"value": 99, "time": 1.0},
        {"value": 98, "time": 2.0},
    ]
    result = calculate_avg_delta(timer_history)
    assert abs(result - 1.0) < 0.001


def test_calculate_avg_delta_varying_intervals() -> None:
    """Varying intervals produce correct average."""
    timer_history = [
        {"value": 100, "time": 0.0},
        {"value": 98.5, "time": 1.0},  # Δtime=1.0, Δvalue=1.5, delta=0.667
        {"value": 97.1, "time": 2.5},  # Δtime=1.5, Δvalue=1.4, delta=1.071
    ]
    result = calculate_avg_delta(timer_history)
    # avg = (0.667 + 1.071) / 2 ≈ 0.869
    assert abs(result - 0.869) < 0.01


def test_calculate_avg_delta_with_none_values() -> None:
    """Entries with None values are skipped gracefully."""
    timer_history = [
        {"value": 100, "time": 0.0},
        {"value": None, "time": 1.0},  # Skip this pair
        {"value": 98, "time": 2.0},
    ]
    result = calculate_avg_delta(timer_history)
    # Only one valid delta: (100-98) / (2-0) = 2 / 2 = 1.0
    assert abs(result - 1.0) < 0.001


def test_calculate_avg_delta_skip_jumps() -> None:
    """Jump (Δvalue > 2.0) is skipped."""
    timer_history = [
        {"value": 100, "time": 0.0},
        {"value": 95, "time": 1.0},  # Jump: Δvalue=5.0 > 2.0, skip
        {"value": 94, "time": 2.0},
    ]
    result = calculate_avg_delta(timer_history)
    # Only one valid delta: (95-94) / (2-1) = 1.0
    assert abs(result - 1.0) < 0.001


def test_calculate_avg_delta_empty_list() -> None:
    """Empty or too-short list returns safe default 1.0."""
    assert calculate_avg_delta([]) == 1.0
    assert calculate_avg_delta([{"value": 100, "time": 0.0}]) == 1.0


def test_calculate_avg_delta_no_valid_deltas() -> None:
    """When no valid deltas exist (all jumps/None), return default 1.0."""
    timer_history = [
        {"value": 100, "time": 0.0},
        {"value": 90, "time": 1.0},  # Jump > 2.0
        {"value": 80, "time": 2.0},  # Jump > 2.0
    ]
    result = calculate_avg_delta(timer_history)
    assert result == 1.0


# ── Tests for Sub-task 3.4: should_trigger_spam() ──────────────────────


def test_should_trigger_spam_ocr_hysteresis_met() -> None:
    """OCR + hysteresis: low timer + enough confirmations triggers spam."""
    result = should_trigger_spam(
        ocr_timer_value=3,
        estimated_t0_mono=None,
        confirmed_count=2,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is True


def test_should_trigger_spam_ocr_hysteresis_not_met() -> None:
    """OCR low timer but hysteresis not satisfied: no trigger."""
    result = should_trigger_spam(
        ocr_timer_value=3,
        estimated_t0_mono=None,
        confirmed_count=1,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is False


def test_should_trigger_spam_ocr_timer_not_low() -> None:
    """OCR timer > spam_threshold: no trigger."""
    result = should_trigger_spam(
        ocr_timer_value=10,
        estimated_t0_mono=None,
        confirmed_count=5,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is False


def test_should_trigger_spam_ocr_timer_none() -> None:
    """OCR failed (timer=None): no trigger via OCR."""
    result = should_trigger_spam(
        ocr_timer_value=None,
        estimated_t0_mono=None,
        confirmed_count=2,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is False


def test_should_trigger_spam_estimated_t0_reached(monkeypatch) -> None:
    """Monotonic T0 estimate reached (within ±0.2s): trigger."""
    current_time = [100.0]

    def mock_monotonic():
        return current_time[0]

    monkeypatch.setattr(time, "monotonic", mock_monotonic)

    result = should_trigger_spam(
        ocr_timer_value=8,
        estimated_t0_mono=100.1,  # Within ±0.2s of 100.0
        confirmed_count=0,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is True


def test_should_trigger_spam_estimated_t0_not_reached(monkeypatch) -> None:
    """Monotonic T0 estimate not yet reached (>0.2s away): no trigger."""
    current_time = [100.0]

    def mock_monotonic():
        return current_time[0]

    monkeypatch.setattr(time, "monotonic", mock_monotonic)

    result = should_trigger_spam(
        ocr_timer_value=8,
        estimated_t0_mono=100.5,  # >0.2s away
        confirmed_count=0,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is False


def test_should_trigger_spam_no_conditions_met() -> None:
    """No trigger conditions met: returns False."""
    result = should_trigger_spam(
        ocr_timer_value=10,
        estimated_t0_mono=None,
        confirmed_count=0,
        hysteresis_confirmations=2,
        spam_threshold=5,
    )
    assert result is False


def test_watch_timer_triggers_immediately_at_gui_spam_threshold(monkeypatch) -> None:
    """When timer hits GUI spam_threshold (e.g. 5s), spam phase starts immediately on 5s,
    not sleeping until 2s before 0."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=1200.0,
        t0_lead_time_s=0.3,
        hysteresis_confirmations=1,
    )

    readings = [5]  # Hits threshold on first read!

    def mock_read(*args, **kwargs):
        val = readings.pop(0) if readings else 5
        return (val, time.monotonic())

    monkeypatch.setattr(engine, "_read_timer_value", mock_read)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    assert engine._step_results[1]["triggered"] is True
    assert len(clicker.spam_calls) == 1


def test_watch_timer_timer_increase_resets_spam_and_does_not_trigger_on_none(monkeypatch) -> None:
    """If timer increases (e.g. 5s -> 25s because a player left), it does NOT trigger spam,
    and a subsequent None reading is NOT treated as disappearance."""
    clicker = _FakeClicker()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 45.0, "top": 16.5, "right": 55.0, "bottom": 22.5},
        click_x=50,
        click_y=52,
        spam_threshold_s=5,
        fast_threshold_s=300,
        timeout_s=0.5,  # Times out after increase
        hysteresis_confirmations=2,
    )

    # 1. 5s (hysteresis 1/2)
    # 2. Timer increases to 25s (resets confirmed_count to 0, last_known_value to 25)
    # 3. None (temporary OCR miss at 25s: last_known_value=25 > 5 -> NOT disappearance!)
    readings = [5, 25, None]

    def mock_read(*args, **kwargs):
        val = readings.pop(0) if readings else None
        return (val, time.monotonic())

    monkeypatch.setattr(engine, "_read_timer_value", mock_read)
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *args, **kwargs: None)

    engine._handle_watch_timer(1, step, win)

    # Should time out without triggering spam
    assert engine._step_results[1]["triggered"] is False
    assert len(clicker.spam_calls) == 0


def test_resolve_spam_params_uses_config_cps() -> None:
    """_resolve_spam_params must prefer config.spam_clicks_per_sec instead of hardcoded 38."""
    from mvp.config import MVPConfig

    config = MVPConfig(spam_clicks_per_sec=28)
    engine = MacroEngine(
        clicker=_FakeClicker(),
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
        config=config,
    )
    duration, cps = engine._resolve_spam_params()
    assert cps == 28, f"Expected 28 from config, got {cps}"


def test_watch_timer_safe_when_spam_click_raises_clicker_error(monkeypatch) -> None:
    """watch_timer must not crash unhandled if spam_click raises ClickerError."""
    from mvp.bot.exceptions import ClickerError

    clicker = _FakeClicker()
    def failing_spam(*args, **kwargs):
        raise ClickerError("Simulated SendInput failure (Error 5)")
    clicker.spam_click = failing_spam

    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=None,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 40.0, "top": 10.0, "right": 60.0, "bottom": 20.0},
        spam_threshold_s=5,
        hysteresis_confirmations=1,
    )
    monkeypatch.setattr(engine, "_read_timer_value", lambda *a, **kw: (3, time.monotonic()))
    monkeypatch.setattr(engine, "_sleep_with_budget", lambda *a, **kw: None)

    # Must catch and not raise ClickerError
    engine._handle_watch_timer(1, step, win)
    assert engine._step_results[1]["triggered"] is True


def test_scroll_listen_chat_direct_click_executes_immediately(monkeypatch) -> None:
    """Verify that when direct_click=True, clicker.click_at is called immediately
    in the same millisecond the alert is detected in scroll_listen_chat."""
    clicker = _FakeScrollClicker()
    ocr = _FakeChatOCR()
    engine = MacroEngine(
        clicker=clicker,
        chat_ocr=ocr,
        timer_ocr=None,
        capture=_FakeCapture(),
    )
    win = WindowContext(left=100, top=100, width=1920, height=1080)
    step = MacroStep(
        type=StepType.SCROLL_LISTEN_CHAT,
        roi_pct={"left": 38.2, "top": 17.9, "right": 61.7, "bottom": 90.7},
        chat_bar_roi={"left": 65.7, "top": 93.1, "right": 94.0, "bottom": 98.7},
        alliance_tab_roi={"left": 47.6, "top": 5.5, "right": 52.4, "bottom": 9.7},
        verify_alliance_open=True,
        timeout_s=5.0,
        direct_click=True,
    )
    monkeypatch.setattr(engine, "_is_alliance_chat_open", lambda *a, **kw: True)

    engine._handle_scroll_listen_chat(1, step, win)

    assert engine._step_results[1]["detected"] is True
    assert engine.memory.get("step_1_direct_clicked") is True
    # Clicker must have registered the immediate direct click!
    assert len(clicker.clicks) == 1


def test_handle_click_check_march_modal_dismisses_when_present(monkeypatch) -> None:
    """When check_march_modal=True and modal is present, MacroEngine dismisses it (checkbox + confirm)."""
    engine = _make_engine()
    # Create frame with yellow confirm button (BGR yellow: 0, 220, 240)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[580:640, 800:960] = (0, 220, 240)
    engine.capture.frame = frame

    win = WindowContext(left=100, top=200, width=1920, height=1080)
    step = MacroStep(
        type=StepType.CLICK,
        roi_pct={"left": 43.8, "top": 71.2, "right": 52.0, "bottom": 75.6},
        check_march_modal=True,
    )

    # Don't wait full 0.35s in unit test
    monkeypatch.setattr(engine._stop_requested, "wait", lambda timeout=None: False)

    engine._handle_click(step, win)

    # Clicks should be:
    # 1. Main click (Step 6 March button)
    # 2. Checkbox click
    # 3. Confirm button click
    assert len(engine.clicker.clicks) == 3
    # Step 6 March click (center of ROI)
    assert engine.clicker.clicks[0] == (1020, 993)
    # Checkbox click (cb_x, cb_y)
    assert engine.clicker.clicks[1] == (988, 714)
    # Confirm click (confirm_x, confirm_y)
    assert engine.clicker.clicks[2] == (980, 810)


def test_handle_click_check_march_modal_ignores_when_absent(monkeypatch) -> None:
    """When check_march_modal=True and modal is NOT present, MacroEngine does nothing extra."""
    engine = _make_engine()
    # Clean black frame — no modal
    engine.capture.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    win = WindowContext(left=100, top=200, width=1920, height=1080)
    step = MacroStep(
        type=StepType.CLICK,
        roi_pct={"left": 43.8, "top": 71.2, "right": 52.0, "bottom": 75.6},
        check_march_modal=True,
    )

    monkeypatch.setattr(engine._stop_requested, "wait", lambda timeout=None: False)

    engine._handle_click(step, win)

    # Exactly 1 click — the March button itself, 0 extra clicks!
    assert len(engine.clicker.clicks) == 1
    assert engine.clicker.clicks[0] == (1020, 993)


def test_watch_timer_dismisses_march_modal_at_start(monkeypatch) -> None:
    """When watch_timer starts and modal is still visible, it dismisses it before reading timer."""
    engine = _make_engine()
    frame_with_modal = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame_with_modal[580:640, 800:960] = (0, 220, 240)
    engine.capture.frame = frame_with_modal

    win = WindowContext(left=0, top=0, width=1920, height=1080)
    step = MacroStep(
        type=StepType.WATCH_TIMER,
        roi_pct={"left": 47.7, "top": 36.2, "right": 52.2, "bottom": 38.5},
        timeout_s=1.0,
    )

    # Don't sleep during test
    monkeypatch.setattr(engine._stop_requested, "wait", lambda timeout=None: False)
    # Terminate loop as soon as first timer read is attempted
    monkeypatch.setattr(engine, "_read_timer_value", lambda *a, **kw: engine._stop_requested.set() or (10, time.monotonic()))

    engine._handle_watch_timer(1, step, win)

    # Modal should have been dismissed: checkbox + confirm
    assert (888, 514) in engine.clicker.clicks
    assert (880, 610) in engine.clicker.clicks



