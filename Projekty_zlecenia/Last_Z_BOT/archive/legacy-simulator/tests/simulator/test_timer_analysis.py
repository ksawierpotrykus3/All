"""
Test suite for timer responsiveness analysis — prediction accuracy, timeline, and degradation trends.
Tests cover heatmaps, timelines, and trend analysis metrics.
"""

import pytest
from mvp.simulator.reporting.timer_analysis import TimerPredictionHeatmap, TimerAnalysis


class TestTimerPredictionHeatmapInit:
    """Tests for TimerPredictionHeatmap initialization."""

    def test_heatmap_init(self):
        """Test TimerPredictionHeatmap initializes correctly."""
        heatmap = TimerPredictionHeatmap()
        assert heatmap.predictions == []

    def test_heatmap_init_empty(self):
        """Test TimerPredictionHeatmap starts empty."""
        heatmap = TimerPredictionHeatmap()
        assert len(heatmap.predictions) == 0


class TestTimerPredictionHeatmapRecording:
    """Tests for recording timer predictions."""

    def test_add_prediction(self):
        """Test adding a prediction record."""
        heatmap = TimerPredictionHeatmap()
        heatmap.add_prediction(
            iteration=1,
            predicted_ms=60000,
            actual_ms=60000,
            accuracy_pct=100.0
        )
        assert len(heatmap.predictions) == 1

    def test_add_multiple_predictions(self):
        """Test adding multiple predictions."""
        heatmap = TimerPredictionHeatmap()
        for i in range(10):
            heatmap.add_prediction(
                iteration=i,
                predicted_ms=60000 - (i * 1000),
                actual_ms=60000,
                accuracy_pct=100.0 - (i * 1.0)
            )
        assert len(heatmap.predictions) == 10

    def test_prediction_record_structure(self):
        """Test prediction record has required fields."""
        heatmap = TimerPredictionHeatmap()
        heatmap.add_prediction(
            iteration=1,
            predicted_ms=59000,
            actual_ms=60000,
            accuracy_pct=98.3
        )
        
        record = heatmap.predictions[0]
        assert 'iteration' in record
        assert 'delta_ms' in record
        assert 'accuracy_pct' in record
        assert record['accuracy_pct'] == 98.3


class TestTimerHeatmapGeneration:
    """Tests for heatmap generation."""

    def test_generate_accuracy_heatmap(self):
        """Test generating accuracy heatmap SVG."""
        heatmap = TimerPredictionHeatmap()
        for i in range(5):
            heatmap.add_prediction(i, 60000 - (i*500), 60000, 99.0 - i*0.5)
        
        svg_bytes = heatmap.generate_accuracy_heatmap_image(width=800, height=600)
        assert isinstance(svg_bytes, bytes)
        assert len(svg_bytes) > 0
        assert b'svg' in svg_bytes.lower() or b'<?xml' in svg_bytes

    def test_generate_error_distribution(self):
        """Test generating error distribution histogram."""
        heatmap = TimerPredictionHeatmap()
        for i in range(10):
            heatmap.add_prediction(i, 60000 + (i*100), 60000, 99.0 - (i*0.1))
        
        svg_bytes = heatmap.generate_error_distribution()
        assert isinstance(svg_bytes, bytes)
        assert len(svg_bytes) > 0

    def test_heatmap_svg_contains_data(self):
        """Test heatmap SVG contains numeric data."""
        heatmap = TimerPredictionHeatmap()
        heatmap.add_prediction(1, 59500, 60000, 99.17)
        heatmap.add_prediction(2, 60500, 60000, 99.17)
        
        svg_bytes = heatmap.generate_accuracy_heatmap_image()
        # Should contain heatmap data
        assert len(svg_bytes) > 100


