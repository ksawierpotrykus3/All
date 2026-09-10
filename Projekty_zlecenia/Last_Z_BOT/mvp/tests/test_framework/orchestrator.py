"""Test orchestrator with adaptive sampling for hybrid macro integration tests."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import subprocess
import threading
import time
import logging
import queue

from mvp.tests.test_framework.metrics import (
    CPULoadClass,
    MetricsCollector,
    RunMetrics,
    TestSuiteResult,
    Deviation,
)
from mvp.tests.test_framework.scenarios import Scenario, ScenarioRandomizer
from mvp.tests.test_framework.cpu_profiler import CPUProfiler
from mvp.tests.test_framework.process_manager import ProcessManager, ProcessResult

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for test orchestrator."""

    max_runs: int = 50  # Maximum total number of runs
    timeout_per_run: float = 15.0  # Maximum time per run in seconds
    target_pass_rate: float = 0.95  # Target pass rate (95%)
    baseline_run_count: int = 10  # Number of baseline runs
    sampling_run_count: int = 10  # Number of adaptive sampling runs
    cpu_critical_threshold: int = 5  # Allow up to N CRITICAL CPU runs before diagnostics
    min_pass_rate_before_sampling: float = 0.95  # Min pass rate to proceed to sampling


class Orchestrator:
    """Orchestrator for adaptive sampling of test scenarios."""

    def __init__(
        self,
        config: OrchestratorConfig,
        scenario_randomizer: ScenarioRandomizer,
        process_manager: Optional[ProcessManager] = None,
        csharp_exe_path: Optional[str] = None,
    ) -> None:
        """Initialize test orchestrator.

        Args:
            config: Orchestrator configuration
            scenario_randomizer: ScenarioRandomizer for generating scenarios
            process_manager: Optional ProcessManager for subprocess handling
            csharp_exe_path: Optional path to C# stub window executable
        """
        self.config = config
        self.scenario_randomizer = scenario_randomizer
        self.process_manager = process_manager or ProcessManager()
        self.csharp_exe_path = csharp_exe_path
        self._run_count = 0
        self._all_runs: list[RunMetrics] = []
        self.logger = logger

    def run_suite(self) -> TestSuiteResult:
        """Run full test suite with adaptive sampling.

        Returns:
            TestSuiteResult with aggregated metrics and results from all phases
        """
        suite_start_time = time.perf_counter()

        # Phase 1: Baseline (10 runs, single-monitor, full-size)
        baseline_runs = self._run_baseline_phase()
        self._all_runs.extend(baseline_runs)

        # Phase 2: Adaptive decision
        baseline_stats = self._compute_statistics(baseline_runs)
        pass_rate = baseline_stats["pass_rate"]
        cpu_critical_count = baseline_stats["cpu_critical_count"]

        additional_runs: list[RunMetrics] = []

        # If baseline pass rate is low or CPU is high, spawn additional runs
        if (
            pass_rate < self.config.min_pass_rate_before_sampling
            or cpu_critical_count > self.config.cpu_critical_threshold
        ):
            additional_runs = self._run_additional_runs(count=10)
            self._all_runs.extend(additional_runs)

        # Phase 2b: Adaptive diagnostic sampling
        # Check pass_rate after baseline/additional runs
        all_runs_so_far = self._all_runs
        current_stats = self._compute_statistics(all_runs_so_far)
        current_pass_rate = current_stats["pass_rate"]

        diagnostic_runs: list[RunMetrics] = []

        # If pass_rate falls below 0.8 (80%), spawn 5 diagnostic runs with extended profiling
        if current_pass_rate < 0.8:
            self.logger.info(
                f"Pass rate ({current_pass_rate:.1%}) below 80% threshold, spawning 5 diagnostic runs"
            )
            # Use next scenario for diagnostics
            diagnostic_scenario = self.scenario_randomizer.next_scenario()

            diagnostic_runs = self._spawn_diagnostic_runs(diagnostic_scenario, count=5)
            self._all_runs.extend(diagnostic_runs)

        # Phase 3: Sampling phase (multi-monitor, clipped, edge cases)
        sampling_runs = self._run_sampling_phase()
        self._all_runs.extend(sampling_runs)

        # Aggregate all results
        suite_duration_s = time.perf_counter() - suite_start_time

        return self._aggregate_results(suite_duration_s)

    def run_single_test(
        self,
        scenario: Scenario,
        timeout_s: float = 60.0,
    ) -> RunMetrics:
        """Execute single test scenario orchestrating both C# window and bot MVP.

        Launches C# stub window with scenario config, waits for ready signal,
        launches bot MVP process, monitors execution with timeout enforcement,
        and collects logs from both processes.

        Process flow:
        1. Launch C# stub window with scenario configuration (2-3s)
        2. Wait for C# window ready signal (up to 5s)
        3. Launch bot MVP process (3-5s)
        4. Monitor both processes with 60s hard timeout
        5. Collect logs from both within 5s of termination

        Args:
            scenario: Test scenario to execute
            timeout_s: Hard timeout limit per run (default 60s)

        Returns:
            RunMetrics with collected data from run

        Raises:
            RuntimeError: If critical process failures occur (window not found, etc.)
        """
        start_time = time.perf_counter()
        csharp_process = None
        bot_process = None
        
        # Thread-safe queues for storing results from monitor threads
        csharp_result_queue: queue.Queue = queue.Queue(maxsize=1)
        bot_result_queue: queue.Queue = queue.Queue(maxsize=1)

        try:
            # Phase 1: Launch C# stub window with scenario configuration
            if self.csharp_exe_path:
                self.logger.info(f"Launching C# stub window for scenario {scenario.id}")
                csharp_process, csharp_pid = self._spawn_csharp_window(scenario)
                self.logger.info(f"C# window launched (PID {csharp_pid})")
            else:
                self.logger.warning("C# executable path not configured; skipping C# window")

            # Phase 2: Launch bot MVP process
            self.logger.info(f"Launching bot MVP for scenario {scenario.id}")
            bot_process, bot_pid = self._spawn_bot_mvp()
            self.logger.info(f"Bot MVP launched (PID {bot_pid})")

            # Phase 3: Monitor both processes with timeout enforcement
            # Run in parallel to reduce total execution time
            csharp_thread = None
            bot_thread = None

            if csharp_process:
                csharp_thread = threading.Thread(
                    target=self._monitor_csharp_process,
                    args=(csharp_process, timeout_s, csharp_result_queue),
                    daemon=False,
                )
                csharp_thread.start()

            if bot_process:
                bot_thread = threading.Thread(
                    target=self._monitor_bot_process,
                    args=(bot_process, timeout_s, bot_result_queue),
                    daemon=False,
                )
                bot_thread.start()

            # Wait for both threads to complete
            csharp_result = None
            bot_result = None

            if csharp_thread:
                csharp_thread.join()
                try:
                    csharp_result = csharp_result_queue.get(timeout=1.0)
                except queue.Empty:
                    self.logger.warning("C# result queue empty after thread join")

            if bot_thread:
                bot_thread.join()
                try:
                    bot_result = bot_result_queue.get(timeout=1.0)
                except queue.Empty:
                    self.logger.warning("Bot result queue empty after thread join")

            # Phase 4: Collect logs from both processes within 5s
            log_start = time.perf_counter()
            all_logs = self._collect_all_logs()
            log_duration = time.perf_counter() - log_start
            self.logger.info(f"Logs collected in {log_duration:.2f}s")

            # Phase 5: Create metrics from collected data
            metrics = self._create_metrics_from_logs(scenario, all_logs, csharp_result, bot_result)
            metrics.run_id = self._run_count

            duration_s = time.perf_counter() - start_time
            metrics.duration_ms = duration_s * 1000.0

            self.logger.info(
                f"Scenario {scenario.id} completed in {duration_s:.2f}s, passed={metrics.passed}"
            )

            return metrics

        except Exception as e:
            # Handle failure - create failed metrics
            self.logger.error(f"Error in run_single_test for {scenario.id}: {e}", exc_info=True)

            # Ensure processes are terminated
            if csharp_process and csharp_process.poll() is None:
                self.logger.warning(f"Force-terminating C# process {csharp_process.pid}")
                self.process_manager._terminate_process(csharp_process, force_kill=True)
            if bot_process and bot_process.poll() is None:
                self.logger.warning(f"Force-terminating bot process {bot_process.pid}")
                self.process_manager._terminate_process(bot_process, force_kill=True)

            # Return failed metrics
            metrics = RunMetrics(
                run_id=self._run_count,
                scenario_id=scenario.id,
                passed=False,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=0.0,
            )
            metrics.duration_ms = (time.perf_counter() - start_time) * 1000.0
            return metrics

    def _spawn_csharp_window(self, scenario: Scenario) -> Tuple:
        """Spawn C# stub window process with scenario configuration.

        Builds command-line arguments from scenario parameters, spawns executable,
        waits for window to appear.

        Args:
            scenario: Test scenario

        Returns:
            Tuple of (process, pid)

        Raises:
            RuntimeError: If executable not found or window spawn fails
        """
        if not self.csharp_exe_path:
            raise RuntimeError("C# executable path not configured")

        process, pid = self.process_manager.spawn_csharp_window(
            scenario,
            self.csharp_exe_path,
            timeout_s=5.0,
        )
        return process, pid

    def _spawn_bot_mvp(self) -> Tuple:
        """Spawn bot MVP process via uv.

        Launches: uv run python mvp/main.py
        Inherits current environment.

        Returns:
            Tuple of (process, pid)

        Raises:
            RuntimeError: If bot process cannot start
        """
        process, pid = self.process_manager.spawn_bot_mvp(timeout_s=15.0)
        return process, pid

    def _monitor_csharp_process(
        self,
        process: subprocess.Popen,
        timeout_s: float = 60.0,
        result_queue: Optional[queue.Queue] = None,
    ) -> None:
        """Monitor C# stub window process with timeout enforcement.

        Runs in separate thread. Enforces timeout and stores result in thread-safe queue.

        Args:
            process: C# process to monitor
            timeout_s: Hard timeout limit
            result_queue: Thread-safe queue for storing ProcessResult
        """
        try:
            result = self.process_manager.enforce_timeout(process, timeout_s)
            if result_queue:
                result_queue.put(result)
            if result.timed_out:
                self.logger.warning(f"C# process timed out after {timeout_s}s")
            else:
                self.logger.info(f"C# process completed (exit code: {result.exit_code})")
        except Exception as e:
            self.logger.error(f"Error monitoring C# process: {e}")
            if result_queue:
                result_queue.put(None)

    def _monitor_bot_process(
        self,
        process: subprocess.Popen,
        timeout_s: float = 60.0,
        result_queue: Optional[queue.Queue] = None,
    ) -> None:
        """Monitor bot MVP process with timeout enforcement.

        Runs in separate thread. Enforces timeout and stores result in thread-safe queue.

        Args:
            process: Bot process to monitor
            timeout_s: Hard timeout limit
            result_queue: Thread-safe queue for storing ProcessResult
        """
        try:
            result = self.process_manager.enforce_timeout(process, timeout_s)
            if result_queue:
                result_queue.put(result)
            if result.timed_out:
                self.logger.warning(f"Bot process timed out after {timeout_s}s")
            else:
                self.logger.info(f"Bot process completed (exit code: {result.exit_code})")
        except Exception as e:
            self.logger.error(f"Error monitoring bot process: {e}")
            if result_queue:
                result_queue.put(None)

    def _collect_all_logs(self) -> Dict[str, str]:
        """Collect log files from work directory within 5s timeout.

        Attempts to collect game_events.log (from C#) and event_log (from bot).

        Returns:
            Dictionary with collected logs
        """
        return self.process_manager.collect_logs(timeout_s=5.0)

    def _create_metrics_from_logs(
        self,
        scenario: Scenario,
        logs: Dict[str, str],
        csharp_result: Optional[ProcessResult] = None,
        bot_result: Optional[ProcessResult] = None,
    ) -> RunMetrics:
        """Create metrics from collected logs and process results.

        Parses logs and extracts metrics. If logs are missing, returns failed metrics.

        Args:
            scenario: Test scenario
            logs: Collected log files
            csharp_result: Optional ProcessResult from C# process
            bot_result: Optional ProcessResult from bot process

        Returns:
            RunMetrics instance
        """
        # Determine pass/fail based on log availability and process results
        has_csharp_logs = bool(logs.get("game_events"))
        has_bot_logs = bool(logs.get("event_log"))
        
        # Run passes if we got at least one log and neither process timed out
        csharp_timed_out = csharp_result and csharp_result.timed_out
        bot_timed_out = bot_result and bot_result.timed_out
        
        # Pass if we have at least game_events log and no timeout
        passed = has_csharp_logs and not csharp_timed_out and not bot_timed_out

        # Parse logs if available
        click_count = 0
        click_deviation = 0.0
        ocr_detections = 0
        ocr_precision = 0.0
        parse_errors: list[str] = []

        if has_csharp_logs:
            # Parse game_events.log (CSV format)
            try:
                click_count = self._parse_click_count(logs["game_events"])
            except Exception as e:
                error_msg = f"Error parsing game_events log: {e}"
                self.logger.warning(error_msg)
                parse_errors.append(error_msg)

        if has_bot_logs:
            # Parse event_log (bot decisions and detections)
            try:
                ocr_detections, ocr_precision = self._parse_ocr_metrics(logs["event_log"])
            except Exception as e:
                error_msg = f"Error parsing event_log: {e}"
                self.logger.warning(error_msg)
                parse_errors.append(error_msg)

        # Classify run status
        classification = "passed"
        if parse_errors:
            classification = "failed_parse"
        elif not has_csharp_logs or not has_bot_logs:
            classification = "failed_missing"
        elif csharp_timed_out or bot_timed_out:
            classification = "failed_missing"
        elif not passed:
            classification = "partial"

        # Create metrics
        metrics = RunMetrics(
            run_id=0,
            scenario_id=scenario.id,
            passed=passed,
            click_count=click_count,
            click_avg_deviation_px=click_deviation,
            ocr_detections=ocr_detections,
            ocr_precision=ocr_precision,
            cpu_load_class=CPULoadClass.MEDIUM,
            memory_mb=100.0,
            parse_errors=parse_errors,
            classification=classification,
        )

        # Add process-level metrics if available
        if csharp_result:
            metrics.deviations.append(
                Deviation(
                    type="csharp_process",
                    severity="info",
                    message=f"C# exit code: {csharp_result.exit_code}, timed_out: {csharp_result.timed_out}",
                )
            )

        if bot_result:
            metrics.deviations.append(
                Deviation(
                    type="bot_process",
                    severity="info",
                    message=f"Bot exit code: {bot_result.exit_code}, timed_out: {bot_result.timed_out}",
                )
            )

        return metrics

    def _parse_click_count(self, game_events_log: str) -> int:
        """Parse game_events.log and count clicks.

        Expects CSV format: timestamp_ms,x,y,element_name,event_type

        Args:
            game_events_log: Raw log content

        Returns:
            Count of click events
        """
        click_count = 0
        for line in game_events_log.strip().split("\n"):
            if not line.strip() or line.startswith("timestamp"):
                continue
            try:
                parts = line.split(",")
                if len(parts) >= 5 and parts[4].strip() == "click":
                    click_count += 1
            except Exception:
                continue
        return click_count

    def _parse_ocr_metrics(self, event_log: str) -> Tuple[int, float]:
        """Parse event_log and extract OCR metrics.

        Expects format: [HH:MM:SS.mmm] TYPE: message

        Args:
            event_log: Raw bot event log

        Returns:
            Tuple of (total_detections, precision)
        """
        detections = 0
        correct_detections = 0

        for line in event_log.strip().split("\n"):
            if not line.strip():
                continue

            if "OCR Detection" in line:
                detections += 1
                if "confidence=" in line:
                    try:
                        conf_str = line.split("confidence=")[1].split()[0]
                        confidence = float(conf_str)
                        if confidence >= 0.85:
                            correct_detections += 1
                    except (ValueError, IndexError):
                        pass

        precision = correct_detections / detections if detections > 0 else 0.0
        return detections, precision

    def _spawn_diagnostic_runs(self, scenario: Scenario, count: int = 5) -> list[RunMetrics]:
        """Spawn diagnostic runs for detailed analysis.

        Spawns additional runs with extended CPU profiling when pass rate drops below 80%.

        Args:
            scenario: Failed scenario to diagnose
            count: Number of diagnostic runs (default 5)

        Returns:
            List of RunMetrics from diagnostic runs
        """
        diagnostic_runs = []

        for i in range(count):
            self.logger.info(f"Running diagnostic run {i+1}/{count} for scenario {scenario.id}")

            # Run with extended profiling (same as _spawn_diagnostic_run)
            metrics = self._spawn_diagnostic_run(scenario)
            metrics.run_id = self._run_count
            self._run_count += 1
            diagnostic_runs.append(metrics)

        return diagnostic_runs

    def _run_baseline_phase(self) -> list[RunMetrics]:
        """Run baseline phase: 10 single-monitor full-size runs.

        Returns:
            List of RunMetrics from baseline phase
        """
        baseline_scenarios = self._create_baseline_scenarios()
        baseline_runs = []

        for i, scenario in enumerate(baseline_scenarios):
            # Use run_single_test for full orchestration if csharp_exe_path is set
            # Otherwise fall back to mock scenario execution
            if self.csharp_exe_path:
                metrics = self.run_single_test(scenario)
            else:
                metrics = self._run_single_scenario(scenario)
                metrics.run_id = self._run_count
            self._run_count += 1
            baseline_runs.append(metrics)

        return baseline_runs

    def _run_additional_runs(self, count: int = 10) -> list[RunMetrics]:
        """Run additional diagnostic runs if baseline failed or CPU was high.

        Args:
            count: Number of additional runs to execute

        Returns:
            List of RunMetrics from additional runs
        """
        additional_runs = []

        for _ in range(count):
            scenario = self.scenario_randomizer.next_scenario()
            metrics = self._run_single_scenario(scenario)
            metrics.run_id = self._run_count
            self._run_count += 1
            additional_runs.append(metrics)

        return additional_runs

    def _run_sampling_phase(self) -> list[RunMetrics]:
        """Run sampling phase: multi-monitor, clipped, edge cases.

        Returns:
            List of RunMetrics from sampling phase
        """
        sampling_runs = []

        for _ in range(self.config.sampling_run_count):
            scenario = self.scenario_randomizer.next_scenario()
            metrics = self._run_single_scenario(scenario)
            metrics.run_id = self._run_count
            self._run_count += 1
            sampling_runs.append(metrics)

        return sampling_runs

    def _run_single_scenario(self, scenario: Scenario) -> RunMetrics:
        """Execute single test scenario.

        Args:
            scenario: Scenario to execute

        Returns:
            RunMetrics with collected data from run
        """
        cpu_profiler = CPUProfiler(enable_scalene=True)
        metrics_collector = MetricsCollector(scenario, cpu_profiler)

        try:
            metrics_collector.start_run()

            # Simulate test execution
            # In real implementation, this would:
            # 1. Set up game window with scenario geometry
            # 2. Run MacroEngine.dispatch_step()
            # 3. Simulate clicks and OCR calls
            # 4. Collect metrics

            # Mock: record some sample metrics for testing
            metrics_collector.record_click(512, 384, 515, 387)
            metrics_collector.record_ocr("TREASURE", "TREASURE", 150.0)
            metrics_collector.record_macro_step("wait_for_chat", 50.0)
            metrics_collector.record_macro_step("click_treasure", 100.0)
            metrics_collector.record_spam_clicks(100, 2.6)

            # Inject mock CPU profile data
            cpu_profiler.inject_profile_data(
                cpu_time_ms=1500.0,
                gpu_time_ms=200.0,
                memory_mb=120.0,
                syscall_time_ms=100.0,
                hot_spots=[],
            )

            # Mark run as passed (in real implementation, check for errors)
            metrics_collector.end_run(passed=True)

        except Exception as e:
            # Mark run as failed if exception occurred
            metrics_collector.end_run(passed=False)

        # Finalize and return metrics
        run_metrics = metrics_collector.finalize()
        return run_metrics

    def _create_baseline_scenarios(self) -> list[Scenario]:
        """Create predefined baseline scenarios (full-size single-monitor).

        Returns:
            List of 10 baseline Scenario objects
        """
        predefined = self.scenario_randomizer.predefined_scenarios()

        # Filter to get full-size, single-monitor scenarios
        baseline = [
            s
            for s in predefined
            if not s.is_clipped and not s.is_multi_monitor and not s.is_offscreen
        ]

        # If we don't have enough predefined scenarios, generate more
        while len(baseline) < self.config.baseline_run_count:
            scenario = self.scenario_randomizer.next_scenario()
            if not scenario.is_clipped and not scenario.is_multi_monitor and not scenario.is_offscreen:
                baseline.append(scenario)

        # Return exactly baseline_run_count scenarios
        return baseline[: self.config.baseline_run_count]

    def _compute_statistics(self, runs: list[RunMetrics]) -> dict:
        """Compute aggregate statistics from runs.

        Args:
            runs: List of RunMetrics to analyze

        Returns:
            Dictionary with statistics:
            - pass_rate: fraction of runs that passed (0.0-1.0)
            - cpu_critical_count: number of CRITICAL CPU runs
            - cpu_load_distribution: dict[CPULoadClass -> count]
            - avg_memory_mb: average memory usage
            - bottleneck_count: total deviations detected
        """
        if not runs:
            return {
                "pass_rate": 0.0,
                "cpu_critical_count": 0,
                "cpu_load_distribution": {},
                "avg_memory_mb": 0.0,
                "bottleneck_count": 0,
            }

        # Calculate pass rate
        passed_count = sum(1 for r in runs if r.passed)
        pass_rate = passed_count / len(runs) if runs else 0.0

        # Count CPU load classes
        cpu_load_distribution = {}
        cpu_critical_count = 0
        for cpu_class in CPULoadClass:
            count = sum(1 for r in runs if r.cpu_load_class == cpu_class)
            cpu_load_distribution[cpu_class.value] = count
            if cpu_class == CPULoadClass.CRITICAL:
                cpu_critical_count = count

        # Calculate average memory
        avg_memory_mb = (
            sum(r.memory_mb for r in runs) / len(runs) if runs else 0.0
        )

        # Count total deviations (bottlenecks)
        bottleneck_count = sum(len(r.deviations) for r in runs)

        return {
            "pass_rate": pass_rate,
            "cpu_critical_count": cpu_critical_count,
            "cpu_load_distribution": cpu_load_distribution,
            "avg_memory_mb": avg_memory_mb,
            "bottleneck_count": bottleneck_count,
        }

    def _should_spawn_more_runs(self, stats: dict) -> bool:
        """Determine if more runs should be spawned based on statistics.

        Args:
            stats: Statistics dictionary from _compute_statistics

        Returns:
            True if more runs needed, False otherwise
        """
        pass_rate = stats.get("pass_rate", 0.0)
        cpu_critical_count = stats.get("cpu_critical_count", 0)

        return (
            pass_rate < self.config.min_pass_rate_before_sampling
            or cpu_critical_count > self.config.cpu_critical_threshold
        )

    def _spawn_diagnostic_run(self, scenario: Scenario) -> RunMetrics:
        """Execute diagnostic run with extended CPU profiling.

        Args:
            scenario: Scenario to execute diagnostically

        Returns:
            RunMetrics with extended profiling data (hot-spots included)
        """
        # Same as _run_single_scenario but with extended profiling enabled
        cpu_profiler = CPUProfiler(enable_scalene=True)
        metrics_collector = MetricsCollector(scenario, cpu_profiler)

        try:
            metrics_collector.start_run()

            # Simulate test execution with diagnostics
            metrics_collector.record_click(512, 384, 515, 387)
            metrics_collector.record_ocr("TREASURE", "TREASURE", 150.0)
            metrics_collector.record_macro_step("wait_for_chat", 50.0)
            metrics_collector.record_macro_step("click_treasure", 100.0)
            metrics_collector.record_spam_clicks(100, 2.6)

            # Inject mock CPU profile with hot-spots for diagnostics
            from mvp.tests.test_framework.metrics import HotSpot

            hot_spots = [
                HotSpot("bot.clicker.click_at", 500.0, 35.0),
                HotSpot("bot.capture.get_frame", 400.0, 28.0),
                HotSpot("bot.ocr.detect", 300.0, 21.0),
            ]

            cpu_profiler.inject_profile_data(
                cpu_time_ms=1500.0,
                gpu_time_ms=200.0,
                memory_mb=120.0,
                syscall_time_ms=100.0,
                hot_spots=hot_spots,
            )

            metrics_collector.end_run(passed=True)

        except Exception:
            metrics_collector.end_run(passed=False)

        return metrics_collector.finalize()

    def _aggregate_results(self, suite_duration_s: float) -> TestSuiteResult:
        """Aggregate all run metrics into final test suite result.

        Args:
            suite_duration_s: Total suite execution time in seconds

        Returns:
            TestSuiteResult with aggregated data
        """
        if not self._all_runs:
            return TestSuiteResult()

        # Calculate statistics
        passed_count = sum(1 for r in self._all_runs if r.passed)
        failed_count = len(self._all_runs) - passed_count
        pass_rate = passed_count / len(self._all_runs) if self._all_runs else 0.0

        # CPU load distribution
        cpu_load_distribution = {}
        for cpu_class in CPULoadClass:
            count = sum(1 for r in self._all_runs if r.cpu_load_class == cpu_class)
            if count > 0:
                cpu_load_distribution[cpu_class.value] = count

        # Memory stats
        memory_values = [r.memory_mb for r in self._all_runs]
        avg_memory_mb = sum(memory_values) / len(memory_values) if memory_values else 0.0
        peak_memory_mb = max(memory_values) if memory_values else 0.0

        # Bottleneck summary
        bottleneck_summary = []
        for run in self._all_runs:
            for deviation in run.deviations:
                bottleneck_summary.append(
                    f"Run {run.run_id}: {deviation.type} ({deviation.severity}) - {deviation.message}"
                )

        result = TestSuiteResult(
            total_runs=len(self._all_runs),
            passed_runs=passed_count,
            failed_runs=failed_count,
            runs=self._all_runs,
            pass_rate=pass_rate,
            cpu_load_distribution=cpu_load_distribution,
            bottleneck_summary=bottleneck_summary,
            avg_memory_mb=avg_memory_mb,
            peak_memory_mb=peak_memory_mb,
            total_duration_s=suite_duration_s,
        )

        return result
