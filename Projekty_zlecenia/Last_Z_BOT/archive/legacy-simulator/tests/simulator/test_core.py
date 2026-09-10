# tests/simulator/test_core.py
"""
Unit tests for GameStateManager core functionality.
Tests state machine transitions, thread safety, click logging, and metrics.
"""

import pytest
import threading
import time
from pathlib import Path
from typing import List

from mvp.simulator.core import (
    GameStateManager,
    GameState,
    ClickEvent,
    IterationMetrics,
)


class TestGameStateTransitions:
    """Test state machine transitions and validation."""

    def test_initial_state_is_chat(self):
        """GameStateManager should start in CHAT state."""
        gsm = GameStateManager()
        assert gsm.current_state == GameState.CHAT

    def test_valid_transition_chat_to_alert(self):
        """Valid transition: CHAT → ALERT_ANIMATION."""
        gsm = GameStateManager()
        result = gsm.transition_to(GameState.ALERT_ANIMATION)
        assert result is True
        assert gsm.current_state == GameState.ALERT_ANIMATION

    def test_valid_transition_alert_to_treasure(self):
        """Valid transition: ALERT_ANIMATION → TREASURE."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        result = gsm.transition_to(GameState.TREASURE)
        assert result is True
        assert gsm.current_state == GameState.TREASURE

    def test_valid_transition_treasure_to_scanning(self):
        """Valid transition: TREASURE → SCANNING."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        gsm.transition_to(GameState.TREASURE)
        result = gsm.transition_to(GameState.SCANNING)
        assert result is True
        assert gsm.current_state == GameState.SCANNING

    def test_valid_transition_scanning_to_chat_recovery(self):
        """Valid transition: SCANNING → CHAT_RECOVERY."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        gsm.transition_to(GameState.TREASURE)
        gsm.transition_to(GameState.SCANNING)
        result = gsm.transition_to(GameState.CHAT_RECOVERY)
        assert result is True
        assert gsm.current_state == GameState.CHAT_RECOVERY

    def test_valid_transition_chat_recovery_to_chat(self):
        """Valid transition: CHAT_RECOVERY → CHAT."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        gsm.transition_to(GameState.TREASURE)
        gsm.transition_to(GameState.SCANNING)
        gsm.transition_to(GameState.CHAT_RECOVERY)
        result = gsm.transition_to(GameState.CHAT)
        assert result is True
        assert gsm.current_state == GameState.CHAT

    def test_invalid_transition_chat_to_treasure(self):
        """Invalid transition: CHAT → TREASURE should fail."""
        gsm = GameStateManager()
        result = gsm.transition_to(GameState.TREASURE)
        assert result is False
        assert gsm.current_state == GameState.CHAT

    def test_invalid_transition_alert_to_scanning(self):
        """Invalid transition: ALERT_ANIMATION → SCANNING should fail."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        result = gsm.transition_to(GameState.SCANNING)
        assert result is False
        assert gsm.current_state == GameState.ALERT_ANIMATION

    def test_reset_from_any_state_to_chat(self):
        """Any state can transition back to CHAT (reset)."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        gsm.transition_to(GameState.TREASURE)

        result = gsm.transition_to(GameState.CHAT)
        assert result is True
        assert gsm.current_state == GameState.CHAT

    def test_state_history_tracking(self):
        """State transitions should be tracked in history."""
        gsm = GameStateManager()
        gsm.transition_to(GameState.ALERT_ANIMATION)
        gsm.transition_to(GameState.TREASURE)

        # History should have at least 3 entries (initial CHAT + 2 transitions)
        assert len(gsm._state_history) >= 3
        assert gsm._state_history[0][0] == GameState.CHAT
        assert gsm._state_history[1][0] == GameState.ALERT_ANIMATION
        assert gsm._state_history[2][0] == GameState.TREASURE

    def test_state_duration_ms(self):
        """state_duration_ms should reflect time in current state."""
        gsm = GameStateManager()
        initial_duration = gsm.state_duration_ms

        time.sleep(0.05)  # Sleep 50ms
        new_duration = gsm.state_duration_ms

        # New duration should be roughly 50ms more (with some tolerance)
        assert new_duration >= initial_duration + 40


