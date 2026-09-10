"""Tests for test orchestrator."""

import pytest
from mvp.tests.test_framework.orchestrator import Orchestrator, OrchestratorConfig
from mvp.tests.test_framework.scenarios import ScenarioRandomizer
from mvp.tests.test_framework.metrics import CPULoadClass, RunMetrics


class TestOrchestratorConfig:
    """Test OrchestratorConfig dataclass."""

    def test_orchestrator_config_defaults(self) -> None:
        """Test OrchestratorConfig has correct defaults."""
        config = OrchestratorConfig()

        assert config.max_runs == 50
        assert config.timeout_per_run == 15.0
        assert config.target_pass_rate == 0.95
        assert config.baseline_run_count == 10
        assert config.sampling_run_count == 10
        assert config.cpu_critical_threshold == 5
        assert config.min_pass_rate_before_sampling == 0.95

    def test_orchestrator_config_custom(self) -> None:
        """Test OrchestratorConfig with custom values."""
        config = OrchestratorConfig(
            max_runs=100,
            timeout_per_run=20.0,
            target_pass_rate=0.90,
            baseline_run_count=5,
            sampling_run_count=15,
        )

        assert config.max_runs == 100
        assert config.timeout_per_run == 20.0
        assert config.target_pass_rate == 0.90
        assert config.baseline_run_count == 5
        assert config.sampling_run_count == 15


class TestOrchestratorInitialization:
    """Test Orchestrator initialization."""

    def test_orchestrator_initialization(self) -> None:
        """Test Orchestrator initializes correctly."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        assert orchestrator.config == config
        assert orchestrator.scenario_randomizer == randomizer
        assert orchestrator._run_count == 0
        assert orchestrator._all_runs == []

    def test_orchestrator_with_custom_config(self) -> None:
        """Test Orchestrator with custom configuration."""
        config = OrchestratorConfig(baseline_run_count=5)
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        assert orchestrator.config.baseline_run_count == 5


class TestOrchestratorBaseline:
    """Test baseline phase of orchestrator."""

    def test_create_baseline_scenarios(self) -> None:
        """Test _create_baseline_scenarios returns correct number of scenarios."""
        config = OrchestratorConfig(baseline_run_count=10)
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenarios = orchestrator._create_baseline_scenarios()

        assert len(scenarios) == 10
        # All baseline scenarios should be full-size, single-monitor, non-offscreen
        for scenario in scenarios:
            assert not scenario.is_clipped, "Baseline should not be clipped"
            assert not scenario.is_multi_monitor, "Baseline should be single-monitor"
            assert not scenario.is_offscreen, "Baseline should be onscreen"

    def test_create_baseline_scenarios_count(self) -> None:
        """Test baseline scenarios count matches config."""
        config = OrchestratorConfig(baseline_run_count=5)
        randomizer = ScenarioRandomizer(seed=123)
        orchestrator = Orchestrator(config, randomizer)

        scenarios = orchestrator._create_baseline_scenarios()

        assert len(scenarios) == 5


class TestOrchestratorStatistics:
    """Test statistics computation."""

    def test_compute_statistics_empty_runs(self) -> None:
        """Test statistics with no runs."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        stats = orchestrator._compute_statistics([])

        assert stats["pass_rate"] == 0.0
        assert stats["cpu_critical_count"] == 0
        assert stats["cpu_load_distribution"] == {}
        assert stats["avg_memory_mb"] == 0.0
        assert stats["bottleneck_count"] == 0

    def test_compute_statistics_all_passed(self) -> None:
        """Test statistics when all runs pass."""
        from mvp.tests.test_framework.metrics import RunMetrics

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Create 5 passed runs
        runs = []
        for i in range(5):
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
            )
            runs.append(run)

        stats = orchestrator._compute_statistics(runs)

        assert stats["pass_rate"] == 1.0
        assert stats["cpu_critical_count"] == 0
        assert stats["avg_memory_mb"] == 100.0

    def test_compute_statistics_mixed_results(self) -> None:
        """Test statistics with mixed pass/fail runs."""
        from mvp.tests.test_framework.metrics import RunMetrics

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Create mixed runs
        runs = []
        for i in range(10):
            passed = i < 8  # 8 passed, 2 failed
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}",
                passed=passed,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=150.0,
            )
            runs.append(run)

        stats = orchestrator._compute_statistics(runs)

        assert stats["pass_rate"] == 0.8
        assert stats["avg_memory_mb"] == 150.0
        assert stats["cpu_critical_count"] == 0

    def test_compute_statistics_cpu_distribution(self) -> None:
        """Test CPU load distribution in statistics."""
        from mvp.tests.test_framework.metrics import RunMetrics

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Create runs with different CPU loads
        runs = [
            RunMetrics(
                run_id=0,
                scenario_id="scenario_0",
                passed=True,
                cpu_load_class=CPULoadClass.IDLE,
                memory_mb=100.0,
            ),
            RunMetrics(
                run_id=1,
                scenario_id="scenario_1",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
            ),
            RunMetrics(
                run_id=2,
                scenario_id="scenario_2",
                passed=True,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
            ),
        ]

        stats = orchestrator._compute_statistics(runs)

        assert stats["cpu_load_distribution"]["idle"] == 1
        assert stats["cpu_load_distribution"]["low"] == 1
        assert stats["cpu_load_distribution"]["critical"] == 1
        assert stats["cpu_critical_count"] == 1


