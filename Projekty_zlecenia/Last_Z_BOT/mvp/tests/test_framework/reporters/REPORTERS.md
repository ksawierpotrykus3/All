# Phase 4: Test Framework Reporters

Comprehensive reporting system for hybrid macro C#/Python test framework with Console, HTML, and SQLite output formats.

## Komponenty

### 1. Console Reporter (`console_reporter.py`)

Generates readable ASCII table output with metrics summary and anomaly detection.

#### Key Methods

- **`format_output(suite_result)`** - ASCII table with ✓/✗ status, CPU class, metrics
- **`detect_bottlenecks(suite_result)`** - Identifies CPU spikes (>70%), timing anomalies (>100ms), accuracy deviations
- **`format_error_summary(suite_result)`** - Categorizes errors by type with counts
- **`generate_report(suite_result)`** - Full report combining all sections
- **`save_report(suite_result, filename)`** - Saves to `reports/console_report_{timestamp}.txt`

#### Features

- Pass rate indicator with visual progress bar
- CPU load distribution (IDLE/LOW/MEDIUM/HIGH/CRITICAL)
- Bottleneck detection with root cause suggestions
- Error categorization (CPU high, OCR precision, click deviation, timing issues)
- Per-run metrics: clicks, OCR precision, spam CPS, memory
- Hot-spots aggregation across HIGH/CRITICAL CPU runs

#### Example Output

```
================================================================================
TEST SUITE REPORT
================================================================================
Test Results: 38/40 passed
Pass Rate: 95.0%

AGGREGATE STATISTICS
CPU Load Distribution:
  IDLE       [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 16 runs ( 40.0%)
  LOW        [██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  6 runs ( 15.0%)
  MEDIUM     [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  12 runs ( 30.0%)
  HIGH       [█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  4 runs (  10.0%)
  CRITICAL   [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  2 runs (  5.0%)

Click Accuracy: 98.5% (789/801 clicks)
OCR Precision: 92.3% (avg across 38 runs)
Spam CPS: 38.2 avg (AGENTS.md limit: 38.46 CPS)
```

---

### 2. HTML Reporter (`html_reporter.py`)

Interactive dashboard with embedded charts (Plotly, Chart.js) and sortable tables.

#### Key Methods

- **`generate_summary_panel()`** - Summary metrics (pass rate, accuracy, OCR, CPU)
- **`generate_results_table()`** - Sortable per-run table with expandable rows
- **`generate_cpu_timeline_chart()`** - Plotly line graph: CPU % vs run sequence
- **`generate_click_scatter_plot()`** - Plotly scatter: click accuracy envelope ±50px
- **`generate_scenario_breakdown_charts()`** - Pie chart (pass rate by category) + histogram (reaction latency)
- **`finalize()`** - Generates `index.html` with self-contained CSS/JS/charts

#### Features

- Responsive grid layout (4 metric boxes: pass rate, click accuracy, OCR, CPU)
- Color-coded status (green ≥95%, orange ≥80%, red <80%)
- Interactive charts with hover/zoom (Plotly)
- Sortable columns by clicking header
- Expandable rows for detail metrics
- Multi-monitor section (if applicable)
- Bottleneck timeline with severity coloring
- Memory trend with baseline + 3x alert threshold
- Hot-spots aggregation table (top 20 functions)
- Deviation summary by type

#### Example Output Structure

```html
<!-- Summary Panel (4 metrics) -->
<div class="summary-metrics">
  <div class="metric-box pass-rate-green">Pass Rate: 95.0%</div>
  <div class="metric-box">Click Accuracy: 98.5%</div>
  <div class="metric-box">OCR Precision: 92.3%</div>
  <div class="metric-box">CPU Average: 28.5%</div>
</div>

<!-- Results Table (sortable) -->
<table id="resultsTable">
  <thead>Run# | Status | CPU | CPU(ms) | Memory(MB) | OCR | Spam CPS | Window | Deviations</thead>
  <tbody><!-- sortable rows with data attributes --></tbody>
</table>

<!-- Interactive Charts -->
<div id="cpu-timeline"><!-- Plotly line chart --></div>
<div id="click-scatter"><!-- Plotly scatter plot --></div>
<div id="scenario-breakdown"><!-- Pie + Histogram --></div>
```

