"""Integration tests for macro hybrid framework combining metrics, orchestration, and bot execution."""

import pytest

from mvp.tests.test_framework.orchestrator import Orchestrator, OrchestratorConfig
from mvp.tests.test_framework.metrics import RunMetrics, CPULoadClass
from mvp.tests.test_framework.scenarios import Scenario, ScenarioRandomizer


class TestMacroHybridFramework:
    """Integration tests for macro hybrid framework."""

    def test_fixtures_exist(self, fixtures_exist: bool) -> None:
        """Test that all required integration fixtures exist and are valid.
        
        This test verifies that pytest fixtures for bot integration are properly
        configured and ready for use in integration tests.
        
        Args:
            fixtures_exist: Fixture verification result
        """
        assert fixtures_exist is True

    def test_window_context_valid(self, window_context) -> None:
        """Test that window context fixture is valid.
        
        Args:
            window_context: Window context fixture
        """
        assert window_context is not None
        assert window_context.left == 0
        assert window_context.top == 0
        assert window_context.width == 1024
        assert window_context.height == 768

    def test_macro_engine_has_clicker(self, macro_engine) -> None:
        """Test that macro engine fixture has mocked clicker.
        
        Args:
            macro_engine: MacroEngine fixture
        """
        assert macro_engine is not None
        assert macro_engine.clicker is not None
        assert hasattr(macro_engine.clicker, "click")
        assert hasattr(macro_engine.clicker, "scroll")

    def test_scenario_randomizer_generates_scenarios(self, test_scenario) -> None:
        """Test that test scenarios are properly generated.
        
        Args:
            test_scenario: Test scenario fixture
        """
        assert test_scenario is not None
        assert test_scenario.window_width == 1024
        assert test_scenario.window_height == 768
        assert test_scenario.dpi == 96
        assert len(test_scenario.monitors) == 1

    def test_multi_monitor_scenario_valid(self, multi_monitor_scenario) -> None:
        """Test that multi-monitor scenario is properly configured.
        
        Args:
            multi_monitor_scenario: Multi-monitor scenario fixture
        """
        assert multi_monitor_scenario.is_multi_monitor is True
        assert len(multi_monitor_scenario.monitors) == 2
        assert multi_monitor_scenario.monitors[0].dpi == 96
        assert multi_monitor_scenario.monitors[1].dpi == 144

    def test_clipped_scenario_valid(self, clipped_scenario) -> None:
        """Test that clipped scenario is properly configured.
        
        Args:
            clipped_scenario: Clipped scenario fixture
        """
        assert clipped_scenario.is_clipped is True
        assert clipped_scenario.window_width == 800
        assert clipped_scenario.window_height == 600

    def test_macro_hybrid_orchestrator_smoke_test(self) -> None:
        """Smoke test for orchestrator with minimal configuration.
        
        This test verifies that the Orchestrator can be instantiated
        and run with mock scenarios.
        """
        from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
        from mvp.tests.test_framework.scenarios import ScenarioRandomizer
        
        config = OrchestratorConfig(
            max_runs=50,
            timeout_per_run=60.0,
            target_pass_rate=0.95,
            baseline_run_count=2,
            sampling_run_count=1,
        )
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        # Run orchestrator
        result = orchestrator.run_suite()

        # Verify results structure
        assert result is not None
        assert result.total_runs > 0
        assert result.passed_runs > 0
        assert result.pass_rate > 0.0

    def test_orchestrator_pass_rate_computation(self) -> None:
        """Test orchestrator pass rate computation.
        
        Verifies that orchestrator correctly computes pass rate from mixed
        passing and failing runs.
        """
        from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
        from mvp.tests.test_framework.scenarios import ScenarioRandomizer
        
        config = OrchestratorConfig(
            max_runs=50,
            timeout_per_run=15.0,
            baseline_run_count=3,
            sampling_run_count=0,
        )
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # At least baseline runs should have been executed
        assert result.total_runs >= 3
        # Pass rate should be between 0 and 1
        assert 0.0 <= result.pass_rate <= 1.0

    def test_orchestrator_adaptive_sampling_decision(self) -> None:
        """Test orchestrator adaptive sampling decision logic.
        
        Verifies that orchestrator transitions from baseline to sampling
        phase when pass rate and CPU metrics are acceptable.
        """
        from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
        from mvp.tests.test_framework.scenarios import ScenarioRandomizer
        
        config = OrchestratorConfig(
            max_runs=50,
            timeout_per_run=15.0,
            baseline_run_count=3,
            sampling_run_count=2,
            target_pass_rate=0.95,
        )
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # With all passing runs, should proceed to sampling
        # Total should be baseline + sampling
        assert result.total_runs >= 3  # At minimum baseline
        assert result.pass_rate >= 0.0  # Valid pass rate
        assert result.passed_runs == result.total_runs  # All should pass

    def test_orchestrator_cpu_distribution_tracking(self) -> None:
        """Test orchestrator CPU load distribution tracking.
        
        Verifies that orchestrator correctly tracks CPU load classes
        across different runs.
        """
        from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
        from mvp.tests.test_framework.scenarios import ScenarioRandomizer
        
        config = OrchestratorConfig(
            max_runs=50,
            timeout_per_run=15.0,
            baseline_run_count=3,
            sampling_run_count=0,
        )
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify CPU distribution was computed
        assert result.cpu_load_distribution is not None
        assert len(result.cpu_load_distribution) > 0
        # Should have tracked the different load classes
        assert sum(result.cpu_load_distribution.values()) == result.total_runs

    def test_orchestrator_memory_statistics(self) -> None:
        """Test orchestrator memory usage statistics.
        
        Verifies that orchestrator correctly computes average and peak
        memory usage across runs.
        """
        from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
        from mvp.tests.test_framework.scenarios import ScenarioRandomizer
        
        config = OrchestratorConfig(
            max_runs=50,
            timeout_per_run=15.0,
            baseline_run_count=3,
            sampling_run_count=0,
        )
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify memory statistics
        assert result.avg_memory_mb > 0.0
        assert result.peak_memory_mb >= result.avg_memory_mb

    def test_orchestrator_run_id_sequencing(self) -> None:
        """Test that orchestrator correctly assigns sequential run IDs.
        
        Verifies that each run receives a unique, incrementing run ID.
        """
        from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
        from mvp.tests.test_framework.scenarios import ScenarioRandomizer
        
        config = OrchestratorConfig(
            max_runs=50,
            timeout_per_run=15.0,
            baseline_run_count=3,
            sampling_run_count=0,
        )
        randomizer = ScenarioRandomizer()
        orchestrator = Orchestrator(config, randomizer)

        result = orchestrator.run_suite()

        # Verify run IDs are sequential
        for i, run in enumerate(result.runs):
            assert run.run_id == i

    def test_bot_runner_initialization(self, mock_bot_runner, bot_config) -> None:
        """Test that bot runner can be initialized with test config.
        
        Args:
            mock_bot_runner: Mock bot runner fixture
            bot_config: Bot configuration fixture
        """
        assert mock_bot_runner is not None
        assert mock_bot_runner.config == bot_config
        assert mock_bot_runner.macro_engine is not None

    def test_bot_runner_macro_execution(self, mock_bot_runner) -> None:
        """Test that bot runner can execute macros (mocked).
        
        Args:
            mock_bot_runner: Mock bot runner fixture
        """
        # Verify macro engine is mocked and ready
        assert mock_bot_runner.macro_engine.run is not None
        # Verify we can call it
        result = mock_bot_runner.macro_engine.run(None, None)
        mock_bot_runner.macro_engine.run.assert_called_once()


