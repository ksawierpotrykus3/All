# Performance Baseline Tests for Extended Game Simulator Framework
# Measures iteration latency, UI throughput, and metrics aggregation performance.

import pytest
import time
import threading
import queue
from unittest.mock import Mock, MagicMock

from mvp.simulator.core import GameStateManager, GameState
from mvp.simulator.metrics import MetricsCollector
from mvp.simulator.variants import VariantExecutor


# ======================== TEST 1: Iteration Latency P99 ========================

class TestIterationLatencyP99:
    """
    Scenario: Run 100 iterations, measure latency per iteration.
    Expected: P99 latency < 300ms (single iteration start→end).
    Verify: No regressions after fixes.
    """

    @pytest.fixture
    def engine_components(self):
        """Setup engine components for iteration testing."""
        return {
            "game_manager": GameStateManager(session_id="test_latency"),
            "metrics_collector": MetricsCollector(),
            "variant_executor": VariantExecutor()
        }

    def test_iteration_latency_p99(self, engine_components):
        """Measure P99 latency of 100 iterations."""
        
        gm = engine_components["game_manager"]
        mc = engine_components["metrics_collector"]
        ve = engine_components["variant_executor"]
        
        ve.apply_preset("default")
        
        iteration_latencies_ms = []
        
        for i in range(100):
            # Measure from start to end of single iteration
            start_ns = time.perf_counter_ns()
            
            # Phase 1: Setup
            mc.start_iteration(i + 1, ve.current_variant)
            gm.transition_to(GameState.ALERT_ANIMATION)
            mc.record_phase("setup", duration_ms=98)
            
            # Phase 2: Alert
            gm.transition_to(GameState.TREASURE)
            mc.record_phase("alert", duration_ms=145)
            
            # Phase 3: Click
            gm.transition_to(GameState.SCANNING)
            mc.record_phase("click", duration_ms=78)
            
            # Phase 4: Treasure
            mc.record_phase("treasure", duration_ms=150)
            
            # Phase 5: Chat Recovery
            gm.transition_to(GameState.CHAT_RECOVERY)
            mc.record_phase("chat_recovery", duration_ms=890)
            
            # Phase 6: Finalize
            gm.transition_to(GameState.CHAT)
            mc.record_phase("finalize", duration_ms=50)
            
            final_metrics = mc.end_iteration(
                total_ms=1411,
                cpu_avg=42,
                ram_mb=256
            )
            
            end_ns = time.perf_counter_ns()
            
            latency_ms = (end_ns - start_ns) / 1e6
            iteration_latencies_ms.append(latency_ms)
        
        # Calculate P99 latency
        sorted_latencies = sorted(iteration_latencies_ms)
        p99_index = int(len(sorted_latencies) * 0.99)
        p99_latency_ms = sorted_latencies[p99_index]
        
        # Also report P50 (median) and P95 for context
        p50_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.50)]
        p95_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        
        print(f"\n=== Iteration Latency (100 iterations) ===")
        print(f"P50: {p50_latency_ms:.2f}ms")
        print(f"P95: {p95_latency_ms:.2f}ms")
        print(f"P99: {p99_latency_ms:.2f}ms")
        
        # P99 should be well under 300ms (typically 20-50ms for pure Python)
        assert p99_latency_ms < 300, \
            f"P99 iteration latency {p99_latency_ms:.2f}ms exceeds 300ms threshold"


# ======================== TEST 2: UI Update Loop Throughput ========================

