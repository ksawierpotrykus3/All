"""
Timer analysis module — prediction accuracy heatmaps, timelines, and degradation trends.
Analyzes bot timer prediction performance across iterations and under system load.
"""

from typing import Dict, List, Any, Optional, Tuple
import statistics
import logging

logger = logging.getLogger(__name__)


class TimerPredictionHeatmap:
    """Generates timer prediction accuracy heatmap and error distributions."""

    def __init__(self):
        """Initialize TimerPredictionHeatmap."""
        self.predictions: List[Dict[str, Any]] = []

    def add_prediction(self, iteration: int, predicted_ms: int, actual_ms: int,
                      accuracy_pct: float) -> None:
        """
        Record a timer prediction attempt.

        Args:
            iteration: Iteration number
            predicted_ms: Predicted click time in ms
            actual_ms: Actual click time in ms
            accuracy_pct: Accuracy percentage (0-100)
        """
        delta_ms = predicted_ms - actual_ms
        self.predictions.append({
            'iteration': iteration,
            'predicted_ms': predicted_ms,
            'actual_ms': actual_ms,
            'delta_ms': delta_ms,
            'accuracy_pct': accuracy_pct,
        })

    def generate_accuracy_heatmap_image(self, width: int = 800, height: int = 600) -> bytes:
        """
        Generate heatmap: X-axis = ΔT (ms), Y-axis = iteration, color = accuracy%.
        Returns SVG bytes.

        Args:
            width: SVG width in pixels
            height: SVG height in pixels

        Returns:
            SVG content as bytes
        """
        if not self.predictions:
            return self._generate_empty_svg(width, height)

        # Build SVG
        svg_parts = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<style>',
            '.heatmap-cell { stroke: #333; stroke-width: 0.5; }',
            '.axis-label { font-size: 12px; fill: #fff; }',
            '.title { font-size: 16px; fill: #fff; font-weight: bold; }',
            '</style>',
            f'<rect width="{width}" height="{height}" fill="#1e1e1e"/>',
            f'<text x="{width//2}" y="20" text-anchor="middle" class="title">Timer Prediction Accuracy Heatmap</text>',
        ]

        # Determine color scale
        if self.predictions:
            min_accuracy = min(p['accuracy_pct'] for p in self.predictions)
            max_accuracy = max(p['accuracy_pct'] for p in self.predictions)
        else:
            min_accuracy = 0
            max_accuracy = 100

        # Draw cells
        cell_height = (height - 50) // max(1, len(self.predictions))
        cell_width = (width - 100) // max(1, len(self.predictions))

        for i, pred in enumerate(self.predictions):
            # Color based on accuracy (green=high, red=low)
            accuracy = pred['accuracy_pct']
            if max_accuracy > min_accuracy:
                normalized = (accuracy - min_accuracy) / (max_accuracy - min_accuracy)
            else:
                normalized = 0.5

            # Green (100%) to Red (0%)
            r = int(255 * (1 - normalized))
            g = int(255 * normalized)
            color = f'rgb({r},{g},0)'

            x = 50 + (i % 20) * cell_width
            y = 50 + (i // 20) * cell_height

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_width}" height="{cell_height}" '
                f'fill="{color}" class="heatmap-cell"/>'
            )

            # Add value label
            if i < 10:  # Only label first 10 to avoid clutter
                svg_parts.append(
                    f'<text x="{x + cell_width//2}" y="{y + cell_height//2}" '
                    f'text-anchor="middle" dominant-baseline="middle" class="axis-label">'
                    f'{accuracy:.1f}%</text>'
                )

        svg_parts.append('</svg>')
        svg_content = '\n'.join(svg_parts)
        return svg_content.encode('utf-8')

    def generate_error_distribution(self) -> bytes:
        """
        Generate histogram of prediction errors (SVG).
        X-axis = error in ms, Y-axis = frequency.

        Returns:
            SVG content as bytes
        """
        if not self.predictions:
            return self._generate_empty_svg(800, 600)

        # Collect errors
        errors = [abs(p['delta_ms']) for p in self.predictions]

        # Build histogram
        bin_size = 100  # 100ms bins
        max_error = max(errors) if errors else 0
        num_bins = max(1, (int(max_error) // bin_size) + 1)

        histogram = [0] * num_bins
        for error in errors:
            bin_idx = min(int(error // bin_size), num_bins - 1)
            histogram[bin_idx] += 1

        # Generate SVG
        width, height = 800, 600
        svg_parts = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<style>',
            '.bar { fill: #00ff00; stroke: #00aa00; stroke-width: 1; }',
            '.axis { stroke: #fff; stroke-width: 1; }',
            '.label { font-size: 12px; fill: #fff; }',
            '</style>',
            f'<rect width="{width}" height="{height}" fill="#1e1e1e"/>',
            f'<text x="{width//2}" y="20" text-anchor="middle" class="label" style="font-size:16px;font-weight:bold;">Error Distribution</text>',
        ]

        # Draw axes
        svg_parts.append(f'<line x1="50" y1="50" x2="50" y2="{height-50}" class="axis"/>')
        svg_parts.append(f'<line x1="50" y1="{height-50}" x2="{width-50}" y2="{height-50}" class="axis"/>')

        # Draw bars
        max_freq = max(histogram) if histogram else 1
        bar_width = (width - 100) // len(histogram)

        for i, freq in enumerate(histogram):
            bar_height = int((freq / max_freq) * (height - 100))
            x = 50 + i * bar_width
            y = height - 50 - bar_height

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" class="bar"/>'
            )

        svg_parts.append('</svg>')
        svg_content = '\n'.join(svg_parts)
        return svg_content.encode('utf-8')

    def calculate_accuracy_by_load(self, cpu_data: Dict[int, float]) -> Dict[str, float]:
        """
        Correlate timer accuracy with CPU load.

        Args:
            cpu_data: Dict mapping iteration to CPU percentage

        Returns:
            Dict with correlation metrics
        """
        if not self.predictions or not cpu_data:
            return {'correlation_coefficient': 0.0, 'average_accuracy': 0.0}

        # Extract parallel data
        accuracies = []
        loads = []

        for pred in self.predictions:
            iteration = pred['iteration']
            if iteration in cpu_data:
                accuracies.append(pred['accuracy_pct'])
                loads.append(cpu_data[iteration])

        if not accuracies or not loads:
            return {'correlation_coefficient': 0.0, 'average_accuracy': 0.0}

        # Calculate correlation (simplified Pearson)
        mean_accuracy = statistics.mean(accuracies)
        mean_load = statistics.mean(loads)

        numerator = sum((a - mean_accuracy) * (l - mean_load) for a, l in zip(accuracies, loads))
        denom_a = sum((a - mean_accuracy) ** 2 for a in accuracies)
        denom_l = sum((l - mean_load) ** 2 for l in loads)

        if denom_a > 0 and denom_l > 0:
            correlation = numerator / (denom_a * denom_l) ** 0.5
        else:
            correlation = 0.0

        return {
            'correlation_coefficient': correlation,
            'average_accuracy': mean_accuracy,
        }

    def _generate_empty_svg(self, width: int, height: int) -> bytes:
        """Generate empty SVG for no data."""
        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="{width}" height="{height}" fill="#1e1e1e"/>
            <text x="{width//2}" y="{height//2}" text-anchor="middle" fill="#fff">
            No data
            </text>
            </svg>'''
        return svg.encode('utf-8')


class TimerAnalysis:
    """Timer accuracy analysis and trend detection."""

    def __init__(self):
        """Initialize TimerAnalysis."""
        self.predictions: List[Dict[str, Any]] = []
        self.timer_events: List[Dict[str, Any]] = []

    def add_prediction_event(self, iteration: int, accuracy: float) -> None:
        """Add prediction event for trend analysis."""
        self.predictions.append({
            'iteration': iteration,
            'accuracy': accuracy,
        })

    def add_timer_event(self, iteration: int, timer_expiry_ms: int, bot_click_ms: int,
                       is_early: bool) -> None:
        """
        Record timer event: expiry time + bot click position.

        Args:
            iteration: Iteration number
            timer_expiry_ms: Timer expiry time
            bot_click_ms: Bot click time
            is_early: True if click before expiry
        """
        self.timer_events.append({
            'iteration': iteration,
            'timer_expiry_ms': timer_expiry_ms,
            'bot_click_ms': bot_click_ms,
            'is_early': is_early,
        })

    def generate_timer_event_timeline(self) -> bytes:
        """Generate SVG timeline showing timer events."""
        if not self.timer_events:
            return self._generate_empty_svg(800, 600)

        width, height = 800, 300
        svg_parts = [
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<style>',
            '.timeline-line { stroke: #fff; stroke-width: 2; }',
            '.expiry-marker { stroke: #ff0000; stroke-width: 2; }',
            '.click-early { fill: #00ff00; }',
            '.click-late { fill: #ff0000; }',
            '.label { font-size: 10px; fill: #fff; }',
            '</style>',
            f'<rect width="{width}" height="{height}" fill="#1e1e1e"/>',
        ]

        # Draw timeline axis
        svg_parts.append(f'<line x1="50" y1="{height//2}" x2="{width-50}" y2="{height//2}" class="timeline-line"/>')

        # Draw events
        x_scale = (width - 100) / max(1, len(self.timer_events))

        for i, event in enumerate(self.timer_events):
            x = 50 + i * x_scale
            color = '#00ff00' if event['is_early'] else '#ff0000'

            # Draw marker
            svg_parts.append(f'<circle cx="{x}" cy="{height//2}" r="4" fill="{color}"/>')

            # Draw label
            svg_parts.append(
                f'<text x="{x}" y="{height//2 + 20}" text-anchor="middle" class="label">'
                f'{"E" if event["is_early"] else "L"}</text>'
            )

        svg_parts.append('</svg>')
        svg_content = '\n'.join(svg_parts)
        return svg_content.encode('utf-8')

    def calculate_timer_accuracy_trend(self) -> Dict[str, Any]:
        """
        Calculate trend metrics for timer accuracy.

        Returns:
            Dict with degradation, average accuracy, etc.
        """
        if not self.predictions:
            return {
                'degradation_pct_per_10_iterations': 0.0,
                'average_accuracy_percent': 0.0,
                'anomaly_count': 0,
            }

        accuracies = [p['accuracy'] for p in self.predictions]
        avg_accuracy = statistics.mean(accuracies)

        # Calculate linear degradation
        if len(self.predictions) >= 2:
            first_half = statistics.mean(accuracies[:len(accuracies)//2])
            second_half = statistics.mean(accuracies[len(accuracies)//2:])
            degradation_per_iter = (first_half - second_half) / (len(self.predictions) // 2)
            degradation_per_10 = degradation_per_iter * 10
        else:
            degradation_per_10 = 0.0

        return {
            'degradation_pct_per_10_iterations': degradation_per_10,
            'average_accuracy_percent': avg_accuracy,
            'anomaly_count': len(self.detect_timer_anomalies()),
        }

    def detect_timer_degradation_under_load(self, cpu_load_data: Dict[int, float],
                                           load_threshold_pct: float = 70.0) -> Dict[str, Any]:
        """
        Detect if accuracy drops when CPU load exceeds threshold.

        Args:
            cpu_load_data: Dict mapping iteration to CPU %
            load_threshold_pct: CPU % threshold

        Returns:
            Dict with degradation analysis
        """
        if not self.predictions:
            return {'is_degraded': False}

        # Split into low/high load groups
        low_load_accuracies = []
        high_load_accuracies = []

        for pred in self.predictions:
            iteration = pred['iteration']
            if iteration in cpu_load_data:
                accuracy = pred['accuracy']
                load = cpu_load_data[iteration]

                if load < load_threshold_pct:
                    low_load_accuracies.append(accuracy)
                else:
                    high_load_accuracies.append(accuracy)

        if not low_load_accuracies or not high_load_accuracies:
            return {'is_degraded': False, 'low_load_accuracy': 0.0, 'high_load_accuracy': 0.0}

        low_avg = statistics.mean(low_load_accuracies)
        high_avg = statistics.mean(high_load_accuracies)
        degradation = low_avg - high_avg

        return {
            'is_degraded': degradation > 5.0,  # >5% degradation
            'low_load_accuracy': low_avg,
            'high_load_accuracy': high_avg,
            'degradation_pct': degradation,
        }

    def detect_timer_anomalies(self, threshold_sigma: float = 2.0) -> List[Dict[str, Any]]:
        """
        Detect anomalous timer predictions using statistical outlier detection.

        Args:
            threshold_sigma: Standard deviation threshold

        Returns:
            List of anomalous predictions
        """
        if not self.predictions or len(self.predictions) < 3:
            return []

        accuracies = [p['accuracy'] for p in self.predictions]
        mean_acc = statistics.mean(accuracies)
        std_dev = statistics.stdev(accuracies) if len(accuracies) > 1 else 0

        if std_dev == 0:
            return []

        anomalies = []
        for pred in self.predictions:
            z_score = abs((pred['accuracy'] - mean_acc) / std_dev)
            if z_score > threshold_sigma:
                anomalies.append({
                    'iteration': pred['iteration'],
                    'accuracy': pred['accuracy'],
                    'z_score': z_score,
                })

        return anomalies

    def _generate_empty_svg(self, width: int, height: int) -> bytes:
        """Generate empty SVG."""
        svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><rect fill="#1e1e1e" width="{width}" height="{height}"/></svg>'
        return svg.encode('utf-8')


__all__ = ['TimerPredictionHeatmap', 'TimerAnalysis']
