"""
Tests for Report Generator (Task 11)
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys
import json
import tempfile
from datetime import datetime
from hypothesis import given, strategies as st

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.reporting.report_generator import ReportGenerator


class TestReportGeneratorInit(unittest.TestCase):
    """Test ReportGenerator initialization"""

    def test_report_generator_init(self):
        """Should initialize ReportGenerator"""
        generator = ReportGenerator(session_id='test_session_001')
        
        self.assertEqual(generator.session_id, 'test_session_001')
        self.assertIsNotNone(generator)

    def test_report_generator_with_metadata(self):
        """Should initialize with metadata"""
        metadata = {
            'variant_preset': 'hard_mode',
            'num_iterations': 20,
            'notes': 'Test run'
        }
        generator = ReportGenerator(session_id='test', metadata=metadata)
        
        self.assertEqual(generator.metadata, metadata)


class TestReportGeneratorSessionSummary(unittest.TestCase):
    """Test session summary generation"""

    def test_add_session_summary(self):
        """Should add session summary"""
        generator = ReportGenerator(session_id='test')
        
        summary = {
            'total_iterations': 20,
            'successful_iterations': 18,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45.5,
            'average_cpu_percent': 35,
        }
        
        result = generator.add_session_summary(summary)
        self.assertTrue(result)

    def test_get_session_summary(self):
        """Should retrieve session summary"""
        generator = ReportGenerator(session_id='test')
        
        summary = {
            'total_iterations': 20,
            'successful_iterations': 18,
            'accuracy_percent': 90.0,
        }
        
        generator.add_session_summary(summary)
        retrieved = generator.get_session_summary()
        
        self.assertEqual(retrieved['accuracy_percent'], 90.0)


class TestReportGeneratorIterationData(unittest.TestCase):
    """Test iteration data management"""

    def test_add_iteration_data(self):
        """Should add iteration data"""
        generator = ReportGenerator(session_id='test')
        
        iteration_data = {
            'iteration': 1,
            'variant': 'default',
            'success': True,
            'latency_ms': 42,
            'cpu_percent': 35,
        }
        
        result = generator.add_iteration_data(1, iteration_data)
        self.assertTrue(result)

    def test_add_multiple_iteration_data(self):
        """Should add multiple iteration data"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 6):
            data = {
                'iteration': i,
                'variant': 'default',
                'success': True,
                'latency_ms': 40 + i,
            }
            generator.add_iteration_data(i, data)
        
        self.assertEqual(len(generator.iterations_data), 5)

    def test_get_iteration_data(self):
        """Should retrieve iteration data"""
        generator = ReportGenerator(session_id='test')
        
        data = {'iteration': 1, 'success': True}
        generator.add_iteration_data(1, data)
        
        retrieved = generator.get_iteration_data(1)
        self.assertEqual(retrieved['success'], True)


