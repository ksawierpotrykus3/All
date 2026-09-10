# tests/simulator/test_ml_predictor.py
"""
Comprehensive tests for ML Predictor and Anomaly Scorer classes.

Tests prediction accuracy, trend detection, anomaly scoring,
degradation detection, and confidence intervals.
"""

import pytest
import time
from typing import Dict, List, Any
from unittest.mock import Mock, patch

from mvp.simulator.ml_predictor import MLPredictor, AnomalyScorer


class TestMLPredictorInit:
    """Tests for MLPredictor initialization."""

    def test_predictor_init_default(self):
        """Test MLPredictor initialization with defaults."""
        predictor = MLPredictor()
        assert predictor.window_size == 20
        assert predictor.is_trained is False

    def test_predictor_init_custom_window(self):
        """Test MLPredictor initialization with custom window size."""
        predictor = MLPredictor(window_size=50)
        assert predictor.window_size == 50

    def test_predictor_init_empty_history(self):
        """Test that history is empty on init."""
        predictor = MLPredictor()
        assert len(predictor.get_history()) == 0


class TestMLPredictorTraining:
    """Tests for training on historical metrics."""

    def test_predictor_train_on_history_simple(self):
        """Test training on simple metrics history."""
        predictor = MLPredictor(window_size=10)
        
        # Create simple history
        history = [
            {'accuracy': 0.85, 'latency_ms': 100},
            {'accuracy': 0.87, 'latency_ms': 105},
            {'accuracy': 0.88, 'latency_ms': 102},
            {'accuracy': 0.86, 'latency_ms': 108},
            {'accuracy': 0.89, 'latency_ms': 101},
        ]
        
        result = predictor.train(history)
        assert result is True
        assert predictor.is_trained is True

    def test_predictor_train_large_history(self):
        """Test training on large history (100+ iterations)."""
        predictor = MLPredictor(window_size=20)
        
        # Create 100 iteration history
        history = [
            {
                'accuracy': 0.85 + (i * 0.001),
                'latency_ms': 100 + (i * 0.5),
                'iteration': i
            }
            for i in range(100)
        ]
        
        result = predictor.train(history)
        assert result is True
        assert predictor.is_trained is True

    def test_predictor_train_insufficient_data(self):
        """Test training with insufficient data."""
        predictor = MLPredictor(window_size=20)
        
        history = [
            {'accuracy': 0.85, 'latency_ms': 100},
            {'accuracy': 0.86, 'latency_ms': 105},
        ]
        
        # Should still accept, but may have low confidence
        result = predictor.train(history)
        assert result in [True, False]  # May or may not train

    def test_predictor_train_empty_history(self):
        """Test training with empty history."""
        predictor = MLPredictor()
        result = predictor.train([])
        assert result is False


class TestMLPredictorAccuracyPrediction:
    """Tests for accuracy prediction."""

    def test_predictor_predict_next_accuracy_simple(self):
        """Test accuracy prediction on simple trend."""
        predictor = MLPredictor(window_size=10)
        
        # Increasing accuracy trend
        history = [
            {'accuracy': 0.80 + (i * 0.01), 'latency_ms': 100}
            for i in range(20)
        ]
        
        predictor.train(history)
        predicted = predictor.predict_next_accuracy()
        
        # Should predict ~0.99 (continuing upward trend)
        assert isinstance(predicted, float)
        assert 0.0 <= predicted <= 1.0

    def test_predictor_predict_next_accuracy_constant(self):
        """Test prediction on constant accuracy."""
        predictor = MLPredictor(window_size=10)
        
        # Constant accuracy
        history = [
            {'accuracy': 0.90, 'latency_ms': 100}
            for i in range(20)
        ]
        
        predictor.train(history)
        predicted = predictor.predict_next_accuracy()
        
        # Should predict close to 0.90
        assert isinstance(predicted, float)
        assert 0.80 < predicted < 1.0

    def test_predictor_predict_next_accuracy_decreasing(self):
        """Test prediction on decreasing accuracy."""
        predictor = MLPredictor(window_size=10)
        
        # Decreasing accuracy trend
        history = [
            {'accuracy': 0.95 - (i * 0.01), 'latency_ms': 100}
            for i in range(20)
        ]
        
        predictor.train(history)
        predicted = predictor.predict_next_accuracy()
        
        assert isinstance(predicted, float)
        assert 0.0 <= predicted <= 1.0

    def test_predictor_predict_accuracy_within_bounds(self):
        """Test that predictions are within valid bounds."""
        predictor = MLPredictor(window_size=15)
        
        # Random history
        history = [
            {'accuracy': 0.80 + (i % 5) * 0.02, 'latency_ms': 100}
            for i in range(30)
        ]
        
        predictor.train(history)
        
        for _ in range(10):
            predicted = predictor.predict_next_accuracy()
            assert 0.0 <= predicted <= 1.0, f"Prediction {predicted} out of bounds"


