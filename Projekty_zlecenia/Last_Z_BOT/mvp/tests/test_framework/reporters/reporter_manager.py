"""Reporter manager coordinating Console, HTML, and SQLite reporters for test results."""

from pathlib import Path
from typing import Optional
from datetime import datetime

from mvp.tests.test_framework.metrics import RunMetrics, TestSuiteResult
from mvp.tests.test_framework.reporters.console_reporter import ConsoleReporter
from mvp.tests.test_framework.reporters.html_reporter import HTMLReporter
from mvp.tests.test_framework.reporters.sqlite_reporter import SQLiteReporter


class ReporterManager:
    """Coordinate multiple reporters for comprehensive test result output."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """Initialize reporter manager.
        
        Args:
            output_dir: Base directory for all reports. Defaults to ./reports
        """
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamp for this report session
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize reporters
        console_dir = self.output_dir / "console"
        console_dir.mkdir(parents=True, exist_ok=True)
        self.console_reporter = ConsoleReporter(output_dir=console_dir)
        
        html_dir = self.output_dir / "html" / self.timestamp
        html_dir.mkdir(parents=True, exist_ok=True)
        self.html_reporter = HTMLReporter(output_dir=html_dir)
        
        db_path = self.output_dir / f"test_results_{self.timestamp}.db"
        self.sqlite_reporter = SQLiteReporter(str(db_path))

    def __del__(self):
        """Cleanup: close database connections on deletion."""
        # SQLite will auto-close when object is destroyed, but we ensure it
        pass

    def add_run(self, run_num: int, scenario, metrics: RunMetrics) -> None:
        """Add a run to all reporters.
        
        Args:
            run_num: Run number (1-indexed)
            scenario: Scenario object for this run
            metrics: RunMetrics for this run
        """
        # Add to console reporter (used for per-run output)
        self.console_reporter.report_run(run_num, scenario, metrics)
        
        # Add to HTML reporter (accumulated for final report)
        self.html_reporter.add_run(run_num, scenario, metrics)
        
        # Add to SQLite reporter (persisted to database)
        self.sqlite_reporter.add_run(run_num, scenario, metrics)

    def finalize_reports(self, suite_result: TestSuiteResult) -> dict[str, Path]:
        """Generate final reports from all reporters.
        
        Args:
            suite_result: TestSuiteResult with aggregated metrics
            
        Returns:
            Dictionary with paths to generated reports
        """
        report_paths = {}
        
        # Console report
        console_path = self.console_reporter.save_report(
            suite_result,
            filename=f"console_report_{self.timestamp}.txt"
        )
        report_paths["console"] = console_path
        print(f"\n✅ Console report saved to: {console_path}")
        
        # HTML report
        html_path = self.html_reporter.finalize()
        report_paths["html"] = html_path
        print(f"✅ HTML report saved to: {html_path}")
        
        # SQLite database path
        report_paths["sqlite"] = Path(self.sqlite_reporter.db_path)
        print(f"✅ SQLite database saved to: {report_paths['sqlite']}")
        
        # Print console report to stdout
        print("\n" + "=" * 80)
        print(self.console_reporter.generate_report(suite_result))
        
        return report_paths

    def get_db_path(self) -> Path:
        """Get path to SQLite database.
        
        Returns:
            Path to test_results.db
        """
        return Path(self.sqlite_reporter.db_path)

    def get_example_queries(self) -> dict[str, str]:
        """Get example SQL queries from SQLite reporter.
        
        Returns:
            Dictionary of query name -> SQL query string
        """
        return self.sqlite_reporter.get_example_queries()
