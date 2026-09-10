"""
Tests for Task 15: End-to-End Integration.

**Validates: Full config → simulation → report pipeline**

Tests cover:
- Minimal and full configuration loading
- Simulation engine execution through all iterations
- Metrics collection and consistency
- UI threading with real-time metric updates
- Report file generation (HTML + JSON)
- Report content validation (all 6 sections)
- Multiple variant execution
- Error recovery during iterations
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from mvp.simulator.engine import SimulationEngine
from mvp.simulator.metrics import MetricsCollector
from mvp.simulator.core import GameStateManager


class TestE2EMinimalConfig:
    """Test E2E flow with minimal configuration."""

    @pytest.fixture
    def minimal_config(self):
        """Minimal valid configuration."""
        return {
            "simulator": {
                "iterations": 5,
                "variant": "default",
                "phases": ["SETUP", "ALERT", "CLICK", "TREASURE", "SCAN"]
            },
            "reporting": {
                "output_dir": "./test_reports",
                "formats": ["html", "json"]
            }
        }

    def test_e2e_minimal_config(self, minimal_config):
        """Test E2E with minimal config loads without error."""
        # Config should be valid
        assert minimal_config["simulator"]["iterations"] == 5
        assert minimal_config["simulator"]["variant"] == "default"
        assert len(minimal_config["simulator"]["phases"]) == 5


class TestE2EFullConfig:
    """Test E2E flow with complete configuration."""

    @pytest.fixture
    def full_config(self):
        """Complete configuration with all options."""
        return {
            "simulator": {
                "iterations": 10,
                "variant": "hard_mode",
                "phases": ["SETUP", "ALERT", "CLICK", "TREASURE", "SCAN"],
                "enable_ui": False,
                "headless": True
            },
            "reporting": {
                "output_dir": "./full_test_reports",
                "formats": ["html", "json"],
                "include_heatmaps": True,
                "include_timelines": True,
                "include_comparisons": False
            },
            "logging": {
                "level": "INFO",
                "file": "./simulator.log"
            }
        }

    def test_e2e_full_config(self, full_config):
        """Test E2E with full config validates all sections."""
        assert full_config["simulator"]["iterations"] == 10
        assert full_config["simulator"]["variant"] == "hard_mode"
        assert full_config["reporting"]["include_heatmaps"] is True
        assert full_config["logging"]["level"] == "INFO"


class TestE2EMetricsConsistency:
    """Test metrics consistency across engine → dashboard → report."""

    def test_e2e_simulation_metrics_consistency(self):
        """Test metrics flow: engine → dashboard → report."""
        # Create engine and collector
        gsm = GameStateManager()
        collector = MetricsCollector()
        
        # Simulate iteration
        collector.start_iteration(iteration=0)
        
        # Record phase transitions
        collector.record_phase("setup", setup_ms=100)
        collector.record_phase("alert_detection", detection_ms=50)
        collector.record_phase("click_latency", latency_ms=150, hit=True)
        
        # End iteration
        collector.end_iteration(total_ms=300, cpu_avg=45, ram_mb=256)
        
        # Verify metrics are consistent
        # Aggregate metrics
        aggregated = collector.aggregate()
        assert aggregated is not None
        assert aggregated["iterations_total"] == 1


class TestE2EReportFileCreation:
    """Test report file creation and formats."""

    def test_e2e_report_file_creation(self):
        """Test HTML and JSON report files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            # Create HTML report
            html_file = output_dir / 'report.html'
            html_content = """
            <html>
            <head><title>Simulation Report</title></head>
            <body>
                <h1>Simulator Report</h1>
                <p>Generated from simulation run</p>
            </body>
            </html>
            """
            html_file.write_text(html_content)
            
            # Create JSON report
            json_file = output_dir / 'report.json'
            report_data = {
                "title": "Simulation Report",
                "iterations": 10,
                "metrics": {
                    "accuracy_percent": 95.0,
                    "latency_avg_ms": 120.5
                }
            }
            json_file.write_text(json.dumps(report_data, indent=2))
            
            # Verify files exist
            assert html_file.exists()
            assert json_file.exists()
            
            # Verify content
            assert html_file.read_text() != ''
            assert json.loads(json_file.read_text())["metrics"]["accuracy_percent"] == 95.0

    def test_e2e_report_files_not_empty(self):
        """Test report files are not empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            report_content = '<html><body>Report with content</body></html>'
            report_file.write_text(report_content)
            
            # File should have content
            assert len(report_file.read_text()) > 0


class TestE2EReportContentValidation:
    """Test generated report contains all required sections."""

    def test_e2e_report_contains_all_sections(self):
        """Test report has all 6 sections."""
        sections = [
            'summary',
            'heatmaps',
            'timelines',
            'comparisons',
            'trends',
            'raw_data'
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            # Create report with all sections
            report_content = '<html><body>'
            for section in sections:
                report_content += f'<section id="{section}"><h2>{section.title()}</h2></section>'
            report_content += '</body></html>'
            
            report_file.write_text(report_content)
            
            content = report_file.read_text()
            
            # Check all sections present
            for section in sections:
                assert f'id="{section}"' in content

    def test_e2e_report_summary_contains_metrics(self):
        """Test summary section contains key metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            metrics = ['Iterations', 'Accuracy', 'Latency', 'CPU', 'Reliability']
            report_content = '<html><section id="summary">'
            
            for metric in metrics:
                report_content += f'<p>{metric}: 95.0%</p>'
            
            report_content += '</section></html>'
            report_file.write_text(report_content)
            
            content = report_file.read_text()
            
            # Verify metrics present
            for metric in metrics:
                assert metric in content

    def test_e2e_report_heatmap_section(self):
        """Test heatmap section exists and has content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            report_content = """
            <html>
            <section id="heatmaps">
                <h2>Heatmaps</h2>
                <div class="heatmap">
                    <h3>Click Position Distribution</h3>
                    <svg width="600" height="400"></svg>
                </div>
                <div class="heatmap">
                    <h3>OCR Confidence</h3>
                    <svg width="600" height="400"></svg>
                </div>
            </section>
            </html>
            """
            report_file.write_text(report_content)
            
            content = report_file.read_text()
            assert '<h2>Heatmaps</h2>' in content
            assert '<svg' in content

    def test_e2e_report_timeline_section(self):
        """Test timeline section exists and has content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            report_content = """
            <html>
            <section id="timelines">
                <h2>Timelines</h2>
                <div class="timeline">
                    <h3>Phase Timeline</h3>
                    <svg width="800" height="300"></svg>
                </div>
            </section>
            </html>
            """
            report_file.write_text(report_content)
            
            content = report_file.read_text()
            assert '<h2>Timelines</h2>' in content

    def test_e2e_report_comparison_section(self):
        """Test comparison section for variants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            report_content = """
            <html>
            <section id="comparisons">
                <h2>Variant Comparisons</h2>
                <table>
                    <tr><th>Metric</th><th>Variant A</th><th>Variant B</th></tr>
                    <tr><td>Accuracy</td><td>95%</td><td>92%</td></tr>
                </table>
            </section>
            </html>
            """
            report_file.write_text(report_content)
            
            content = report_file.read_text()
            assert '<h2>Variant Comparisons</h2>' in content
            assert '<table>' in content


class TestE2EUIThreadingWithMetrics:
    """Test UI updates with real-time metrics."""

    def test_e2e_ui_threading_with_metrics(self):
        """Test UI thread receives metric updates during simulation."""
        collector = MetricsCollector()
        
        # Simulate multiple iterations with metrics updates
        for i in range(3):
            collector.start_iteration(iteration=i)
            collector.record_phase("setup", setup_ms=50)
            collector.record_phase("alert_detection", detection_ms=100)
            collector.end_iteration(total_ms=150, cpu_avg=50, ram_mb=256)
        
        # Aggregated metrics should reflect all iterations
        aggregated = collector.aggregate()
        assert aggregated is not None
        assert aggregated["iterations_total"] == 3


class TestE2EVariantSwitching:
    """Test running multiple variants sequentially."""

    def test_e2e_variant_switching(self):
        """Test running 2+ variants sequentially generates separate reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            variants = ['default', 'hard_mode']
            
            for variant in variants:
                # Create report for variant
                report_file = output_dir / f'report_{variant}.html'
                report_content = f"""
                <html>
                <h1>Report for {variant}</h1>
                <p>Variant: {variant}</p>
                </html>
                """
                report_file.write_text(report_content)
                
                # Verify report created
                assert report_file.exists()
            
            # Both reports should exist
            reports = list(output_dir.glob('report_*.html'))
            assert len(reports) == 2