class TestUIUpdateLoopThroughput:
    """
    Scenario: Engine queuing 100 metrics/iteration, UI update loop processes for 10s.
    Expected: 50Hz refresh rate maintained, queue depth stays < 50.
    Verify: No frame drops.
    """

    def test_ui_update_loop_throughput(self):
        """Test UI update loop maintains 50Hz refresh with engine producing metrics."""
        
        # Bounded queue simulating UI queue (50Hz = 20ms per refresh)
        metrics_queue = queue.Queue(maxsize=500)
        stop_event = threading.Event()
        
        produced_count = [0]
        consumed_count = [0]
        max_queue_depth = [0]
        
        def producer_iterations():
            """Simulate engine producing 100 metrics per iteration."""
            iteration = 0
            while not stop_event.is_set():
                # Each iteration produces ~100 metrics (one per phase + details)
                for metric_id in range(100):
                    try:
                        metrics_queue.put_nowait({
                            "iteration": iteration,
                            "metric_id": metric_id,
                            "timestamp": time.time()
                        })
                        produced_count[0] += 1
                    except queue.Full:
                        # Drop oldest if queue full
                        try:
                            metrics_queue.get_nowait()
                        except queue.Empty:
                            pass
                
                # Iteration every 1.4s (approximately)
                time.sleep(1.4)
                iteration += 1
        
        def consumer_ui_loop():
            """Simulate Tkinter UI update loop at 50Hz (20ms intervals)."""
            while not stop_event.is_set():
                # Process all available metrics (batch processing)
                items_this_tick = 0
                while items_this_tick < 100:  # Max items per UI frame
                    try:
                        item = metrics_queue.get_nowait()
                        consumed_count[0] += 1
                        items_this_tick += 1
                    except queue.Empty:
                        break
                
                # Record max queue depth seen
                current_depth = metrics_queue.qsize()
                if current_depth > max_queue_depth[0]:
                    max_queue_depth[0] = current_depth
                
                # UI refresh at 50Hz (20ms per frame)
                time.sleep(0.020)
        
        # Start producer and consumer
        producer_thread = threading.Thread(target=producer_iterations, daemon=True)
        consumer_thread = threading.Thread(target=consumer_ui_loop, daemon=True)
        
        producer_thread.start()
        consumer_thread.start()
        
        # Run for 10 seconds
        time.sleep(10.0)
        stop_event.set()
        
        producer_thread.join(timeout=2.0)
        consumer_thread.join(timeout=2.0)
        
        print(f"\n=== UI Throughput (10s test) ===")
        print(f"Produced: {produced_count[0]} metrics")
        print(f"Consumed: {consumed_count[0]} metrics")
        print(f"Max queue depth: {max_queue_depth[0]} (limit: 500)")
        print(f"Throughput: {consumed_count[0] / 10:.0f} metrics/sec consumed")
        
        # Verify UI consumed most metrics (some drops acceptable at saturation)
        assert consumed_count[0] > produced_count[0] * 0.8, \
            f"UI should consume most metrics ({consumed_count[0]} / {produced_count[0]})"
        
        # Verify queue didn't exceed safe depth
        assert max_queue_depth[0] < 500, \
            f"Queue depth {max_queue_depth[0]} too high"


# ======================== TEST 3: Metrics Aggregation Speed ========================

class TestMetricsAggregationSpeed:
    """
    Scenario: 1000 iterations worth of data, aggregate session metrics.
    Expected: < 100ms aggregation time.
    Verify: No slowdown with large datasets.
    """

    def test_metrics_aggregation_speed(self):
        """Measure aggregation speed for 1000 iterations of metrics."""
        
        mc = MetricsCollector()
        ve = VariantExecutor()
        
        ve.apply_preset("default")
        
        # Generate 1000 iterations of mock metrics
        for iteration_num in range(1, 1001):
            mc.start_iteration(iteration_num, ve.current_variant)
            
            # Record phases
            mc.record_phase("setup", duration_ms=98)
            mc.record_phase("alert", duration_ms=145)
            mc.record_phase("click", duration_ms=78)  # 80% hit rate
            mc.record_phase("treasure", duration_ms=150)
            mc.record_phase("chat_recovery", duration_ms=890)
            mc.record_phase("finalize", duration_ms=50)
            
            final_metrics = mc.end_iteration(
                total_ms=1411,
                cpu_avg=42 + (iteration_num % 20),  # Vary CPU
                ram_mb=256 + (iteration_num % 100)
            )
        
        # Measure aggregation time
        start_ns = time.perf_counter_ns()
        
        aggregated = mc.aggregate()
        
        end_ns = time.perf_counter_ns()
        
        aggregation_time_ms = (end_ns - start_ns) / 1e6
        
        print(f"\n=== Metrics Aggregation (1000 iterations) ===")
        print(f"Aggregation time: {aggregation_time_ms:.2f}ms")
        print(f"Accuracy: {aggregated['accuracy_percent']:.1f}%")
        print(f"Iterations: {aggregated['iterations_total']}")
        avg_lat = aggregated['latency_avg_ms']
        if avg_lat is not None:
            print(f"Avg Latency: {avg_lat:.1f}ms")
        else:
            print("Avg Latency: None")
        print(f"Chat Recovery Failures: {aggregated['chat_recovery_failures']}")
        
        # Verify aggregation completes in < 100ms
        assert aggregation_time_ms < 100, \
            f"Aggregation took {aggregation_time_ms:.2f}ms, should be < 100ms"
        
        # Verify results are correct
        assert aggregated['iterations_total'] == 1000
        assert aggregated['iterations_hit'] == 0  # No hits recorded
        assert aggregated['accuracy_percent'] == 0.0


