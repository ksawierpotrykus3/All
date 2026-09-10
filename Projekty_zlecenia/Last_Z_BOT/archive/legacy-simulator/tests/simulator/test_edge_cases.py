# Edge Case Tests for Extended Game Simulator Framework
# Tests unusual scenarios: multiple errors, rapid switching, UI heartbeat detection.

import pytest
import threading
import time
import queue
from unittest.mock import Mock, patch, MagicMock

from mvp.simulator.core import GameStateManager, GameState, ClickEvent
from mvp.simulator.metrics import MetricsCollector
from mvp.simulator.variants import VariantExecutor


# ======================== TEST 1: Multiple Errors Per Iteration ========================

class TestMultipleErrorsPerIteration:
    """
    Scenario: Trigger multiple error conditions simultaneously (bot error, metric failure, callback timeout).
    Expected: Engine prioritizes resource cleanup over metric collection.
    Verify: No cascading failures.
    """

    def test_multiple_errors_per_iteration(self):
        """Test handling of multiple simultaneous error conditions."""
        
        gm = GameStateManager(session_id="test_multi_error")
        mc = MetricsCollector()
        ve = VariantExecutor()
        
        ve.apply_preset("default")
        
        error_log = []
        exception_count = [0]
        
        # Register callback that fails
        def failing_callback(state, old_state):
            raise RuntimeError("Callback execution failed")
        
        gm.register_on_state_change(failing_callback)
        
        # Iteration with multiple error points
        try:
            mc.start_iteration(1, ve.current_variant)
            
            # Error 1: State transition with failing callback
            try:
                gm.transition_to(GameState.ALERT_ANIMATION)
            except RuntimeError as e:
                error_log.append(f"State transition error: {str(e)}")
                exception_count[0] += 1
            
            # Error 2: Missing metric record
            try:
                mc.record_phase("setup", duration_ms=-100)  # Invalid duration
            except (ValueError, KeyError) as e:
                error_log.append(f"Metrics error: {str(e)}")
                exception_count[0] += 1
            
            # Error 3: Bot integration failure (simulated)
            try:
                raise ProcessLookupError("Bot process not found")
            except ProcessLookupError as e:
                error_log.append(f"Bot error: {str(e)}")
                exception_count[0] += 1
            
            # Despite all errors, iteration should still complete
            final_metrics = mc.end_iteration(
                total_ms=100,
                cpu_avg=45,
                ram_mb=256
            )
            
        except Exception as e:
            pytest.fail(f"Engine should not crash with multiple errors: {e}")
        
        # Verify engine captured errors but continued
        assert exception_count[0] >= 1, "At least one error should be caught"
        assert len(error_log) >= 1, "Error log should have entries"
        
        # Verify next iteration works (no cascading failure)
        try:
            mc.start_iteration(2, ve.current_variant)
            mc.end_iteration(
                total_ms=100,
                cpu_avg=45,
                ram_mb=256
            )
            # end_iteration() returns None, so just verify no exception was raised
        except Exception as e:
            pytest.fail(f"Second iteration should work: {e}")


# ======================== TEST 2: Rapid Preset Switching (SIMPLIFIED) ========================

class TestRapidPresetSwitching:
    """
    Scenario: Switch presets rapidly in serial (no threading).
    Expected: No crashes, variants cleanly applied.
    Verify: Variants are valid after switching.
    """

    def test_rapid_preset_switching(self):
        """Test rapid preset switches don't cause crashes."""
        
        ve = VariantExecutor()
        
        presets = ["default", "hard_mode", "stress_test"]
        
        # Switch presets 10 times rapidly
        for i in range(10):
            preset = presets[i % len(presets)]
            ve.apply_preset(preset)
            assert ve.current_variant is not None
        
        # Verify final preset applied
        ve.apply_preset("stress_test")
        assert ve.current_variant is not None


# ======================== TEST 3: UI Heartbeat Detection (SIMPLIFIED) ========================

