"""Tests for console reporter."""

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from mvp.tests.test_framework.metrics import (
    CPULoadClass,
    Deviation,
    HotSpot,
    RunMetrics,
    TestSuiteResult,
)
from mvp.tests.test_framework.reporters.console_reporter import ConsoleReporter
from mvp.tests.test_framework.scenarios import Scenario, ChatState, MonitorConfig


@pytest.fixture
def console_reporter():
    """Create a console reporter instance."""
    return ConsoleReporter()


@pytest.fixture
def mock_scenario():
    """Create a mock scenario."""
    scenario = MagicMock(spec=Scenario)
    scenario.window_width = 1024
    scenario.window_height = 768
    scenario.window_x = 100
    scenario.window_y = 200
    scenario.timer_seconds = 300
    scenario.dpi = 96
    scenario.monitors = [MagicMock(spec=MonitorConfig, id=0, offset_x=0, width=1920, dpi=96)]
    return scenario


@pytest.fixture
def sample_run_metrics():
    """Create sample RunMetrics with typical values."""
    return RunMetrics(
        run_id=1,
        scenario_id="test_scenario_1",
        passed=True,
        click_count=20,
        click_avg_deviation_px=5.2,
        ocr_detections=5,
        ocr_precision=0.85,
        macro_step_latency_ms={"WAIT_FOR_TIMER": 300500.0, "CLICK": 50.0},
        spam_click_count=266,
        spam_click_duration_s=7.0,
        spam_cps=38.0,
        cpu_time_ms=1200.0,
        gpu_time_ms=0.0,
        syscall_time_ms=50.0,
        memory_mb=145.0,
        cpu_load_class=CPULoadClass.MEDIUM,
        hot_spots=[
            HotSpot(function_name="bot.clicker.click_at", cpu_time_ms=42.0, percent=35.0),
            HotSpot(function_name="bot.capture.get_frame", cpu_time_ms=28.0, percent=23.0),
            HotSpot(function_name="bot.ocr.detect", cpu_time_ms=22.0, percent=18.0),
        ],
        deviations=[],
        duration_ms=3400.0,
    )


