# mvp/simulator/ml_predictor.py
"""
Machine Learning Predictions and Anomaly Detection.

Provides:
- MLPredictor: Forecasts accuracy and latency trends using linear regression
- AnomalyScorer: Detects statistical anomalies and degradation
"""

import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from collections import deque
import statistics


logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Machine Learning Predictor for accuracy and latency forecasting.

    Uses linear regression on rolling window of historical metrics
    to predict next iteration performance.
    """

    def __init__(self, window_size: int = 20):
        """
        Initialize MLPredictor.

        Args:
            window_size: Rolling window size for training (default: 20)
        """
        self.window_size = window_size
        self.is_trained = False
        self._history: List[Dict[str, Any]] = []

        # Model parameters
        self._accuracy_model: Optional[Tuple[float, float]] = None  # (slope, intercept)
        self._latency_model: Optional[Tuple[float, float]] = None

    def train(self, metrics_history: List[Dict[str, Any]]) -> bool:
        """
        Train predictor on historical metrics.

        Args:
            metrics_history: List of iteration metrics dicts

        Returns:
            True if training successful, False otherwise
        """
        try:
            if not metrics_history or len(metrics_history) < 2:
                logger.warning("Insufficient data for training")
                return False

            self._history = metrics_history[-self.window_size:]

            # Extract features
            accuracies = []
            latencies = []

            for metric in self._history:
                if 'accuracy' in metric and metric['accuracy'] is not None:
                    accuracies.append(metric['accuracy'])
                if 'latency_ms' in metric and metric['latency_ms'] is not None:
                    latencies.append(metric['latency_ms'])

            if len(accuracies) < 2 or len(latencies) < 2:
                return False

            # Simple linear regression: fit y = mx + b
            self._accuracy_model = self._linear_regression(
                list(range(len(accuracies))), accuracies
            )
            self._latency_model = self._linear_regression(
                list(range(len(latencies))), latencies
            )

            self.is_trained = True
            logger.info(f"MLPredictor trained on {len(self._history)} iterations")
            return True

        except Exception as e:
            logger.error(f"Training error: {e}")
            return False

    def predict_next_accuracy(self) -> float:
        """
        Forecast accuracy for next iteration.

        Returns:
            Predicted accuracy (0.0 to 1.0) or 0.5 if untrained
        """
        if not self.is_trained or self._accuracy_model is None:
            return 0.5

        try:
            slope, intercept = self._accuracy_model
            next_index = len(self._history)
            predicted = slope * next_index + intercept

            # Clamp to valid range
            return max(0.0, min(1.0, predicted))

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0.5

    def predict_latency_trend(self) -> Tuple[float, float]:
        """
        Forecast latency trend for next iteration.

        Returns:
            Tuple of (predicted_latency_ms, confidence_0_to_1)
        """
        if not self.is_trained or self._latency_model is None:
            return (100.0, 0.0)

        try:
            slope, intercept = self._latency_model
            next_index = len(self._history)
            predicted_latency = max(0.0, slope * next_index + intercept)

            # Calculate confidence based on variance
            confidence = self.get_prediction_confidence()

            return (predicted_latency, confidence)

        except Exception as e:
            logger.error(f"Latency prediction error: {e}")
            return (100.0, 0.0)

    def get_prediction_confidence(self) -> float:
        """
        Get confidence of predictions (0.0 to 1.0).

        Returns:
            Confidence score
        """
        if not self.is_trained or not self._history:
            return 0.0

        try:
            # Confidence based on data consistency
            if len(self._history) < 5:
                return 0.3

            # Calculate variance of accuracies
            accuracies = [
                m['accuracy'] for m in self._history
                if 'accuracy' in m and m['accuracy'] is not None
            ]

            if not accuracies or len(accuracies) < 2:
                return 0.2

            # Low variance = high confidence
            mean_acc = statistics.mean(accuracies)
            variance = sum((x - mean_acc) ** 2 for x in accuracies) / len(accuracies)
            std_dev = math.sqrt(variance) if variance >= 0 else 0

            # Confidence inversely proportional to std dev
            # Normalize to 0-1 range
            confidence = max(0.0, 1.0 - (std_dev * 2))
            return min(1.0, confidence)

        except Exception as e:
            logger.error(f"Confidence calculation error: {e}")
            return 0.1

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get training history.

        Returns:
            List of metrics dicts used for training
        """
        return list(self._history)

    @staticmethod
    def _linear_regression(
        x_values: List[float],
        y_values: List[float]
    ) -> Tuple[float, float]:
        """
        Simple linear regression (y = mx + b).

        Args:
            x_values: Independent variable values
            y_values: Dependent variable values

        Returns:
            Tuple of (slope, intercept)
        """
        if len(x_values) < 2 or len(y_values) < 2:
            return (0.0, statistics.mean(y_values) if y_values else 0.5)

        try:
            n = len(x_values)
            x_mean = statistics.mean(x_values)
            y_mean = statistics.mean(y_values)

            # Calculate slope: m = Σ((x - x_mean)(y - y_mean)) / Σ((x - x_mean)²)
            numerator = sum(
                (x_values[i] - x_mean) * (y_values[i] - y_mean)
                for i in range(n)
            )
            denominator = sum(
                (x_values[i] - x_mean) ** 2
                for i in range(n)
            )

            if abs(denominator) < 1e-10:
                slope = 0.0
            else:
                slope = numerator / denominator

            intercept = y_mean - slope * x_mean

            return (slope, intercept)

        except Exception:
            return (0.0, statistics.mean(y_values) if y_values else 0.5)