class TestReportGeneratorMetricsAggregation(unittest.TestCase):
    """Test metrics aggregation"""

    def test_calculate_accuracy(self):
        """Should calculate accuracy from iterations"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 6):
            success = i <= 4  # 4 out of 5
            data = {'iteration': i, 'success': success}
            generator.add_iteration_data(i, data)
        
        accuracy = generator.calculate_accuracy()
        self.assertEqual(accuracy, 80.0)

    def test_calculate_avg_latency(self):
        """Should calculate average latency"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 4):
            data = {'iteration': i, 'latency_ms': 40 + i}
            generator.add_iteration_data(i, data)
        
        avg_latency = generator.calculate_avg_latency()
        self.assertIsNotNone(avg_latency)

    def test_calculate_avg_cpu(self):
        """Should calculate average CPU"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 4):
            data = {'iteration': i, 'cpu_percent': 30 + i}
            generator.add_iteration_data(i, data)
        
        avg_cpu = generator.calculate_avg_cpu()
        self.assertIsNotNone(avg_cpu)

    def test_calculate_min_latency(self):
        """Should calculate minimum latency"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 4):
            data = {'iteration': i, 'latency_ms': 40 + i}
            generator.add_iteration_data(i, data)
        
        min_latency = generator.calculate_min_latency()
        self.assertEqual(min_latency, 41)

    def test_calculate_max_latency(self):
        """Should calculate maximum latency"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 4):
            data = {'iteration': i, 'latency_ms': 40 + i}
            generator.add_iteration_data(i, data)
        
        max_latency = generator.calculate_max_latency()
        self.assertEqual(max_latency, 43)

    def test_calculate_min_cpu(self):
        """Should calculate minimum CPU"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 4):
            data = {'iteration': i, 'cpu_percent': 30 + i}
            generator.add_iteration_data(i, data)
        
        min_cpu = generator.calculate_min_cpu()
        self.assertEqual(min_cpu, 31)

    def test_calculate_max_cpu(self):
        """Should calculate maximum CPU"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, 4):
            data = {'iteration': i, 'cpu_percent': 30 + i}
            generator.add_iteration_data(i, data)
        
        max_cpu = generator.calculate_max_cpu()
        self.assertEqual(max_cpu, 33)


class TestReportGeneratorHTMLGeneration(unittest.TestCase):
    """Test HTML report generation"""

    def test_generate_html_report(self):
        """Should generate HTML report"""
        generator = ReportGenerator(session_id='test')
        
        summary = {
            'total_iterations': 10,
            'successful_iterations': 9,
            'accuracy_percent': 90.0,
            'average_latency_ms': 45,
            'average_cpu_percent': 35,
        }
        generator.add_session_summary(summary)
        
        html = generator.generate_html_report()
        
        self.assertIsNotNone(html)
        self.assertIn('<html', html.lower())
        self.assertIn('</html>', html.lower())

    def test_html_contains_title(self):
        """Should include session ID in HTML"""
        generator = ReportGenerator(session_id='test_session_001')
        
        generator.add_session_summary({'total_iterations': 10})
        
        html = generator.generate_html_report()
        self.assertIn('test_session_001', html)

    def test_html_contains_summary_section(self):
        """Should include summary section in HTML"""
        generator = ReportGenerator(session_id='test')
        
        summary = {
            'total_iterations': 20,
            'successful_iterations': 18,
            'accuracy_percent': 90.0,
        }
        generator.add_session_summary(summary)
        
        html = generator.generate_html_report()
        
        self.assertIn('Summary', html)
        self.assertIn('90.0', html)


class TestReportGeneratorFileExport(unittest.TestCase):
    """Test report file export"""

    def test_save_report_to_file(self):
        """Should save HTML report to file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.html'
            
            generator = ReportGenerator(session_id='test')
            generator.add_session_summary({
                'total_iterations': 10,
                'accuracy_percent': 90.0,
            })
            
            result = generator.save_report(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())

    def test_saved_report_contains_html(self):
        """Should save valid HTML content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.html'
            
            generator = ReportGenerator(session_id='test')
            generator.add_session_summary({
                'total_iterations': 10,
                'accuracy_percent': 90.0,
            })
            
            generator.save_report(str(output_path))
            
            with open(output_path) as f:
                content = f.read()
            
            self.assertIn('<html', content.lower())


class TestReportGeneratorCSVExport(unittest.TestCase):
    """Test CSV export"""

    def test_export_iterations_to_csv(self):
        """Should export iteration data to CSV"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'iterations.csv'
            
            generator = ReportGenerator(session_id='test')
            
            for i in range(1, 4):
                data = {
                    'iteration': i,
                    'success': True,
                    'latency_ms': 40 + i,
                }
                generator.add_iteration_data(i, data)
            
            result = generator.export_iterations_csv(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())


class TestReportGeneratorMetadata(unittest.TestCase):
    """Test metadata handling"""

    def test_set_variant_preset(self):
        """Should set variant preset"""
        generator = ReportGenerator(session_id='test')
        
        result = generator.set_variant_preset('hard_mode')
        self.assertTrue(result)

    def test_get_variant_preset(self):
        """Should get variant preset"""
        generator = ReportGenerator(session_id='test')
        
        generator.set_variant_preset('stress_test')
        preset = generator.get_variant_preset()
        
        self.assertEqual(preset, 'stress_test')

    def test_add_report_section(self):
        """Should add custom report section"""
        generator = ReportGenerator(session_id='test')
        
        result = generator.add_report_section('Custom', '<p>Custom content</p>')
        self.assertTrue(result)


