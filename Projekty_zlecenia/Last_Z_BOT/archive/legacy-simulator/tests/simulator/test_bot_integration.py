# tests/simulator/test_bot_integration.py
"""
Unit tests for BotIntegrationLayer.
Tests frame queue connection, OCR confidence reading, click logging, CPU/RAM monitoring, and thread safety.
"""

import pytest
import threading
import time
import queue
from pathlib import Path
from typing import List
from unittest.mock import Mock, MagicMock, patch

from mvp.simulator.core import GameStateManager, GameState, ClickEvent
from mvp.simulator.bot_integration import BotIntegrationLayer


class TestBotIntegrationLayerInitialization:
    """Test BotIntegrationLayer initialization and configuration."""

    def test_initialization_default(self):
        """BotIntegrationLayer should initialize with defaults."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        assert layer.game_state_manager == gsm
        assert layer.is_connected is False
        assert layer.ocr_confidence == 0.0
        assert layer.cpu_percent == 0
        assert layer.ram_mb == 0

    def test_initialization_with_config(self):
        """BotIntegrationLayer should accept configuration."""
        gsm = GameStateManager()
        config = {
            'bot_process_name': 'game.exe',
            'frame_queue_size': 50,
            'cpu_threshold_percent': 75
        }
        layer = BotIntegrationLayer(gsm, config=config)

        assert layer.bot_process_name == 'game.exe'
        assert layer.frame_queue_max_size == 50
        assert layer.cpu_threshold_percent == 75

    def test_initialization_creates_queues(self):
        """BotIntegrationLayer should create internal queues."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        assert hasattr(layer, 'frame_queue')
        assert isinstance(layer.frame_queue, queue.Queue)
        assert hasattr(layer, 'click_queue')
        assert isinstance(layer.click_queue, queue.Queue)

    def test_thread_safety_lock_created(self):
        """BotIntegrationLayer should create threading lock."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        assert hasattr(layer, '_lock')
        # Check that it's a lock-like object with acquire/release
        assert hasattr(layer._lock, 'acquire')
        assert hasattr(layer._lock, 'release')


class TestFrameQueueConnection:
    """Test frame queue connection to BotRunner."""

    def test_connect_to_bot(self):
        """connect_to_bot should establish connection."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        result = layer.connect_to_bot()
        assert result is True
        assert layer.is_connected is True

    def test_disconnect_from_bot(self):
        """disconnect_from_bot should close connection."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()

        result = layer.disconnect_from_bot()
        assert result is True
        assert layer.is_connected is False

    def test_push_frame_to_queue(self):
        """push_frame should add frame to queue."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()

        frame_data = {
            'timestamp': 1000,
            'image': b'fake_image_data',
            'width': 640,
            'height': 480,
            'state': 'chat'
        }

        result = layer.push_frame(frame_data)
        assert result is True

        # Retrieve frame from queue
        frame = layer.frame_queue.get(timeout=1)
        assert frame['state'] == 'chat'
        assert frame['width'] == 640

    def test_push_frame_when_disconnected(self):
        """push_frame should fail when disconnected."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        frame_data = {'timestamp': 1000, 'image': b'data'}
        result = layer.push_frame(frame_data)
        assert result is False

    def test_pop_frame_from_queue(self):
        """pop_frame should retrieve frame from queue."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()

        frame_data = {
            'timestamp': 1000,
            'image': b'fake_image',
            'state': 'alert'
        }
        layer.push_frame(frame_data)

        frame = layer.pop_frame(timeout=1)
        assert frame is not None
        assert frame['state'] == 'alert'

    def test_pop_frame_timeout_when_empty(self):
        """pop_frame should timeout when queue is empty."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        frame = layer.pop_frame(timeout=0.1)
        assert frame is None

    def test_frame_queue_size_limit(self):
        """Frame queue should respect size limit."""
        gsm = GameStateManager()
        config = {'frame_queue_size': 3}
        layer = BotIntegrationLayer(gsm, config=config)
        layer.connect_to_bot()

        # Push 5 frames, but queue size is 3
        for i in range(5):
            layer.push_frame({'timestamp': i, 'data': f'frame_{i}'})

        # Queue should have at most 3 frames
        size = layer.frame_queue.qsize()
        assert size <= 3


class TestOCRConfidenceReading:
    """Test OCR confidence reading from bot."""

    def test_get_ocr_confidence(self):
        """get_ocr_confidence should return current confidence."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()

        # Simulate OCR confidence update
        layer.ocr_confidence = 0.92

        confidence = layer.get_ocr_confidence()
        assert confidence == 0.92

    def test_update_ocr_confidence(self):
        """update_ocr_confidence should set confidence value."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        layer.update_ocr_confidence(0.85)
        assert layer.ocr_confidence == 0.85

        layer.update_ocr_confidence(0.95)
        assert layer.ocr_confidence == 0.95

    def test_ocr_confidence_bounds(self):
        """OCR confidence should be between 0 and 1."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        layer.update_ocr_confidence(0.0)
        assert layer.ocr_confidence == 0.0

        layer.update_ocr_confidence(1.0)
        assert layer.ocr_confidence == 1.0

        # Invalid values should be clamped
        layer.update_ocr_confidence(1.5)
        assert layer.ocr_confidence <= 1.0

    def test_ocr_confidence_history(self):
        """BotIntegrationLayer should track OCR confidence history."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        layer.update_ocr_confidence(0.80)
        layer.update_ocr_confidence(0.85)
        layer.update_ocr_confidence(0.90)

        history = layer.get_ocr_confidence_history()
        assert len(history) >= 3
        assert 0.80 in history
        assert 0.90 in history

    def test_read_ocr_from_mock_api(self):
        """read_ocr_confidence_from_api should fetch confidence."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        with patch.object(layer, '_fetch_from_bot_api') as mock_fetch:
            mock_fetch.return_value = {'ocr_confidence': 0.88}

            confidence = layer.read_ocr_confidence_from_api()
            assert confidence == 0.88


