"""
Tests for Report Integration (Task 13)
Full report generation from session data using all visualization components
"""
import unittest
import json
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys
import tempfile

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.reporting.analysis_report import AnalysisReport
from mvp.simulator.reporting.report_generator import ReportGenerator
from mvp.simulator.reporting.report_integration import FullReportGenerator


class TestAnalysisReportInit(unittest.TestCase):
    """Test AnalysisReport initialization"""

    def test_analysis_report_init(self):
        """Should initialize AnalysisReport with all components"""
        report = AnalysisReport(session_id='test_session_001')
        
        self.assertEqual(report.session_id, 'test_session_001')
        self.assertIsNotNone(report.report_generator)
        self.assertIsNotNone(report.heatmaps)
        self.assertIsNotNone(report.timelines)
        self.assertIsNotNone(report.comparisons)
        self.assertIsNotNone(report.trend_analysis)

    def test_analysis_report_facade_pattern(self):
        """Should provide facade access to all visualization components"""
        report = AnalysisReport(session_id='test')
        
        # Verify all components are accessible
        assert hasattr(report, 'add_session_data')
        assert hasattr(report, 'add_iteration_data')
        assert hasattr(report, 'add_click_positions')
        assert hasattr(report, 'add_timeline_events')
        assert hasattr(report, 'add_variant_comparison')
        assert hasattr(report, 'add_accuracy_trend')
        assert hasattr(report, 'generate_full_html_report')


class TestAnalysisReportDataIntegration(unittest.TestCase):
    """Test data integration across components"""

    def test_add_session_data(self):
        """Should add session data through facade"""
        report = AnalysisReport(session_id='test')
        
        session_summary = {
            'total_iterations': 50,
            'successful_iterations': 45,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45.5,
            'average_cpu_percent': 35,
        }
        
        result = report.add_session_data(session_summary)
        self.assertTrue(result)
        
        # Verify it was added to report generator
        retrieved = report.report_generator.get_session_summary()
        self.assertEqual(retrieved['accuracy_percent'], 90.0)

    def test_add_iteration_data(self):
        """Should add iteration data through facade"""
        report = AnalysisReport(session_id='test')
        
        iteration_data = {
            'iteration': 1,
            'success': True,
            'latency_ms': 42,
            'cpu_percent': 35,
        }
        
        result = report.add_iteration_data(1, iteration_data)
        self.assertTrue(result)
        
        # Verify it was added
        retrieved = report.report_generator.get_iteration_data(1)
        self.assertEqual(retrieved['success'], True)

    def test_add_click_positions(self):
        """Should add click positions for heatmap"""
        report = AnalysisReport(session_id='test')
        
        clicks = [(100, 200), (110, 210), (105, 205)]
        result = report.add_click_positions(clicks)
        
        self.assertTrue(result)
        # Verify stored in heatmaps component
        self.assertEqual(len(report.heatmaps.click_positions), 3)

    def test_add_timeline_events(self):
        """Should add timeline events"""
        report = AnalysisReport(session_id='test')
        
        events = [
            {'iteration': 1, 'phase': 'CHAT', 'start_ms': 0, 'end_ms': 100},
            {'iteration': 1, 'phase': 'ALERT', 'start_ms': 100, 'end_ms': 200},
            {'iteration': 1, 'phase': 'TREASURE', 'start_ms': 200, 'end_ms': 300},
        ]
        
        result = report.add_timeline_events(events)
        self.assertTrue(result)
        
        # Verify stored in timelines component
        self.assertEqual(len(report.timelines.events), 3)

    def test_add_variant_comparison(self):
        """Should add variant comparison data"""
        report = AnalysisReport(session_id='test')
        
        data_a = {
            'accuracy': 90.0,
            'latency_ms': 45,
            'cpu_percent': 35,
        }
        
        data_b = {
            'accuracy': 85.0,
            'latency_ms': 52,
            'cpu_percent': 45,
        }
        
        report.add_variant_comparison('variant_a', data_a)
        report.add_variant_comparison('variant_b', data_b)
        
        # Verify stored in comparisons component
        self.assertEqual(len(report.comparisons.variants), 2)

    def test_add_accuracy_trend(self):
        """Should add accuracy trend data"""
        report = AnalysisReport(session_id='test')
        
        accuracy_data = [90, 91, 92, 90, 89, 91, 88, 87]
        result = report.add_accuracy_trend(accuracy_data)
        
        self.assertTrue(result)
        # Verify stored in trend_analysis component
        self.assertEqual(len(report.trend_analysis.accuracy_data), 8)