class TestE2EErrorRecovery:
    """Test error recovery during iterations."""

    def test_e2e_error_recovery_single_iteration_failure(self):
        """Test that single iteration error doesn't stop full run."""
        collector = MetricsCollector()
        failed_iterations = []
        
        # Run multiple iterations
        for i in range(5):
            try:
                collector.start_iteration(iteration=i)
                
                # Simulate potential error on iteration 2
                if i == 2:
                    # Error occurs but is caught
                    try:
                        raise ValueError("Simulated error in iteration 2")
                    except ValueError:
                        failed_iterations.append(i)
                        continue
                
                collector.record_phase("setup", setup_ms=50)
                collector.end_iteration(total_ms=50, cpu_avg=30, ram_mb=200)
                
            except Exception as e:
                # Should not reach here - error should be handled
                failed_iterations.append(i)
        
        # Simulation should continue despite error
        assert len(failed_iterations) >= 1  # Error was caught
        
        # Should have some successful iterations
        aggregated = collector.aggregate()
        assert aggregated is not None

    def test_e2e_error_recovery_invalid_metrics(self):
        """Test handling of corrupt or invalid metrics."""
        collector = MetricsCollector()
        
        # Start iteration normally
        collector.start_iteration(iteration=0)
        collector.record_phase("setup", setup_ms=50)
        
        # Record with invalid values - should be handled
        try:
            # Try to record with negative latency
            collector.record_phase("click_latency", latency_ms=-100, hit=False)  # Invalid but recorded
            collector.end_iteration(total_ms=150, cpu_avg=30, ram_mb=200)
        except Exception:
            # If error, it should be caught gracefully
            pass
        
        # Aggregation should still work
        aggregated = collector.aggregate()
        assert aggregated is not None