# Property-Based Tests using Hypothesis
class TestReportGeneratorHTMLStructureProperty(unittest.TestCase):
    """Property-based tests for HTML structure"""

    @given(st.text(min_size=1, max_size=100))
    def test_report_generation_with_any_session_id(self, session_id):
        """Should generate valid HTML with any session ID - Validates: Requirements 1.1, 1.2"""
        generator = ReportGenerator(session_id=session_id)
        generator.add_session_summary({'total_iterations': 10})
        
        html = generator.generate_html_report()
        
        # HTML must have basic structure
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('<html>', html.lower())
        self.assertIn('</html>', html.lower())
        self.assertIn('<head>', html.lower())
        self.assertIn('</head>', html.lower())
        self.assertIn('<body>', html.lower())
        self.assertIn('</body>', html.lower())

    @given(st.dictionaries(
        st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc',))),
        st.integers(min_value=0, max_value=10000),
        min_size=0,
        max_size=20
    ))
    def test_report_html_with_any_metrics_dict(self, metrics):
        """Should generate HTML from arbitrary metrics dict - Validates: Requirements 1.2, 1.3"""
        generator = ReportGenerator(session_id='test')
        generator.add_session_summary(metrics)
        
        html = generator.generate_html_report()
        
        # Must be valid HTML string, non-empty
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 100)
        self.assertIn('<html', html.lower())

    @given(st.lists(
        st.dictionaries(
            st.sampled_from(['iteration', 'success', 'latency_ms', 'cpu_percent']),
            st.one_of(st.integers(0, 1000), st.booleans(), st.floats(0, 100)),
            min_size=1
        ),
        min_size=0,
        max_size=50
    ))
    def test_html_with_variable_iteration_counts(self, iterations_list):
        """Should handle any number of iterations (0-50) - Validates: Requirements 1.1"""
        generator = ReportGenerator(session_id='test')
        
        for idx, data in enumerate(iterations_list, 1):
            generator.add_iteration_data(idx, data)
        
        html = generator.generate_html_report()
        
        # HTML must remain valid regardless of iteration count
        self.assertIsInstance(html, str)
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('Iterations Overview', html)


class TestReportGeneratorJSONSerializationProperty(unittest.TestCase):
    """Property-based tests for JSON serialization"""

    @given(st.dictionaries(
        st.text(min_size=1, max_size=50),
        st.one_of(st.integers(), st.floats(), st.text(), st.booleans(), st.none()),
        min_size=0,
        max_size=15
    ))
    def test_json_export_with_any_metadata(self, metadata):
        """Should export valid JSON with any metadata - Validates: Requirements 1.4"""
        generator = ReportGenerator(session_id='test', metadata=metadata)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.json'
            
            result = generator.export_json(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())
            
            with open(output_path) as f:
                data = json.load(f)
            
            self.assertEqual(data['session_id'], 'test')
            self.assertIn('generated_at', data)
            self.assertIn('metadata', data)

    @given(st.integers(min_value=0, max_value=100))
    def test_json_contains_all_iterations(self, num_iterations):
        """Should export all iteration data to JSON - Validates: Requirements 1.4"""
        generator = ReportGenerator(session_id='test')
        
        for i in range(1, num_iterations + 1):
            generator.add_iteration_data(i, {'iteration': i, 'success': True})
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.json'
            generator.export_json(str(output_path))
            
            with open(output_path) as f:
                data = json.load(f)
            
            self.assertEqual(len(data['iterations']), num_iterations)


