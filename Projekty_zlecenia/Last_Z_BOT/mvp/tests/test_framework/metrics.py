"""Metrics and data classes for test framework."""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional
import statistics
import time

from mvp.tests.test_framework.log_parser import Click, OCRDetection, MacroDecision

if TYPE_CHECKING:
    from mvp.tests.test_framework.scenarios import Scenario
    from mvp.tests.test_framework.cpu_profiler import CPUProfiler


class CPULoadClass(Enum):
    """CPU load classification."""

    IDLE = "idle"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HotSpot:
    """CPU hot spot information."""

    function_name: str
    cpu_time_ms: float
    percent: float


@dataclass
class Deviation:
    """Deviation from expected behavior."""

    type: str  # "click_deviation", "ocr_precision", "spam_cps", "cpu_high", "memory_high"
    severity: str  # "warning", "error"
    value: float
    threshold: float
    message: str


@dataclass
class BottleneckInfo:
    """Bottleneck information."""

    type: str  # "CPU", "MEMORY", "OCR_SLOW", "CLICK_DRIFT"
    severity: str  # "WARNING", "ERROR", "CRITICAL"
    value: float
    threshold: float
    function_name: Optional[str] = None
    message: str = ""


@dataclass
class MultiMonitorMetrics:
    """Multi-monitor specific metrics."""

    monitor_count: int
    dpi_values: list[int] = field(default_factory=list)
    coordinate_transform_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class ClickMetrics:
    """Detailed click accuracy metrics."""

    total_clicks: int = 0
    accurate_clicks: int = 0  # Clicks within 50px of ROI
    avg_deviation_px: float = 0.0  # Euclidean distance
    max_deviation_px: float = 0.0
    accuracy_ratio: float = 0.0  # accurate_clicks / total_clicks


@dataclass
class OcrMetrics:
    """Detailed OCR precision metrics."""

    total_detections: int = 0
    correct_detections: int = 0
    precision: float = 0.0  # correct / total (0.0-1.0)
    low_confidence_count: int = 0  # confidence < 0.70
    consecutive_low_confidence: int = 0  # Counter for consecutive failures
    failed: bool = False  # True if >3 consecutive low confidence


@dataclass
class RunMetrics:
    """Metrics for a single test run."""

    run_id: int
    scenario_id: str
    passed: bool
    click_count: int = 0
    click_avg_deviation_px: float = 0.0
    ocr_detections: int = 0
    ocr_precision: float = 0.0
    macro_step_latency_ms: dict[str, float] = field(default_factory=dict)
    spam_click_count: int = 0
    spam_click_duration_s: float = 0.0
    spam_cps: float = 0.0
    cpu_time_ms: float = 0.0
    gpu_time_ms: float = 0.0
    syscall_time_ms: float = 0.0
    memory_mb: float = 0.0
    cpu_load_class: CPULoadClass = CPULoadClass.IDLE
    hot_spots: list[HotSpot] = field(default_factory=list)
    deviations: list[Deviation] = field(default_factory=list)
    multi_monitor_metrics: Optional[MultiMonitorMetrics] = None
    timestamp_ms: float = 0.0
    duration_ms: float = 0.0
    # New metrics fields
    click_metrics: Optional[ClickMetrics] = None
    ocr_metrics: Optional[OcrMetrics] = None
    # Task 3.3.1-3.3.3 timing fields
    reaction_latency_ms: float = 0.0
    timer_accuracy_percent: float = 0.0
    arrow_latency_ms: float = 0.0
    heli_latency_ms: float = 0.0
    # Task 3.4.1-3.4.2 CPU profiling fields
    cpu_percent_avg: float = 0.0
    cpu_percent_peak: float = 0.0
    # Task 3.4.3 memory peak tracking field
    memory_peak_mb: float = 0.0
    # Task 3.5 error classification fields
    parse_errors: list[str] = field(default_factory=list)
    classification: str = "passed"  # passed, partial, failed_parse, failed_missing


