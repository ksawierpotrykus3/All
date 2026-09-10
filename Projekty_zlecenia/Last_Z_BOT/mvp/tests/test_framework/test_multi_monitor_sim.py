"""Tests for multi-monitor coordinate transformation simulator."""

import pytest
from .scenarios import MonitorConfig
from .multi_monitor_sim import MultiMonitorSimulator, BASE_DPI


class TestMultiMonitorSimulator:
    """Test suite for MultiMonitorSimulator."""

    @pytest.fixture
    def single_monitor(self):
        """Single monitor setup: 1920x1080 @ 96 DPI."""
        return [MonitorConfig(id=0, width=1920, height=1080, dpi=96)]

    @pytest.fixture
    def dual_monitor_same_dpi(self):
        """Dual monitor setup with same DPI: 1920x1080 @ 96 DPI each, side-by-side."""
        return [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
        ]

    @pytest.fixture
    def dual_monitor_different_dpi(self):
        """Dual monitor setup with different DPI: 96 DPI and 144 DPI."""
        return [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=144, offset_x=1920, offset_y=0),
        ]

    def test_single_monitor_no_transform(self, single_monitor):
        """Test that same-monitor transform returns identity."""
        sim = MultiMonitorSimulator(single_monitor)

        px, py = 100, 200
        result_px, result_py = sim.transform_coords(px, py, 0, 0)

        assert result_px == px
        assert result_py == py

    def test_transform_same_dpi_no_change(self, dual_monitor_same_dpi):
        """Test that transform with same DPI and no offset returns identity."""
        sim = MultiMonitorSimulator(dual_monitor_same_dpi)

        px, py = 100, 200
        result_px, result_py = sim.transform_coords(px, py, 0, 0)

        assert result_px == px
        assert result_py == py

    def test_transform_different_dpi_96_to_144(self, dual_monitor_different_dpi):
        """Test coordinate scaling from 96 DPI to 144 DPI (1.5x).

        Transform from monitor 0 (96 DPI) to monitor 1 (144 DPI).
        """
        sim = MultiMonitorSimulator(dual_monitor_different_dpi)

        # Transform from monitor 0 (96 DPI) to monitor 1 (144 DPI)
        px, py = 96, 96  # 96 pixels at 96 DPI
        result_px, result_py = sim.transform_coords(px, py, 0, 1)

        # Expected: 96 * (144/96) - 1920 = 144 - 1920 = -1776
        assert result_px == -1776
        assert result_py == 144

    def test_transform_144_to_96_scaling(self, dual_monitor_different_dpi):
        """Test scaling down from 144 DPI to 96 DPI (0.667x)."""
        sim = MultiMonitorSimulator(dual_monitor_different_dpi)

        # Transform from monitor 1 (144 DPI, offset 1920) to monitor 0 (96 DPI, offset 0)
        px, py = 144, 144  # 144 pixels at 144 DPI in monitor 1's local space
        result_px, result_py = sim.transform_coords(px, py, 1, 0)

        # Expected math:
        # - abs: (144 + 1920, 144 + 0) = (2064, 144)
        # - scaled: (2064 * 96/144, 144 * 96/144) = (1376, 96)
        # - local: (1376 - 0, 96 - 0) = (1376, 96)

        assert result_px == 1376
        assert result_py == 96

    def test_validate_click_in_bounds(self, single_monitor):
        """Test that valid click target is accepted."""
        sim = MultiMonitorSimulator(single_monitor)

        assert sim.validate_click_target(0, 0, 0) is True
        assert sim.validate_click_target(1919, 1079, 0) is True
        assert sim.validate_click_target(960, 540, 0) is True

    def test_validate_click_out_of_bounds(self, single_monitor):
        """Test that invalid click target is rejected."""
        sim = MultiMonitorSimulator(single_monitor)

        assert sim.validate_click_target(-1, 0, 0) is False
        assert sim.validate_click_target(1920, 0, 0) is False
        assert sim.validate_click_target(0, -1, 0) is False
        assert sim.validate_click_target(0, 1080, 0) is False
        assert sim.validate_click_target(2000, 2000, 0) is False

    def test_validate_click_invalid_monitor(self, single_monitor):
        """Test that invalid monitor ID is rejected."""
        sim = MultiMonitorSimulator(single_monitor)

        assert sim.validate_click_target(100, 100, 999) is False

    def test_monitor_bounds_local(self, single_monitor):
        """Test monitor bounds in local coordinate space."""
        sim = MultiMonitorSimulator(single_monitor)

        x_min, y_min, x_max, y_max = sim.get_monitor_bounds(0)

        assert x_min == 0
        assert y_min == 0
        assert x_max == 1920
        assert y_max == 1080

    def test_monitor_bounds_absolute(self, dual_monitor_same_dpi):
        """Test monitor bounds in absolute screen coordinate space."""
        sim = MultiMonitorSimulator(dual_monitor_same_dpi)

        # Monitor 0: offset (0, 0), size 1920x1080
        x_min, y_min, x_max, y_max = sim.get_monitor_bounds_absolute(0)
        assert x_min == 0
        assert y_min == 0
        assert x_max == 1920
        assert y_max == 1080

        # Monitor 1: offset (1920, 0), size 1920x1080
        x_min, y_min, x_max, y_max = sim.get_monitor_bounds_absolute(1)
        assert x_min == 1920
        assert y_min == 0
        assert x_max == 3840
        assert y_max == 1080

    def test_monitor_bounds_invalid(self, single_monitor):
        """Test that invalid monitor returns None."""
        sim = MultiMonitorSimulator(single_monitor)

        bounds = sim.get_monitor_bounds(999)
        assert bounds is None

    def test_transform_time_estimation_same_monitor(self, single_monitor):
        """Test that same-monitor transform time is minimal."""
        sim = MultiMonitorSimulator(single_monitor)

        time_ms = sim.estimate_transform_time(0, 0)

        assert time_ms == 0.0

    def test_transform_time_estimation_same_dpi(self, dual_monitor_same_dpi):
        """Test transform time with same DPI (minimal overhead)."""
        sim = MultiMonitorSimulator(dual_monitor_same_dpi)

        time_ms = sim.estimate_transform_time(0, 1)

        # Same DPI: 5.0ms
        assert time_ms == 5.0

    def test_transform_time_estimation_different_dpi(self, dual_monitor_different_dpi):
        """Test transform time with different DPI (overhead for scaling)."""
        sim = MultiMonitorSimulator(dual_monitor_different_dpi)

        time_ms = sim.estimate_transform_time(0, 1)

        # Different DPI: 10.0ms
        assert time_ms == 10.0

    def test_validate_click_target_absolute(self, dual_monitor_same_dpi):
        """Test absolute coordinate validation across monitors."""
        sim = MultiMonitorSimulator(dual_monitor_same_dpi)

        # Click on monitor 0 (offset 0, width 1920)
        is_valid, monitor_id = sim.validate_click_target_absolute(100, 100)
        assert is_valid is True
        assert monitor_id == 0

        # Click on monitor 1 (offset 1920, width 1920, so range [1920, 3840))
        is_valid, monitor_id = sim.validate_click_target_absolute(2000, 100)
        assert is_valid is True
        assert monitor_id == 1

        # Click at right edge of monitor 0 (at x=1919)
        is_valid, monitor_id = sim.validate_click_target_absolute(1919, 100)
        assert is_valid is True
        assert monitor_id == 0

        # Click at left edge of monitor 1 (at x=1920)
        is_valid, monitor_id = sim.validate_click_target_absolute(1920, 100)
        assert is_valid is True
        assert monitor_id == 1

        # Click way out of bounds
        is_valid, monitor_id = sim.validate_click_target_absolute(-100, -100)
        assert is_valid is False
        assert monitor_id is None

    def test_transform_with_timing(self, dual_monitor_same_dpi):
        """Test that transform_with_timing returns valid result."""
        sim = MultiMonitorSimulator(dual_monitor_same_dpi)

        result = sim.transform_with_timing(100, 100, 0, 1)

        assert result.source_monitor_id == 0
        assert result.target_monitor_id == 1
        assert result.source_coords == (100, 100)
        assert result.dpi_source == 96
        assert result.dpi_target == 96
        assert result.scale_factor == 1.0
        assert result.transform_time_ms >= 0
        assert result.valid is True

    def test_dpi_mismatch_error_distance(self, dual_monitor_different_dpi):
        """Test DPI mismatch error calculation."""
        sim = MultiMonitorSimulator(dual_monitor_different_dpi)

        # Original coords at 96 DPI
        original_px, original_py = 100, 100

        # Transform to 144 DPI
        result_px, result_py = sim.transform_coords(
            original_px, original_py, 0, 1
        )

        # Calculate error distance
        error_distance = sim.get_dpi_mismatch_error(
            original_px, original_py, result_px, result_py
        )

        # Error should be > 0 since coordinates changed
        assert error_distance > 0

    def test_invalid_monitor_initialization(self):
        """Test that invalid monitor setup raises error."""
        # Empty monitor list
        with pytest.raises(ValueError):
            MultiMonitorSimulator([])

    def test_invalid_monitor_dimensions(self):
        """Test that invalid monitor dimensions raise error."""
        # Zero width
        with pytest.raises(ValueError):
            MultiMonitorSimulator([MonitorConfig(id=0, width=0, height=1080, dpi=96)])

        # Negative height
        with pytest.raises(ValueError):
            MultiMonitorSimulator([MonitorConfig(id=0, width=1920, height=-1, dpi=96)])

    def test_invalid_monitor_dpi(self):
        """Test that invalid DPI raises error."""
        with pytest.raises(ValueError):
            MultiMonitorSimulator([MonitorConfig(id=0, width=1920, height=1080, dpi=0)])

    def test_transform_with_invalid_source_monitor(self, single_monitor):
        """Test that transform with invalid source monitor raises error."""
        sim = MultiMonitorSimulator(single_monitor)

        with pytest.raises(ValueError):
            sim.transform_coords(100, 100, 999, 0)

    def test_transform_with_invalid_target_monitor(self, single_monitor):
        """Test that transform with invalid target monitor raises error."""
        sim = MultiMonitorSimulator(single_monitor)

        with pytest.raises(ValueError):
            sim.transform_coords(100, 100, 0, 999)

    def test_complex_multi_monitor_setup(self):
        """Test complex multi-monitor setup with various configurations."""
        monitors = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=144, offset_x=1920, offset_y=0),
            MonitorConfig(id=2, width=1920, height=1080, dpi=96, offset_x=3840, offset_y=0),
        ]
        sim = MultiMonitorSimulator(monitors)

        # Validate all monitors present
        assert len(sim.monitors) == 3

        # Test clicks on each monitor (absolute coords)
        is_valid, mid = sim.validate_click_target_absolute(100, 100)
        assert is_valid and mid == 0

        is_valid, mid = sim.validate_click_target_absolute(2000, 100)
        assert is_valid and mid == 1

        is_valid, mid = sim.validate_click_target_absolute(4000, 100)
        assert is_valid and mid == 2