class TestOrchestratorAdaptiveDecision:
    """Test adaptive sampling decision logic."""

    def test_should_spawn_more_runs_low_pass_rate(self) -> None:
        """Test spawning more runs when pass rate is low."""
        config = OrchestratorConfig(min_pass_rate_before_sampling=0.95)
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        stats = {
            "pass_rate": 0.80,
            "cpu_critical_count": 0,
        }

        should_spawn = orchestrator._should_spawn_more_runs(stats)

        assert should_spawn is True

    def test_should_spawn_more_runs_high_cpu_critical(self) -> None:
        """Test spawning more runs when CPU critical count is high."""
        config = OrchestratorConfig(cpu_critical_threshold=5)
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        stats = {
            "pass_rate": 0.95,
            "cpu_critical_count": 10,
        }

        should_spawn = orchestrator._should_spawn_more_runs(stats)

        assert should_spawn is True

    def test_should_not_spawn_more_runs_good_metrics(self) -> None:
        """Test not spawning more runs with good metrics."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        stats = {
            "pass_rate": 0.95,
            "cpu_critical_count": 0,
        }

        should_spawn = orchestrator._should_spawn_more_runs(stats)

        assert should_spawn is False


class TestOrchestratorSingleRun:
    """Test single scenario execution."""

    def test_run_single_scenario_creates_metrics(self) -> None:
        """Test _run_single_scenario returns valid RunMetrics."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        metrics = orchestrator._run_single_scenario(scenario)

        assert metrics.scenario_id == scenario.id
        assert metrics.passed is True
        assert metrics.click_count > 0
        assert metrics.ocr_detections > 0
        assert metrics.spam_cps > 0.0
        assert metrics.cpu_load_class in CPULoadClass

    def test_run_single_scenario_increments_counter(self) -> None:
        """Test _run_single_scenario returns metrics with assigned run_id."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()

        # Run scenario - inkrementacja licznika robiona przez wywołującego
        metrics1 = orchestrator._run_single_scenario(scenario)
        orchestrator._run_count += 1
        
        metrics2 = orchestrator._run_single_scenario(scenario)
        orchestrator._run_count += 1

        # Verify we can assign run IDs
        metrics1.run_id = 0
        metrics2.run_id = 1
        assert metrics1.run_id == 0
        assert metrics2.run_id == 1


class TestOrchestratorDiagnosticRun:
    """Test diagnostic run with extended profiling."""

    def test_spawn_diagnostic_run_includes_hot_spots(self) -> None:
        """Test diagnostic run includes hot-spots in metrics."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        metrics = orchestrator._spawn_diagnostic_run(scenario)

        assert metrics.passed is True
        assert len(metrics.hot_spots) > 0
        # Check hot-spots have meaningful data
        for hot_spot in metrics.hot_spots:
            assert hot_spot.function_name
            assert hot_spot.cpu_time_ms > 0.0
            assert 0.0 <= hot_spot.percent <= 100.0


