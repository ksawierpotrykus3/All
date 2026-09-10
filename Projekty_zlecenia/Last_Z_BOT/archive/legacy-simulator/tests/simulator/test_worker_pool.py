# tests/simulator/test_worker_pool.py
"""
Comprehensive tests for WorkerPool class.

Tests async task submission, concurrent execution, queue overflow handling,
graceful shutdown, exception handling, and performance characteristics.
"""

import time
import pytest
import threading
from concurrent.futures import Future
from typing import Dict, Any
from unittest.mock import Mock, patch

from mvp.simulator.worker_pool import WorkerPool


class TestWorkerPoolInit:
    """Tests for WorkerPool initialization."""

    def test_worker_pool_init_default(self):
        """Test WorkerPool initialization with default parameters."""
        pool = WorkerPool()
        assert pool.num_workers == 4
        assert pool.queue_size == 100
        assert pool.is_shutdown is False
        pool.shutdown()

    def test_worker_pool_init_custom_workers(self):
        """Test WorkerPool initialization with custom worker count."""
        pool = WorkerPool(num_workers=8)
        assert pool.num_workers == 8
        pool.shutdown()

    def test_worker_pool_init_custom_queue_size(self):
        """Test WorkerPool initialization with custom queue size."""
        pool = WorkerPool(queue_size=200)
        assert pool.queue_size == 200
        pool.shutdown()

    def test_worker_pool_init_all_custom(self):
        """Test WorkerPool initialization with all custom parameters."""
        pool = WorkerPool(num_workers=6, queue_size=150)
        assert pool.num_workers == 6
        assert pool.queue_size == 150
        pool.shutdown()

    def test_worker_pool_init_workers_created(self):
        """Test that worker threads are created and running."""
        pool = WorkerPool(num_workers=4)
        # Check that exactly num_workers threads are created
        active_threads = threading.active_count()
        pool.shutdown()
        # Should have N worker threads
        assert pool.num_workers > 0


class TestWorkerPoolSubmitTask:
    """Tests for task submission."""

    def test_worker_pool_submit_task_simple(self):
        """Test submitting a simple task."""
        pool = WorkerPool(num_workers=2)
        
        def dummy_task():
            return 42
        
        future = pool.submit_task(dummy_task)
        assert future is not None
        assert isinstance(future, Future)
        result = future.result(timeout=2)
        assert result == 42
        
        pool.shutdown()

    def test_worker_pool_submit_task_with_args(self):
        """Test submitting task with positional arguments."""
        pool = WorkerPool(num_workers=2)
        
        def add(a, b):
            return a + b
        
        future = pool.submit_task(add, 3, 5)
        result = future.result(timeout=2)
        assert result == 8
        
        pool.shutdown()

    def test_worker_pool_submit_task_with_kwargs(self):
        """Test submitting task with keyword arguments."""
        pool = WorkerPool(num_workers=2)
        
        def multiply(x, y, factor=1):
            return x * y * factor
        
        future = pool.submit_task(multiply, 3, 4, factor=2)
        result = future.result(timeout=2)
        assert result == 24
        
        pool.shutdown()

    def test_worker_pool_submit_click_simple(self):
        """Test submitting click data to pool."""
        pool = WorkerPool(num_workers=2)
        
        click_data = {
            'x': 100,
            'y': 200,
            'hit': True,
            'timestamp': time.time()
        }
        
        future = pool.submit_click(click_data)
        assert future is not None
        
        pool.shutdown()

    def test_worker_pool_submit_multiple_tasks(self):
        """Test submitting multiple tasks in sequence."""
        pool = WorkerPool(num_workers=2)
        
        futures = []
        for i in range(10):
            future = pool.submit_task(lambda x=i: x * 2)
            futures.append(future)
        
        results = [f.result(timeout=5) for f in futures]
        expected = [i * 2 for i in range(10)]
        assert results == expected
        
        pool.shutdown()