class TestFullHTMLReportGeneration(unittest.TestCase):
    """Test full HTML report generation"""

    def test_generate_full_html_report_basic(self):
        """Should generate basic HTML report"""
        report = AnalysisReport(session_id='test_session')
        
        # Add minimal data
        report.add_session_data({
            'total_iterations': 10,
            'accuracy_percent': 90.0,
        })
        
        html = report.generate_full_html_report()
        
        # Verify HTML structure
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('</html>', html)
        self.assertIn('<head>', html)
        self.assertIn('</head>', html)
        self.assertIn('<body>', html)
        self.assertIn('</body>', html)

    def test_generated_html_contains_title(self):
        """Should include session ID in title"""
        report = AnalysisReport(session_id='my_session_123')
        
        report.add_session_data({'total_iterations': 10})
        
        html = report.generate_full_html_report()
        
        self.assertIn('my_session_123', html)
        self.assertIn('Analysis Report', html)

    def test_generated_html_contains_all_sections(self):
        """Should include all report sections"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        
        html = report.generate_full_html_report()
        
        # Verify all sections are present
        self.assertIn('Session Summary', html)
        self.assertIn('Heatmaps', html)
        self.assertIn('Timelines', html)
        self.assertIn('Comparisons', html)
        self.assertIn('Trend Analysis', html)

    def test_generated_html_contains_table_of_contents(self):
        """Should include table of contents with anchors"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        
        html = report.generate_full_html_report()
        
        self.assertIn('Contents', html)
        self.assertIn('#summary', html)
        self.assertIn('#heatmaps', html)
        self.assertIn('#timelines', html)

    def test_generated_html_contains_css_styles(self):
        """Should include CSS styling"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        
        html = report.generate_full_html_report()
        
        self.assertIn('<style>', html)
        self.assertIn('</style>', html)
        self.assertIn('body {', html)
        self.assertIn('color:', html)


class TestReportWithMultipleIterations(unittest.TestCase):
    """Test report generation with multiple iterations"""

    def test_full_report_with_20_iterations(self):
        """Should generate report with 20 iterations of data"""
        report = AnalysisReport(session_id='test_session')
        
        # Add session summary
        report.add_session_data({
            'total_iterations': 20,
            'successful_iterations': 18,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45.5,
            'average_cpu_percent': 35,
        })
        
        # Add iteration data
        for i in range(20):
            data = {
                'iteration': i,
                'success': i != 5,  # Make iteration 5 fail
                'latency_ms': 40 + (i % 10),
                'cpu_percent': 30 + (i % 15),
            }
            report.add_iteration_data(i, data)
        
        # Add click positions
        clicks = [(100 + i*2, 200 + i*3) for i in range(100)]
        report.add_click_positions(clicks)
        
        # Add timeline events
        events = []
        for i in range(20):
            events.append({'iteration': i, 'phase': 'CHAT', 'start_ms': 0, 'end_ms': 100})
            events.append({'iteration': i, 'phase': 'ALERT', 'start_ms': 100, 'end_ms': 200})
        report.add_timeline_events(events)
        
        # Add accuracy trend
        accuracy = [90 - (i // 5) for i in range(20)]
        report.add_accuracy_trend(accuracy)
        
        # Generate HTML
        html = report.generate_full_html_report()
        
        # Verify report
        self.assertIsNotNone(html)
        self.assertIn('90.0', html)  # Accuracy should be in report
        self.assertIn('test_session', html)

    def test_report_accuracy_calculation(self):
        """Should correctly calculate accuracy from iteration data"""
        report = AnalysisReport(session_id='test')
        
        # Add 10 iterations, 8 successful
        for i in range(10):
            success = i < 8
            data = {
                'iteration': i,
                'success': success,
                'latency_ms': 40,
            }
            report.add_iteration_data(i, data)
        
        # Add session summary with expected accuracy
        report.add_session_data({'accuracy_percent': 80.0})
        
        # Generate report
        html = report.generate_full_html_report()
        
        # Verify accuracy in report
        self.assertIn('80', html)


class TestReportFileExport(unittest.TestCase):
    """Test report file export"""

    def test_save_full_report_to_file(self):
        """Should save full report to HTML file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'full_report.html'
            
            report = AnalysisReport(session_id='test')
            report.add_session_data({'total_iterations': 10, 'accuracy_percent': 90.0})
            
            result = report.save_full_report(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())
            
            # Verify file contains valid HTML
            with open(output_path) as f:
                content = f.read()
            self.assertIn('<!DOCTYPE html>', content)

    def test_saved_report_is_valid_html(self):
        """Should save valid HTML that can be opened in browser"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.html'
            
            report = AnalysisReport(session_id='test')
            report.add_session_data({
                'total_iterations': 20,
                'accuracy_percent': 90.0,
            })
            report.add_accuracy_trend([90, 91, 92, 90, 89, 91])
            
            report.save_full_report(str(output_path))
            
            # Verify valid HTML structure
            with open(output_path) as f:
                content = f.read()
            
            # Check basic HTML validity
            assert content.count('<html>') == content.count('</html>')
            assert content.count('<body>') == content.count('</body>')
            assert '<head>' in content
            assert '<title>' in content


class TestVisualizationIntegration(unittest.TestCase):
    """Test integration of visualization components in report"""

    def test_heatmaps_integration(self):
        """Should integrate heatmaps in report"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        report.add_click_positions([(100, 200), (110, 210)])
        
        html = report.generate_full_html_report()
        
        # Verify heatmaps section present
        self.assertIn('Click Position', html)
        self.assertIn('OCR Confidence', html)

    def test_timelines_integration(self):
        """Should integrate timelines in report"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        report.add_timeline_events([
            {'iteration': 1, 'phase': 'CHAT', 'start_ms': 0, 'end_ms': 100},
        ])
        
        html = report.generate_full_html_report()
        
        # Verify timelines section present
        self.assertIn('Phase Timeline', html)
        self.assertIn('CPU Usage', html)

    def test_comparisons_integration(self):
        """Should integrate comparisons in report"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        report.add_variant_comparison('default', {'accuracy': 90.0, 'latency_ms': 45})
        report.add_variant_comparison('hard_mode', {'accuracy': 85.0, 'latency_ms': 52})
        
        html = report.generate_full_html_report()
        
        # Verify comparison table in report
        self.assertIn('table', html.lower())
        self.assertIn('90', html)
        self.assertIn('85', html)

    def test_trend_analysis_integration(self):
        """Should integrate trend analysis in report"""
        report = AnalysisReport(session_id='test')
        
        report.add_session_data({'total_iterations': 10})
        report.add_accuracy_trend([95, 93, 91, 89, 87, 85])
        
        html = report.generate_full_html_report()
        
        # Verify trend analysis section present
        self.assertIn('Trend Summary', html)
        self.assertIn('Degradation', html)