import math


class AnomalyScorer:
    """
    Statistical Anomaly Detector and Degradation Analyzer.

    Detects outliers and performance degradation using
    multi-dimensional statistics.
    """

    def __init__(self, sensitivity: float = 2.0):
        """
        Initialize AnomalyScorer.

        Args:
            sensitivity: Standard deviation multiplier (default: 2.0)
                Lower = more sensitive, Higher = less sensitive
        """
        self.sensitivity = sensitivity
        self._score_history: deque = deque(maxlen=100)
        self._baseline: Optional[Dict[str, Any]] = None

    def score_iteration(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate anomaly score for iteration metrics (0-100).

        Args:
            metrics: Current iteration metrics

        Returns:
            Anomaly score (0=normal, 100=extreme anomaly)
        """
        try:
            if self._baseline is None:
                # Use first metric as baseline
                self._baseline = metrics.copy()
                self._score_history.append(0.0)
                return 0.0

            score = 0.0

            # Check accuracy
            accuracy = metrics.get('accuracy', 0.5)
            baseline_acc = self._baseline.get('accuracy', 0.5)
            acc_delta = abs(accuracy - baseline_acc)

            if acc_delta > 0.1:
                score += min(50.0, acc_delta * 100)

            # Check latency
            latency = metrics.get('latency_ms', 100)
            baseline_lat = self._baseline.get('latency_ms', 100)
            lat_delta = abs(latency - baseline_lat)

            if lat_delta > baseline_lat * 0.5:
                score += min(50.0, (lat_delta / baseline_lat) * 50)

            # Check OCR confidence
            ocr_conf = metrics.get('ocr_confidence', 0.95)
            if ocr_conf < 0.7:
                score += (0.7 - ocr_conf) * 50

            # Check CPU
            cpu = metrics.get('cpu_percent', 50)
            if cpu > 80:
                score += (cpu - 80)

            # Normalize score
            final_score = min(100.0, score)
            self._score_history.append(final_score)

            return final_score

        except Exception as e:
            logger.error(f"Scoring error: {e}")
            return 0.0

    def detect_degradation(
        self,
        current_metrics: Dict[str, Any],
        baseline_metrics: Dict[str, Any]
    ) -> bool:
        """
        Detect if current metrics show significant degradation vs baseline.

        Args:
            current_metrics: Current iteration metrics
            baseline_metrics: Baseline/normal metrics

        Returns:
            True if degradation detected, False otherwise
        """
        try:
            # Accuracy drop > 10%
            curr_acc = current_metrics.get('accuracy', 0.5)
            base_acc = baseline_metrics.get('accuracy', 0.5)
            acc_drop = base_acc - curr_acc

            if acc_drop > 0.10:
                logger.warning(
                    f"Accuracy degradation detected: {base_acc:.2%} → {curr_acc:.2%}"
                )
                return True

            # Latency spike > 2x
            curr_lat = current_metrics.get('latency_ms', 100)
            base_lat = baseline_metrics.get('latency_ms', 100)

            if curr_lat > base_lat * 2:
                logger.warning(
                    f"Latency spike detected: {base_lat}ms → {curr_lat}ms"
                )
                return True

            # OCR confidence drop > 20%
            curr_ocr = current_metrics.get('ocr_confidence', 1.0)
            base_ocr = baseline_metrics.get('ocr_confidence', 1.0)
            ocr_drop = base_ocr - curr_ocr

            if ocr_drop > 0.20:
                logger.warning(
                    f"OCR confidence degradation: {base_ocr:.2%} → {curr_ocr:.2%}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Degradation detection error: {e}")
            return False

    def get_alerting_threshold(self) -> float:
        """
        Get dynamic alerting threshold based on observed scores.

        Returns:
            Threshold score (0-100) for alerting
        """
        try:
            if len(self._score_history) < 5:
                return 40.0

            scores = list(self._score_history)
            mean_score = statistics.mean(scores)
            variance = statistics.variance(scores) if len(scores) > 1 else 0
            std_dev = math.sqrt(variance)

            # Threshold = mean + (sensitivity * std_dev)
            # Higher sensitivity = higher threshold (less alerts)
            threshold = mean_score + (self.sensitivity * std_dev)

            return max(10.0, min(100.0, threshold))

        except Exception as e:
            logger.error(f"Threshold calculation error: {e}")
            return 50.0