@dataclass
class TestSuiteResult:
    """Overall test suite result."""

    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    runs: list[RunMetrics] = field(default_factory=list)
    pass_rate: float = 0.0
    cpu_load_distribution: dict[str, int] = field(default_factory=dict)
    bottleneck_summary: list[str] = field(default_factory=list)
    avg_memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    total_duration_s: float = 0.0
    timestamp_ms: float = 0.0


class MetricsCollector:
    """Collect metrics during test execution."""

    def __init__(self, scenario: "Scenario", cpu_profiler: "CPUProfiler") -> None:
        """Initialize metrics collector.
        
        Args:
            scenario: Test scenario configuration
            cpu_profiler: CPUProfiler instance for profiling
        """
        self.scenario = scenario
        self.cpu_profiler = cpu_profiler
        
        # Click tracking
        self._clicks: list[tuple[int, int, int, int]] = []  # (target_px, target_py, actual_px, actual_py)
        
        # OCR tracking
        self._ocr_samples: list[tuple[str, str, float]] = []  # (detected, expected, latency_ms)
        
        # Macro step timing
        self._macro_steps: dict[str, list[float]] = {}  # step_name -> [latencies_ms]
        
        # Spam clicks
        self._spam_click_count: int = 0
        self._spam_click_duration_s: float = 0.0
        
        # Task-specific latency metrics
        self._reaction_latency_ms: float = 0.0
        self._timer_accuracy_percent: float = 0.0
        self._arrow_latency_ms: float = 0.0
        self._heli_latency_ms: float = 0.0
        
        # Timing
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        
        # Run result
        self._passed: bool = False

    def start_run(self) -> None:
        """Mark start of metrics collection."""
        self._start_time = time.perf_counter()
        self.cpu_profiler.start_profile()

    def end_run(self, passed: bool) -> None:
        """Mark end of metrics collection.
        
        Args:
            passed: Whether the run passed
        """
        self._end_time = time.perf_counter()
        self._passed = passed

    def record_click(
        self, target_px: int, target_py: int, actual_px: int, actual_py: int
    ) -> None:
        """Record a click with target and actual coordinates.
        
        Args:
            target_px: Target X coordinate
            target_py: Target Y coordinate
            actual_px: Actual X coordinate achieved
            actual_py: Actual Y coordinate achieved
        """
        self._clicks.append((target_px, target_py, actual_px, actual_py))

    def record_ocr(
        self, detected: str, expected: str, latency_ms: float
    ) -> None:
        """Record OCR detection result.
        
        Args:
            detected: Detected text from OCR
            expected: Expected text
            latency_ms: OCR latency in milliseconds
        """
        self._ocr_samples.append((detected, expected, latency_ms))

    def record_macro_step(self, step_name: str, latency_ms: float) -> None:
        """Record macro step timing.
        
        Args:
            step_name: Name of the macro step
            latency_ms: Step latency in milliseconds
        """
        if step_name not in self._macro_steps:
            self._macro_steps[step_name] = []
        self._macro_steps[step_name].append(latency_ms)

    def record_spam_clicks(self, count: int, duration_s: float) -> None:
        """Record spam click metrics.
        
        Args:
            count: Number of clicks in spam burst
            duration_s: Duration of spam burst in seconds
        """
        self._spam_click_count = count
        self._spam_click_duration_s = duration_s

    def record_reaction_latency(self, latency_ms: float) -> None:
        """Record reaction latency (time from event to first click).
        
        Args:
            latency_ms: Reaction latency in milliseconds
        """
        self._reaction_latency_ms = latency_ms

    def record_timer_accuracy(self, accuracy_percent: float) -> None:
        """Record timer accuracy (how close timer countdowns match expected).
        
        Args:
            accuracy_percent: Accuracy as percentage 0-100
        """
        self._timer_accuracy_percent = accuracy_percent

    def record_arrow_latency(self, latency_ms: float) -> None:
        """Record arrow appearance latency (time from spawn to detection).
        
        Args:
            latency_ms: Arrow latency in milliseconds
        """
        self._arrow_latency_ms = latency_ms

    def record_heli_latency(self, latency_ms: float) -> None:
        """Record heli/treasure latency (time from spawn to clicks).
        
        Args:
            latency_ms: Heli latency in milliseconds
        """
        self._heli_latency_ms = latency_ms

    def finalize(self) -> RunMetrics:
        """Finalize and return RunMetrics for the run.
        
        Returns:
            RunMetrics with all collected data and deviations detected
        """
        if self._start_time is None or self._end_time is None:
            raise ValueError("Metrics collection not started or ended properly")

        duration_ms = (self._end_time - self._start_time) * 1000
        
        # Stop profiling and get CPU metrics
        cpu_profile = self.cpu_profiler.stop_profile()
        
        # Calculate click metrics
        click_count = len(self._clicks)
        click_avg_deviation_px = self._calculate_click_deviation()
        
        # Calculate OCR metrics
        ocr_detections = len(self._ocr_samples)
        ocr_precision = self._calculate_ocr_precision()
        
        # Calculate macro step metrics
        macro_step_latency_ms = self._aggregate_macro_steps()
        
        # Calculate spam metrics
        spam_cps = (
            self._spam_click_count / self._spam_click_duration_s
            if self._spam_click_duration_s > 0
            else 0.0
        )
        
        # Classify CPU load
        cpu_percent = (cpu_profile.cpu_time_ms / duration_ms * 100) if duration_ms > 0 else 0
        cpu_load_class = self._classify_cpu_load(cpu_percent)
        
        # Detect deviations
        deviations = self._detect_deviations(
            click_avg_deviation_px,
            ocr_precision,
            spam_cps,
            cpu_percent,
            cpu_profile.memory_mb,
        )
        
        # Get memory peak tracking
        memory_peak_mb = self.cpu_profiler.get_memory_peak_mb()
        
        # Get CPU peak percent
        cpu_percent_peak = (cpu_profile.cpu_time_ms / duration_ms * 100) if duration_ms > 0 else 0
        
        # Build RunMetrics
        run_metrics = RunMetrics(
            run_id=0,  # Will be assigned by orchestrator
            scenario_id=self.scenario.id,
            passed=self._passed,
            click_count=click_count,
            click_avg_deviation_px=click_avg_deviation_px,
            ocr_detections=ocr_detections,
            ocr_precision=ocr_precision,
            macro_step_latency_ms=macro_step_latency_ms,
            spam_click_count=self._spam_click_count,
            spam_click_duration_s=self._spam_click_duration_s,
            spam_cps=spam_cps,
            cpu_time_ms=cpu_profile.cpu_time_ms,
            gpu_time_ms=cpu_profile.gpu_time_ms,
            syscall_time_ms=cpu_profile.syscall_time_ms,
            memory_mb=cpu_profile.memory_mb,
            cpu_load_class=cpu_load_class,
            hot_spots=cpu_profile.hot_spots,
            deviations=deviations,
            duration_ms=duration_ms,
            memory_peak_mb=memory_peak_mb,
            reaction_latency_ms=self._reaction_latency_ms,
            timer_accuracy_percent=self._timer_accuracy_percent,
            arrow_latency_ms=self._arrow_latency_ms,
            heli_latency_ms=self._heli_latency_ms,
            cpu_percent_peak=cpu_percent_peak,
        )
        
        return run_metrics

    def _calculate_click_deviation(self) -> float:
        """Calculate average click deviation from target.
        
        Returns:
            Average deviation in pixels
        """
        if not self._clicks:
            return 0.0
        
        deviations = [
            ((actual_px - target_px) ** 2 + (actual_py - target_py) ** 2) ** 0.5
            for target_px, target_py, actual_px, actual_py in self._clicks
        ]
        
        return statistics.mean(deviations) if deviations else 0.0

    def _calculate_ocr_precision(self) -> float:
        """Calculate OCR precision (accuracy of detected vs expected text).
        
        Returns:
            Precision as fraction 0.0-1.0
        """
        if not self._ocr_samples:
            return 1.0  # No OCR samples = perfect (no errors)
        
        correct_count = sum(
            1 for detected, expected, _ in self._ocr_samples if detected == expected
        )
        
        # For clipped windows, adjust expected precision
        if self.scenario.is_clipped:
            # Baseline precision reduced by clipping factor
            baseline_precision = correct_count / len(self._ocr_samples)
            detectable_ratio = min(
                1.0,
                (self.scenario.window_width / 1024.0) * (self.scenario.window_height / 768.0),
            )
            return baseline_precision * detectable_ratio
        
        return correct_count / len(self._ocr_samples)

    def _aggregate_macro_steps(self) -> dict[str, float]:
        """Aggregate macro step latencies by computing median per step.
        
        Returns:
            Dictionary mapping step_name to median latency_ms
        """
        result = {}
        for step_name, latencies in self._macro_steps.items():
            if latencies:
                result[step_name] = statistics.median(latencies)
        return result

    def _classify_cpu_load(self, cpu_percent: float) -> CPULoadClass:
        """Classify CPU load based on percentage.
        
        Args:
            cpu_percent: CPU usage percentage (0-100)
            
        Returns:
            CPULoadClass
        """
        if cpu_percent < 20.0:
            return CPULoadClass.IDLE
        elif cpu_percent < 40.0:
            return CPULoadClass.LOW
        elif cpu_percent < 60.0:
            return CPULoadClass.MEDIUM
        elif cpu_percent < 80.0:
            return CPULoadClass.HIGH
        else:
            return CPULoadClass.CRITICAL

    def _detect_deviations(
        self,
        click_deviation_px: float,
        ocr_precision: float,
        spam_cps: float,
        cpu_percent: float,
        memory_mb: float,
    ) -> list[Deviation]:
        """Detect deviations from expected metrics with adaptive thresholds for clipping.
        
        Args:
            click_deviation_px: Average click deviation in pixels
            ocr_precision: OCR precision 0.0-1.0
            spam_cps: Spam clicks per second
            cpu_percent: CPU usage percentage
            memory_mb: Memory usage in MB
            
        Returns:
            List of detected Deviation objects
        """
        deviations: list[Deviation] = []
        
        # Calculate detectable elements ratio if clipped
        detectable_ratio = self._calculate_detectable_ratio()
        
        # Click deviation threshold
        # For DPI mismatch, allow higher deviation (15px)
        # For normal DPI, allow up to 100px
        click_threshold = 15.0 if self.scenario.dpi != 96 else 100.0
        if click_deviation_px > click_threshold:
            deviations.append(
                Deviation(
                    type="click_deviation",
                    severity="warning",
                    value=click_deviation_px,
                    threshold=click_threshold,
                    message=f"Click deviation {click_deviation_px:.1f}px exceeds threshold {click_threshold}px",
                )
            )
        
        # OCR precision threshold (adjusted for clipping)
        expected_ocr_precision = self._get_expected_ocr_precision(0.80, detectable_ratio)
        
        if ocr_precision < expected_ocr_precision:
            deviations.append(
                Deviation(
                    type="ocr_precision",
                    severity="warning",
                    value=ocr_precision,
                    threshold=expected_ocr_precision,
                    message=f"OCR precision {ocr_precision:.2%} below threshold {expected_ocr_precision:.2%}",
                )
            )
        
        # Spam CPS threshold (adjusted for clipping)
        spam_threshold = self._get_expected_spam_cps(detectable_ratio)
        if spam_cps < spam_threshold and self._spam_click_count > 0:
            deviations.append(
                Deviation(
                    type="spam_cps",
                    severity="error",
                    value=spam_cps,
                    threshold=spam_threshold,
                    message=f"Spam CPS {spam_cps:.1f} below minimum {spam_threshold:.1f}",
                )
            )
        
        # CPU threshold (always 70%, independent of clipping)
        if cpu_percent > 70.0:
            deviations.append(
                Deviation(
                    type="cpu_high",
                    severity="error",
                    value=cpu_percent,
                    threshold=70.0,
                    message=f"CPU usage {cpu_percent:.1f}% exceeds threshold 70%",
                )
            )
        
        # Memory threshold (always 300MB, independent of clipping)
        if memory_mb > 300.0:
            deviations.append(
                Deviation(
                    type="memory_high",
                    severity="error",
                    value=memory_mb,
                    threshold=300.0,
                    message=f"Memory usage {memory_mb:.1f}MB exceeds threshold 300MB",
                )
            )
        
        return deviations
    
    def _calculate_detectable_ratio(self) -> float:
        """Calculate ratio of detectable elements for clipped windows.
        
        For full-size windows: returns 1.0 (everything visible)
        For clipped windows: returns (width/1024) * (height/768)
        
        Returns:
            Detectable ratio 0.0-1.0
        """
        if not self.scenario.is_clipped:
            return 1.0
        
        # Calculate visible surface area as fraction of full 1024x768
        clipped_width = min(self.scenario.window_width, 1024)
        clipped_height = min(self.scenario.window_height, 768)
        ratio = (clipped_width / 1024.0) * (clipped_height / 768.0)
        
        return min(ratio, 1.0)
    
    def _get_expected_ocr_precision(self, baseline: float, detectable_ratio: float) -> float:
        """Get expected OCR precision adapted for clipping.
        
        Args:
            baseline: Baseline OCR precision (e.g., 0.80 for 80%)
            detectable_ratio: Ratio of detectable elements (1.0 = full window)
            
        Returns:
            Expected OCR precision, minimum 60%
        """
        minimum = 0.60
        expected = baseline * detectable_ratio
        return max(expected, minimum)
    
    def _get_expected_spam_cps(self, detectable_ratio: float) -> float:
        """Get expected spam CPS adapted for clipping.
        
        Args:
            detectable_ratio: Ratio of detectable elements (1.0 = full window)
            
        Returns:
            Expected spam CPS, minimum 20
        """
        baseline_cps = 30.0
        expected_cps = baseline_cps * detectable_ratio
        return max(expected_cps, 20.0)

    @staticmethod
    def calculate_click_accuracy(
        clicks: list[Click], roi_center_x: int, roi_center_y: int, roi_radius_px: int = 50
    ) -> ClickMetrics:
        """Calculate click accuracy metrics based on clicks and ROI.

        **Validates: Requirements 1.3.1, 1.5.3**

        Args:
            clicks: List of Click objects from game_events.log
            roi_center_x: Expected ROI center X coordinate
            roi_center_y: Expected ROI center Y coordinate
            roi_radius_px: ROI radius in pixels (default 50)

        Returns:
            ClickMetrics with deviation calculations and accuracy ratio
        """
        metrics = ClickMetrics(total_clicks=len(clicks))

        if not clicks:
            return metrics

        deviations_px = []

        for click in clicks:
            # Calculate Euclidean distance from ROI center
            deviation = ((click.x - roi_center_x) ** 2 + (click.y - roi_center_y) ** 2) ** 0.5

            deviations_px.append(deviation)

            # Count accurate clicks (deviation <= 50px)
            if deviation <= roi_radius_px:
                metrics.accurate_clicks += 1

        # Calculate aggregate metrics
        if deviations_px:
            metrics.avg_deviation_px = statistics.mean(deviations_px)
            metrics.max_deviation_px = max(deviations_px)

        metrics.accuracy_ratio = (
            metrics.accurate_clicks / metrics.total_clicks if metrics.total_clicks > 0 else 0.0
        )

        return metrics

    @staticmethod
    def get_accurate_clicks_count(
        clicks: list[Click], roi_center_x: int, roi_center_y: int, roi_radius_px: int = 50
    ) -> tuple[int, float]:
        """Count clicks within ROI and calculate accuracy ratio.

        **Validates: Requirements 1.3.1**

        Args:
            clicks: List of Click objects
            roi_center_x: Expected ROI center X coordinate
            roi_center_y: Expected ROI center Y coordinate
            roi_radius_px: ROI radius in pixels (default 50)

        Returns:
            Tuple of (accurate_click_count, accuracy_ratio)
        """
        if not clicks:
            return 0, 0.0

        accurate_count = 0

        for click in clicks:
            deviation = ((click.x - roi_center_x) ** 2 + (click.y - roi_center_y) ** 2) ** 0.5
            if deviation <= roi_radius_px:
                accurate_count += 1

        accuracy_ratio = accurate_count / len(clicks)

        return accurate_count, accuracy_ratio

    @staticmethod
    def calculate_max_deviation(
        clicks: list[Click], roi_center_x: int, roi_center_y: int
    ) -> tuple[float, Optional[Click]]:
        """Find click with maximum deviation and return max deviation value.

        **Validates: Requirements 1.3.1**

        Args:
            clicks: List of Click objects
            roi_center_x: Expected ROI center X coordinate
            roi_center_y: Expected ROI center Y coordinate

        Returns:
            Tuple of (max_deviation_px, click_with_max_deviation)
        """
        if not clicks:
            return 0.0, None

        max_deviation = 0.0
        max_click = None

        for click in clicks:
            deviation = ((click.x - roi_center_x) ** 2 + (click.y - roi_center_y) ** 2) ** 0.5
            if deviation > max_deviation:
                max_deviation = deviation
                max_click = click

        return max_deviation, max_click

    @staticmethod
    def calculate_ocr_precision(
        detections: list[OCRDetection], expected_elements: list[str]
    ) -> OcrMetrics:
        """Calculate OCR precision and confidence tracking.

        **Validates: Requirements 1.3.2, 1.5.2**

        Args:
            detections: List of OCRDetection objects from event_log
            expected_elements: List of expected element names to detect

        Returns:
            OcrMetrics with precision and confidence information
        """
        metrics = OcrMetrics(total_detections=len(detections))

        if not detections:
            return metrics

        consecutive_low_confidence = 0

        for detection in detections:
            # Check if detection matches expected
            if detection.element_name in expected_elements:
                metrics.correct_detections += 1

            # Track low confidence
            if detection.confidence < 0.70:
                metrics.low_confidence_count += 1
                consecutive_low_confidence += 1

                # Check if threshold exceeded
                if consecutive_low_confidence > 3:
                    metrics.failed = True
            else:
                consecutive_low_confidence = 0

        # Store max consecutive low confidence for analysis
        metrics.consecutive_low_confidence = consecutive_low_confidence

        # Calculate precision
        metrics.precision = (
            metrics.correct_detections / metrics.total_detections
            if metrics.total_detections > 0
            else 0.0
        )

        # Clamp to 0.0-1.0 range
        metrics.precision = max(0.0, min(1.0, metrics.precision))

        return metrics

    @staticmethod
    def calculate_reaction_latency(
        ocr_detections: list[OCRDetection], macro_decisions: list[MacroDecision]
    ) -> float:
        """Calculate latency: bot_detection_time - event_appearance_time.

        **Validates: Requirements 3.3.1**

        Measures time between OCR detection event (when element appears on screen)
        and macro decision (when bot decides to act), in milliseconds.

        Args:
            ocr_detections: List of OCRDetection objects with timestamps
            macro_decisions: List of MacroDecision objects with timestamps

        Returns:
            Reaction latency in milliseconds (float). Returns 0.0 if no data.
        """
        if not ocr_detections or not macro_decisions:
            return 0.0

        # Find matching OCR detection and macro decision pairs
        # Typically, we match the last OCR detection before each macro decision
        latencies: list[float] = []

        for decision in macro_decisions:
            # Find the most recent OCR detection before this decision
            matching_detections = [
                det for det in ocr_detections
                if det.timestamp <= decision.timestamp and det.element_name == decision.target_element
            ]

            if matching_detections:
                # Use the most recent detection
                last_detection = max(matching_detections, key=lambda d: d.timestamp)
                # Calculate latency in milliseconds
                latency = (decision.timestamp - last_detection.timestamp).total_seconds() * 1000
                if latency >= 0:  # Only include positive latencies
                    latencies.append(latency)

        # Return average latency or 0 if no matches
        if latencies:
            return statistics.mean(latencies)
        return 0.0

    @staticmethod
    def calculate_timer_accuracy(
        bot_timer_readings: list[float], actual_timer_seconds: float, tolerance_s: float = 5.0
    ) -> float:
        """Calculate timer accuracy percentage.

        **Validates: Requirements 3.3.2**

        Accuracy = (1 - |bot_timer - actual_timer| / actual_timer) × 100%
        with ±5s tolerance (fails if |error| > 5s)

        Args:
            bot_timer_readings: List of timer readings from bot (seconds)
            actual_timer_seconds: Actual timer value from C# window (seconds)
            tolerance_s: Maximum allowed error in seconds (default 5.0)

        Returns:
            Timer accuracy percentage (0.0-100.0), clamped to valid range
        """
        if not bot_timer_readings or actual_timer_seconds <= 0:
            return 0.0

        # Calculate average bot reading
        avg_bot_reading = statistics.mean(bot_timer_readings)

        # Calculate absolute error
        error_s = abs(avg_bot_reading - actual_timer_seconds)

        # Check tolerance
        if error_s > tolerance_s:
            return 0.0  # Failed tolerance check

        # Calculate accuracy percentage
        # When error is 0, accuracy = 100%
        # As error approaches tolerance, accuracy approaches 0%
        if actual_timer_seconds > 0:
            accuracy = (1.0 - (error_s / actual_timer_seconds)) * 100.0
        else:
            accuracy = 0.0

        # Clamp to 0-100 range
        return max(0.0, min(100.0, accuracy))

    @staticmethod
    def track_ocr_low_confidence(
        detections: list[OCRDetection], confidence_threshold: float = 0.70, max_consecutive: int = 3
    ) -> OcrMetrics:
        """Track OCR detections with low confidence and consecutive failures.

        **Validates: Requirements 1.5.2**

        Args:
            detections: List of OCRDetection objects
            confidence_threshold: Confidence threshold (default 0.70)
            max_consecutive: Maximum consecutive low confidence before failing (default 3)

        Returns:
            OcrMetrics with confidence tracking information
        """
        metrics = OcrMetrics(total_detections=len(detections))

        if not detections:
            return metrics

        consecutive_low_confidence = 0

        for detection in detections:
            if detection.confidence < confidence_threshold:
                metrics.low_confidence_count += 1
                consecutive_low_confidence += 1

                # Trigger failure if threshold exceeded
                if consecutive_low_confidence > max_consecutive:
                    metrics.failed = True
            else:
                # Reset counter on normal confidence
                consecutive_low_confidence = 0

        metrics.consecutive_low_confidence = consecutive_low_confidence

        # Calculate precision (assuming all detections that pass confidence are correct)
        correct_count = len(detections) - metrics.low_confidence_count
        metrics.correct_detections = correct_count
        metrics.precision = (
            correct_count / len(detections) if len(detections) > 0 else 0.0
        )

        return metrics

    @staticmethod
    def detect_arrow_and_heli_latencies(
        ocr_detections: list[OCRDetection], macro_decisions: list[MacroDecision]
    ) -> tuple[float, float]:
        """Measure time_to_detect for arrow and heli elements separately.

        **Validates: Requirements 3.3.3**

        Tracks separate latencies for arrow and heli element detection.
        Measures from OCR detection event to macro click decision.

        Args:
            ocr_detections: List of OCRDetection objects
            macro_decisions: List of MacroDecision objects

        Returns:
            Tuple of (arrow_latency_ms, heli_latency_ms). Returns 0.0 for missing elements.
        """
        arrow_latencies: list[float] = []
        heli_latencies: list[float] = []

        # For each macro decision, find matching OCR detection
        for decision in macro_decisions:
            matching_detections = [
                det for det in ocr_detections
                if det.timestamp <= decision.timestamp
                and det.element_name == decision.target_element
            ]

            if matching_detections:
                last_detection = max(matching_detections, key=lambda d: d.timestamp)
                latency = (decision.timestamp - last_detection.timestamp).total_seconds() * 1000

                if latency >= 0:
                    if decision.target_element == "arrow":
                        arrow_latencies.append(latency)
                    elif decision.target_element == "heli":
                        heli_latencies.append(latency)

        # Return average latencies or 0.0 if no samples
        arrow_avg = statistics.mean(arrow_latencies) if arrow_latencies else 0.0
        heli_avg = statistics.mean(heli_latencies) if heli_latencies else 0.0

        return arrow_avg, heli_avg