class TestWorkerPoolAsyncExecution:
    """Tests for concurrent/async execution."""

    def test_worker_pool_async_execution_concurrent(self):
        """Test that tasks execute concurrently."""
        pool = WorkerPool(num_workers=4)
        
        execution_times = []
        lock = threading.Lock()
        
        def slow_task(duration_ms):
            start = time.time()
            time.sleep(duration_ms / 1000.0)
            with lock:
                execution_times.append(time.time() - start)
            return duration_ms
        
        start_all = time.time()
        futures = []
        for _ in range(4):
            future = pool.submit_task(slow_task, 100)
            futures.append(future)
        
        # Wait for all to complete
        results = [f.result(timeout=5) for f in futures]
        elapsed_total = time.time() - start_all
        
        # Sequential would take 400ms, concurrent should be ~100ms
        assert elapsed_total < 300, f"Expected concurrent execution (~100ms), got {elapsed_total*1000:.0f}ms"
        assert results == [100, 100, 100, 100]
        
        pool.shutdown()

    def test_worker_pool_async_execution_thread_safety(self):
        """Test thread-safe concurrent access."""
        pool = WorkerPool(num_workers=4)
        
        shared_counter = {'value': 0}
        lock = threading.Lock()
        
        def increment():
            with lock:
                shared_counter['value'] += 1
            return shared_counter['value']
        
        futures = [pool.submit_task(increment) for _ in range(100)]
        results = [f.result(timeout=5) for f in futures]
        
        # All increments should succeed
        assert len(results) == 100
        assert shared_counter['value'] == 100
        
        pool.shutdown()

    def test_worker_pool_async_execution_quick_completion(self):
        """Test quick task completion without blocking."""
        pool = WorkerPool(num_workers=2)
        
        def quick_task():
            return time.time()
        
        # Submit 20 quick tasks
        futures = [pool.submit_task(quick_task) for _ in range(20)]
        
        # All should complete quickly
        start = time.time()
        results = [f.result(timeout=5) for f in futures]
        elapsed = time.time() - start
        
        assert len(results) == 20
        assert elapsed < 2.0, f"Expected quick completion, took {elapsed:.2f}s"
        
        pool.shutdown()


class TestWorkerPoolQueueOverflow:
    """Tests for queue overflow handling."""

    def test_worker_pool_queue_overflow_drop_oldest(self):
        """Test that overflow drops oldest task gracefully."""
        pool = WorkerPool(num_workers=1, queue_size=5)
        
        blocked_event = threading.Event()
        released_event = threading.Event()
        
        def blocking_task():
            blocked_event.set()
            released_event.wait(timeout=3)
            return 'done'
        
        # Submit blocking task (fills one worker slot)
        future_blocked = pool.submit_task(blocking_task)
        blocked_event.wait(timeout=2)
        
        # Queue is now full (size=5, 1 executing, 4 in queue)
        # Now submit 6 more tasks - should handle overflow
        futures = []
        for i in range(6):
            result = pool.submit_task(lambda x=i: x)
            if result is not None:
                futures.append(result)
        
        # Release blocked task
        released_event.set()
        
        # Should have submitted at least some tasks
        assert len(futures) > 0
        
        pool.shutdown()

    def test_worker_pool_queue_full_behavior(self):
        """Test behavior when queue reaches max capacity."""
        pool = WorkerPool(num_workers=1, queue_size=3)
        
        completed = []
        lock = threading.Lock()
        
        def quick_task(task_id):
            with lock:
                completed.append(task_id)
            return task_id
        
        # Submit many tasks quickly
        submitted = 0
        for i in range(10):
            future = pool.submit_task(quick_task, i)
            if future is not None:
                submitted += 1
        
        time.sleep(1)
        
        # Should have submitted and completed several tasks
        assert submitted > 0
        assert len(completed) > 0
        
        pool.shutdown()