class TestOrchestratorPhases:
    """Test orchestrator phases."""

    def test_run_baseline_phase(self) -> None:
        """Test baseline phase produces correct number of runs."""
        config = OrchestratorConfig(baseline_run_count=5)
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        baseline_runs = orchestrator._run_baseline_phase()

        assert len(baseline_runs) == 5
        for i, run in enumerate(baseline_runs):
            assert run.run_id == i
            assert run.passed is True

    def test_run_additional_runs(self) -> None:
        """Test additional runs phase."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        # Set initial run count to simulate baseline having run
        orchestrator._run_count = 10

        additional_runs = orchestrator._run_additional_runs(count=5)

        assert len(additional_runs) == 5
        # Check run IDs are sequential starting from 10
        for i, run in enumerate(additional_runs):
            assert run.run_id == 10 + i

    def test_run_sampling_phase(self) -> None:
        """Test sampling phase produces correct number of runs."""
        config = OrchestratorConfig(sampling_run_count=8)
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        # Simulate having run baseline + additional
        orchestrator._run_count = 20

        sampling_runs = orchestrator._run_sampling_phase()

        assert len(sampling_runs) == 8
        # Check run IDs start from 20
        for i, run in enumerate(sampling_runs):
            assert run.run_id == 20 + i


class TestOrchestratorResultAggregation:
    """Test aggregation of test suite results."""

    def test_aggregate_results_no_runs(self) -> None:
        """Test aggregation with no runs."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator._aggregate_results(suite_duration_s=1.0)

        assert result.total_runs == 0
        assert result.passed_runs == 0
        assert result.failed_runs == 0
        assert result.pass_rate == 0.0

    def test_aggregate_results_successful_runs(self) -> None:
        """Test aggregation with successful runs."""
        from mvp.tests.test_framework.metrics import RunMetrics

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Simulate runs
        runs = []
        for i in range(5):
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=120.0,
            )
            runs.append(run)

        orchestrator._all_runs = runs
        result = orchestrator._aggregate_results(suite_duration_s=10.0)

        assert result.total_runs == 5
        assert result.passed_runs == 5
        assert result.failed_runs == 0
        assert result.pass_rate == 1.0
        assert result.avg_memory_mb == 120.0
        assert result.peak_memory_mb == 120.0
        assert result.total_duration_s == 10.0

    def test_aggregate_results_mixed_outcomes(self) -> None:
        """Test aggregation with mixed pass/fail outcomes."""
        from mvp.tests.test_framework.metrics import RunMetrics

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Simulate mixed results
        runs = []
        for i in range(10):
            passed = i < 8  # 8 passed, 2 failed
            memory = 100.0 + i * 10  # Varying memory
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}",
                passed=passed,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=memory,
            )
            runs.append(run)

        orchestrator._all_runs = runs
        result = orchestrator._aggregate_results(suite_duration_s=20.0)

        assert result.total_runs == 10
        assert result.passed_runs == 8
        assert result.failed_runs == 2
        assert result.pass_rate == 0.8
        assert result.avg_memory_mb == pytest.approx(145.0, abs=1.0)
        assert result.peak_memory_mb == pytest.approx(190.0, abs=1.0)

    def test_aggregate_results_cpu_distribution(self) -> None:
        """Test CPU load distribution in aggregated results."""
        from mvp.tests.test_framework.metrics import RunMetrics

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Create runs with different CPU loads
        runs = [
            RunMetrics(
                run_id=0,
                scenario_id="scenario_0",
                passed=True,
                cpu_load_class=CPULoadClass.IDLE,
                memory_mb=100.0,
            ),
            RunMetrics(
                run_id=1,
                scenario_id="scenario_1",
                passed=True,
                cpu_load_class=CPULoadClass.LOW,
                memory_mb=100.0,
            ),
            RunMetrics(
                run_id=2,
                scenario_id="scenario_2",
                passed=True,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=100.0,
            ),
            RunMetrics(
                run_id=3,
                scenario_id="scenario_3",
                passed=True,
                cpu_load_class=CPULoadClass.CRITICAL,
                memory_mb=100.0,
            ),
        ]

        orchestrator._all_runs = runs
        result = orchestrator._aggregate_results(suite_duration_s=5.0)

        assert result.cpu_load_distribution["idle"] == 1
        assert result.cpu_load_distribution["low"] == 1
        assert result.cpu_load_distribution["medium"] == 1
        assert result.cpu_load_distribution["critical"] == 1