---

### 3. SQLite Reporter (`sqlite_reporter.py`)

Persistent storage with queryable schema for regression tracking.

#### Schema

- **`runs`** - Main table per run
  - `id`, `timestamp`, `scenario_json`, `metrics_json`, `status`
  - `cpu_load_class`, `cpu_percent_avg`, `memory_peak_mb`, `bottleneck_type`
  - Indexes: `timestamp`, `scenario_name`, `passed`

- **`bottlenecks`** - Hot-spots and deviations
  - `run_id`, `bottleneck_type`, `severity`, `function_name`
  - `cpu_time_ms`, `cpu_percent`

- **`multi_monitor_metrics`** - Multi-monitor specific data
  - `run_id`, `monitor_count`, `monitor_0_dpi`, `monitor_1_dpi`
  - `coord_transform_time_ms`, `click_on_wrong_monitor`

#### Key Methods

- **`create_schema()`** - Initialize tables and indexes
- **`insert_run(run_num, scenario, metrics)`** - Append-only row insertion
- **`query_regression_detection()`** - Compare metrics by date, alert on >5% degradation
- **`query_cpu_spikes()`** - Find runs with `cpu_peak > 70%`
- **`query_low_accuracy()`** - Find runs with `click_accuracy < 90%`
- **`query_high_latency()`** - Find runs with `reaction_time_ms > 150`
- **`get_example_queries()`** - Return documented SQL examples

#### Example Queries

```sql
-- Regression Detection: Compare avg metrics by date
SELECT DATE(timestamp) as date, 
       AVG(cpu_percent_avg) as cpu_avg,
       AVG(json_extract(metrics_json, '$.ocr_precision')) as ocr_avg
FROM runs
GROUP BY DATE(timestamp)
ORDER BY timestamp DESC
LIMIT 7;

-- CPU Spikes: Find high-CPU runs
SELECT id, timestamp, scenario_json, cpu_percent_avg
FROM runs
WHERE cpu_percent_avg > 70
ORDER BY cpu_percent_avg DESC;

-- Low Accuracy: Find click accuracy issues
SELECT id, timestamp, bottleneck_type, severity
FROM runs
WHERE json_extract(metrics_json, '$.click_accuracy') < 0.90;
```

---

### 4. Reporter Manager (`reporter_manager.py`)

Coordinates all three reporters for unified output.

#### Key Methods

- **`add_run(run_num, scenario, metrics)`** - Add to all three reporters
- **`finalize_reports(suite_result)`** - Generate console, HTML, SQLite reports
- **`get_db_path()`** - Return SQLite database path
- **`get_example_queries()`** - Get documented SQL query examples

#### Example Usage

```python
from mvp.tests.test_framework.reporters import ReporterManager

# Initialize with custom output directory
manager = ReporterManager(output_dir=Path("reports"))

# Add runs during test execution
for run_num, scenario, metrics in test_results:
    manager.add_run(run_num, scenario, metrics)

# Generate all reports after suite completes
report_paths = manager.finalize_reports(suite_result)

# Access reports
print(f"Console: {report_paths['console']}")
print(f"HTML: {report_paths['html']}")
print(f"SQLite: {report_paths['sqlite']}")

# Query database
db_path = manager.get_db_path()
queries = manager.get_example_queries()
```

---

## Output Directory Structure

```
reports/
├── console/
│   └── console_report_20250901_231325.txt
├── html/
│   └── 20250901_231325/
│       └── index.html
└── test_results_20250901_231325.db
```

---

## Acceptance Criteria