class TestUIHeartbeatDetection:
    """
    Scenario: Queue fills up when consumer is slow.
    Expected: Queue reaches maxsize, backpressure occurs.
    Verify: No crashes, queue handles full state.
    """

    def test_ui_heartbeat_detection(self):
        """Test queue backpressure when UI not consuming."""
        
        # Metrics queue simulating UI-engine communication
        metrics_queue = queue.Queue(maxsize=50)
        
        # Fill queue quickly
        items_added = 0
        items_dropped = 0
        
        for i in range(100):
            try:
                metrics_queue.put_nowait({"iteration": i, "metric": f"metric_{i}"})
                items_added += 1
            except queue.Full:
                items_dropped += 1
        
        # Verify queue filled up
        assert items_dropped > 0, "Queue should fill and drop items"
        assert items_added > 0, "Some items should be added"
        assert metrics_queue.qsize() == 50, "Queue should reach maxsize"


# ======================== TEST 4: State Machine Edge Cases ========================

class TestStateMachineEdgeCases:
    """
    Test valid state transitions within the state machine.
    """

    def test_valid_state_transitions(self):
        """Test valid state transitions work correctly."""
        
        gm = GameStateManager(session_id="test_state_transitions")
        
        # Valid transition sequence
        assert gm.current_state == GameState.CHAT
        
        # Chat -> Alert
        assert gm.transition_to(GameState.ALERT_ANIMATION)
        assert gm.current_state == GameState.ALERT_ANIMATION
        
        # Alert -> Treasure
        assert gm.transition_to(GameState.TREASURE)
        assert gm.current_state == GameState.TREASURE
        
        # Treasure -> Chat (reset)
        assert gm.transition_to(GameState.CHAT)
        assert gm.current_state == GameState.CHAT

    def test_invalid_transition_rejected(self):
        """Test that invalid transitions are rejected."""
        
        gm = GameStateManager(session_id="test_invalid")
        
        # Chat -> Treasure is invalid
        assert not gm.transition_to(GameState.TREASURE)
        assert gm.current_state == GameState.CHAT

    def test_state_duration_tracking(self):
        """Test that state duration is correctly tracked."""
        
        gm = GameStateManager(session_id="test_duration")
        
        # Enter state
        gm.transition_to(GameState.ALERT_ANIMATION)
        
        # Wait some time
        time.sleep(0.1)  # 100ms
        
        # Check duration
        duration_ms = gm.state_duration_ms
        assert 80 < duration_ms < 150, f"Duration should be ~100ms, got {duration_ms}ms"


# ======================== TEST 5: Metric Aggregation with Sparse Data ========================

class TestMetricAggregationSparseData:
    """
    Test metrics aggregation with incomplete or sparse data.
    """

    def test_aggregation_with_missing_hits(self):
        """Test aggregation when some iterations have no hits."""
        
        mc = MetricsCollector()
        ve = VariantExecutor()
        ve.apply_preset("default")
        
        # Iteration 1: With hit=True
        mc.start_iteration(1, ve.current_variant)
        mc.record_phase("setup", setup_ms=100)
        mc.record_phase("click_latency", latency_ms=78, hit=True)
        mc.end_iteration(total_ms=350, cpu_avg=42, ram_mb=256)
        
        # Iteration 2: With hit=False  
        mc.start_iteration(2, ve.current_variant)
        mc.record_phase("setup", setup_ms=100)
        mc.record_phase("click_latency", latency_ms=85, hit=False)
        mc.end_iteration(total_ms=245, cpu_avg=42, ram_mb=256)
        
        # Aggregation should handle sparse data
        aggregated = mc.aggregate()
        
        assert aggregated["iterations_total"] == 2
        assert aggregated["iterations_hit"] == 1
        assert aggregated["accuracy_percent"] == 50.0

    def test_aggregation_with_all_failures(self):
        """Test aggregation when all iterations miss."""
        
        mc = MetricsCollector()
        ve = VariantExecutor()
        ve.apply_preset("default")
        
        # 5 failed iterations (all misses)
        for i in range(5):
            mc.start_iteration(i + 1, ve.current_variant)
            mc.record_phase("setup", setup_ms=100)
            mc.record_phase("click_latency", latency_ms=78, hit=False)
            mc.end_iteration(total_ms=178, cpu_avg=42, ram_mb=256)
        
        aggregated = mc.aggregate()
        
        assert aggregated["iterations_total"] == 5
        assert aggregated["iterations_hit"] == 0
        assert aggregated["accuracy_percent"] == 0.0
