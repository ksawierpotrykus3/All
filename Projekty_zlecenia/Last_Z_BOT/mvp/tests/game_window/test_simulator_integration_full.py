"""
Integration test suite for the deterministic GameSimulator state machine.

The legacy simulator (frame queues, ROI colour sniffing, auto-triggered alerts,
`extract_rois_from_frame` / `track_click_in_roi` / `connect_to_bot`-thread API)
was removed in the deterministic rewrite. The simulator is now a state machine
(no_chat -> chat -> alert -> helka) driven by the bot's real clicks, and the bot
reads frames through a capture frame-source wired by `connect_to_bot`.

This suite validates the *integration* surface that unit tests do not cover:
  - bot capture <-> simulator frame source wiring,
  - the helicopter alert snippet being composited inside the scroll_listen ROI
    (so SCROLL_LISTEN_CHAT OCR actually finds it),
  - renderer + click-driver concurrency staying consistent,
  - strict (bot) alert clicks mapping OCR percents to the current viewport,
  - neutral in-helka clicks not polluting click accuracy,
  - clean reset across multiple macro iterations.
"""

import threading
import time

import numpy as np
import pytest

from mvp import macro_def as md
from mvp.bot.coordinates import calib_y_to_client_fraction
from mvp.simulator.game import GameSimulator, _roi_to_pixels

VIEW_W, VIEW_H = 1920, 1080