### Console Reporter (4.1)

✅ Generates readable ASCII table with pass rate, metrics summary  
✅ Pass/fail status marked with ✓/✗ symbols  
✅ Anomalies highlighted with ⚠️  
✅ Bottleneck detection identifies CPU spikes (>70%), timing anomalies (>100ms), accuracy deviations (<90%)  
✅ Root causes suggested: OCR spike, jitter impact, frame drop, DPI scaling  
✅ Error categorization: window_not_found, ocr_low_confidence, click_miss, timer_sync_loss, timeout, log_parse_error  

### HTML Reporter (4.2)

✅ Summary panel visible on load with 4 key metrics  
✅ Responsive layout (grid: repeat(auto-fit, minmax(200px, 1fr)))  
✅ Results table sortable by clicking headers  
✅ Rows expandable for detail metrics  
✅ CPU timeline chart (Plotly line) with avg/peak values  
✅ Click accuracy scatter plot with ±50px envelope  
✅ Scenario breakdown pie chart + reaction latency histogram  
✅ Memory trend line with baseline and 3x alert threshold  

### SQLite Reporter (4.3)

✅ Schema creates 3 tables: runs, bottlenecks, multi_monitor_metrics  
✅ Indexes on timestamp, scenario_name, passed  
✅ Append-only rows (no overwrites)  
✅ Example queries: regression detection, CPU spikes, low accuracy, high latency  
✅ Timestamps ISO 8601 with millisecond precision  

---

## Testing

All reporters fully tested with 140 test cases:

- **Console Reporter**: 38 tests ✅
- **HTML Reporter**: 52 tests ✅
- **SQLite Reporter**: 42 tests ✅
- **Reporter Manager**: 8 tests ✅

Run all tests:

```bash
uv run pytest mvp/tests/test_framework/reporters/ -v
```

---

## Compliance Notes

### AGENTS.md Constraints

- Spam CPS verified against 38.46 CPS limit (3.3 CPS = 38.0 CPS ≥ 26.0ms period)
- CPU classification respects DIG_HOLD_MS timing (18.0ms uniform in 60 FPS mode)
- Multi-monitor metrics track DPI mismatches and coordinate transform overhead
- Error classification follows logging severity levels (error vs warning)

### Technical Requirements

- **Format**: ASCII tables, HTML with Plotly/Chart.js, SQLite3
- **Self-contained**: HTML includes all CSS, JS, chart data (no external dependencies)
- **Timestamps**: ISO 8601 format with millisecond precision
- **Database**: Append-only, indexed for fast queries
- **Metrics**: CPU %, memory MB, OCR %, click accuracy %, spam CPS, reaction latency ms

---

## Integration Example

```python
from pathlib import Path
from mvp.tests.test_framework.reporters import ReporterManager
from mvp.tests.test_framework.orchestrator import Orchestrator

# Run test suite
orchestrator = Orchestrator(config, scenario_randomizer)
suite_result = orchestrator.run_suite()

# Generate reports
manager = ReporterManager(output_dir=Path("test_reports"))
for run in suite_result.runs:
    manager.add_run(run.run_id, run.scenario, run)

report_paths = manager.finalize_reports(suite_result)

print(f"✅ Reports generated:")
print(f"  Console: {report_paths['console']}")
print(f"  HTML: {report_paths['html']}")
print(f"  SQLite: {report_paths['sqlite']}")
```

---

## Files

- `console_reporter.py` - Console ASCII output
- `html_reporter.py` - Interactive HTML dashboard
- `sqlite_reporter.py` - Persistent SQLite storage
- `reporter_manager.py` - Unified coordinator
- `__init__.py` - Package exports
- `test_console_reporter.py` - 38 tests
- `test_html_reporter.py` - 52 tests
- `test_sqlite_reporter.py` - 42 tests
- `test_reporter_manager.py` - 8 integration tests

**Total: 140 tests, all passing ✅**
