"""Log Parser for game_events.log and event_log files.

This module parses logs from both C# window and bot MVP processes,
extracting metrics for click accuracy, OCR precision, timing analysis.

Log Formats:
  game_events.log (CSV): timestamp_ms,x,y,element_name,event_type
  event_log (text): [HH:MM:SS.mmm] MESSAGE_TYPE: message content
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Click:
    """Represents a single click event from game_events.log."""

    timestamp_ms: int  # System clock milliseconds
    x: int  # Screen pixel X coordinate
    y: int  # Screen pixel Y coordinate
    element_name: str  # arrow, heli, details, timer, other
    event_type: str  # click, scroll, frame_drop, etc.

    def __hash__(self) -> int:
        return hash((self.timestamp_ms, self.x, self.y, self.element_name))


@dataclass
class OCRDetection:
    """Represents OCR detection from event_log."""

    timestamp: datetime
    element_name: str  # arrow, heli, details, chat, etc.
    confidence: float  # 0.0 - 1.0
    x: Optional[int] = None  # Detected coordinates (optional)
    y: Optional[int] = None

    def __hash__(self) -> int:
        return hash((self.timestamp, self.element_name, self.confidence))


@dataclass
class MacroDecision:
    """Represents a macro decision (action) from event_log."""

    timestamp: datetime
    decision_type: str  # click, wait, scroll, etc.
    target_element: str  # arrow, heli, etc.
    target_x: Optional[int] = None
    target_y: Optional[int] = None
    latency_ms: Optional[float] = None  # Time to decide
    action_info: Optional[str] = None  # Extra info


@dataclass
class TimingEvent:
    """Represents a timing event from event_log."""

    timestamp: datetime
    event_type: str  # timer_read, timer_update, etc.
    value: Optional[float] = None  # Timer seconds, latency ms, etc.


@dataclass
class ParsedGameEventsLog:
    """Parsed game_events.log data."""

    clicks: list[Click] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # Non-click events
    malformed_count: int = 0
    parse_errors: list[str] = field(default_factory=list)


@dataclass
class ParsedEventLog:
    """Parsed event_log data."""

    ocr_detections: list[OCRDetection] = field(default_factory=list)
    macro_decisions: list[MacroDecision] = field(default_factory=list)
    timing_events: list[TimingEvent] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)  # Unparsed lines
    malformed_count: int = 0
    parse_errors: list[str] = field(default_factory=list)


class LogParser:
    """Parses logs from C# window and bot MVP processes."""

    # Regex patterns for event_log parsing
    TIMESTAMP_PATTERN = r"\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})\]"
    OCR_DETECTION_PATTERN = r"Detection:\s+(\w+)\s+detected.*?confidence\s*=\s*([\d.]+)"
    MACRO_DECISION_PATTERN = r"(?:Decision|Click|Action):\s+(\w+)\s+(\w+).*?at\s*\((\d+),\s*(\d+)\)"
    TIMER_PATTERN = r"(?:Timer|Timing|Latency).*?(\d+)"

    def __init__(self, enable_warnings: bool = True) -> None:
        """Initialize log parser.

        Args:
            enable_warnings: If True, log warnings for malformed entries
        """
        self.enable_warnings = enable_warnings

    def collect_game_events_log(
        self, work_dir: str | Path, timeout_s: int = 5
    ) -> ParsedGameEventsLog:
        """Collect and parse game_events.log from C# window directory.

        Args:
            work_dir: Working directory of C# process
            timeout_s: Maximum time to wait for log file (not enforced here)

        Returns:
            ParsedGameEventsLog with parsed clicks and events
        """
        work_path = Path(work_dir)
        log_file = work_path / "game_events.log"

        parsed = ParsedGameEventsLog()

        if not log_file.exists():
            error_msg = f"game_events.log not found in {work_path}"
            parsed.parse_errors.append(error_msg)
            if self.enable_warnings:
                logger.warning(error_msg)
            return parsed

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    error_msg = "game_events.log has no header row"
                    parsed.parse_errors.append(error_msg)
                    if self.enable_warnings:
                        logger.warning(error_msg)
                    return parsed

                for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                    try:
                        click = self._parse_game_event_row(row)
                        if click:
                            parsed.clicks.append(click)
                        else:
                            parsed.events.append(row)
                    except (ValueError, KeyError) as e:
                        parsed.malformed_count += 1
                        error_msg = f"Row {row_num}: {str(e)}"
                        parsed.parse_errors.append(error_msg)
                        if self.enable_warnings:
                            logger.warning(f"Skipping malformed line in game_events.log: {error_msg}")

        except OSError as e:
            error_msg = f"Failed to read game_events.log: {e}"
            parsed.parse_errors.append(error_msg)
            if self.enable_warnings:
                logger.warning(error_msg)

        return parsed

    def collect_event_log(
        self, work_dir: str | Path, timeout_s: int = 5
    ) -> ParsedEventLog:
        """Collect and parse event_log from bot MVP directory.

        Args:
            work_dir: Working directory of bot process
            timeout_s: Maximum time to wait for log file (not enforced here)

        Returns:
            ParsedEventLog with parsed detections, decisions, timing
        """
        work_path = Path(work_dir)
        log_file = work_path / "event_log"

        parsed = ParsedEventLog()

        if not log_file.exists():
            # Try with .log or .txt extensions
            for ext in [".log", ".txt", ""]:
                alt_file = work_path / f"event_log{ext}"
                if alt_file.exists():
                    log_file = alt_file
                    break

        if not log_file.exists():
            error_msg = f"event_log not found in {work_path}"
            parsed.parse_errors.append(error_msg)
            if self.enable_warnings:
                logger.warning(error_msg)
            return parsed

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                line = line.rstrip("\n\r")
                if not line.strip():
                    continue

                parsed.raw_lines.append(line)

                try:
                    # Parse line based on message type
                    if "OCR" in line and "Detection" in line:
                        detection = self._parse_ocr_detection(line)
                        if detection:
                            parsed.ocr_detections.append(detection)
                    elif "Decision" in line or "Click" in line or "Action" in line:
                        decision = self._parse_macro_decision(line)
                        if decision:
                            parsed.macro_decisions.append(decision)
                    elif "Timer" in line or "timer" in line:
                        timing = self._parse_timing_event(line)
                        if timing:
                            parsed.timing_events.append(timing)

                except (ValueError, AttributeError) as e:
                    parsed.malformed_count += 1
                    error_msg = f"Line {line_num}: {str(e)}"
                    parsed.parse_errors.append(error_msg)
                    if self.enable_warnings:
                        logger.warning(f"Skipping malformed line in event_log: {error_msg}")

        except OSError as e:
            error_msg = f"Failed to read event_log: {e}"
            parsed.parse_errors.append(error_msg)
            if self.enable_warnings:
                logger.warning(error_msg)

        return parsed

    def _parse_game_event_row(self, row: dict) -> Optional[Click]:
        """Parse a single row from game_events.log CSV.

        Expected fields: timestamp_ms, x, y, element_name, event_type

        Args:
            row: CSV row as dictionary

        Returns:
            Click object if event_type is 'click', None for other events

        Raises:
            ValueError: If required fields missing or invalid
            KeyError: If expected columns not in row
        """
        required_fields = ["timestamp_ms", "x", "y", "element_name", "event_type"]

        # Check for required fields (case-insensitive)
        row_lower = {k.lower(): v for k, v in row.items()}
        for field in required_fields:
            if field not in row_lower:
                raise KeyError(f"Missing field: {field}")

        try:
            timestamp_ms = int(row_lower["timestamp_ms"])
            x = int(row_lower["x"])
            y = int(row_lower["y"])
            element_name = str(row_lower["element_name"]).strip()
            event_type = str(row_lower["event_type"]).strip()
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid field types: {e}") from e

        if event_type.lower() != "click":
            return None  # Not a click event

        return Click(
            timestamp_ms=timestamp_ms, x=x, y=y, element_name=element_name, event_type=event_type
        )

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp from event_log format [HH:MM:SS.mmm].

        Args:
            timestamp_str: Timestamp string from log

        Returns:
            datetime object or None if parsing fails
        """
        match = re.search(self.TIMESTAMP_PATTERN, timestamp_str)
        if not match:
            return None

        hour, minute, second, millisecond = match.groups()

        try:
            # Create a datetime with today's date (logs don't include date)
            return datetime(
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day,
                hour=int(hour),
                minute=int(minute),
                second=int(second),
                microsecond=int(millisecond) * 1000,
            )
        except ValueError:
            return None

    def _parse_ocr_detection(self, line: str) -> Optional[OCRDetection]:
        """Parse OCR detection line from event_log.

        Expected format: [HH:MM:SS.mmm] OCR Detection: element_name detected confidence=X.XX

        Args:
            line: Log line to parse

        Returns:
            OCRDetection object or None if parsing fails
        """
        timestamp = self._parse_timestamp(line)
        if not timestamp:
            return None

        # Extract element name and confidence
        match = re.search(self.OCR_DETECTION_PATTERN, line, re.IGNORECASE)
        if not match:
            return None

        element_name = match.group(1)
        try:
            confidence = float(match.group(2))
        except ValueError:
            return None

        # Try to extract coordinates if present
        x, y = None, None
        coord_match = re.search(r"\((\d+),\s*(\d+)\)", line)
        if coord_match:
            try:
                x = int(coord_match.group(1))
                y = int(coord_match.group(2))
            except ValueError:
                pass

        return OCRDetection(timestamp=timestamp, element_name=element_name, confidence=confidence, x=x, y=y)

    def _parse_macro_decision(self, line: str) -> Optional[MacroDecision]:
        """Parse macro decision/click line from event_log.

        Expected format: [HH:MM:SS.mmm] Decision: click arrow at (512, 768)

        Args:
            line: Log line to parse

        Returns:
            MacroDecision object or None if parsing fails
        """
        timestamp = self._parse_timestamp(line)
        if not timestamp:
            return None

        # Extract decision type, target, and coordinates
        match = re.search(self.MACRO_DECISION_PATTERN, line, re.IGNORECASE)
        if not match:
            return None

        decision_type = match.group(1)
        target_element = match.group(2)
        try:
            target_x = int(match.group(3))
            target_y = int(match.group(4))
        except ValueError:
            return None

        return MacroDecision(
            timestamp=timestamp,
            decision_type=decision_type,
            target_element=target_element,
            target_x=target_x,
            target_y=target_y,
        )

    def _parse_timing_event(self, line: str) -> Optional[TimingEvent]:
        """Parse timing event from event_log.

        Expected format: [HH:MM:SS.mmm] Timer: 299 seconds

        Args:
            line: Log line to parse

        Returns:
            TimingEvent object or None if parsing fails
        """
        timestamp = self._parse_timestamp(line)
        if not timestamp:
            return None

        # Extract timing value
        match = re.search(self.TIMER_PATTERN, line)
        if not match:
            return None

        event_type = "timer"
        if "latency" in line.lower() or "lag" in line.lower():
            event_type = "latency"

        try:
            value = float(match.group(1))
        except ValueError:
            value = None

        return TimingEvent(timestamp=timestamp, event_type=event_type, value=value)
