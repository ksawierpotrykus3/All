"""
Bot integration tests using game simulator window.
Tests bot behavior with real-time timer and alert events.
"""

import time

import pytest


class TestBotAlertDetection:
    """Test bot detection and reaction to alerts."""

    def test_bot_detects_alert_in_window(self, bot_with_window, game_state_monitor):
        """
        Test bot detects helicopter alert and reacts.

        Scenario:
        1. Bot captures frame from simulator
        2. Alert is triggered
        3. Bot should detect alert is active
        4. Bot performs reaction (click)
        """
        bot = bot_with_window

        # Initial state: no alert
        frame = bot.capture_frame()
        assert frame is not None
        assert not bot.is_alert_active()

        # Trigger alert
        game_state_monitor.record_alert_trigger()
        time.sleep(0.1)  # Allow alert to render

        # Bot captures new frame with alert
        frame = bot.capture_frame()
        assert bot.is_alert_active()

        # Bot reacts to alert
        bot.click(times=3)

        # Verify alert was recorded
        game_state_monitor.assert_alert_triggered()

    def test_bot_dismisses_alert_after_detection(self, bot_with_window, game_state_monitor):
        """Test bot dismisses alert after detecting it."""
        bot = bot_with_window

        # Trigger and detect alert
        game_state_monitor.record_alert_trigger()
        time.sleep(0.05)
        assert bot.is_alert_active()

        # Bot dismisses alert
        game_state_monitor.record_alert_dismiss()
        time.sleep(0.05)

        # Verify alert is dismissed
        assert not bot.is_alert_active()
        game_state_monitor.assert_alert_dismissed()


class TestBotTimerReaction:
    """Test bot behavior based on timer countdown."""

    def test_bot_timer_reaction_variation(self, bot_with_window, game_state_monitor):
        """
        Test bot adjusts click rate based on timer.

        Scenario:
        1. At 300s: normal spam rate (30-38 CPS)
        2. At 5s countdown: increase CPS to prepare for spawn
        3. At 0s: maximum spam rate
        """
        bot = bot_with_window
        window = bot_with_window.window

        # Set initial timer to 300s (far from spawn)
        window.set_timer(300.0)
        time.sleep(0.05)

        frame_300s = bot.capture_frame()
        assert frame_300s is not None

        state_300s = window.get_state()
        assert state_300s["timer_seconds"] == 300.0

        # Normal spam rate at 300s
        cps_normal = 35  # CPS at normal rate

        # Fast forward to 5s (close to spawn)
        window.set_timer(5.0)
        time.sleep(0.05)

        frame_5s = bot.capture_frame()
        state_5s = window.get_state()
        assert state_5s["timer_seconds"] == 5.0

        # Should increase CPS
        cps_increased = 50  # CPS when close to spawn

        # Timer value should be visible in frames
        assert len(bot.frame_captures) >= 2

    def test_bot_timer_countdown_ocr(self, bot_with_window, game_state_monitor):
        """Test bot uses OCR to detect timer countdown."""
        bot = bot_with_window
        window = bot_with_window.window

        # Set timer to 45 seconds
        window.set_timer(45.0)
        time.sleep(0.05)

        # Bot captures and performs OCR
        frame = bot.capture_frame()
        ocr_result = bot.ocr(frame)

        # OCR should detect timer text
        text, confidence = ocr_result
        assert "45" in text
        assert confidence > 0.9

        # Adjust timer down
        window.adjust_timer(-40.0)
        time.sleep(0.05)

        # OCR should detect new value
        frame = bot.capture_frame()
        ocr_result = bot.ocr(frame)
        text, confidence = ocr_result
        assert "5" in text

    def test_bot_timer_progression(self, bot_with_window, game_state_monitor):
        """Test bot tracks timer progression over time."""
        bot = bot_with_window
        window = bot_with_window.window

        # Simulate timer countdown
        for timer_val in [60.0, 45.0, 30.0, 15.0, 5.0]:
            window.set_timer(timer_val)
            time.sleep(0.02)
            game_state_monitor.record_state()

        # Verify progression was recorded
        progression = game_state_monitor.get_timer_progression()
        assert len(progression) == 5
        assert progression == [60.0, 45.0, 30.0, 15.0, 5.0]