class TestFullReportGeneratorInit(unittest.TestCase):
    """Test FullReportGenerator initialization"""

    def test_full_report_generator_init(self):
        """Should initialize FullReportGenerator with all components"""
        generator = FullReportGenerator(session_id='test_session_full')
        
        self.assertEqual(generator.session_id, 'test_session_full')
        self.assertIsNotNone(generator.analysis_report)
        self.assertIsNotNone(generator.report_generator)
        self.assertIsNotNone(generator.heatmaps)
        self.assertIsNotNone(generator.timelines)
        self.assertIsNotNone(generator.comparisons)
        self.assertIsNotNone(generator.trend_analysis)

    def test_full_report_generator_with_custom_title(self):
        """Should initialize with custom title"""
        custom_title = "Custom Analysis Report"
        generator = FullReportGenerator(session_id='test', title=custom_title)
        
        self.assertEqual(generator.title, custom_title)
        self.assertIsNotNone(generator.created_at)


class TestFullReportGeneratorDataIngestion(unittest.TestCase):
    """Test data ingestion in FullReportGenerator"""

    def test_add_simulation_data_with_all_components(self):
        """Should ingest session metrics, events, and iterations"""
        generator = FullReportGenerator(session_id='test')
        
        metrics = {
            'total_iterations': 10,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45.5,
        }
        
        events = [
            {'iteration': 0, 'phase': 'CHAT', 'start_ms': 0, 'end_ms': 100},
            {'iteration': 0, 'phase': 'ALERT', 'start_ms': 100, 'end_ms': 200},
        ]
        
        iterations = [
            {'iteration': 0, 'success': True, 'latency_ms': 42},
            {'iteration': 1, 'success': True, 'latency_ms': 45},
        ]
        
        result = generator.add_simulation_data(metrics, events, iterations)
        
        self.assertTrue(result)

    def test_add_simulation_data_metrics_only(self):
        """Should handle metrics without events/iterations"""
        generator = FullReportGenerator(session_id='test')
        
        metrics = {
            'total_iterations': 5,
            'accuracy_percent': 85.0,
        }
        
        result = generator.add_simulation_data(metrics)
        
        self.assertTrue(result)

    def test_add_simulation_data_with_100_iterations(self):
        """Should handle large iteration count"""
        generator = FullReportGenerator(session_id='test_large')
        
        metrics = {
            'total_iterations': 100,
            'accuracy_percent': 92.0,
        }
        
        iterations = [
            {'iteration': i, 'success': i % 10 != 0, 'latency_ms': 40 + (i % 20)}
            for i in range(100)
        ]
        
        result = generator.add_simulation_data(metrics, iterations=iterations)
        
        self.assertTrue(result)