class TestTimerAccuracyByLoad:
    """Tests for correlation between accuracy and CPU load."""

    def test_calculate_accuracy_by_load(self):
        """Test calculating accuracy correlation with CPU load."""
        heatmap = TimerPredictionHeatmap()
        
        # Add predictions with varying accuracy
        for i in range(10):
            accuracy = 100.0 - (i * 2.0)  # Degrading accuracy
            heatmap.add_prediction(i, 60000, 60000, accuracy)
        
        # Simulate CPU load data
        cpu_data = {i: 10 + (i * 10) for i in range(10)}  # 10% to 100%
        
        result = heatmap.calculate_accuracy_by_load(cpu_data)
        assert isinstance(result, dict)
        assert 'correlation_coefficient' in result
        assert 'average_accuracy' in result


class TestTimerEarlyVsLateClicks:
    """Tests for early vs late click distribution."""

    def test_early_vs_late_distribution(self):
        """Test analyzing early vs late click distribution."""
        analysis = TimerAnalysis()
        
        # Add early clicks (before expiry)
        for i in range(5):
            analysis.add_timer_event(
                iteration=i,
                timer_expiry_ms=60000,
                bot_click_ms=59000,  # 1 second early
                is_early=True
            )
        
        # Add late clicks (after expiry)
        for i in range(5, 10):
            analysis.add_timer_event(
                iteration=i,
                timer_expiry_ms=60000,
                bot_click_ms=61000,  # 1 second late
                is_early=False
            )
        
        assert len(analysis.timer_events) == 10


class TestTimerEventTimeline:
    """Tests for timer event timeline generation."""

    def test_add_timer_event(self):
        """Test adding timer events."""
        analysis = TimerAnalysis()
        analysis.add_timer_event(1, 60000, 60000, False)
        assert len(analysis.timer_events) == 1

    def test_timer_event_structure(self):
        """Test timer event record structure."""
        analysis = TimerAnalysis()
        analysis.add_timer_event(
            iteration=1,
            timer_expiry_ms=60000,
            bot_click_ms=59500,
            is_early=True
        )
        
        event = analysis.timer_events[0]
        assert 'iteration' in event
        assert 'timer_expiry_ms' in event
        assert 'bot_click_ms' in event
        assert 'is_early' in event

    def test_generate_timer_event_timeline(self):
        """Test generating timer event timeline SVG."""
        analysis = TimerAnalysis()
        
        for i in range(10):
            is_early = i % 2 == 0
            click_ms = 59000 if is_early else 61000
            analysis.add_timer_event(i, 60000, click_ms, is_early)
        
        svg_bytes = analysis.generate_timer_event_timeline()
        assert isinstance(svg_bytes, bytes)
        assert len(svg_bytes) > 0


class TestTimerTrendAnalysis:
    """Tests for timer accuracy trend analysis."""

    def test_calculate_timer_accuracy_trend(self):
        """Test calculating timer accuracy trend."""
        analysis = TimerAnalysis()
        
        # Simulate degrading accuracy over iterations
        for i in range(20):
            accuracy = 100.0 - (i * 1.0)  # Degrade 1% per iteration
            analysis.add_prediction_event(i, accuracy)
        
        trend = analysis.calculate_timer_accuracy_trend()
        assert isinstance(trend, dict)
        assert 'degradation_pct_per_10_iterations' in trend
        assert 'average_accuracy_percent' in trend

    def test_detect_timer_degradation_under_load(self):
        """Test detecting accuracy degradation under CPU load."""
        analysis = TimerAnalysis()
        
        # Low load: high accuracy
        for i in range(10):
            analysis.add_prediction_event(i, accuracy=98.0)
        
        # High load: low accuracy
        for i in range(10, 20):
            analysis.add_prediction_event(i, accuracy=85.0)
        
        # Simulate CPU load
        cpu_load_data = {i: 20.0 for i in range(10)}  # Low load
        cpu_load_data.update({i: 80.0 for i in range(10, 20)})  # High load
        
        degradation = analysis.detect_timer_degradation_under_load(
            cpu_load_data=cpu_load_data,
            load_threshold_pct=70.0
        )
        
        assert isinstance(degradation, dict)
        assert 'is_degraded' in degradation
        assert 'low_load_accuracy' in degradation
        assert 'high_load_accuracy' in degradation


