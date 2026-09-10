"""Smoke test for hybrid macro integration test framework.

Quick validation test (3 runs, ~15-20s total) to ensure framework
is working correctly before running full integration tests.
"""

import pytest

from mvp.tests.test_framework.orchestrator import Orchestrator, OrchestratorConfig
from mvp.tests.test_framework.scenarios import ScenarioRandomizer


@pytest.mark.integration
def test_smoke_single_monitor_full_size() -> None:
    """Smoke test for single-monitor full-size configuration.
    
    Quick validation with 3 runs on single monitor with full-size window.
    - Window: 1024x768 (standard baseline)
    - Position: various positions within single monitor
    - DPI: 96 (standard)
    - Duration target: ~15-20s total (3 runs × 5-7s per run)
    
    **Acceptance Criteria:**
    - Pass rate >= 95% (allow max 1 failure in 3 runs)
    - All runs have valid metrics
    - Total execution time < 20s
    
    **What this validates:**
    - Orchestrator can initialize and run basic suite
    - Scenarios generate correctly
    - Metrics are collected properly
    - CPU profiling works
    - Memory tracking works
    - Results structure is valid
    """
    # Configure orchestrator for quick smoke test
    # 3 baseline runs only, no sampling phase
    config = OrchestratorConfig(
        max_runs=3,                            # 3 quick runs only
        timeout_per_run=15.0,                  # 15s per run
        target_pass_rate=0.95,                 # 95% pass rate target
        baseline_run_count=3,                  # All 3 runs are baseline
        sampling_run_count=0,                  # No sampling phase (speed)
        cpu_critical_threshold=5,              # Allow up to 5 CRITICAL CPU runs
        min_pass_rate_before_sampling=0.95,    # Min pass rate before sampling
    )
    
    # Initialize orchestrator with scenario randomizer
    scenario_randomizer = ScenarioRandomizer()
    orchestrator = Orchestrator(config, scenario_randomizer)
    
    # Execute smoke test suite
    result = orchestrator.run_suite()
    
    # Validate results structure
    assert result is not None, "Test suite result is None"
    assert result.total_runs == 3, f"Expected 3 runs, got {result.total_runs}"
    assert result.passed_runs >= 0, "Invalid passed_runs count"
    assert result.failed_runs >= 0, "Invalid failed_runs count"
    
    # PRIMARY ACCEPTANCE CRITERION: Pass rate >= 95%
    # With 3 runs: need at least 3 passes (100%) or 2 passes (66%) still fails
    # But 95% of 3 = 2.85, so need 3 passes to meet criteria
    assert result.pass_rate >= 0.95, (
        f"Pass rate {result.pass_rate:.2%} is below 95% "
        f"({result.passed_runs}/{result.total_runs} passed)"
    )
    
    # Validate metrics are properly collected
    assert len(result.runs) == 3, f"Expected 3 run metrics, got {len(result.runs)}"
    assert result.runs, "No run metrics collected"
    
    # Verify all runs have valid metrics
    for i, run_metrics in enumerate(result.runs):
        assert run_metrics is not None, f"Run {i} has None metrics"
        assert run_metrics.run_id == i, f"Run {i} has incorrect run_id"
        assert run_metrics.cpu_load_class is not None, f"Run {i} missing CPU load class"
        assert run_metrics.memory_mb > 0, f"Run {i} has invalid memory"
        assert run_metrics.passed is not None, f"Run {i} missing pass/fail status"
    
    # Validate CPU profiling data
    assert result.cpu_load_distribution is not None, "CPU load distribution is None"
    assert len(result.cpu_load_distribution) > 0, "No CPU load distribution data"
    total_cpu_runs = sum(result.cpu_load_distribution.values())
    assert total_cpu_runs == 3, (
        f"CPU load distribution count mismatch: {total_cpu_runs} != 3"
    )
    
    # Validate memory statistics
    assert result.avg_memory_mb > 0.0, "Average memory is invalid"
    assert result.peak_memory_mb >= result.avg_memory_mb, (
        f"Peak memory {result.peak_memory_mb} < avg {result.avg_memory_mb}"
    )
    
    # Validate total duration (should be < 20s for 3 runs)
    assert result.total_duration_s > 0.0, "Total suite duration is invalid"
    assert result.total_duration_s < 20.0, (
        f"Smoke test took {result.total_duration_s:.1f}s, expected < 20s"
    )
    
    # Summary output (informational)
    print(f"\n✓ Smoke Test PASSED:")
    print(f"  Total runs: {result.total_runs}")
    print(f"  Passed: {result.passed_runs}")
    print(f"  Failed: {result.failed_runs}")
    print(f"  Pass rate: {result.pass_rate:.1%}")
    print(f"  Avg memory: {result.avg_memory_mb:.1f} MB")
    print(f"  Peak memory: {result.peak_memory_mb:.1f} MB")
    print(f"  Duration: {result.total_duration_s:.1f}s")