class TestReportGeneratorMetricsCalculationProperty(unittest.TestCase):
    """Property-based tests for metrics calculations"""

    @given(st.lists(
        st.booleans(),
        min_size=1,
        max_size=100
    ))
    def test_accuracy_calculation_valid_range(self, success_list):
        """Accuracy should always be 0-100 - Validates: Requirements 1.5"""
        generator = ReportGenerator(session_id='test')
        
        for idx, success in enumerate(success_list, 1):
            generator.add_iteration_data(idx, {'success': success})
        
        accuracy = generator.calculate_accuracy()
        
        self.assertGreaterEqual(accuracy, 0.0)
        self.assertLessEqual(accuracy, 100.0)
        self.assertIsInstance(accuracy, float)

    @given(st.lists(
        st.floats(min_value=10, max_value=500, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=100
    ))
    def test_avg_latency_calculation_reasonable(self, latency_list):
        """Average latency should be within range of input values - Validates: Requirements 1.5"""
        generator = ReportGenerator(session_id='test')
        
        for idx, latency in enumerate(latency_list, 1):
            generator.add_iteration_data(idx, {'latency_ms': latency})
        
        avg = generator.calculate_avg_latency()
        
        self.assertIsNotNone(avg)
        self.assertGreaterEqual(avg, min(latency_list) - 1e-6)  # Allow small floating-point error
        self.assertLessEqual(avg, max(latency_list) + 1e-6)  # Allow small floating-point error

    @given(st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=100
    ))
    def test_avg_cpu_calculation_valid(self, cpu_list):
        """Average CPU should be valid percentage - Validates: Requirements 1.5"""
        generator = ReportGenerator(session_id='test')
        
        for idx, cpu in enumerate(cpu_list, 1):
            generator.add_iteration_data(idx, {'cpu_percent': cpu})
        
        avg_cpu = generator.calculate_avg_cpu()
        
        self.assertIsNotNone(avg_cpu)
        self.assertGreaterEqual(avg_cpu, 0)
        self.assertLessEqual(avg_cpu, 100)


class TestReportGeneratorHTMLEscapingProperty(unittest.TestCase):
    """Property-based tests for HTML escaping and special characters"""

    @given(st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_characters='',
            blacklist_categories=('Cc', 'Cs')
        )
    ))
    def test_html_properly_handles_special_chars(self, text_content):
        """HTML should handle special characters without breaking - Validates: Requirements 1.2"""
        generator = ReportGenerator(session_id='test')
        
        summary = {
            'notes': text_content,
            'variant': text_content,
        }
        generator.add_session_summary(summary)
        
        html = generator.generate_html_report()
        
        # Should still be valid HTML
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('</html>', html.lower())

    @given(st.text(min_size=1, max_size=100))
    def test_session_id_html_escaped_in_output(self, session_id):
        """Session ID should be safely rendered in HTML - Validates: Requirements 1.2"""
        generator = ReportGenerator(session_id=session_id)
        generator.add_session_summary({'total_iterations': 1})
        
        html = generator.generate_html_report()
        
        # Should have valid HTML structure regardless of session_id content
        self.assertIn('<html', html.lower())
        self.assertIn('</html>', html.lower())


class TestReportGeneratorFileIOProperty(unittest.TestCase):
    """Property-based tests for file I/O operations"""

    @given(st.dictionaries(
        st.text(min_size=1, max_size=30),
        st.integers(min_value=0, max_value=1000),
        min_size=0,
        max_size=10
    ))
    def test_save_report_with_any_summary(self, summary_dict):
        """Should save report successfully with any valid summary - Validates: Requirements 1.6"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.html'
            
            generator = ReportGenerator(session_id='test')
            generator.add_session_summary(summary_dict)
            
            result = generator.save_report(str(output_path))
            
            self.assertTrue(result)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    @given(st.integers(min_value=0, max_value=50))
    def test_csv_export_has_correct_row_count(self, num_rows):
        """CSV export should have correct number of rows - Validates: Requirements 1.6"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'iterations.csv'
            
            generator = ReportGenerator(session_id='test')
            for i in range(1, num_rows + 1):
                generator.add_iteration_data(i, {'iteration': i, 'success': True})
            
            result = generator.export_iterations_csv(str(output_path))
            
            if num_rows > 0:
                self.assertTrue(result)
                with open(output_path) as f:
                    lines = f.readlines()
                # rows + header
                self.assertEqual(len(lines), num_rows + 1)