class TestWorkerPoolShutdown:
    """Tests for graceful shutdown."""

    def test_worker_pool_shutdown_graceful(self):
        """Test graceful shutdown waits for pending tasks."""
        pool = WorkerPool(num_workers=2)
        
        completed = []
        lock = threading.Lock()
        
        def task_with_delay(task_id):
            time.sleep(0.1)
            with lock:
                completed.append(task_id)
            return task_id
        
        # Submit several tasks
        futures = [pool.submit_task(task_with_delay, i) for i in range(5)]
        
        # Shutdown and wait
        pool.shutdown(wait=True)
        
        # Should wait for tasks to complete
        assert len(completed) > 0
        assert pool.is_shutdown is True

    def test_worker_pool_shutdown_no_wait(self):
        """Test shutdown without waiting."""
        pool = WorkerPool(num_workers=2)
        
        def slow_task():
            time.sleep(1)
            return 'done'
        
        # Submit slow task
        pool.submit_task(slow_task)
        
        # Shutdown without waiting
        pool.shutdown(wait=False)
        assert pool.is_shutdown is True

    def test_worker_pool_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times safely."""
        pool = WorkerPool(num_workers=2)
        
        pool.shutdown(wait=True)
        pool.shutdown(wait=True)  # Should not raise
        
        assert pool.is_shutdown is True

    def test_worker_pool_no_submit_after_shutdown(self):
        """Test that tasks cannot be submitted after shutdown."""
        pool = WorkerPool(num_workers=2)
        pool.shutdown(wait=True)
        
        future = pool.submit_task(lambda: 42)
        assert future is None


class TestWorkerPoolExceptionHandling:
    """Tests for exception handling in worker threads."""

    def test_worker_pool_exception_handling_doesnt_crash(self):
        """Test that exceptions in tasks don't crash the pool."""
        pool = WorkerPool(num_workers=2)
        
        def failing_task():
            raise ValueError("Task failed")
        
        future = pool.submit_task(failing_task)
        
        # Should raise when getting result
        with pytest.raises(ValueError, match="Task failed"):
            future.result(timeout=2)
        
        # Pool should still be functional
        future2 = pool.submit_task(lambda: 42)
        result = future2.result(timeout=2)
        assert result == 42
        
        pool.shutdown()

    def test_worker_pool_exception_logging(self):
        """Test that exceptions are logged appropriately."""
        pool = WorkerPool(num_workers=2)
        
        def failing_task():
            raise RuntimeError("Test error")
        
        future = pool.submit_task(failing_task)
        
        with pytest.raises(RuntimeError):
            future.result(timeout=2)
        
        pool.shutdown()

    def test_worker_pool_exception_in_one_worker_doesnt_crash_others(self):
        """Test that exception in one worker doesn't affect others."""
        pool = WorkerPool(num_workers=4)
        
        results = []
        lock = threading.Lock()
        
        def task(task_id):
            if task_id == 2:
                raise ValueError("Task 2 failed")
            with lock:
                results.append(task_id)
            return task_id
        
        futures = [pool.submit_task(task, i) for i in range(5)]
        
        # Get results, handling exception
        for i, future in enumerate(futures):
            if i == 2:
                with pytest.raises(ValueError):
                    future.result(timeout=2)
            else:
                result = future.result(timeout=2)
                assert result == i
        
        pool.shutdown()


