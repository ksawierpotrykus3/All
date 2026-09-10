"""Comprehensive tests for click accuracy and OCR precision metrics.

**Validates: Requirements 1.3.1, 1.3.2, 1.5.2, 1.5.3**
"""

from datetime import datetime

import pytest

from mvp.tests.test_framework.log_parser import Click, OCRDetection
from mvp.tests.test_framework.metrics import (
    ClickMetrics,
    MetricsCollector,
    OcrMetrics,
)


class TestClickAccuracyCalculation:
    """Tests for calculate_click_accuracy() method."""

    def test_calculate_click_accuracy_perfect_accuracy(self) -> None:
        """Test click accuracy with all clicks at ROI center."""
        clicks = [
            Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1050, x=512, y=768, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1100, x=512, y=768, element_name="arrow", event_type="click"),
        ]

        metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert metrics.total_clicks == 3
        assert metrics.accurate_clicks == 3
        assert metrics.avg_deviation_px == 0.0
        assert metrics.max_deviation_px == 0.0
        assert metrics.accuracy_ratio == 1.0

    def test_calculate_click_accuracy_partial_accuracy(self) -> None:
        """Test click accuracy with some clicks outside ROI."""
        clicks = [
            Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click"),  # Center
            Click(timestamp_ms=1050, x=520, y=770, element_name="arrow", event_type="click"),  # ~11px away
            Click(timestamp_ms=1100, x=562, y=768, element_name="arrow", event_type="click"),  # 50px away (on boundary)
            Click(timestamp_ms=1150, x=600, y=768, element_name="arrow", event_type="click"),  # 88px away
        ]

        metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert metrics.total_clicks == 4
        assert metrics.accurate_clicks == 3  # First 3 within 50px
        assert metrics.max_deviation_px == pytest.approx(88.0, abs=1.0)
        assert metrics.accuracy_ratio == pytest.approx(0.75, abs=0.01)

    def test_calculate_click_accuracy_all_outside_roi(self) -> None:
        """Test click accuracy with all clicks outside ROI."""
        clicks = [
            Click(timestamp_ms=1000, x=200, y=200, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1050, x=800, y=800, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1100, x=100, y=900, element_name="arrow", event_type="click"),
        ]

        metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert metrics.total_clicks == 3
        assert metrics.accurate_clicks == 0
        assert metrics.avg_deviation_px > 50
        assert metrics.accuracy_ratio == 0.0

    def test_calculate_click_accuracy_empty_clicks(self) -> None:
        """Test click accuracy with empty click list."""
        clicks: list[Click] = []

        metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert metrics.total_clicks == 0
        assert metrics.accurate_clicks == 0
        assert metrics.avg_deviation_px == 0.0
        assert metrics.max_deviation_px == 0.0
        assert metrics.accuracy_ratio == 0.0

    def test_calculate_click_accuracy_custom_roi_radius(self) -> None:
        """Test click accuracy with custom ROI radius."""
        clicks = [
            Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1050, x=525, y=768, element_name="arrow", event_type="click"),  # 13px away
            Click(timestamp_ms=1100, x=540, y=768, element_name="arrow", event_type="click"),  # 28px away
        ]

        # With radius 25px
        metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=25
        )

        assert metrics.total_clicks == 3
        assert metrics.accurate_clicks == 2  # First two within 25px
        assert metrics.accuracy_ratio == pytest.approx(0.667, abs=0.01)

    def test_calculate_click_accuracy_euclidean_distance(self) -> None:
        """Test click accuracy uses Euclidean distance correctly."""
        # Point at (512+30, 768+40) is sqrt(30^2 + 40^2) = 50px away
        clicks = [
            Click(timestamp_ms=1000, x=542, y=808, element_name="arrow", event_type="click"),
        ]

        metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert metrics.total_clicks == 1
        assert metrics.accurate_clicks == 1  # Exactly at boundary
        assert metrics.avg_deviation_px == pytest.approx(50.0, abs=0.1)


