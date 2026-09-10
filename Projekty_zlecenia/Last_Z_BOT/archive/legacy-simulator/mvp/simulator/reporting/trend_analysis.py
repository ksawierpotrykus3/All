"""
Trend analysis module.
Detects trends, anomalies, and patterns in simulation data with real analysis.
"""
from typing import List, Dict, Tuple, Optional
import logging
import statistics

logger = logging.getLogger(__name__)


class TrendAnalysis:
    """
    Analyzes trends and anomalies in simulation data.
    """

    def __init__(self):
        """Initialize TrendAnalysis."""
        self.accuracy_data: List[float] = []
        self.recovery_data: List[float] = []
        self.last_image_bytes = None

    def add_accuracy_data(self, accuracy_values: List[float]) -> bool:
        """
        Add accuracy trend data.

        Args:
            accuracy_values: List of accuracy percentages

        Returns:
            True if successful
        """
        try:
            self.accuracy_data = accuracy_values.copy()
            logger.debug(f"Added {len(accuracy_values)} accuracy data points")
            return True
        except Exception as e:
            logger.error(f"Error adding accuracy data: {e}")
            return False

    def calculate_degradation(self) -> Optional[float]:
        """
        Calculate accuracy degradation trend using linear regression.

        Returns:
            Degradation percentage per 10 iterations (negative = decline)
        """
        try:
            if len(self.accuracy_data) < 2:
                return 0.0
            
            # Simple linear regression to get slope
            n = len(self.accuracy_data)
            x_values = list(range(n))
            y_values = self.accuracy_data
            
            # Calculate slope
            x_mean = sum(x_values) / n
            y_mean = sum(y_values) / n
            
            numerator = sum(
                (x_values[i] - x_mean) * (y_values[i] - y_mean)
                for i in range(n)
            )
            denominator = sum(
                (x_values[i] - x_mean) ** 2
                for i in range(n)
            )
            
            if denominator == 0:
                return 0.0
            
            slope = numerator / denominator
            
            # Per 10 iterations
            degradation_per_10 = slope * 10
            
            logger.debug(f"Degradation: {degradation_per_10:.2f}% per 10 iterations")
            return degradation_per_10
        except Exception as e:
            logger.error(f"Error calculating degradation: {e}")
            return None

    def detect_anomalies(self, threshold: float = 2.0) -> List[Tuple[int, float]]:
        """
        Detect anomalies in accuracy data using Z-score (standard deviation).
        
        Threshold 2.0 = |Z| > 2.0 (95% confidence)
        Threshold 2.5 = |Z| > 2.5 (closer to 99%)

        Args:
            threshold: Number of standard deviations for anomaly threshold

        Returns:
            List of (index, value) tuples for anomalies
        """
        try:
            if len(self.accuracy_data) < 2:
                return []
            
            mean = statistics.mean(self.accuracy_data)
            stdev = statistics.stdev(self.accuracy_data)
            
            if stdev == 0:
                return []
            
            anomalies = []
            for i, value in enumerate(self.accuracy_data):
                z_score = abs((value - mean) / stdev)
                if z_score > threshold:
                    anomalies.append((i, value))
            
            logger.debug(f"Detected {len(anomalies)} anomalies (threshold={threshold})")
            return anomalies
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []

    def generate_degradation_chart_image(self, width: int = 1000, height: int = 400) -> bytes:
        """
        Generate degradation trend chart as SVG.

        Args:
            width: Image width
            height: Image height

        Returns:
            SVG bytes
        """
        try:
            if not self.accuracy_data:
                return self._generate_empty_svg(width, height).encode('utf-8')
            
            # Normalize points
            n = len(self.accuracy_data)
            points = []
            for i, value in enumerate(self.accuracy_data):
                x = i / (n - 1) if n > 1 else 0.5
                y = value / 100.0  # Normalize to 0-1
                points.append((x, y))
            
            # Calculate linear fit for trend line
            if n >= 2:
                x_vals = [p[0] for p in points]
                y_vals = [p[1] for p in points]
                x_mean = sum(x_vals) / n
                y_mean = sum(y_vals) / n
                
                numerator = sum(
                    (x_vals[i] - x_mean) * (y_vals[i] - y_mean)
                    for i in range(n)
                )
                denominator = sum(
                    (x_vals[i] - x_mean) ** 2
                    for i in range(n)
                )
                
                if denominator > 0:
                    slope = numerator / denominator
                    intercept = y_mean - slope * x_mean
                    
                    # Trend line endpoints
                    trend_start = intercept
                    trend_end = slope + intercept
                    trend_points = [(0, trend_start), (1, trend_end)]
                else:
                    trend_points = None
            else:
                trend_points = None
            
            # Build SVG
            margin = 50
            svg_parts = [
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 11px; }</style>',
                f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="black" stroke-width="1"/>',
            ]
            
            chart_w = width - 2 * margin
            chart_h = height - 2 * margin
            
            # Trend line (if available)
            if trend_points and len(trend_points) == 2:
                x1 = margin + trend_points[0][0] * chart_w
                y1 = margin + (1 - trend_points[0][1]) * chart_h
                x2 = margin + trend_points[1][0] * chart_w
                y2 = margin + (1 - trend_points[1][1]) * chart_h
                
                svg_parts.append(
                    f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#FF6B6B" stroke-width="2" stroke-dasharray="5,5"/>'
                )
            
            # Data points
            for i, (x, y) in enumerate(points):
                px = margin + x * chart_w
                py = margin + (1 - y) * chart_h
                
                # Check if anomaly
                is_anomaly = False
                anomalies = self.detect_anomalies()
                for anomaly_idx, _ in anomalies:
                    if anomaly_idx == i:
                        is_anomaly = True
                        break
                
                if is_anomaly:
                    svg_parts.append(
                        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#FF6B6B" stroke="black" stroke-width="2"/>'
                    )
                else:
                    svg_parts.append(
                        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#4CAF50" stroke="black" stroke-width="1"/>'
                    )
            
            # Connect points
            if len(points) > 1:
                path_parts = []
                for i, (x, y) in enumerate(points):
                    px = margin + x * chart_w
                    py = margin + (1 - y) * chart_h
                    if i == 0:
                        path_parts.append(f"M {px:.1f} {py:.1f}")
                    else:
                        path_parts.append(f"L {px:.1f} {py:.1f}")
                
                svg_parts.append(
                    f'<path d="{" ".join(path_parts)}" stroke="#4CAF50" stroke-width="2" fill="none" opacity="0.5"/>'
                )
            
            # Axes
            svg_parts.append(f'<line x1="{margin}" y1="{margin + chart_h}" x2="{width - margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            
            # Labels
            svg_parts.append(f'<text x="{width/2}" y="{height - 5}" text-anchor="middle">Iteration</text>')
            svg_parts.append(f'<text x="15" y="{margin + chart_h/2}" text-anchor="middle" transform="rotate(-90 15 {margin + chart_h/2})">Accuracy %</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            self.last_image_bytes = svg_str.encode('utf-8')
            logger.debug("Degradation chart SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating degradation chart: {e}")
            return b''

    def calculate_recovery_rate(self, recovery_data: List[float]) -> Optional[float]:
        """
        Calculate chat recovery rate trend (average of recovery percentages).

        Args:
            recovery_data: List of recovery percentages

        Returns:
            Average recovery rate or None
        """
        try:
            if not recovery_data:
                return 0.0
            
            avg_recovery = sum(recovery_data) / len(recovery_data)
            logger.debug(f"Recovery rate: {avg_recovery:.2f}%")
            return avg_recovery
        except Exception as e:
            logger.error(f"Error calculating recovery rate: {e}")
            return None

    def get_trend_summary(self) -> Dict[str, float]:
        """
        Get summary of trend statistics.

        Returns:
            Dictionary with trend metrics (mean, std_dev, min, max, count, degradation, anomaly_count)
        """
        try:
            if not self.accuracy_data:
                return {}
            
            summary = {
                'mean': statistics.mean(self.accuracy_data),
                'std_dev': statistics.stdev(self.accuracy_data) if len(self.accuracy_data) > 1 else 0.0,
                'min': min(self.accuracy_data),
                'max': max(self.accuracy_data),
                'count': len(self.accuracy_data),
                'degradation': self.calculate_degradation() or 0.0,
                'anomaly_count': len(self.detect_anomalies()),
            }
            
            logger.debug(f"Trend summary: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error getting trend summary: {e}")
            return {}

    def _generate_empty_svg(self, width: int = 1000, height: int = 400) -> str:
        """Generate empty placeholder SVG."""
        return (
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="{height}" fill="#f0f0f0"/>'
            f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#999">No data</text>'
            f'</svg>'
        )

    def save_image(self, output_path: str) -> bool:
        """
        Save trend analysis image to file.

        Args:
            output_path: Path to save file

        Returns:
            True if successful
        """
        try:
            if not self.last_image_bytes:
                self.generate_degradation_chart_image()
            
            with open(output_path, 'wb') as f:
                f.write(self.last_image_bytes)
            
            logger.info(f"Trend analysis chart saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving trend analysis image: {e}")
            return False


__all__ = ['TrendAnalysis']