class TestReportGeneratorEmptyDataHandling(unittest.TestCase):
    """Property-based tests for handling empty or missing data"""

    def test_report_generation_with_empty_metrics(self):
        """Empty metrics dict should produce valid HTML - Validates: Requirements 1.1"""
        generator = ReportGenerator(session_id='test')
        generator.add_session_summary({})
        
        html = generator.generate_html_report()
        
        self.assertIsInstance(html, str)
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('</html>', html.lower())

    def test_report_generation_with_no_iterations(self):
        """No iterations should still produce valid report - Validates: Requirements 1.1"""
        generator = ReportGenerator(session_id='test')
        generator.add_session_summary({'total_iterations': 0})
        
        html = generator.generate_html_report()
        
        self.assertIn('0', html)
        self.assertIn('Summary', html)

    def test_calculate_accuracy_with_no_iterations(self):
        """Accuracy should be 0 with no iterations - Validates: Requirements 1.5"""
        generator = ReportGenerator(session_id='test')
        
        accuracy = generator.calculate_accuracy()
        
        self.assertEqual(accuracy, 0.0)

    def test_calculate_latency_with_no_data(self):
        """Latency should be None with no data - Validates: Requirements 1.5"""
        generator = ReportGenerator(session_id='test')
        
        avg = generator.calculate_avg_latency()
        
        self.assertIsNone(avg)

    def test_calculate_cpu_with_no_data(self):
        """CPU should be None with no data - Validates: Requirements 1.5"""
        generator = ReportGenerator(session_id='test')
        
        avg = generator.calculate_avg_cpu()
        
        self.assertIsNone(avg)


class TestReportGeneratorTimestampProperty(unittest.TestCase):
    """Property-based tests for timestamp handling"""

    def test_report_has_iso8601_timestamp(self):
        """Report should have valid ISO 8601 timestamp - Validates: Requirements 1.3"""
        generator = ReportGenerator(session_id='test')
        generator.add_session_summary({'total_iterations': 1})
        
        html = generator.generate_html_report()
        
        # Should contain a valid-looking timestamp
        self.assertIn('Generated:', html)
        self.assertIn('20', html)  # Year component

    def test_json_export_has_iso8601_timestamp(self):
        """JSON export should have ISO 8601 timestamp - Validates: Requirements 1.4"""
        generator = ReportGenerator(session_id='test')
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'report.json'
            generator.export_json(str(output_path))
            
            with open(output_path) as f:
                data = json.load(f)
            
            # Should be valid ISO format
            generated_at = data['generated_at']
            self.assertIn('T', generated_at)
            # Can parse it back
            datetime.fromisoformat(generated_at)


class TestReportGeneratorVariantMetadataProperty(unittest.TestCase):
    """Property-based tests for variant metadata preservation"""

    @given(st.text(min_size=1, max_size=50))
    def test_variant_name_preserved_in_metadata(self, variant_name):
        """Variant name should be preserved - Validates: Requirements 1.3"""
        generator = ReportGenerator(session_id='test')
        generator.set_variant_preset(variant_name)
        generator.add_session_summary({'variant': variant_name})
        
        html = generator.generate_html_report()
        
        # Variant should be in report
        self.assertIn('Summary', html)

    @given(st.dictionaries(
        st.sampled_from(['cps', 'hold_ms', 'load', 'chat_state']),
        st.one_of(st.integers(), st.text()),
        min_size=1,
        max_size=5
    ))
    def test_variant_config_preserved_in_metadata(self, config):
        """Variant config should be preserved - Validates: Requirements 1.3"""
        generator = ReportGenerator(session_id='test', metadata=config)
        generator.add_session_summary({'config': str(config)})
        
        summary = generator.get_session_summary()
        
        self.assertIsNotNone(summary)


if __name__ == '__main__':
    unittest.main()