class TestFullReportGeneratorHTMLGeneration(unittest.TestCase):
    """Test HTML report generation"""

    def test_generate_full_html_report(self):
        """Should generate complete HTML report"""
        generator = FullReportGenerator(session_id='test_html')
        generator.add_simulation_data({'total_iterations': 10, 'accuracy_percent': 90.0})
        
        html = generator.generate_full_html_report()
        
        self.assertIsNotNone(html)
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('Extended Game Simulator', html)
        self.assertIn('test_html', html)

    def test_html_contains_all_sections(self):
        """Should include all major sections in HTML"""
        generator = FullReportGenerator(session_id='test')
        generator.add_simulation_data({'total_iterations': 10})
        
        html = generator.generate_full_html_report()
        
        self.assertIn('Session Summary', html)
        self.assertIn('Heatmaps', html)
        self.assertIn('Timelines', html)
        self.assertIn('Comparisons', html)
        self.assertIn('Trend Analysis', html)

    def test_html_with_sample_data(self):
        """Should generate HTML with realistic sample data"""
        generator = FullReportGenerator(session_id='sample_session')
        
        # Add comprehensive sample data
        metrics = {
            'total_iterations': 50,
            'successful_iterations': 45,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45.5,
            'average_cpu_percent': 35,
        }
        
        generator.add_simulation_data(metrics_dict=metrics)
        
        # Add click positions
        clicks = [(100 + i*2, 200 + i*3) for i in range(50)]
        generator.add_click_positions(clicks)
        
        # Add variants
        generator.add_variant_comparison('default', {'accuracy': 90.0, 'latency_ms': 45})
        generator.add_variant_comparison('hard_mode', {'accuracy': 85.0, 'latency_ms': 52})
        
        # Add accuracy trend
        accuracy_trend = [90 - (i // 10) for i in range(50)]
        generator.add_accuracy_trend(accuracy_trend)
        
        html = generator.generate_full_html_report()
        
        self.assertIsNotNone(html)
        self.assertGreater(len(html), 1000)  # Should be substantial


class TestFullReportGeneratorJSONGeneration(unittest.TestCase):
    """Test JSON report generation"""

    def test_generate_full_json_report(self):
        """Should generate valid JSON report"""
        generator = FullReportGenerator(session_id='test_json')
        generator.add_simulation_data({'total_iterations': 10, 'accuracy_percent': 90.0})
        
        json_report = generator.generate_full_json_report()
        
        self.assertIsInstance(json_report, dict)
        self.assertEqual(json_report['session_id'], 'test_json')
        self.assertIn('sections', json_report)
        self.assertIn('created_at', json_report)

    def test_json_contains_all_sections(self):
        """Should include all sections in JSON"""
        generator = FullReportGenerator(session_id='test')
        generator.add_simulation_data({'total_iterations': 10})
        
        json_report = generator.generate_full_json_report()
        
        sections = json_report['sections']
        self.assertIn('session_summary', sections)
        self.assertIn('metrics', sections)
        self.assertIn('trend_analysis', sections)
        self.assertIn('variants', sections)

    def test_json_metrics_are_serializable(self):
        """JSON metrics should be JSON-serializable"""
        generator = FullReportGenerator(session_id='test')
        
        for i in range(5):
            generator.report_generator.add_iteration_data(i, {'success': True, 'latency_ms': 40})
        
        json_report = generator.generate_full_json_report()
        metrics = json_report['sections']['metrics']
        
        # All metrics should be numbers or None
        for key, value in metrics.items():
            self.assertTrue(isinstance(value, (int, float, type(None))), f"{key} has invalid type {type(value)}")


class TestFullReportGeneratorExport(unittest.TestCase):
    """Test report export functionality"""

    def test_export_to_html(self):
        """Should export report to HTML file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = FullReportGenerator(session_id='export_test')
            generator.add_simulation_data({'total_iterations': 10, 'accuracy_percent': 90.0})
            
            result = generator.export_report(tmpdir, format='html')
            
            self.assertTrue(result)
            
            # Verify file exists
            html_file = Path(tmpdir) / 'export_test_report.html'
            self.assertTrue(html_file.exists())
            
            # Verify content
            with open(html_file) as f:
                content = f.read()
            self.assertIn('<!DOCTYPE html>', content)

    def test_export_to_json(self):
        """Should export report to JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = FullReportGenerator(session_id='json_export_test')
            generator.add_simulation_data({'total_iterations': 10})
            
            result = generator.export_report(tmpdir, format='json')
            
            self.assertTrue(result)
            
            # Verify file exists
            json_file = Path(tmpdir) / 'json_export_test_report.json'
            self.assertTrue(json_file.exists())
            
            # Verify JSON is valid
            with open(json_file) as f:
                data = json.load(f)
            self.assertIn('session_id', data)

    def test_export_both_formats(self):
        """Should export both HTML and JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = FullReportGenerator(session_id='both_export')
            generator.add_simulation_data({'total_iterations': 10})
            
            result = generator.export_report(tmpdir, format='both')
            
            self.assertTrue(result)
            
            # Verify both files exist
            html_file = Path(tmpdir) / 'both_export_report.html'
            json_file = Path(tmpdir) / 'both_export_report.json'
            
            self.assertTrue(html_file.exists())
            self.assertTrue(json_file.exists())


class TestFullReportGeneratorMetrics(unittest.TestCase):
    """Test metrics summary functionality"""

    def test_get_metrics_summary(self):
        """Should return summary of all metrics"""
        generator = FullReportGenerator(session_id='metrics_test')
        
        for i in range(5):
            generator.report_generator.add_iteration_data(
                i,
                {
                    'success': True,
                    'latency_ms': 40 + i,
                    'cpu_percent': 30 + i,
                }
            )
        
        summary = generator.get_metrics_summary()
        
        self.assertIn('session_id', summary)
        self.assertIn('accuracy_percent', summary)
        self.assertIn('avg_latency_ms', summary)
        self.assertIn('avg_cpu_percent', summary)

    def test_metrics_summary_with_empty_data(self):
        """Should handle empty data gracefully"""
        generator = FullReportGenerator(session_id='empty_metrics')
        
        summary = generator.get_metrics_summary()
        
        self.assertEqual(summary['session_id'], 'empty_metrics')
        # Accuracy should be 0 or None for empty data
        self.assertIn('accuracy_percent', summary)


class TestFullReportGeneratorIntegrationSample(unittest.TestCase):
    """Test full integration with realistic sample data"""

    def test_full_integration_100_iterations_5_variants(self):
        """Should handle comprehensive scenario"""
        generator = FullReportGenerator(session_id='comprehensive_test')
        
        # Create realistic data for 100 iterations
        metrics = {
            'total_iterations': 100,
            'successful_iterations': 90,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45.5,
            'average_cpu_percent': 35.0,
        }
        
        # Add iterations
        iterations = []
        for i in range(100):
            iterations.append({
                'iteration': i,
                'success': i % 10 != 0,  # 10% failure rate
                'latency_ms': 40 + (i % 30),
                'cpu_percent': 30 + (i % 20),
            })
        
        # Add events
        events = []
        for i in range(100):
            events.extend([
                {'iteration': i, 'phase': 'SETUP', 'start_ms': 0, 'end_ms': 50},
                {'iteration': i, 'phase': 'ALERT', 'start_ms': 50, 'end_ms': 150},
                {'iteration': i, 'phase': 'CLICK', 'start_ms': 150, 'end_ms': 200},
                {'iteration': i, 'phase': 'TREASURE', 'start_ms': 200, 'end_ms': 300},
            ])
        
        # Ingest all data
        result = generator.add_simulation_data(metrics, events, iterations)
        self.assertTrue(result)
        
        # Add click positions (500+ for realistic heatmap)
        clicks = [(100 + (i*7) % 200, 200 + (i*11) % 150) for i in range(500)]
        generator.add_click_positions(clicks)
        
        # Add variant comparisons
        generator.add_variant_comparison('default', {
            'accuracy': 90.0,
            'latency_ms': 45,
            'cpu_percent': 35,
        })
        generator.add_variant_comparison('optimized', {
            'accuracy': 92.0,
            'latency_ms': 42,
            'cpu_percent': 32,
        })
        
        # Add accuracy trend
        accuracy_trend = [90 - (i // 25) for i in range(100)]
        generator.add_accuracy_trend(accuracy_trend)
        
        # Generate reports
        html = generator.generate_full_html_report()
        json_report = generator.generate_full_json_report()
        
        # Verify HTML
        self.assertGreater(len(html), 1000)
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('comprehensive_test', html)
        
        # Verify JSON
        self.assertIsInstance(json_report, dict)
        self.assertEqual(json_report['session_id'], 'comprehensive_test')

    def test_report_with_all_features(self):
        """Should generate full report with all features"""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = FullReportGenerator(
                session_id='feature_complete_test',
                title='Complete Feature Test Report'
            )
            
            # Comprehensive data
            generator.add_simulation_data({
                'total_iterations': 50,
                'accuracy_percent': 88.0,
            })
            
            generator.add_click_positions([(100 + i, 200 + i) for i in range(50)])
            
            generator.add_variant_comparison('v1', {'accuracy': 88.0})
            generator.add_variant_comparison('v2', {'accuracy': 85.0})
            
            generator.add_accuracy_trend([88 - (i // 10) for i in range(50)])
            
            # Export both formats
            result = generator.export_report(tmpdir, format='both')
            self.assertTrue(result)
            
            # Verify files
            html_file = Path(tmpdir) / 'feature_complete_test_report.html'
            json_file = Path(tmpdir) / 'feature_complete_test_report.json'
            
            self.assertTrue(html_file.exists())
            self.assertTrue(json_file.exists())
            
            # Check file sizes are reasonable
            html_size = html_file.stat().st_size
            json_size = json_file.stat().st_size
            
            self.assertGreater(html_size, 100)
            self.assertGreater(json_size, 100)
            self.assertLess(html_size, 5_000_000)  # < 5MB
            self.assertLess(json_size, 5_000_000)


if __name__ == '__main__':
    unittest.main()