class TestClickEventIntegration:
    """Test click event logging integration with bot."""

    def test_log_bot_click(self):
        """log_bot_click should record click from bot."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        gsm.start_iteration(1, variant='test')

        layer.log_bot_click(
            position_x=150,
            position_y=250,
            hit=True,
            latency_ms=75,
            ocr_confidence=0.92
        )

        assert len(gsm.all_clicks) == 1
        click = gsm.all_clicks[0]
        assert click.position_x == 150
        assert click.position_y == 250
        assert click.hit is True
        assert click.latency_ms == 75

    def test_click_event_callback_from_bot(self):
        """BotIntegrationLayer should hook click callbacks to GameStateManager."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        gsm.start_iteration(1, variant='test')

        clicked_events: List[ClickEvent] = []

        def track_click(click: ClickEvent):
            clicked_events.append(click)

        gsm.register_on_click(track_click)

        layer.log_bot_click(100, 200, hit=True, latency_ms=80)

        assert len(clicked_events) == 1
        assert clicked_events[0].position_x == 100

    def test_multiple_clicks_logged(self):
        """Multiple click events should be logged sequentially."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        gsm.start_iteration(1, variant='test')

        layer.log_bot_click(100, 100, hit=True, latency_ms=75)
        layer.log_bot_click(150, 150, hit=False, latency_ms=95)
        layer.log_bot_click(200, 200, hit=True, latency_ms=80)

        assert len(gsm.all_clicks) == 3
        assert gsm.all_clicks[0].hit is True
        assert gsm.all_clicks[1].hit is False
        assert gsm.all_clicks[2].hit is True

    def test_click_logging_thread_safe(self):
        """Concurrent click logging should be thread-safe."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        gsm.start_iteration(1, variant='test')

        def worker(worker_id):
            for i in range(10):
                layer.log_bot_click(
                    100 + worker_id,
                    200 + i,
                    hit=(i % 2 == 0),
                    latency_ms=75 + i
                )
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(gsm.all_clicks) == 30  # 3 workers × 10 clicks