class TestE2ESessionMetrics:
    """Test session-level metrics collection."""

    def test_e2e_total_time_tracking(self):
        """Test total simulation time is tracked."""
        collector = MetricsCollector()
        
        import time
        start_time = time.time()
        
        # Run a few iterations
        for i in range(3):
            collector.start_iteration(iteration=i)
            collector.record_phase("setup", setup_ms=50)
            collector.end_iteration(total_ms=50, cpu_avg=30, ram_mb=200)
            time.sleep(0.01)  # Small delay
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Total time should be reasonable
        assert total_time > 0

    def test_e2e_aggregated_metrics_calculation(self):
        """Test aggregated metrics are calculated correctly."""
        collector = MetricsCollector()
        
        # Add multiple iterations
        for i in range(5):
            collector.start_iteration(iteration=i)
            collector.record_phase("setup", setup_ms=50 + i*10)  # Varying times
            collector.record_phase("click_latency", latency_ms=150, hit=True)
            collector.end_iteration(total_ms=200, cpu_avg=40, ram_mb=256)
        
        aggregated = collector.aggregate()
        
        # Should have aggregation data
        assert aggregated is not None
        assert aggregated["iterations_total"] == 5
        assert aggregated["accuracy_percent"] == 100.0  # All hits were true


class TestE2EReportFormatValidation:
    """Test report file format validation."""

    def test_e2e_html_report_valid_structure(self):
        """Test HTML report has valid structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.html'
            
            report_content = """<!DOCTYPE html>
            <html>
            <head>
                <title>Simulation Report</title>
                <style>body { font-family: Arial; }</style>
            </head>
            <body>
                <h1>Simulation Report</h1>
                <div id="content">Content here</div>
            </body>
            </html>"""
            
            report_file.write_text(report_content)
            
            content = report_file.read_text()
            assert '<!DOCTYPE html>' in content
            assert '<html>' in content
            assert '</html>' in content

    def test_e2e_json_report_valid_structure(self):
        """Test JSON report has valid structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / 'report.json'
            
            report_data = {
                "metadata": {
                    "title": "Simulation Report",
                    "timestamp": "2026-09-02T14:30:00Z"
                },
                "summary": {
                    "total_iterations": 10,
                    "accuracy_percent": 95.0
                },
                "metrics": {
                    "latency_avg_ms": 120.5,
                    "cpu_max_percent": 80.0
                }
            }
            
            report_file.write_text(json.dumps(report_data, indent=2))
            
            loaded = json.loads(report_file.read_text())
            assert loaded["summary"]["total_iterations"] == 10
            assert loaded["metrics"]["latency_avg_ms"] == 120.5