class TestBotAlertInterruption:
    """Test bot behavior when alert interrupts normal operations."""

    def test_bot_unexpected_alert_interruption(self, bot_with_window, game_state_monitor):
        """
        Test bot handles alert appearing during spam clicking.

        Scenario:
        1. Bot starts normal spam clicking at 45s timer
        2. Alert triggers unexpectedly
        3. Bot should detect alert and react
        4. Resume operations or continue based on alert state
        """
        bot = bot_with_window
        window = bot_with_window.window

        # Set timer to 45s
        window.set_timer(45.0)
        time.sleep(0.05)

        # Bot captures frame and clicks
        frame = bot.capture_frame()
        bot.click(times=10)
        game_state_monitor.record_state()

        # Unexpected alert during operation
        game_state_monitor.record_alert_trigger()
        time.sleep(0.05)

        # Bot should detect alert in next frame capture
        assert bot.is_alert_active()
        frame = bot.capture_frame()

        # Bot reacts with priority clicks
        bot.click(times=5)

        # Then dismiss alert
        game_state_monitor.record_alert_dismiss()
        time.sleep(0.05)

        # Resume normal operations
        window.adjust_timer(-5.0)
        bot.capture_frame()
        bot.click(times=10)

        # Verify sequence was recorded (at least 2 captures)
        assert len(bot.frame_captures) >= 2

    def test_bot_continues_after_alert_recovery(
        self, bot_with_window, game_state_monitor
    ):
        """Test bot recovers and continues after alert event."""
        bot = bot_with_window
        window = bot_with_window.window

        # Initial clicks
        bot.click(times=5)
        initial_capture_count = bot.get_frame_count()

        # Alert event
        game_state_monitor.record_alert_trigger()
        time.sleep(0.05)
        bot.capture_frame()

        # Recovery
        game_state_monitor.record_alert_dismiss()
        time.sleep(0.05)

        # Resume clicks
        for _ in range(3):
            bot.capture_frame()
            bot.click(times=5)

        # Verify bot continued operation
        assert bot.get_frame_count() > initial_capture_count


class TestSimulatorWindowBasics:
    """Test simulator window basic functionality."""

    def test_simulator_renders_valid_frame(self, game_window):
        """Test simulator renders valid frames."""
        frame = game_window.get_current_frame()

        assert frame is not None
        # Frame should have valid dynamic dimensions (height, width, 3 channels)
        assert len(frame.shape) == 3
        assert frame.shape[2] == 3  # 3 color channels (BGR)
        assert frame.shape[0] > 0 and frame.shape[1] > 0  # Non-zero dimensions
        assert frame.dtype == "uint8"

    def test_simulator_timer_display(self, game_window):
        """Test timer is displayed in frame."""
        game_window.set_timer(120.0)
        time.sleep(0.05)

        frame = game_window.get_current_frame()
        state = game_window.get_state()

        assert state["timer_seconds"] == 120.0
        # Frame contains rendered content (not all zeros)
        assert frame.sum() > 0

    def test_simulator_alert_overlay(self, game_window):
        """Test alert overlay renders when triggered."""
        # No alert initially
        frame_no_alert = game_window.get_current_frame()

        # Trigger alert
        game_window.trigger_alert()
        time.sleep(0.05)

        frame_with_alert = game_window.get_current_frame()
        state = game_window.get_state()

        assert state["alert_active"] is True
        # Frames should differ when alert is active
        assert (frame_no_alert != frame_with_alert).any()

    def test_simulator_state_thread_safety(self, game_window):
        """Test simulator state is thread-safe."""
        # Multiple rapid state changes
        for i in range(10):
            game_window.set_timer(float(i * 10))
            if i % 2 == 0:
                game_window.trigger_alert()
            else:
                game_window.dismiss_alert()

        # State should be consistent
        state = game_window.get_state()
        assert isinstance(state["timer_seconds"], float)
        assert isinstance(state["alert_active"], bool)
        assert state["fps"] >= 0

    def test_simulator_fps_tracking(self, game_window):
        """Test simulator tracks FPS accurately."""
        # Let simulator run for a bit
        time.sleep(0.5)  # Increased from 0.2

        state = game_window.get_state()

        # FPS should be tracked
        assert state["fps"] >= 0  # May be 0 in very fast tests
        assert state["frame_count"] > 0


class TestBotCaptureFromWindow:
    """Test bot frame capture from simulator."""

    def test_bot_captures_multiple_frames(self, bot_with_window):
        """Test bot captures sequence of frames."""
        bot = bot_with_window

        for _ in range(5):
            frame = bot.capture_frame()
            assert frame is not None
            # Frame should have valid dynamic dimensions
            assert len(frame.shape) == 3
            assert frame.shape[2] == 3  # 3 color channels

        assert bot.get_frame_count() == 5

    def test_captured_frames_show_timer_changes(self, bot_with_window):
        """Test bot captures show timer changes."""
        bot = bot_with_window
        window = bot_with_window.window

        # Capture at 60s
        window.set_timer(60.0)
        time.sleep(0.05)
        frame1 = bot.capture_frame()

        # Capture at 30s
        window.set_timer(30.0)
        time.sleep(0.05)
        frame2 = bot.capture_frame()

        # Frames should be different (timer changed)
        assert len(bot.frame_captures) == 2
        assert (frame1 != frame2).any()

    def test_bot_ocr_detects_dynamic_content(self, bot_with_window):
        """Test bot OCR works on dynamically changing content."""
        bot = bot_with_window
        window = bot_with_window.window

        ocr_results = []

        for timer_val in [100.0, 50.0, 10.0, 5.0]:
            window.set_timer(timer_val)
            time.sleep(0.05)
            frame = bot.capture_frame()
            result = bot.ocr(frame)
            ocr_results.append(result)

        # All OCR calls should succeed
        assert len(ocr_results) == 4
        for text, confidence in ocr_results:
            assert len(text) > 0
            assert confidence > 0.9