class TestCPURamMonitoring:
    """Test CPU and RAM monitoring."""

    @patch('mvp.simulator.bot_integration.psutil.Process')
    def test_get_cpu_percent(self, mock_process):
        """get_cpu_percent should return CPU usage."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        mock_instance = MagicMock()
        mock_instance.cpu_percent.return_value = 42.5
        mock_process.return_value = mock_instance

        # Manually set bot process to mocked instance
        layer._bot_process = mock_instance

        cpu = layer.get_cpu_percent()
        assert cpu == 42.5

    @patch('mvp.simulator.bot_integration.psutil.Process')
    def test_get_memory_mb(self, mock_process):
        """get_memory_mb should return memory usage in MB."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        mock_instance = MagicMock()
        mock_instance.memory_info.return_value.rss = 256 * 1024 * 1024  # 256 MB
        mock_process.return_value = mock_instance

        # Manually set bot process to mocked instance
        layer._bot_process = mock_instance

        ram = layer.get_memory_mb()
        assert ram == 256

    @patch('psutil.cpu_percent')
    def test_get_system_cpu_percent(self, mock_cpu):
        """get_system_cpu_percent should return system-wide CPU usage."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        mock_cpu.return_value = 55.3

        cpu = layer.get_system_cpu_percent()
        assert cpu == 55.3

    @patch('psutil.virtual_memory')
    def test_get_system_memory_percent(self, mock_mem):
        """get_system_memory_percent should return system memory usage."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        mock_mem_obj = MagicMock()
        mock_mem_obj.percent = 72.5
        mock_mem.return_value = mock_mem_obj

        mem = layer.get_system_memory_percent()
        assert mem == 72.5

    def test_update_resource_metrics(self):
        """update_resource_metrics should update CPU/RAM values."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        layer.update_resource_metrics(cpu_percent=45, ram_mb=320)

        assert layer.cpu_percent == 45
        assert layer.ram_mb == 320

    def test_start_monitoring_thread(self):
        """start_monitoring should spawn monitoring thread."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        result = layer.start_monitoring()
        assert result is True
        assert layer.is_monitoring is True

        # Clean up
        layer.stop_monitoring()

    def test_stop_monitoring_thread(self):
        """stop_monitoring should stop monitoring thread."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.start_monitoring()

        result = layer.stop_monitoring()
        assert result is True
        assert layer.is_monitoring is False

    def test_monitoring_thread_updates_metrics(self):
        """Monitoring thread should periodically update metrics."""
        gsm = GameStateManager()
        config = {'monitoring_interval_ms': 50}
        layer = BotIntegrationLayer(gsm, config=config)

        layer.start_monitoring()
        time.sleep(0.15)  # Wait 150ms for at least 2 updates

        # Should have some CPU/RAM data
        metrics = layer.get_resource_metrics()
        assert 'cpu_percent' in metrics
        assert 'ram_mb' in metrics

        layer.stop_monitoring()

    def test_get_resource_metrics(self):
        """get_resource_metrics should return current readings."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        layer.update_resource_metrics(cpu_percent=40, ram_mb=300)

        metrics = layer.get_resource_metrics()
        assert metrics['cpu_percent'] == 40
        assert metrics['ram_mb'] == 300

    def test_resource_metrics_history(self):
        """BotIntegrationLayer should track resource metrics history."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        layer.update_resource_metrics(cpu_percent=30, ram_mb=250)
        layer.update_resource_metrics(cpu_percent=40, ram_mb=300)
        layer.update_resource_metrics(cpu_percent=50, ram_mb=350)

        history = layer.get_resource_metrics_history()
        assert len(history) >= 3
        # Should have timestamps and measurements
        assert all('cpu_percent' in h for h in history)


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_frame_pushes(self):
        """Multiple threads pushing frames should be safe."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()

        def worker(worker_id):
            for i in range(5):
                layer.push_frame({
                    'timestamp': worker_id * 1000 + i * 100,
                    'data': f'frame_{worker_id}_{i}'
                })
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All frames should be queued
        total = 0
        while True:
            frame = layer.pop_frame(timeout=0.1)
            if frame is None:
                break
            total += 1

        assert total == 15  # 3 workers × 5 frames

    def test_concurrent_ocr_updates(self):
        """Multiple threads updating OCR should be safe."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        def worker(worker_id):
            for i in range(10):
                confidence = 0.5 + (worker_id * 0.1) + (i * 0.01)
                layer.update_ocr_confidence(min(confidence, 1.0))
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final confidence should be valid
        confidence = layer.get_ocr_confidence()
        assert 0.0 <= confidence <= 1.0

    def test_concurrent_metrics_updates(self):
        """Multiple threads updating metrics should be safe."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        def worker(worker_id):
            for i in range(10):
                layer.update_resource_metrics(
                    cpu_percent=30 + worker_id * 5 + i,
                    ram_mb=250 + worker_id * 50 + i * 10
                )
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have valid metrics
        metrics = layer.get_resource_metrics()
        assert 0 <= metrics['cpu_percent'] <= 100
        assert metrics['ram_mb'] > 0


