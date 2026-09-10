"""
Tests for Analysis Visualizations (Task 12)
Heatmaps, Timelines, Comparisons, Trend Analysis
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys
import tempfile

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.reporting.heatmaps import Heatmaps
from mvp.simulator.reporting.timelines import Timelines
from mvp.simulator.reporting.comparisons import Comparisons
from mvp.simulator.reporting.trend_analysis import TrendAnalysis


class TestHeatmapsClickPosition(unittest.TestCase):
    """Test click position heatmap"""

    def test_heatmap_init(self):
        """Should initialize Heatmaps"""
        heatmap = Heatmaps()
        self.assertIsNotNone(heatmap)

    def test_add_click_positions(self):
        """Should add click positions"""
        heatmap = Heatmaps()
        
        clicks = [
            (100, 200),
            (110, 210),
            (105, 205),
        ]
        
        result = heatmap.add_click_positions(clicks)
        self.assertTrue(result)

    def test_generate_click_heatmap_image(self):
        """Should generate click position heatmap image"""
        heatmap = Heatmaps()
        
        clicks = [(100 + i*5, 200 + i*3) for i in range(10)]
        heatmap.add_click_positions(clicks)
        
        image_bytes = heatmap.generate_click_heatmap_image()
        self.assertIsNotNone(image_bytes)

    def test_generate_ocr_confidence_heatmap(self):
        """Should generate OCR confidence heatmap"""
        heatmap = Heatmaps()
        
        # OCR data: iteration -> confidence
        ocr_data = {
            1: 0.85,
            2: 0.88,
            3: 0.82,
            4: 0.90,
            5: 0.75,
        }
        
        image_bytes = heatmap.generate_ocr_confidence_heatmap(ocr_data)
        self.assertIsNotNone(image_bytes)


class TestTimelinesVisualization(unittest.TestCase):
    """Test timeline visualization"""

    def test_timeline_init(self):
        """Should initialize Timelines"""
        timeline = Timelines()
        self.assertIsNotNone(timeline)

    def test_add_phase_event(self):
        """Should add phase event"""
        timeline = Timelines()
        
        result = timeline.add_phase_event(1, 'CHAT', 0, 100)
        self.assertTrue(result)

    def test_add_multiple_phase_events(self):
        """Should add multiple phase events"""
        timeline = Timelines()
        
        phases = [
            (1, 'CHAT', 0, 100),
            (1, 'ALERT', 100, 200),
            (1, 'TREASURE', 200, 300),
        ]
        
        for iteration, phase, start_ms, end_ms in phases:
            timeline.add_phase_event(iteration, phase, start_ms, end_ms)
        
        self.assertEqual(len(timeline.events), 3)

    def test_generate_phase_timeline_image(self):
        """Should generate phase timeline image"""
        timeline = Timelines()
        
        timeline.add_phase_event(1, 'CHAT', 0, 100)
        timeline.add_phase_event(1, 'ALERT', 100, 200)
        
        image_bytes = timeline.generate_phase_timeline_image()
        self.assertIsNotNone(image_bytes)

    def test_generate_cpu_trend_image(self):
        """Should generate CPU trend timeline"""
        timeline = Timelines()
        
        cpu_data = {1: 25, 2: 30, 3: 28, 4: 35, 5: 32}
        
        image_bytes = timeline.generate_cpu_trend_image(cpu_data)
        self.assertIsNotNone(image_bytes)

    def test_generate_accuracy_curve_image(self):
        """Should generate accuracy curve image"""
        timeline = Timelines()
        
        accuracy_data = {1: 90, 2: 92, 3: 88, 4: 95, 5: 93}
        
        image_bytes = timeline.generate_accuracy_curve_image(accuracy_data)
        self.assertIsNotNone(image_bytes)


class TestComparisonsVisualization(unittest.TestCase):
    """Test variant comparison visualization"""

    def test_comparison_init(self):
        """Should initialize Comparisons"""
        comp = Comparisons()
        self.assertIsNotNone(comp)

    def test_add_variant_data(self):
        """Should add variant comparison data"""
        comp = Comparisons()
        
        data_a = {
            'variant': 'default',
            'accuracy': 90.0,
            'latency_ms': 45,
            'cpu_percent': 35,
        }
        
        result = comp.add_variant_data('variant_a', data_a)
        self.assertTrue(result)

    def test_add_two_variants(self):
        """Should compare two variants"""
        comp = Comparisons()
        
        comp.add_variant_data('default', {
            'accuracy': 90.0,
            'latency_ms': 45,
            'cpu_percent': 35,
        })
        
        comp.add_variant_data('hard_mode', {
            'accuracy': 85.0,
            'latency_ms': 52,
            'cpu_percent': 45,
        })
        
        self.assertEqual(len(comp.variants), 2)

    def test_generate_comparison_table(self):
        """Should generate comparison table HTML"""
        comp = Comparisons()
        
        comp.add_variant_data('A', {
            'accuracy': 90.0,
            'latency_ms': 45,
        })
        
        comp.add_variant_data('B', {
            'accuracy': 85.0,
            'latency_ms': 52,
        })
        
        html = comp.generate_comparison_table()
        
        self.assertIsNotNone(html)
        self.assertIn('table', html.lower())
        self.assertIn('90', html)

    def test_generate_comparison_chart_image(self):
        """Should generate comparison chart image"""
        comp = Comparisons()
        
        comp.add_variant_data('default', {
            'accuracy': 90.0,
            'latency_ms': 45,
            'cpu_percent': 35,
        })
        
        comp.add_variant_data('hard_mode', {
            'accuracy': 85.0,
            'latency_ms': 52,
            'cpu_percent': 45,
        })
        
        image_bytes = comp.generate_comparison_chart_image()
        self.assertIsNotNone(image_bytes)


class TestTrendAnalysis(unittest.TestCase):
    """Test trend analysis"""

    def test_trend_analysis_init(self):
        """Should initialize TrendAnalysis"""
        trend = TrendAnalysis()
        self.assertIsNotNone(trend)

    def test_add_accuracy_data(self):
        """Should add accuracy trend data"""
        trend = TrendAnalysis()
        
        accuracy_data = [90, 91, 92, 90, 89, 91]
        
        result = trend.add_accuracy_data(accuracy_data)
        self.assertTrue(result)

    def test_calculate_degradation(self):
        """Should calculate accuracy degradation"""
        trend = TrendAnalysis()
        
        # Degrading trend
        accuracy_data = [95, 93, 91, 89, 87, 85]
        trend.add_accuracy_data(accuracy_data)
        
        degradation = trend.calculate_degradation()
        
        self.assertIsNotNone(degradation)
        self.assertLess(degradation, 0)  # Negative = degradation

    def test_detect_anomalies(self):
        """Should detect anomalies in data"""
        trend = TrendAnalysis()
        
        # Data with anomaly
        accuracy_data = [90, 89, 91, 92, 10, 91, 90]  # 10 is anomaly
        trend.add_accuracy_data(accuracy_data)
        
        anomalies = trend.detect_anomalies()
        
        self.assertIsNotNone(anomalies)
        self.assertGreater(len(anomalies), 0)

    def test_generate_degradation_chart(self):
        """Should generate degradation chart image"""
        trend = TrendAnalysis()
        
        accuracy_data = [95, 93, 91, 89, 87, 85]
        trend.add_accuracy_data(accuracy_data)
        
        image_bytes = trend.generate_degradation_chart_image()
        self.assertIsNotNone(image_bytes)

    def test_calculate_chat_recovery_rate(self):
        """Should calculate chat recovery rate"""
        trend = TrendAnalysis()
        
        recovery_data = [100, 95, 90, 85, 80, 75]  # Declining recovery
        
        rate = trend.calculate_recovery_rate(recovery_data)
        
        self.assertIsNotNone(rate)

    def test_get_trend_summary(self):
        """Should return trend summary"""
        trend = TrendAnalysis()
        
        accuracy_data = [90, 89, 91, 92, 90, 88]
        trend.add_accuracy_data(accuracy_data)
        
        summary = trend.get_trend_summary()
        
        self.assertIsNotNone(summary)
        self.assertIn('mean', summary)
        self.assertIn('std_dev', summary)


class TestVisualizationFileExport(unittest.TestCase):
    """Test visualization file export"""

    def test_save_heatmap_image(self):
        """Should save heatmap image to file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'heatmap.png'
            
            heatmap = Heatmaps()
            heatmap.add_click_positions([(100, 200), (110, 210)])
            
            result = heatmap.save_image(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())

    def test_save_timeline_image(self):
        """Should save timeline image to file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'timeline.png'
            
            timeline = Timelines()
            timeline.add_phase_event(1, 'CHAT', 0, 100)
            
            result = timeline.save_image(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())


if __name__ == '__main__':
    unittest.main()
