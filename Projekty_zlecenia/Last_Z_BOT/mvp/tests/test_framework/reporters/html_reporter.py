"""HTML reporter for test framework results with interactive dashboard and embedded charts."""

from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from jinja2 import Environment, PackageLoader, select_autoescape
import plotly.graph_objects as go
import plotly.express as px

from mvp.tests.test_framework.metrics import (
    RunMetrics,
    TestSuiteResult,
    CPULoadClass,
    HotSpot,
)


class HTMLReporter:
    """Generate interactive HTML dashboard with CPU trends, bottlenecks, and multi-monitor results."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """Initialize HTML reporter.
        
        Args:
            output_dir: Directory to write HTML report to. Defaults to current directory.
        """
        self.output_dir = output_dir or Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.runs: list[RunMetrics] = []
        self.scenarios: dict[int, dict] = {}  # run_id -> scenario_dict
        
        # Setup Jinja2 environment
        self.env = Environment(
            loader=PackageLoader("mvp.tests.test_framework.reporters", package_path="."),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def add_run(self, run_num: int, scenario, metrics: RunMetrics) -> None:
        """Add single run to report.
        
        Args:
            run_num: Run number (1-indexed)
            scenario: Scenario object with window and monitor configuration
            metrics: RunMetrics for this run
        """
        self.runs.append(metrics)
        self.scenarios[len(self.runs) - 1] = {
            "run_num": run_num,
            "window_width": scenario.window_width,
            "window_height": scenario.window_height,
            "window_x": scenario.window_x,
            "window_y": scenario.window_y,
            "dpi": scenario.dpi,
            "timer_seconds": scenario.timer_seconds,
            "is_clipped": scenario.is_clipped,
            "monitor_count": scenario.monitor_count,
        }

    def finalize(self) -> Path:
        """Generate HTML report and return path to index.html.
        
        Returns:
            Path to generated index.html file
        """
        if not self.runs:
            raise ValueError("No runs added to report")
        
        # Build suite result
        suite_result = self._build_suite_result()
        
        # Generate charts
        run_list_data = self._build_run_list_data()
        cpu_pie_chart = self._generate_cpu_pie_chart()
        hot_spots_table = self._build_hot_spots_table()
        bottleneck_timeline = self._generate_bottleneck_timeline()
        memory_chart = self._generate_memory_chart()
        multi_monitor_section = self._build_multi_monitor_section()
        deviation_summary = self._build_deviation_summary()
        
        # Create HTML from template
        html_content = self._render_html(
            suite_result=suite_result,
            run_list_data=run_list_data,
            cpu_pie_chart=cpu_pie_chart,
            hot_spots_table=hot_spots_table,
            bottleneck_timeline=bottleneck_timeline,
            memory_chart=memory_chart,
            multi_monitor_section=multi_monitor_section,
            deviation_summary=deviation_summary,
        )
        
        # Write to file
        index_path = self.output_dir / "index.html"
        index_path.write_text(html_content, encoding="utf-8")
        
        return index_path

    def generate_summary_panel(self) -> str:
        """Generate HTML summary panel with metrics displayed prominently.
        
        **Validates: Requirements 4.2.1**
        
        Creates HTML summary with:
        - Pass rate indicator (colored badge)
        - Click accuracy percentage
        - OCR precision
        - CPU statistics
        - Memory stats
        
        Returns:
            HTML string with summary panel markup
        """
        if not self.runs:
            return "<p>No runs available for summary</p>"
        
        suite_result = self._build_suite_result()
        
        # Calculate aggregate metrics
        total_clicks = sum(r.click_count for r in self.runs)
        avg_click_accuracy = 0.0
        if total_clicks > 0:
            accurate_clicks = sum(
                r.click_count * (r.click_metrics.accuracy_ratio if r.click_metrics else 0)
                for r in self.runs
            )
            avg_click_accuracy = accurate_clicks / total_clicks
        
        avg_ocr_precision = (
            sum(r.ocr_precision for r in self.runs) / len(self.runs)
            if self.runs else 0.0
        )
        
        avg_cpu_percent = 0.0
        for run in self.runs:
            cpu_pct = (run.cpu_time_ms / run.duration_ms * 100) if run.duration_ms > 0 else 0
            avg_cpu_percent += cpu_pct
        avg_cpu_percent /= len(self.runs) if self.runs else 1
        
        # Determine pass rate color
        pass_rate_color = "green" if suite_result.pass_rate >= 0.95 else (
            "orange" if suite_result.pass_rate >= 0.80 else "red"
        )
        
        # Build HTML using string concatenation to avoid f-string CSS issues
        html_parts = [
            '<div class="summary-panel">',
            '    <div class="summary-metrics">',
            f'        <div class="metric-box pass-rate-{pass_rate_color}">',
            '            <h3>Pass Rate</h3>',
            f'            <div class="metric-value">{suite_result.pass_rate:.1%}</div>',
            f'            <div class="metric-detail">{suite_result.passed_runs}/{suite_result.total_runs} runs</div>',
            '        </div>',
            '',
            '        <div class="metric-box">',
            '            <h3>Click Accuracy</h3>',
            f'            <div class="metric-value">{avg_click_accuracy:.1%}</div>',
            f'            <div class="metric-detail">{total_clicks} clicks tracked</div>',
            '        </div>',
            '',
            '        <div class="metric-box">',
            '            <h3>OCR Precision</h3>',
            f'            <div class="metric-value">{avg_ocr_precision:.1%}</div>',
            '            <div class="metric-detail">Average across all runs</div>',
            '        </div>',
            '',
            '        <div class="metric-box">',
            '            <h3>CPU Average</h3>',
            f'            <div class="metric-value">{avg_cpu_percent:.1f}%</div>',
            f'            <div class="metric-detail">Peak: {suite_result.peak_memory_mb:.0f}MB</div>',
            '        </div>',
            '    </div>',
            '</div>',
            '',
            '<style>',
            '    .summary-panel { margin-bottom: 30px; }',
            '    .summary-metrics {',
            '        display: grid;',
            '        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));',
            '        gap: 20px;',
            '        margin-bottom: 20px;',
            '    }',
            '    .metric-box {',
            '        background: #f9f9f9;',
            '        border: 2px solid #ddd;',
            '        border-radius: 6px;',
            '        padding: 20px;',
            '        text-align: center;',
            '    }',
            '    .metric-box h3 {',
            '        font-size: 0.9em;',
            '        color: #666;',
            '        text-transform: uppercase;',
            '        margin-bottom: 10px;',
            '        font-weight: 600;',
            '    }',
            '    .metric-value {',
            '        font-size: 2.2em;',
            '        font-weight: bold;',
            '        margin-bottom: 5px;',
            '        color: #333;',
            '    }',
            '    .metric-detail {',
            '        font-size: 0.85em;',
            '        color: #888;',
            '    }',
            '    .pass-rate-green { border-left: 4px solid #27ae60; }',
            '    .pass-rate-green .metric-value { color: #27ae60; }',
            '    .pass-rate-orange { border-left: 4px solid #f39c12; }',
            '    .pass-rate-orange .metric-value { color: #f39c12; }',
            '    .pass-rate-red { border-left: 4px solid #e74c3c; }',
            '    .pass-rate-red .metric-value { color: #e74c3c; }',
            '</style>',
        ]
        
        return "\n".join(html_parts)

    def generate_results_table(self) -> str:
        """Generate HTML per-run table with sortable columns.
        
        **Validates: Requirements 4.2.2**
        
        Creates interactive table with:
        - Run ID, status (pass/fail), CPU class
        - Key metrics: CPU time, memory, OCR precision, spam CPS
        - Window configuration
        - Sortable columns via HTML data attributes
        - Clickable rows for detail view
        
        Returns:
            HTML string with sortable table markup
        """
        if not self.runs:
            return "<p>No runs available for display</p>"
        
        run_list_data = self._build_run_list_data()
        
        # Build table HTML line by line to avoid f-string CSS issues
        table_lines = [
            '<div class="results-table-container">',
            '    <table class="results-table" id="resultsTable">',
            '        <thead>',
            '            <tr>',
            '                <th onclick="sortTable(0)">Run #</th>',
            '                <th onclick="sortTable(1)">Status</th>',
            '                <th onclick="sortTable(2)">CPU Class</th>',
            '                <th onclick="sortTable(3)">CPU (ms)</th>',
            '                <th onclick="sortTable(4)">Memory (MB)</th>',
            '                <th onclick="sortTable(5)">OCR Precision</th>',
            '                <th onclick="sortTable(6)">Spam CPS</th>',
            '                <th onclick="sortTable(7)">Window</th>',
            '                <th onclick="sortTable(8)">Deviations</th>',
            '            </tr>',
            '        </thead>',
            '        <tbody>',
        ]
        
        for run in run_list_data:
            status_class = "pass" if run["passed"] == "✓" else "fail"
            cpu_class = run["cpu_class"].lower()
            
            table_lines.append(f'            <tr class="run-row" onclick="expandRow(this)">')
            table_lines.append(f'                <td data-sort="{run["run_num"]}">{run["run_num"]}</td>')
            table_lines.append(f'                <td data-sort="{run["passed"]}" class="status-{status_class}">{run["passed"]}</td>')
            table_lines.append(f'                <td data-sort="{run["cpu_class"]}" class="cpu-{cpu_class}">{run["cpu_class"].upper()}</td>')
            table_lines.append(f'                <td data-sort="{run["cpu_time_ms"]}" class="numeric">{run["cpu_time_ms"]}</td>')
            table_lines.append(f'                <td data-sort="{run["memory_mb"]}" class="numeric">{run["memory_mb"]}</td>')
            table_lines.append(f'                <td data-sort="{run["ocr_precision"]}">{run["ocr_precision"]}</td>')
            table_lines.append(f'                <td data-sort="{run["spam_cps"]}">{run["spam_cps"]}</td>')
            table_lines.append(f'                <td>{run["window"]}</td>')
            table_lines.append(f'                <td data-sort="{run["deviations"]}" class="numeric">{run["deviations"]}</td>')
            table_lines.append('            </tr>')
        
        table_lines.extend([
            '        </tbody>',
            '    </table>',
            '</div>',
        ])
        
        # CSS and JavaScript
        css_js = [
            '',
            '<style>',
            '    .results-table-container { margin-bottom: 30px; overflow-x: auto; }',
            '    .results-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }',
            '    .results-table th {',
            '        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);',
            '        color: white;',
            '        padding: 12px;',
            '        text-align: left;',
            '        font-weight: 600;',
            '        cursor: pointer;',
            '        user-select: none;',
            '    }',
            '    .results-table th:hover {',
            '        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);',
            '    }',
            '    .results-table td {',
            '        padding: 12px;',
            '        border-bottom: 1px solid #ddd;',
            '    }',
            '    .results-table tbody tr {',
            '        transition: background-color 0.2s;',
            '        cursor: pointer;',
            '    }',
            '    .results-table tbody tr:hover {',
            '        background-color: #f5f5f5;',
            '    }',
            '    .results-table tbody tr:nth-child(even) {',
            '        background-color: #fafafa;',
            '    }',
            '    .status-pass { color: #27ae60; font-weight: bold; }',
            '    .status-fail { color: #e74c3c; font-weight: bold; }',
            '    .cpu-idle { color: #66c2a5; font-weight: bold; }',
            '    .cpu-low { color: #3288bd; font-weight: bold; }',
            '    .cpu-medium { color: #fee08b; font-weight: bold; }',
            '    .cpu-high { color: #fc8d59; font-weight: bold; }',
            '    .cpu-critical { color: #d73027; font-weight: bold; }',
            '    .numeric { text-align: right; font-family: monospace; }',
            '</style>',
            '',
            '<script>',
            'function sortTable(columnIndex) {',
            '    const table = document.getElementById("resultsTable");',
            '    const tbody = table.tBodies[0];',
            '    const rows = Array.from(tbody.rows);',
            '    ',
            '    const isAscending = table.dataset.sortColumn !== String(columnIndex) || table.dataset.sortOrder === "desc";',
            '    const sortOrder = isAscending ? "asc" : "desc";',
            '    ',
            '    rows.sort((a, b) => {',
            '        const aValue = a.cells[columnIndex].dataset.sort || a.cells[columnIndex].textContent;',
            '        const bValue = b.cells[columnIndex].dataset.sort || b.cells[columnIndex].textContent;',
            '        ',
            '        const aNum = parseFloat(aValue);',
            '        const bNum = parseFloat(bValue);',
            '        ',
            '        if (!isNaN(aNum) && !isNaN(bNum)) {',
            '            return isAscending ? aNum - bNum : bNum - aNum;',
            '        }',
            '        ',
            '        if (isAscending) {',
            '            return aValue.localeCompare(bValue);',
            '        } else {',
            '            return bValue.localeCompare(aValue);',
            '        }',
            '    });',
            '    ',
            '    rows.forEach(row => tbody.appendChild(row));',
            '    ',
            '    table.dataset.sortColumn = columnIndex;',
            '    table.dataset.sortOrder = sortOrder;',
            '}',
            '',
            'function expandRow(row) {',
            '    console.log("Row clicked:", row);',
            '}',
            '</script>',
        ]
        
        return "\n".join(table_lines + css_js)


    def _build_suite_result(self) -> TestSuiteResult:
        """Build suite result from accumulated runs.
        
        Returns:
            TestSuiteResult with aggregated statistics
        """
        total_runs = len(self.runs)
        passed_runs = sum(1 for r in self.runs if r.passed)
        failed_runs = total_runs - passed_runs
        pass_rate = (passed_runs / total_runs) if total_runs > 0 else 0.0
        
        # CPU distribution
        cpu_dist = {}
        for run in self.runs:
            class_name = run.cpu_load_class.value.upper()
            cpu_dist[class_name] = cpu_dist.get(class_name, 0) + 1
        
        # Memory statistics
        memory_values = [r.memory_mb for r in self.runs]
        avg_memory = sum(memory_values) / len(memory_values) if memory_values else 0.0
        peak_memory = max(memory_values) if memory_values else 0.0
        
        # Bottleneck summary
        bottleneck_summary = []
        for run in self.runs:
            if run.deviations:
                for deviation in run.deviations:
                    if deviation.severity == "error":
                        bottleneck_summary.append(f"Run {run.run_id}: {deviation.message}")
        
        suite_result = TestSuiteResult(
            total_runs=total_runs,
            passed_runs=passed_runs,
            failed_runs=failed_runs,
            runs=self.runs,
            pass_rate=pass_rate,
            cpu_load_distribution=cpu_dist,
            bottleneck_summary=bottleneck_summary,
            avg_memory_mb=avg_memory,
            peak_memory_mb=peak_memory,
            total_duration_s=sum(r.duration_ms for r in self.runs) / 1000,
            timestamp_ms=datetime.now().timestamp() * 1000,
        )
        
        return suite_result

    def _build_run_list_data(self) -> list[dict]:
        """Build run list data for table display.
        
        Returns:
            List of dictionaries with run data, sortable by metric
        """
        run_list = []
        for i, run in enumerate(self.runs):
            scenario = self.scenarios.get(i, {})
            run_list.append({
                "run_id": run.run_id,
                "run_num": scenario.get("run_num", i + 1),
                "passed": "✓" if run.passed else "✗",
                "cpu_class": run.cpu_load_class.value,
                "cpu_time_ms": f"{run.cpu_time_ms:.0f}",
                "memory_mb": f"{run.memory_mb:.0f}",
                "ocr_precision": f"{run.ocr_precision:.1%}",
                "spam_cps": f"{run.spam_cps:.1f}",
                "window": f"{scenario.get('window_width', 0)}x{scenario.get('window_height', 0)}",
                "timer_s": scenario.get("timer_seconds", 0),
                "deviations": len(run.deviations),
            })
        
        return run_list

    def _generate_cpu_pie_chart(self) -> str:
        """Generate CPU load distribution pie chart.
        
        Returns:
            Plotly graph JSON for embedding in HTML
        """
        cpu_dist = {}
        for run in self.runs:
            class_name = run.cpu_load_class.value
            cpu_dist[class_name] = cpu_dist.get(class_name, 0) + 1
        
        labels = list(cpu_dist.keys())
        values = list(cpu_dist.values())
        colors = {
            "idle": "#66c2a5",
            "low": "#3288bd",
            "medium": "#fee08b",
            "high": "#fc8d59",
            "critical": "#d73027",
        }
        color_list = [colors.get(label, "#999999") for label in labels]
        
        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=color_list),
                textposition="auto",
                hovertemplate="<b>%{label}</b><br>%{value} runs (%{percent})<extra></extra>",
            )
        ])
        
        fig.update_layout(
            title="CPU Load Distribution",
            height=400,
            showlegend=True,
        )
        
        return fig.to_json()

    def _build_hot_spots_table(self) -> list[dict]:
        """Build aggregated hot-spots table data.
        
        Returns:
            List of hot-spot dictionaries sorted by CPU time
        """
        hot_spot_map: dict[str, tuple[float, float, int]] = {}
        
        for run in self.runs:
            # Only include runs with HIGH or CRITICAL CPU
            if run.cpu_load_class not in (CPULoadClass.HIGH, CPULoadClass.CRITICAL):
                continue
            
            for hot_spot in run.hot_spots:
                if hot_spot.function_name not in hot_spot_map:
                    hot_spot_map[hot_spot.function_name] = (0.0, 0.0, 0)
                
                total_ms, total_percent, count = hot_spot_map[hot_spot.function_name]
                hot_spot_map[hot_spot.function_name] = (
                    total_ms + hot_spot.cpu_time_ms,
                    total_percent + hot_spot.percent,
                    count + 1,
                )
        
        # Convert to list and sort by total_ms descending
        hot_spots = []
        for func_name, (total_ms, total_percent, count) in hot_spot_map.items():
            avg_percent = total_percent / count if count > 0 else 0
            hot_spots.append({
                "function": func_name,
                "cpu_ms": f"{total_ms:.1f}",
                "percent": f"{avg_percent:.1f}",
                "count": count,
            })
        
        hot_spots.sort(key=lambda x: float(x["cpu_ms"]), reverse=True)
        
        return hot_spots[:20]  # Top 20 hot-spots

    def _generate_bottleneck_timeline(self) -> str:
        """Generate bottleneck timeline visualization.
        
        Returns:
            Plotly graph JSON for embedding in HTML
        """
        bottleneck_data = []
        for i, run in enumerate(self.runs):
            severity = "None"
            if run.deviations:
                max_severity = max(
                    (d.severity for d in run.deviations),
                    default="warning",
                )
                severity = max_severity.upper()
            
            bottleneck_data.append({
                "run": i + 1,
                "severity": severity,
                "cpu_percent": (run.cpu_time_ms / run.duration_ms * 100) if run.duration_ms > 0 else 0,
            })
        
        severities = [d["severity"] for d in bottleneck_data]
        cpu_percents = [d["cpu_percent"] for d in bottleneck_data]
        runs = [d["run"] for d in bottleneck_data]
        
        color_map = {
            "CRITICAL": "#d73027",
            "ERROR": "#fc8d59",
            "WARNING": "#fee08b",
            "None": "#66c2a5",
        }
        
        fig = go.Figure()
        
        for severity in ["CRITICAL", "ERROR", "WARNING", "None"]:
            mask = [s == severity for s in severities]
            fig.add_trace(go.Scatter(
                x=[r for r, m in zip(runs, mask) if m],
                y=[c for c, m in zip(cpu_percents, mask) if m],
                mode="markers+lines",
                name=severity,
                marker=dict(
                    size=10,
                    color=color_map.get(severity, "#999999"),
                ),
                hovertemplate="Run %{x}<br>CPU: %{y:.1f}%<extra></extra>",
            ))
        
        fig.update_layout(
            title="Bottleneck Timeline (CPU % by Run)",
            xaxis_title="Run Number",
            yaxis_title="CPU Usage (%)",
            height=400,
            showlegend=True,
            hovermode="x unified",
        )
        
        return fig.to_json()

    def _generate_memory_chart(self) -> str:
        """Generate memory usage trend line chart.
        
        Returns:
            Plotly graph JSON for embedding in HTML
        """
        runs = list(range(1, len(self.runs) + 1))
        memory_values = [r.memory_mb for r in self.runs]
        baseline_memory = memory_values[0] if memory_values else 0
        
        fig = go.Figure()
        
        # Memory line
        fig.add_trace(go.Scatter(
            x=runs,
            y=memory_values,
            mode="lines+markers",
            name="Memory Usage",
            line=dict(color="#3288bd", width=2),
            marker=dict(size=6),
            hovertemplate="Run %{x}<br>Memory: %{y:.0f}MB<extra></extra>",
        ))
        
        # Add baseline and 3x baseline reference lines
        fig.add_hline(
            y=baseline_memory,
            line_dash="dash",
            line_color="gray",
            annotation_text="Baseline",
            annotation_position="right",
        )
        
        fig.add_hline(
            y=baseline_memory * 3,
            line_dash="dash",
            line_color="red",
            annotation_text="3x Baseline (Alert)",
            annotation_position="right",
        )
        
        fig.update_layout(
            title="Memory Usage Trend",
            xaxis_title="Run Number",
            yaxis_title="Memory (MB)",
            height=400,
            showlegend=True,
            hovermode="x unified",
        )
        
        return fig.to_json()

    def _build_multi_monitor_section(self) -> dict:
        """Build multi-monitor results comparison section.
        
        Returns:
            Dictionary with multi-monitor statistics
        """
        multi_monitor_runs = [
            r for r in self.runs
            if r.multi_monitor_metrics is not None
        ]
        
        if not multi_monitor_runs:
            return {
                "has_multi_monitor": False,
                "message": "No multi-monitor tests performed",
            }
        
        # Aggregate multi-monitor metrics
        total_coord_transform_ms = sum(
            r.multi_monitor_metrics.coordinate_transform_ms
            for r in multi_monitor_runs
        )
        avg_coord_transform_ms = (
            total_coord_transform_ms / len(multi_monitor_runs)
            if multi_monitor_runs
            else 0
        )
        
        total_errors = sum(
            len(r.multi_monitor_metrics.errors)
            for r in multi_monitor_runs
        )
        
        dpi_mismatches = [
            r for r in multi_monitor_runs
            if len(r.multi_monitor_metrics.dpi_values) > 1
            and len(set(r.multi_monitor_metrics.dpi_values)) > 1
        ]
        
        return {
            "has_multi_monitor": True,
            "multi_monitor_runs": len(multi_monitor_runs),
            "avg_coord_transform_ms": f"{avg_coord_transform_ms:.2f}",
            "total_errors": total_errors,
            "dpi_mismatch_runs": len(dpi_mismatches),
            "pass_rate": f"{sum(1 for r in multi_monitor_runs if r.passed) / len(multi_monitor_runs):.1%}",
        }

    def _build_deviation_summary(self) -> dict:
        """Build deviation summary statistics.
        
        Returns:
            Dictionary with deviation summary
        """
        deviation_types = {}
        for run in self.runs:
            for deviation in run.deviations:
                dev_type = deviation.type
                if dev_type not in deviation_types:
                    deviation_types[dev_type] = {
                        "count": 0,
                        "severity_error": 0,
                        "severity_warning": 0,
                    }
                
                deviation_types[dev_type]["count"] += 1
                if deviation.severity == "error":
                    deviation_types[dev_type]["severity_error"] += 1
                else:
                    deviation_types[dev_type]["severity_warning"] += 1
        
        summary = []
        for dev_type, stats in deviation_types.items():
            summary.append({
                "type": dev_type,
                "count": stats["count"],
                "errors": stats["severity_error"],
                "warnings": stats["severity_warning"],
            })
        
        summary.sort(key=lambda x: x["count"], reverse=True)
        
        return {"deviations": summary}

    def _render_html(
        self,
        suite_result: TestSuiteResult,
        run_list_data: list[dict],
        cpu_pie_chart: str,
        hot_spots_table: list[dict],
        bottleneck_timeline: str,
        memory_chart: str,
        multi_monitor_section: dict,
        deviation_summary: dict,
    ) -> str:
        """Render final HTML from template.
        
        Args:
            suite_result: Aggregated test suite result
            run_list_data: Run list data for table
            cpu_pie_chart: CPU pie chart JSON
            hot_spots_table: Hot-spots table data
            bottleneck_timeline: Bottleneck timeline JSON
            memory_chart: Memory trend chart JSON
            multi_monitor_section: Multi-monitor results
            deviation_summary: Deviation summary
            
        Returns:
            Rendered HTML string
        """
        template = self._get_template()
        
        html_content = template.render(
            suite_result=suite_result,
            run_list_data=run_list_data,
            cpu_pie_chart=cpu_pie_chart,
            hot_spots_table=hot_spots_table,
            bottleneck_timeline=bottleneck_timeline,
            memory_chart=memory_chart,
            multi_monitor_section=multi_monitor_section,
            deviation_summary=deviation_summary,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        
        return html_content

    def generate_cpu_timeline_chart(self) -> str:
        """Generate CPU timeline chart (line graph).
        
        **Validates: Requirements 4.2.3**
        
        Plot CPU % on y-axis, run sequence on x-axis, show avg/peak.
        
        Returns:
            Plotly graph JSON for embedding in HTML
        """
        if not self.runs:
            return "{}"
        
        runs = list(range(1, len(self.runs) + 1))
        cpu_percents = []
        
        for run in self.runs:
            cpu_pct = (run.cpu_time_ms / run.duration_ms * 100) if run.duration_ms > 0 else 0
            cpu_percents.append(cpu_pct)
        
        avg_cpu = sum(cpu_percents) / len(cpu_percents) if cpu_percents else 0
        peak_cpu = max(cpu_percents) if cpu_percents else 0
        
        fig = go.Figure()
        
        # CPU line chart
        fig.add_trace(go.Scatter(
            x=runs,
            y=cpu_percents,
            mode="lines+markers",
            name="CPU %",
            line=dict(color="#667eea", width=2),
            marker=dict(size=7),
            fill="tozeroy",
            hovertemplate="Run %{x}<br>CPU: %{y:.1f}%<extra></extra>",
        ))
        
        # Add average reference line
        fig.add_hline(
            y=avg_cpu,
            line_dash="dash",
            line_color="orange",
            annotation_text=f"Average: {avg_cpu:.1f}%",
            annotation_position="right",
        )
        
        # Add critical threshold (70%)
        fig.add_hline(
            y=70.0,
            line_dash="dash",
            line_color="red",
            annotation_text="Critical (70%)",
            annotation_position="right",
        )
        
        fig.update_layout(
            title="CPU Timeline (Run Sequence)",
            xaxis_title="Run Number",
            yaxis_title="CPU Usage (%)",
            height=400,
            hovermode="x unified",
            showlegend=True,
        )
        
        return fig.to_json()

    def generate_click_scatter_plot(self) -> str:
        """Generate click accuracy scatter plot.
        
        **Validates: Requirements 4.2.4**
        
        Plot clicks vs expected ROI, show deviations visually.
        Scatter shows accuracy distribution, out-of-bounds highlighted.
        
        Returns:
            Plotly graph JSON for embedding in HTML
        """
        if not self.runs:
            return "{}"
        
        click_counts = []
        deviations = []
        colors = []
        run_ids = []
        
        for i, run in enumerate(self.runs):
            click_counts.append(run.click_count)
            deviation = run.click_avg_deviation_px
            deviations.append(deviation)
            run_ids.append(i + 1)
            
            # Color code: green = good (<15px), yellow = warning (15-50px), red = error (>50px)
            if deviation < 15:
                colors.append("#27ae60")  # Green
            elif deviation < 50:
                colors.append("#f39c12")  # Orange
            else:
                colors.append("#e74c3c")  # Red
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=click_counts,
            y=deviations,
            mode="markers+text",
            marker=dict(
                size=10,
                color=colors,
                line=dict(width=1, color="white"),
            ),
            text=[f"Run {rid}" for rid in run_ids],
            textposition="top center",
            hovertemplate="Run %{text}<br>Clicks: %{x}<br>Deviation: %{y:.1f}px<extra></extra>",
        ))
        
        # Add threshold lines
        fig.add_hline(y=15.0, line_dash="dash", line_color="green", annotation_text="Good (15px)")
        fig.add_hline(y=50.0, line_dash="dash", line_color="orange", annotation_text="Warning (50px)")
        fig.add_hline(y=100.0, line_dash="dash", line_color="red", annotation_text="Error (100px)")
        
        fig.update_layout(
            title="Click Accuracy Scatter (Deviation Distribution)",
            xaxis_title="Click Count",
            yaxis_title="Avg Deviation (px)",
            height=400,
            hovermode="closest",
            showlegend=False,
        )
        
        return fig.to_json()

    def generate_scenario_breakdown_charts(self) -> dict[str, str]:
        """Generate scenario breakdown charts.
        
        **Validates: Requirements 4.2.5**
        
        Group results by category (baseline/window/timer/event/stress), timing histogram.
        Charts render, data grouped correctly.
        
        Returns:
            Dictionary with chart JSONs:
                - category_pie: pie chart of scenario categories
                - timing_histogram: histogram of run times by category
        """
        if not self.runs or not self.scenarios:
            return {"category_pie": "{}", "timing_histogram": "{}"}
        
        # Categorize scenarios
        categories = {}  # category -> list of (run_num, duration_ms)
        
        for i, run in enumerate(self.runs):
            scenario = self.scenarios.get(i, {})
            
            # Determine category based on scenario characteristics
            window_size = scenario.get("window_height", 768)
            timer_s = scenario.get("timer_seconds", 300)
            is_clipped = scenario.get("is_clipped", False)
            monitor_count = scenario.get("monitor_count", 1)
            
            if is_clipped:
                category = "clipped"
            elif monitor_count > 1:
                category = "multi_monitor"
            elif window_size < 768:
                category = "small_window"
            elif timer_s < 30:
                category = "short_timer"
            elif timer_s > 100:
                category = "long_timer"
            else:
                category = "baseline"
            
            if category not in categories:
                categories[category] = []
            categories[category].append((scenario.get("run_num", i + 1), run.duration_ms))
        
        # Generate category pie chart
        category_names = list(categories.keys())
        category_counts = [len(categories[cat]) for cat in category_names]
        
        fig_pie = go.Figure(data=[
            go.Pie(
                labels=category_names,
                values=category_counts,
                marker=dict(
                    colors=px.colors.qualitative.Set2[:len(category_names)]
                ),
                textposition="auto",
                hovertemplate="<b>%{label}</b><br>%{value} runs<extra></extra>",
            )
        ])
        fig_pie.update_layout(
            title="Scenario Categories Distribution",
            height=400,
        )
        
        # Generate timing histogram (duration by category)
        durations_by_cat = []
        cat_labels = []
        
        for cat in category_names:
            durations = [duration for _, duration in categories[cat]]
            durations_by_cat.append(durations)
            cat_labels.append(f"{cat}<br>({len(durations)} runs)")
        
        fig_hist = go.Figure()
        
        for i, (cat, durations) in enumerate(zip(category_names, durations_by_cat)):
            fig_hist.add_trace(go.Box(
                y=durations,
                name=cat,
                boxmean="sd",
                hovertemplate="%{y:.0f}ms<extra></extra>",
            ))
        
        fig_hist.update_layout(
            title="Run Duration by Scenario Category",
            yaxis_title="Duration (ms)",
            height=400,
            boxmode="group",
            hovermode="y unified",
        )
        
        return {
            "category_pie": fig_pie.to_json(),
            "timing_histogram": fig_hist.to_json(),
        }

    def _get_template(self) -> any:
        """Get Jinja2 template for HTML report.
        
        Returns:
            Jinja2 template object
        """
        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Framework Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }
        
        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 20px;
            border-bottom: 2px solid #eee;
        }
        
        .summary-card {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }
        
        .summary-card h3 {
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .summary-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        
        .pass { color: #27ae60; }
        .fail { color: #e74c3c; }
        
        .section {
            padding: 30px 20px;
            border-bottom: 1px solid #eee;
        }
        
        .section h2 {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        
        .chart-container {
            background: #f9f9f9;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        
        table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        
        table td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        
        table tr:hover {
            background: #f5f5f5;
        }
        
        .cpu-idle { color: #66c2a5; font-weight: bold; }
        .cpu-low { color: #3288bd; font-weight: bold; }
        .cpu-medium { color: #fee08b; font-weight: bold; }
        .cpu-high { color: #fc8d59; font-weight: bold; }
        .cpu-critical { color: #d73027; font-weight: bold; }
        
        .status-pass { color: #27ae60; font-weight: bold; }
        .status-fail { color: #e74c3c; font-weight: bold; }
        
        .deviation-box {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        
        .deviation-error {
            background: #f8d7da;
            border-left-color: #dc3545;
        }
        
        footer {
            background: #f9f9f9;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Test Framework Report</h1>
            <p>Generated: {{ timestamp }}</p>
        </header>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Runs</h3>
                <div class="value">{{ suite_result.total_runs }}</div>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <div class="value pass">{{ "%.1f%%"|format(suite_result.pass_rate * 100) }}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value pass">{{ suite_result.passed_runs }}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value fail">{{ suite_result.failed_runs }}</div>
            </div>
            <div class="summary-card">
                <h3>Avg Memory</h3>
                <div class="value">{{ "%.0f"|format(suite_result.avg_memory_mb) }}MB</div>
            </div>
            <div class="summary-card">
                <h3>Peak Memory</h3>
                <div class="value">{{ "%.0f"|format(suite_result.peak_memory_mb) }}MB</div>
            </div>
        </div>
        
        <!-- Run List -->
        <div class="section">
            <h2>📊 Run Details</h2>
            <div class="chart-container">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Status</th>
                            <th>CPU Class</th>
                            <th>CPU (ms)</th>
                            <th>Memory (MB)</th>
                            <th>OCR Precision</th>
                            <th>Spam CPS</th>
                            <th>Window</th>
                            <th>Deviations</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for run in run_list_data %}
                        <tr>
                            <td>{{ run.run_num }}</td>
                            <td><span class="status-{% if run.passed == '✓' %}pass{% else %}fail{% endif %}">{{ run.passed }}</span></td>
                            <td><span class="cpu-{{ run.cpu_class }}">{{ run.cpu_class.upper() }}</span></td>
                            <td>{{ run.cpu_time_ms }}</td>
                            <td>{{ run.memory_mb }}</td>
                            <td>{{ run.ocr_precision }}</td>
                            <td>{{ run.spam_cps }}</td>
                            <td>{{ run.window }}</td>
                            <td>{{ run.deviations }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- CPU Distribution Pie Chart -->
        <div class="section">
            <h2>📈 CPU Load Distribution</h2>
            <div class="metric-grid">
                <div class="chart-container">
                    <div id="cpu-pie-chart" style="width: 100%;"></div>
                </div>
            </div>
        </div>
        
        <!-- Hot-spots Table -->
        <div class="section">
            <h2>🔥 Top Hot-spots (CPU > 50%)</h2>
            <div class="chart-container">
                <table>
                    <thead>
                        <tr>
                            <th>Function</th>
                            <th>CPU Time (ms)</th>
                            <th>CPU %</th>
                            <th>Occurrences</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for hot_spot in hot_spots_table %}
                        <tr>
                            <td>{{ hot_spot.function }}</td>
                            <td>{{ hot_spot.cpu_ms }}</td>
                            <td>{{ hot_spot.percent }}%</td>
                            <td>{{ hot_spot.count }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Bottleneck Timeline -->
        <div class="section">
            <h2>⚠️ Bottleneck Timeline</h2>
            <div class="chart-container">
                <div id="bottleneck-timeline" style="width: 100%;"></div>
            </div>
        </div>
        
        <!-- Memory Trend Chart -->
        <div class="section">
            <h2>💾 Memory Trend</h2>
            <div class="chart-container">
                <div id="memory-chart" style="width: 100%;"></div>
            </div>
        </div>
        
        <!-- Multi-Monitor Results -->
        {% if multi_monitor_section.has_multi_monitor %}
        <div class="section">
            <h2>🖥️ Multi-Monitor Results</h2>
            <div class="chart-container">
                <table>
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Multi-Monitor Runs</td>
                            <td>{{ multi_monitor_section.multi_monitor_runs }}</td>
                        </tr>
                        <tr>
                            <td>Avg Coordinate Transform (ms)</td>
                            <td>{{ multi_monitor_section.avg_coord_transform_ms }}</td>
                        </tr>
                        <tr>
                            <td>Total Errors</td>
                            <td>{{ multi_monitor_section.total_errors }}</td>
                        </tr>
                        <tr>
                            <td>DPI Mismatch Runs</td>
                            <td>{{ multi_monitor_section.dpi_mismatch_runs }}</td>
                        </tr>
                        <tr>
                            <td>Pass Rate</td>
                            <td>{{ multi_monitor_section.pass_rate }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        {% else %}
        <div class="section">
            <h2>🖥️ Multi-Monitor Results</h2>
            <div class="chart-container">
                <p>{{ multi_monitor_section.message }}</p>
            </div>
        </div>
        {% endif %}
        
        <!-- Deviation Summary -->
        <div class="section">
            <h2>📋 Deviation Summary</h2>
            {% if deviation_summary.deviations %}
            <div class="chart-container">
                <table>
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Count</th>
                            <th>Errors</th>
                            <th>Warnings</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for dev in deviation_summary.deviations %}
                        <tr>
                            <td>{{ dev.type }}</td>
                            <td>{{ dev.count }}</td>
                            <td>{{ dev.errors }}</td>
                            <td>{{ dev.warnings }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="chart-container">
                <p>No deviations detected.</p>
            </div>
            {% endif %}
        </div>
        
        <footer>
            <p>Test Framework Report • Generated on {{ timestamp }}</p>
        </footer>
    </div>
    
    <script>
        // Render CPU Pie Chart
        var cpuPieData = {{ cpu_pie_chart | safe }};
        Plotly.newPlot('cpu-pie-chart', cpuPieData.data, cpuPieData.layout, {responsive: true});
        
        // Render Bottleneck Timeline
        var bottleneckData = {{ bottleneck_timeline | safe }};
        Plotly.newPlot('bottleneck-timeline', bottleneckData.data, bottleneckData.layout, {responsive: true});
        
        // Render Memory Chart
        var memoryData = {{ memory_chart | safe }};
        Plotly.newPlot('memory-chart', memoryData.data, memoryData.layout, {responsive: true});
    </script>
</body>
</html>
"""
        return self.env.from_string(template_str)