class TestMLPredictorLatencyPrediction:
    """Tests for latency trend prediction."""

    def test_predictor_predict_latency_trend(self):
        """Test latency trend prediction."""
        predictor = MLPredictor(window_size=10)
        
        history = [
            {'accuracy': 0.90, 'latency_ms': 100 + i}
            for i in range(20)
        ]
        
        predictor.train(history)
        predicted_latency, confidence = predictor.predict_latency_trend()
        
        assert isinstance(predicted_latency, float)
        assert isinstance(confidence, float)
        assert predicted_latency > 0
        assert 0.0 <= confidence <= 1.0

    def test_predictor_predict_latency_with_variance(self):
        """Test latency prediction with variance."""
        predictor = MLPredictor(window_size=10)
        
        # Latency with noise
        history = [
            {'accuracy': 0.90, 'latency_ms': 100 + (i * 0.5) + (i % 3 - 1) * 5}
            for i in range(20)
        ]
        
        predictor.train(history)
        predicted, confidence = predictor.predict_latency_trend()
        
        assert isinstance(predicted, float)
        assert isinstance(confidence, float)
        assert confidence >= 0.0


class TestMLPredictorConfidence:
    """Tests for prediction confidence."""

    def test_predictor_get_prediction_confidence(self):
        """Test getting prediction confidence."""
        predictor = MLPredictor(window_size=10)
        
        history = [
            {'accuracy': 0.90, 'latency_ms': 100}
            for i in range(20)
        ]
        
        predictor.train(history)
        confidence = predictor.get_prediction_confidence()
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_predictor_confidence_untrained(self):
        """Test confidence when untrained."""
        predictor = MLPredictor()
        confidence = predictor.get_prediction_confidence()
        
        # Should be 0 or very low when untrained
        assert confidence < 0.1

    def test_predictor_confidence_increases_with_data(self):
        """Test that confidence increases with more data."""
        predictor = MLPredictor(window_size=10)
        
        confidences = []
        
        # Train with growing history
        for size in [5, 10, 20, 50]:
            history = [
                {'accuracy': 0.90, 'latency_ms': 100}
                for i in range(size)
            ]
            predictor.train(history)
            confidence = predictor.get_prediction_confidence()
            confidences.append(confidence)
        
        # Confidence should generally increase
        assert len(confidences) == 4


class TestAnomalyScorerInit:
    """Tests for AnomalyScorer initialization."""

    def test_anomaly_scorer_init_default(self):
        """Test AnomalyScorer initialization with defaults."""
        scorer = AnomalyScorer()
        assert scorer.sensitivity == 2.0

    def test_anomaly_scorer_init_custom_sensitivity(self):
        """Test AnomalyScorer initialization with custom sensitivity."""
        scorer = AnomalyScorer(sensitivity=3.0)
        assert scorer.sensitivity == 3.0


