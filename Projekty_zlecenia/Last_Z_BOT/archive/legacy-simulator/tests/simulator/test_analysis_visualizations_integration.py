"""
Integration tests for Analysis Visualizations with sample data.
Tests all 4 visualization types with realistic sample simulation data.
"""
import unittest
from pathlib import Path
import sys
import tempfile

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.reporting.heatmaps import Heatmaps
from mvp.simulator.reporting.timelines import Timelines
from mvp.simulator.reporting.comparisons import Comparisons
from mvp.simulator.reporting.trend_analysis import TrendAnalysis


class TestAnalysisVisualizationsIntegration(unittest.TestCase):
    """Integration test: all visualizations with sample data."""

    def setUp(self):
        """Set up sample data mimicking 100 iterations, 5 variants."""
        # 100 iterations of click data
        self.click_positions = [
            (100 + (i % 10) * 5, 200 + (i % 10) * 3)
            for i in range(100)
        ]
        
        # OCR confidence per iteration
        self.ocr_data = {
            i: 0.75 + 0.2 * ((i % 20) / 20)  # Varies 75-95%
            for i in range(1, 101)
        }
        
        # Latency values (ms)
        self.latencies = [
            50 + 20 * ((i % 30) / 30) + (i // 10)
            for i in range(100)
        ]
        
        # Phase events
        self.phase_events = []
        for iteration in range(10):  # First 10 iterations
            self.phase_events.append((iteration, 'SETUP', 0, 100))
            self.phase_events.append((iteration, 'ALERT', 100, 150))
            self.phase_events.append((iteration, 'CLICK', 150, 200))
            self.phase_events.append((iteration, 'TREASURE', 200, 800))
            self.phase_events.append((iteration, 'SCAN', 800, 1300))
        
        # Variant comparison data
        self.variant_a = {
            'accuracy': 92.5,
            'latency_ms': 78,
            'cpu_percent': 35,
            'reliability_percent': 98,
        }
        
        self.variant_b = {
            'accuracy': 88.0,
            'latency_ms': 92,
            'cpu_percent': 42,
            'reliability_percent': 95,
        }
        
        # CPU trend data
        self.cpu_data = {
            i: 25 + 15 * ((i % 20) / 20)
            for i in range(1, 101)
        }
        
        # Accuracy curve data
        self.accuracy_data = {
            i: 90 - (i // 10) + 5 * ((i % 5) / 5)
            for i in range(1, 101)
        }
        
        # Chat recovery rate data
        self.recovery_data = [
            95 - (i // 20) for i in range(100)
        ]

    def test_heatmap_click_position_xy(self):
        """Test click position heatmap generation."""
        heatmap = Heatmaps()
        heatmap.add_click_positions(self.click_positions)
        
        image = heatmap.generate_click_heatmap_image(width=1920, height=1080)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        # SVG should contain <svg> tag
        self.assertIn(b'<svg', image)
        self.assertIn(b'</svg>', image)

    def test_heatmap_ocr_confidence_by_variant(self):
        """Test OCR confidence heatmap."""
        heatmap = Heatmaps()
        
        image = heatmap.generate_ocr_confidence_heatmap(self.ocr_data)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        # HTML table should contain <table> tag
        self.assertIn(b'<table', image)
        self.assertIn(b'</table>', image)

    def test_heatmap_latency_distribution(self):
        """Test latency distribution heatmap."""
        heatmap = Heatmaps()
        
        image = heatmap.generate_latency_distribution_heatmap(self.latencies)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        # SVG bar chart
        self.assertIn(b'<svg', image)
        self.assertIn(b'<rect', image)  # Bar elements

    def test_timeline_per_iteration_phases(self):
        """Test phase timeline visualization."""
        timeline = Timelines()
        
        for iteration, phase, start_ms, end_ms in self.phase_events:
            timeline.add_phase_event(iteration, phase, start_ms, end_ms)
        
        image = timeline.generate_phase_timeline_image()
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        self.assertIn(b'<svg', image)
        self.assertIn(b'Phase Timeline', image)

    def test_timeline_cpu_trend(self):
        """Test CPU trend timeline."""
        timeline = Timelines()
        
        image = timeline.generate_cpu_trend_image(self.cpu_data)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        self.assertIn(b'<svg', image)
        self.assertIn(b'CPU', image)

    def test_timeline_ram_trend(self):
        """Test memory trend (RAM) timeline."""
        timeline = Timelines()
        
        ram_data = {
            i: 200 + 50 * ((i % 30) / 30)
            for i in range(1, 101)
        }
        
        image = timeline.generate_cpu_trend_image(ram_data)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)

    def test_timeline_accuracy_curve(self):
        """Test accuracy curve timeline."""
        timeline = Timelines()
        
        image = timeline.generate_accuracy_curve_image(self.accuracy_data)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        self.assertIn(b'<svg', image)
        self.assertIn(b'Accuracy', image)

    def test_timeline_ocr_trend(self):
        """Test OCR confidence trend."""
        timeline = Timelines()
        
        image = timeline.generate_ocr_confidence_trend(self.ocr_data)
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)

    def test_comparison_variant_a_vs_b(self):
        """Test variant A vs B comparison."""
        comp = Comparisons()
        comp.add_variant_data('variant_a', self.variant_a)
        comp.add_variant_data('variant_b', self.variant_b)
        
        # HTML table
        table_html = comp.generate_comparison_table()
        
        self.assertIsNotNone(table_html)
        self.assertIn('<table', table_html)
        self.assertIn('variant_a', table_html)
        self.assertIn('variant_b', table_html)
        self.assertIn('92.50', table_html)  # Variant A accuracy
        self.assertIn('88.00', table_html)  # Variant B accuracy

    def test_comparison_cps_load_before_after(self):
        """Test CPS/load before/after comparison."""
        comp = Comparisons()
        
        before = {
            'accuracy': 85.0,
            'latency_ms': 95,
            'cpu_percent': 45,
        }
        
        after = {
            'accuracy': 92.0,
            'latency_ms': 78,
            'cpu_percent': 35,
        }
        
        comp.add_variant_data('before_optimization', before)
        comp.add_variant_data('after_optimization', after)
        
        # SVG chart
        image = comp.generate_comparison_chart_image()
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        self.assertIn(b'<svg', image)

    def test_trend_analysis_accuracy_degradation(self):
        """Test accuracy degradation detection."""
        trend = TrendAnalysis()
        
        # Degrading accuracy: 95, 93, 91, 89, 87, 85
        degrading_data = [95, 93, 91, 89, 87, 85]
        trend.add_accuracy_data(degrading_data)
        
        degradation = trend.calculate_degradation()
        
        self.assertIsNotNone(degradation)
        self.assertLess(degradation, 0)  # Should be negative (degrading)

    def test_trend_analysis_chat_recovery_rate(self):
        """Test chat recovery rate consistency."""
        trend = TrendAnalysis()
        
        rate = trend.calculate_recovery_rate(self.recovery_data)
        
        self.assertIsNotNone(rate)
        self.assertGreater(rate, 0)
        self.assertLess(rate, 100)

    def test_trend_analysis_anomaly_detection(self):
        """Test statistical anomaly detection."""
        trend = TrendAnalysis()
        
        # Data with anomaly at index 4
        data_with_anomaly = [90, 89, 91, 92, 10, 91, 90]
        trend.add_accuracy_data(data_with_anomaly)
        
        anomalies = trend.detect_anomalies(threshold=2.0)
        
        self.assertIsNotNone(anomalies)
        # Should detect the 10 as anomaly
        self.assertGreater(len(anomalies), 0)

    def test_trend_analysis_degradation_chart(self):
        """Test degradation chart generation."""
        trend = TrendAnalysis()
        
        trend.add_accuracy_data(list(self.accuracy_data.values()))
        
        image = trend.generate_degradation_chart_image()
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)
        self.assertIn(b'<svg', image)

    def test_edge_case_empty_data(self):
        """Test visualizations with empty data."""
        heatmap = Heatmaps()
        timeline = Timelines()
        comp = Comparisons()
        trend = TrendAnalysis()
        
        # Should handle gracefully
        heatmap_img = heatmap.generate_click_heatmap_image()
        timeline_img = timeline.generate_phase_timeline_image()
        comp_table = comp.generate_comparison_table()
        trend_img = trend.generate_degradation_chart_image()
        
        self.assertIsNotNone(heatmap_img)
        self.assertIsNotNone(timeline_img)
        self.assertIsNotNone(comp_table)
        self.assertIsNotNone(trend_img)

    def test_edge_case_single_iteration(self):
        """Test visualizations with single data point."""
        heatmap = Heatmaps()
        heatmap.add_click_positions([(100, 200)])
        
        image = heatmap.generate_click_heatmap_image()
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)

    def test_edge_case_large_dataset(self):
        """Test visualizations with large datasets."""
        heatmap = Heatmaps()
        
        # 10,000 click positions
        large_clicks = [(100 + (i % 1000), 200 + (i % 1000)) for i in range(10000)]
        heatmap.add_click_positions(large_clicks)
        
        image = heatmap.generate_click_heatmap_image()
        
        self.assertIsNotNone(image)
        self.assertGreater(len(image), 0)

    def test_visualization_file_export_integration(self):
        """Test exporting all visualizations to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Heatmap
            heatmap = Heatmaps()
            heatmap.add_click_positions(self.click_positions)
            heatmap_path = tmpdir / 'heatmap.svg'
            heatmap.save_image(str(heatmap_path))
            self.assertTrue(heatmap_path.exists())
            
            # Timeline
            timeline = Timelines()
            for iteration, phase, start_ms, end_ms in self.phase_events:
                timeline.add_phase_event(iteration, phase, start_ms, end_ms)
            timeline_path = tmpdir / 'timeline.svg'
            timeline.save_image(str(timeline_path))
            self.assertTrue(timeline_path.exists())
            
            # Comparison
            comp = Comparisons()
            comp.add_variant_data('a', self.variant_a)
            comp.add_variant_data('b', self.variant_b)
            comp_path = tmpdir / 'comparison.svg'
            comp.save_image(str(comp_path))
            self.assertTrue(comp_path.exists())
            
            # Trend
            trend = TrendAnalysis()
            trend.add_accuracy_data(list(self.accuracy_data.values()))
            trend_path = tmpdir / 'trend.svg'
            trend.save_image(str(trend_path))
            self.assertTrue(trend_path.exists())

    def test_summary_metrics_calculation(self):
        """Test trend summary calculation."""
        trend = TrendAnalysis()
        
        trend.add_accuracy_data(list(self.accuracy_data.values()))
        
        summary = trend.get_trend_summary()
        
        self.assertIn('mean', summary)
        self.assertIn('std_dev', summary)
        self.assertIn('min', summary)
        self.assertIn('max', summary)
        self.assertIn('count', summary)
        self.assertIn('degradation', summary)
        self.assertIn('anomaly_count', summary)
        
        self.assertGreater(summary['mean'], 0)
        self.assertGreater(summary['count'], 0)


if __name__ == '__main__':
    unittest.main()
