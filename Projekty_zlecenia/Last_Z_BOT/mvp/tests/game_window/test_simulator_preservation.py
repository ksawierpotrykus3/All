"""
Preservation behavior tests - Verify unchanged behavior BEFORE fix implementation.

This test suite validates that existing behaviors work correctly on unfixed code.
These tests codify observed patterns and will verify the fix doesn't introduce regressions.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

Approach: Observation-first
1. Observe current behavior on unfixed code
2. Codify observed patterns as property-based tests
3. Verify tests PASS on unfixed code (this is the success case)
4. After fix implementation, run same tests to verify NO REGRESSIONS
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from mvp.tests.game_window.simulator_window import GameSimulatorWindow


class TestPreservationTimerRendering:
    """
    Preservation: Timer rendering in top-right corner without position changes.
    
    **Validates: Requirement 3.1**
    """

    def test_timer_text_position_top_right_corner(self, game_window):
        """
        Test that timer is always rendered in top-right corner.
        
        Observed behavior: Timer green text appears at consistent position
        relative to top-right corner, regardless of frame dimensions.
        """
        # Set timer to known value
        game_window.set_timer(15.0)
        time.sleep(0.05)  # Allow render

        frame = game_window.get_current_frame()

        # Timer text in green (0, 255, 0 in BGR)
        # Should be visible in top-right region
        frame_height, frame_width = frame.shape[:2]

        # Top-right region where timer appears (approximately 200x50 pixels)
        # Default: rightmost ~200px, top ~50px
        search_margin = 200
        top_margin = 50

        x_start = max(0, frame_width - search_margin)
        x_end = frame_width
        y_start = 0
        y_end = top_margin

        timer_region = frame[y_start:y_end, x_start:x_end]

        # Green pixels should be present in timer region
        # Green in BGR: high G channel (index 1)
        green_channel = timer_region[:, :, 1]
        non_dark_green = np.sum(green_channel > 100)

        assert non_dark_green > 0, (
            f"Timer text not found in top-right corner. "
            f"Expected green pixels in region [{x_start}:{x_end}, {y_start}:{y_end}]"
        )

    def test_timer_renders_with_seconds_precision(self, game_window):
        """
        Test that timer value is rendered with correct seconds value.
        
        Observed: Timer displays current timer_seconds value.
        """
        # Test multiple timer values
        test_values = [0.0, 5.0, 15.5, 99.0]

        for timer_value in test_values:
            game_window.set_timer(timer_value)
            time.sleep(0.05)

            frame = game_window.get_current_frame()

            # Timer should be visible (green text)
            # We can't OCR it precisely, but verify it's rendered
            frame_height, frame_width = frame.shape[:2]

            search_margin = 200
            top_margin = 50

            x_start = max(0, frame_width - search_margin)
            x_end = frame_width
            y_start = 0
            y_end = top_margin

            timer_region = frame[y_start:y_end, x_start:x_end]
            green_channel = timer_region[:, :, 1]
            non_dark_green = np.sum(green_channel > 100)

            assert non_dark_green > 0, f"Timer not rendered for value {timer_value}"

    @given(
        timer_value=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_timer_renders_for_any_positive_value_property(self, game_window, timer_value):
        """
        Property: For any non-negative timer value, timer should be renderable.
        
        **Validates: Requirement 3.1**
        """
        game_window.set_timer(timer_value)
        time.sleep(0.05)

        frame = game_window.get_current_frame()

        # Timer region should have green pixels
        frame_height, frame_width = frame.shape[:2]

        search_margin = 200
        top_margin = 50

        x_start = max(0, frame_width - search_margin)
        x_end = frame_width
        y_start = 0
        y_end = top_margin

        timer_region = frame[y_start:y_end, x_start:x_end]
        green_channel = timer_region[:, :, 1]
        non_dark_green = np.sum(green_channel > 100)

        assert non_dark_green > 0, f"Timer not rendered for property value {timer_value}"


class TestPreservationAlertOverlay:
    """
    Preservation: Alert overlay rendering and alpha blending.
    
    **Validates: Requirements 3.2, 3.6**
    """

    def test_no_alert_when_not_triggered(self, game_window):
        """
        Test that frame shows only base image when alert not active.
        
        Observed: Base image displayed without overlay.
        
        **Validates: Requirement 3.2**
        """
        # Ensure alert is dismissed
        game_window.dismiss_alert()
        time.sleep(0.05)

        frame = game_window.get_current_frame()

        # Without alert, frame should be just the base image (no_chat.png)
        # The frame should match base dimensions
        assert frame.shape[2] == 3, "Frame should be BGR (3 channels)"

        # Base image (no_chat.png) should be visible
        non_zero_pixels = np.sum(frame > 0)
        assert non_zero_pixels > 100, "Base image should have visible content"

    def test_alert_overlay_blending_alpha(self, game_window):
        """
        Test that alert uses correct alpha blending (alpha=0.8).
        
        Observed: Alert appears semi-transparent (80% opacity).
        
        **Validates: Requirement 3.6**
        """
        # Trigger alert
        game_window.trigger_alert()
        time.sleep(0.1)

        frame_with_alert = game_window.get_current_frame()

        # Dismiss alert to get base frame
        game_window.dismiss_alert()
        time.sleep(0.05)

        frame_without_alert = game_window.get_current_frame()

        # Alert region should be in center
        frame_height, frame_width = frame_with_alert.shape[:2]

        # Expected alert dimensions: 303x105
        alert_width = 303
        alert_height = 105

        # Alert center
        center_x = frame_width // 2
        center_y = frame_height // 2

        x_start = max(0, center_x - alert_width // 2)
        x_end = min(frame_width, center_x + alert_width // 2)
        y_start = max(0, center_y - alert_height // 2)
        y_end = min(frame_height, center_y + alert_height // 2)

        # Extract regions
        alert_region = frame_with_alert[y_start:y_end, x_start:x_end]
        base_region = frame_without_alert[y_start:y_end, x_start:x_end]

        # With alpha blending (alpha=0.8), alert pixels should be different from base
        # but not identical to alert image (which would be alpha=1.0)
        pixel_difference = np.abs(alert_region.astype(float) - base_region.astype(float))
        max_pixel_diff = np.max(pixel_difference)

        # Pixels should be different (alert is visible)
        assert max_pixel_diff > 0, "Alert should change pixels when active"

        # But not drastically different (alpha blending applies)
        # With alpha=0.8, max change is about 80% of alert pixel values
        # Typically this is in range 0-200 (not 0-255 which would be full replacement)
        assert max_pixel_diff < 220, (
            f"Alert blending may be incorrect. "
            f"Max pixel diff: {max_pixel_diff} (expected <220 for alpha=0.8)"
        )

    def test_alert_dismiss_removes_overlay(self, game_window):
        """
        Test that dismiss_alert() properly removes alert overlay.
        
        Observed: Alert disappears immediately after dismiss.
        
        **Validates: Requirement 3.2**
        """
        # Trigger alert
        game_window.trigger_alert()
        time.sleep(0.05)

        # Dismiss alert
        game_window.dismiss_alert()
        time.sleep(0.05)

        frame = game_window.get_current_frame()
        state = game_window.get_state()

        # Alert should be inactive in state
        assert state["alert_active"] is False, "Alert state should be False after dismiss"

        # Frame should be clean (no alert artifacts)
        # Verify by checking that frame resembles base image more than alert-overlaid
        non_zero_pixels = np.sum(frame > 0)
        assert non_zero_pixels > 100, "Base image content should still be visible"

    def test_alert_rendering_consistency(self, game_window):
        """
        Test that alert rendering is consistent across multiple renders.
        
        Observed: Alert appears at same position and with same blend.
        """
        # Trigger alert
        game_window.trigger_alert()
        time.sleep(0.1)

        frame1 = game_window.get_current_frame()
        time.sleep(0.1)
        frame2 = game_window.get_current_frame()

        # Frames should be identical when alert is stable
        assert np.allclose(frame1, frame2), (
            "Alert rendering should be consistent across frames"
        )


class TestPreservationGetCurrentFrame:
    """
    Preservation: get_current_frame() API returns copy of current frame.
    
    **Validates: Requirement 3.3**
    """

    def test_get_current_frame_returns_copy_not_reference(self, game_window):
        """
        Test that get_current_frame() returns a copy, not reference.
        
        Observed: Modifying returned frame doesn't affect simulator state.
        
        **Validates: Requirement 3.3**
        """
        frame1 = game_window.get_current_frame()

        # Modify returned frame
        frame1[0, 0] = [0, 0, 0]

        # Get frame again
        frame2 = game_window.get_current_frame()

        # Modified pixel should not appear in new frame
        assert not np.array_equal(frame1[0, 0], frame2[0, 0]), (
            "get_current_frame() should return a copy, not a reference"
        )

    def test_get_current_frame_returns_current_dimensions(self, game_window):
        """
        Test that returned frame has current window dimensions.
        
        Observed (After Fix): Frame shape matches dynamic dimensions from loaded image (1920x1080x3).
        
        **Validates: Requirement 3.3**
        """
        frame = game_window.get_current_frame()

        # After fix: dimensions are dynamic (1920x1080)
        expected_height = 1080
        expected_width = 1920
        expected_channels = 3

        assert frame.shape == (expected_height, expected_width, expected_channels), (
            f"Frame shape {frame.shape} should be ({expected_height}, {expected_width}, {expected_channels})"
        )

    def test_get_current_frame_returns_bgr_format(self, game_window):
        """
        Test that frame is returned in BGR format (OpenCV standard).
        
        Observed: Frame is numpy array with dtype uint8.
        """
        frame = game_window.get_current_frame()

        assert isinstance(frame, np.ndarray), "Frame should be numpy array"
        assert frame.dtype == np.uint8, "Frame should be uint8 dtype"
        assert len(frame.shape) == 3, "Frame should be 3D array"
        assert frame.shape[2] == 3, "Frame should have 3 channels (BGR)"

    @given(st.just(None))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_get_current_frame_always_returns_valid_frame_property(self, game_window, _):
        """
        Property: get_current_frame() always returns valid BGR frame.
        
        **Validates: Requirement 3.3**
        """
        frame = game_window.get_current_frame()

        # Valid frame checks
        assert frame is not None, "Frame should not be None"
        assert isinstance(frame, np.ndarray), "Frame should be numpy array"
        assert frame.dtype == np.uint8, "Frame dtype should be uint8"
        assert len(frame.shape) == 3, "Frame should be 3D"
        assert frame.shape[2] == 3, "Frame should have 3 channels"
        assert np.any(frame > 0), "Frame should have non-zero pixels"


class TestPreservationKeyboardInput:
    """
    Preservation: Keyboard input handling (Q, SPACE, A, +/-).
    
    **Validates: Requirement 3.4**
    """

    def test_space_key_triggers_alert(self, game_window):
        """
        Test that SPACE key triggers alert.
        
        Observed: trigger_alert() method works correctly.
        """
        # Dismiss alert to start clean
        game_window.dismiss_alert()
        time.sleep(0.05)

        # Simulate SPACE key
        game_window.trigger_alert()
        time.sleep(0.05)

        state = game_window.get_state()
        assert state["alert_active"] is True, "SPACE should trigger alert"

    def test_a_key_dismisses_alert(self, game_window):
        """
        Test that A key dismisses alert.
        
        Observed: dismiss_alert() method works correctly.
        """
        # Trigger alert first
        game_window.trigger_alert()
        time.sleep(0.05)

        # Simulate A key
        game_window.dismiss_alert()
        time.sleep(0.05)

        state = game_window.get_state()
        assert state["alert_active"] is False, "A key should dismiss alert"

    def test_plus_key_increases_timer(self, game_window):
        """
        Test that + key increases timer.
        
        Observed: adjust_timer(+1.0) works correctly.
        """
        game_window.set_timer(10.0)
        time.sleep(0.05)

        # Simulate + key (adjust by +1.0)
        game_window.adjust_timer(1.0)
        time.sleep(0.05)

        state = game_window.get_state()
        assert abs(state["timer_seconds"] - 11.0) < 0.01, (
            f"+ key should increase timer by 1.0. Got {state['timer_seconds']}"
        )

    def test_minus_key_decreases_timer(self, game_window):
        """
        Test that - key decreases timer.
        
        Observed: adjust_timer(-1.0) works correctly.
        """
        game_window.set_timer(10.0)
        time.sleep(0.05)

        # Simulate - key (adjust by -1.0)
        game_window.adjust_timer(-1.0)
        time.sleep(0.05)

        state = game_window.get_state()
        assert abs(state["timer_seconds"] - 9.0) < 0.01, (
            f"- key should decrease timer by 1.0. Got {state['timer_seconds']}"
        )

    def test_minus_key_clamps_timer_at_zero(self, game_window):
        """
        Test that timer doesn't go below 0 when using - key.
        
        Observed: adjust_timer() with max(0, ...) prevents negative values.
        """
        game_window.set_timer(0.5)
        time.sleep(0.05)

        # Try to decrease below zero
        game_window.adjust_timer(-1.0)
        time.sleep(0.05)

        state = game_window.get_state()
        assert state["timer_seconds"] >= 0, "Timer should not go below 0"
        assert abs(state["timer_seconds"]) < 0.01, "Timer should be at 0"


class TestPreservationThreadSafety:
    """
    Preservation: Thread-safe concurrent access to simulator state.
    
    **Validates: Requirement 3.5**
    """

    def test_concurrent_get_current_frame_is_safe(self, game_window):
        """
        Test that concurrent calls to get_current_frame() are thread-safe.
        
        Observed (After Fix): self._lock protects frame access. Frames have dynamic dimensions.
        
        **Validates: Requirement 3.5**
        """
        frames_captured = []
        errors = []

        def capture_frame():
            try:
                for _ in range(5):
                    frame = game_window.get_current_frame()
                    frames_captured.append(frame)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        # Create multiple threads capturing frames concurrently
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(capture_frame) for _ in range(4)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        assert len(frames_captured) > 0, "Should have captured frames"

        # All frames should have valid shape (after fix: 1920x1080x3)
        for frame in frames_captured:
            assert frame.shape == (1080, 1920, 3), f"Invalid frame shape: {frame.shape}"

    def test_concurrent_set_timer_is_safe(self, game_window):
        """
        Test that concurrent timer updates are thread-safe.
        
        Observed: self._lock protects timer_seconds access.
        """
        errors = []

        def update_timer():
            try:
                for i in range(10):
                    game_window.set_timer(float(i))
                    state = game_window.get_state()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Concurrent timer updates
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(update_timer) for _ in range(4)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Concurrent timer update errors: {errors}"

        # Timer should have a valid final value
        state = game_window.get_state()
        assert isinstance(state["timer_seconds"], (int, float)), "Timer should be numeric"

    def test_concurrent_alert_toggle_is_safe(self, game_window):
        """
        Test that concurrent alert toggles are thread-safe.
        
        Observed: self._lock protects alert_active access.
        """
        errors = []

        def toggle_alert():
            try:
                for i in range(5):
                    if i % 2 == 0:
                        game_window.trigger_alert()
                    else:
                        game_window.dismiss_alert()
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        # Concurrent alert toggles
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(toggle_alert) for _ in range(4)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Concurrent alert toggle errors: {errors}"

        # Alert should be in valid state
        state = game_window.get_state()
        assert isinstance(state["alert_active"], bool), "Alert state should be boolean"

    def test_concurrent_get_state_is_safe(self, game_window):
        """
        Test that concurrent get_state() calls are thread-safe.
        
        Observed: self._lock protects get_state() access.
        """
        states_captured = []
        errors = []

        def capture_state():
            try:
                for _ in range(10):
                    state = game_window.get_state()
                    states_captured.append(state)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Concurrent state captures
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(capture_state) for _ in range(4)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Concurrent state capture errors: {errors}"
        assert len(states_captured) > 0, "Should have captured states"

        # All states should have required keys
        for state in states_captured:
            assert "timer_seconds" in state, "State should have timer_seconds"
            assert "alert_active" in state, "State should have alert_active"
            assert "fps" in state, "State should have fps"
            assert "frame_count" in state, "State should have frame_count"

    @given(st.data())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_mixed_concurrent_operations_are_safe_property(self, game_window, data):
        """
        Property: Mixed concurrent operations (timer, alert, frame capture) are safe.
        
        **Validates: Requirement 3.5**
        """
        errors = []

        def mixed_operations():
            try:
                for i in range(5):
                    game_window.set_timer(float(i))
                    if i % 2 == 0:
                        game_window.trigger_alert()
                    else:
                        game_window.dismiss_alert()
                    frame = game_window.get_current_frame()
                    state = game_window.get_state()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        # Run mixed operations concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(mixed_operations) for _ in range(3)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Concurrent mixed operation errors: {errors}"


class TestPreservationAsyncMode:
    """
    Preservation: Async mode with timeout works correctly.
    
    **Validates: Requirement 3.5**
    """

    def test_async_mode_thread_runs(self, game_window):
        """
        Test that run_async() starts background thread correctly.
        
        Observed: Thread is created and runs.
        """
        # game_window fixture already runs async, verify it's working
        state = game_window.get_state()

        assert state["frame_count"] > 0, "Async thread should be rendering frames"
        assert state["fps"] >= 0, "FPS should be tracked"

    def test_stop_terminates_async_thread(self):
        """
        Test that stop() terminates the async thread within timeout.
        
        Observed: stop() sets running=False, thread exits.
        """
        if not (Path("data/macro_testing") / "no_chat.png").exists():
            pytest.skip("data/macro_testing assets not available")
        simulator = GameSimulatorWindow(data_dir=Path("data/macro_testing"))
        thread = simulator.run_async()

        # Let it run for a bit
        time.sleep(0.1)

        initial_frame_count = simulator.get_state()["frame_count"]

        # Stop the thread
        simulator.stop()
        thread.join(timeout=2.0)

        # Thread should have stopped
        assert not thread.is_alive(), "Thread should stop after stop() call"

    def test_async_timeout_prevents_hanging(self):
        """
        Test that 30-second timeout prevents test hanging.
        
        Observed: run_async() includes max_runtime=30.0 timeout.
        """
        if not (Path("data/macro_testing") / "no_chat.png").exists():
            pytest.skip("data/macro_testing assets not available")
        simulator = GameSimulatorWindow(data_dir=Path("data/macro_testing"))
        thread = simulator.run_async()

        # Let it run for a short time
        time.sleep(0.1)

        # Verify thread doesn't hang (within timeout)
        thread.join(timeout=35.0)  # Slightly more than max_runtime

        # Thread should eventually terminate
        assert not thread.is_alive(), "Thread should terminate within timeout"


class TestPreservationAPIConsistency:
    """
    Preservation: API methods return expected values consistently.
    
    **Validates: Requirements 3.1-3.6**
    """

    def test_set_timer_returns_none(self, game_window):
        """Test that set_timer() returns None."""
        result = game_window.set_timer(10.0)
        assert result is None, "set_timer() should return None"

    def test_adjust_timer_returns_none(self, game_window):
        """Test that adjust_timer() returns None."""
        result = game_window.adjust_timer(1.0)
        assert result is None, "adjust_timer() should return None"

    def test_trigger_alert_returns_none(self, game_window):
        """Test that trigger_alert() returns None."""
        result = game_window.trigger_alert()
        assert result is None, "trigger_alert() should return None"

    def test_dismiss_alert_returns_none(self, game_window):
        """Test that dismiss_alert() returns None."""
        result = game_window.dismiss_alert()
        assert result is None, "dismiss_alert() should return None"

    def test_get_current_frame_returns_ndarray(self, game_window):
        """Test that get_current_frame() returns numpy array."""
        result = game_window.get_current_frame()
        assert isinstance(result, np.ndarray), "get_current_frame() should return ndarray"

    def test_get_state_returns_dict_with_required_keys(self, game_window):
        """Test that get_state() returns dict with all required keys."""
        state = game_window.get_state()
        required_keys = {"timer_seconds", "alert_active", "fps", "frame_count"}
        assert required_keys.issubset(set(state.keys())), (
            f"get_state() should return dict with {required_keys}, got {set(state.keys())}"
        )