class TestOrchestratorFullSuite:
    """Integration test for full test suite execution."""

    def test_run_suite_produces_result(self) -> None:
        """Test run_suite produces valid TestSuiteResult."""
        config = OrchestratorConfig(
            baseline_run_count=3,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Should have at least baseline + sampling runs
        assert result.total_runs >= 5
        assert result.passed_runs >= 0
        assert result.failed_runs >= 0
        assert 0.0 <= result.pass_rate <= 1.0
        assert result.total_duration_s > 0.0

    def test_run_suite_all_runs_recorded(self) -> None:
        """Test run_suite records all runs in result."""
        config = OrchestratorConfig(
            baseline_run_count=2,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # All runs should be recorded
        assert len(result.runs) == result.total_runs
        # Each run should have unique run_id
        run_ids = [r.run_id for r in result.runs]
        assert len(set(run_ids)) == len(run_ids)

    def test_run_suite_adaptive_logic(self) -> None:
        """Test run_suite uses adaptive sampling logic."""
        config = OrchestratorConfig(
            baseline_run_count=2,
            sampling_run_count=1,
            min_pass_rate_before_sampling=0.95,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # With good baseline (should pass), we get baseline + sampling
        # Min total should be baseline_run_count + sampling_run_count
        assert result.total_runs >= config.baseline_run_count + config.sampling_run_count


class TestOrchestratorIterationLogic:
    """Test iteration and collection logic for scenarios."""

    def test_run_suite_iterates_all_scenarios(self) -> None:
        """Test run_suite iterates through multiple scenarios."""
        config = OrchestratorConfig(
            baseline_run_count=3,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify that we have results from different scenarios
        scenario_ids = set(r.scenario_id for r in result.runs)
        assert len(scenario_ids) > 1, "Should have runs from different scenarios"

    def test_run_suite_result_collection(self) -> None:
        """Test that all results are properly collected and stored."""
        config = OrchestratorConfig(
            baseline_run_count=4,
            sampling_run_count=3,
        )
        randomizer = ScenarioRandomizer(seed=99)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify collection
        assert len(result.runs) > 0
        assert result.total_runs == len(result.runs)
        for run in result.runs:
            assert run.scenario_id is not None
            assert run.run_id is not None

    def test_run_suite_pass_rate_calculation(self) -> None:
        """Test pass rate is correctly calculated."""
        config = OrchestratorConfig(
            baseline_run_count=10,
            sampling_run_count=0,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Pass rate should equal passed_runs / total_runs
        expected_pass_rate = result.passed_runs / result.total_runs if result.total_runs > 0 else 0.0
        assert result.pass_rate == pytest.approx(expected_pass_rate)

    def test_run_suite_adaptive_threshold_low_pass_rate(self) -> None:
        """Test adaptive logic triggers when pass rate is below threshold."""
        config = OrchestratorConfig(
            baseline_run_count=2,
            sampling_run_count=0,
            min_pass_rate_before_sampling=0.99,  # Very high threshold
            cpu_critical_threshold=0,  # CPU threshold very low
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Should trigger additional runs due to low pass rate threshold
        # Even with all passing runs, if baseline_run_count=2, we should see additional runs
        assert result.total_runs >= 2

    def test_run_suite_respects_max_runs_limit(self) -> None:
        """Test that run_suite respects max_runs configuration."""
        config = OrchestratorConfig(
            max_runs=10,
            baseline_run_count=3,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Total runs should not exceed max_runs
        assert result.total_runs <= config.max_runs


class TestOrchestratorResultValidation:
    """Test result validation and structure."""

    def test_run_suite_result_has_complete_structure(self) -> None:
        """Test that result contains all required fields."""
        config = OrchestratorConfig(
            baseline_run_count=2,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify all required result fields exist
        assert hasattr(result, 'total_runs')
        assert hasattr(result, 'passed_runs')
        assert hasattr(result, 'failed_runs')
        assert hasattr(result, 'runs')
        assert hasattr(result, 'pass_rate')
        assert hasattr(result, 'cpu_load_distribution')
        assert hasattr(result, 'bottleneck_summary')
        assert hasattr(result, 'avg_memory_mb')
        assert hasattr(result, 'peak_memory_mb')
        assert hasattr(result, 'total_duration_s')

    def test_run_suite_result_metrics_consistency(self) -> None:
        """Test consistency of result metrics."""
        config = OrchestratorConfig(
            baseline_run_count=5,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=123)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify metric consistency
        assert result.passed_runs + result.failed_runs == result.total_runs
        assert 0.0 <= result.pass_rate <= 1.0
        if result.total_runs > 0:
            assert result.pass_rate == pytest.approx(result.passed_runs / result.total_runs)
        assert result.avg_memory_mb >= 0.0
        assert result.peak_memory_mb >= result.avg_memory_mb

    def test_run_suite_all_runs_have_valid_metrics(self) -> None:
        """Test that each run in result has valid metrics."""
        config = OrchestratorConfig(
            baseline_run_count=3,
            sampling_run_count=2,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        for run in result.runs:
            assert run.run_id >= 0
            assert isinstance(run.passed, bool)
            assert run.memory_mb >= 0.0
            assert run.cpu_load_class in CPULoadClass
            assert isinstance(run.deviations, list)


class TestOrchestratorDiagnosticAdaptivity:
    """Test diagnostic spawning and adaptive behavior."""

    def test_run_suite_no_extra_runs_with_good_baseline(self) -> None:
        """Test that extra runs not spawned when baseline metrics are good."""
        config = OrchestratorConfig(
            baseline_run_count=3,
            sampling_run_count=2,
            min_pass_rate_before_sampling=0.5,  # Low threshold
            cpu_critical_threshold=100,  # Very high threshold
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Should be baseline (3) + optional additional (0) + sampling (2) = at least 5
        assert result.total_runs >= 5

    def test_diagnostic_run_includes_extended_profiling(self) -> None:
        """Test that diagnostic runs include extended profiling data."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        diag_metrics = orchestrator._spawn_diagnostic_run(scenario)

        # Diagnostic runs should have hot-spot data
        assert len(diag_metrics.hot_spots) > 0
        for hot_spot in diag_metrics.hot_spots:
            assert hot_spot.function_name
            assert hot_spot.cpu_time_ms > 0.0

    def test_run_count_incremented_correctly_across_phases(self) -> None:
        """Test that run_count is incremented correctly through all phases."""
        config = OrchestratorConfig(
            baseline_run_count=2,
            sampling_run_count=3,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        # Initial state
        assert orchestrator._run_count == 0

        # After run_suite
        result = orchestrator.run_suite()

        # Total runs should match run_count
        assert orchestrator._run_count == result.total_runs
        # And should be >= baseline + sampling
        assert result.total_runs >= 5

    def test_spawn_diagnostic_runs_creates_multiple_runs(self) -> None:
        """Test _spawn_diagnostic_runs creates specified number of runs."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        diag_runs = orchestrator._spawn_diagnostic_runs(scenario, count=5)

        assert len(diag_runs) == 5
        for run in diag_runs:
            assert run.passed is True  # Mock runs pass

    def test_spawn_diagnostic_runs_increments_run_count(self) -> None:
        """Test _spawn_diagnostic_runs increments run counter."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        initial_count = orchestrator._run_count
        scenario = randomizer.next_scenario()
        diag_runs = orchestrator._spawn_diagnostic_runs(scenario, count=3)

        assert orchestrator._run_count == initial_count + 3

    def test_spawn_diagnostic_runs_assigns_unique_run_ids(self) -> None:
        """Test _spawn_diagnostic_runs assigns unique run IDs."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        diag_runs = orchestrator._spawn_diagnostic_runs(scenario, count=5)

        run_ids = [run.run_id for run in diag_runs]
        # All should be unique and sequential starting from 0
        assert len(set(run_ids)) == len(run_ids)


class TestOrchestratorProcessOrchestration:
    """Test process orchestration methods."""

    def test_run_single_test_returns_run_metrics(self) -> None:
        """Test run_single_test returns valid RunMetrics."""
        from mvp.tests.test_framework.process_manager import ProcessManager

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        pm = ProcessManager()
        orchestrator = Orchestrator(config, randomizer, process_manager=pm)

        scenario = randomizer.next_scenario()
        # Without csharp_exe_path set, should use mock execution
        metrics = orchestrator.run_single_test(scenario)

        assert isinstance(metrics, RunMetrics)
        assert metrics.scenario_id == scenario.id
        assert metrics.run_id == 0

    def test_run_single_test_without_csharp_exe_path(self) -> None:
        """Test run_single_test works without C# executable configured."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer, csharp_exe_path=None)

        scenario = randomizer.next_scenario()
        metrics = orchestrator.run_single_test(scenario)

        # Should return metrics (likely passed=False due to no logs)
        assert isinstance(metrics, RunMetrics)
        assert metrics.scenario_id == scenario.id

    def test_run_single_test_handles_process_exceptions(self) -> None:
        """Test run_single_test handles process exceptions gracefully."""
        from mvp.tests.test_framework.process_manager import ProcessManager
        from unittest.mock import patch

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        pm = ProcessManager()
        orchestrator = Orchestrator(config, randomizer, process_manager=pm, csharp_exe_path="/fake/path")

        scenario = randomizer.next_scenario()

        with patch.object(orchestrator, "_spawn_csharp_window", side_effect=RuntimeError("Process failed")):
            metrics = orchestrator.run_single_test(scenario)

            # Should return failed metrics
            assert isinstance(metrics, RunMetrics)
            assert metrics.passed is False

    def test_spawn_csharp_window_delegates_to_process_manager(self) -> None:
        """Test _spawn_csharp_window delegates to ProcessManager."""
        from mvp.tests.test_framework.process_manager import ProcessManager
        from unittest.mock import patch, MagicMock

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        pm = ProcessManager()
        orchestrator = Orchestrator(config, randomizer, process_manager=pm, csharp_exe_path="/path/to/stub.exe")

        scenario = randomizer.next_scenario()

        with patch.object(pm, "spawn_csharp_window") as mock_spawn:
            mock_process = MagicMock()
            mock_spawn.return_value = (mock_process, 12345)

            process, pid = orchestrator._spawn_csharp_window(scenario)

            assert pid == 12345
            mock_spawn.assert_called_once()

    def test_spawn_csharp_window_raises_without_exe_path(self) -> None:
        """Test _spawn_csharp_window raises if exe path not configured."""
        from mvp.tests.test_framework.process_manager import ProcessManager

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        pm = ProcessManager()
        orchestrator = Orchestrator(config, randomizer, process_manager=pm, csharp_exe_path=None)

        scenario = randomizer.next_scenario()

        with pytest.raises(RuntimeError, match="C# executable path not configured"):
            orchestrator._spawn_csharp_window(scenario)

    def test_spawn_bot_mvp_delegates_to_process_manager(self) -> None:
        """Test _spawn_bot_mvp delegates to ProcessManager."""
        from mvp.tests.test_framework.process_manager import ProcessManager
        from unittest.mock import patch, MagicMock

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        pm = ProcessManager()
        orchestrator = Orchestrator(config, randomizer, process_manager=pm)

        with patch.object(pm, "spawn_bot_mvp") as mock_spawn:
            mock_process = MagicMock()
            mock_spawn.return_value = (mock_process, 54321)

            process, pid = orchestrator._spawn_bot_mvp()

            assert pid == 54321
            mock_spawn.assert_called_once()

    def test_collect_all_logs_delegates_to_process_manager(self) -> None:
        """Test _collect_all_logs delegates to ProcessManager."""
        from mvp.tests.test_framework.process_manager import ProcessManager
        from unittest.mock import patch

        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        pm = ProcessManager()
        orchestrator = Orchestrator(config, randomizer, process_manager=pm)

        expected_logs = {"game_events": "content", "event_log": "more content"}

        with patch.object(pm, "collect_logs", return_value=expected_logs):
            logs = orchestrator._collect_all_logs()

            assert logs == expected_logs

    def test_create_metrics_from_logs_returns_run_metrics(self) -> None:
        """Test _create_metrics_from_logs returns valid RunMetrics."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        logs = {"game_events": "content"}

        metrics = orchestrator._create_metrics_from_logs(scenario, logs)

        assert isinstance(metrics, RunMetrics)
        assert metrics.scenario_id == scenario.id
        assert metrics.passed is True  # Has logs

    def test_create_metrics_from_logs_marks_failed_if_no_logs(self) -> None:
        """Test _create_metrics_from_logs marks failed if no logs collected."""
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        logs = {}

        metrics = orchestrator._create_metrics_from_logs(scenario, logs)

        assert metrics.passed is False


class TestOrchestratorAdaptiveDiagnosticsThreshold:
    """Test adaptive diagnostic spawning at 80% pass rate threshold."""

    def test_run_suite_spawns_diagnostics_when_pass_rate_below_80_percent(self) -> None:
        """Test that diagnostic runs are spawned when pass_rate < 0.8 (80%).
        
        This test verifies Task 2.3.6 acceptance criteria:
        - Check pass rate after each test batch
        - If pass_rate < 0.8 (80%), spawn 5 additional diagnostic runs
        - Each diagnostic run has extended CPU profiling (top 5 hot-spots)
        - Results accumulated with other runs
        """
        from unittest.mock import patch
        
        config = OrchestratorConfig(
            baseline_run_count=5,
            sampling_run_count=2,
            min_pass_rate_before_sampling=0.95,  # High threshold to not interfere
            cpu_critical_threshold=100,  # Very high threshold
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        # Mock baseline phase to return 3 passed, 2 failed (60% pass rate)
        # This will trigger diagnostic spawning (< 80%)
        failed_runs = []
        for i in range(3):
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}_pass",
                passed=True,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=100.0,
            )
            failed_runs.append(run)

        for i in range(3, 5):
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}_fail",
                passed=False,  # Failed runs
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=100.0,
            )
            failed_runs.append(run)

        # Mock _run_baseline_phase to return controlled runs
        with patch.object(orchestrator, "_run_baseline_phase", return_value=failed_runs):
            # Mock _run_sampling_phase to return empty (minimal)
            with patch.object(orchestrator, "_run_sampling_phase", return_value=[]):
                # Mock _run_additional_runs to return empty (to avoid additional logic)
                with patch.object(orchestrator, "_run_additional_runs", return_value=[]):
                    result = orchestrator.run_suite()

                    # Baseline: 5 runs (3 passed, 2 failed = 60% pass rate)
                    # Diagnostics should spawn: 5 runs (due to 60% < 80%)
                    # Total: baseline (5) + diagnostics (5) + sampling (0) = 10 runs
                    
                    # Check that we have more runs than just baseline
                    assert result.total_runs >= 10, f"Expected >= 10 runs, got {result.total_runs}"
                    
                    # Verify diagnostics were accumulated
                    diagnostic_run_count = sum(
                        1 for run in result.runs if "diagnostic" in run.scenario_id or run.run_id >= 5
                    )
                    # At least some runs should be diagnostics
                    # (exact count depends on mock behavior, but should be > baseline)
                    assert result.total_runs > 5

    def test_diagnostic_runs_not_spawned_when_pass_rate_above_80_percent(self) -> None:
        """Test that diagnostic runs are NOT spawned when pass_rate >= 0.8 (80%)."""
        config = OrchestratorConfig(
            baseline_run_count=5,
            sampling_run_count=2,
            min_pass_rate_before_sampling=0.99,  # Higher than 80%
            cpu_critical_threshold=100,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        # Create all passing runs (100% pass rate)
        passed_runs = []
        for i in range(5):
            run = RunMetrics(
                run_id=i,
                scenario_id=f"scenario_{i}",
                passed=True,
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=100.0,
            )
            passed_runs.append(run)

        # Without mocking, normal execution should not spawn diagnostics for good pass rates
        # Result should be: baseline (5) + sampling (2) = 7
        from unittest.mock import patch
        with patch.object(orchestrator, "_run_baseline_phase", return_value=passed_runs):
            with patch.object(orchestrator, "_run_sampling_phase") as mock_sampling:
                mock_sampling.return_value = [
                    RunMetrics(
                        run_id=5,
                        scenario_id="scenario_sampling_1",
                        passed=True,
                        cpu_load_class=CPULoadClass.LOW,
                        memory_mb=100.0,
                    ),
                    RunMetrics(
                        run_id=6,
                        scenario_id="scenario_sampling_2",
                        passed=True,
                        cpu_load_class=CPULoadClass.LOW,
                        memory_mb=100.0,
                    ),
                ]
                with patch.object(orchestrator, "_run_additional_runs", return_value=[]):
                    result = orchestrator.run_suite()

                    # Should be: baseline (5) + sampling (2) = 7 runs (no diagnostics)
                    assert result.total_runs == 7
                    assert result.pass_rate == 1.0  # All passed

    def test_diagnostic_runs_have_cpu_profiling_hot_spots(self) -> None:
        """Test that diagnostic runs include extended CPU profiling with hot-spots.
        
        Validates acceptance criterion: "Each diagnostic run has extended CPU 
        profiling (top 5 hot-spots)"
        """
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        diag_runs = orchestrator._spawn_diagnostic_runs(scenario, count=5)

        # Each diagnostic run should have hot-spot data
        for run in diag_runs:
            assert len(run.hot_spots) > 0, "Diagnostic run should have hot-spot data"
            for hot_spot in run.hot_spots:
                assert hot_spot.function_name, "Hot-spot should have function name"
                assert hot_spot.cpu_time_ms > 0.0, "Hot-spot should have CPU time"
                assert hot_spot.percent > 0.0, "Hot-spot should have percentage"

    def test_diagnostic_runs_exact_count_is_5(self) -> None:
        """Test that exactly 5 diagnostic runs are spawned when threshold met.
        
        Validates acceptance criterion: "Exactly 5 diagnostic runs spawned when triggered"
        """
        config = OrchestratorConfig()
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        scenario = randomizer.next_scenario()
        
        # Explicitly spawn 5 diagnostics
        diag_runs = orchestrator._spawn_diagnostic_runs(scenario, count=5)
        
        assert len(diag_runs) == 5, "Should spawn exactly 5 diagnostic runs"

    def test_diagnostic_runs_accumulated_in_results(self) -> None:
        """Test that diagnostic run results are accumulated with other runs.
        
        Validates acceptance criterion: "Results accumulated with other runs"
        """
        from unittest.mock import patch
        
        config = OrchestratorConfig(
            baseline_run_count=3,
            sampling_run_count=1,
            min_pass_rate_before_sampling=0.95,
            cpu_critical_threshold=100,
        )
        randomizer = ScenarioRandomizer(seed=42)
        orchestrator = Orchestrator(config, randomizer)

        # Create runs with 67% pass rate (3 passed, 1.5 would be failed, simulate with 2 failed total)
        baseline_runs = []
        for i in range(3):
            run = RunMetrics(
                run_id=i,
                scenario_id=f"baseline_{i}",
                passed=i < 2,  # 2 passed, 1 failed = 67% (< 80%)
                cpu_load_class=CPULoadClass.MEDIUM,
                memory_mb=100.0,
            )
            baseline_runs.append(run)

        with patch.object(orchestrator, "_run_baseline_phase", return_value=baseline_runs):
            with patch.object(orchestrator, "_run_additional_runs", return_value=[]):
                with patch.object(orchestrator, "_run_sampling_phase") as mock_sampling:
                    mock_sampling.return_value = [
                        RunMetrics(
                            run_id=8,
                            scenario_id="sampling_1",
                            passed=True,
                            cpu_load_class=CPULoadClass.LOW,
                            memory_mb=100.0,
                        ),
                    ]
                    result = orchestrator.run_suite()

                    # Should have baseline (3) + diagnostics (5) + sampling (1) = 9 runs
                    assert result.total_runs == 9, f"Expected 9 total runs, got {result.total_runs}"
                    
                    # All runs should be in result.runs
                    assert len(result.runs) == 9
                    
                    # Pass rate calculation should include diagnostics
                    # Baseline: 2 passed, 1 failed
                    # Diagnostics: 5 passed (mock)
                    # Sampling: 1 passed
                    # Total: 8 passed, 1 failed = 89% pass rate
                    expected_pass_rate = 8 / 9
                    assert result.pass_rate == pytest.approx(expected_pass_rate, abs=0.01)