class TestTimerAnomalyDetection:
    """Tests for anomaly detection in timer predictions."""

    def test_detect_anomaly_outlier(self):
        """Test detecting anomalous predictions (outliers)."""
        analysis = TimerAnalysis()
        
        # Normal predictions
        for i in range(20):
            analysis.add_prediction_event(i, accuracy=98.0)
        
        # Anomaly: very low accuracy
        analysis.add_prediction_event(20, accuracy=20.0)
        
        anomalies = analysis.detect_timer_anomalies()
        assert len(anomalies) > 0
        assert any(a['iteration'] == 20 for a in anomalies)

    def test_anomaly_detection_threshold(self):
        """Test anomaly detection with configurable threshold."""
        analysis = TimerAnalysis()
        
        for i in range(10):
            accuracy = 95.0 if i % 2 == 0 else 85.0
            analysis.add_prediction_event(i, accuracy)
        
        # Loose threshold
        anomalies_loose = analysis.detect_timer_anomalies(threshold_sigma=3.0)
        # Tight threshold
        anomalies_tight = analysis.detect_timer_anomalies(threshold_sigma=1.0)
        
        # Tight threshold should find more anomalies
        assert len(anomalies_tight) >= len(anomalies_loose)


class TestTimerAnalysisEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_analysis(self):
        """Test analysis with no data."""
        analysis = TimerAnalysis()
        trend = analysis.calculate_timer_accuracy_trend()
        
        assert trend is not None
        # Should handle empty gracefully
        assert isinstance(trend, dict)

    def test_single_prediction(self):
        """Test analysis with single prediction."""
        analysis = TimerAnalysis()
        analysis.add_prediction_event(0, accuracy=99.5)
        
        trend = analysis.calculate_timer_accuracy_trend()
        assert 'average_accuracy_percent' in trend

    def test_all_perfect_predictions(self):
        """Test analysis where all predictions are perfect (100%)."""
        analysis = TimerAnalysis()
        
        for i in range(10):
            analysis.add_prediction_event(i, accuracy=100.0)
        
        trend = analysis.calculate_timer_accuracy_trend()
        assert trend['average_accuracy_percent'] == 100.0
        assert trend['degradation_pct_per_10_iterations'] == 0.0

    def test_all_terrible_predictions(self):
        """Test analysis where all predictions are terrible (0%)."""
        analysis = TimerAnalysis()
        
        for i in range(10):
            analysis.add_prediction_event(i, accuracy=0.0)
        
        trend = analysis.calculate_timer_accuracy_trend()
        assert trend['average_accuracy_percent'] == 0.0

    def test_zero_cpu_load(self):
        """Test degradation detection with zero CPU load."""
        analysis = TimerAnalysis()
        
        for i in range(10):
            analysis.add_prediction_event(i, accuracy=99.0)
        
        cpu_load = {i: 0.0 for i in range(10)}
        
        degradation = analysis.detect_timer_degradation_under_load(
            cpu_load_data=cpu_load,
            load_threshold_pct=50.0
        )
        
        # No high load, so no degradation detected
        assert degradation['is_degraded'] is False

    def test_extremely_high_cpu_load(self):
        """Test degradation with extremely high CPU load (100%)."""
        analysis = TimerAnalysis()
        
        for i in range(10):
            analysis.add_prediction_event(i, accuracy=50.0)  # Poor accuracy
        
        cpu_load = {i: 100.0 for i in range(10)}
        
        degradation = analysis.detect_timer_degradation_under_load(
            cpu_load_data=cpu_load,
            load_threshold_pct=70.0
        )
        
        assert isinstance(degradation, dict)
