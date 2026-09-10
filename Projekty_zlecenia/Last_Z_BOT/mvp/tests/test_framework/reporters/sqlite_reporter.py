"""SQLite reporter for structured data storage and query support."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from mvp.tests.test_framework.metrics import (
    RunMetrics,
    TestSuiteResult,
    CPULoadClass,
    MultiMonitorMetrics,
    BottleneckInfo,
)


class SQLiteReporter:
    """Store test results in SQLite database with query support."""

    def __init__(self, db_path: str) -> None:
        """Initialize SQLite reporter with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create database schema if not exists."""
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    scenario_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cpu_load_class TEXT,
                    cpu_percent_avg REAL,
                    memory_peak_mb REAL,
                    bottleneck_type TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bottlenecks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    bottleneck_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    function_name TEXT,
                    cpu_time_ms REAL,
                    cpu_percent REAL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS multi_monitor_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    monitor_count INTEGER NOT NULL,
                    monitor_0_dpi REAL,
                    monitor_1_dpi REAL,
                    coord_transform_time_ms REAL,
                    click_on_wrong_monitor INTEGER,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                )
            """)
            
            conn.commit()

    def add_run(self, run_num: int, scenario, metrics: RunMetrics) -> int:
        """Insert run metrics into database.
        
        Args:
            run_num: Run number (1-indexed)
            scenario: Scenario object for this run
            metrics: RunMetrics collected during run
            
        Returns:
            ID of inserted run record
        """
        timestamp = datetime.now().isoformat()
        status = "passed" if metrics.passed else "failed"
        cpu_load_class = metrics.cpu_load_class.value if metrics.cpu_load_class else None
        
        # Serialize scenario and metrics as JSON
        scenario_json = json.dumps({
            "run_num": run_num,
            "window_position": scenario.window_position,
            "window_size": scenario.window_size,
            "viewport_clip": scenario.viewport_clip,
            "dpi_scaling": scenario.dpi_scaling,
            "chat_initial_state": scenario.chat_initial_state,
            "timer_seconds": scenario.timer_seconds,
            "timer_jitter_ms": scenario.timer_jitter_ms,
            "event_injection_delay_ms": scenario.event_injection_delay_ms,
            "has_glitch": scenario.has_glitch,
        })
        
        metrics_json = json.dumps({
            "scenario_id": metrics.scenario_id,
            "click_count": metrics.click_count,
            "click_avg_deviation_px": metrics.click_avg_deviation_px,
            "ocr_detections": metrics.ocr_detections,
            "ocr_precision": metrics.ocr_precision,
            "spam_click_count": metrics.spam_click_count,
            "spam_click_duration_s": metrics.spam_click_duration_s,
            "spam_cps": metrics.spam_cps,
            "cpu_time_ms": metrics.cpu_time_ms,
            "gpu_time_ms": metrics.gpu_time_ms,
            "syscall_time_ms": metrics.syscall_time_ms,
            "memory_mb": metrics.memory_mb,
            "duration_ms": metrics.duration_ms,
        })
        
        # Determine bottleneck type from deviations/hot-spots
        bottleneck_type = self._classify_bottleneck(metrics)
        
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("""
                INSERT INTO runs (
                    timestamp, scenario_json, metrics_json, status,
                    cpu_load_class, cpu_percent_avg, memory_peak_mb, bottleneck_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, scenario_json, metrics_json, status,
                cpu_load_class, metrics.cpu_time_ms, metrics.memory_mb, bottleneck_type
            ))
            run_id = cursor.lastrowid
            
            # Insert bottlenecks
            if metrics.deviations:
                for deviation in metrics.deviations:
                    conn.execute("""
                        INSERT INTO bottlenecks (
                            run_id, bottleneck_type, severity, function_name,
                            cpu_time_ms, cpu_percent
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        run_id, deviation.type, deviation.severity,
                        None, None, None
                    ))
            
            # Insert hot-spots as bottlenecks
            if metrics.hot_spots:
                for hot_spot in metrics.hot_spots:
                    conn.execute("""
                        INSERT INTO bottlenecks (
                            run_id, bottleneck_type, severity, function_name,
                            cpu_time_ms, cpu_percent
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        run_id, "CPU", "WARNING",
                        hot_spot.function_name, hot_spot.cpu_time_ms, hot_spot.percent
                    ))
            
            # Insert multi-monitor metrics
            if metrics.multi_monitor_metrics:
                mmm = metrics.multi_monitor_metrics
                dpi_0 = mmm.dpi_values[0] if len(mmm.dpi_values) > 0 else None
                dpi_1 = mmm.dpi_values[1] if len(mmm.dpi_values) > 1 else None
                click_wrong = 1 if "click_on_wrong_monitor" in mmm.errors else 0
                
                conn.execute("""
                    INSERT INTO multi_monitor_metrics (
                        run_id, monitor_count, monitor_0_dpi, monitor_1_dpi,
                        coord_transform_time_ms, click_on_wrong_monitor
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    run_id, mmm.monitor_count, dpi_0, dpi_1,
                    mmm.coordinate_transform_ms, click_wrong
                ))
            
            conn.commit()
        
        return run_id

    def _classify_bottleneck(self, metrics: RunMetrics) -> Optional[str]:
        """Classify primary bottleneck type from metrics.
        
        Args:
            metrics: RunMetrics to analyze
            
        Returns:
            Bottleneck type: "CPU", "MEMORY", "OCR_SLOW", "CLICK_DRIFT", or None
        """
        if metrics.cpu_load_class in (CPULoadClass.CRITICAL, CPULoadClass.HIGH):
            return "CPU"
        
        if metrics.memory_mb > 500:
            return "MEMORY"
        
        if metrics.ocr_precision < 0.5:
            return "OCR_SLOW"
        
        if metrics.click_avg_deviation_px > 100:
            return "CLICK_DRIFT"
        
        return None

    def query_cpu_distribution(self) -> dict[str, int]:
        """Query CPU load class distribution across all runs.
        
        Returns:
            Dictionary with cpu_load_class -> count mapping
        """
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("""
                SELECT cpu_load_class, COUNT(*) as count
                FROM runs
                WHERE cpu_load_class IS NOT NULL
                GROUP BY cpu_load_class
            """)
            
            result = {}
            for cpu_class, count in cursor.fetchall():
                result[cpu_class] = count
            
            return result

    def query_bottleneck_summary(self) -> list[dict]:
        """Query bottleneck summary (errors and high-severity items).
        
        Returns:
            List of bottleneck dictionaries with fields:
                - bottleneck_type: str
                - severity: str
                - function_name: Optional[str]
                - cpu_time_ms: Optional[float]
                - cpu_percent: Optional[float]
                - count: int
        """
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("""
                SELECT
                    bottleneck_type,
                    severity,
                    function_name,
                    AVG(cpu_time_ms) as avg_cpu_time_ms,
                    AVG(cpu_percent) as avg_cpu_percent,
                    COUNT(*) as count
                FROM bottlenecks
                WHERE severity IN ('WARNING', 'ERROR', 'CRITICAL')
                GROUP BY bottleneck_type, severity, function_name
                ORDER BY count DESC, avg_cpu_time_ms DESC
            """)
            
            result = []
            for row in cursor.fetchall():
                result.append({
                    "bottleneck_type": row[0],
                    "severity": row[1],
                    "function_name": row[2],
                    "cpu_time_ms": row[3],
                    "cpu_percent": row[4],
                    "count": row[5],
                })
            
            return result

    def query_multi_monitor_results(self) -> list[dict]:
        """Query multi-monitor metrics summary.
        
        Returns:
            List of multi-monitor result dictionaries with fields:
                - run_id: int
                - monitor_count: int
                - monitor_0_dpi: Optional[float]
                - monitor_1_dpi: Optional[float]
                - coord_transform_time_ms: float
                - click_on_wrong_monitor: int
        """
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("""
                SELECT
                    run_id,
                    monitor_count,
                    monitor_0_dpi,
                    monitor_1_dpi,
                    coord_transform_time_ms,
                    click_on_wrong_monitor
                FROM multi_monitor_metrics
                ORDER BY run_id
            """)
            
            result = []
            for row in cursor.fetchall():
                result.append({
                    "run_id": row[0],
                    "monitor_count": row[1],
                    "monitor_0_dpi": row[2],
                    "monitor_1_dpi": row[3],
                    "coord_transform_time_ms": row[4],
                    "click_on_wrong_monitor": row[5],
                })
            
            return result

    def query_avg_coord_transform_time(self) -> Optional[float]:
        """Query average coordinate transformation time across all multi-monitor runs.
        
        Returns:
            Average time in milliseconds, or None if no data
        """
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.execute("""
                SELECT AVG(coord_transform_time_ms)
                FROM multi_monitor_metrics
            """)
            
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else None

    def create_schema(self) -> None:
        """Create database schema with test_results.db structure.
        
        **Validates: Requirements 4.3.1**
        
        Create `test_results.db` with `runs` table, indexes.
        Database creates, schema matches, queries work.
        
        Establishes schema:
            - runs: run_id, timestamp, scenario_id, pass_rate, click_accuracy, 
                    ocr_precision, cpu_avg, memory_mb
            - bottlenecks: run_id (FK), bottleneck_type, severity
            - multi_monitor_metrics: run_id (FK), monitor_count, dpi values
        """
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            # Create runs table if not exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    scenario_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cpu_load_class TEXT,
                    cpu_percent_avg REAL,
                    memory_peak_mb REAL,
                    bottleneck_type TEXT,
                    run_id INTEGER UNIQUE
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_timestamp 
                ON runs(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_status 
                ON runs(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_cpu_load 
                ON runs(cpu_load_class)
            """)
            
            # Create bottlenecks table if not exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bottlenecks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    bottleneck_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    function_name TEXT,
                    cpu_time_ms REAL,
                    cpu_percent REAL,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    UNIQUE(run_id, bottleneck_type, function_name)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bottlenecks_severity 
                ON bottlenecks(severity)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bottlenecks_type 
                ON bottlenecks(bottleneck_type)
            """)
            
            # Create multi_monitor_metrics table if not exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS multi_monitor_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    monitor_count INTEGER NOT NULL,
                    monitor_0_dpi REAL,
                    monitor_1_dpi REAL,
                    coord_transform_time_ms REAL,
                    click_on_wrong_monitor INTEGER,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    UNIQUE(run_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_multi_monitor_count 
                ON multi_monitor_metrics(monitor_count)
            """)
            
            conn.commit()

    def insert_run(self, run_num: int, scenario, metrics: RunMetrics) -> int:
        """Insert result row after each run.
        
        **Validates: Requirements 4.3.2**
        
        Insert row into `runs` table, append-only.
        Rows inserted, no overwrites, timestamps accurate.
        
        Args:
            run_num: Run number (1-indexed)
            scenario: Scenario object for this run
            metrics: RunMetrics collected during run
            
        Returns:
            ID of inserted run record
        """
        # Call existing add_run method which does the insertion
        return self.add_run(run_num, scenario, metrics)

    def get_example_queries(self) -> dict[str, str]:
        """Get example queries for regression tracking.
        
        **Validates: Requirements 4.3.3**
        
        Provide documented queries for regression tracking.
        Queries work, tested on example database.
        
        Returns:
            Dictionary with query name -> SQL string mapping
        """
        return {
            "cpu_distribution": """
-- Query 1: CPU Load Distribution (regression tracking)
-- Shows count of runs by CPU load class
SELECT cpu_load_class, COUNT(*) as run_count
FROM runs
WHERE cpu_load_class IS NOT NULL
GROUP BY cpu_load_class
ORDER BY run_count DESC;
-- Expected: Baseline should have IDLE/LOW dominant
""",
            "pass_rate": """
-- Query 2: Pass Rate Trend
-- Calculate pass rate across all runs
SELECT 
    COUNT(*) as total_runs,
    SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed_runs,
    ROUND(100.0 * SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate_percent
FROM runs;
-- Expected: Pass rate should be >= 95%
""",
            "bottleneck_summary": """
-- Query 3: Top Bottleneck Functions
-- Identify most common bottleneck functions by CPU time
SELECT 
    function_name,
    bottleneck_type,
    COUNT(*) as occurrence_count,
    ROUND(AVG(cpu_time_ms), 2) as avg_cpu_ms,
    ROUND(MAX(cpu_time_ms), 2) as max_cpu_ms
FROM bottlenecks
WHERE function_name IS NOT NULL
GROUP BY function_name, bottleneck_type
ORDER BY avg_cpu_ms DESC
LIMIT 10;
-- Expected: Identify performance regression hotspots
""",
            "memory_regression": """
-- Query 4: Memory Trend Detection
-- Show memory usage over time to detect leaks
SELECT 
    id,
    timestamp,
    ROUND(memory_peak_mb, 2) as memory_mb,
    ROUND(memory_peak_mb - LAG(memory_peak_mb) OVER (ORDER BY id), 2) as memory_delta_mb
FROM runs
ORDER BY id;
-- Expected: Memory delta should stay near zero (no drift)
""",
            "multi_monitor_performance": """
-- Query 5: Multi-Monitor Performance Impact
-- Compare single vs multi-monitor coordinate transform time
SELECT 
    monitor_count,
    COUNT(*) as test_count,
    ROUND(AVG(coord_transform_time_ms), 3) as avg_transform_ms,
    ROUND(MAX(coord_transform_time_ms), 3) as max_transform_ms,
    SUM(click_on_wrong_monitor) as total_wrong_clicks
FROM multi_monitor_metrics
GROUP BY monitor_count
ORDER BY monitor_count;
-- Expected: Transform time < 5ms for same DPI, < 10ms for different DPI
""",
            "cpu_critical_runs": """
-- Query 6: CPU Critical Incidents
-- Find all runs with CRITICAL CPU usage and their bottlenecks
SELECT 
    r.id,
    r.timestamp,
    r.cpu_load_class,
    ROUND(r.cpu_percent_avg, 2) as cpu_percent,
    b.function_name,
    ROUND(b.cpu_time_ms, 2) as bottleneck_cpu_ms
FROM runs r
LEFT JOIN bottlenecks b ON r.id = b.run_id
WHERE r.cpu_load_class = 'critical'
ORDER BY r.id DESC;
-- Expected: CRITICAL runs should be rare (<5% of suite)
""",
            "performance_degradation": """
-- Query 7: Performance Degradation Detection
-- Find runs where pass_rate or OCR precision dropped significantly
SELECT 
    id,
    timestamp,
    status,
    bottleneck_type,
    ROUND(cpu_percent_avg, 2) as cpu_pct,
    ROUND(memory_peak_mb, 0) as memory_mb
FROM runs
WHERE status = 'failed' OR cpu_percent_avg > 70.0
ORDER BY timestamp DESC;
-- Expected: Identify when/where performance regressed
""",
            "scenario_comparison": """
-- Query 8: Scenario Type Performance Comparison
-- Compare metrics across different scenario types
SELECT 
    JSON_EXTRACT(scenario_json, '$.is_clipped') as clipped,
    JSON_EXTRACT(scenario_json, '$.monitor_count') as monitor_count,
    COUNT(*) as run_count,
    SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed_count,
    ROUND(100.0 * SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate
FROM runs
GROUP BY clipped, monitor_count
ORDER BY pass_rate DESC;
-- Expected: Baseline should have highest pass rate
""",
            "dpi_mismatch_impact": """
-- Query 9: DPI Mismatch Impact on Click Accuracy
-- Analyze coordinate transform overhead with different DPI configs
SELECT 
    CASE 
        WHEN monitor_0_dpi = monitor_1_dpi THEN 'same_dpi'
        WHEN monitor_0_dpi <> monitor_1_dpi THEN 'different_dpi'
        ELSE 'single_monitor'
    END as dpi_config,
    COUNT(*) as test_count,
    ROUND(AVG(coord_transform_time_ms), 3) as avg_transform_ms,
    COUNT(CASE WHEN click_on_wrong_monitor > 0 THEN 1 END) as misplaced_clicks
FROM multi_monitor_metrics
WHERE monitor_0_dpi IS NOT NULL
GROUP BY dpi_config
ORDER BY test_count DESC;
-- Expected: Different DPI should show coordinate transform overhead
""",
            "regression_baseline": """
-- Query 10: Regression Baseline Establishment
-- Get baseline metrics for future regression detection
SELECT 
    'Pass Rate' as metric, 
    ROUND(100.0 * SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) / COUNT(*), 2) as baseline_value
FROM runs
WHERE JSON_EXTRACT(scenario_json, '$.is_clipped') = 0
  AND JSON_EXTRACT(scenario_json, '$.monitor_count') = 1
UNION ALL
SELECT 
    'Avg CPU %', 
    ROUND(AVG(cpu_percent_avg), 2)
FROM runs
WHERE JSON_EXTRACT(scenario_json, '$.is_clipped') = 0
  AND JSON_EXTRACT(scenario_json, '$.monitor_count') = 1
UNION ALL
SELECT 
    'Avg Memory MB', 
    ROUND(AVG(memory_peak_mb), 2)
FROM runs
WHERE JSON_EXTRACT(scenario_json, '$.is_clipped') = 0
  AND JSON_EXTRACT(scenario_json, '$.monitor_count') = 1;
-- Expected: Baseline should establish reference points for regression detection
""",
        }
