"""
Heatmap visualization module.
Generates click position and OCR confidence heatmaps with HTML table and SVG rendering.
"""
import io
from typing import List, Dict, Tuple, Optional
import logging
import statistics

logger = logging.getLogger(__name__)


def _get_color_gradient(value: float, min_val: float = 0.0, max_val: float = 1.0) -> str:
    """
    Convert normalized value (0-1) to RGB hex color (blue -> red gradient).
    
    Args:
        value: Normalized value 0-1
        min_val: Minimum value for scaling
        max_val: Maximum value for scaling
    
    Returns:
        Hex color string #RRGGBB
    """
    # Normalize value
    if max_val == min_val:
        norm = 0.5
    else:
        norm = (value - min_val) / (max_val - min_val)
    
    norm = max(0.0, min(1.0, norm))  # Clamp 0-1
    
    # Blue (0, 0, 255) -> Red (255, 0, 0)
    r = int(255 * norm)
    b = int(255 * (1 - norm))
    g = 0
    
    return f"#{r:02x}{g:02x}{b:02x}"


class Heatmaps:
    """
    Heatmap visualization for simulator analysis.
    """

    def __init__(self):
        """Initialize Heatmaps."""
        self.click_positions: List[Tuple[int, int]] = []
        self.ocr_data: Dict[int, float] = {}
        self.last_image_bytes = None

    def add_click_positions(self, positions: List[Tuple[int, int]]) -> bool:
        """
        Add click positions for heatmap.

        Args:
            positions: List of (x, y) tuples

        Returns:
            True if successful
        """
        try:
            self.click_positions.extend(positions)
            logger.debug(f"Added {len(positions)} click positions")
            return True
        except Exception as e:
            logger.error(f"Error adding click positions: {e}")
            return False

    def generate_click_heatmap_image(self, width: int = 800, height: int = 600) -> bytes:
        """
        Generate click position heatmap as SVG.

        Args:
            width: Image width
            height: Image height

        Returns:
            SVG bytes
        """
        try:
            if not self.click_positions:
                return self._generate_empty_svg(width, height).encode('utf-8')
            
            # Build 2D grid (32x32 buckets for 1920x1080 resolution)
            grid_x, grid_y = 32, 32
            bucket_w = width / grid_x
            bucket_h = height / grid_y
            
            # Count clicks per bucket
            grid = [[0 for _ in range(grid_x)] for _ in range(grid_y)]
            for x, y in self.click_positions:
                # Normalize to grid
                bx = min(int(x / (1920 / grid_x)), grid_x - 1)
                by = min(int(y / (1080 / grid_y)), grid_y - 1)
                grid[by][bx] += 1
            
            # Find min/max for color scaling
            flat = [v for row in grid for v in row if v > 0]
            min_val = min(flat) if flat else 0
            max_val = max(flat) if flat else 1
            
            # Build SVG
            svg_parts = [
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 12px; }</style>',
            ]
            
            # Draw grid cells
            for by in range(grid_y):
                for bx in range(grid_x):
                    count = grid[by][bx]
                    x = bx * bucket_w
                    y = by * bucket_h
                    color = _get_color_gradient(count, min_val, max_val)
                    
                    svg_parts.append(
                        f'<rect x="{x:.1f}" y="{y:.1f}" width="{bucket_w:.1f}" '
                        f'height="{bucket_h:.1f}" fill="{color}" stroke="#ccc" stroke-width="0.5"/>'
                    )
            
            # Add axes
            svg_parts.append(f'<line x1="0" y1="{height}" x2="{width}" y2="{height}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<line x1="0" y1="0" x2="0" y2="{height}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<text x="10" y="{height - 10}">X</text>')
            svg_parts.append(f'<text x="-40" y="20" transform="rotate(-90)">Y</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            self.last_image_bytes = svg_str.encode('utf-8')
            logger.debug("Click heatmap SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating click heatmap: {e}")
            return b''

    def generate_ocr_confidence_heatmap(
        self, ocr_data: Dict[int, float], width: int = 800, height: int = 600
    ) -> bytes:
        """
        Generate OCR confidence heatmap as HTML table.

        Args:
            ocr_data: Dictionary {iteration: confidence}
            width: Image width (unused for table)
            height: Image height (unused for table)

        Returns:
            HTML bytes
        """
        try:
            self.ocr_data = ocr_data
            
            if not ocr_data:
                return b'<table><tr><td>No OCR data</td></tr></table>'
            
            # Build HTML table
            html_parts = [
                '<table class="ocr-heatmap" style="border-collapse: collapse; width: 100%;">',
                '<tr><th style="border: 1px solid #ccc; padding: 8px;">Iteration</th>'
                '<th style="border: 1px solid #ccc; padding: 8px;">OCR Confidence</th></tr>',
            ]
            
            min_conf = min(ocr_data.values()) if ocr_data else 0
            max_conf = max(ocr_data.values()) if ocr_data else 1
            
            for iteration in sorted(ocr_data.keys()):
                conf = ocr_data[iteration]
                color = _get_color_gradient(conf, min_conf, max_conf)
                
                html_parts.append(
                    f'<tr style="background-color: {color};">'
                    f'<td style="border: 1px solid #ccc; padding: 8px;">{iteration}</td>'
                    f'<td style="border: 1px solid #ccc; padding: 8px;">{conf:.3f}</td>'
                    f'</tr>'
                )
            
            html_parts.append('</table>')
            html_str = ''.join(html_parts)
            
            logger.debug("OCR confidence heatmap HTML generated")
            return html_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating OCR confidence heatmap: {e}")
            return b''

    def generate_latency_distribution_heatmap(self, latencies: List[float]) -> bytes:
        """
        Generate latency distribution heatmap (histogram) as SVG.

        Args:
            latencies: List of latency values in ms

        Returns:
            SVG bytes
        """
        try:
            if not latencies:
                return self._generate_empty_svg().encode('utf-8')
            
            # Create buckets (10 buckets from min to max)
            min_lat = min(latencies)
            max_lat = max(latencies)
            bucket_count = 10
            bucket_width = (max_lat - min_lat) / bucket_count if max_lat > min_lat else 1
            
            buckets = [0] * bucket_count
            for lat in latencies:
                bucket_idx = min(int((lat - min_lat) / bucket_width), bucket_count - 1)
                buckets[bucket_idx] += 1
            
            max_count = max(buckets) if buckets else 1
            
            # Build SVG bar chart
            width, height = 800, 400
            margin = 60
            chart_w = width - 2 * margin
            chart_h = height - 2 * margin
            bar_w = chart_w / bucket_count
            
            svg_parts = [
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 11px; }</style>',
            ]
            
            # Draw bars
            for i, count in enumerate(buckets):
                x = margin + i * bar_w
                bar_height = (count / max_count) * chart_h if max_count > 0 else 0
                y = margin + chart_h - bar_height
                
                svg_parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 2:.1f}" '
                    f'height="{bar_height:.1f}" fill="#4169E1" stroke="black" stroke-width="0.5"/>'
                )
                
                # Label
                bucket_start = min_lat + i * bucket_width
                bucket_end = bucket_start + bucket_width
                svg_parts.append(
                    f'<text x="{x + bar_w/2:.1f}" y="{height - 10:.1f}" text-anchor="middle">'
                    f'{bucket_start:.0f}-{bucket_end:.0f}</text>'
                )
            
            # Axes
            svg_parts.append(f'<line x1="{margin}" y1="{margin + chart_h}" x2="{width - margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            
            svg_parts.append(f'<text x="{width/2}" y="{height - 5}" text-anchor="middle">Latency (ms)</text>')
            svg_parts.append(f'<text x="15" y="{margin + chart_h/2}" text-anchor="middle" transform="rotate(-90 15 {margin + chart_h/2})">Count</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            logger.debug("Latency distribution heatmap SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating latency heatmap: {e}")
            return b''

    def _generate_empty_svg(self, width: int = 800, height: int = 600) -> str:
        """Generate empty placeholder SVG."""
        return (
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="{height}" fill="#f0f0f0"/>'
            f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#999">No data</text>'
            f'</svg>'
        )

    def save_image(self, output_path: str) -> bool:
        """
        Save heatmap image to file.

        Args:
            output_path: Path to save file

        Returns:
            True if successful
        """
        try:
            if not self.last_image_bytes:
                self.generate_click_heatmap_image()
            
            with open(output_path, 'wb') as f:
                f.write(self.last_image_bytes)
            
            logger.info(f"Heatmap saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving heatmap image: {e}")
            return False


__all__ = ['Heatmaps']
