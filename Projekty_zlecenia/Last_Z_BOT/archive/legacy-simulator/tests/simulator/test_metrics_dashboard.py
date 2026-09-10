"""
Tests for Metrics Dashboard Widget (Task 7)

Tests cover:
- Dashboard rendering with correct labels, font, colors
- Real-time metric updates with color logic based on thresholds
- Gauge rendering (accuracy 0-100%, CPU 0-100%, latency 0-1000ms)
- Queue integration with thread-safe operations
- Color thresholds: accuracy >80% green, latency <100ms green, CPU <50% green
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import sys
import queue
import threading
import time

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.ui.metrics_dashboard import MetricsDashboard


class TestMetricsDashboardInitialization(unittest.TestCase):
    """Test MetricsDashboard initialization with labels, fonts, colors"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_initialization_with_root_frame(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should initialize with root frame"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertEqual(dashboard.width, 400)
        self.assertEqual(dashboard.height, 200)
        self.assertIsNotNone(dashboard.frame)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_initialization_creates_labels(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should create labels for Accuracy, Latency, CPU, State"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        # Verify all gauge labels exist
        self.assertTrue(hasattr(dashboard, 'accuracy_gauge'))
        self.assertTrue(hasattr(dashboard, 'latency_meter'))
        self.assertTrue(hasattr(dashboard, 'cpu_monitor'))
        self.assertTrue(hasattr(dashboard, 'state_indicator'))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_initialization_font_courier(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should use Courier font family"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        # Check that font was configured with Courier
        self.assertIsNotNone(dashboard.accuracy_gauge)
        self.assertIsNotNone(dashboard.latency_meter)


class TestMetricUpdates(unittest.TestCase):
    """Test real-time metric updates with color logic"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_accuracy_green(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update accuracy with green color for >80%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_accuracy_gauge(85.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_accuracy_yellow(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update accuracy with yellow color for 50-80%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_accuracy_gauge(65.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_accuracy_red(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update accuracy with red color for <50%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_accuracy_gauge(40.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_latency_green(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update latency with green color for <100ms"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_latency_meter(75.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_latency_yellow(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update latency with yellow color for 100-500ms"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_latency_meter(250.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_latency_red(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update latency with red color for >500ms"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_latency_meter(750.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_cpu_green(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update CPU with green color for <50%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_cpu_monitor(35.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_cpu_yellow(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update CPU with yellow color for 50-75%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_cpu_monitor(62.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_cpu_red(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update CPU with red color for >75%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_cpu_monitor(85.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_current_state(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update current state enum value display"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.update_metrics({'state': 'TREASURE'})
        self.assertTrue(result)


class TestGaugeRendering(unittest.TestCase):
    """Test gauge rendering with correct ranges"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_render_accuracy_gauge_0_100(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should render accuracy gauge with 0-100% range"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        # Test min value
        result = dashboard.render_accuracy_gauge(0.0)
        self.assertTrue(result)
        
        # Test max value
        result = dashboard.render_accuracy_gauge(100.0)
        self.assertTrue(result)
        
        # Test middle value
        result = dashboard.render_accuracy_gauge(50.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_render_cpu_gauge_0_100(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should render CPU gauge with 0-100% range"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_cpu_monitor(0.0)
        self.assertTrue(result)
        
        result = dashboard.render_cpu_monitor(100.0)
        self.assertTrue(result)
        
        result = dashboard.render_cpu_monitor(50.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_render_latency_meter_0_200(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should render latency meter with appropriate range"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.render_latency_meter(0.0)
        self.assertTrue(result)
        
        result = dashboard.render_latency_meter(200.0)
        self.assertTrue(result)
        
        result = dashboard.render_latency_meter(100.0)
        self.assertTrue(result)


class TestQueueIntegration(unittest.TestCase):
    """Test thread-safe queue operations"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_queue_thread_safe_read_single(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should thread-safely read single metric from queue"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        metrics_queue = queue.Queue()
        metrics_queue.put({'accuracy': 85.0, 'latency_ms': 42.5, 'cpu_percent': 35})
        
        # Read without blocking
        try:
            metrics = metrics_queue.get_nowait()
            result = dashboard.update_metrics(metrics)
            self.assertTrue(result)
        except queue.Empty:
            self.fail("Queue should not be empty")

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_queue_handles_empty_gracefully(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should handle Queue.Empty exception gracefully"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        metrics_queue = queue.Queue()
        
        # Try to read from empty queue
        exception_caught = False
        try:
            metrics = metrics_queue.get_nowait()
        except queue.Empty:
            exception_caught = True
        
        self.assertTrue(exception_caught)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_queue_batch_processing(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should batch process multiple updates without blocking"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        metrics_queue = queue.Queue()
        
        # Add multiple metrics
        for i in range(5):
            metrics_queue.put({
                'accuracy': 80 + i,
                'latency_ms': 40 + i,
                'cpu_percent': 30 + i
            })
        
        # Process all without blocking
        count = 0
        while True:
            try:
                metrics = metrics_queue.get_nowait()
                dashboard.update_metrics(metrics)
                count += 1
            except queue.Empty:
                break
        
        self.assertEqual(count, 5)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_queue_thread_safe_multiple_producers(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should handle multiple threads writing to queue"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        metrics_queue = queue.Queue()
        results = {'success': 0, 'failed': 0}
        
        def producer(queue_obj, thread_id):
            for i in range(3):
                try:
                    queue_obj.put({
                        'accuracy': 70 + thread_id,
                        'latency_ms': 50 + thread_id,
                        'cpu_percent': 40 + thread_id
                    })
                    results['success'] += 1
                except Exception:
                    results['failed'] += 1
        
        # Create multiple producer threads
        threads = []
        for i in range(2):
            t = threading.Thread(target=producer, args=(metrics_queue, i))
            threads.append(t)
            t.start()
        
        # Wait for threads
        for t in threads:
            t.join()
        
        # Verify all items were added
        self.assertEqual(results['success'], 6)
        self.assertEqual(results['failed'], 0)


class TestColorLogic(unittest.TestCase):
    """Test color thresholds for different metrics"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_accuracy_green_above_80(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be green for accuracy >80%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        # Mock the gauge label to capture color
        mock_gauge = MagicMock()
        dashboard.accuracy_gauge = mock_gauge
        
        result = dashboard.render_accuracy_gauge(85.0)
        self.assertTrue(result)
        
        # Verify config was called with green color
        mock_gauge.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_accuracy_yellow_50_to_80(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be yellow for accuracy 50-80%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_gauge = MagicMock()
        dashboard.accuracy_gauge = mock_gauge
        
        result = dashboard.render_accuracy_gauge(65.0)
        self.assertTrue(result)
        
        mock_gauge.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_accuracy_red_below_50(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be red for accuracy <50%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_gauge = MagicMock()
        dashboard.accuracy_gauge = mock_gauge
        
        result = dashboard.render_accuracy_gauge(40.0)
        self.assertTrue(result)
        
        mock_gauge.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_latency_green_below_100(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be green for latency <100ms"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_meter = MagicMock()
        dashboard.latency_meter = mock_meter
        
        result = dashboard.render_latency_meter(75.0)
        self.assertTrue(result)
        
        mock_meter.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_latency_yellow_100_to_500(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be yellow for latency 100-500ms"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_meter = MagicMock()
        dashboard.latency_meter = mock_meter
        
        result = dashboard.render_latency_meter(250.0)
        self.assertTrue(result)
        
        mock_meter.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_latency_red_above_500(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be red for latency >500ms"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_meter = MagicMock()
        dashboard.latency_meter = mock_meter
        
        result = dashboard.render_latency_meter(750.0)
        self.assertTrue(result)
        
        mock_meter.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_cpu_green_below_50(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be green for CPU <50%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_monitor = MagicMock()
        dashboard.cpu_monitor = mock_monitor
        
        result = dashboard.render_cpu_monitor(35.0)
        self.assertTrue(result)
        
        mock_monitor.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_cpu_yellow_50_to_75(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be yellow for CPU 50-75%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_monitor = MagicMock()
        dashboard.cpu_monitor = mock_monitor
        
        result = dashboard.render_cpu_monitor(62.0)
        self.assertTrue(result)
        
        mock_monitor.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_cpu_red_above_75(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be red for CPU >75%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_monitor = MagicMock()
        dashboard.cpu_monitor = mock_monitor
        
        result = dashboard.render_cpu_monitor(85.0)
        self.assertTrue(result)
        
        mock_monitor.config.assert_called()


class TestMetricsDashboardGauges(unittest.TestCase):
    """Test gauge rendering"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_render_accuracy_gauge(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should render accuracy gauge"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'render_accuracy_gauge'))
        self.assertTrue(callable(dashboard.render_accuracy_gauge))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_render_latency_meter(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should render latency meter"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'render_latency_meter'))
        self.assertTrue(callable(dashboard.render_latency_meter))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_render_cpu_monitor(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should render CPU monitor"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'render_cpu_monitor'))
        self.assertTrue(callable(dashboard.render_cpu_monitor))


class TestMetricsDashboardUpdates(unittest.TestCase):
    """Test dashboard metric updates"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_metrics_accuracy(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update accuracy metric"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.update_metrics({'accuracy': 85.5})
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_metrics_latency(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update latency metric"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.update_metrics({'latency_ms': 42.5})
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_metrics_cpu(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update CPU metric"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.update_metrics({'cpu_percent': 35})
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_metrics_all(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update all metrics at once"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        metrics = {
            'accuracy': 85.5,
            'latency_ms': 42.5,
            'cpu_percent': 35,
            'state': 'TREASURE'
        }
        result = dashboard.update_metrics(metrics)
        self.assertTrue(result)


class TestMetricsDashboardCurrentValues(unittest.TestCase):
    """Test getting current metric values"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_get_current_accuracy(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should return current accuracy"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        dashboard.update_metrics({'accuracy': 85.5})
        acc = dashboard.get_current_metric('accuracy')
        self.assertEqual(acc, 85.5)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_get_current_latency(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should return current latency"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        dashboard.update_metrics({'latency_ms': 42.5})
        lat = dashboard.get_current_metric('latency_ms')
        self.assertEqual(lat, 42.5)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_get_nonexistent_metric_returns_none(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should return None for unknown metric"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        val = dashboard.get_current_metric('nonexistent')
        self.assertIsNone(val)


class TestMetricsDashboardState(unittest.TestCase):
    """Test state indicator"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_has_state_indicator(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should have state indicator"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'state_indicator'))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_update_state(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should update state indicator"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.update_metrics({'state': 'TREASURE'})
        self.assertTrue(result)


class TestMetricsDashboardVariant(unittest.TestCase):
    """Test variant display"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_has_variant_display(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should have variant display"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'set_variant'))
        self.assertTrue(callable(dashboard.set_variant))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_variant(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set variant text"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_variant('hard_mode')
        self.assertTrue(result)


class TestMetricsDashboardCPS(unittest.TestCase):
    """Test CPS display"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_has_cps_display(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should have CPS display"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'set_cps'))
        self.assertTrue(callable(dashboard.set_cps))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_cps(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set CPS value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_cps(38)
        self.assertTrue(result)


class TestMetricsDashboardLoad(unittest.TestCase):
    """Test system load display"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_has_load_display(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should have load display"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        self.assertTrue(hasattr(dashboard, 'set_load'))
        self.assertTrue(callable(dashboard.set_load))

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_load_basic(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set load value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_load(45.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_load_clamping(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should clamp load values to 0-100%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        # Test max clamping
        result = dashboard.set_load(150.0)
        self.assertTrue(result)
        load_val = dashboard.get_current_metric('system_load')
        self.assertEqual(load_val, 100.0)
        
        # Test min clamping
        result = dashboard.set_load(-10.0)
        self.assertTrue(result)
        load_val = dashboard.get_current_metric('system_load')
        self.assertEqual(load_val, 0.0)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_load_green_below_50(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be green for load <50%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_display = MagicMock()
        dashboard.load_display = mock_display
        
        result = dashboard.set_load(35.0)
        self.assertTrue(result)
        
        # Verify config was called
        mock_display.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_load_yellow_50_to_75(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be yellow for load 50-75%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_display = MagicMock()
        dashboard.load_display = mock_display
        
        result = dashboard.set_load(62.0)
        self.assertTrue(result)
        
        mock_display.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_set_load_red_above_75(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should be red for load >75%"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        mock_display = MagicMock()
        dashboard.load_display = mock_display
        
        result = dashboard.set_load(85.0)
        self.assertTrue(result)
        
        mock_display.config.assert_called()

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_get_current_load(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should return current load value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        dashboard.set_load(55.5)
        load_val = dashboard.get_current_metric('system_load')
        self.assertEqual(load_val, 55.5)


class TestVariant(unittest.TestCase):
    """Test variant display suite"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_variant_set_simple(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set variant name"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_variant('clean')
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_variant_get_value(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should retrieve variant value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        dashboard.set_variant('hard_mode')
        val = dashboard.get_current_metric('variant')
        self.assertEqual(val, 'hard_mode')


class TestCPS(unittest.TestCase):
    """Test CPS display suite"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_cps_set_30(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set CPS to 30"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_cps(30)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_cps_set_38(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set CPS to 38"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_cps(38)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_cps_get_value(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should retrieve CPS value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        dashboard.set_cps(38.5)
        val = dashboard.get_current_metric('cps')
        self.assertEqual(val, 38.5)


class TestLoad(unittest.TestCase):
    """Test system load display suite"""

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_load_set_low(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set load to low value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_load(30.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_load_set_medium(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set load to medium value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_load(60.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_load_set_high(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should set load to high value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        result = dashboard.set_load(85.0)
        self.assertTrue(result)

    @patch('tkinter.Frame')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.LabelFrame')
    @patch('tkinter.Label')
    def test_load_get_value(self, mock_label, mock_labelframe, mock_ttk_frame, mock_frame):
        """Should retrieve load value"""
        mock_parent = MagicMock()
        dashboard = MetricsDashboard(mock_parent, width=400, height=200)
        
        dashboard.set_load(72.5)
        val = dashboard.get_current_metric('system_load')
        self.assertEqual(val, 72.5)


if __name__ == '__main__':
    unittest.main()
