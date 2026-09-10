"""
Bot-connection tests for the deterministic GameSimulator.

The legacy AdvancedGameSimulator consumed a BotRunner frame queue, sniffed ROI
colours out of bot-drawn frames (`extract_rois_from_frame`, `latest_rois`,
`update_roi_from_bot`) and auto-triggered alerts when it saw green/red boxes.
That whole pipeline was removed in the deterministic rewrite: the state machine
(no_chat -> chat -> alert -> helka) advances only via `handle_click`, and the
simulator feeds the bot through a capture frame-source wired by
`connect_to_bot`.

This suite validates the surviving bot-connection surface:
  - `connect_to_bot` wiring of the capture frame-source + frame queue,
  - the frame-source output tracking the deterministic state machine,
  - the no-op legacy frame-reader API (no threads are ever started),
  - bot frames no longer auto-trigger anything,
  - macro ROI percent rects mapping to sane viewport pixel rectangles.
"""

import queue

import cv2
import numpy as np
import pytest

from mvp import macro_def as md
from mvp.simulator.game import _MACRO_ROIS, GameSimulator, _roi_to_pixels

VIEW_W, VIEW_H = 1920, 1080


class _Capture:
    """Minimal capture stand-in with the frame-source hook the simulator uses."""

    def __init__(self):
        self.source = None
        self.set_frame_source_calls = 0

    def set_frame_source(self, source) -> None:
        self.set_frame_source_calls += 1
        self.source = source


class _BotRunner:
    """Minimal bot runner exposing a capture and a frame queue."""

    def __init__(self, frame_queue=None):
        self.capture = _Capture()
        self.frame_queue = frame_queue


def _roi_center(roi_pct, vw: int = VIEW_W, vh: int = VIEW_H) -> tuple[int, int]:
    left, top, right, bottom = _roi_to_pixels(roi_pct, vw, vh)
    return (int((left + right) // 2), int((top + bottom) // 2))


def test_connect_to_bot_wires_capture_frame_source():
    """The bot capture is fed a live frame source during connect_to_bot."""
    sim = GameSimulator()
    bot = _BotRunner()

    sim.connect_to_bot(bot)

    assert bot.capture.set_frame_source_calls == 1
    assert bot.capture.source is not None
    frame = bot.capture.source()
    assert isinstance(frame, np.ndarray)
    assert frame.dtype == np.uint8
    assert frame.shape == (VIEW_H, VIEW_W, 3)


def test_connect_to_bot_keeps_frame_queue_reference():
    """connect_to_bot stores the bot runner frame queue (API compatibility)."""
    sim = GameSimulator()
    assert sim.frame_queue is None

    frame_queue = queue.Queue(maxsize=2)
    sim.connect_to_bot(_BotRunner(frame_queue=frame_queue))

    assert sim.frame_queue is frame_queue


def test_connect_to_bot_without_capture_or_queue_is_safe():
    """A runner with no capture/frame_queue still connects without error."""
    sim = GameSimulator()

    sim.connect_to_bot(object())  # neither capture nor frame_queue attributes
    assert sim.frame_queue is None

    bot = _BotRunner(frame_queue=queue.Queue())
    bot.capture = None  # capture exists but is None -> skipped
    sim.connect_to_bot(bot)
    assert sim.frame_queue is not None


def test_capture_frame_source_tracks_state_transitions():
    """The frame the bot receives changes with every machine transition."""
    sim = GameSimulator()
    bot = _BotRunner()
    sim.connect_to_bot(bot)
    source = bot.capture.source

    no_chat = source()
    assert np.array_equal(no_chat, sim.images["no_chat"])

    assert sim.handle_click(*_roi_center(md._ROI_CHAT_BAR)) is True
    chat = source()
    assert np.array_equal(chat, sim.images["chat"])
    assert not np.array_equal(no_chat, chat)

    assert sim.handle_click(*_roi_center(md._ROI_ALLIANCE_TAB)) is True
    alert = source()  # base chat image + composited alert snippet
    assert not np.array_equal(chat, alert)

    sim.reset_to_chat()
    assert np.array_equal(source(), sim.images["no_chat"])


def test_capture_frame_source_matches_current_viewport_size():
    """The frame source always returns viewport-sized frames (1:1 with window)."""
    sim = GameSimulator()
    bot = _BotRunner()
    sim.connect_to_bot(bot)
    source = bot.capture.source

    sim.set_viewport_size(800, 600)
    assert source().shape == (600, 800, 3)

    sim.set_viewport_size(VIEW_W, VIEW_H)
    assert source().shape == (VIEW_H, VIEW_W, 3)


def test_legacy_frame_reader_api_is_noop_and_never_starts_threads():
    """The removed worker-thread frame reader survives only as a no-op."""
    sim = GameSimulator()
    sim.connect_to_bot(_BotRunner(frame_queue=queue.Queue()))

    assert sim.bot_thread is None

    sim.start_frame_reader()
    sim.start_frame_reader()  # idempotent: no new thread, no error
    sim.stop_frame_reader()
    sim.stop_frame_reader()

    assert sim.bot_thread is None
    assert sim.running is True


def test_bot_frames_no_longer_auto_trigger_anything():
    """Pushing frames into the queue never advances the state machine."""
    sim = GameSimulator()
    frame_queue = queue.Queue(maxsize=2)
    sim.connect_to_bot(_BotRunner(frame_queue=frame_queue))

    # Legacy behaviour: a green-box frame auto-triggered the alert. Now the
    # queue is never consumed and the frame content is irrelevant.
    frame = np.zeros((VIEW_H, VIEW_W, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (300, 300), (0, 255, 0), 3)
    frame_queue.put_nowait(frame)

    assert sim.current_state == "no_chat"
    assert sim.latest_rois == []
    assert sim.alert_start_time is None

    # The machine still advances only via a real click in the chat bar.
    assert sim.handle_click(*_roi_center(md._ROI_CHAT_BAR)) is True
    assert sim.current_state == "chat"


def test_macro_rois_map_to_valid_viewport_rectangles():
    """Every macro ROI maps to a sane, non-empty pixel rect in the viewport."""
    sim = GameSimulator()
    vw, vh = sim.viewport_size

    for name, roi_pct in _MACRO_ROIS:
        left, top, right, bottom = _roi_to_pixels(roi_pct, vw, vh)
        assert left < right, f"{name}: empty width ({left},{right})"
        assert top < bottom, f"{name}: empty height ({top},{bottom})"
        assert 0 <= left < vw, f"{name}: left out of viewport"
        assert 0 <= top < vh, f"{name}: top out of viewport"
        assert 0 < right <= vw, f"{name}: right out of viewport"
        assert 0 < bottom <= vh, f"{name}: bottom out of viewport"
        # Small helper ROIs (explore/timer/...) are legitimately tiny, but a
        # healthy rect must still be at least 0.1% of the frame in area.
        assert (right - left) * (bottom - top) >= (vw * vh) // 1000, (
            f"{name}: suspiciously small ROI"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
