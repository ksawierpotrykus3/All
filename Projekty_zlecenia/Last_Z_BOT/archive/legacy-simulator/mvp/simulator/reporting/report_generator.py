"""
Report Generator for simulation session analysis.
Generates HTML reports with session summary, metrics, and visualizations.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import csv
import logging
from io import BytesIO
import base64

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates comprehensive HTML reports from simulation session data.
    """

    def __init__(self, session_id: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize ReportGenerator.

        Args:
            session_id: Session identifier
            metadata: Optional metadata dictionary
        """
        self.session_id = session_id
        self.metadata = metadata or {}
        
        # Data storage
        self.session_summary: Dict[str, Any] = {}
        self.iterations_data: Dict[int, Dict[str, Any]] = {}
        self.report_sections: Dict[str, str] = {}  # Custom sections for HTML
        
        # Report generation timestamp
        self.generated_at = datetime.now()

    def add_session_summary(self, summary: Dict[str, Any]) -> bool:
        """
        Add session summary data.

        Args:
            summary: Summary dictionary with metrics

        Returns:
            True if successful
        """
        try:
            self.session_summary = summary
            logger.debug(f"Session summary added: {summary}")
            return True
        except Exception as e:
            logger.error(f"Error adding session summary: {e}")
            return False

    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        return self.session_summary.copy()

    def add_iteration_data(self, iteration: int, data: Dict[str, Any]) -> bool:
        """
        Add iteration data.

        Args:
            iteration: Iteration number
            data: Iteration data dictionary

        Returns:
            True if successful
        """
        try:
            self.iterations_data[iteration] = data
            logger.debug(f"Iteration {iteration} data added")
            return True
        except Exception as e:
            logger.error(f"Error adding iteration data: {e}")
            return False

    def get_iteration_data(self, iteration: int) -> Optional[Dict[str, Any]]:
        """Get iteration data."""
        return self.iterations_data.get(iteration)

    def calculate_accuracy(self) -> float:
        """
        Calculate accuracy from iteration data.

        Returns:
            Accuracy percentage (0-100)
        """
        if not self.iterations_data:
            return 0.0
        
        successful = sum(
            1 for data in self.iterations_data.values()
            if data.get('success', False)
        )
        total = len(self.iterations_data)
        
        return (successful / total * 100) if total > 0 else 0.0

    def calculate_avg_latency(self) -> Optional[float]:
        """
        Calculate average latency from iteration data.

        Returns:
            Average latency in milliseconds or None
        """
        latencies = [
            data.get('latency_ms')
            for data in self.iterations_data.values()
            if data.get('latency_ms') is not None
        ]
        
        if latencies:
            return sum(latencies) / len(latencies)
        return None

    def calculate_avg_cpu(self) -> Optional[float]:
        """
        Calculate average CPU from iteration data.

        Returns:
            Average CPU percentage or None
        """
        cpu_values = [
            data.get('cpu_percent')
            for data in self.iterations_data.values()
            if data.get('cpu_percent') is not None
        ]
        
        if cpu_values:
            return sum(cpu_values) / len(cpu_values)
        return None

    def calculate_min_latency(self) -> Optional[float]:
        """
        Calculate minimum latency from iteration data.

        Returns:
            Minimum latency in milliseconds or None
        """
        latencies = [
            data.get('latency_ms')
            for data in self.iterations_data.values()
            if data.get('latency_ms') is not None
        ]
        
        return min(latencies) if latencies else None

    def calculate_max_latency(self) -> Optional[float]:
        """
        Calculate maximum latency from iteration data.

        Returns:
            Maximum latency in milliseconds or None
        """
        latencies = [
            data.get('latency_ms')
            for data in self.iterations_data.values()
            if data.get('latency_ms') is not None
        ]
        
        return max(latencies) if latencies else None

    def calculate_min_cpu(self) -> Optional[float]:
        """
        Calculate minimum CPU from iteration data.

        Returns:
            Minimum CPU percentage or None
        """
        cpu_values = [
            data.get('cpu_percent')
            for data in self.iterations_data.values()
            if data.get('cpu_percent') is not None
        ]
        
        return min(cpu_values) if cpu_values else None

    def calculate_max_cpu(self) -> Optional[float]:
        """
        Calculate maximum CPU from iteration data.

        Returns:
            Maximum CPU percentage or None
        """
        cpu_values = [
            data.get('cpu_percent')
            for data in self.iterations_data.values()
            if data.get('cpu_percent') is not None
        ]
        
        return max(cpu_values) if cpu_values else None

    def set_variant_preset(self, preset: str) -> bool:
        """Set variant preset."""
        try:
            self.metadata['variant_preset'] = preset
            return True
        except Exception as e:
            logger.error(f"Error setting variant preset: {e}")
            return False

    def get_variant_preset(self) -> Optional[str]:
        """Get variant preset."""
        return self.metadata.get('variant_preset')

    def add_report_section(self, section_name: str, html_content: str) -> bool:
        """
        Add custom report section.

        Args:
            section_name: Section name
            html_content: HTML content for section

        Returns:
            True if successful
        """
        try:
            self.report_sections[section_name] = html_content
            return True
        except Exception as e:
            logger.error(f"Error adding report section: {e}")
            return False

    def generate_html_report(self) -> str:
        """
        Generate HTML report.

        Returns:
            HTML string
        """
        html_parts = []
        
        # HTML header
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html>')
        html_parts.append('<head>')
        html_parts.append('<meta charset="utf-8">')
        html_parts.append(f'<title>Simulator Report - {self.session_id}</title>')
        html_parts.append('<style>')
        html_parts.append(self._get_css_styles())
        html_parts.append('</style>')
        html_parts.append('</head>')
        html_parts.append('<body>')
        
        # Title
        html_parts.append(f'<h1>Extended Game Simulator Report</h1>')
        html_parts.append(f'<p><strong>Session ID:</strong> {self.session_id}</p>')
        html_parts.append(
            f'<p><strong>Generated:</strong> {self.generated_at.strftime("%Y-%m-%d %H:%M:%S")}</p>'
        )
        
        # Summary section
        html_parts.append('<h2>Session Summary</h2>')
        html_parts.append('<div class="summary-section">')
        
        if self.session_summary:
            html_parts.append('<table class="metrics-table">')
            for key, value in self.session_summary.items():
                if isinstance(value, float):
                    formatted_value = f'{value:.2f}'
                else:
                    formatted_value = str(value)
                html_parts.append(f'<tr><td>{key}</td><td>{formatted_value}</td></tr>')
            html_parts.append('</table>')
        
        html_parts.append('</div>')
        
        # Iterations overview
        html_parts.append('<h2>Iterations Overview</h2>')
        html_parts.append(f'<p>Total iterations: {len(self.iterations_data)}</p>')
        
        # Custom sections
        for section_name, section_html in self.report_sections.items():
            html_parts.append(f'<h2>{section_name}</h2>')
            html_parts.append(f'<div class="section">{section_html}</div>')
        
        # Footer
        html_parts.append('<hr>')
        html_parts.append(f'<p class="footer">Generated by Extended Game Simulator Framework</p>')
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        return '\n'.join(html_parts)

    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            margin: 20px;
            padding: 0;
        }
        h1, h2, h3 {
            color: #1976d2;
            border-bottom: 2px solid #1976d2;
            padding-bottom: 10px;
        }
        .summary-section {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
        }
        .metrics-table tr {
            border-bottom: 1px solid #ddd;
        }
        .metrics-table td {
            padding: 12px;
            text-align: left;
        }
        .metrics-table tr:hover {
            background-color: #f9f9f9;
        }
        .section {
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        .footer {
            font-size: 12px;
            color: #999;
            text-align: center;
            margin-top: 40px;
        }
        """

    def save_report(self, output_path: str) -> bool:
        """
        Save HTML report to file.

        Args:
            output_path: Path to save HTML file

        Returns:
            True if successful
        """
        try:
            html = self.generate_html_report()
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"Report saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return False

    def export_iterations_csv(self, output_path: str) -> bool:
        """
        Export iteration data to CSV.

        Args:
            output_path: Path to save CSV file

        Returns:
            True if successful
        """
        try:
            if not self.iterations_data:
                logger.warning("No iteration data to export")
                return False
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get all unique field names
            fieldnames = set()
            for data in self.iterations_data.values():
                fieldnames.update(data.keys())
            fieldnames = sorted(list(fieldnames))
            
            # Write CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for iteration in sorted(self.iterations_data.keys()):
                    row = self.iterations_data[iteration]
                    writer.writerow(row)
            
            logger.info(f"Iterations exported to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting iterations to CSV: {e}")
            return False

    def export_json(self, output_path: str) -> bool:
        """
        Export all report data to JSON.

        Args:
            output_path: Path to save JSON file

        Returns:
            True if successful
        """
        try:
            data = {
                'session_id': self.session_id,
                'generated_at': self.generated_at.isoformat(),
                'metadata': self.metadata,
                'session_summary': self.session_summary,
                'iterations': self.iterations_data,
            }
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Report exported to JSON: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return False


__all__ = ['ReportGenerator']