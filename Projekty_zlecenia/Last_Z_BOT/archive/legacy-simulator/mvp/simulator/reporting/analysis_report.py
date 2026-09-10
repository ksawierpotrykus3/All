"""
Analysis Report facade combining all visualizations.
Integrates Heatmaps, Timelines, Comparisons, and TrendAnalysis
into a comprehensive HTML report.
"""
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from .report_generator import ReportGenerator
from .heatmaps import Heatmaps
from .timelines import Timelines
from .comparisons import Comparisons
from .trend_analysis import TrendAnalysis

logger = logging.getLogger(__name__)


class AnalysisReport:
    """
    Facade combining all visualization components into a comprehensive report.
    """

    def __init__(self, session_id: str):
        """
        Initialize AnalysisReport.

        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self.report_generator = ReportGenerator(session_id)
        
        # Visualization components
        self.heatmaps = Heatmaps()
        self.timelines = Timelines()
        self.comparisons = Comparisons()
        self.trend_analysis = TrendAnalysis()
        
        logger.debug(f"AnalysisReport initialized for session: {session_id}")

    def add_session_data(self, session_summary: Dict[str, Any]) -> bool:
        """
        Add session summary data to report.

        Args:
            session_summary: Session summary dictionary

        Returns:
            True if successful
        """
        try:
            self.report_generator.add_session_summary(session_summary)
            logger.debug("Session data added to report")
            return True
        except Exception as e:
            logger.error(f"Error adding session data: {e}")
            return False

    def add_iteration_data(self, iteration: int, data: Dict[str, Any]) -> bool:
        """
        Add iteration data to report.

        Args:
            iteration: Iteration number
            data: Iteration data dictionary

        Returns:
            True if successful
        """
        try:
            self.report_generator.add_iteration_data(iteration, data)
            logger.debug(f"Iteration {iteration} data added to report")
            return True
        except Exception as e:
            logger.error(f"Error adding iteration data: {e}")
            return False

    def add_click_positions(self, clicks: list) -> bool:
        """
        Add click position data for heatmap.

        Args:
            clicks: List of (x, y) tuples

        Returns:
            True if successful
        """
        try:
            return self.heatmaps.add_click_positions(clicks)
        except Exception as e:
            logger.error(f"Error adding click positions: {e}")
            return False

    def add_timeline_events(self, events: list) -> bool:
        """
        Add timeline events.

        Args:
            events: List of phase events

        Returns:
            True if successful
        """
        try:
            for event in events:
                iteration = event.get('iteration')
                phase = event.get('phase')
                start_ms = event.get('start_ms')
                end_ms = event.get('end_ms')
                
                self.timelines.add_phase_event(iteration, phase, start_ms, end_ms)
            
            logger.debug(f"Added {len(events)} timeline events")
            return True
        except Exception as e:
            logger.error(f"Error adding timeline events: {e}")
            return False

    def add_variant_comparison(self, variant_name: str, data: Dict[str, Any]) -> bool:
        """
        Add variant comparison data.

        Args:
            variant_name: Variant identifier
            data: Variant metrics

        Returns:
            True if successful
        """
        try:
            return self.comparisons.add_variant_data(variant_name, data)
        except Exception as e:
            logger.error(f"Error adding variant comparison: {e}")
            return False

    def add_accuracy_trend(self, accuracy_data: list) -> bool:
        """
        Add accuracy trend data for trend analysis.

        Args:
            accuracy_data: List of accuracy percentages

        Returns:
            True if successful
        """
        try:
            return self.trend_analysis.add_accuracy_data(accuracy_data)
        except Exception as e:
            logger.error(f"Error adding accuracy trend: {e}")
            return False

    def generate_full_html_report(self) -> str:
        """
        Generate full HTML report with all visualizations.

        Returns:
            HTML string with all sections
        """
        try:
            html_parts = []
            
            # Start with base HTML structure
            html_parts.append('<!DOCTYPE html>')
            html_parts.append('<html>')
            html_parts.append('<head>')
            html_parts.append('<meta charset="utf-8">')
            html_parts.append(f'<title>Analysis Report - {self.session_id}</title>')
            html_parts.append('<style>')
            html_parts.append(self._get_css_styles())
            html_parts.append('</style>')
            html_parts.append('</head>')
            html_parts.append('<body>')
            
            # Title
            html_parts.append('<h1>Extended Game Simulator - Comprehensive Analysis Report</h1>')
            html_parts.append(f'<p class="subtitle">Session ID: {self.session_id}</p>')
            
            # Table of contents
            html_parts.append('<div class="toc">')
            html_parts.append('<h2>Contents</h2>')
            html_parts.append('<ul>')
            html_parts.append('<li><a href="#summary">Session Summary</a></li>')
            html_parts.append('<li><a href="#heatmaps">Click Position & OCR Confidence</a></li>')
            html_parts.append('<li><a href="#timelines">Timelines & Trends</a></li>')
            html_parts.append('<li><a href="#comparisons">Variant Comparisons</a></li>')
            html_parts.append('<li><a href="#trends">Trend Analysis & Anomalies</a></li>')
            html_parts.append('</ul>')
            html_parts.append('</div>')
            
            # Session Summary Section
            html_parts.append('<section id="summary" class="section">')
            html_parts.append('<h2>Session Summary</h2>')
            summary_table = self._generate_summary_section()
            html_parts.append(summary_table)
            html_parts.append('</section>')
            
            # Heatmaps Section
            html_parts.append('<section id="heatmaps" class="section">')
            html_parts.append('<h2>Click Position & OCR Confidence Heatmaps</h2>')
            heatmap_html = self._generate_heatmaps_section()
            html_parts.append(heatmap_html)
            html_parts.append('</section>')
            
            # Timelines Section
            html_parts.append('<section id="timelines" class="section">')
            html_parts.append('<h2>Phase Timelines & Performance Trends</h2>')
            timeline_html = self._generate_timelines_section()
            html_parts.append(timeline_html)
            html_parts.append('</section>')
            
            # Comparisons Section
            html_parts.append('<section id="comparisons" class="section">')
            html_parts.append('<h2>Variant Comparisons</h2>')
            comparison_html = self._generate_comparisons_section()
            html_parts.append(comparison_html)
            html_parts.append('</section>')
            
            # Trend Analysis Section
            html_parts.append('<section id="trends" class="section">')
            html_parts.append('<h2>Trend Analysis & Anomaly Detection</h2>')
            trend_html = self._generate_trend_analysis_section()
            html_parts.append(trend_html)
            html_parts.append('</section>')
            
            # Footer
            html_parts.append('<hr>')
            html_parts.append('<footer class="footer">')
            html_parts.append('<p>Generated by Extended Game Simulator Framework</p>')
            html_parts.append('</footer>')
            
            html_parts.append('</body>')
            html_parts.append('</html>')
            
            logger.debug("Full HTML report generated")
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating full HTML report: {e}")
            return '<html><body><p>Error generating report</p></body></html>'

    def _generate_summary_section(self) -> str:
        """Generate HTML for session summary section."""
        try:
            summary = self.report_generator.get_session_summary()
            
            if not summary:
                return '<p>No summary data available</p>'
            
            html_parts = ['<div class="summary-box">']
            html_parts.append('<table class="metrics-table">')
            
            for key, value in summary.items():
                if isinstance(value, float):
                    formatted = f'{value:.2f}'
                else:
                    formatted = str(value)
                html_parts.append(f'<tr><td class="metric-name">{key}</td><td class="metric-value">{formatted}</td></tr>')
            
            html_parts.append('</table>')
            html_parts.append('</div>')
            
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating summary section: {e}")
            return f'<p>Error: {e}</p>'

    def _generate_heatmaps_section(self) -> str:
        """Generate HTML for heatmaps section."""
        try:
            html_parts = []
            html_parts.append('<div class="heatmaps-container">')
            html_parts.append('<p>Click Position Heatmap: Shows distribution of bot clicks across screen coordinates.</p>')
            html_parts.append('<div class="placeholder-image">[Click Position Heatmap]</div>')
            html_parts.append('<p>OCR Confidence Heatmap: Displays OCR confidence levels across variants.</p>')
            html_parts.append('<div class="placeholder-image">[OCR Confidence Heatmap]</div>')
            html_parts.append('</div>')
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating heatmaps section: {e}")
            return f'<p>Error: {e}</p>'

    def _generate_timelines_section(self) -> str:
        """Generate HTML for timelines section."""
        try:
            html_parts = []
            html_parts.append('<div class="timelines-container">')
            html_parts.append('<p>Phase Timeline: Visualization of all iterations with phase breakdown.</p>')
            html_parts.append('<div class="placeholder-image">[Phase Timeline]</div>')
            html_parts.append('<p>CPU Usage Trend: CPU spike patterns across iterations.</p>')
            html_parts.append('<div class="placeholder-image">[CPU Trend]</div>')
            html_parts.append('<p>Accuracy Curve: Accuracy performance over time showing degradation.</p>')
            html_parts.append('<div class="placeholder-image">[Accuracy Curve]</div>')
            html_parts.append('</div>')
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating timelines section: {e}")
            return f'<p>Error: {e}</p>'

    def _generate_comparisons_section(self) -> str:
        """Generate HTML for comparisons section."""
        try:
            html_parts = []
            html_parts.append('<div class="comparisons-container">')
            
            # Generate comparison table
            table = self.comparisons.generate_comparison_table()
            html_parts.append(table)
            
            html_parts.append('<p>Variant comparison chart:</p>')
            html_parts.append('<div class="placeholder-image">[Comparison Chart]</div>')
            
            html_parts.append('</div>')
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating comparisons section: {e}")
            return f'<p>Error: {e}</p>'

    def _generate_trend_analysis_section(self) -> str:
        """Generate HTML for trend analysis section."""
        try:
            html_parts = []
            html_parts.append('<div class="trend-analysis-container">')
            
            # Get trend summary
            summary = self.trend_analysis.get_trend_summary()
            if summary:
                html_parts.append('<h3>Trend Summary</h3>')
                html_parts.append('<table class="metrics-table">')
                for key, value in summary.items():
                    if isinstance(value, float):
                        formatted = f'{value:.2f}'
                    else:
                        formatted = str(value)
                    html_parts.append(f'<tr><td>{key}</td><td>{formatted}</td></tr>')
                html_parts.append('</table>')
            
            # Degradation analysis
            degradation = self.trend_analysis.calculate_degradation()
            if degradation is not None:
                html_parts.append(f'<h3>Accuracy Degradation</h3>')
                html_parts.append(f'<p>Degradation: {degradation:.2f}% per 10 iterations</p>')
            
            # Anomalies
            anomalies = self.trend_analysis.detect_anomalies()
            if anomalies:
                html_parts.append('<h3>Detected Anomalies</h3>')
                html_parts.append('<ul>')
                for idx, value in anomalies[:10]:  # Show first 10
                    html_parts.append(f'<li>Iteration {idx}: {value:.2f}%</li>')
                html_parts.append('</ul>')
            
            html_parts.append('<p>Degradation Chart:</p>')
            html_parts.append('<div class="placeholder-image">[Degradation Chart]</div>')
            
            html_parts.append('</div>')
            return '\n'.join(html_parts)
        except Exception as e:
            logger.error(f"Error generating trend analysis section: {e}")
            return f'<p>Error: {e}</p>'

    def _get_css_styles(self) -> str:
        """Get comprehensive CSS styles for full report."""
        return """
        * {
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f0f2f5;
            color: #333;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }
        
        h1 {
            color: #1976d2;
            text-align: center;
            border-bottom: 3px solid #1976d2;
            padding-bottom: 15px;
            margin-bottom: 5px;
        }
        
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
        }
        
        h2 {
            color: #1976d2;
            border-left: 4px solid #1976d2;
            padding-left: 15px;
            margin-top: 40px;
            margin-bottom: 20px;
        }
        
        h3 {
            color: #424242;
            margin-top: 20px;
            margin-bottom: 15px;
        }
        
        .toc {
            background-color: #e3f2fd;
            border-left: 4px solid #1976d2;
            padding: 20px;
            border-radius: 4px;
            margin-bottom: 40px;
        }
        
        .toc ul {
            list-style-type: none;
            padding-left: 0;
        }
        
        .toc li {
            margin: 8px 0;
        }
        
        .toc a {
            color: #1976d2;
            text-decoration: none;
            font-weight: 500;
        }
        
        .toc a:hover {
            text-decoration: underline;
        }
        
        section {
            background-color: white;
            padding: 25px;
            margin-bottom: 30px;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .summary-box {
            background-color: #fafafa;
            padding: 20px;
            border-radius: 4px;
            border-left: 4px solid #4caf50;
        }
        
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        .metrics-table tr {
            border-bottom: 1px solid #e0e0e0;
        }
        
        .metrics-table tr:hover {
            background-color: #f5f5f5;
        }
        
        .metrics-table td {
            padding: 12px;
            text-align: left;
        }
        
        .metric-name {
            font-weight: 600;
            width: 40%;
            color: #1976d2;
        }
        
        .metric-value {
            color: #333;
            font-family: 'Courier New', monospace;
        }
        
        .comparison-table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        .comparison-table th,
        .comparison-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
            border-right: 1px solid #e0e0e0;
        }
        
        .comparison-table th {
            background-color: #1976d2;
            color: white;
            font-weight: 600;
        }
        
        .comparison-table tr:hover {
            background-color: #f9f9f9;
        }
        
        .placeholder-image {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: 2px dashed #1976d2;
            border-radius: 4px;
            padding: 40px;
            text-align: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
            margin: 20px 0;
            min-height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .heatmaps-container,
        .timelines-container,
        .comparisons-container,
        .trend-analysis-container {
            background-color: #fafafa;
            padding: 15px;
            border-radius: 4px;
        }
        
        footer {
            text-align: center;
            font-size: 12px;
            color: #999;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }
        
        ul {
            line-height: 1.8;
        }
        
        p {
            margin: 10px 0;
        }
        """

    def save_full_report(self, output_path: str) -> bool:
        """
        Save full HTML report to file.

        Args:
            output_path: Path to save HTML file

        Returns:
            True if successful
        """
        try:
            html = self.generate_full_html_report()
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"Full report saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving full report: {e}")
            return False


__all__ = ['AnalysisReport']