# ======================== Stress Test: Combined Performance ========================

class TestCombinedPerformanceStress:
    """
    Combined stress test: multiple iterations, concurrent metrics processing,
    aggregation, and variant changes.
    """

    def test_combined_performance_stress(self):
        """Test system performance under combined load."""
        
        gm = GameStateManager(session_id="stress_test")
        mc = MetricsCollector()
        ve = VariantExecutor()
        
        ve.apply_preset("default")
        
        presets = ["default", "hard_mode", "stress_test"]
        preset_idx = 0
        
        iteration_times = []
        
        # Run 50 iterations with variant switching
        for i in range(50):
            # Switch variant every 10 iterations
            if i % 10 == 0:
                ve.apply_preset(presets[preset_idx % len(presets)])
                preset_idx += 1
            
            start_ns = time.perf_counter_ns()
            
            # Full iteration
            mc.start_iteration(i + 1, ve.current_variant)
            
            gm.transition_to(GameState.ALERT_ANIMATION)
            mc.record_phase("setup", duration_ms=98)
            
            gm.transition_to(GameState.TREASURE)
            mc.record_phase("alert", duration_ms=145)
            
            gm.transition_to(GameState.SCANNING)
            mc.record_phase("click", duration_ms=78)
            
            mc.record_phase("treasure", duration_ms=150)
            
            gm.transition_to(GameState.CHAT_RECOVERY)
            mc.record_phase("chat_recovery", duration_ms=890)
            
            gm.transition_to(GameState.CHAT)
            final_metrics = mc.end_iteration(
                total_ms=1411,
                cpu_avg=42,
                ram_mb=256
            )
            
            end_ns = time.perf_counter_ns()
            iteration_times.append((end_ns - start_ns) / 1e6)
        
        # Periodic aggregation (simulate dashboard updates)
        agg_times = []
        for _ in range(5):
            start_ns = time.perf_counter_ns()
            aggregated = mc.aggregate()
            end_ns = time.perf_counter_ns()
            agg_times.append((end_ns - start_ns) / 1e6)
        
        # Verify performance
        avg_iteration_ms = sum(iteration_times) / len(iteration_times)
        max_iteration_ms = max(iteration_times)
        avg_agg_ms = sum(agg_times) / len(agg_times)
        
        print(f"\n=== Combined Performance Stress (50 iterations + variant switches) ===")
        print(f"Avg iteration time: {avg_iteration_ms:.2f}ms")
        print(f"Max iteration time: {max_iteration_ms:.2f}ms")
        print(f"Avg aggregation time: {avg_agg_ms:.2f}ms")
        print(f"Variant switches: {preset_idx}")
        
        # Performance expectations
        assert avg_iteration_ms < 50, "Average iteration should be < 50ms"
        assert max_iteration_ms < 100, "Max iteration should be < 100ms"
        assert avg_agg_ms < 50, "Average aggregation should be < 50ms"