class TestConsoleReporterRunReport:
    """Test report_run method."""

    def test_report_run_basic_pass(self, console_reporter, mock_scenario, sample_run_metrics, capsys):
        """Test basic run report with passed metrics."""
        console_reporter.report_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        assert "Run #1: 1024x768 @ (100,200)" in captured.out
        assert "[Monitor 0, 96 DPI]" in captured.out
        assert "Timer=300s" in captured.out
        assert "✓ PASS" in captured.out
        assert "Clicks: 20" in captured.out
        assert "OCR: 85% precision" in captured.out
        assert "Spam: 38.0 CPS" in captured.out
        assert "Memory: 145MB" in captured.out

    def test_report_run_failed(self, console_reporter, mock_scenario, sample_run_metrics, capsys):
        """Test run report with failed result."""
        sample_run_metrics.passed = False
        console_reporter.report_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        assert "✗ FAIL" in captured.out

    def test_report_run_with_deviations(self, console_reporter, mock_scenario, sample_run_metrics, capsys):
        """Test run report with deviations."""
        sample_run_metrics.deviations = [
            Deviation(
                type="cpu_high",
                severity="error",
                value=75.0,
                threshold=70.0,
                message="CPU usage 75.0% exceeds threshold 70%",
            ),
            Deviation(
                type="ocr_precision",
                severity="warning",
                value=0.60,
                threshold=0.80,
                message="OCR precision 60% below threshold 80%",
            ),
        ]
        console_reporter.report_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        assert "Deviations:" in captured.out
        assert "cpu_high" in captured.out
        assert "ocr_precision" in captured.out

    def test_report_run_high_cpu_shows_hot_spots(self, console_reporter, mock_scenario, sample_run_metrics, capsys):
        """Test that hot-spots are shown when CPU load is HIGH."""
        sample_run_metrics.cpu_load_class = CPULoadClass.HIGH
        console_reporter.report_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        assert "Hot-spots:" in captured.out
        assert "bot.clicker.click_at" in captured.out
        assert "42.0ms" in captured.out
        assert "35.0%" in captured.out

    def test_report_run_critical_cpu_shows_hot_spots(self, console_reporter, mock_scenario, sample_run_metrics, capsys):
        """Test that hot-spots are shown when CPU load is CRITICAL."""
        sample_run_metrics.cpu_load_class = CPULoadClass.CRITICAL
        console_reporter.report_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        assert "Hot-spots:" in captured.out
        assert "bot.clicker.click_at" in captured.out

    def test_report_run_low_cpu_no_hot_spots(self, console_reporter, mock_scenario, sample_run_metrics, capsys):
        """Test that hot-spots are NOT shown for LOW CPU."""
        sample_run_metrics.cpu_load_class = CPULoadClass.LOW
        console_reporter.report_run(1, mock_scenario, sample_run_metrics)
        
        captured = capsys.readouterr()
        assert "Hot-spots:" not in captured.out

    def test_report_run_no_clicks_no_ocr(self, console_reporter, mock_scenario, capsys):
        """Test run report with no clicks or OCR detections."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test",
            passed=True,
            click_count=0,
            ocr_detections=0,
            cpu_load_class=CPULoadClass.IDLE,
            memory_mb=100.0,
        )
        console_reporter.report_run(1, mock_scenario, metrics)
        
        captured = capsys.readouterr()
        assert "✓ PASS" in captured.out
        # Should not print click/OCR lines if count is 0
        assert "Clicks: 0" not in captured.out
        assert "OCR: " not in captured.out

    def test_report_run_with_multiple_monitors(self, console_reporter, capsys):
        """Test run report with multi-monitor scenario."""
        scenario = MagicMock(spec=Scenario)
        scenario.window_width = 1024
        scenario.window_height = 768
        scenario.window_x = 2000  # On second monitor
        scenario.window_y = 100
        scenario.timer_seconds = 30
        scenario.dpi = 96
        scenario.monitors = [
            MagicMock(spec=MonitorConfig, id=0, offset_x=0, width=1920, dpi=96),
            MagicMock(spec=MonitorConfig, id=1, offset_x=1920, width=1920, dpi=96),
        ]
        
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_multi",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=120.0,
        )
        console_reporter.report_run(1, scenario, metrics)
        
        captured = capsys.readouterr()
        assert "[Monitor 1, 96 DPI]" in captured.out
        assert "Timer=30s" in captured.out


class TestConsoleReporterSuiteSummary:
    """Test report_suite method."""

    def test_report_suite_basic_summary(self, console_reporter, capsys):
        """Test basic suite summary."""
        suite = TestSuiteResult(
            total_runs=10,
            passed_runs=9,
            failed_runs=1,
            pass_rate=0.90,
            avg_memory_mb=150.0,
            peak_memory_mb=250.0,
            cpu_load_distribution={"LOW": 4, "MEDIUM": 4, "HIGH": 2},
            bottleneck_summary=["OCR detection is slow"],
        )
        suite.runs = [
            RunMetrics(run_id=i, scenario_id=f"s{i}", passed=i < 9, cpu_load_class=CPULoadClass.MEDIUM, memory_mb=150.0)
            for i in range(10)
        ]
        
        console_reporter.report_suite(suite)
        
        captured = capsys.readouterr()
        assert "SUITE SUMMARY" in captured.out
        assert "Total runs: 10" in captured.out
        assert "Passed: 9" in captured.out
        assert "Failed: 1" in captured.out
        assert "Pass rate: 90.0%" in captured.out
        assert "Average: 150.0MB" in captured.out
        assert "Peak: 250.0MB" in captured.out

    def test_report_suite_cpu_distribution(self, console_reporter, capsys):
        """Test CPU load distribution in suite summary."""
        suite = TestSuiteResult(total_runs=10, passed_runs=10)
        suite.runs = [
            RunMetrics(run_id=i, scenario_id=f"s{i}", passed=True, cpu_load_class=CPULoadClass.LOW if i < 3 else CPULoadClass.MEDIUM, memory_mb=100.0)
            for i in range(10)
        ]
        
        console_reporter.report_suite(suite)
        
        captured = capsys.readouterr()
        assert "CPU Load Distribution:" in captured.out
        assert "LOW" in captured.out
        assert "MEDIUM" in captured.out

    def test_report_suite_aggregate_hot_spots(self, console_reporter, capsys):
        """Test aggregated hot-spots across runs."""
        suite = TestSuiteResult(total_runs=2, passed_runs=2)
        
        # Run 1: HIGH CPU with hot-spots
        metrics1 = RunMetrics(
            run_id=1,
            scenario_id="s1",
            passed=True,
            cpu_load_class=CPULoadClass.HIGH,
            memory_mb=100.0,
            hot_spots=[
                HotSpot(function_name="func_a", cpu_time_ms=50.0, percent=40.0),
                HotSpot(function_name="func_b", cpu_time_ms=30.0, percent=24.0),
            ],
        )
        
        # Run 2: CRITICAL CPU with hot-spots
        metrics2 = RunMetrics(
            run_id=2,
            scenario_id="s2",
            passed=True,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=120.0,
            hot_spots=[
                HotSpot(function_name="func_a", cpu_time_ms=60.0, percent=48.0),
                HotSpot(function_name="func_c", cpu_time_ms=20.0, percent=16.0),
            ],
        )
        
        suite.runs = [metrics1, metrics2]
        
        console_reporter.report_suite(suite)
        
        captured = capsys.readouterr()
        assert "Aggregate Hot-spots" in captured.out
        assert "func_a" in captured.out  # Should appear (total: 110ms)
        assert "110.0ms" in captured.out or "110" in captured.out  # Aggregated value

    def test_report_suite_no_hot_spots(self, console_reporter, capsys):
        """Test suite summary with no hot-spots."""
        suite = TestSuiteResult(total_runs=5, passed_runs=5)
        suite.runs = [
            RunMetrics(
                run_id=i,
                scenario_id=f"s{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,  # Low CPU, no hot-spots shown
                memory_mb=100.0,
            )
            for i in range(5)
        ]
        
        console_reporter.report_suite(suite)
        
        captured = capsys.readouterr()
        assert "Aggregate Hot-spots" in captured.out
        assert "(None detected)" in captured.out

    def test_report_suite_bottleneck_summary(self, console_reporter, capsys):
        """Test bottleneck summary in suite report."""
        suite = TestSuiteResult(
            total_runs=5,
            passed_runs=4,
            bottleneck_summary=[
                "CPU bottleneck in bot.ocr.detect (avg 150ms per call)",
                "Memory spike: 450MB at run #3",
            ],
        )
        suite.runs = [
            RunMetrics(run_id=i, scenario_id=f"s{i}", passed=True, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0)
            for i in range(5)
        ]
        
        console_reporter.report_suite(suite)
        
        captured = capsys.readouterr()
        assert "Bottleneck Summary:" in captured.out
        assert "bot.ocr.detect" in captured.out
        assert "Memory spike" in captured.out


class TestConsoleReporterFormatting:
    """Test internal formatting methods."""

    def test_format_header_standard(self, console_reporter, mock_scenario):
        """Test header formatting."""
        header = console_reporter._format_header(1, mock_scenario, MagicMock())
        
        assert "Run #1:" in header
        assert "1024x768" in header
        assert "(100,200)" in header
        assert "[Monitor 0, 96 DPI]" in header
        assert "Timer=300s" in header

    def test_format_header_small_window(self, console_reporter):
        """Test header formatting with small clipped window."""
        scenario = MagicMock(spec=Scenario)
        scenario.window_width = 640
        scenario.window_height = 480
        scenario.window_x = 0
        scenario.window_y = 0
        scenario.timer_seconds = 5
        scenario.dpi = 120
        scenario.monitors = [MagicMock(spec=MonitorConfig, id=0, offset_x=0, width=1920, dpi=120)]
        
        header = console_reporter._format_header(5, scenario, MagicMock())
        
        assert "Run #5:" in header
        assert "640x480" in header
        assert "(0,0)" in header
        assert "Timer=5s" in header

    def test_calculate_cpu_distribution(self, console_reporter):
        """Test CPU distribution calculation."""
        suite = TestSuiteResult(total_runs=10)
        suite.runs = []
        
        # Create runs with different CPU classes
        for i in range(10):
            cpu_class = [CPULoadClass.IDLE, CPULoadClass.LOW, CPULoadClass.MEDIUM, CPULoadClass.HIGH, CPULoadClass.CRITICAL][i % 5]
            suite.runs.append(
                RunMetrics(
                    run_id=i,
                    scenario_id=f"s{i}",
                    passed=True,
                    cpu_load_class=cpu_class,
                    memory_mb=100.0,
                )
            )
        
        distribution = console_reporter._calculate_cpu_distribution(suite)
        
        assert distribution["IDLE"] == 2
        assert distribution["LOW"] == 2
        assert distribution["MEDIUM"] == 2
        assert distribution["HIGH"] == 2
        assert distribution["CRITICAL"] == 2

    def test_aggregate_hot_spots_top_10(self, console_reporter):
        """Test that only top 10 hot-spots are returned."""
        suite = TestSuiteResult(total_runs=1)
        
        # Create metrics with 15 hot-spots
        hot_spots = [
            HotSpot(function_name=f"func_{i:02d}", cpu_time_ms=100.0 - i * 5, percent=50.0 - i * 2.5)
            for i in range(15)
        ]
        
        metrics = RunMetrics(
            run_id=1,
            scenario_id="s1",
            passed=True,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=100.0,
            hot_spots=hot_spots,
        )
        
        suite.runs = [metrics]
        
        aggregated = console_reporter._aggregate_hot_spots(suite)
        
        # Should return top 10 only
        assert len(aggregated) <= 10
        # Should be sorted by CPU time descending
        assert aggregated[0][1] >= aggregated[-1][1]

    def test_aggregate_hot_spots_filters_by_cpu_class(self, console_reporter):
        """Test that aggregate hot-spots only include HIGH/CRITICAL CPU runs."""
        suite = TestSuiteResult(total_runs=2)
        
        # Run 1: LOW CPU (should be excluded)
        metrics1 = RunMetrics(
            run_id=1,
            scenario_id="s1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            hot_spots=[HotSpot(function_name="func_low", cpu_time_ms=50.0, percent=40.0)],
        )
        
        # Run 2: HIGH CPU (should be included)
        metrics2 = RunMetrics(
            run_id=2,
            scenario_id="s2",
            passed=True,
            cpu_load_class=CPULoadClass.HIGH,
            memory_mb=100.0,
            hot_spots=[HotSpot(function_name="func_high", cpu_time_ms=75.0, percent=60.0)],
        )
        
        suite.runs = [metrics1, metrics2]
        
        aggregated = console_reporter._aggregate_hot_spots(suite)
        
        # Should only include func_high
        func_names = [name for name, _, _, _ in aggregated]
        assert "func_high" in func_names
        assert "func_low" not in func_names


class TestConsoleReporterEdgeCases:
    """Test edge cases."""

    def test_empty_suite_result(self, console_reporter, capsys):
        """Test suite report with empty suite."""
        suite = TestSuiteResult(total_runs=0, passed_runs=0)
        suite.runs = []
        
        console_reporter.report_suite(suite)
        
        captured = capsys.readouterr()
        assert "SUITE SUMMARY" in captured.out
        assert "Total runs: 0" in captured.out
        assert "Pass rate: 0.0%" in captured.out

    def test_run_with_no_metrics(self, console_reporter, mock_scenario, capsys):
        """Test run report with minimal metrics."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test",
            passed=True,
            cpu_load_class=CPULoadClass.IDLE,
        )
        
        console_reporter.report_run(1, mock_scenario, metrics)
        
        captured = capsys.readouterr()
        assert "✓ PASS" in captured.out
        assert "Run #1:" in captured.out

    def test_run_with_very_high_cpu(self, console_reporter, mock_scenario, capsys):
        """Test run with very high CPU and many hot-spots."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test",
            passed=False,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=500.0,
            hot_spots=[
                HotSpot(function_name=f"func_{i}", cpu_time_ms=100.0 - i * 5, percent=80.0 - i * 5)
                for i in range(20)
            ],
            deviations=[
                Deviation(
                    type="cpu_high",
                    severity="error",
                    value=95.0,
                    threshold=70.0,
                    message="Critical CPU usage",
                )
            ],
        )
        
        console_reporter.report_run(1, mock_scenario, metrics)
        
        captured = capsys.readouterr()
        assert "✗ FAIL" in captured.out
        assert "CRITICAL" in captured.out
        assert "Hot-spots:" in captured.out
        assert "Deviations:" in captured.out


class TestConsoleReporterFormatOutput:
    """Test format_output method."""

    def test_format_output_returns_string(self, console_reporter):
        """Test format_output returns a string."""
        suite = TestSuiteResult(total_runs=1, passed_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="s1",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
            )
        ]
        
        output = console_reporter.format_output(suite)
        
        assert isinstance(output, str)
        assert len(output) > 0

    def test_format_output_contains_table_headers(self, console_reporter):
        """Test format_output includes table headers."""
        suite = TestSuiteResult(total_runs=1, passed_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
            )
        ]
        
        output = console_reporter.format_output(suite)
        
        assert "#" in output
        assert "Status" in output
        assert "CPU" in output
        assert "Scenario" in output

    def test_format_output_shows_pass_fail_status(self, console_reporter):
        """Test format_output displays pass/fail correctly."""
        suite = TestSuiteResult(total_runs=2, passed_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
            ),
            RunMetrics(
                run_id=2,
                scenario_id="test2",
                passed=False,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=150.0,
                duration_ms=3000.0,
            ),
        ]
        
        output = console_reporter.format_output(suite)
        
        assert "✓" in output
        assert "✗" in output

    def test_format_output_flags_anomalies_with_warning(self, console_reporter):
        """Test format_output flags anomalies with ⚠️."""
        suite = TestSuiteResult(total_runs=1, passed_runs=0)
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=False,
            cpu_load_class=CPULoadClass.HIGH,
            memory_mb=100.0,
            duration_ms=3000.0,
            deviations=[
                Deviation("cpu_high", "error", 75.0, 70.0, "CPU high"),
            ],
        )
        suite.runs = [metrics]
        
        output = console_reporter.format_output(suite)
        
        assert "⚠️" in output

    def test_format_output_empty_suite(self, console_reporter):
        """Test format_output with empty suite."""
        suite = TestSuiteResult(total_runs=0)
        suite.runs = []
        
        output = console_reporter.format_output(suite)
        
        assert "No runs" in output or output == "No runs to display."

    def test_format_output_metrics_displayed(self, console_reporter):
        """Test format_output includes key metrics."""
        suite = TestSuiteResult(total_runs=1, passed_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=True,
                click_count=20,
                ocr_detections=5,
                ocr_precision=0.90,
                spam_cps=38.0,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=145.0,
                duration_ms=3000.0,
            )
        ]
        
        output = console_reporter.format_output(suite)
        
        # Should contain metrics values
        assert "90%" in output or "0.9" in output
        assert "20" in output  # click count
        assert "145" in output  # memory


class TestConsoleReporterDetectBottlenecks:
    """Test detect_bottlenecks method."""

    def test_detect_bottlenecks_no_issues(self, console_reporter):
        """Test detect_bottlenecks with no bottlenecks."""
        suite = TestSuiteResult(total_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                reaction_latency_ms=50.0,
                cpu_time_ms=500.0,
                click_avg_deviation_px=20.0,
            )
        ]
        
        report = console_reporter.detect_bottlenecks(suite)
        
        assert "✅" in report or "No bottlenecks" in report

    def test_detect_bottlenecks_detects_cpu_spikes(self, console_reporter):
        """Test detect_bottlenecks detects CPU > 70%."""
        suite = TestSuiteResult(total_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=False,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
                duration_ms=3000.0,
                cpu_time_ms=2500.0,  # 83% CPU
                reaction_latency_ms=50.0,
                click_avg_deviation_px=20.0,
            )
        ]
        
        report = console_reporter.detect_bottlenecks(suite)
        
        assert "CPU SPIKES" in report or "🔴" in report

    def test_detect_bottlenecks_detects_timing_issues(self, console_reporter):
        """Test detect_bottlenecks detects reaction latency > 100ms."""
        suite = TestSuiteResult(total_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=False,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                cpu_time_ms=500.0,
                reaction_latency_ms=150.0,  # > 100ms
                click_avg_deviation_px=20.0,
            )
        ]
        
        report = console_reporter.detect_bottlenecks(suite)
        
        assert "TIMING" in report or "⏱️" in report or "latency" in report

    def test_detect_bottlenecks_detects_accuracy_issues(self, console_reporter):
        """Test detect_bottlenecks detects click deviation > 100px."""
        suite = TestSuiteResult(total_runs=1)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=False,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                cpu_time_ms=500.0,
                reaction_latency_ms=50.0,
                click_count=10,
                click_avg_deviation_px=120.0,  # > 100px
            )
        ]
        
        report = console_reporter.detect_bottlenecks(suite)
        
        assert "ACCURACY" in report or "📊" in report or "deviation" in report

    def test_detect_bottlenecks_multiple_issues(self, console_reporter):
        """Test detect_bottlenecks with multiple types of issues."""
        suite = TestSuiteResult(total_runs=2)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=False,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
                duration_ms=3000.0,
                cpu_time_ms=2500.0,  # CPU spike
                reaction_latency_ms=50.0,
                click_avg_deviation_px=20.0,
            ),
            RunMetrics(
                run_id=2,
                scenario_id="test2",
                passed=False,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                cpu_time_ms=500.0,
                reaction_latency_ms=150.0,  # Timing issue
                click_avg_deviation_px=20.0,
            ),
        ]
        
        report = console_reporter.detect_bottlenecks(suite)
        
        # Should detect at least one type of bottleneck
        has_issue = "CPU SPIKES" in report or "TIMING" in report or "ACCURACY" in report
        assert has_issue


class TestConsoleReporterErrorSummary:
    """Test format_error_summary method."""

    def test_format_error_summary_no_errors(self, console_reporter):
        """Test format_error_summary with all passing runs."""
        suite = TestSuiteResult(total_runs=2, passed_runs=2)
        suite.runs = [
            RunMetrics(run_id=1, scenario_id="test1", passed=True, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0),
            RunMetrics(run_id=2, scenario_id="test2", passed=True, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0),
        ]
        
        report = console_reporter.format_error_summary(suite)
        
        assert "✅" in report or "All runs passed" in report

    def test_format_error_summary_categorizes_cpu_errors(self, console_reporter):
        """Test format_error_summary categorizes CPU errors."""
        suite = TestSuiteResult(total_runs=1, failed_runs=1)
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=False,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=100.0,
            duration_ms=3000.0,
            deviations=[
                Deviation("cpu_high", "error", 75.0, 70.0, "CPU usage high"),
            ],
        )
        suite.runs = [metrics]
        
        report = console_reporter.format_error_summary(suite)
        
        assert "❌" in report or "ERROR" in report
        assert "CPU" in report or "🔴" in report

    def test_format_error_summary_categorizes_ocr_errors(self, console_reporter):
        """Test format_error_summary categorizes OCR errors."""
        suite = TestSuiteResult(total_runs=1, failed_runs=1)
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
            deviations=[
                Deviation("ocr_precision", "warning", 0.65, 0.80, "OCR precision low"),
            ],
        )
        suite.runs = [metrics]
        
        report = console_reporter.format_error_summary(suite)
        
        assert "OCR" in report or "📖" in report

    def test_format_error_summary_shows_error_count(self, console_reporter):
        """Test format_error_summary shows failed run count."""
        suite = TestSuiteResult(total_runs=5, failed_runs=3)
        suite.runs = [
            RunMetrics(run_id=1, scenario_id="test1", passed=False, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0, deviations=[]),
            RunMetrics(run_id=2, scenario_id="test2", passed=True, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0),
            RunMetrics(run_id=3, scenario_id="test3", passed=False, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0, deviations=[]),
            RunMetrics(run_id=4, scenario_id="test4", passed=True, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0),
            RunMetrics(run_id=5, scenario_id="test5", passed=False, cpu_load_class=CPULoadClass.LOW, memory_mb=100.0, duration_ms=3000.0, deviations=[]),
        ]
        
        report = console_reporter.format_error_summary(suite)
        
        # Should mention 3 failed runs
        assert "3" in report

    def test_format_error_summary_limits_examples(self, console_reporter):
        """Test format_error_summary shows first 3 examples per category."""
        suite = TestSuiteResult(total_runs=5, failed_runs=5)
        suite.runs = [
            RunMetrics(
                run_id=i,
                scenario_id=f"test{i}",
                passed=False,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
                duration_ms=3000.0,
                deviations=[Deviation("cpu_high", "error", 75.0 + i, 70.0, f"CPU error {i}")],
            )
            for i in range(1, 6)
        ]
        
        report = console_reporter.format_error_summary(suite)
        
        # Should show first 3 and then "... and 2 more"
        assert "and 2 more" in report or "Run #1:" in report

    def test_format_error_summary_multiple_categories(self, console_reporter):
        """Test format_error_summary with errors in multiple categories."""
        suite = TestSuiteResult(total_runs=3, failed_runs=3)
        suite.runs = [
            RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=False,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
                duration_ms=3000.0,
                deviations=[Deviation("cpu_high", "error", 75.0, 70.0, "CPU error")],
            ),
            RunMetrics(
                run_id=2,
                scenario_id="test2",
                passed=False,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                deviations=[Deviation("ocr_precision", "warning", 0.65, 0.80, "OCR error")],
            ),
            RunMetrics(
                run_id=3,
                scenario_id="test3",
                passed=False,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                deviations=[Deviation("click_deviation", "warning", 120.0, 100.0, "Click error")],
            ),
        ]
        
        report = console_reporter.format_error_summary(suite)
        
        # Should have at least 2-3 categories represented
        category_count = (("CPU" in report or "🔴" in report) +
                         ("OCR" in report or "📖" in report) +
                         ("Click" in report or "🖱️" in report))
        assert category_count >= 2