class TestGracefulDisconnection:
    """Test disconnection and cleanup."""

    def test_disconnect_stops_monitoring(self):
        """disconnect_from_bot should stop monitoring thread."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()
        layer.start_monitoring()

        assert layer.is_monitoring is True

        layer.disconnect_from_bot()

        assert layer.is_connected is False
        assert layer.is_monitoring is False

    def test_disconnect_clears_queues(self):
        """disconnect_from_bot should clear frame/click queues."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()

        # Add frames to queue
        layer.push_frame({'timestamp': 1, 'data': 'frame1'})
        layer.push_frame({'timestamp': 2, 'data': 'frame2'})

        # Queues should have data
        assert not layer.frame_queue.empty()

        layer.disconnect_from_bot()

        # Queue should be cleared
        assert layer.frame_queue.empty()

    def test_context_manager_cleanup(self):
        """BotIntegrationLayer should support context manager cleanup."""
        gsm = GameStateManager()

        with BotIntegrationLayer(gsm) as layer:
            layer.connect_to_bot()
            assert layer.is_connected is True

        # After context, should be disconnected
        assert layer.is_connected is False

    def test_disconnect_with_active_monitoring(self):
        """Disconnecting with active monitoring should not error."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)
        layer.connect_to_bot()
        layer.start_monitoring()

        # Should not raise exception
        try:
            layer.disconnect_from_bot()
        except Exception as e:
            pytest.fail(f"Disconnect with monitoring raised: {e}")

        assert layer.is_connected is False
        assert layer.is_monitoring is False


class TestIntegrationWithGameStateManager:
    """Test integration with GameStateManager."""

    def test_bot_layer_hooks_to_gsm_callbacks(self):
        """BotIntegrationLayer should register callbacks with GSM."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        # Layer should have hooked callbacks — should be in GSM's callbacks
        assert len(gsm._on_state_change_callbacks) > 0

    def test_state_change_affects_bot_layer(self):
        """State changes in GSM should be visible to bot layer."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        state_changes = []

        def track_state(old, new, ts):
            state_changes.append((old, new))

        layer.register_on_state_change(track_state)
        gsm.transition_to(GameState.ALERT_ANIMATION)

        assert len(state_changes) > 0

    def test_bot_layer_tracks_iteration(self):
        """BotIntegrationLayer should track current iteration."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        gsm.start_iteration(5, variant='test')
        layer.log_bot_click(100, 200, hit=True)

        click = gsm.all_clicks[0]
        assert click.iteration == 5

    def test_full_iteration_flow_with_bot_layer(self):
        """Full iteration flow: setup → alert → click → treasure → scan."""
        gsm = GameStateManager()
        layer = BotIntegrationLayer(gsm)

        # Setup
        gsm.start_iteration(1, variant='clean_38cps')

        # Alert phase
        gsm.transition_to(GameState.ALERT_ANIMATION)
        gsm.log_phase_metric('alert', 'detection_ms', 145)
        layer.update_ocr_confidence(0.92)

        # Click
        layer.log_bot_click(150, 250, hit=True, latency_ms=78, ocr_confidence=0.92)

        # Treasure
        gsm.transition_to(GameState.TREASURE)
        gsm.log_phase_metric('treasure', 'cpu_spike_percent', 45)
        layer.update_resource_metrics(cpu_percent=45, ram_mb=280)

        # Chat recovery
        gsm.transition_to(GameState.SCANNING)
        gsm.transition_to(GameState.CHAT_RECOVERY)
        gsm.log_phase_metric('chat_recovery', 'recovery_ms', 890)
        gsm.log_phase_metric('chat_recovery', 'ocr_confidence', 0.87)
        gsm.log_phase_metric('chat_recovery', 'state_verified', True)

        # Complete iteration
        metrics = gsm.complete_iteration(total_time_ms=1356, cpu_avg=42, ram_mb=256)

        assert metrics.phase_2_alert_detection_ms == 145
        # Click hit is logged via log_bot_click, which sets phase_3_hit indirectly
        # through log_click method in GSM
        assert len(gsm.all_clicks) == 1
        assert gsm.all_clicks[0].hit is True
        assert metrics.phase_4_cpu_spike_percent == 45
        assert metrics.phase_5_ocr_confidence == 0.87
        assert metrics.phase_5_state_verified is True
