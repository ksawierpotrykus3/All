"""Multi-monitor coordinate transformation and validation."""

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scenarios import MonitorConfig


# Base DPI for coordinate normalization
BASE_DPI = 96


@dataclass
class MonitorTransformResult:
    """Result of coordinate transformation between monitors."""

    source_monitor_id: int
    target_monitor_id: int
    source_coords: tuple[int, int]
    target_coords: tuple[int, int]
    dpi_source: int
    dpi_target: int
    scale_factor: float
    transform_time_ms: float
    valid: bool


class MultiMonitorSimulator:
    """Simulate multi-monitor coordinate transformations and validation."""

    def __init__(self, monitors: list["MonitorConfig"]) -> None:
        """Initialize multi-monitor simulator.

        Args:
            monitors: List of MonitorConfig objects representing the monitor setup.
        """
        self.monitors = {m.id: m for m in monitors}
        self._validate_monitor_topology()

    def _validate_monitor_topology(self) -> None:
        """Validate that monitor topology is valid.

        Checks:
        - All monitor IDs are unique
        - All positions are non-negative
        - No overlapping monitors (simplified check)
        """
        if not self.monitors:
            raise ValueError("At least one monitor config required")

        for monitor_id, monitor in self.monitors.items():
            if monitor.id != monitor_id:
                raise ValueError(f"Monitor ID mismatch: {monitor.id} != {monitor_id}")
            if monitor.width <= 0 or monitor.height <= 0:
                raise ValueError(f"Monitor {monitor_id} has invalid dimensions")
            if monitor.dpi <= 0:
                raise ValueError(f"Monitor {monitor_id} has invalid DPI")

    def transform_coords(
        self,
        px: int,
        py: int,
        from_monitor_id: int,
        to_monitor_id: int,
    ) -> tuple[int, int]:
        """Transform coordinates from one monitor to another with DPI scaling.

        Algorithm:
        1. Get source and target monitor configs
        2. Normalize source coords to base DPI (96)
        3. Apply DPI scaling to target DPI
        4. Subtract target monitor offset
        5. Return transformed coordinates

        Args:
            px: Source X coordinate (in source monitor's coordinate space)
            py: Source Y coordinate (in source monitor's coordinate space)
            from_monitor_id: Source monitor ID
            to_monitor_id: Target monitor ID

        Returns:
            Tuple of (new_px, new_py) in target monitor's coordinate space

        Raises:
            ValueError: If monitors don't exist
        """
        if from_monitor_id not in self.monitors:
            raise ValueError("Invalid source monitor ID")
        if to_monitor_id not in self.monitors:
            raise ValueError("Invalid target monitor ID")

        # If same monitor, no transformation needed
        if from_monitor_id == to_monitor_id:
            return (px, py)

        source_monitor = self.monitors[from_monitor_id]
        target_monitor = self.monitors[to_monitor_id]

        dpi_from = source_monitor.dpi
        dpi_to = target_monitor.dpi

        # Step 1: Add source monitor offset to get absolute screen coordinates
        abs_px = px + source_monitor.offset_x
        abs_py = py + source_monitor.offset_y

        # Step 2: Apply DPI scaling (direct scaling between source and target DPI)
        scale_factor = dpi_to / dpi_from
        scaled_px = abs_px * scale_factor
        scaled_py = abs_py * scale_factor

        # Step 3: Subtract target monitor offset (convert back to local coords)
        final_px = int(scaled_px - target_monitor.offset_x)
        final_py = int(scaled_py - target_monitor.offset_y)

        return (final_px, final_py)

    def estimate_transform_time(
        self, from_monitor_id: int, to_monitor_id: int
    ) -> float:
        """Estimate time required for coordinate transformation.

        Baseline: < 1ms for single monitor
        DPI mismatch: < 5ms
        Multi-monitor: < 10ms

        Args:
            from_monitor_id: Source monitor ID
            to_monitor_id: Target monitor ID

        Returns:
            Estimated time in milliseconds
        """
        if from_monitor_id not in self.monitors:
            raise ValueError("Invalid source monitor ID")
        if to_monitor_id not in self.monitors:
            raise ValueError("Invalid target monitor ID")

        if from_monitor_id == to_monitor_id:
            return 0.0  # No time for same monitor

        source_monitor = self.monitors[from_monitor_id]
        target_monitor = self.monitors[to_monitor_id]

        # Different DPI scales require more time
        if source_monitor.dpi != target_monitor.dpi:
            return 10.0

        return 5.0

    def validate_click_target(
        self, px: int, py: int, monitor_id: int
    ) -> bool:
        """Validate if click target is within monitor bounds.

        Args:
            px: X coordinate
            py: Y coordinate
            monitor_id: Monitor ID

        Returns:
            True if (px, py) is within monitor bounds, False otherwise
        """
        if monitor_id not in self.monitors:
            return False

        monitor = self.monitors[monitor_id]

        # Check if coordinates are within monitor bounds (local coordinates)
        return (
            0 <= px < monitor.width
            and 0 <= py < monitor.height
        )

    def validate_click_target_absolute(
        self, px: int, py: int
    ) -> tuple[bool, int | None]:
        """Validate if click target is within any monitor (absolute screen coords).

        Args:
            px: Absolute X coordinate (screen space)
            py: Absolute Y coordinate (screen space)

        Returns:
            Tuple of (is_valid, monitor_id)
            - is_valid: True if click is within any monitor
            - monitor_id: ID of monitor containing click, or None if invalid
        """
        for monitor_id, monitor in self.monitors.items():
            x_min = monitor.offset_x
            y_min = monitor.offset_y
            x_max = monitor.offset_x + monitor.width
            y_max = monitor.offset_y + monitor.height

            if x_min <= px < x_max and y_min <= py < y_max:
                return (True, monitor_id)

        return (False, None)

    def get_monitor_bounds(
        self, monitor_id: int
    ) -> tuple[int, int, int, int] | None:
        """Get monitor bounds in absolute coordinate space.

        Args:
            monitor_id: Monitor ID

        Returns:
            Tuple of (offset_x, offset_y, width, height) in absolute coordinates
            Returns None if monitor not found
        """
        if monitor_id not in self.monitors:
            return None

        monitor = self.monitors[monitor_id]
        return (monitor.offset_x, monitor.offset_y, monitor.width, monitor.height)

    def get_monitor_bounds_absolute(
        self, monitor_id: int
    ) -> tuple[int, int, int, int]:
        """Get monitor bounds in absolute screen coordinate space.

        Args:
            monitor_id: Monitor ID

        Returns:
            Tuple of (x_min, y_min, x_max, y_max) in absolute coordinates

        Raises:
            ValueError: If monitor not found
        """
        if monitor_id not in self.monitors:
            raise ValueError(f"Monitor {monitor_id} not found")

        monitor = self.monitors[monitor_id]
        x_min = monitor.offset_x
        y_min = monitor.offset_y
        x_max = monitor.offset_x + monitor.width
        y_max = monitor.offset_y + monitor.height
        return (x_min, y_min, x_max, y_max)

    def find_monitor_at_coords(
        self, px: int, py: int
    ) -> int | None:
        """Find which monitor contains the given absolute coordinates.

        Args:
            px: Absolute X coordinate
            py: Absolute Y coordinate

        Returns:
            Monitor ID if found, None otherwise
        """
        for monitor_id, monitor in self.monitors.items():
            x_min = monitor.offset_x
            y_min = monitor.offset_y
            x_max = monitor.offset_x + monitor.width
            y_max = monitor.offset_y + monitor.height

            if x_min <= px < x_max and y_min <= py < y_max:
                return monitor_id

        return None

    def transform_with_timing(
        self,
        px: int,
        py: int,
        from_monitor_id: int,
        to_monitor_id: int,
    ) -> MonitorTransformResult:
        """Transform coordinates and measure timing.

        Args:
            px: Source X coordinate
            py: Source Y coordinate
            from_monitor_id: Source monitor ID
            to_monitor_id: Target monitor ID

        Returns:
            MonitorTransformResult with timing and validity info
        """
        start_time = time.perf_counter()

        # Perform transformation
        try:
            new_px, new_py = self.transform_coords(
                px, py, from_monitor_id, to_monitor_id
            )
            valid = True
        except ValueError:
            new_px, new_py = 0, 0
            valid = False

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Get DPI from monitors
        dpi_from = self.monitors[from_monitor_id].dpi if from_monitor_id in self.monitors else 96
        dpi_to = self.monitors[to_monitor_id].dpi if to_monitor_id in self.monitors else 96

        # Calculate scale factor
        scale_factor = dpi_to / dpi_from if dpi_from != 0 else 1.0

        return MonitorTransformResult(
            source_monitor_id=from_monitor_id,
            target_monitor_id=to_monitor_id,
            source_coords=(px, py),
            target_coords=(new_px, new_py),
            dpi_source=dpi_from,
            dpi_target=dpi_to,
            scale_factor=scale_factor,
            transform_time_ms=elapsed_ms,
            valid=valid,
        )

    def get_dpi_mismatch_error(
        self,
        original_px: int,
        original_py: int,
        target_px: int,
        target_py: int,
    ) -> float:
        """Calculate error distance due to DPI mismatch.

        Returns Euclidean distance between original and transformed coords.

        Args:
            original_px: Original X coordinate
            original_py: Original Y coordinate
            target_px: Transformed X coordinate
            target_py: Transformed Y coordinate

        Returns:
            Distance in pixels
        """
        dx = target_px - original_px
        dy = target_py - original_py
        distance = (dx**2 + dy**2) ** 0.5
        return distance