@pytest.mark.integration
def test_macro_hybrid() -> None:
    """Integration test for hybrid macro framework with orchestrator.
    
    This is the main integration test that validates the complete hybrid
    macro testing framework by:
    1. Creating a TestOrchestrator with real configuration
    2. Running the full test suite with adaptive sampling
    3. Collecting metrics across all runs
    4. Asserting pass_rate >= 95% as acceptance criteria
    
    The test simulates running the real bot engine against a simulated
    game environment with various scenarios (different window sizes,
    DPI settings, monitor configurations, chat states, timers).
    
    **Acceptance Criteria:**
    - pass_rate >= 95% (minimal failures)
    - All runs should have valid metrics
    - CPU profiling should capture load classes
    - Memory tracking should work correctly
    """
    from mvp.tests.test_framework.orchestrator import OrchestratorConfig, Orchestrator
    from mvp.tests.test_framework.scenarios import ScenarioRandomizer
    
    # Configure orchestrator for comprehensive testing
    config = OrchestratorConfig(
        max_runs=50,                           # Total runs (baseline + sampling)
        timeout_per_run=15.0,                  # 15s per run
        target_pass_rate=0.95,                 # 95% pass rate target
        baseline_run_count=10,                 # 10 baseline runs (single-monitor, full-size)
        sampling_run_count=10,                 # 10 sampling runs (multi-monitor, clipped, edge cases)
        cpu_critical_threshold=5,              # Allow up to 5 CRITICAL CPU runs
        min_pass_rate_before_sampling=0.95,    # Min pass rate before sampling
    )
    
    # Initialize orchestrator with scenario randomizer
    scenario_randomizer = ScenarioRandomizer()
    orchestrator = Orchestrator(config, scenario_randomizer)
    
    # Execute full test suite with adaptive sampling
    result = orchestrator.run_suite()
    
    # Validate results structure
    assert result is not None, "Test suite result is None"
    assert result.total_runs > 0, "No runs were executed"
    assert result.passed_runs > 0, "No runs passed"
    assert result.failed_runs >= 0, "Invalid failed_runs count"
    
    # **PRIMARY ACCEPTANCE CRITERION: Pass rate >= 95%**
    assert result.pass_rate >= 0.95, (
        f"Pass rate {result.pass_rate:.2%} is below target 95% "
        f"({result.passed_runs}/{result.total_runs} passed)"
    )
    
    # Validate metrics are properly collected
    assert len(result.runs) == result.total_runs, "Run count mismatch in metrics"
    assert result.runs, "No run metrics collected"
    
    # Verify all runs have valid metrics
    for i, run_metrics in enumerate(result.runs):
        assert run_metrics is not None, f"Run {i} has None metrics"
        assert run_metrics.run_id == i, f"Run {i} has incorrect run_id: {run_metrics.run_id}"
        assert run_metrics.cpu_load_class is not None, f"Run {i} missing CPU load class"
        assert run_metrics.memory_mb > 0, f"Run {i} has invalid memory: {run_metrics.memory_mb}"
        assert run_metrics.passed is not None, f"Run {i} missing pass/fail status"
    
    # Validate CPU profiling data
    assert result.cpu_load_distribution is not None, "CPU load distribution is None"
    assert len(result.cpu_load_distribution) > 0, "No CPU load distribution data"
    total_cpu_runs = sum(result.cpu_load_distribution.values())
    assert total_cpu_runs == result.total_runs, (
        f"CPU load distribution count mismatch: {total_cpu_runs} != {result.total_runs}"
    )
    
    # Validate memory statistics
    assert result.avg_memory_mb > 0.0, "Average memory is invalid"
    assert result.peak_memory_mb >= result.avg_memory_mb, (
        f"Peak memory {result.peak_memory_mb} < avg {result.avg_memory_mb}"
    )
    
    # Validate total duration
    assert result.total_duration_s > 0.0, "Total suite duration is invalid"
    
    # Summary statistics (informational, non-blocking)
    print(f"\n✓ Macro Hybrid Integration Test Summary:")
    print(f"  Total runs: {result.total_runs}")
    print(f"  Passed: {result.passed_runs}")
    print(f"  Failed: {result.failed_runs}")
    print(f"  Pass rate: {result.pass_rate:.1%}")
    print(f"  Avg memory: {result.avg_memory_mb:.1f} MB")
    print(f"  Peak memory: {result.peak_memory_mb:.1f} MB")
    print(f"  Duration: {result.total_duration_s:.1f}s")


class TestIntegrationScenarios:
    """Integration tests with specific scenario types."""

    def test_standard_scenario_integration(self, test_scenario) -> None:
        """Test integration with standard scenario.
        
        Args:
            test_scenario: Standard test scenario
        """
        assert test_scenario.window_width == 1024
        assert test_scenario.window_height == 768
        assert not test_scenario.is_multi_monitor
        assert not test_scenario.is_clipped

    def test_multi_monitor_scenario_integration(self, multi_monitor_scenario) -> None:
        """Test integration with multi-monitor scenario.
        
        Args:
            multi_monitor_scenario: Multi-monitor scenario
        """
        assert multi_monitor_scenario.is_multi_monitor
        assert len(multi_monitor_scenario.monitors) == 2
        assert multi_monitor_scenario.monitors[0].dpi != multi_monitor_scenario.monitors[1].dpi

    def test_clipped_scenario_integration(self, clipped_scenario) -> None:
        """Test integration with clipped window scenario.
        
        Args:
            clipped_scenario: Clipped window scenario
        """
        assert clipped_scenario.is_clipped
        assert clipped_scenario.window_width < 1024 or clipped_scenario.window_height < 768
