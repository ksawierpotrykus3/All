"""Tests for multi-monitor coordinate transformation simulator."""

import pytest

from mvp.tests.test_framework.multi_monitor_sim import MultiMonitorSimulator
from mvp.tests.test_framework.scenarios import MonitorConfig


class TestMultiMonitorSimulator:
    """Tests for MultiMonitorSimulator."""

    def test_initialization_single_monitor(self) -> None:
        """Test initialization with single monitor."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        assert 0 in simulator.monitors
        assert simulator.monitors[0] == config

    def test_initialization_multiple_monitors(self) -> None:
        """Test initialization with multiple monitors."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        assert len(simulator.monitors) == 2
        assert 0 in simulator.monitors
        assert 1 in simulator.monitors

    def test_initialization_empty_config_raises_error(self) -> None:
        """Test that empty config list raises error."""
        with pytest.raises(ValueError, match="At least one monitor config required"):
            MultiMonitorSimulator([])

    def test_same_dpi_transform_no_offset(self) -> None:
        """Test coordinate transform between monitors with same DPI and no offset."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Point at (100, 100) on monitor 0
        result_x, result_y = simulator.transform_coords(100, 100, 0, 1)

        # Should be same coordinates on monitor 1 (since same DPI and direct adjacency)
        # abs_x = 100 + 0 = 100, no scaling, final = 100 - 1920 = -1820
        # But coordinates are relative to each monitor, so we're transforming within monitor space
        assert result_x == -1820  # 100 + 0 - 1920
        assert result_y == 100

    def test_different_dpi_transform_96_to_144(self) -> None:
        """Test coordinate transform with DPI scaling from 96 to 144 DPI."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=2560, height=1440, dpi=144, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Point at (100, 100) on 96 DPI monitor
        result_x, result_y = simulator.transform_coords(100, 100, 0, 1)

        # DPI ratio = 144/96 = 1.5
        # abs_x = 100 + 0 = 100
        # scaled = 100 * 1.5 = 150
        # final = 150 - 1920 = -1770
        assert result_x == -1770
        assert result_y == 150

    def test_different_dpi_transform_144_to_96(self) -> None:
        """Test coordinate transform with DPI scaling from 144 to 96 DPI."""
        configs = [
            MonitorConfig(id=0, width=2560, height=1440, dpi=144, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=2560, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Point at (150, 150) on 144 DPI monitor
        result_x, result_y = simulator.transform_coords(150, 150, 0, 1)

        # DPI ratio = 96/144 = 0.666...
        # abs_x = 150 + 0 = 150
        # scaled = 150 * (96/144) = 100
        # final = 100 - 2560 = -2460
        assert result_x == -2460
        assert result_y == 100

    def test_same_monitor_transform(self) -> None:
        """Test transforming coordinates within same monitor."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        result_x, result_y = simulator.transform_coords(500, 600, 0, 0)

        # Should be identity: abs_x = 500 + 0 = 500, no scaling, final = 500 - 0 = 500
        assert result_x == 500
        assert result_y == 600

    def test_invalid_source_monitor_raises_error(self) -> None:
        """Test that invalid source monitor ID raises error."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        with pytest.raises(ValueError, match="Invalid source monitor ID"):
            simulator.transform_coords(100, 100, 99, 0)

    def test_invalid_target_monitor_raises_error(self) -> None:
        """Test that invalid target monitor ID raises error."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        with pytest.raises(ValueError, match="Invalid target monitor ID"):
            simulator.transform_coords(100, 100, 0, 99)

    def test_estimate_transform_time_same_dpi(self) -> None:
        """Test that same DPI transform is estimated at ~5ms."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        time_ms = simulator.estimate_transform_time(0, 1)

        assert time_ms == 5.0

    def test_estimate_transform_time_different_dpi(self) -> None:
        """Test that different DPI transform is estimated at ~10ms."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=2560, height=1440, dpi=144, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        time_ms = simulator.estimate_transform_time(0, 1)

        assert time_ms == 10.0

    def test_estimate_transform_time_invalid_source(self) -> None:
        """Test invalid source monitor in estimate_transform_time."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        with pytest.raises(ValueError, match="Invalid source monitor ID"):
            simulator.estimate_transform_time(99, 0)

    def test_estimate_transform_time_invalid_target(self) -> None:
        """Test invalid target monitor in estimate_transform_time."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        with pytest.raises(ValueError, match="Invalid target monitor ID"):
            simulator.estimate_transform_time(0, 99)

    def test_validate_click_target_valid(self) -> None:
        """Test validating a valid click target."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        assert simulator.validate_click_target(100, 100, 0) is True
        assert simulator.validate_click_target(1919, 1079, 0) is True
        assert simulator.validate_click_target(0, 0, 0) is True

    def test_validate_click_target_out_of_bounds_x(self) -> None:
        """Test validating click target out of bounds in X."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        assert simulator.validate_click_target(-1, 100, 0) is False
        assert simulator.validate_click_target(1920, 100, 0) is False
        assert simulator.validate_click_target(2000, 100, 0) is False

    def test_validate_click_target_out_of_bounds_y(self) -> None:
        """Test validating click target out of bounds in Y."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        assert simulator.validate_click_target(100, -1, 0) is False
        assert simulator.validate_click_target(100, 1080, 0) is False
        assert simulator.validate_click_target(100, 2000, 0) is False

    def test_validate_click_target_invalid_monitor(self) -> None:
        """Test validating click target on invalid monitor."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        assert simulator.validate_click_target(100, 100, 99) is False

    def test_get_monitor_bounds_valid(self) -> None:
        """Test getting bounds of a valid monitor."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=100, offset_y=50)
        simulator = MultiMonitorSimulator([config])

        bounds = simulator.get_monitor_bounds(0)

        assert bounds == (100, 50, 1920, 1080)

    def test_get_monitor_bounds_invalid(self) -> None:
        """Test getting bounds of an invalid monitor."""
        config = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        simulator = MultiMonitorSimulator([config])

        bounds = simulator.get_monitor_bounds(99)

        assert bounds is None

    def test_find_monitor_at_coords_found(self) -> None:
        """Test finding monitor at absolute coordinates."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Point at (100, 100) should be on monitor 0
        assert simulator.find_monitor_at_coords(100, 100) == 0

        # Point at (2000, 100) should be on monitor 1 (1920 + 80)
        assert simulator.find_monitor_at_coords(2000, 100) == 1

    def test_find_monitor_at_coords_not_found(self) -> None:
        """Test finding monitor when coordinates are not on any monitor."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Point between monitors (at edge)
        assert simulator.find_monitor_at_coords(1920, 100) == 1

        # Point way out of bounds
        assert simulator.find_monitor_at_coords(10000, 10000) is None

    def test_coordinate_transform_accuracy_scaling(self) -> None:
        """Test coordinate transform maintains position accuracy across DPI scales."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=2560, height=1440, dpi=144, offset_x=1920, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Test several key points to ensure scaling is consistent
        test_points = [(0, 0), (100, 100), (500, 500), (1000, 1000)]

        for px, py in test_points:
            result_x, result_y = simulator.transform_coords(px, py, 0, 1)

            # Verify scaling is applied (1.5x for 96→144 DPI)
            # Should be: (px * 1.5) - 1920, (py * 1.5)
            expected_x = int(px * 1.5) - 1920
            expected_y = int(py * 1.5)

            assert result_x == expected_x
            assert result_y == expected_y

    def test_triple_monitor_setup(self) -> None:
        """Test with three monitors (different configurations)."""
        configs = [
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
            MonitorConfig(id=2, width=2560, height=1440, dpi=144, offset_x=3840, offset_y=0),
        ]
        simulator = MultiMonitorSimulator(configs)

        # Validate all monitors are registered
        assert len(simulator.monitors) == 3

        # Transform from monitor 0 to monitor 2
        result_x, result_y = simulator.transform_coords(100, 100, 0, 2)

        # Same DPI doesn't exist, so no scaling from 0 to 2
        # But 0 is 96 DPI and 2 is 144 DPI, so 1.5x scaling applies
        # abs_x = 100 + 0 = 100, scaled = 150, final = 150 - 3840 = -3690
        assert result_x == -3690
        assert result_y == 150
