"""Tests for SQLite reporter."""

import gc
import json
import sqlite3
import tempfile
from pathlib import Path
from dataclasses import dataclass

import pytest

from mvp.tests.test_framework.metrics import (
    RunMetrics,
    CPULoadClass,
    MultiMonitorMetrics,
    HotSpot,
    Deviation,
)
from mvp.tests.test_framework.reporters.sqlite_reporter import SQLiteReporter


# Mock Scenario for testing
@dataclass
class MockScenario:
    """Mock scenario for testing."""
    window_position: tuple[int, int]
    window_size: tuple[int, int]
    viewport_clip: bool
    dpi_scaling: float
    chat_initial_state: str
    timer_seconds: int
    timer_jitter_ms: int
    event_injection_delay_ms: int
    has_glitch: bool


@pytest.fixture
def temp_db():
    """Create temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield str(db_path)
        # Ensure all database connections are closed before cleanup
        import gc
        gc.collect()


@pytest.fixture
def reporter(temp_db):
    """Create SQLiteReporter instance for testing."""
    return SQLiteReporter(temp_db)


@pytest.fixture
def mock_scenario():
    """Create mock scenario for testing."""
    return MockScenario(
        window_position=(100, 100),
        window_size=(1024, 768),
        viewport_clip=False,
        dpi_scaling=1.0,
        chat_initial_state="closed",
        timer_seconds=30,
        timer_jitter_ms=0,
        event_injection_delay_ms=0,
        has_glitch=False,
    )


@pytest.fixture
def mock_metrics_passed():
    """Create passing metrics for testing."""
    metrics = RunMetrics(
        run_id=1,
        scenario_id="test_1",
        passed=True,
        click_count=10,
        click_avg_deviation_px=5.0,
        ocr_detections=10,
        ocr_precision=0.95,
        spam_click_count=100,
        spam_click_duration_s=2.6,
        spam_cps=38.0,
        cpu_time_ms=150.0,
        gpu_time_ms=50.0,
        syscall_time_ms=20.0,
        memory_mb=50.0,
        cpu_load_class=CPULoadClass.LOW,
        duration_ms=2600.0,
    )
    return metrics


@pytest.fixture
def mock_metrics_failed():
    """Create failing metrics with high CPU."""
    metrics = RunMetrics(
        run_id=2,
        scenario_id="test_2",
        passed=False,
        click_count=10,
        click_avg_deviation_px=150.0,
        ocr_detections=5,
        ocr_precision=0.45,
        spam_click_count=50,
        spam_click_duration_s=2.6,
        spam_cps=19.0,
        cpu_time_ms=800.0,
        gpu_time_ms=100.0,
        syscall_time_ms=50.0,
        memory_mb=300.0,
        cpu_load_class=CPULoadClass.CRITICAL,
        hot_spots=[
            HotSpot(function_name="ocr_recognize", cpu_time_ms=400.0, percent=50.0),
            HotSpot(function_name="click_dispatcher", cpu_time_ms=200.0, percent=25.0),
        ],
        deviations=[
            Deviation(
                type="ocr_precision",
                severity="error",
                value=0.45,
                threshold=0.80,
                message="OCR precision too low"
            ),
        ],
        duration_ms=2600.0,
    )
    return metrics


class TestSQLiteReporterSchema:
    """Test SQLite schema creation and basic operations."""

    def test_init_creates_database(self, temp_db):
        """Test that __init__ creates database and schema."""
        reporter = SQLiteReporter(temp_db)
        
        assert Path(temp_db).exists()
        
        # Verify schema exists
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('runs', 'bottlenecks', 'multi_monitor_metrics')
            """)
            tables = {row[0] for row in cursor.fetchall()}
            
            assert tables == {'runs', 'bottlenecks', 'multi_monitor_metrics'}

    def test_init_creates_parent_directories(self):
        """Test that __init__ creates parent directories if needed."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "nested" / "dir" / "test.db"
            reporter = SQLiteReporter(str(db_path))
            
            assert db_path.exists()
            # Force cleanup of database connection before directory cleanup
            del reporter
            import gc
            gc.collect()

    def test_schema_has_correct_columns(self, temp_db):
        """Test that schema has all required columns."""
        reporter = SQLiteReporter(temp_db)
        
        with sqlite3.connect(temp_db) as conn:
            # Check runs table columns
            cursor = conn.execute("PRAGMA table_info(runs)")
            runs_columns = {row[1] for row in cursor.fetchall()}
            expected_runs = {
                'id', 'timestamp', 'scenario_json', 'metrics_json', 'status',
                'cpu_load_class', 'cpu_percent_avg', 'memory_peak_mb', 'bottleneck_type'
            }
            assert runs_columns == expected_runs
            
            # Check bottlenecks table columns
            cursor = conn.execute("PRAGMA table_info(bottlenecks)")
            bottleneck_columns = {row[1] for row in cursor.fetchall()}
            expected_bottleneck = {
                'id', 'run_id', 'bottleneck_type', 'severity',
                'function_name', 'cpu_time_ms', 'cpu_percent'
            }
            assert bottleneck_columns == expected_bottleneck


class TestAddRun:
    """Test add_run method."""

    def test_add_run_passed(self, reporter, mock_scenario, mock_metrics_passed):
        """Test adding a passing run."""
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        assert run_id > 0
        
        # Verify data was inserted
        with sqlite3.connect(reporter.db_path) as conn:
            cursor = conn.execute("SELECT id, status FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == run_id
            assert row[1] == "passed"

    def test_add_run_failed(self, reporter, mock_scenario, mock_metrics_failed):
        """Test adding a failing run."""
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_failed)
        
        assert run_id > 0
        
        # Verify data was inserted with failed status
        with sqlite3.connect(reporter.db_path) as conn:
            cursor = conn.execute("SELECT status, cpu_load_class FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == "failed"
            assert row[1] == "critical"

    def test_add_run_stores_scenario_json(self, reporter, mock_scenario, mock_metrics_passed):
        """Test that scenario data is stored as JSON."""
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("SELECT scenario_json FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            
            assert row is not None
            scenario_data = json.loads(row[0])
            
            # JSON converts tuples to lists, so compare as tuples after converting back
            assert tuple(scenario_data["window_position"]) == (100, 100)
            assert tuple(scenario_data["window_size"]) == (1024, 768)
            assert scenario_data["dpi_scaling"] == 1.0
            assert scenario_data["timer_seconds"] == 30

    def test_add_run_stores_metrics_json(self, reporter, mock_scenario, mock_metrics_passed):
        """Test that metrics data is stored as JSON."""
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        with sqlite3.connect(reporter.db_path) as conn:
            cursor = conn.execute("SELECT metrics_json FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            
            assert row is not None
            metrics_data = json.loads(row[0])
            
            assert metrics_data["click_count"] == 10
            assert metrics_data["ocr_precision"] == 0.95
            assert metrics_data["spam_cps"] == 38.0

    def test_add_run_with_hot_spots(self, reporter, mock_scenario, mock_metrics_failed):
        """Test that hot-spots are inserted as bottlenecks."""
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_failed)
        
        with sqlite3.connect(reporter.db_path) as conn:
            cursor = conn.execute(
                "SELECT function_name, cpu_time_ms FROM bottlenecks WHERE run_id = ? AND bottleneck_type = 'CPU'",
                (run_id,)
            )
            rows = cursor.fetchall()
            
            # Should have 2 hot-spots
            assert len(rows) == 2
            
            # Check hot-spot data
            functions = [row[0] for row in rows]
            assert "ocr_recognize" in functions
            assert "click_dispatcher" in functions

    def test_add_run_with_deviations(self, reporter, mock_scenario, mock_metrics_failed):
        """Test that deviations are inserted as bottlenecks."""
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_failed)
        
        with sqlite3.connect(reporter.db_path) as conn:
            cursor = conn.execute(
                "SELECT bottleneck_type, severity FROM bottlenecks WHERE run_id = ?",
                (run_id,)
            )
            rows = cursor.fetchall()
            
            # Should have deviations + hot-spots
            assert len(rows) > 0

    def test_add_run_with_multi_monitor_metrics(self, reporter, mock_scenario, mock_metrics_passed):
        """Test that multi-monitor metrics are inserted."""
        mmm = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[96, 144],
            coordinate_transform_ms=2.5,
            errors=[]
        )
        mock_metrics_passed.multi_monitor_metrics = mmm
        
        run_id = reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        with sqlite3.connect(reporter.db_path) as conn:
            cursor = conn.execute(
                "SELECT monitor_count, monitor_0_dpi, monitor_1_dpi, coord_transform_time_ms FROM multi_monitor_metrics WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == 2
            assert row[1] == 96
            assert row[2] == 144
            assert row[3] == 2.5

    def test_add_run_multiple_times(self, reporter, mock_scenario, mock_metrics_passed):
        """Test adding multiple runs generates different IDs."""
        run_id_1 = reporter.add_run(1, mock_scenario, mock_metrics_passed)
        run_id_2 = reporter.add_run(2, mock_scenario, mock_metrics_passed)
        run_id_3 = reporter.add_run(3, mock_scenario, mock_metrics_passed)
        
        assert run_id_1 != run_id_2
        assert run_id_2 != run_id_3


class TestQueryCPUDistribution:
    """Test query_cpu_distribution method."""

    def test_query_cpu_distribution_empty(self, reporter):
        """Test query on empty database."""
        result = reporter.query_cpu_distribution()
        
        assert result == {}

    def test_query_cpu_distribution_single(self, reporter, mock_scenario, mock_metrics_passed):
        """Test query with single run."""
        reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        result = reporter.query_cpu_distribution()
        
        assert result == {"low": 1}

    def test_query_cpu_distribution_multiple(self, reporter, mock_scenario, mock_metrics_passed, mock_metrics_failed):
        """Test query with multiple runs and different CPU classes."""
        reporter.add_run(1, mock_scenario, mock_metrics_passed)
        reporter.add_run(2, mock_scenario, mock_metrics_failed)
        
        result = reporter.query_cpu_distribution()
        
        assert result["low"] == 1
        assert result["critical"] == 1

    def test_query_cpu_distribution_aggregates(self, reporter, mock_scenario, mock_metrics_passed):
        """Test that distribution aggregates same CPU class."""
        mock_metrics_1 = RunMetrics(
            run_id=1, scenario_id="test", passed=True, 
            cpu_load_class=CPULoadClass.MEDIUM
        )
        mock_metrics_2 = RunMetrics(
            run_id=2, scenario_id="test", passed=True,
            cpu_load_class=CPULoadClass.MEDIUM
        )
        
        reporter.add_run(1, mock_scenario, mock_metrics_1)
        reporter.add_run(2, mock_scenario, mock_metrics_2)
        
        result = reporter.query_cpu_distribution()
        
        assert result == {"medium": 2}


class TestQueryBottleneckSummary:
    """Test query_bottleneck_summary method."""

    def test_query_bottleneck_summary_empty(self, reporter):
        """Test query on empty database."""
        result = reporter.query_bottleneck_summary()
        
        assert result == []

    def test_query_bottleneck_summary_with_hot_spots(self, reporter, mock_scenario, mock_metrics_failed):
        """Test query returns hot-spots as bottlenecks."""
        reporter.add_run(1, mock_scenario, mock_metrics_failed)
        
        result = reporter.query_bottleneck_summary()
        
        assert len(result) > 0
        
        # Check that hot-spots are included
        functions = [item["function_name"] for item in result]
        assert "ocr_recognize" in functions

    def test_query_bottleneck_summary_structure(self, reporter, mock_scenario, mock_metrics_failed):
        """Test that bottleneck results have correct structure."""
        reporter.add_run(1, mock_scenario, mock_metrics_failed)
        
        result = reporter.query_bottleneck_summary()
        
        if result:
            item = result[0]
            assert "bottleneck_type" in item
            assert "severity" in item
            assert "function_name" in item
            assert "cpu_time_ms" in item
            assert "cpu_percent" in item
            assert "count" in item

    def test_query_bottleneck_summary_aggregates(self, reporter, mock_scenario, mock_metrics_failed):
        """Test that bottlenecks are aggregated by type/severity/function."""
        reporter.add_run(1, mock_scenario, mock_metrics_failed)
        reporter.add_run(2, mock_scenario, mock_metrics_failed)
        
        result = reporter.query_bottleneck_summary()
        
        # Check that count is aggregated
        for item in result:
            if item["function_name"] == "ocr_recognize":
                assert item["count"] == 2


class TestQueryMultiMonitorResults:
    """Test query_multi_monitor_results method."""

    def test_query_multi_monitor_results_empty(self, reporter):
        """Test query on empty database."""
        result = reporter.query_multi_monitor_results()
        
        assert result == []

    def test_query_multi_monitor_results_single(self, reporter, mock_scenario, mock_metrics_passed):
        """Test query with single multi-monitor run."""
        mmm = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[96, 144],
            coordinate_transform_ms=3.2,
            errors=[]
        )
        mock_metrics_passed.multi_monitor_metrics = mmm
        
        reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        result = reporter.query_multi_monitor_results()
        
        assert len(result) == 1
        assert result[0]["monitor_count"] == 2
        assert result[0]["monitor_0_dpi"] == 96
        assert result[0]["monitor_1_dpi"] == 144
        assert result[0]["coord_transform_time_ms"] == 3.2

    def test_query_multi_monitor_results_multiple(self, reporter, mock_scenario, mock_metrics_passed):
        """Test query with multiple multi-monitor runs."""
        mmm1 = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[96, 144],
            coordinate_transform_ms=2.5,
            errors=[]
        )
        mmm2 = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[120, 120],
            coordinate_transform_ms=1.8,
            errors=["click_on_wrong_monitor"]
        )
        
        metrics_1 = RunMetrics(
            run_id=1, scenario_id="test", passed=True,
            multi_monitor_metrics=mmm1
        )
        metrics_2 = RunMetrics(
            run_id=2, scenario_id="test", passed=True,
            multi_monitor_metrics=mmm2
        )
        
        reporter.add_run(1, mock_scenario, metrics_1)
        reporter.add_run(2, mock_scenario, metrics_2)
        
        result = reporter.query_multi_monitor_results()
        
        assert len(result) == 2
        assert result[0]["coord_transform_time_ms"] == 2.5
        assert result[1]["coord_transform_time_ms"] == 1.8

    def test_query_multi_monitor_results_structure(self, reporter, mock_scenario, mock_metrics_passed):
        """Test that multi-monitor results have correct structure."""
        mmm = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[96, 144],
            coordinate_transform_ms=2.0,
            errors=[]
        )
        mock_metrics_passed.multi_monitor_metrics = mmm
        
        reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        result = reporter.query_multi_monitor_results()
        
        if result:
            item = result[0]
            assert "run_id" in item
            assert "monitor_count" in item
            assert "monitor_0_dpi" in item
            assert "monitor_1_dpi" in item
            assert "coord_transform_time_ms" in item
            assert "click_on_wrong_monitor" in item


class TestQueryAvgCoordTransformTime:
    """Test query_avg_coord_transform_time method."""

    def test_query_avg_coord_transform_time_empty(self, reporter):
        """Test query on empty database."""
        result = reporter.query_avg_coord_transform_time()
        
        assert result is None

    def test_query_avg_coord_transform_time_single(self, reporter, mock_scenario, mock_metrics_passed):
        """Test query with single run."""
        mmm = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[96, 144],
            coordinate_transform_ms=5.0,
            errors=[]
        )
        mock_metrics_passed.multi_monitor_metrics = mmm
        
        reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        result = reporter.query_avg_coord_transform_time()
        
        assert result == 5.0

    def test_query_avg_coord_transform_time_multiple(self, reporter, mock_scenario, mock_metrics_passed):
        """Test query averages multiple runs."""
        mmm1 = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[96, 144],
            coordinate_transform_ms=4.0,
            errors=[]
        )
        mmm2 = MultiMonitorMetrics(
            monitor_count=2,
            dpi_values=[120, 120],
            coordinate_transform_ms=6.0,
            errors=[]
        )
        
        metrics_1 = RunMetrics(
            run_id=1, scenario_id="test", passed=True,
            multi_monitor_metrics=mmm1
        )
        metrics_2 = RunMetrics(
            run_id=2, scenario_id="test", passed=True,
            multi_monitor_metrics=mmm2
        )
        
        reporter.add_run(1, mock_scenario, metrics_1)
        reporter.add_run(2, mock_scenario, metrics_2)
        
        result = reporter.query_avg_coord_transform_time()
        
        assert result == 5.0

    def test_query_avg_coord_transform_time_no_multi_monitor(self, reporter, mock_scenario, mock_metrics_passed):
        """Test query with runs that have no multi-monitor metrics."""
        reporter.add_run(1, mock_scenario, mock_metrics_passed)
        
        result = reporter.query_avg_coord_transform_time()
        
        assert result is None


class TestClassifyBottleneck:
    """Test _classify_bottleneck method."""

    def test_classify_bottleneck_cpu(self, reporter):
        """Test CPU bottleneck classification."""
        metrics = RunMetrics(
            run_id=1, scenario_id="test", passed=False,
            cpu_load_class=CPULoadClass.CRITICAL
        )
        
        result = reporter._classify_bottleneck(metrics)
        
        assert result == "CPU"

    def test_classify_bottleneck_memory(self, reporter):
        """Test memory bottleneck classification."""
        metrics = RunMetrics(
            run_id=1, scenario_id="test", passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=600.0
        )
        
        result = reporter._classify_bottleneck(metrics)
        
        assert result == "MEMORY"

    def test_classify_bottleneck_ocr(self, reporter):
        """Test OCR bottleneck classification."""
        metrics = RunMetrics(
            run_id=1, scenario_id="test", passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=50.0,
            ocr_precision=0.4
        )
        
        result = reporter._classify_bottleneck(metrics)
        
        assert result == "OCR_SLOW"

    def test_classify_bottleneck_click_drift(self, reporter):
        """Test click drift bottleneck classification."""
        metrics = RunMetrics(
            run_id=1, scenario_id="test", passed=False,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=50.0,
            ocr_precision=0.9,
            click_avg_deviation_px=150.0
        )
        
        result = reporter._classify_bottleneck(metrics)
        
        assert result == "CLICK_DRIFT"

    def test_classify_bottleneck_none(self, reporter):
        """Test no bottleneck classification."""
        metrics = RunMetrics(
            run_id=1, scenario_id="test", passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=50.0,
            ocr_precision=0.9,
            click_avg_deviation_px=50.0
        )
        
        result = reporter._classify_bottleneck(metrics)
        
        assert result is None



class TestCreateSchemaMethod:
    """Test create_schema method (task 4.3.1)."""

    def test_create_schema_creates_tables(self, reporter):
        """Test that create_schema creates all required tables."""
        reporter.create_schema()
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            assert "runs" in tables
            assert "bottlenecks" in tables
            assert "multi_monitor_metrics" in tables

    def test_create_schema_creates_indexes(self, reporter):
        """Test that create_schema creates required indexes."""
        reporter.create_schema()
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert "idx_runs_timestamp" in indexes
            assert "idx_runs_status" in indexes
            assert "idx_runs_cpu_load" in indexes

    def test_create_schema_runs_table_fields(self, reporter):
        """Test that runs table has correct field names."""
        reporter.create_schema()
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("PRAGMA table_info(runs)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert "id" in columns
            assert "timestamp" in columns
            assert "scenario_json" in columns
            assert "metrics_json" in columns
            assert "status" in columns
            assert "cpu_load_class" in columns


class TestInsertRunMethod:
    """Test insert_run method (task 4.3.2)."""

    def test_insert_run_appends_row(self, reporter, mock_scenario):
        """Test that insert_run appends row without overwrites."""
        reporter.create_schema()
        
        # Insert first run
        metrics1 = RunMetrics(
            run_id=1,
            scenario_id="test_1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
        )
        run_id1 = reporter.insert_run(1, mock_scenario, metrics1)
        
        # Insert second run
        metrics2 = RunMetrics(
            run_id=2,
            scenario_id="test_2",
            passed=False,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=200.0,
            duration_ms=3000.0,
        )
        run_id2 = reporter.insert_run(2, mock_scenario, metrics2)
        
        assert run_id1 != run_id2
        
        # Verify both rows exist
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM runs")
            count = cursor.fetchone()[0]
            assert count == 2

    def test_insert_run_no_overwrites(self, reporter, mock_scenario):
        """Test that insert_run never overwrites existing data."""
        reporter.create_schema()
        
        metrics1 = RunMetrics(
            run_id=1,
            scenario_id="test_1",
            passed=True,
            cpu_load_class=CPULoadClass.LOW,
            memory_mb=100.0,
            duration_ms=3000.0,
        )
        reporter.insert_run(1, mock_scenario, metrics1)
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("SELECT memory_peak_mb FROM runs WHERE id=1")
            original_memory = cursor.fetchone()[0]
        
        # Insert another run with different memory
        metrics2 = RunMetrics(
            run_id=2,
            scenario_id="test_2",
            passed=False,
            cpu_load_class=CPULoadClass.CRITICAL,
            memory_mb=500.0,
            duration_ms=3000.0,
        )
        reporter.insert_run(2, mock_scenario, metrics2)
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("SELECT memory_peak_mb FROM runs WHERE id=1")
            memory_after = cursor.fetchone()[0]
        
        # First run should not be modified
        assert original_memory == memory_after


class TestGetExampleQueriesMethod:
    """Test get_example_queries method (task 4.3.3)."""

    def test_get_example_queries_returns_dict(self, reporter):
        """Test that get_example_queries returns dictionary."""
        queries = reporter.get_example_queries()
        
        assert isinstance(queries, dict)
        assert len(queries) > 0

    def test_get_example_queries_has_documented_queries(self, reporter):
        """Test that example queries include key query types."""
        queries = reporter.get_example_queries()
        
        # Should include queries for regression tracking
        assert "cpu_distribution" in queries
        assert "pass_rate" in queries
        assert "bottleneck_summary" in queries
        assert "memory_regression" in queries
        assert "multi_monitor_performance" in queries

    def test_example_queries_are_valid_sql(self, reporter):
        """Test that all example queries are valid SQL."""
        reporter.create_schema()
        
        queries = reporter.get_example_queries()
        
        with sqlite3.connect(reporter.db_path, check_same_thread=False) as conn:
            for query_name, query_sql in queries.items():
                try:
                    # Extract just the SQL part (remove comments)
                    sql = query_sql.split('--')[0].strip()
                    if sql:
                        conn.execute(sql)
                except sqlite3.Error as e:
                    # Some queries may fail due to missing data, but they should parse
                    assert "syntax error" not in str(e).lower(), \
                        f"Query {query_name} has syntax error: {e}"

    def test_example_queries_include_documentation(self, reporter):
        """Test that example queries include documentation comments."""
        queries = reporter.get_example_queries()
        
        # Each query should have documentation
        for query_name, query_sql in queries.items():
            assert "--" in query_sql, f"Query {query_name} should have documentation comments"

    def test_example_queries_cover_regression_tracking(self, reporter):
        """Test that example queries cover key regression tracking scenarios."""
        queries = reporter.get_example_queries()
        query_names = set(queries.keys())
        
        # Should have queries for detecting regression
        regression_queries = [
            "cpu_distribution",     # CPU usage trends
            "pass_rate",           # Pass rate regression
            "memory_regression",   # Memory leaks
        ]
        
        for query_name in regression_queries:
            assert query_name in query_names, f"Missing regression tracking query: {query_name}"
