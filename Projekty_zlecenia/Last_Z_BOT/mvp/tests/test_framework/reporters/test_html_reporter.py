"""Tests for HTML reporter."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mvp.tests.test_framework.metrics import (
    CPULoadClass,
    Deviation,
    HotSpot,
    MultiMonitorMetrics,
    RunMetrics,
)
from mvp.tests.test_framework.reporters.html_reporter import HTMLReporter
from mvp.tests.test_framework.scenarios import Scenario, MonitorConfig


@pytest.fixture
def html_reporter():
    """Create an HTML reporter instance with temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reporter = HTMLReporter(output_dir=Path(tmpdir))
        yield reporter


@pytest.fixture
def mock_scenario():
    """Create a mock scenario."""
    scenario = MagicMock(spec=Scenario)
    scenario.window_width = 1024
    scenario.window_height = 768
    scenario.window_x = 100
    scenario.window_y = 200
    scenario.dpi = 96
    scenario.timer_seconds = 300
    scenario.is_clipped = False
    scenario.monitor_count = 1
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
        macro_step_latency_ms={"WAIT_FOR_TIMER": 3000.0},
        spam_click_count=266,
        spam_click_duration_s=7.0,
        spam_cps=38.2,
        cpu_time_ms=1050.0,
        gpu_time_ms=0.0,
        syscall_time_ms=150.0,
        memory_mb=145.0,
        cpu_load_class=CPULoadClass.MEDIUM,
        hot_spots=[
            HotSpot(function_name="bot.clicker.click_at", cpu_time_ms=42.0, percent=35.0),
            HotSpot(function_name="bot.capture.get_frame", cpu_time_ms=28.0, percent=23.0),
            HotSpot(function_name="bot.ocr.detect", cpu_time_ms=22.0, percent=18.0),
        ],
        deviations=[],
        duration_ms=3000.0,
    )