class TestGetAccurateClicksCount:
    """Tests for get_accurate_clicks_count() method."""

    def test_get_accurate_clicks_count_all_accurate(self) -> None:
        """Test accurate click count when all clicks are within ROI."""
        clicks = [
            Click(timestamp_ms=1000, x=510, y=770, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1050, x=514, y=766, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1100, x=512, y=768, element_name="arrow", event_type="click"),
        ]

        count, ratio = MetricsCollector.get_accurate_clicks_count(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert count == 3
        assert ratio == pytest.approx(1.0, abs=0.01)

    def test_get_accurate_clicks_count_mixed(self) -> None:
        """Test accurate click count with mixed accuracy."""
        clicks = [
            Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click"),  # Accurate
            Click(timestamp_ms=1050, x=600, y=800, element_name="arrow", event_type="click"),  # Inaccurate
            Click(timestamp_ms=1100, x=515, y=770, element_name="arrow", event_type="click"),  # Accurate
        ]

        count, ratio = MetricsCollector.get_accurate_clicks_count(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert count == 2
        assert ratio == pytest.approx(0.667, abs=0.01)

    def test_get_accurate_clicks_count_empty(self) -> None:
        """Test accurate click count with empty list."""
        clicks: list[Click] = []

        count, ratio = MetricsCollector.get_accurate_clicks_count(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert count == 0
        assert ratio == 0.0

    def test_get_accurate_clicks_count_single_click(self) -> None:
        """Test accurate click count with single click."""
        clicks = [
            Click(timestamp_ms=1000, x=520, y=775, element_name="arrow", event_type="click"),
        ]

        count, ratio = MetricsCollector.get_accurate_clicks_count(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )

        assert count == 1
        assert ratio == pytest.approx(1.0, abs=0.01)


class TestCalculateMaxDeviation:
    """Tests for calculate_max_deviation() method."""

    def test_calculate_max_deviation_single_click(self) -> None:
        """Test max deviation with single click."""
        clicks = [
            Click(timestamp_ms=1000, x=600, y=700, element_name="arrow", event_type="click"),
        ]

        max_dev, click = MetricsCollector.calculate_max_deviation(
            clicks, roi_center_x=512, roi_center_y=768
        )

        expected_dev = ((600 - 512) ** 2 + (700 - 768) ** 2) ** 0.5
        assert max_dev == pytest.approx(expected_dev, abs=0.1)
        assert click is not None
        assert click.x == 600
        assert click.y == 700

    def test_calculate_max_deviation_multiple_clicks(self) -> None:
        """Test max deviation identifies largest deviation."""
        clicks = [
            Click(timestamp_ms=1000, x=520, y=770, element_name="arrow", event_type="click"),  # ~11px
            Click(timestamp_ms=1050, x=512, y=768, element_name="arrow", event_type="click"),  # 0px
            Click(timestamp_ms=1100, x=600, y=850, element_name="arrow", event_type="click"),  # ~110px
        ]

        max_dev, click = MetricsCollector.calculate_max_deviation(
            clicks, roi_center_x=512, roi_center_y=768
        )

        assert max_dev > 100.0
        assert click is not None
        assert click.x == 600
        assert click.y == 850

    def test_calculate_max_deviation_empty(self) -> None:
        """Test max deviation with empty list."""
        clicks: list[Click] = []

        max_dev, click = MetricsCollector.calculate_max_deviation(
            clicks, roi_center_x=512, roi_center_y=768
        )

        assert max_dev == 0.0
        assert click is None

    def test_calculate_max_deviation_logging(self) -> None:
        """Test max deviation returns click for logging/analysis."""
        clicks = [
            Click(timestamp_ms=2000, x=100, y=100, element_name="arrow", event_type="click"),
        ]

        max_dev, click = MetricsCollector.calculate_max_deviation(
            clicks, roi_center_x=512, roi_center_y=768
        )

        # Should be able to log click for analysis
        assert click is not None
        assert click.timestamp_ms == 2000
        assert click.element_name == "arrow"


class TestOCRPrecisionCalculation:
    """Tests for calculate_ocr_precision() method."""

    def test_calculate_ocr_precision_perfect(self) -> None:
        """Test OCR precision with perfect detections."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.95),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.90),
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.88),
        ]
        expected = ["arrow", "timer", "chat"]

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert metrics.total_detections == 3
        assert metrics.correct_detections == 3
        assert metrics.precision == pytest.approx(1.0, abs=0.01)
        assert metrics.low_confidence_count == 0
        assert metrics.failed is False

    def test_calculate_ocr_precision_partial(self) -> None:
        """Test OCR precision with partial correct detections."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.95),
            OCRDetection(timestamp=datetime.now(), element_name="wrong", confidence=0.90),
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.88),
        ]
        expected = ["arrow", "timer", "chat"]

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert metrics.total_detections == 3
        assert metrics.correct_detections == 2
        assert metrics.precision == pytest.approx(0.667, abs=0.01)

    def test_calculate_ocr_precision_low_confidence(self) -> None:
        """Test OCR precision tracks low confidence detections."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.50),  # Low
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.60),  # Low
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.95),
        ]
        expected = ["arrow", "timer", "chat"]

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert metrics.total_detections == 3
        assert metrics.correct_detections == 3
        assert metrics.low_confidence_count == 2
        assert metrics.precision == 1.0

    def test_calculate_ocr_precision_consecutive_low_confidence_failure(self) -> None:
        """Test OCR precision fails on 4+ consecutive low confidence."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.50),  # Low #1
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.60),  # Low #2
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.65),   # Low #3
            OCRDetection(timestamp=datetime.now(), element_name="item", confidence=0.68),   # Low #4 - FAILS
        ]
        expected = ["arrow", "timer", "chat", "item"]

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert metrics.failed is True
        assert metrics.low_confidence_count == 4

    def test_calculate_ocr_precision_consecutive_reset(self) -> None:
        """Test consecutive low confidence counter resets on normal confidence."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.50),  # Low
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.60),  # Low
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.85),   # Normal - reset
            OCRDetection(timestamp=datetime.now(), element_name="item", confidence=0.50),   # Low (count=1)
        ]
        expected = ["arrow", "timer", "chat", "item"]

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert metrics.failed is False  # Never reached 4 consecutive

    def test_calculate_ocr_precision_empty(self) -> None:
        """Test OCR precision with empty detections."""
        detections: list[OCRDetection] = []
        expected: list[str] = []

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert metrics.total_detections == 0
        assert metrics.correct_detections == 0
        assert metrics.precision == 0.0

    def test_calculate_ocr_precision_range_clamping(self) -> None:
        """Test OCR precision is clamped to [0.0, 1.0]."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.95),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.90),
        ]
        expected = ["arrow", "timer"]

        metrics = MetricsCollector.calculate_ocr_precision(detections, expected)

        assert 0.0 <= metrics.precision <= 1.0