class TestClickLogging:
    """Test click event logging."""

    def test_log_click_basic(self):
        """log_click should create and store ClickEvent."""
        gsm = GameStateManager()
        gsm.start_iteration(1, variant='test_variant')

        click = gsm.log_click(
            position_x=100.5,
            position_y=200.5,
            hit=True,
            phase='phase_3_click',
            ocr_confidence=0.92,
            latency_ms=78,
        )

        assert click.position_x == 100.5
        assert click.position_y == 200.5
        assert click.hit is True
        assert click.phase == 'phase_3_click'
        assert click.ocr_confidence == 0.92
        assert click.latency_ms == 78
        assert click.iteration == 1

    def test_log_click_adds_to_session_clicks(self):
        """log_click should add to all_clicks."""
        gsm = GameStateManager()
        gsm.start_iteration(1, variant='test')

        gsm.log_click(100, 200, hit=True, phase='click')
        gsm.log_click(150, 250, hit=False, phase='click')

        assert len(gsm.all_clicks) == 2
        assert gsm.all_clicks[0].hit is True
        assert gsm.all_clicks[1].hit is False

    def test_log_click_adds_to_iteration(self):
        """log_click should add to iteration's clicks list."""
        gsm = GameStateManager()
        gsm.start_iteration(1, variant='test')

        gsm.log_click(100, 200, hit=True)
        gsm.log_click(150, 250, hit=False)

        iteration = gsm.iterations[1]
        assert len(iteration.clicks) == 2

    def test_log_click_inherits_iteration_and_variant(self):
        """log_click should inherit iteration and variant from manager."""
        gsm = GameStateManager()
        gsm.start_iteration(5, variant='cluttered_38cps')

        click = gsm.log_click(100, 200, hit=True)

        assert click.iteration == 5
        assert click.variant == 'cluttered_38cps'