class TestHTMLReporter:
    """Tests for HTMLReporter class."""

    def test_init_creates_output_dir(self):
        """Test that __init__ creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nonexistent" / "nested"
            reporter = HTMLReporter(output_dir=output_dir)
            assert output_dir.exists()

    def test_add_run_stores_metrics(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that add_run stores run metrics."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        assert len(html_reporter.runs) == 1
        assert html_reporter.runs[0] == sample_run_metrics
        assert len(html_reporter.scenarios) == 1

    def test_add_run_stores_scenario_data(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that add_run stores scenario configuration."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        scenario_data = html_reporter.scenarios[0]
        assert scenario_data["run_num"] == 1
        assert scenario_data["window_width"] == 1024
        assert scenario_data["window_height"] == 768
        assert scenario_data["dpi"] == 96
        assert scenario_data["timer_seconds"] == 300

    def test_add_multiple_runs(self, html_reporter, mock_scenario):
        """Test adding multiple runs."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=150.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        assert len(html_reporter.runs) == 3
        assert len(html_reporter.scenarios) == 3

    def test_finalize_raises_without_runs(self, html_reporter):
        """Test that finalize raises error if no runs added."""
        with pytest.raises(ValueError, match="No runs added"):
            html_reporter.finalize()

    def test_finalize_generates_html(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that finalize generates index.html."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        
        assert html_path.exists()
        assert html_path.name == "index.html"
        assert html_path.parent == html_reporter.output_dir

    def test_finalize_returns_path(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that finalize returns Path object."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        
        assert isinstance(html_path, Path)

    def test_html_content_includes_suite_summary(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes suite summary."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "Test Framework Report" in content
        assert "Total runs:" in content or "Total Runs" in content

    def test_html_content_includes_run_list(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes run details table."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "Run Details" in content
        assert "1024x768" in content

    def test_html_content_includes_cpu_chart(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes CPU pie chart."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "CPU Load Distribution" in content
        assert "cpu-pie-chart" in content

    def test_html_content_includes_hot_spots_table(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes hot-spots table."""
        # Create run with HIGH CPU to include hot-spots
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_scenario_1",
            passed=True,
            cpu_load_class=CPULoadClass.HIGH,
            cpu_time_ms=2000.0,
            memory_mb=145.0,
            duration_ms=3000.0,
            hot_spots=[
                HotSpot(function_name="bot.clicker.click_at", cpu_time_ms=42.0, percent=35.0),
                HotSpot(function_name="bot.capture.get_frame", cpu_time_ms=28.0, percent=23.0),
            ],
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "Hot-spots" in content
        assert "bot.clicker.click_at" in content

    def test_html_content_includes_bottleneck_timeline(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes bottleneck timeline chart."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "Bottleneck Timeline" in content
        assert "bottleneck-timeline" in content

    def test_html_content_includes_memory_chart(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes memory trend chart."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "Memory Trend" in content
        assert "memory-chart" in content

    def test_build_suite_result_calculates_pass_rate(self, html_reporter, mock_scenario):
        """Test that suite result calculates pass rate correctly."""
        # Add 2 passed and 1 failed run
        for i in range(2):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=150.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        metrics = RunMetrics(
            run_id=3,
            scenario_id="test_scenario_2",
            passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=150.0,
            duration_ms=3000.0,
        )
        html_reporter.add_run(run_num=3, scenario=mock_scenario, metrics=metrics)
        
        suite_result = html_reporter._build_suite_result()
        
        assert suite_result.total_runs == 3
        assert suite_result.passed_runs == 2
        assert suite_result.failed_runs == 1
        assert abs(suite_result.pass_rate - 2/3) < 0.01

    def test_build_suite_result_aggregates_cpu_distribution(self, html_reporter, mock_scenario):
        """Test that suite result aggregates CPU load distribution."""
        cpu_classes = [CPULoadClass.LOW, CPULoadClass.MEDIUM, CPULoadClass.HIGH]
        for i, cpu_class in enumerate(cpu_classes):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=True,
                cpu_load_class=cpu_class,
                memory_mb=150.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        suite_result = html_reporter._build_suite_result()
        
        assert suite_result.cpu_load_distribution["LOW"] == 1
        assert suite_result.cpu_load_distribution["MEDIUM"] == 1
        assert suite_result.cpu_load_distribution["HIGH"] == 1

    def test_build_run_list_data_includes_all_runs(self, html_reporter, mock_scenario):
        """Test that run list includes all runs."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=150.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        run_list = html_reporter._build_run_list_data()
        
        assert len(run_list) == 3
        assert all(run["passed"] == "✓" for run in run_list)

    def test_build_run_list_shows_deviations(self, html_reporter, mock_scenario):
        """Test that run list shows deviation count."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_scenario_1",
            passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=150.0,
            duration_ms=3000.0,
            deviations=[
                Deviation("cpu_high", "error", 75.0, 70.0, "CPU usage too high"),
                Deviation("ocr_precision", "warning", 0.65, 0.80, "OCR precision low"),
            ],
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        run_list = html_reporter._build_run_list_data()
        
        assert run_list[0]["deviations"] == 2

    def test_generate_cpu_pie_chart_creates_valid_json(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that CPU pie chart generates valid JSON."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        chart_json = html_reporter._generate_cpu_pie_chart()
        
        # Should be valid JSON with data and layout
        assert '"data"' in chart_json
        assert '"layout"' in chart_json
        assert 'medium' in chart_json.lower()  # CPU class name

    def test_build_hot_spots_table_empty_when_no_high_cpu(self, html_reporter, mock_scenario):
        """Test that hot-spots table is empty for low CPU runs."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_scenario_1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,  # Not HIGH or CRITICAL
            memory_mb=150.0,
            duration_ms=3000.0,
            hot_spots=[
                HotSpot(function_name="bot.clicker.click_at", cpu_time_ms=42.0, percent=35.0),
            ],
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        hot_spots = html_reporter._build_hot_spots_table()
        
        assert len(hot_spots) == 0

    def test_build_hot_spots_table_aggregates_from_high_cpu(self, html_reporter, mock_scenario):
        """Test that hot-spots table aggregates from HIGH and CRITICAL CPU runs."""
        for i in range(2):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.HIGH,
                memory_mb=150.0,
                duration_ms=3000.0,
                hot_spots=[
                    HotSpot(function_name="bot.clicker.click_at", cpu_time_ms=42.0, percent=35.0),
                    HotSpot(function_name="bot.capture.get_frame", cpu_time_ms=28.0, percent=23.0),
                ],
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        hot_spots = html_reporter._build_hot_spots_table()
        
        assert len(hot_spots) == 2
        # First hot-spot should be from click_at (higher CPU time)
        assert hot_spots[0]["function"] == "bot.clicker.click_at"
        assert float(hot_spots[0]["cpu_ms"]) == 84.0  # 42 * 2 runs

    def test_generate_memory_chart_creates_valid_json(self, html_reporter, mock_scenario):
        """Test that memory chart generates valid JSON."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0 + i * 50,  # Increasing memory
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        chart_json = html_reporter._generate_memory_chart()
        
        # Should be valid JSON with memory trend data
        assert '"data"' in chart_json
        assert '"layout"' in chart_json

    def test_build_multi_monitor_section_no_tests(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test multi-monitor section when no multi-monitor tests."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        mm_section = html_reporter._build_multi_monitor_section()
        
        assert mm_section["has_multi_monitor"] is False
        assert "No multi-monitor tests" in mm_section["message"]

    def test_build_multi_monitor_section_with_tests(self, html_reporter, mock_scenario):
        """Test multi-monitor section when multi-monitor tests exist."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_scenario_1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=150.0,
            duration_ms=3000.0,
            multi_monitor_metrics=MultiMonitorMetrics(
                monitor_count=2,
                dpi_values=[96, 144],
                coordinate_transform_ms=3.5,
                errors=[],
            ),
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        mm_section = html_reporter._build_multi_monitor_section()
        
        assert mm_section["has_multi_monitor"] is True
        assert mm_section["multi_monitor_runs"] == 1
        assert float(mm_section["avg_coord_transform_ms"]) == 3.5

    def test_build_deviation_summary(self, html_reporter, mock_scenario):
        """Test deviation summary aggregation."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_scenario_1",
            passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=150.0,
            duration_ms=3000.0,
            deviations=[
                Deviation("cpu_high", "error", 75.0, 70.0, "CPU high"),
                Deviation("ocr_precision", "warning", 0.65, 0.80, "OCR low"),
                Deviation("cpu_high", "error", 72.0, 70.0, "CPU high"),
            ],
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        dev_summary = html_reporter._build_deviation_summary()
        
        assert len(dev_summary["deviations"]) == 2
        
        # cpu_high should be first (count=2)
        cpu_high = [d for d in dev_summary["deviations"] if d["type"] == "cpu_high"][0]
        assert cpu_high["count"] == 2
        assert cpu_high["errors"] == 2

    def test_html_valid_structure(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that generated HTML has valid structure."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        # Check basic HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<body>" in content
        assert "</body>" in content

    def test_html_includes_plotly_charts(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that HTML includes Plotly script and chart containers."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        assert "plotly-latest.min.js" in content
        assert "Plotly.newPlot" in content

    def test_finalize_multiple_runs_with_deviations(self, html_reporter, mock_scenario):
        """Test finalize with multiple runs that have deviations."""
        for i in range(3):
            passed = i < 2
            cpu_class = CPULoadClass.CRITICAL if not passed else CPULoadClass.LOW
            deviations = [] if passed else [
                Deviation("cpu_high", "error", 75.0, 70.0, "CPU too high"),
            ]
            
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test_scenario_{i}",
                passed=passed,
                cpu_load_class=cpu_class,
                memory_mb=150.0,
                duration_ms=3000.0,
                deviations=deviations,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        html_path = html_reporter.finalize()
        content = html_path.read_text(encoding='utf-8')
        
        # Should include pass and fail indicators
        assert "✓" in content
        assert "✗" in content
        assert "Deviation Summary" in content


class TestHTMLDashboardSummaryPanel:
    """Test generate_summary_panel method."""

    @pytest.fixture
    def html_reporter_new(self):
        """Create an HTML reporter instance with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = HTMLReporter(output_dir=Path(tmpdir))
            yield reporter

    def test_generate_summary_panel_returns_html(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that generate_summary_panel returns HTML string."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html = html_reporter.generate_summary_panel()
        
        assert isinstance(html, str)
        assert len(html) > 0
        assert "<" in html and ">" in html

    def test_generate_summary_panel_includes_pass_rate(self, html_reporter, mock_scenario):
        """Test that summary panel includes pass rate."""
        for i in range(2):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_summary_panel()
        
        assert "Pass Rate" in html
        assert "100.0%" in html or "100%" in html

    def test_generate_summary_panel_includes_ocr_precision(self, html_reporter, mock_scenario):
        """Test that summary panel includes OCR precision."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
            ocr_detections=10,
            ocr_precision=0.95,
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_summary_panel()
        
        assert "OCR Precision" in html
        assert "95.0%" in html or "95%" in html

    def test_generate_summary_panel_includes_cpu_stats(self, html_reporter, mock_scenario):
        """Test that summary panel includes CPU statistics."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.MEDIUM,
            memory_mb=150.0,
            duration_ms=3000.0,
            cpu_time_ms=1500.0,  # 50% CPU
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_summary_panel()
        
        assert "CPU" in html

    def test_generate_summary_panel_empty_runs(self, html_reporter):
        """Test generate_summary_panel with no runs."""
        html = html_reporter.generate_summary_panel()
        
        assert isinstance(html, str)
        assert "No runs" in html or len(html) > 0

    def test_generate_summary_panel_color_coding(self, html_reporter, mock_scenario):
        """Test that summary panel uses color coding for pass rate."""
        # High pass rate (green)
        metrics_pass = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics_pass)
        
        html_high = html_reporter.generate_summary_panel()
        assert "pass-rate-green" in html_high
        
        # Low pass rate (red) - create new reporter in separate context
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            html_reporter2 = HTMLReporter(output_dir=Path(tmpdir))
            
            metrics_fail = RunMetrics(
                run_id=1,
                scenario_id="test1",
                passed=False,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
                duration_ms=3000.0,
            )
            html_reporter2.add_run(run_num=1, scenario=mock_scenario, metrics=metrics_fail)
            
            html_low = html_reporter2.generate_summary_panel()
            assert "pass-rate-red" in html_low


class TestHTMLChartsGeneration:
    """Test new chart generation methods (tasks 4.2.3-4.2.5)."""

    def test_generate_cpu_timeline_chart_returns_json(self, html_reporter, mock_scenario):
        """Test that generate_cpu_timeline_chart returns valid Plotly JSON."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW if i < 2 else CPULoadClass.MEDIUM,
                memory_mb=100.0 + i * 50,
                duration_ms=3000.0,
                cpu_time_ms=1000 + i * 200,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        chart_json = html_reporter.generate_cpu_timeline_chart()
        
        assert isinstance(chart_json, str)
        assert '"data"' in chart_json
        assert '"layout"' in chart_json

    def test_generate_cpu_timeline_shows_avg_and_peak(self, html_reporter, mock_scenario):
        """Test that CPU timeline includes average and critical threshold lines."""
        for i in range(2):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=True,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=150.0,
                duration_ms=3000.0,
                cpu_time_ms=1500.0 + i * 100,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        chart_json = html_reporter.generate_cpu_timeline_chart()
        
        # Should contain references to average, peak, and critical threshold
        assert "Average" in chart_json or "average" in chart_json
        assert "Critical" in chart_json or "critical" in chart_json

    def test_generate_cpu_timeline_empty_runs(self, html_reporter):
        """Test generate_cpu_timeline_chart with no runs."""
        chart_json = html_reporter.generate_cpu_timeline_chart()
        
        # Should return empty or minimal JSON
        assert isinstance(chart_json, str)

    def test_generate_click_scatter_plot_returns_json(self, html_reporter, mock_scenario):
        """Test that generate_click_scatter_plot returns valid Plotly JSON."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                click_count=20 + i * 5,
                click_avg_deviation_px=5.0 + i * 10,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        chart_json = html_reporter.generate_click_scatter_plot()
        
        assert isinstance(chart_json, str)
        assert '"data"' in chart_json
        assert '"layout"' in chart_json

    def test_generate_click_scatter_color_codes_deviations(self, html_reporter, mock_scenario):
        """Test that scatter plot color-codes deviations (good/warning/error)."""
        # Create runs with different deviation levels
        for i, deviation in enumerate([5.0, 30.0, 100.0]):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=i < 2,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
                click_count=20,
                click_avg_deviation_px=deviation,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        chart_json = html_reporter.generate_click_scatter_plot()
        
        # Should include color references for good/warning/error
        assert "#27ae60" in chart_json or "green" in chart_json  # Green (good)
        assert "#f39c12" in chart_json or "orange" in chart_json  # Orange (warning)
        assert "#e74c3c" in chart_json or "red" in chart_json     # Red (error)

    def test_generate_click_scatter_includes_thresholds(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that scatter plot includes threshold lines."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        chart_json = html_reporter.generate_click_scatter_plot()
        
        # Should reference threshold values
        assert "15" in chart_json or "Good" in chart_json
        assert "50" in chart_json or "Warning" in chart_json
        assert "100" in chart_json or "Error" in chart_json

    def test_generate_click_scatter_empty_runs(self, html_reporter):
        """Test generate_click_scatter_plot with no runs."""
        chart_json = html_reporter.generate_click_scatter_plot()
        
        assert isinstance(chart_json, str)

    def test_generate_scenario_breakdown_charts_returns_dict(self, html_reporter, mock_scenario):
        """Test that generate_scenario_breakdown_charts returns dictionary with both charts."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        charts = html_reporter.generate_scenario_breakdown_charts()
        
        assert isinstance(charts, dict)
        assert "category_pie" in charts
        assert "timing_histogram" in charts

    def test_generate_scenario_breakdown_categorizes_runs(self, html_reporter, mock_scenario):
        """Test that scenario breakdown correctly categorizes runs."""
        # Add various scenario types (all with required attributes)
        scenario_clipped = MagicMock(spec=Scenario)
        scenario_clipped.window_width = 800
        scenario_clipped.window_height = 600
        scenario_clipped.window_x = 0
        scenario_clipped.window_y = 0
        scenario_clipped.dpi = 96
        scenario_clipped.timer_seconds = 300
        scenario_clipped.is_clipped = True
        scenario_clipped.monitor_count = 1
        
        scenario_mm = MagicMock(spec=Scenario)
        scenario_mm.window_width = 1024
        scenario_mm.window_height = 768
        scenario_mm.window_x = 0
        scenario_mm.window_y = 0
        scenario_mm.dpi = 96
        scenario_mm.timer_seconds = 300
        scenario_mm.is_clipped = False
        scenario_mm.monitor_count = 2
        
        scenario_baseline = MagicMock(spec=Scenario)
        scenario_baseline.window_width = 1024
        scenario_baseline.window_height = 768
        scenario_baseline.window_x = 0
        scenario_baseline.window_y = 0
        scenario_baseline.dpi = 96
        scenario_baseline.timer_seconds = 300
        scenario_baseline.is_clipped = False
        scenario_baseline.monitor_count = 1
        
        for scenario, run_num in [(scenario_clipped, 1), (scenario_mm, 2), (scenario_baseline, 3)]:
            metrics = RunMetrics(
                run_id=run_num,
                scenario_id=f"test{run_num}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=run_num, scenario=scenario, metrics=metrics)
        
        charts = html_reporter.generate_scenario_breakdown_charts()
        
        # Charts should be valid Plotly JSON
        assert "category_pie" in charts
        assert '"data"' in charts["category_pie"]
        assert "timing_histogram" in charts
        assert '"data"' in charts["timing_histogram"]

    def test_generate_scenario_breakdown_empty_runs(self, html_reporter):
        """Test generate_scenario_breakdown_charts with no runs."""
        charts = html_reporter.generate_scenario_breakdown_charts()
        
        assert isinstance(charts, dict)
        assert "category_pie" in charts
        assert "timing_histogram" in charts


class TestHTMLDashboardResultsTable:
    """Test generate_results_table method."""

    def test_generate_results_table_returns_html(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that generate_results_table returns HTML string."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html = html_reporter.generate_results_table()
        
        assert isinstance(html, str)
        assert "<table" in html
        assert "</table>" in html

    def test_generate_results_table_includes_headers(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that results table includes all expected headers."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html = html_reporter.generate_results_table()
        
        assert "Run #" in html
        assert "Status" in html
        assert "CPU Class" in html
        assert "CPU (ms)" in html
        assert "Memory (MB)" in html
        assert "OCR Precision" in html
        assert "Spam CPS" in html

    def test_generate_results_table_includes_run_data(self, html_reporter, mock_scenario):
        """Test that results table includes run data rows."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.MEDIUM,
            memory_mb=145.0,
            duration_ms=3000.0,
            ocr_precision=0.90,
            spam_cps=38.0,
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_results_table()
        
        # Should include run number
        assert "1" in html
        # Should include pass indicator
        assert "✓" in html
        # Should include metrics
        assert "90%" in html or "0.9" in html

    def test_generate_results_table_multiple_runs(self, html_reporter, mock_scenario):
        """Test results table with multiple runs."""
        for i in range(3):
            metrics = RunMetrics(
                run_id=i + 1,
                scenario_id=f"test{i}",
                passed=i < 2,
                cpu_load_class=CPULoadClass.LOW if i < 2 else CPULoadClass.CRITICAL,
                memory_mb=100.0 + i * 50,
                duration_ms=3000.0,
            )
            html_reporter.add_run(run_num=i + 1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_results_table()
        
        # Should have 3 rows (one for each run)
        assert html.count("<tr class=\"run-row\"") == 3

    def test_generate_results_table_sortable_columns(self, html_reporter, mock_scenario, sample_run_metrics):
        """Test that table has sortable columns."""
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=sample_run_metrics)
        
        html = html_reporter.generate_results_table()
        
        # Should include onclick handlers for sorting
        assert "onclick=\"sortTable(" in html
        # Should include JavaScript sort function
        assert "function sortTable" in html

    def test_generate_results_table_status_styling(self, html_reporter, mock_scenario):
        """Test that pass/fail status has proper styling."""
        # Create passed run
        metrics_pass = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics_pass)
        
        html = html_reporter.generate_results_table()
        
        assert "status-pass" in html or "✓" in html

    def test_generate_results_table_cpu_class_colors(self, html_reporter, mock_scenario):
        """Test that CPU class has proper color styling."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=100.0,
            duration_ms=3000.0,
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_results_table()
        
        assert "cpu-critical" in html or "CRITICAL" in html

    def test_generate_results_table_empty_runs(self, html_reporter):
        """Test generate_results_table with no runs."""
        html = html_reporter.generate_results_table()
        
        assert isinstance(html, str)
        assert "No runs" in html or len(html) > 0

    def test_generate_results_table_data_attributes(self, html_reporter, mock_scenario):
        """Test that table cells have data-sort attributes for sorting."""
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
            cpu_time_ms=500.0,
        )
        html_reporter.add_run(run_num=1, scenario=mock_scenario, metrics=metrics)
        
        html = html_reporter.generate_results_table()
        
        # Should have data-sort attributes for numeric columns
        assert "data-sort=" in html