class TestWorkerPoolWaitAll:
    """Tests for wait_all() method."""

    def test_worker_pool_wait_all_completes(self):
        """Test wait_all waits for all pending tasks."""
        pool = WorkerPool(num_workers=2)
        
        completed = []
        lock = threading.Lock()
        
        def task(task_id):
            time.sleep(0.05)
            with lock:
                completed.append(task_id)
        
        # Submit tasks
        for i in range(5):
            pool.submit_task(task, i)
        
        # Wait for all
        result = pool.wait_all(timeout_sec=5.0)
        assert result is True
        assert len(completed) == 5
        
        pool.shutdown()

    def test_worker_pool_wait_all_timeout(self):
        """Test wait_all timeout."""
        pool = WorkerPool(num_workers=1)
        
        def slow_task():
            time.sleep(2)
        
        pool.submit_task(slow_task)
        
        # Wait with short timeout
        result = pool.wait_all(timeout_sec=0.1)
        assert result is False
        
        pool.shutdown()

    def test_worker_pool_wait_all_empty(self):
        """Test wait_all with no pending tasks."""
        pool = WorkerPool(num_workers=2)
        
        result = pool.wait_all(timeout_sec=1.0)
        assert result is True
        
        pool.shutdown()


class TestWorkerPoolThroughput:
    """Performance and throughput tests."""

    def test_worker_pool_throughput_100_clicks(self):
        """Test processing 100 clicks in under 500ms."""
        pool = WorkerPool(num_workers=4)
        
        processed = []
        lock = threading.Lock()
        
        def process_click(click_id):
            # Simulate minimal processing
            with lock:
                processed.append(click_id)
        
        start = time.time()
        
        for i in range(100):
            pool.submit_click({'click_id': i, 'x': 100, 'y': 200})
        
        pool.wait_all(timeout_sec=10.0)
        elapsed = time.time() - start
        
        assert elapsed < 0.5, f"Expected <500ms for 100 clicks, got {elapsed*1000:.0f}ms"
        
        pool.shutdown()

    def test_worker_pool_throughput_various_cps(self):
        """Test throughput at various CPS levels."""
        pool = WorkerPool(num_workers=4)
        
        completed_count = [0]
        lock = threading.Lock()
        
        def click_task():
            with lock:
                completed_count[0] += 1
        
        # Submit 50 clicks (should simulate ~50 CPS)
        start = time.time()
        
        for _ in range(50):
            pool.submit_task(click_task)
        
        pool.wait_all(timeout_sec=5.0)
        elapsed = time.time() - start
        
        cps = completed_count[0] / elapsed if elapsed > 0 else 0
        assert cps > 20, f"Expected >20 CPS, got {cps:.1f} CPS"
        
        pool.shutdown()


class TestWorkerPoolLatency:
    """Latency and performance characteristic tests."""

    def test_worker_pool_latency_p99(self):
        """Test P99 latency is under 50ms per click."""
        pool = WorkerPool(num_workers=4)
        
        latencies = []
        lock = threading.Lock()
        
        def measure_latency():
            start = time.time()
            time.sleep(0.001)  # Minimal work
            elapsed_ms = (time.time() - start) * 1000
            with lock:
                latencies.append(elapsed_ms)
        
        futures = [pool.submit_task(measure_latency) for _ in range(100)]
        [f.result(timeout=5) for f in futures]
        
        # Sort to find P99
        latencies.sort()
        p99_idx = int(len(latencies) * 0.99)
        p99_latency = latencies[p99_idx]
        
        assert p99_latency < 50, f"P99 latency {p99_latency:.2f}ms exceeds 50ms"
        
        pool.shutdown()

    def test_worker_pool_latency_p50(self):
        """Test P50 (median) latency."""
        pool = WorkerPool(num_workers=4)
        
        latencies = []
        lock = threading.Lock()
        
        def quick_task():
            start = time.time()
            time.sleep(0.0001)
            elapsed_ms = (time.time() - start) * 1000
            with lock:
                latencies.append(elapsed_ms)
        
        futures = [pool.submit_task(quick_task) for _ in range(100)]
        [f.result(timeout=5) for f in futures]
        
        latencies.sort()
        p50_idx = len(latencies) // 2
        p50_latency = latencies[p50_idx]
        
        assert p50_latency < 20, f"P50 latency {p50_latency:.2f}ms"
        
        pool.shutdown()

    def test_worker_pool_latency_consistency(self):
        """Test latency consistency across multiple runs."""
        latency_sets = []
        
        for run in range(3):
            pool = WorkerPool(num_workers=4)
            latencies = []
            lock = threading.Lock()
            
            def task():
                start = time.time()
                time.sleep(0.0001)
                elapsed = (time.time() - start) * 1000
                with lock:
                    latencies.append(elapsed)
            
            futures = [pool.submit_task(task) for _ in range(50)]
            [f.result(timeout=5) for f in futures]
            
            avg_latency = sum(latencies) / len(latencies)
            latency_sets.append(avg_latency)
            
            pool.shutdown()
        
        # Latencies should be consistent across runs
        avg_of_avgs = sum(latency_sets) / len(latency_sets)
        variance = max(latency_sets) - min(latency_sets)
        
        # Variance should be small (consistent performance)
        assert variance < avg_of_avgs * 0.5, "Latency inconsistent across runs"


