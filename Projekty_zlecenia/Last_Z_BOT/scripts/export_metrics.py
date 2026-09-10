"""Export and analyze watch_timer metrics from JSON files.

This script reads a metrics JSON file (exported by BotMetrics.export_json())
and converts it to various formats for analysis:

- JSON (pretty-printed, default)
- CSV (timer reads and spam clicks as separate files)
- HTML (human-readable report with summary)

Usage:
    python scripts/export_metrics.py INPUT.json [--output OUTPUT] [--format FORMAT] [--pretty]

Examples:
    # Pretty-print JSON
    python scripts/export_metrics.py metrics.json --pretty

    # Export to CSV (creates metrics_timer_reads.csv and metrics_spam_clicks.csv)
    python scripts/export_metrics.py metrics.json --format csv --output metrics.csv

    # Generate HTML report
    python scripts/export_metrics.py metrics.json --format html --output report.html
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


def load_metrics(input_path: Path) -> dict[str, Any]:
    """Load metrics from JSON file."""
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate structure
    if "summary" not in data:
        print(f"ERROR: Missing 'summary' key in {input_path}", file=sys.stderr)
        sys.exit(1)

    return data


def export_json(data: dict[str, Any], output_path: Path, pretty: bool) -> None:
    """Export metrics as pretty-printed JSON."""
    indent = 2 if pretty else None
    output_path.write_text(
        json.dumps(data, indent=indent, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Exported JSON to: {output_path}")


def export_csv(data: dict[str, Any], output_path: Path) -> None:
    """Export metrics as CSV files (timer reads and spam clicks)."""
    base = output_path.with_suffix("")
    timer_csv = base.with_name(f"{base.name}_timer_reads.csv")
    clicks_csv = base.with_name(f"{base.name}_spam_clicks.csv")
    phases_csv = base.with_name(f"{base.name}_phase_transitions.csv")

    # Timer reads
    with timer_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "value", "confidence", "method", "passed_sanity"])
        for read in data.get("timer_reads", []):
            writer.writerow([
                read.get("ts", ""),
                read.get("value", ""),
                read.get("confidence", ""),
                read.get("method", ""),
                read.get("passed_sanity", ""),
            ])
    print(f"Exported timer reads to: {timer_csv}")

    # Spam clicks
    with clicks_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x", "y", "chunk_size"])
        for click in data.get("spam_clicks", []):
            writer.writerow([
                click.get("ts", ""),
                click.get("x", ""),
                click.get("y", ""),
                click.get("chunk_size", ""),
            ])
    print(f"Exported spam clicks to: {clicks_csv}")

    # Phase transitions
    with phases_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "phase"])
        for phase in data.get("phase_transitions", []):
            writer.writerow([
                phase.get("ts", ""),
                phase.get("phase", ""),
            ])
    print(f"Exported phase transitions to: {phases_csv}")


def _format_metric_value(value: Any) -> str:
    """Format metric value for HTML display."""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _get_metric_class(value: Any, threshold: float, reverse: bool = False) -> str:
    """Get CSS class for metric based on threshold."""
    if not isinstance(value, (int, float)):
        return ""
    if reverse:
        return "success" if value <= threshold else "error"
    return "success" if value >= threshold else "error"


def _build_summary_html(summary: dict[str, Any]) -> str:
    """Build summary grid HTML."""
    summary_items = [
        ("OCR Failures", summary.get("ocr_failures", 0), 10, True),
        ("Sanity Failures", summary.get("sanity_failures", 0), 5, True),
        ("Hysteresis Confirmations", summary.get("hysteresis_confirmations", 0), 0, False),
        ("Spam Triggers", summary.get("spam_triggers", 0), 0, False),
        ("Forced Triggers", summary.get("spam_forced_triggers", 0), 0, True),
        ("Click Rate (1s)", summary.get("click_rate_1s", 0), 0, False),
        ("Click Rate (5s)", summary.get("click_rate_5s", 0), 0, False),
        ("Last Timer Value", summary.get("last_timer_value", "N/A"), 0, False),
        ("Last Timer Confidence", summary.get("last_timer_confidence", 0), 0, False),
        ("Last Timer Method", summary.get("last_timer_method", "none"), 0, False),
        ("Timer Reads", summary.get("timer_reads_count", 0), 0, False),
        ("Spam Clicks", summary.get("spam_clicks_count", 0), 0, False),
        ("Phase Transitions", summary.get("phase_transitions_count", 0), 0, False),
    ]

    parts = []
    for label, value, threshold, reverse in summary_items:
        css_class = _get_metric_class(value, threshold, reverse) if threshold > 0 else ""
        formatted_value = _format_metric_value(value)
        parts.append("            <div class=\"metric\">" + chr(10))
        parts.append("                <div class=\"metric-label\">" + str(label) + "</div>" + chr(10))
        parts.append("                <div class=\"metric-value " + css_class + "\">" + formatted_value + "</div>" + chr(10))
        parts.append("         </div>" + chr(10))
    return "".join(parts)


def _build_timer_reads_html(timer_reads: list[dict[str, Any]]) -> str:
    """Build timer reads table HTML."""
    parts = []
    for read in timer_reads[-20:]:
        sanity_class = "success" if read.get("passed_sanity") else "error"
        sanity_text = "PASS" if read.get("passed_sanity") else "FAIL"
        ts = _format_metric_value(read.get("ts", 0))
        value = _format_metric_value(read.get("value", "N/A"))
        confidence = _format_metric_value(read.get("confidence", 0))
        method = read.get("method", "unknown")
        parts.append("            <tr>" + chr(10))
        parts.append("                <td>" + ts + "</td>" + chr(10))
        parts.append("                <td>" + value + "</td>" + chr(10))
        parts.append("                <td>" + confidence + "</td>" + chr(10))
        parts.append("                <td>" + str(method) + "</td>" + chr(10))
        parts.append("                <td class=\"" + sanity_class + "\">" + sanity_text + "</td>" + chr(10))
        parts.append("         </tr>" + chr(10))
    return "".join(parts)


def _build_phases_html(phases: list[dict[str, Any]]) -> str:
    """Build phase transitions table HTML."""
    parts = []
    for phase in phases:
        ts = _format_metric_value(phase.get("ts", 0))
        phase_name = phase.get("phase", "unknown")
        parts.append("            <tr>" + chr(10))
        parts.append("                <td>" + ts + "</td>" + chr(10))
        parts.append("                <td>" + str(phase_name) + "</td>" + chr(10))
        parts.append("         </tr>" + chr(10))
    return "".join(parts)


def export_html(data: dict[str, Any], output_path: Path) -> None:
    """Export metrics as HTML report."""
    summary = data.get("summary", {})
    summary_html = _build_summary_html(summary)
    timer_reads_html = _build_timer_reads_html(data.get("timer_reads", []))
    phases_html = _build_phases_html(data.get("phase_transitions", []))

    # Build HTML using string concatenation (no f-strings with backslashes)
    nl = chr(10)
    html = (
        "<!DOCTYPE html>" + nl
        + "<html lang=\"en\">" + nl
        + "<head>" + nl
        + "    <meta charset=\"UTF-8\">" + nl
        + "    <title>Watch Timer Metrics Report</title>" + nl
        + "    <style>" + nl
        + "        body {" + nl
        + "            font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;" + nl
        + "            max-width: 1200px;" + nl
        + "            margin: 0 auto;" + nl
        + "            padding: 20px;" + nl
        + "            background: #18181b;" + nl
        + "            color: #e4e4e7;" + nl
        + "        }" + nl
        + "        h1, h2 {" + nl
        + "            color: #f97316;" + nl
        + "        }" + nl
        + "        .summary {" + nl
        + "            background: #27272a;" + nl
        + "            border: 1px solid #3f3f46;" + nl
        + "            border-radius: 8px;" + nl
        + "            padding: 20px;" + nl
        + "            margin-bottom: 20px;" + nl
        + "        }" + nl
        + "        .summary-grid {" + nl
        + "            display: grid;" + nl
        + "            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));" + nl
        + "            gap: 15px;" + nl
        + "        }" + nl
        + "        .metric {" + nl
        + "            background: #18181b;" + nl
        + "            border: 1px solid #3f3f46;" + nl
        + "            border-radius: 4px;" + nl
        + "            padding: 10px;" + nl
        + "        }" + nl
        + "        .metric-label {" + nl
        + "            font-size: 0.85em;" + nl
        + "            color: #a1a1aa;" + nl
        + "            margin-bottom: 5px;" + nl
        + "        }" + nl
        + "        .metric-value {" + nl
        + "            font-size: 1.5em;" + nl
        + "            font-weight: bold;" + nl
        + "            color: #f97316;" + nl
        + "        }" + nl
        + "        table {" + nl
        + "            width: 100%;" + nl
        + "            border-collapse: collapse;" + nl
        + "            margin-top: 10px;" + nl
        + "            background: #27272a;" + nl
        + "        }" + nl
        + "        th, td {" + nl
        + "            padding: 8px;" + nl
        + "            text-align: left;" + nl
        + "            border-bottom: 1px solid #3f3f46;" + nl
        + "        }" + nl
        + "        th {" + nl
        + "            background: #18181b;" + nl
        + "            color: #f97316;" + nl
        + "            font-weight: bold;" + nl
        + "        }" + nl
        + "        .success { color: #22c55e; }" + nl
        + "        .warning { color: #f59e0b; }" + nl
        + "        .error { color: #ef4444; }" + nl
        + "    </style>" + nl
        + "</head>" + nl
        + "<body>" + nl
        + "    <h1>Watch Timer Metrics Report</h1>" + nl
        + nl
        + "    <div class=\"summary\">" + nl
        + "        <h2>Summary</h2>" + nl
        + "        <div class=\"summary-grid\">" + nl
        + summary_html
        + "       </div>" + nl
        + "   </div>" + nl
        + nl
        + "    <h2>Recent Timer Reads (last 20)</h2>" + nl
        + "    <table>" + nl
        + "        <thead>" + nl
        + "            <tr>" + nl
        + "                <th>Timestamp</th>" + nl
        + "                <th>Value</th>" + nl
        + "                <th>Confidence</th>" + nl
        + "                <th>Method</th>" + nl
        + "                <th>Sanity</th>" + nl
        + "           </tr>" + nl
        + "       </thead>" + nl
        + "        <tbody>" + nl
        + timer_reads_html
        + "      </tbody>" + nl
        + "   </table>" + nl
        + nl
        + "    <h2>Phase Transitions</h2>" + nl
        + "    <table>" + nl
        + "        <thead>" + nl
        + "            <tr>" + nl
        + "                <th>Timestamp</th>" + nl
        + "                <th>Phase</th>" + nl
        + "           </tr>" + nl
        + "       </thead>" + nl
        + "        <tbody>" + nl
        + phases_html
        + "      </tbody>" + nl
        + "   </table>" + nl
        + "</body>" + nl
        + "</html>" + nl
    )

    output_path.write_text(html, encoding="utf-8")
    print(f"Exported HTML report to: {output_path}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export and analyze watch_timer metrics from JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input JSON file (exported by BotMetrics.export_json())",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: input with new extension)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "csv", "html"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (default: True for json format)",
    )

    args = parser.parse_args()

    # Load metrics
    data = load_metrics(args.input)

    # Determine output path
    if args.output is None:
        if args.format == "json":
            args.output = args.input.with_suffix(".pretty.json")
        elif args.format == "csv":
            args.output = args.input.with_suffix(".csv")
        elif args.format == "html":
            args.output = args.input.with_suffix(".html")

    # Export based on format
    if args.format == "json":
        export_json(data, args.output, args.pretty)
    elif args.format == "csv":
        export_csv(data, args.output)
    elif args.format == "html":
        export_html(data, args.output)


if __name__ == "__main__":
    main()
