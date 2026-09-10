"""Console reporter for test framework results with formatted output and hot-spot display."""

from typing import Optional
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

from mvp.tests.test_framework.metrics import (
    RunMetrics,
    TestSuiteResult,
    CPULoadClass,
    HotSpot,
)


class ConsoleReporter:
    """Report test results to console with formatted output and metrics display."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """Initialize console reporter.
        
        Args:
            output_dir: Directory to write reports to. Defaults to current directory.
        """
        self.output_dir = output_dir or Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def format_output(self, suite_result: TestSuiteResult) -> str:
        """Format test results as ASCII table with metrics and anomalies flagged.
        
        **Validates: Requirements 4.1.1**
        
        Produces readable ASCII table with:
        - Run pass/fail status (✓/✗)
        - CPU class and usage
        - Scenario configuration
        - Key metrics (OCR, clicks, spam CPS)
        - Anomalies flagged with ⚠️
        
        Args:
            suite_result: TestSuiteResult with all aggregated metrics
            
        Returns:
            Formatted ASCII table as string
        """
        if not suite_result.runs:
            return "No runs to display."
        
        # Build table data
        table_data = []
        headers = ["#", "Status", "CPU", "Scenario", "OCR", "Clicks", "Spam CPS", "Memory", "Anomalies"]
        
        for i, run in enumerate(suite_result.runs, 1):
            status = "✓" if run.passed else "✗"
            cpu_class = run.cpu_load_class.value.upper()
            scenario = f"{run.scenario_id}"
            ocr = f"{run.ocr_precision:.0%}"
            clicks = str(run.click_count) if run.click_count > 0 else "-"
            spam_cps = f"{run.spam_cps:.1f}" if run.spam_cps > 0 else "-"
            memory = f"{run.memory_mb:.0f}MB"
            
            # Flag anomalies
            anomalies = []
            if run.deviations:
                for deviation in run.deviations:
                    if deviation.severity == "error":
                        anomalies.append("⚠️")
                        break
            anomaly_str = " ".join(anomalies) if anomalies else ""
            
            table_data.append([
                i,
                status,
                cpu_class,
                scenario,
                ocr,
                clicks,
                spam_cps,
                memory,
                anomaly_str,
            ])
        
        # Generate table using tabulate
        table_str = tabulate(
            table_data,
            headers=headers,
            tablefmt="grid",
            stralign="center",
            numalign="right",
        )
        
        return table_str

    def detect_bottlenecks(self, suite_result: TestSuiteResult) -> str:
        """Identify and report bottlenecks with suggestions.
        
        **Validates: Requirements 4.1.2**
        
        Detects:
        - CPU spikes (>70%)
        - Timing anomalies (reaction latency >100ms)
        - Accuracy deviations (click >100px, OCR <85%, accuracy <95%)
        
        Highlights bottlenecks and suggests root causes.
        
        Args:
            suite_result: TestSuiteResult with all aggregated metrics
            
        Returns:
            Summary of anomalies with suggestions
        """
        bottleneck_report = []
        
        # Track anomalies by type
        cpu_spikes = []
        timing_issues = []
        accuracy_issues = []
        
        for run in suite_result.runs:
            # CPU spikes
            cpu_percent = (run.cpu_time_ms / run.duration_ms * 100) if run.duration_ms > 0 else 0
            if cpu_percent > 70.0:
                cpu_spikes.append((run.run_id, cpu_percent))
            
            # Reaction latency anomalies
            if run.reaction_latency_ms > 100.0:
                timing_issues.append((run.run_id, run.reaction_latency_ms))
            
            # Accuracy deviations
            if run.click_count > 0 and run.click_avg_deviation_px > 100.0:
                accuracy_issues.append(("click_deviation", run.run_id, run.click_avg_deviation_px))
            if run.ocr_detections > 0 and run.ocr_precision < 0.85:
                accuracy_issues.append(("ocr_precision", run.run_id, run.ocr_precision))
        
        # Report CPU spikes
        if cpu_spikes:
            bottleneck_report.append("\n🔴 CPU SPIKES (>70%):")
            for run_id, cpu_percent in cpu_spikes:
                bottleneck_report.append(f"  Run #{run_id}: {cpu_percent:.1f}%")
                bottleneck_report.append("    → Suggest: Reduce frame capture frequency or optimize OCR")
        
        # Report timing anomalies
        if timing_issues:
            bottleneck_report.append("\n⏱️ TIMING ANOMALIES (latency >100ms):")
            for run_id, latency in timing_issues:
                bottleneck_report.append(f"  Run #{run_id}: {latency:.1f}ms")
                bottleneck_report.append("    → Suggest: Check OCR detection pipeline or macro step delays")
        
        # Report accuracy deviations
        if accuracy_issues:
            bottleneck_report.append("\n📊 ACCURACY DEVIATIONS:")
            for issue_type, run_id, value in accuracy_issues:
                if issue_type == "click_deviation":
                    bottleneck_report.append(f"  Run #{run_id}: Click deviation {value:.1f}px (threshold 100px)")
                    bottleneck_report.append("    → Suggest: Check DPI settings or click timing jitter")
                elif issue_type == "ocr_precision":
                    bottleneck_report.append(f"  Run #{run_id}: OCR precision {value:.1%} (threshold 85%)")
                    bottleneck_report.append("    → Suggest: Verify image quality or OCR confidence thresholds")
        
        if not bottleneck_report:
            bottleneck_report.append("✅ No bottlenecks detected - all metrics within acceptable ranges")
        
        return "\n".join(bottleneck_report)

    def format_error_summary(self, suite_result: TestSuiteResult) -> str:
        """Format error summary with categorization by type.
        
        **Validates: Requirements 4.1.3**
        
        Lists all failed runs, categorized by error reason:
        - CPU anomalies
        - OCR failures
        - Click inaccuracies
        - Timing issues
        - Other deviations
        
        Includes counts and example-driven breakdown.
        
        Args:
            suite_result: TestSuiteResult with all aggregated metrics
            
        Returns:
            Error breakdown section with counts and examples
        """
        error_report = []
        
        # Categorize errors by type
        error_categories = {
            "cpu_high": [],
            "ocr_precision": [],
            "click_deviation": [],
            "timing": [],
            "other": [],
        }
        
        failed_runs = [r for r in suite_result.runs if not r.passed]
        
        if not failed_runs:
            return "✅ All runs passed - no errors to report."
        
        # Categorize each failed run
        for run in failed_runs:
            categorized = False
            
            for deviation in run.deviations:
                if deviation.type == "cpu_high":
                    error_categories["cpu_high"].append((run.run_id, deviation))
                    categorized = True
                elif deviation.type == "ocr_precision":
                    error_categories["ocr_precision"].append((run.run_id, deviation))
                    categorized = True
                elif deviation.type == "click_deviation":
                    error_categories["click_deviation"].append((run.run_id, deviation))
                    categorized = True
            
            # Check for timing issues
            if run.reaction_latency_ms > 100.0 and not categorized:
                error_categories["timing"].append((run.run_id, f"Reaction latency {run.reaction_latency_ms:.1f}ms"))
                categorized = True
            
            # If no specific deviation, categorize as other
            if not categorized:
                error_categories["other"].append((run.run_id, "Test failed - unclassified error"))
        
        # Report errors by category
        error_report.append(f"\n❌ ERROR SUMMARY ({len(failed_runs)} failed runs)")
        error_report.append("=" * 60)
        
        for category, errors in error_categories.items():
            if errors:
                category_name = {
                    "cpu_high": "🔴 CPU Anomalies",
                    "ocr_precision": "📖 OCR Failures",
                    "click_deviation": "🖱️ Click Inaccuracies",
                    "timing": "⏱️ Timing Issues",
                    "other": "❓ Other Errors",
                }.get(category, category)
                
                error_report.append(f"\n{category_name} ({len(errors)} runs):")
                
                # Show first 3 examples
                for run_id, error_info in errors[:3]:
                    if isinstance(error_info, str):
                        error_report.append(f"  • Run #{run_id}: {error_info}")
                    else:
                        # It's a Deviation object
                        error_report.append(f"  • Run #{run_id}: {error_info.message}")
                
                if len(errors) > 3:
                    error_report.append(f"  ... and {len(errors) - 3} more")
        
        return "\n".join(error_report)

    def report_run(self, run_num: int, scenario, metrics: RunMetrics) -> None:
        """Print single run summary with metrics and hot-spots.
        
        Args:
            run_num: Run number (1-indexed)
            scenario: Scenario object with window and monitor configuration
            metrics: RunMetrics for this run
        """
        # Header line: "Run #1: 1024x768 @ (448,136) [Monitor 0, 96 DPI] Timer=300s"
        header = self._format_header(run_num, scenario, metrics)
        print(header)
        
        # Result: "✓ PASS" or "✗ FAIL"
        result_str = "✓ PASS" if metrics.passed else "✗ FAIL"
        print(f"{result_str}")
        
        # Metrics
        self._print_metrics(metrics, scenario)
        
        # Hot-spots (only when cpu > 50%)
        if metrics.cpu_load_class in (CPULoadClass.HIGH, CPULoadClass.CRITICAL):
            self._print_hot_spots(metrics)
        
        # Deviations (if any)
        if metrics.deviations:
            self._print_deviations(metrics)
        
        print()  # Blank line after each run

    def report_suite(self, suite_result: TestSuiteResult) -> None:
        """Print overall suite summary with aggregated statistics.
        
        Args:
            suite_result: TestSuiteResult for the entire suite
        """
        print("\n" + "=" * 80)
        print("SUITE SUMMARY")
        print("=" * 80)
        
        # Total runs and pass rate
        print(f"\nTotal runs: {suite_result.total_runs}")
        print(f"Passed: {suite_result.passed_runs}")
        print(f"Failed: {suite_result.failed_runs}")
        print(f"Pass rate: {suite_result.pass_rate:.1%}")
        
        # Overall CPU distribution
        print("\nCPU Load Distribution:")
        cpu_dist = self._calculate_cpu_distribution(suite_result)
        for load_class in ["IDLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            count = cpu_dist.get(load_class, 0)
            percent = (count / suite_result.total_runs * 100) if suite_result.total_runs > 0 else 0
            print(f"  {load_class:10}: {count:3} runs ({percent:5.1f}%)")
        
        # Aggregate hot-spots across all runs (when cpu > 50%)
        print("\nAggregate Hot-spots (CPU > 50%):")
        hot_spots_agg = self._aggregate_hot_spots(suite_result)
        if hot_spots_agg:
            for func_name, total_ms, total_percent, count in hot_spots_agg:
                avg_percent = total_percent / count if count > 0 else 0
                print(f"  {func_name:40} {total_ms:8.1f}ms ({avg_percent:5.1f}% avg)")
        else:
            print("  (None detected)")
        
        # Memory trend
        print("\nMemory Statistics:")
        print(f"  Average: {suite_result.avg_memory_mb:.1f}MB")
        print(f"  Peak: {suite_result.peak_memory_mb:.1f}MB")
        
        # CPU load distribution (string summary)
        if suite_result.cpu_load_distribution:
            print("\nCPU Load Classes:")
            for load_class, count in sorted(suite_result.cpu_load_distribution.items()):
                print(f"  {load_class}: {count}")
        
        # Bottleneck summary
        if suite_result.bottleneck_summary:
            print("\nBottleneck Summary:")
            for bottleneck_desc in suite_result.bottleneck_summary:
                print(f"  - {bottleneck_desc}")
        
        print("\n" + "=" * 80 + "\n")

    def _format_header(self, run_num: int, scenario, metrics: RunMetrics) -> str:
        """Format run header line.
        
        Example: "Run #1: 1024x768 @ (448,136) [Monitor 0, 96 DPI] Timer=300s"
        
        Args:
            run_num: Run number
            scenario: Scenario object
            metrics: RunMetrics
            
        Returns:
            Formatted header string
        """
        size_str = f"{scenario.window_width}x{scenario.window_height}"
        pos_str = f"({scenario.window_x},{scenario.window_y})"
        
        # Monitor info
        monitor_id = 0
        dpi = scenario.dpi
        if scenario.monitors and len(scenario.monitors) > 0:
            # Find which monitor contains this window
            for mon in scenario.monitors:
                if (scenario.window_x >= mon.offset_x and
                    scenario.window_x < mon.offset_x + mon.width):
                    monitor_id = mon.id
                    dpi = mon.dpi
                    break
        
        monitor_str = f"[Monitor {monitor_id}, {dpi} DPI]"
        timer_str = f"Timer={scenario.timer_seconds}s"
        
        return f"Run #{run_num}: {size_str} @ {pos_str} {monitor_str} {timer_str}"

    def _print_metrics(self, metrics: RunMetrics, scenario) -> None:
        """Print formatted metrics section.
        
        Args:
            metrics: RunMetrics object
            scenario: Scenario object
        """
        # Clicks
        if metrics.click_count > 0:
            print(f"Clicks: {metrics.click_count} (avg +{metrics.click_avg_deviation_px:.1f}px)")
        
        # OCR
        if metrics.ocr_detections > 0:
            ocr_percent = metrics.ocr_precision * 100
            print(f"OCR: {ocr_percent:.0f}% precision ({metrics.ocr_detections} detections)")
        
        # Timer
        if "WAIT_FOR_TIMER" in metrics.macro_step_latency_ms:
            timer_latency = metrics.macro_step_latency_ms["WAIT_FOR_TIMER"]
            expected_timer = scenario.timer_seconds
            error_percent = ((timer_latency / 1000 - expected_timer) / expected_timer * 100)
            print(f"Timer: {timer_latency/1000:.1f}s (expected {expected_timer}s, {error_percent:+.1f}%)")
        
        # Spam
        if metrics.spam_click_count > 0:
            print(f"Spam: {metrics.spam_cps:.1f} CPS ({metrics.spam_click_count}/{metrics.spam_click_count} clicks)")
        
        # CPU and Memory
        print(f"CPU: {metrics.cpu_time_ms:.0f}ms ({metrics.cpu_load_class.value.upper()})")
        print(f"Memory: {metrics.memory_mb:.0f}MB")

    def _print_hot_spots(self, metrics: RunMetrics) -> None:
        """Print hot-spots section (only when CPU > 50%).
        
        Args:
            metrics: RunMetrics object
        """
        if not metrics.hot_spots:
            return
        
        print("\nHot-spots:")
        for hot_spot in metrics.hot_spots[:5]:  # Top 5 hot-spots
            print(f"  {hot_spot.function_name:40} {hot_spot.cpu_time_ms:8.1f}ms ({hot_spot.percent:5.1f}%)")

    def _print_deviations(self, metrics: RunMetrics) -> None:
        """Print deviations section.
        
        Args:
            metrics: RunMetrics object
        """
        if not metrics.deviations:
            return
        
        print("\nDeviations:")
        for deviation in metrics.deviations:
            severity_icon = "⚠️" if deviation.severity == "warning" else "❌"
            print(f"  {severity_icon} {deviation.type}: {deviation.message}")

    def _calculate_cpu_distribution(self, suite_result: TestSuiteResult) -> dict[str, int]:
        """Calculate CPU load class distribution across all runs.
        
        Args:
            suite_result: TestSuiteResult
            
        Returns:
            Dictionary mapping load class names to counts
        """
        distribution = {
            "IDLE": 0,
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0,
        }
        
        for run in suite_result.runs:
            class_name = run.cpu_load_class.value.upper()
            if class_name in distribution:
                distribution[class_name] += 1
        
        return distribution

    def _aggregate_hot_spots(self, suite_result: TestSuiteResult) -> list[tuple[str, float, float, int]]:
        """Aggregate hot-spots across all runs.
        
        Only includes hot-spots from runs with cpu > 50% (HIGH or CRITICAL).
        
        Args:
            suite_result: TestSuiteResult
            
        Returns:
            List of (function_name, total_cpu_ms, total_percent, count) tuples,
            sorted by total CPU time descending, limited to top 10.
        """
        hot_spot_map: dict[str, tuple[float, float, int]] = {}  # function_name -> (total_ms, total_percent, count)
        
        for run in suite_result.runs:
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
        result = [
            (func_name, total_ms, total_percent, count)
            for func_name, (total_ms, total_percent, count) in hot_spot_map.items()
        ]
        result.sort(key=lambda x: x[1], reverse=True)
        
        return result[:10]  # Top 10 hot-spots

    def generate_report(self, suite_result: TestSuiteResult) -> str:
        """Generate full console report with all sections.
        
        **Validates: Requirements 4.1.1**
        
        Combines all report sections into a comprehensive output:
        1. Header with pass rate and suite metrics
        2. Per-run summary table
        3. Aggregate statistics and CPU distribution
        4. Bottleneck section with root cause suggestions
        5. Error summary with categorization
        
        Args:
            suite_result: TestSuiteResult with all aggregated metrics
            
        Returns:
            Complete report as formatted string
        """
        report_parts = []
        
        # Header section
        report_parts.append("=" * 80)
        report_parts.append("TEST SUITE REPORT")
        report_parts.append("=" * 80)
        
        # Overall metrics
        report_parts.append(f"\nTest Results: {suite_result.passed_runs}/{suite_result.total_runs} passed")
        report_parts.append(f"Pass Rate: {suite_result.pass_rate:.1%}")
        
        # Per-run summary
        report_parts.append("\n" + "=" * 80)
        report_parts.append("PER-RUN SUMMARY")
        report_parts.append("=" * 80)
        report_parts.append(self.format_output(suite_result))
        
        # Aggregate statistics
        report_parts.append("\n" + "=" * 80)
        report_parts.append("AGGREGATE STATISTICS")
        report_parts.append("=" * 80)
        
        # CPU distribution
        report_parts.append("\nCPU Load Distribution:")
        cpu_dist = self._calculate_cpu_distribution(suite_result)
        for load_class in ["IDLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            count = cpu_dist.get(load_class, 0)
            percent = (count / suite_result.total_runs * 100) if suite_result.total_runs > 0 else 0
            bar_length = int(percent / 2)
            bar = "█" * bar_length + "░" * (50 - bar_length)
            report_parts.append(f"  {load_class:10} [{bar}] {count:3} runs ({percent:5.1f}%)")
        
        # Click accuracy (if available)
        total_clicks = sum(r.click_count for r in suite_result.runs)
        if total_clicks > 0:
            accurate_clicks = sum(
                r.click_count * (r.click_metrics.accuracy_ratio if r.click_metrics else 1.0)
                for r in suite_result.runs
            )
            click_accuracy = accurate_clicks / total_clicks
            report_parts.append(f"\nClick Accuracy: {click_accuracy:.1%} ({int(accurate_clicks)}/{total_clicks} clicks)")
        
        # OCR precision (if available)
        runs_with_ocr = [r for r in suite_result.runs if r.ocr_detections > 0]
        if runs_with_ocr:
            avg_ocr = sum(r.ocr_precision for r in runs_with_ocr) / len(runs_with_ocr)
            report_parts.append(f"OCR Precision: {avg_ocr:.1%} (avg across {len(runs_with_ocr)} runs)")
        
        # Spam CPS statistics
        spam_runs = [r for r in suite_result.runs if r.spam_cps > 0]
        if spam_runs:
            avg_cps = sum(r.spam_cps for r in spam_runs) / len(spam_runs)
            report_parts.append(f"Spam CPS: {avg_cps:.1f} avg (AGENTS.md limit: 38.46 CPS)")
        
        # Memory statistics
        report_parts.append(f"\nMemory Statistics:")
        report_parts.append(f"  Average: {suite_result.avg_memory_mb:.1f}MB")
        report_parts.append(f"  Peak: {suite_result.peak_memory_mb:.1f}MB")
        
        # Bottleneck section
        report_parts.append("\n" + "=" * 80)
        report_parts.append("BOTTLENECK DETECTION & ROOT CAUSES")
        report_parts.append("=" * 80)
        report_parts.append(self.detect_bottlenecks(suite_result))
        
        # Error summary
        report_parts.append("\n" + "=" * 80)
        report_parts.append("ERROR SUMMARY")
        report_parts.append("=" * 80)
        report_parts.append(self.format_error_summary(suite_result))
        
        # Footer
        report_parts.append("\n" + "=" * 80)
        
        return "\n".join(report_parts)

    def save_report(self, suite_result: TestSuiteResult, filename: Optional[str] = None) -> Path:
        """Generate and save full console report to file.
        
        Args:
            suite_result: TestSuiteResult with all aggregated metrics
            filename: Optional custom filename. Defaults to console_report_{timestamp}.txt
            
        Returns:
            Path to saved report file
        """
        report = self.generate_report(suite_result)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"console_report_{timestamp}.txt"
        
        report_path = self.output_dir / filename
        report_path.write_text(report, encoding="utf-8")
        
        return report_path