class TestTrackOCRLowConfidence:
    """Tests for track_ocr_low_confidence() method."""

    def test_track_ocr_low_confidence_threshold_exceeded(self) -> None:
        """Test low confidence tracking with threshold exceeded."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.50),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.60),
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.65),
            OCRDetection(timestamp=datetime.now(), element_name="item", confidence=0.68),
        ]

        metrics = MetricsCollector.track_ocr_low_confidence(
            detections, confidence_threshold=0.70, max_consecutive=3
        )

        assert metrics.total_detections == 4
        assert metrics.low_confidence_count == 4
        assert metrics.failed is True

    def test_track_ocr_low_confidence_below_threshold(self) -> None:
        """Test low confidence tracking with threshold not exceeded."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.50),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.60),
            OCRDetection(timestamp=datetime.now(), element_name="chat", confidence=0.95),
        ]

        metrics = MetricsCollector.track_ocr_low_confidence(
            detections, confidence_threshold=0.70, max_consecutive=3
        )

        assert metrics.low_confidence_count == 2
        assert metrics.failed is False
        assert metrics.consecutive_low_confidence == 0  # Reset by high confidence

    def test_track_ocr_low_confidence_custom_threshold(self) -> None:
        """Test low confidence tracking with custom threshold."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.75),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.80),
        ]

        # Using 0.85 threshold instead of default 0.70
        metrics = MetricsCollector.track_ocr_low_confidence(
            detections, confidence_threshold=0.85, max_consecutive=3
        )

        assert metrics.low_confidence_count == 2  # Both below 0.85

    def test_track_ocr_low_confidence_custom_max_consecutive(self) -> None:
        """Test low confidence tracking with custom max consecutive."""
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.50),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.60),
        ]

        # Max consecutive is 1 (fail on second low confidence)
        metrics = MetricsCollector.track_ocr_low_confidence(
            detections, confidence_threshold=0.70, max_consecutive=1
        )

        assert metrics.failed is True


class TestClickMetricsDataclass:
    """Tests for ClickMetrics dataclass."""

    def test_click_metrics_creation(self) -> None:
        """Test ClickMetrics creation."""
        metrics = ClickMetrics(
            total_clicks=10,
            accurate_clicks=9,
            avg_deviation_px=5.5,
            max_deviation_px=15.0,
            accuracy_ratio=0.9,
        )

        assert metrics.total_clicks == 10
        assert metrics.accurate_clicks == 9
        assert metrics.avg_deviation_px == 5.5
        assert metrics.accuracy_ratio == 0.9

    def test_click_metrics_default_values(self) -> None:
        """Test ClickMetrics default values."""
        metrics = ClickMetrics()

        assert metrics.total_clicks == 0
        assert metrics.accurate_clicks == 0
        assert metrics.avg_deviation_px == 0.0
        assert metrics.accuracy_ratio == 0.0


class TestOcrMetricsDataclass:
    """Tests for OcrMetrics dataclass."""

    def test_ocr_metrics_creation(self) -> None:
        """Test OcrMetrics creation."""
        metrics = OcrMetrics(
            total_detections=10,
            correct_detections=8,
            precision=0.8,
            low_confidence_count=1,
            consecutive_low_confidence=0,
            failed=False,
        )

        assert metrics.total_detections == 10
        assert metrics.correct_detections == 8
        assert metrics.precision == 0.8
        assert metrics.failed is False

    def test_ocr_metrics_failure_state(self) -> None:
        """Test OcrMetrics with failure state."""
        metrics = OcrMetrics(
            total_detections=5,
            correct_detections=5,
            precision=1.0,
            low_confidence_count=4,
            consecutive_low_confidence=4,
            failed=True,
        )

        assert metrics.failed is True
        assert metrics.consecutive_low_confidence == 4


class TestIntegrationClickAndOcrMetrics:
    """Integration tests combining click and OCR metrics."""

    def test_combined_metrics_good_run(self) -> None:
        """Test combined metrics for good run."""
        # Good clicks
        clicks = [
            Click(timestamp_ms=1000, x=510, y=770, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1050, x=514, y=766, element_name="arrow", event_type="click"),
        ]

        # Good OCR
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="arrow", confidence=0.95),
            OCRDetection(timestamp=datetime.now(), element_name="timer", confidence=0.90),
        ]

        click_metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )
        ocr_metrics = MetricsCollector.calculate_ocr_precision(detections, ["arrow", "timer"])

        # Both should be good
        assert click_metrics.accuracy_ratio > 0.9
        assert ocr_metrics.precision > 0.9
        assert not ocr_metrics.failed

    def test_combined_metrics_bad_run(self) -> None:
        """Test combined metrics for bad run."""
        # Poor clicks
        clicks = [
            Click(timestamp_ms=1000, x=100, y=100, element_name="arrow", event_type="click"),
            Click(timestamp_ms=1050, x=200, y=200, element_name="arrow", event_type="click"),
        ]

        # Poor OCR
        detections = [
            OCRDetection(timestamp=datetime.now(), element_name="wrong1", confidence=0.50),
            OCRDetection(timestamp=datetime.now(), element_name="wrong2", confidence=0.60),
            OCRDetection(timestamp=datetime.now(), element_name="wrong3", confidence=0.65),
            OCRDetection(timestamp=datetime.now(), element_name="wrong4", confidence=0.68),
        ]

        click_metrics = MetricsCollector.calculate_click_accuracy(
            clicks, roi_center_x=512, roi_center_y=768, roi_radius_px=50
        )
        ocr_metrics = MetricsCollector.calculate_ocr_precision(detections, ["arrow", "timer"])

        # Both should be bad
        assert click_metrics.accuracy_ratio < 0.5
        assert ocr_metrics.precision == 0.0
        assert ocr_metrics.failed