def _roi_center(roi_pct, vw: int = VIEW_W, vh: int = VIEW_H) -> tuple[int, int]:
    """Frame-pixel centre of an ROI for an arbitrary viewport."""
    left, top, right, bottom = _roi_to_pixels(roi_pct, vw, vh)
    return (int((left + right) // 2), int((top + bottom) // 2))


def _click(sim: GameSimulator, roi_pct) -> bool:
    """Click the centre of `roi_pct` in the simulator's current viewport."""
    with sim._lock:
        vw, vh = sim.viewport_size
    return sim.handle_click(*_roi_center(roi_pct, vw, vh))


def _to_chat(sim: GameSimulator) -> None:
    assert _click(sim, md._ROI_CHAT_BAR) is True
    assert sim.current_state == "chat"


def _to_alert(sim: GameSimulator) -> None:
    _to_chat(sim)
    assert _click(sim, md._ROI_ALLIANCE_TAB) is True
    assert sim.current_state == "alert"


class _Capture:
    """Minimal stand-in for the bot capture object the simulator feeds frames to."""

    def __init__(self):
        self.source = None

    def set_frame_source(self, source) -> None:
        self.source = source


class _Bot:
    """Minimal stand-in for a bot runner exposing a capture + frame queue."""

    frame_queue = "BOT_FRAME_QUEUE"

    def __init__(self):
        self.capture = _Capture()


def test_connect_to_bot_feeds_capture_and_keeps_queue_reference():
    """connect_to_bot wires the frame source so the bot sees simulator state."""
    sim = GameSimulator()
    bot = _Bot()

    sim.connect_to_bot(bot)

    assert bot.capture.source is not None
    assert sim.frame_queue == "BOT_FRAME_QUEUE"

    # The capture source is a live viewport-sized frame of the current state.
    no_chat_frame = bot.capture.source()
    assert no_chat_frame.shape[:2] == (VIEW_H, VIEW_W)

    # After the macro opens the chat bar the bot's next read reflects the state.
    _to_chat(sim)
    chat_frame = bot.capture.source()
    assert chat_frame.shape[:2] == (VIEW_H, VIEW_W)
    assert not np.array_equal(no_chat_frame, chat_frame)


def test_alert_snippet_is_composited_inside_scroll_listen_roi():
    """In the alert state the OCR-scanned ROI must actually contain the alert."""
    sim = GameSimulator()
    sim.set_viewport_size(VIEW_W, VIEW_H)
    _to_chat(sim)
    base = sim.get_current_frame_raw()

    assert _click(sim, md._ROI_ALLIANCE_TAB) is True
    assert sim.current_state == "alert"
    alert_frame = sim.get_current_frame_raw()

    left, top, right, bottom = _roi_to_pixels(md._ROI_SCROLL_LISTEN, VIEW_W, VIEW_H)
    region_before = base[top:bottom, left:right]
    region_alert = alert_frame[top:bottom, left:right]
    assert region_before.shape == region_alert.shape
    # The overlay changed pixels inside the scroll ROI, i.e. the alert appears
    # exactly where SCROLL_LISTEN_CHAT runs its OCR scan.
    assert not np.array_equal(region_before, region_alert)


def test_strict_alert_click_maps_ocr_percent_to_current_viewport():
    """Bot-mode alert clicks use OCR percents converted at the live viewport."""
    sim = GameSimulator()
    sim.set_viewport_size(800, 600)
    sim.strict_alert_hit = True
    _to_alert(sim)

    # No OCR-detected position yet: even a click in the scroll ROI is a miss.
    assert _click(sim, md._ROI_SCROLL_LISTEN) is False
    assert sim.current_state == "alert"

    # Bot reports the detected alert at 25%/25% of the (calibrated) screen.
    sim.expected_chat_click_pct = (25.0, 25.0)
    px = int(25.0 / 100.0 * 800)
    py = int(calib_y_to_client_fraction(25.0) * 600)
    assert sim.handle_click(px, py) is True
    assert sim.current_state == "helka"


def test_helka_actions_are_neutral_for_accuracy():
    """In-helka macro clicks log neutrally and never distort hit accuracy."""
    sim = GameSimulator()
    _to_alert(sim)
    assert _click(sim, md._ROI_SCROLL_LISTEN) is True  # alert -> helka
    assert sim.current_state == "helka"

    for _ in range(3):
        assert _click(sim, md._ROI_HELICOPTER_SELECT) is False  # neutral
    assert sim.current_state == "helka"

    stats = sim.get_click_statistics()
    # chat hit + alliance hit + scroll hit = 3 attempts, 3 neutral helka clicks.
    assert stats["total_clicks"] == 6  # neutral clicks are still logged
    assert stats["hits"] == 3  # but excluded from accuracy
    assert stats["accuracy_percent"] == 100.0
    assert sim.click_log[-1]["hit"] is None


def test_multi_iteration_loop_resets_cleanly():
    """Several macro iterations reset to no_chat without leaking alert state."""
    sim = GameSimulator()
    for _ in range(3):
        _to_alert(sim)
        assert sim.alert_start_time is not None
        assert _click(sim, md._ROI_SCROLL_LISTEN) is True
        assert sim.current_state == "helka"

        sim.reset_to_chat()
        assert sim.current_state == "no_chat"
        assert sim.alert_start_time is None

    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 9
    assert stats["hits"] == 9
    assert stats["accuracy_percent"] == 100.0


def test_concurrent_render_load_does_not_break_state_machine():
    """Renderer threads reading frames/stats never corrupt the click driver."""
    sim = GameSimulator()
    stop = threading.Event()
    errors: list[Exception] = []

    def hammer() -> None:
        while not stop.is_set():
            try:
                frame = sim.get_current_frame_raw()
                sim.render_roi_boxes(frame)
                sim.get_click_statistics()
            except Exception as exc:  # pragma: no cover - failure evidence only
                errors.append(exc)
            time.sleep(0.001)

    readers = [threading.Thread(target=hammer) for _ in range(2)]
    for t in readers:
        t.start()

    try:
        _to_alert(sim)
        assert sim.alert_start_time is not None
        assert _click(sim, md._ROI_SCROLL_LISTEN) is True
        assert sim.current_state == "helka"
    finally:
        stop.set()
        for t in readers:
            t.join()

    assert errors == []
    assert sim.current_state == "helka"
    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 3
    assert stats["hits"] == 3
    assert len(sim.click_markers) == len(sim.click_log) == 3


def test_roi_overlay_renders_at_small_viewport():
    """ROI boxes and the strict-mode crosshair render at non-native sizes."""
    sim = GameSimulator()
    sim.set_viewport_size(640, 360)

    frame = sim.get_current_frame_raw()
    out = sim.render_roi_boxes(frame)
    assert out.shape == (360, 640, 3)

    _to_alert(sim)
    sim.strict_alert_hit = True
    sim.expected_chat_click_pct = (50.0, 50.0)
    alert_out = sim.render_roi_boxes(sim.get_current_frame_raw())
    assert alert_out.shape == (360, 640, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
