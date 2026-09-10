"""
Timeline visualization module.
Generates phase timelines, CPU/RAM trends, accuracy curves with SVG and HTML.
"""
from typing import List, Dict, Tuple, Optional
import logging
import statistics

logger = logging.getLogger(__name__)


def _get_trend_line_svg(points: List[Tuple[float, float]], width: float, height: float, margin: float = 40) -> str:
    """
    Generate SVG path for trend line from points.
    
    Args:
        points: List of (x, y) normalized points (0-1)
        width: SVG width
        height: SVG height
        margin: Margin for axes
    
    Returns:
        SVG path string
    """
    if len(points) < 2:
        return ""
    
    chart_w = width - 2 * margin
    chart_h = height - 2 * margin
    
    path_parts = []
    for i, (x, y) in enumerate(points):
        px = margin + x * chart_w
        py = margin + chart_h - (y * chart_h)
        
        if i == 0:
            path_parts.append(f"M {px:.1f} {py:.1f}")
        else:
            path_parts.append(f"L {px:.1f} {py:.1f}")
    
    return " ".join(path_parts)


class Timelines:
    """
    Timeline visualization for simulator analysis.
    """

    def __init__(self):
        """Initialize Timelines."""
        self.events: List[Dict] = []
        self.cpu_data: Dict[int, float] = {}
        self.accuracy_data: Dict[int, float] = {}
        self.last_image_bytes = None

    def add_phase_event(
        self, iteration: int, phase: str, start_ms: int, end_ms: int
    ) -> bool:
        """
        Add phase event to timeline.

        Args:
            iteration: Iteration number
            phase: Phase name
            start_ms: Start time (ms)
            end_ms: End time (ms)

        Returns:
            True if successful
        """
        try:
            event = {
                'iteration': iteration,
                'phase': phase,
                'start_ms': start_ms,
                'end_ms': end_ms,
                'duration_ms': end_ms - start_ms,
            }
            self.events.append(event)
            logger.debug(f"Phase event added: {phase}")
            return True
        except Exception as e:
            logger.error(f"Error adding phase event: {e}")
            return False

    def generate_phase_timeline_image(self, width: int = 1000, height: int = 400) -> bytes:
        """
        Generate phase timeline visualization as SVG.

        Args:
            width: Image width
            height: Image height

        Returns:
            SVG bytes
        """
        try:
            if not self.events:
                return self._generate_empty_svg(width, height).encode('utf-8')
            
            # Group by iteration
            by_iteration = {}
            for evt in self.events:
                it = evt['iteration']
                if it not in by_iteration:
                    by_iteration[it] = []
                by_iteration[it].append(evt)
            
            # Phase colors
            phase_colors = {
                'CHAT': '#4CAF50',
                'ALERT': '#FFC107',
                'TREASURE': '#2196F3',
                'CLICK': '#FF9800',
                'SCAN': '#9C27B0',
                'SETUP': '#9E9E9E',
            }
            
            # Build SVG
            margin = 40
            iterations = sorted(by_iteration.keys())
            max_iterations = len(iterations)
            bar_height = 30
            total_height = margin * 2 + max_iterations * (bar_height + 10)
            
            svg_parts = [
                f'<svg width="{width}" height="{total_height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 11px; }</style>',
            ]
            
            # Find max time
            max_time = max([evt['end_ms'] for evt in self.events])
            if max_time == 0:
                max_time = 1
            
            chart_w = width - 2 * margin
            
            # Draw bars per iteration
            for idx, iteration in enumerate(iterations):
                events = by_iteration[iteration]
                y = margin + idx * (bar_height + 10)
                
                # Iteration label
                svg_parts.append(
                    f'<text x="5" y="{y + bar_height/2 + 4}" font-size="10">{iteration}</text>'
                )
                
                # Phases
                for evt in events:
                    x_start = margin + (evt['start_ms'] / max_time) * chart_w
                    x_end = margin + (evt['end_ms'] / max_time) * chart_w
                    color = phase_colors.get(evt['phase'], '#CCCCCC')
                    
                    svg_parts.append(
                        f'<rect x="{x_start:.1f}" y="{y:.1f}" width="{max(1, x_end - x_start):.1f}" '
                        f'height="{bar_height:.1f}" fill="{color}" stroke="black" stroke-width="1"/>'
                    )
                    
                    # Phase label
                    if x_end - x_start > 30:
                        svg_parts.append(
                            f'<text x="{(x_start + x_end) / 2:.1f}" y="{y + bar_height/2 + 4}" '
                            f'text-anchor="middle" font-size="9" fill="white">{evt["phase"]}</text>'
                        )
            
            # Axes
            svg_parts.append(f'<line x1="{margin}" y1="{margin - 10}" x2="{width - margin}" y2="{margin - 10}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<text x="{width/2}" y="30" text-anchor="middle" font-size="12">Phase Timeline (ms)</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            logger.debug("Phase timeline SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating phase timeline: {e}")
            return b''

    def generate_cpu_trend_image(self, cpu_data: Dict[int, float]) -> bytes:
        """
        Generate CPU usage trend timeline as SVG.

        Args:
            cpu_data: Dictionary {iteration: cpu_percent}

        Returns:
            SVG bytes
        """
        try:
            if not cpu_data:
                return self._generate_empty_svg().encode('utf-8')
            
            self.cpu_data = cpu_data
            
            # Normalize points
            iterations = sorted(cpu_data.keys())
            values = [cpu_data[it] for it in iterations]
            max_cpu = max(values) if values else 100
            min_cpu = min(values) if values else 0
            
            points = []
            for i, it in enumerate(iterations):
                x = i / (len(iterations) - 1) if len(iterations) > 1 else 0.5
                y = (cpu_data[it] - min_cpu) / (max_cpu - min_cpu) if max_cpu > min_cpu else 0.5
                points.append((x, y))
            
            # Build SVG
            width, height = 1000, 400
            margin = 50
            
            svg_parts = [
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 11px; }</style>',
                f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="black" stroke-width="1"/>',
            ]
            
            # Trend line
            path = _get_trend_line_svg(points, width, height, margin)
            if path:
                svg_parts.append(
                    f'<path d="{path}" stroke="#1976D2" stroke-width="2" fill="none"/>'
                )
            
            # Points
            for x, y in points:
                px = margin + x * (width - 2 * margin)
                py = margin + (1 - y) * (height - 2 * margin)
                svg_parts.append(
                    f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#1976D2" stroke="black" stroke-width="1"/>'
                )
            
            # Axes
            chart_w = width - 2 * margin
            chart_h = height - 2 * margin
            svg_parts.append(f'<line x1="{margin}" y1="{margin + chart_h}" x2="{width - margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            
            # Labels
            svg_parts.append(f'<text x="{width/2}" y="{height - 5}" text-anchor="middle">Iteration</text>')
            svg_parts.append(f'<text x="15" y="{margin + chart_h/2}" text-anchor="middle" transform="rotate(-90 15 {margin + chart_h/2})">CPU %</text>')
            
            # Y-axis values
            svg_parts.append(f'<text x="{margin - 30}" y="{margin + chart_h + 5}">{min_cpu:.0f}%</text>')
            svg_parts.append(f'<text x="{margin - 30}" y="{margin + 5}">{max_cpu:.0f}%</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            self.last_image_bytes = svg_str.encode('utf-8')
            logger.debug("CPU trend SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating CPU trend: {e}")
            return b''

    def generate_accuracy_curve_image(self, accuracy_data: Dict[int, float]) -> bytes:
        """
        Generate accuracy curve timeline as SVG.

        Args:
            accuracy_data: Dictionary {iteration: accuracy_percent}

        Returns:
            SVG bytes
        """
        try:
            if not accuracy_data:
                return self._generate_empty_svg().encode('utf-8')
            
            self.accuracy_data = accuracy_data
            
            # Normalize points
            iterations = sorted(accuracy_data.keys())
            values = [accuracy_data[it] for it in iterations]
            
            points = []
            for i, it in enumerate(iterations):
                x = i / (len(iterations) - 1) if len(iterations) > 1 else 0.5
                y = accuracy_data[it] / 100.0  # Normalize to 0-1
                points.append((x, y))
            
            # Build SVG
            width, height = 1000, 400
            margin = 50
            
            svg_parts = [
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 11px; }</style>',
                f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="black" stroke-width="1"/>',
            ]
            
            # Trend line
            path = _get_trend_line_svg(points, width, height, margin)
            if path:
                svg_parts.append(
                    f'<path d="{path}" stroke="#4CAF50" stroke-width="2" fill="none"/>'
                )
            
            # Points
            for x, y in points:
                px = margin + x * (width - 2 * margin)
                py = margin + (1 - y) * (height - 2 * margin)
                svg_parts.append(
                    f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#4CAF50" stroke="black" stroke-width="1"/>'
                )
            
            # Axes
            chart_w = width - 2 * margin
            chart_h = height - 2 * margin
            svg_parts.append(f'<line x1="{margin}" y1="{margin + chart_h}" x2="{width - margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            
            # Labels
            svg_parts.append(f'<text x="{width/2}" y="{height - 5}" text-anchor="middle">Iteration</text>')
            svg_parts.append(f'<text x="15" y="{margin + chart_h/2}" text-anchor="middle" transform="rotate(-90 15 {margin + chart_h/2})">Accuracy %</text>')
            
            # Y-axis values
            svg_parts.append(f'<text x="{margin - 20}" y="{margin + chart_h + 5}">0%</text>')
            svg_parts.append(f'<text x="{margin - 20}" y="{margin + 5}">100%</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            self.last_image_bytes = svg_str.encode('utf-8')
            logger.debug("Accuracy curve SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating accuracy curve: {e}")
            return b''

    def generate_ocr_confidence_trend(self, ocr_data: Dict[int, float]) -> bytes:
        """
        Generate OCR confidence trend as SVG.

        Args:
            ocr_data: Dictionary {iteration: ocr_confidence}

        Returns:
            SVG bytes
        """
        try:
            if not ocr_data:
                return self._generate_empty_svg().encode('utf-8')
            
            # Similar to accuracy curve
            return self.generate_accuracy_curve_image(
                {it: conf * 100 for it, conf in ocr_data.items()}
            )
        except Exception as e:
            logger.error(f"Error generating OCR trend: {e}")
            return b''

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
        Save timeline image to file.

        Args:
            output_path: Path to save file

        Returns:
            True if successful
        """
        try:
            if self.last_image_bytes is None:
                self.generate_phase_timeline_image()
            
            if self.last_image_bytes is None:
                # Fallback: generate phase timeline
                image_bytes = self.generate_phase_timeline_image()
                if not image_bytes:
                    return False
                self.last_image_bytes = image_bytes
            
            with open(output_path, 'wb') as f:
                f.write(self.last_image_bytes)
            
            logger.info(f"Timeline saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving timeline image: {e}")
            return False


__all__ = ['Timelines']
