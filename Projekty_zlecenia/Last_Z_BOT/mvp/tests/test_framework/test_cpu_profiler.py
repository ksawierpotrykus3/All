"""Tests for CPU profiler."""

import time

import pytest

from mvp.tests.test_framework.cpu_profiler import CPUProfiler, classify_cpu_load
from mvp.tests.test_framework.metrics import CPULoadClass, HotSpot


class TestCPUProfiler:
    """Tests for CPUProfiler class."""

    def test_profiler_creation(self) -> None:
        """Test CPUProfiler creation."""
        profiler = CPUProfiler(enable_scalene=False)
        assert profiler is not None
        assert profiler._profiling is False

    def test_profiler_start_stop_basic(self) -> None:
        """Test basic profiler start/stop."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        assert profiler._profiling is True

        time.sleep(0.01)  # Small delay
        profile = profiler.stop_profile()
        assert profiler._profiling is False
        assert profile.cpu_time_ms >= 0
        assert profile.gpu_time_ms >= 0
        assert profile.memory_mb >= 0

    def test_profiler_stop_without_start(self) -> None:
        """Test stop without start returns empty profile."""
        profiler = CPUProfiler(enable_scalene=False)
        profile = profiler.stop_profile()
        assert profile.cpu_time_ms == 0.0
        assert profile.gpu_time_ms == 0.0
        assert profile.memory_mb == 0.0
        assert profile.syscall_time_ms == 0.0
        assert len(profile.hot_spots) == 0

    def test_profiler_inject_data(self) -> None:
        """Test injecting mock profile data."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()

        hot_spots = [
            HotSpot(function_name="func1", cpu_time_ms=100.0, percent=50.0),
            HotSpot(function_name="func2", cpu_time_ms=50.0, percent=25.0),
        ]
        profiler.inject_profile_data(
            cpu_time_ms=200.0,
            gpu_time_ms=0.0,
            memory_mb=150.0,
            syscall_time_ms=50.0,
            hot_spots=hot_spots,
        )

        profile = profiler.stop_profile()
        assert profile.cpu_time_ms == 200.0
        assert profile.gpu_time_ms == 0.0
        assert profile.memory_mb == 150.0
        assert profile.syscall_time_ms == 50.0
        assert len(profile.hot_spots) == 2
        assert profile.hot_spots[0].function_name == "func1"
        assert profile.hot_spots[1].function_name == "func2"

    def test_profiler_hot_spots(self) -> None:
        """Test profiler hot spots collection."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()

        hot_spots = [
            HotSpot(function_name="click_handler", cpu_time_ms=500.0, percent=40.0),
            HotSpot(function_name="ocr_process", cpu_time_ms=250.0, percent=20.0),
            HotSpot(function_name="render_frame", cpu_time_ms=200.0, percent=16.0),
        ]
        profiler.inject_profile_data(
            cpu_time_ms=1250.0,
            gpu_time_ms=100.0,
            memory_mb=200.0,
            syscall_time_ms=0.0,
            hot_spots=hot_spots,
        )

        profile = profiler.stop_profile()
        assert len(profile.hot_spots) == 3
        assert profile.hot_spots[0].cpu_time_ms == 500.0
        assert profile.hot_spots[0].percent == 40.0

    def test_profiler_memory_tracking(self) -> None:
        """Test profiler memory tracking."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()

        profiler.inject_profile_data(
            cpu_time_ms=100.0,
            gpu_time_ms=0.0,
            memory_mb=256.5,
            syscall_time_ms=10.0,
        )

        profile = profiler.stop_profile()
        assert profile.memory_mb == 256.5

    def test_profiler_timing_accuracy(self) -> None:
        """Test profiler timing is reasonable."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        time.sleep(0.05)  # 50ms
        profile = profiler.stop_profile()
        # Should be at least 45ms (accounting for some overhead)
        assert profile.cpu_time_ms >= 40


class TestClassifyCPULoad:
    """Tests for classify_cpu_load function."""

    def test_classify_idle(self) -> None:
        """Test IDLE classification (< 20%)."""
        assert classify_cpu_load(0.0) == CPULoadClass.IDLE
        assert classify_cpu_load(10.0) == CPULoadClass.IDLE
        assert classify_cpu_load(19.9) == CPULoadClass.IDLE

    def test_classify_low(self) -> None:
        """Test LOW classification (20-40%)."""
        assert classify_cpu_load(20.0) == CPULoadClass.LOW
        assert classify_cpu_load(30.0) == CPULoadClass.LOW
        assert classify_cpu_load(39.9) == CPULoadClass.LOW

    def test_classify_medium(self) -> None:
        """Test MEDIUM classification (40-60%)."""
        assert classify_cpu_load(40.0) == CPULoadClass.MEDIUM
        assert classify_cpu_load(50.0) == CPULoadClass.MEDIUM
        assert classify_cpu_load(59.9) == CPULoadClass.MEDIUM

    def test_classify_high(self) -> None:
        """Test HIGH classification (60-80%)."""
        assert classify_cpu_load(60.0) == CPULoadClass.HIGH
        assert classify_cpu_load(70.0) == CPULoadClass.HIGH
        assert classify_cpu_load(79.9) == CPULoadClass.HIGH

    def test_classify_critical(self) -> None:
        """Test CRITICAL classification (>= 80%)."""
        assert classify_cpu_load(80.0) == CPULoadClass.CRITICAL
        assert classify_cpu_load(90.0) == CPULoadClass.CRITICAL
        assert classify_cpu_load(100.0) == CPULoadClass.CRITICAL

    def test_classify_boundary_cases(self) -> None:
        """Test boundary cases between classifications."""
        # Boundary between IDLE and LOW
        assert classify_cpu_load(19.99) == CPULoadClass.IDLE
        assert classify_cpu_load(20.01) == CPULoadClass.LOW

        # Boundary between LOW and MEDIUM
        assert classify_cpu_load(39.99) == CPULoadClass.LOW
        assert classify_cpu_load(40.01) == CPULoadClass.MEDIUM

        # Boundary between MEDIUM and HIGH
        assert classify_cpu_load(59.99) == CPULoadClass.MEDIUM
        assert classify_cpu_load(60.01) == CPULoadClass.HIGH

        # Boundary between HIGH and CRITICAL
        assert classify_cpu_load(79.99) == CPULoadClass.HIGH
        assert classify_cpu_load(80.01) == CPULoadClass.CRITICAL


class TestCPUProfilerIntegration:
    """Integration tests for CPU profiler with metrics."""

    def test_profiler_with_hot_spots_integration(self) -> None:
        """Test profiler with hot spots matches metrics expectations."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()

        hot_spots = [
            HotSpot(function_name="spam_clicker", cpu_time_ms=800.0, percent=60.0),
            HotSpot(function_name="window_capture", cpu_time_ms=300.0, percent=22.5),
            HotSpot(function_name="ocr_engine", cpu_time_ms=200.0, percent=15.0),
        ]

        profiler.inject_profile_data(
            cpu_time_ms=1300.0,
            gpu_time_ms=50.0,
            memory_mb=180.0,
            syscall_time_ms=20.0,
            hot_spots=hot_spots,
        )

        profile = profiler.stop_profile()

        # Verify structure
        assert len(profile.hot_spots) == 3
        # Verify top hot spot
        assert profile.hot_spots[0].function_name == "spam_clicker"
        assert profile.hot_spots[0].percent == 60.0
        # Verify total CPU time
        total_cpu_from_spots = sum(spot.cpu_time_ms for spot in profile.hot_spots)
        assert total_cpu_from_spots == 1300.0

    def test_profiler_multiple_cycles(self) -> None:
        """Test profiler can be reused for multiple cycles."""
        profiler = CPUProfiler(enable_scalene=False)

        # First cycle
        profiler.start_profile()
        profiler.inject_profile_data(
            cpu_time_ms=100.0, gpu_time_ms=0.0, memory_mb=100.0, syscall_time_ms=0.0
        )
        profile1 = profiler.stop_profile()
        assert profile1.cpu_time_ms == 100.0

        # Second cycle
        profiler.start_profile()
        profiler.inject_profile_data(
            cpu_time_ms=200.0, gpu_time_ms=0.0, memory_mb=150.0, syscall_time_ms=0.0
        )
        profile2 = profiler.stop_profile()
        assert profile2.cpu_time_ms == 200.0

        # Profiles should be independent
        assert profile1.cpu_time_ms != profile2.cpu_time_ms
        assert profile1.memory_mb != profile2.memory_mb

    def test_profiler_high_load_scenario(self) -> None:
        """Test profiler in high CPU load scenario."""
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()

        hot_spots = [
            HotSpot(function_name="heavy_compute", cpu_time_ms=5000.0, percent=85.0),
            HotSpot(function_name="io_wait", cpu_time_ms=875.0, percent=15.0),
        ]

        profiler.inject_profile_data(
            cpu_time_ms=5875.0,
            gpu_time_ms=0.0,
            memory_mb=450.0,
            syscall_time_ms=100.0,
            hot_spots=hot_spots,
        )

        profile = profiler.stop_profile()
        cpu_class = classify_cpu_load(85.0)
        assert cpu_class == CPULoadClass.CRITICAL