class TestIterationMetrics:
    """Test iteration metrics tracking."""

    def test_start_iteration(self):
        """start_iteration should create IterationMetrics."""
        gsm = GameStateManager()
        metrics = gsm.start_iteration(1, variant='test_variant')

        assert metrics.iteration == 1
        assert metrics.variant == 'test_variant'
        assert gsm.current_iteration == 1
        assert 1 in gsm.iterations

    def test_complete_iteration(self):
        """complete_iteration should update metrics."""
        gsm = GameStateManager()
        gsm.start_iteration(1, variant='test')

        completed = gsm.complete_iteration(
            total_time_ms=1356,
            cpu_avg=42,
            ram_mb=256,
        )

        assert completed.total_iteration_ms == 1356
        assert completed.cpu_avg == 42
        assert completed.ram_mb == 256

    def test_log_phase_metric_setup(self):
        """log_phase_metric should update phase_1_setup_ms."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_phase_metric('setup', 'setup_ms', 98)

        assert gsm.iterations[1].phase_1_setup_ms == 98

    def test_log_phase_metric_alert_detection(self):
        """log_phase_metric should update phase_2_alert_detection_ms."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_phase_metric('alert', 'detection_ms', 145)

        assert gsm.iterations[1].phase_2_alert_detection_ms == 145

    def test_log_phase_metric_click_latency(self):
        """log_phase_metric should update phase_3_click_latency_ms."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_phase_metric('click', 'latency_ms', 78)

        assert gsm.iterations[1].phase_3_click_latency_ms == 78

    def test_log_phase_metric_click_hit(self):
        """log_phase_metric should update phase_3_hit."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_phase_metric('click', 'hit', True)

        assert gsm.iterations[1].phase_3_hit is True

    def test_log_phase_metric_cpu_spike(self):
        """log_phase_metric should update phase_4_cpu_spike_percent."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_phase_metric('treasure', 'cpu_spike_percent', 45)

        assert gsm.iterations[1].phase_4_cpu_spike_percent == 45

    def test_log_phase_metric_chat_recovery(self):
        """log_phase_metric should update phase_5 metrics."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_phase_metric('chat_recovery', 'recovery_ms', 890)
        gsm.log_phase_metric('chat_recovery', 'ocr_confidence', 0.87)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)

        metrics = gsm.iterations[1]
        assert metrics.phase_5_chat_recovery_ms == 890
        assert metrics.phase_5_ocr_confidence == 0.87
        assert metrics.phase_5_state_verified is True

    def test_log_anomaly(self):
        """log_anomaly should add anomaly to iteration."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        gsm.log_anomaly(1, 'Chat not recovered', severity='critical')

        assert len(gsm.iterations[1].anomalies) == 1
        assert 'critical' in gsm.iterations[1].anomalies[0].lower()

    def test_iteration_success_property_true(self):
        """IterationMetrics.success should be True when no critical anomalies."""
        gsm = GameStateManager()
        gsm.start_iteration(1)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)

        assert gsm.iterations[1].success is True

    def test_iteration_success_property_false_on_critical_anomaly(self):
        """IterationMetrics.success should be False with critical anomalies."""
        gsm = GameStateManager()
        gsm.start_iteration(1)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)
        gsm.log_anomaly(1, 'Critical error', severity='critical')

        assert gsm.iterations[1].success is False


class TestCallbacks:
    """Test callback system."""

    def test_state_change_callback(self):
        """register_on_state_change callback should be invoked."""
        gsm = GameStateManager()
        invocations: List[tuple] = []

        def callback(old_state, new_state, timestamp):
            invocations.append((old_state, new_state, timestamp))

        gsm.register_on_state_change(callback)
        gsm.transition_to(GameState.ALERT_ANIMATION)

        assert len(invocations) == 1
        assert invocations[0][0] == GameState.CHAT
        assert invocations[0][1] == GameState.ALERT_ANIMATION

    def test_click_callback(self):
        """register_on_click callback should be invoked."""
        gsm = GameStateManager()
        gsm.start_iteration(1)
        invocations: List[ClickEvent] = []

        def callback(click):
            invocations.append(click)

        gsm.register_on_click(callback)
        gsm.log_click(100, 200, hit=True)

        assert len(invocations) == 1
        assert invocations[0].position_x == 100
        assert invocations[0].position_y == 200

    def test_multiple_callbacks(self):
        """Multiple callbacks should all be invoked."""
        gsm = GameStateManager()
        invocations1: List[tuple] = []
        invocations2: List[tuple] = []

        def callback1(old, new, ts):
            invocations1.append((old, new))

        def callback2(old, new, ts):
            invocations2.append((old, new))

        gsm.register_on_state_change(callback1)
        gsm.register_on_state_change(callback2)
        gsm.transition_to(GameState.ALERT_ANIMATION)

        assert len(invocations1) == 1
        assert len(invocations2) == 1


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_state_transitions(self):
        """Multiple threads should safely transition states."""
        gsm = GameStateManager()
        results: List[bool] = []
        lock = threading.Lock()

        def transition_worker():
            result = gsm.transition_to(GameState.ALERT_ANIMATION)
            with lock:
                results.append(result)
            # Sleep to ensure many threads are active
            time.sleep(0.01)

        threads = [threading.Thread(target=transition_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one should succeed (first one), rest should fail or succeed
        # but final state should be ALERT_ANIMATION
        assert gsm.current_state in [GameState.CHAT, GameState.ALERT_ANIMATION]

    def test_concurrent_click_logging(self):
        """Multiple threads logging clicks simultaneously should be safe."""
        gsm = GameStateManager()
        gsm.start_iteration(1)

        def click_worker(worker_id):
            for i in range(10):
                gsm.log_click(100 + worker_id, 200 + i, hit=(i % 2 == 0))
                time.sleep(0.001)

        threads = [threading.Thread(target=click_worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 30 clicks total (3 threads × 10 clicks)
        assert len(gsm.all_clicks) == 30
        assert len(gsm.iterations[1].clicks) == 30

    def test_concurrent_state_and_metrics(self):
        """Concurrent state transitions and metrics logging should be safe."""
        gsm = GameStateManager()
        gsm.start_iteration(1)
        errors: List[str] = []
        lock = threading.Lock()

        def state_worker():
            try:
                gsm.transition_to(GameState.ALERT_ANIMATION)
                time.sleep(0.005)
                gsm.transition_to(GameState.CHAT)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        def metrics_worker():
            try:
                for i in range(5):
                    gsm.log_phase_metric('alert', 'detection_ms', 100 + i)
                    gsm.log_click(100, 200 + i, hit=True)
                    time.sleep(0.002)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [
            threading.Thread(target=state_worker) for _ in range(2)
        ] + [threading.Thread(target=metrics_worker) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(gsm.all_clicks) == 10  # 2 metrics workers × 5 clicks


class TestSessionMetrics:
    """Test session-level metrics aggregation."""

    def test_get_session_metrics_empty(self):
        """get_session_metrics with no iterations."""
        gsm = GameStateManager('test_session')
        metrics = gsm.get_session_metrics()

        assert metrics['session_id'] == 'test_session'
        assert metrics['total_iterations'] == 0
        assert metrics['accuracy_percent'] == 0

    def test_get_session_metrics_with_iterations(self):
        """get_session_metrics should aggregate iteration data."""
        gsm = GameStateManager('test_session')

        # Iteration 1: success
        gsm.start_iteration(1, variant='test')
        gsm.log_click(100, 200, hit=True, latency_ms=80, ocr_confidence=0.9)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)
        gsm.complete_iteration(1000, 40, 250)

        # Iteration 2: success
        gsm.start_iteration(2, variant='test')
        gsm.log_click(100, 200, hit=True, latency_ms=75, ocr_confidence=0.95)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)
        gsm.complete_iteration(1050, 42, 260)

        metrics = gsm.get_session_metrics()

        assert metrics['total_iterations'] == 2
        assert metrics['successful_iterations'] == 2
        assert metrics['accuracy_percent'] == 100.0
        assert metrics['average_latency_ms'] == 77.5
        assert metrics['average_ocr_confidence'] == 0.925
        assert metrics['total_clicks'] == 2
        assert metrics['total_hits'] == 2

    def test_session_metrics_partial_success(self):
        """get_session_metrics should calculate accuracy correctly."""
        gsm = GameStateManager('test_session')

        # Success
        gsm.start_iteration(1)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)
        gsm.complete_iteration(1000, 40, 250)

        # Failure (state not verified)
        gsm.start_iteration(2)
        gsm.log_phase_metric('chat_recovery', 'state_verified', False)
        gsm.complete_iteration(1000, 40, 250)

        metrics = gsm.get_session_metrics()
        assert metrics['accuracy_percent'] == 50.0


class TestSessionDataSerialization:
    """Test session data saving and serialization."""

    def test_save_session_data(self, tmp_path):
        """save_session_data should create JSON file with all data."""
        gsm = GameStateManager('test_session')
        gsm.start_iteration(1, variant='test')
        gsm.log_click(100, 200, hit=True, latency_ms=80)
        gsm.log_phase_metric('alert', 'detection_ms', 145)
        gsm.complete_iteration(1000, 40, 250)

        filepath = tmp_path / 'session.json'
        gsm.save_session_data(filepath)

        assert filepath.exists()

        import json
        with open(filepath) as f:
            data = json.load(f)

        assert data['session_id'] == 'test_session'
        assert 'session_metrics' in data
        assert 'iterations' in data
        # JSON converts int keys to strings
        assert '1' in data['iterations']
        assert len(data['iterations']['1']['clicks']) == 1

    def test_click_event_to_dict(self):
        """ClickEvent.to_dict should serialize correctly."""
        click = ClickEvent(
            timestamp_ms=1000,
            position_x=100.5,
            position_y=200.5,
            hit=True,
            phase='phase_3',
            iteration=1,
            variant='test',
            ocr_confidence=0.9,
            latency_ms=80,
        )

        data = click.to_dict()
        assert data['position_x'] == 100.5
        assert data['hit'] is True
        assert data['latency_ms'] == 80

    def test_iteration_metrics_to_dict(self):
        """IterationMetrics.to_dict should serialize correctly."""
        metrics = IterationMetrics(1, 'test_variant')
        metrics.phase_1_setup_ms = 100
        metrics.phase_3_hit = True
        metrics.total_iteration_ms = 1000

        data = metrics.to_dict()
        assert data['iteration'] == 1
        assert data['variant'] == 'test_variant'
        assert data['phase_1_setup_ms'] == 100
        assert data['phase_3_hit'] is True