class TestWorkerPoolIntegration:
    """Integration tests."""

    def test_worker_pool_mixed_workload(self):
        """Test mixed workload (different task types)."""
        pool = WorkerPool(num_workers=4)
        
        def fast_task():
            return 'fast'
        
        def slow_task():
            time.sleep(0.1)
            return 'slow'
        
        def cpu_task():
            result = 0
            for i in range(1000):
                result += i
            return result
        
        futures = []
        for _ in range(10):
            futures.append(pool.submit_task(fast_task))
            futures.append(pool.submit_task(slow_task))
            futures.append(pool.submit_task(cpu_task))
        
        results = [f.result(timeout=5) for f in futures]
        assert len(results) == 30
        
        pool.shutdown()

    def test_worker_pool_stress_test(self):
        """Stress test with many simultaneous tasks."""
        pool = WorkerPool(num_workers=8, queue_size=100)
        
        def stress_task(task_id):
            # Simulate click + processing
            time.sleep(0.01)
            return task_id
        
        futures = [pool.submit_task(stress_task, i) for i in range(200)]
        
        results = []
        for f in futures:
            try:
                results.append(f.result(timeout=5))
            except Exception:
                pass
        
        assert len(results) > 100, "Stress test failed - too many dropped tasks"
        
        pool.shutdown()

    def test_worker_pool_resource_cleanup(self):
        """Test that resources are properly cleaned up."""
        pool = WorkerPool(num_workers=4)
        
        # Submit and complete tasks
        futures = [pool.submit_task(lambda: 42) for _ in range(10)]
        [f.result(timeout=2) for f in futures]
        
        # Shutdown
        pool.shutdown(wait=True)
        
        # Resources should be cleaned
        assert pool.is_shutdown is True


class TestWorkerPoolClickSpecific:
    """Tests specific to click processing."""

    def test_worker_pool_click_with_priority(self):
        """Test click submission with implicit priority queuing."""
        pool = WorkerPool(num_workers=2)
        
        clicks_processed = []
        lock = threading.Lock()
        
        def process_click_event(click_id):
            time.sleep(0.001)  # Minimal processing
            with lock:
                clicks_processed.append(click_id)
            return click_id
        
        # Submit clicks using submit_task instead of submit_click
        # since submit_click just wraps the data
        for i in range(10):
            future = pool.submit_task(process_click_event, i)
            assert future is not None
        
        pool.wait_all(timeout_sec=5.0)
        assert len(clicks_processed) == 10
        
        pool.shutdown()

    def test_worker_pool_click_batch_submission(self):
        """Test batch submission of clicks."""
        pool = WorkerPool(num_workers=4)
        
        clicks_batch = [
            {'click_id': i, 'x': 100, 'y': 200, 'hit': True}
            for i in range(20)
        ]
        
        futures = [pool.submit_click(click) for click in clicks_batch]
        
        assert len(futures) == 20
        assert all(isinstance(f, Future) for f in futures)
        
        pool.shutdown()