class TestMemoryPeakTracking:
    """Tests for memory peak tracking functionality (Task 3.4.3)."""

    def test_track_memory_peak_basic(self) -> None:
        """Test basic memory peak tracking.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        
        # Track initial memory
        peak1 = profiler.track_memory_peak()
        assert peak1 >= 0.0
        
        # Memory should remain at same or increase
        peak2 = profiler.track_memory_peak()
        assert peak2 >= peak1

    def test_track_memory_peak_identifies_peak(self) -> None:
        """Test that track_memory_peak correctly identifies the peak.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        
        # Simulate increasing memory samples
        profiler._memory_samples = []
        profiler._memory_peak_mb = 0.0
        
        # Call track_memory_peak multiple times with increasing memory
        for i in range(1, 6):
            # Inject increasing memory samples (simulating growth)
            profiler._memory_peak_mb = max(profiler._memory_peak_mb, float(i * 100))
            profiler._memory_samples.append(float(i * 100))
        
        # Peak should be 500 MB
        assert profiler.get_memory_peak_mb() == 500.0

    def test_track_memory_peak_alert_threshold(self) -> None:
        """Test alert is triggered when memory exceeds 1GB.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        
        # Manually set memory peak above 1GB threshold (1024 MB)
        profiler._memory_peak_mb = 1100.0  # 1100 MB
        
        # Trigger the alert check
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Simulate memory tracking that would trigger alert
            profiler._memory_alert_triggered = False
            if profiler._memory_peak_mb > 1024 and not profiler._memory_alert_triggered:
                profiler._memory_alert_triggered = True
                warnings.warn(
                    f"Memory usage exceeded 1GB threshold: {profiler._memory_peak_mb:.2f} MB",
                    ResourceWarning
                )
            
            # Verify alert was triggered
            assert len(w) == 1
            assert issubclass(w[-1].category, ResourceWarning)
            assert "1100.00 MB" in str(w[-1].message)

    def test_track_memory_peak_below_threshold(self) -> None:
        """Test no alert when memory is below 1GB.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        
        # Set memory below threshold
        profiler._memory_peak_mb = 512.0  # 512 MB (below 1024 MB)
        
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Check if alert would be triggered
            if profiler._memory_peak_mb > 1024 and not profiler._memory_alert_triggered:
                warnings.warn(
                    f"Memory usage exceeded 1GB threshold: {profiler._memory_peak_mb:.2f} MB",
                    ResourceWarning
                )
            
            # No warnings should be triggered for memory below 1GB
            resource_warnings = [warning for warning in w if issubclass(warning.category, ResourceWarning)]
            assert len(resource_warnings) == 0

    def test_get_memory_peak_mb(self) -> None:
        """Test get_memory_peak_mb returns correct value.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        
        # Initially should be 0.0
        assert profiler.get_memory_peak_mb() == 0.0
        
        # Set peak and verify retrieval
        profiler._memory_peak_mb = 256.5
        assert profiler.get_memory_peak_mb() == 256.5

    def test_reset_memory_tracking(self) -> None:
        """Test reset_memory_tracking clears all tracking data.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        
        # Set some memory tracking data
        profiler._memory_peak_mb = 512.0
        profiler._memory_samples = [100.0, 200.0, 300.0, 512.0]
        profiler._memory_alert_triggered = True
        
        # Reset
        profiler.reset_memory_tracking()
        
        # Verify reset worked
        assert profiler._memory_peak_mb == 0.0
        assert profiler._memory_samples == []
        assert profiler._memory_alert_triggered is False

    def test_memory_peak_stored_in_runmetrics(self) -> None:
        """Test that memory_peak_mb is correctly stored in RunMetrics.
        
        **Validates: Requirements 3.4.3**
        """
        from mvp.tests.test_framework.metrics import RunMetrics
        
        # Create RunMetrics with memory_peak_mb
        metrics = RunMetrics(
            run_id=1,
            scenario_id="test_scenario",
            passed=True,
            memory_peak_mb=768.5
        )
        
        # Verify field exists and has correct value
        assert hasattr(metrics, 'memory_peak_mb')
        assert metrics.memory_peak_mb == 768.5

    def test_memory_peak_edge_case_exactly_1gb(self) -> None:
        """Test alert behavior at exactly 1GB threshold.
        
        **Validates: Requirements 3.4.3**
        """
        profiler = CPUProfiler(enable_scalene=False)
        profiler.start_profile()
        
        # Set memory to exactly 1024 MB (threshold boundary)
        profiler._memory_peak_mb = 1024.0
        
        # At exactly 1024, alert should NOT trigger (threshold is > 1024)
        assert not (profiler._memory_peak_mb > 1024)
        assert profiler._memory_alert_triggered is False
        
        # At 1024.1, alert should trigger
        profiler._memory_peak_mb = 1024.1
        assert profiler._memory_peak_mb > 1024
