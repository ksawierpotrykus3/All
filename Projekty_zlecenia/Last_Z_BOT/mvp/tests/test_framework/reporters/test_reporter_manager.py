"""Tests for reporter manager integration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import gc

import pytest

from mvp.tests.test_framework.metrics import (
    CPULoadClass,
    RunMetrics,
    TestSuiteResult,
)
from mvp.tests.test_framework.reporters.reporter_manager import ReporterManager
from mvp.tests.test_framework.scenarios import Scenario, MonitorConfig


@pytest.fixture
def temp_reports_dir():
    """Create temporary directory for reports."""
    # Use a non-temporary directory to avoid cleanup issues
    import uuid
    tmpdir = Path(f"./tmp_reports_{uuid.uuid4().hex[:8]}")
    tmpdir.mkdir(parents=True, exist_ok=True)
    yield tmpdir
    # Manual cleanup
    import shutil
    gc.collect()  # Force garbage collection to close DB connections
    if tmpdir.exists():
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass  # Ignore cleanup errors in tests


@pytest.fixture
def reporter_manager(temp_reports_dir):
    """Create reporter manager instance."""
    return ReporterManager(output_dir=temp_reports_dir)


@pytest.fixture
def mock_scenario():
    """Create mock scenario."""
    scenario = MagicMock(spec=Scenario)
    scenario.window_width = 1024
    scenario.window_height = 768
    scenario.window_x = 100
    scenario.window_y = 200
    scenario.window_position = (100, 200)
    scenario.window_size = (1024, 768)
    scenario.viewport_clip = (0, 0, 1024, 768)
    scenario.dpi_scaling = 1.0
    scenario.chat_initial_state = "CLOSED"
    scenario.timer_seconds = 300
    scenario.timer_jitter_ms = 0
    scenario.event_injection_delay_ms = 0
    scenario.has_glitch = False
    scenario.dpi = 96
    scenario.monitor_count = 1
    scenario.is_clipped = False
    scenario.monitors = [MagicMock(spec=MonitorConfig, id=0, offset_x=0, width=1920, dpi=96)]
    return scenario


@pytest.fixture
def sample_run_metrics():
    """Create sample run metrics."""
    return RunMetrics(
        run_id=1,
        scenario_id="test_scenario_1",
        passed=True,
        click_count=20,
        click_avg_deviation_px=5.2,
        ocr_detections=5,
        ocr_precision=0.85,
        spam_click_count=266,
        spam_click_duration_s=7.0,
        spam_cps=38.0,
        cpu_time_ms=1200.0,
        gpu_time_ms=0.0,
        syscall_time_ms=50.0,
        memory_mb=145.0,
        cpu_load_class=CPULoadClass.MEDIUM,
        duration_ms=3400.0,
    )


@pytest.fixture
def sample_suite_result():
    """Create sample suite result."""
    return TestSuiteResult(
        total_runs=5,
        passed_runs=4,
        failed_runs=1,
        runs=[],
        pass_rate=0.8,
        cpu_load_distribution={"IDLE": 2, "LOW": 2, "MEDIUM": 1},
        bottleneck_summary=[],
        avg_memory_mb=150.0,
        peak_memory_mb=200.0,
        total_duration_s=17.0,
    )


class TestReporterManager:
    """Test reporter manager functionality."""

    def test_init_creates_output_directories(self, temp_reports_dir):
        """Test that init creates necessary directories."""
        manager = ReporterManager(output_dir=temp_reports_dir)
        
        assert (temp_reports_dir / "console").exists()
        assert (temp_reports_dir / "html").exists()
        assert manager.output_dir == temp_reports_dir

    def test_add_run_coordinates_all_reporters(
        self, reporter_manager, mock_scenario, sample_run_metrics, capsys
    ):
        """Test that add_run coordinates all three reporters."""
        # Capture print output for console reporter
        reporter_manager.add_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        
        # Verify console reporter output (printed)
        assert "Run #1" in captured.out
        assert "1024x768" in captured.out
        
        # Verify runs added to HTML reporter
        assert len(reporter_manager.html_reporter.runs) == 1
        assert reporter_manager.html_reporter.runs[0].run_id == 1
        
        # Verify database was created
        assert reporter_manager.sqlite_reporter.db_path.exists()

    def test_add_multiple_runs(
        self, reporter_manager, mock_scenario, sample_run_metrics
    ):
        """Test adding multiple runs."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"scenario_{i}",
                passed=i < 2,  # First 2 pass
                click_count=20,
                cpu_time_ms=1200.0,
                memory_mb=145.0,
                cpu_load_class=CPULoadClass.MEDIUM,
                duration_ms=3400.0,
            )
            reporter_manager.add_run(i + 1, mock_scenario, metrics)
        
        # Check HTML reporter accumulated all runs
        assert len(reporter_manager.html_reporter.runs) == 3

    def test_finalize_reports_creates_all_outputs(
        self, reporter_manager, mock_scenario, sample_run_metrics, sample_suite_result
    ):
        """Test that finalize_reports creates all three report types."""
        # Add a run
        reporter_manager.add_run(1, mock_scenario, sample_run_metrics)
        
        # Finalize
        report_paths = reporter_manager.finalize_reports(sample_suite_result)
        
        # Verify all report types
        assert "console" in report_paths
        assert "html" in report_paths
        assert "sqlite" in report_paths
        
        # Verify console report file exists and has content
        console_path = report_paths["console"]
        assert console_path.exists()
        content = console_path.read_text()
        assert "TEST SUITE REPORT" in content
        assert "AGGREGATE STATISTICS" in content
        
        # Verify HTML report file exists
        html_path = report_paths["html"]
        assert html_path.exists()
        assert html_path.suffix == ".html"
        
        # Verify SQLite database exists
        db_path = report_paths["sqlite"]
        assert db_path.exists()
        assert db_path.suffix == ".db"

    def test_get_db_path(self, reporter_manager):
        """Test get_db_path returns correct path."""
        db_path = reporter_manager.get_db_path()
        
        assert db_path.exists()
        assert db_path.suffix == ".db"
        assert "_" in db_path.name  # Contains timestamp

    def test_get_example_queries(self, reporter_manager):
        """Test get_example_queries returns query dictionary."""
        queries = reporter_manager.get_example_queries()
        
        assert isinstance(queries, dict)
        assert len(queries) > 0
        
        # Should have some common query types
        query_names = list(queries.keys())
        assert any("regression" in name.lower() for name in query_names)
        assert any("cpu" in name.lower() for name in query_names)

    def test_finalize_prints_console_report(
        self, reporter_manager, mock_scenario, sample_run_metrics, sample_suite_result, capsys
    ):
        """Test that finalize_reports prints console report."""
        reporter_manager.add_run(1, mock_scenario, sample_run_metrics)
        reporter_manager.finalize_reports(sample_suite_result)
        
        captured = capsys.readouterr()
        
        # Check for report output
        assert "Console report saved to" in captured.out
        assert "HTML report saved to" in captured.out
        assert "SQLite database saved to" in captured.out
        assert "TEST SUITE REPORT" in captured.out

    def test_timestamp_format_in_filenames(self, reporter_manager):
        """Test that timestamp is included in filenames."""
        # Timestamp should be YYYYMMDD_HHMMSS format
        assert len(reporter_manager.timestamp) == 15  # 8 + 1 + 6 chars
        assert "_" in reporter_manager.timestamp
