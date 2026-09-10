"""
End-to-end integration tests for the deterministic GameSimulator state machine.

The simulator no longer auto-triggers alerts from frame queues / ROI colors.
It is a deterministic state machine (no_chat -> chat -> alert -> helka) that is
driven by the macro bot's real clicks landing in the correct ROIs. These tests
replay the full loop the way the helicopter macro is expected to play it.
"""

import numpy as np

from mvp import macro_def as md
from mvp.bot.coordinates import calib_y_to_client_fraction
from mvp.simulator.game import GameSimulator, _roi_to_pixels

VIEW_W, VIEW_H = 1920, 1080


def _roi_center(roi_pct):
    left, top, right, bottom = _roi_to_pixels(roi_pct, VIEW_W, VIEW_H)
    return (int((left + right) // 2), int((top + bottom) // 2))


def _click_to_chat(sim) -> None:
    sim.handle_click(*_roi_center(md._ROI_CHAT_BAR))


def _click_to_alert(sim) -> None:
    _click_to_chat(sim)
    sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB))


def test_e2e_full_macro_loop_replays_and_resets():
    """Full deterministic loop: no_chat -> chat -> alert -> helka -> reset."""
    sim = GameSimulator()
    assert sim.current_state == "no_chat"

    assert sim.handle_click(*_roi_center(md._ROI_CHAT_BAR)) is True
    assert sim.current_state == "chat"
    assert sim.alert_start_time is None

    assert sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB)) is True
    assert sim.current_state == "alert"
    assert sim.alert_start_time is not None

    assert sim.handle_click(*_roi_center(md._ROI_SCROLL_LISTEN)) is True
    assert sim.current_state == "helka"

    # In-helka macro actions are neutral and do not change the state.
    assert sim.handle_click(*_roi_center(md._ROI_HELICOPTER_SELECT)) is False
    assert sim.current_state == "helka"

    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 4
    assert stats["hits"] == 3
    assert stats["accuracy_percent"] == 100.0

    sim.reset_to_chat()
    assert sim.current_state == "no_chat"
    assert sim.alert_start_time is None


def test_alert_reached_only_via_correct_roi_clicks():
    """Wrong-area clicks must never advance the state machine."""
    sim = GameSimulator()

    assert sim.handle_click(10, 10) is False
    assert sim.current_state == "no_chat"

    # alliance_tab is not the active target while in no_chat.
    assert sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB)) is False
    assert sim.current_state == "no_chat"

    _click_to_chat(sim)
    # In chat the active target is alliance_tab; clicking chat_bar again is a miss.
    assert sim.handle_click(*_roi_center(md._ROI_CHAT_BAR)) is False
    assert sim.current_state == "chat"

    sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB))
    # In alert the alliance_tab is outside the scroll ROI -> still a miss.
    assert sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB)) is False
    assert sim.current_state == "alert"


def test_click_logging_records_state_and_hit():
    sim = GameSimulator()

    assert sim.handle_click(10, 10) is False
    assert sim.handle_click(*_roi_center(md._ROI_CHAT_BAR)) is True

    assert len(sim.click_log) == 2
    miss_entry = sim.click_log[0]
    assert miss_entry["x"] == 10
    assert miss_entry["y"] == 10
    assert miss_entry["hit"] is False
    assert miss_entry["roi_name"] == "no_chat"
    assert "timestamp" in miss_entry

    hit_entry = sim.click_log[1]
    assert hit_entry["hit"] is True
    assert hit_entry["roi_name"] == "no_chat"
    assert sim.click_markers[-1][3] is True


def test_click_accuracy_two_hits_three_attempts():
    """HIT chat, HIT alliance, MISS inside alert -> 66.67%."""
    sim = GameSimulator()
    sim.handle_click(*_roi_center(md._ROI_CHAT_BAR))
    sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB))
    assert sim.handle_click(10, 10) is False  # miss, stays in alert

    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 3
    assert stats["hits"] == 2
    assert abs(stats["accuracy_percent"] - 66.67) < 0.1


def test_click_accuracy_all_hits():
    sim = GameSimulator()
    _click_to_alert(sim)
    sim.handle_click(*_roi_center(md._ROI_SCROLL_LISTEN))

    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 3
    assert stats["hits"] == 3
    assert stats["accuracy_percent"] == 100.0


def test_click_accuracy_all_misses():
    sim = GameSimulator()
    for _ in range(3):
        assert sim.handle_click(10, 10) is False

    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 3
    assert stats["hits"] == 0
    assert stats["accuracy_percent"] == 0.0
    assert sim.current_state == "no_chat"


def test_click_log_empty_statistics():
    sim = GameSimulator()
    assert sim.click_log == []
    stats = sim.get_click_statistics()
    assert stats["total_clicks"] == 0
    assert stats["hits"] == 0
    assert stats["accuracy_percent"] == 0.0


def test_bot_strict_mode_requires_ocr_detected_alert_position():
    """In bot mode the alert transition waits for the OCR-detected click target."""
    sim = GameSimulator()
    sim.strict_alert_hit = True
    _click_to_alert(sim)

    # No OCR position known yet -> even a click in the scroll ROI does nothing.
    assert sim.handle_click(*_roi_center(md._ROI_SCROLL_LISTEN)) is False
    assert sim.current_state == "alert"

    # Bot reports the detected alert position (Step-2 click target).
    sim.expected_chat_click_pct = (50.0, 50.0)
    px = int(50.0 / 100.0 * VIEW_W)
    py = int(calib_y_to_client_fraction(50.0) * VIEW_H)
    assert sim.handle_click(px, py) is True
    assert sim.current_state == "helka"


def test_alert_state_is_visualized_in_frame():
    """The alert snippet is composited onto the chat frame while in alert."""
    sim = GameSimulator()
    chat_frame = sim.get_current_frame_raw()
    _click_to_alert(sim)
    alert_frame = sim.get_current_frame_raw()
    assert alert_frame.shape == chat_frame.shape
    assert not (alert_frame == chat_frame).all()


def test_frame_is_1_1_with_viewport_and_state():
    sim = GameSimulator()
    raw = sim.get_current_frame_raw()
    assert raw.shape == (VIEW_H, VIEW_W, 3)

    sim.set_viewport_size(800, 600)
    assert sim.get_current_frame_raw().shape == (600, 800, 3)
    # Reset viewport for subsequent state checks.
    sim.set_viewport_size(VIEW_W, VIEW_H)

    assert np.array_equal(sim.get_current_frame_raw(), sim.images["no_chat"])
    _click_to_chat(sim)
    assert np.array_equal(sim.get_current_frame_raw(), sim.images["chat"])


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
