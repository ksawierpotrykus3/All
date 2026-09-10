"""
Variant comparison visualization module.
Compares metrics across different variants with HTML table and SVG chart.
"""
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class Comparisons:
    """
    Variant comparison visualization.
    """

    def __init__(self):
        """Initialize Comparisons."""
        self.variants: Dict[str, Dict[str, Any]] = {}
        self.last_image_bytes = None

    def add_variant_data(self, variant_name: str, data: Dict[str, Any]) -> bool:
        """
        Add variant comparison data.

        Args:
            variant_name: Variant identifier
            data: Variant metrics dictionary

        Returns:
            True if successful
        """
        try:
            self.variants[variant_name] = data
            logger.debug(f"Variant '{variant_name}' data added")
            return True
        except Exception as e:
            logger.error(f"Error adding variant data: {e}")
            return False

    def generate_comparison_table(self) -> str:
        """
        Generate comparison table HTML.

        Returns:
            HTML table string
        """
        try:
            if not self.variants:
                return '<p>No variant data to compare</p>'
            
            # Build HTML table
            html_parts = ['<table class="comparison-table" border="1" style="border-collapse: collapse; width: 100%; margin: 10px 0;">']
            html_parts.append('<tr style="background-color: #f0f0f0;">')
            html_parts.append('<th style="border: 1px solid #ccc; padding: 10px; text-align: left;"><strong>Metric</strong></th>')
            
            # Header with variant names
            variant_names = list(self.variants.keys())
            for variant_name in variant_names:
                html_parts.append(f'<th style="border: 1px solid #ccc; padding: 10px; text-align: center;"><strong>{variant_name}</strong></th>')
            
            # Delta columns if 2 variants
            if len(variant_names) == 2:
                html_parts.append('<th style="border: 1px solid #ccc; padding: 10px; text-align: center;"><strong>Delta (A-B)</strong></th>')
                html_parts.append('<th style="border: 1px solid #ccc; padding: 10px; text-align: center;"><strong>% Diff</strong></th>')
            
            html_parts.append('</tr>')
            
            # Collect all metric keys
            all_metrics = set()
            for data in self.variants.values():
                all_metrics.update(data.keys())
            
            # Rows with metrics
            for metric in sorted(all_metrics):
                html_parts.append(f'<tr>')
                html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px;"><strong>{metric}</strong></td>')
                
                values = []
                for variant_name in variant_names:
                    value = self.variants[variant_name].get(metric, None)
                    if value is not None:
                        if isinstance(value, float):
                            formatted = f'{value:.2f}'
                        else:
                            formatted = str(value)
                        values.append((variant_name, value, formatted))
                        html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px; text-align: right;">{formatted}</td>')
                    else:
                        html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px; text-align: right;">-</td>')
                
                # Delta columns
                if len(variant_names) == 2 and len(values) == 2:
                    try:
                        val_a = float(values[0][1])
                        val_b = float(values[1][1])
                        delta = val_a - val_b
                        pct_diff = (delta / val_b * 100) if val_b != 0 else 0
                        
                        delta_color = '#d4edda' if delta >= 0 else '#f8d7da'
                        html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px; text-align: right; background-color: {delta_color};">{delta:+.2f}</td>')
                        html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px; text-align: right; background-color: {delta_color};">{pct_diff:+.1f}%</td>')
                    except (ValueError, ZeroDivisionError):
                        html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px;">-</td>')
                        html_parts.append(f'<td style="border: 1px solid #ccc; padding: 8px;">-</td>')
                
                html_parts.append(f'</tr>')
            
            html_parts.append('</table>')
            
            logger.debug("Comparison table HTML generated")
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating comparison table: {e}")
            return f'<p>Error: {e}</p>'

    def generate_comparison_chart_image(self, width: int = 1000, height: int = 600) -> bytes:
        """
        Generate comparison chart as SVG bar chart.

        Args:
            width: Image width
            height: Image height

        Returns:
            SVG bytes
        """
        try:
            if not self.variants:
                return self._generate_empty_svg(width, height).encode('utf-8')
            
            # Extract numeric metrics
            variant_names = list(self.variants.keys())
            
            # Find all numeric metrics
            numeric_metrics = {}
            for variant_name, data in self.variants.items():
                for key, value in data.items():
                    if isinstance(value, (int, float)):
                        if key not in numeric_metrics:
                            numeric_metrics[key] = {}
                        numeric_metrics[key][variant_name] = value
            
            if not numeric_metrics:
                return self._generate_empty_svg(width, height).encode('utf-8')
            
            # Take first 4 metrics for chart
            metrics_to_plot = list(numeric_metrics.keys())[:4]
            
            # Build SVG bar chart
            margin = 60
            chart_w = width - 2 * margin
            chart_h = height - 2 * margin
            
            bar_w = chart_w / (len(metrics_to_plot) * (len(variant_names) + 1))
            
            svg_parts = [
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                '<style>text { font-family: Arial; font-size: 11px; }</style>',
                f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="black" stroke-width="1"/>',
            ]
            
            colors = ['#1976D2', '#388E3C', '#F57C00']
            max_value = max(
                max(values.values()) for values in numeric_metrics.values() if values
            )
            if max_value == 0:
                max_value = 1
            
            # Draw bars
            x_pos = margin + 20
            for metric_idx, metric in enumerate(metrics_to_plot):
                metric_values = numeric_metrics[metric]
                
                for var_idx, variant_name in enumerate(variant_names):
                    if variant_name in metric_values:
                        value = metric_values[variant_name]
                        bar_height = (value / max_value) * chart_h
                        y = margin + chart_h - bar_height
                        
                        svg_parts.append(
                            f'<rect x="{x_pos:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                            f'height="{bar_height:.1f}" fill="{colors[var_idx % len(colors)]}" stroke="black" stroke-width="0.5"/>'
                        )
                    
                    x_pos += bar_w + 2
                
                x_pos += 10
            
            # Axes
            svg_parts.append(f'<line x1="{margin}" y1="{margin + chart_h}" x2="{width - margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{margin + chart_h}" stroke="black" stroke-width="2"/>')
            
            # Legend
            legend_y = height - 30
            for var_idx, variant_name in enumerate(variant_names):
                x = margin + var_idx * 100
                color = colors[var_idx % len(colors)]
                svg_parts.append(f'<rect x="{x}" y="{legend_y}" width="15" height="15" fill="{color}" stroke="black" stroke-width="0.5"/>')
                svg_parts.append(f'<text x="{x + 20}" y="{legend_y + 12}">{variant_name}</text>')
            
            svg_parts.append('</svg>')
            
            svg_str = ''.join(svg_parts)
            self.last_image_bytes = svg_str.encode('utf-8')
            logger.debug("Comparison chart SVG generated")
            return svg_str.encode('utf-8')
        except Exception as e:
            logger.error(f"Error generating comparison chart: {e}")
            return b''

    def _generate_empty_svg(self, width: int = 1000, height: int = 600) -> str:
        """Generate empty placeholder SVG."""
        return (
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="{height}" fill="#f0f0f0"/>'
            f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#999">No data</text>'
            f'</svg>'
        )

    def save_image(self, output_path: str) -> bool:
        """
        Save comparison chart image to file.

        Args:
            output_path: Path to save file

        Returns:
            True if successful
        """
        try:
            if not self.last_image_bytes:
                self.generate_comparison_chart_image()
            
            with open(output_path, 'wb') as f:
                f.write(self.last_image_bytes)
            
            logger.info(f"Comparison chart saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving comparison chart: {e}")
            return False


__all__ = ['Comparisons']