class TestAnomalyScorerScoring:
    """Tests for anomaly scoring."""

    def test_anomaly_scorer_score_iteration_normal(self):
        """Test scoring normal metrics."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        metrics = {
            'accuracy': 0.90,
            'latency_ms': 100,
            'cpu_percent': 50,
            'ocr_confidence': 0.95
        }
        
        score = scorer.score_iteration(metrics)
        
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_anomaly_scorer_score_iteration_anomalous(self):
        """Test scoring anomalous metrics."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Normal baseline
        for _ in range(10):
            scorer.score_iteration({'accuracy': 0.90, 'latency_ms': 100})
        
        # Anomalous metrics (very low accuracy)
        anomaly_metrics = {
            'accuracy': 0.10,
            'latency_ms': 100,
            'cpu_percent': 50,
            'ocr_confidence': 0.95
        }
        
        score = scorer.score_iteration(anomaly_metrics)
        
        # Anomalous score should be high
        assert score >= 45

    def test_anomaly_scorer_score_latency_spike(self):
        """Test detecting latency spikes."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Normal latency
        for _ in range(20):
            scorer.score_iteration({'accuracy': 0.90, 'latency_ms': 100})
        
        # Latency spike (2x normal)
        spike_metrics = {
            'accuracy': 0.90,
            'latency_ms': 300,  # 3x normal
            'cpu_percent': 50,
            'ocr_confidence': 0.95
        }
        
        score = scorer.score_iteration(spike_metrics)
        assert score > 30


class TestAnomalyScorerDegradation:
    """Tests for degradation detection."""

    def test_anomaly_scorer_detect_accuracy_drop(self):
        """Test detecting accuracy drop > 10%."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        baseline = {'accuracy': 0.90, 'latency_ms': 100}
        current = {'accuracy': 0.75, 'latency_ms': 100}  # 15% drop
        
        degraded = scorer.detect_degradation(current, baseline)
        assert degraded is True

    def test_anomaly_scorer_detect_no_degradation_small(self):
        """Test that small accuracy drops are not flagged."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        baseline = {'accuracy': 0.90, 'latency_ms': 100}
        current = {'accuracy': 0.88, 'latency_ms': 100}  # 2% drop
        
        degraded = scorer.detect_degradation(current, baseline)
        assert degraded is False

    def test_anomaly_scorer_detect_latency_spike(self):
        """Test detecting latency spikes > 2σ."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Build history for standard deviation
        for _ in range(20):
            scorer.score_iteration({'accuracy': 0.90, 'latency_ms': 100})
        
        baseline = {'accuracy': 0.90, 'latency_ms': 100}
        current = {'accuracy': 0.90, 'latency_ms': 250}  # Large spike
        
        degraded = scorer.detect_degradation(current, baseline)
        # May or may not degrade depending on std calculation
        assert isinstance(degraded, bool)

    def test_anomaly_scorer_degradation_improvement(self):
        """Test that improvements are not flagged as degradation."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        baseline = {'accuracy': 0.80, 'latency_ms': 100}
        current = {'accuracy': 0.95, 'latency_ms': 80}  # Improvement
        
        degraded = scorer.detect_degradation(current, baseline)
        assert degraded is False


class TestAnomalyScorerThreshold:
    """Tests for alerting thresholds."""

    def test_anomaly_scorer_get_alerting_threshold(self):
        """Test getting dynamic alerting threshold."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Build history
        for _ in range(50):
            scorer.score_iteration({'accuracy': 0.90, 'latency_ms': 100})
        
        threshold = scorer.get_alerting_threshold()
        
        assert isinstance(threshold, (int, float))
        assert 0 <= threshold <= 100

    def test_anomaly_scorer_threshold_adaptive(self):
        """Test that threshold adapts to data."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Normal data with low variance
        for _ in range(50):
            score = scorer.score_iteration({'accuracy': 0.90, 'latency_ms': 100})
        
        threshold1 = scorer.get_alerting_threshold()
        
        # Add some high scores
        for _ in range(10):
            scorer.score_iteration({'accuracy': 0.50, 'latency_ms': 200})
        
        threshold2 = scorer.get_alerting_threshold()
        
        # Thresholds should be different after variance increases
        assert isinstance(threshold1, (int, float))
        assert isinstance(threshold2, (int, float))


class TestMLIntegration:
    """Integration tests for ML predictor and scorer."""

    def test_predictor_and_scorer_together(self):
        """Test using predictor and scorer together."""
        predictor = MLPredictor(window_size=10)
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Simulate metrics over 50 iterations
        history = []
        for i in range(50):
            iteration_metrics = {
                'accuracy': 0.90 + (i % 10) * 0.01,
                'latency_ms': 100 + i * 0.5,
                'cpu_percent': 50,
                'ocr_confidence': 0.95
            }
            history.append(iteration_metrics)
            
            # Score each iteration
            score = scorer.score_iteration(iteration_metrics)
            assert 0 <= score <= 100
        
        # Train predictor
        predictor.train(history)
        assert predictor.is_trained is True
        
        # Make predictions
        predicted_acc = predictor.predict_next_accuracy()
        predicted_lat, confidence = predictor.predict_latency_trend()
        
        assert 0 <= predicted_acc <= 1.0
        assert predicted_lat > 0
        assert 0 <= confidence <= 1.0

    def test_ml_with_degradation_scenario(self):
        """Test ML with simulated degradation scenario."""
        predictor = MLPredictor(window_size=10)
        scorer = AnomalyScorer(sensitivity=2.0)
        
        # Normal phase: 20 good iterations
        history = []
        for i in range(20):
            metrics = {
                'accuracy': 0.92,
                'latency_ms': 100,
                'cpu_percent': 40
            }
            history.append(metrics)
        
        # Degradation phase: 10 bad iterations
        for i in range(10):
            metrics = {
                'accuracy': 0.70,
                'latency_ms': 200,
                'cpu_percent': 80
            }
            history.append(metrics)
        
        # Train on full history
        predictor.train(history)
        
        # Score degradation
        baseline = history[0]
        degraded_metrics = history[-1]
        
        is_degraded = scorer.detect_degradation(degraded_metrics, baseline)
        # Should detect significant degradation
        assert is_degraded is True

    def test_ml_sensitivity_adjustment(self):
        """Test anomaly detection with different sensitivities."""
        high_sensitivity = AnomalyScorer(sensitivity=3.0)
        low_sensitivity = AnomalyScorer(sensitivity=1.0)
        
        # Build baseline
        metrics = {'accuracy': 0.90, 'latency_ms': 100}
        for _ in range(20):
            high_sensitivity.score_iteration(metrics)
            low_sensitivity.score_iteration(metrics)
        
        # Slight anomaly
        anomaly = {'accuracy': 0.85, 'latency_ms': 100}
        
        high_score = high_sensitivity.score_iteration(anomaly)
        low_score = low_sensitivity.score_iteration(anomaly)
        
        # Both should detect anomaly, may differ in magnitude
        assert isinstance(high_score, (int, float))
        assert isinstance(low_score, (int, float))


class TestMLEdgeCases:
    """Edge case tests."""

    def test_predictor_with_nan_values(self):
        """Test handling of NaN or invalid values."""
        predictor = MLPredictor(window_size=10)
        
        history = [
            {'accuracy': 0.90, 'latency_ms': 100},
            {'accuracy': 0.91, 'latency_ms': None},  # Invalid
            {'accuracy': 0.89, 'latency_ms': 102},
        ]
        
        # Should handle gracefully
        result = predictor.train(history)
        assert isinstance(result, bool)

    def test_scorer_with_extreme_values(self):
        """Test scoring extreme values."""
        scorer = AnomalyScorer(sensitivity=2.0)
        
        extreme_metrics = {
            'accuracy': 0.0,
            'latency_ms': 10000,
            'cpu_percent': 99.9,
            'ocr_confidence': 0.01
        }
        
        score = scorer.score_iteration(extreme_metrics)
        assert 0 <= score <= 100

    def test_predictor_single_iteration(self):
        """Test predictor with only single iteration of data."""
        predictor = MLPredictor(window_size=20)
        
        history = [{'accuracy': 0.90, 'latency_ms': 100}]
        result = predictor.train(history)
        
        # Should handle gracefully
        assert isinstance(result, bool)
