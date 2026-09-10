"""
Full Report Integration class combining all visualization and reporting components.
Provides a unified interface for generating comprehensive analysis reports.
"""
from typing import Dict, Any, Optional, List, Tuple
import logging
import json
from pathlib import Path
from datetime import datetime

from .report_generator import ReportGenerator
from .heatmaps import Heatmaps
from .timelines import Timelines
from .comparisons import Comparisons
from .trend_analysis import TrendAnalysis
from .analysis_report import AnalysisReport

logger = logging.getLogger(__name__)


class FullReportGenerator:
    """
    Full Report Generator combining all visualization components.
    Provides unified interface for comprehensive report generation.
    """

    def __init__(self, session_id: str, title: str = "Extended Game Simulator Report"):
        """
        Initialize FullReportGenerator.

        Args:
            session_id: Session identifier
            title: Report title (default: "Extended Game Simulator Report")
        """
        self.session_id = session_id
        self.title = title
        self.created_at = datetime.now().isoformat()
        
        # Initialize analysis report (which internally manages all components)
        self.analysis_report = AnalysisReport(session_id)
        
        # Direct access to components for advanced usage
        self.report_generator = self.analysis_report.report_generator
        self.heatmaps = self.analysis_report.heatmaps
        self.timelines = self.analysis_report.timelines
        self.comparisons = self.analysis_report.comparisons
        self.trend_analysis = self.analysis_report.trend_analysis
        
        logger.debug(f"FullReportGenerator initialized for session: {session_id}")

    def add_simulation_data(
        self,
        metrics_dict: Dict[str, Any],
        events: Optional[List[Dict[str, Any]]] = None,
        iterations: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Ingest all data at once.

        Args:
            metrics_dict: Session metrics dictionary
            events: List of phase timeline events
            iterations: List of iteration data dictionaries

        Returns:
            True if successful
        """
        try:
            # Add session data
            self.analysis_report.add_session_data(metrics_dict)
            
            # Add timeline events
            if events:
                self.analysis_report.add_timeline_events(events)
            
            # Add iteration data
            if iterations:
                for idx, iteration_data in enumerate(iterations):
                    self.analysis_report.add_iteration_data(idx, iteration_data)
            
            logger.debug(f"Added simulation data: {len(iterations or [])} iterations, {len(events or [])} events")
            return True
        except Exception as e:
            logger.error(f"Error adding simulation data: {e}")
            return False

    def generate_full_html_report(self) -> str:
        """
        Generate complete HTML report with all embedded visualizations.

        Returns:
            HTML string with all sections and visualizations
        """
        try:
            html = self.analysis_report.generate_full_html_report()
            logger.debug("Generated full HTML report")
            return html
        except Exception as e:
            logger.error(f"Error generating full HTML report: {e}")
            return f"<html><body><p>Error generating report: {e}</p></body></html>"

    def generate_full_json_report(self) -> Dict[str, Any]:
        """
        Generate complete JSON report with all sections.

        Returns:
            Dictionary containing all report sections
        """
        try:
            report_data = {
                "session_id": self.session_id,
                "title": self.title,
                "created_at": self.created_at,
                "sections": {
                    "session_summary": self.report_generator.get_session_summary() or {},
                    "metrics": {
                        "accuracy": self.report_generator.calculate_accuracy(),
                        "avg_latency_ms": self.report_generator.calculate_avg_latency(),
                        "avg_cpu_percent": self.report_generator.calculate_avg_cpu(),
                        "min_latency_ms": self.report_generator.calculate_min_latency(),
                        "max_latency_ms": self.report_generator.calculate_max_latency(),
                        "min_cpu_percent": self.report_generator.calculate_min_cpu(),
                        "max_cpu_percent": self.report_generator.calculate_max_cpu(),
                    },
                    "trend_analysis": self.trend_analysis.get_trend_summary() or {},
                    "degradation": self.trend_analysis.calculate_degradation(),
                    "recovery_rate": self.trend_analysis.calculate_recovery_rate([]),
                    "variants": self.comparisons.variants or {},
                },
            }
            
            logger.debug("Generated full JSON report")
            return report_data
        except Exception as e:
            logger.error(f"Error generating full JSON report: {e}")
            return {"error": str(e)}

    def export_report(
        self,
        output_dir: str,
        format: str = "both",
    ) -> bool:
        """
        Export report in specified format(s).

        Args:
            output_dir: Output directory path
            format: Export format - 'html', 'json', or 'both' (default: 'both')

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            success = True
            
            # Export HTML
            if format in ("html", "both"):
                html_file = output_path / f"{self.session_id}_report.html"
                html = self.generate_full_html_report()
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(f"Exported HTML report to {html_file}")
            
            # Export JSON
            if format in ("json", "both"):
                json_file = output_path / f"{self.session_id}_report.json"
                json_data = self.generate_full_json_report()
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, indent=2, default=str)
                logger.info(f"Exported JSON report to {json_file}")
            
            return success
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return False

    def add_click_positions(self, positions: List[Tuple[int, int]]) -> bool:
        """
        Add click position data for heatmap visualization.

        Args:
            positions: List of (x, y) click coordinates

        Returns:
            True if successful
        """
        return self.analysis_report.add_click_positions(positions)

    def add_variant_comparison(self, variant_name: str, data: Dict[str, Any]) -> bool:
        """
        Add variant comparison data.

        Args:
            variant_name: Variant identifier
            data: Variant metrics dictionary

        Returns:
            True if successful
        """
        return self.analysis_report.add_variant_comparison(variant_name, data)

    def add_accuracy_trend(self, accuracy_data: List[float]) -> bool:
        """
        Add accuracy trend data for trend analysis.

        Args:
            accuracy_data: List of accuracy percentages

        Returns:
            True if successful
        """
        return self.analysis_report.add_accuracy_trend(accuracy_data)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of all calculated metrics.

        Returns:
            Dictionary containing metric summaries
        """
        return {
            "session_id": self.session_id,
            "accuracy_percent": self.report_generator.calculate_accuracy(),
            "avg_latency_ms": self.report_generator.calculate_avg_latency(),
            "avg_cpu_percent": self.report_generator.calculate_avg_cpu(),
            "min_latency_ms": self.report_generator.calculate_min_latency(),
            "max_latency_ms": self.report_generator.calculate_max_latency(),
            "min_cpu_percent": self.report_generator.calculate_min_cpu(),
            "max_cpu_percent": self.report_generator.calculate_max_cpu(),
        }


__all__ = ["FullReportGenerator"]

