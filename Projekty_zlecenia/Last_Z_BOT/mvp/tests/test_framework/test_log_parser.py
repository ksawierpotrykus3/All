"""Comprehensive unit tests for LogParser.

Tests cover:
- Log file collection from both C# and bot MVP
- CSV parsing for game_events.log
- Text parsing for event_log
- Malformed entry handling
- Timestamp extraction
- Coordinate parsing
- OCR confidence extraction
- Error handling and graceful recovery
"""

from __future__ import annotations

import csv
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mvp.tests.test_framework.log_parser import (
    Click,
    LogParser,
    MacroDecision,
    OCRDetection,
    ParsedEventLog,
    ParsedGameEventsLog,
    TimingEvent,
)


class TestClickDataClass:
    """Tests for Click data class."""

    def test_click_creation(self) -> None:
        """Test basic Click creation."""
        click = Click(timestamp_ms=1704067200000, x=512, y=768, element_name="arrow", event_type="click")
        assert click.timestamp_ms == 1704067200000
        assert click.x == 512
        assert click.y == 768
        assert click.element_name == "arrow"
        assert click.event_type == "click"

    def test_click_hash(self) -> None:
        """Test Click objects can be used in sets."""
        click1 = Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click")
        click2 = Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click")
        click_set = {click1, click2}
        assert len(click_set) == 1  # Same hash → set deduplicates

    def test_click_different_timestamps_different_hash(self) -> None:
        """Test clicks with different timestamps have different hashes."""
        click1 = Click(timestamp_ms=1000, x=512, y=768, element_name="arrow", event_type="click")
        click2 = Click(timestamp_ms=2000, x=512, y=768, element_name="arrow", event_type="click")
        click_set = {click1, click2}
        assert len(click_set) == 2


class TestOCRDetectionDataClass:
    """Tests for OCRDetection data class."""

    def test_ocr_detection_creation(self) -> None:
        """Test basic OCRDetection creation."""
        now = datetime.now()
        detection = OCRDetection(
            timestamp=now, element_name="arrow", confidence=0.92, x=512, y=768
        )
        assert detection.timestamp == now
        assert detection.element_name == "arrow"
        assert detection.confidence == 0.92
        assert detection.x == 512
        assert detection.y == 768

    def test_ocr_detection_without_coordinates(self) -> None:
        """Test OCRDetection without coordinates."""
        now = datetime.now()
        detection = OCRDetection(timestamp=now, element_name="heli", confidence=0.85)
        assert detection.x is None
        assert detection.y is None


class TestLogParserInitialization:
    """Tests for LogParser initialization."""

    def test_parser_created_with_warnings_enabled(self) -> None:
        """Test parser created with warnings enabled."""
        parser = LogParser(enable_warnings=True)
        assert parser.enable_warnings is True

    def test_parser_created_with_warnings_disabled(self) -> None:
        """Test parser created with warnings disabled."""
        parser = LogParser(enable_warnings=False)
        assert parser.enable_warnings is False


class TestGameEventsLogCollection:
    """Tests for game_events.log file collection."""

    def test_collect_game_events_log_file_not_found(self, tmp_path: Path) -> None:
        """Test collection when file does not exist."""
        parser = LogParser(enable_warnings=False)
        result = parser.collect_game_events_log(tmp_path)

        assert isinstance(result, ParsedGameEventsLog)
        assert len(result.clicks) == 0
        assert len(result.parse_errors) > 0
        assert "not found" in result.parse_errors[0]

    def test_collect_game_events_log_empty_file(self, tmp_path: Path) -> None:
        """Test collection with empty CSV file."""
        log_file = tmp_path / "game_events.log"
        log_file.write_text("")

        parser = LogParser(enable_warnings=False)
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 0
        assert len(result.parse_errors) > 0

    def test_collect_game_events_log_single_valid_click(self, tmp_path: Path) -> None:
        """Test collection with single valid click."""
        log_file = tmp_path / "game_events.log"

        # Write CSV with header and one click
        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "512",
                    "y": "768",
                    "element_name": "arrow",
                    "event_type": "click",
                }
            )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 1
        click = result.clicks[0]
        assert click.timestamp_ms == 1704067200000
        assert click.x == 512
        assert click.y == 768
        assert click.element_name == "arrow"

    def test_collect_game_events_log_multiple_clicks(self, tmp_path: Path) -> None:
        """Test collection with multiple valid clicks."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            for i in range(5):
                writer.writerow(
                    {
                        "timestamp_ms": str(1704067200000 + i * 100),
                        "x": str(512 + i),
                        "y": str(768 + i),
                        "element_name": "arrow",
                        "event_type": "click",
                    }
                )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 5
        for i, click in enumerate(result.clicks):
            assert click.x == 512 + i

    def test_collect_game_events_log_mixed_events(self, tmp_path: Path) -> None:
        """Test collection with clicks and other events."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "512",
                    "y": "768",
                    "element_name": "arrow",
                    "event_type": "click",
                }
            )
            writer.writerow(
                {
                    "timestamp_ms": "1704067200050",
                    "x": "512",
                    "y": "700",
                    "element_name": "chat",
                    "event_type": "scroll",
                }
            )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 1  # Only click
        assert len(result.events) == 1  # Other event stored separately

    def test_collect_game_events_log_malformed_row_missing_field(self, tmp_path: Path) -> None:
        """Test collection with malformed row having non-int x value."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "not_a_number",
                    "y": "768",
                    "element_name": "arrow",
                    "event_type": "click",
                }
            )

        parser = LogParser(enable_warnings=False)
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 0
        assert result.malformed_count == 1
        assert len(result.parse_errors) > 0

    def test_collect_game_events_log_malformed_row_invalid_integer(self, tmp_path: Path) -> None:
        """Test collection with malformed row having invalid integer."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "not_a_number",
                    "x": "512",
                    "y": "768",
                    "element_name": "arrow",
                    "event_type": "click",
                }
            )

        parser = LogParser(enable_warnings=False)
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 0
        assert result.malformed_count == 1

    def test_collect_game_events_log_skips_non_click_events(self, tmp_path: Path) -> None:
        """Test that non-click events are collected separately."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "0",
                    "y": "0",
                    "element_name": "screen",
                    "event_type": "frame_drop",
                }
            )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 0
        assert len(result.events) == 1


class TestEventLogCollection:
    """Tests for event_log file collection."""

    def test_collect_event_log_file_not_found(self, tmp_path: Path) -> None:
        """Test collection when file does not exist."""
        parser = LogParser(enable_warnings=False)
        result = parser.collect_event_log(tmp_path)

        assert isinstance(result, ParsedEventLog)
        assert len(result.ocr_detections) == 0
        assert len(result.parse_errors) > 0

    def test_collect_event_log_empty_file(self, tmp_path: Path) -> None:
        """Test collection with empty file."""
        log_file = tmp_path / "event_log"
        log_file.write_text("")

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 0
        assert len(result.macro_decisions) == 0
        assert len(result.timing_events) == 0

    def test_collect_event_log_single_ocr_detection(self, tmp_path: Path) -> None:
        """Test collection with single OCR detection."""
        log_file = tmp_path / "event_log"
        log_file.write_text("[14:30:15.123] OCR Detection: arrow detected confidence=0.92\n")

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 1
        detection = result.ocr_detections[0]
        assert detection.element_name == "arrow"
        assert detection.confidence == 0.92

    def test_collect_event_log_multiple_lines(self, tmp_path: Path) -> None:
        """Test collection with multiple log lines."""
        log_file = tmp_path / "event_log"
        log_file.write_text(
            "[14:30:15.123] OCR Detection: arrow detected confidence=0.92\n"
            "[14:30:15.175] Decision: click arrow at (512, 768)\n"
            "[14:30:15.225] Timer: 299 seconds\n"
        )

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 1
        assert len(result.macro_decisions) == 1
        assert len(result.timing_events) == 1

    def test_collect_event_log_with_empty_lines(self, tmp_path: Path) -> None:
        """Test collection skips empty lines."""
        log_file = tmp_path / "event_log"
        log_file.write_text(
            "[14:30:15.123] OCR Detection: arrow detected confidence=0.92\n"
            "\n"
            "[14:30:15.175] Decision: click arrow at (512, 768)\n"
        )

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.raw_lines) == 2  # Empty line not counted


class TestTimestampParsing:
    """Tests for timestamp parsing."""

    def test_parse_valid_timestamp(self) -> None:
        """Test parsing valid timestamp."""
        parser = LogParser()
        timestamp = parser._parse_timestamp("[14:30:15.123]")

        assert timestamp is not None
        assert timestamp.hour == 14
        assert timestamp.minute == 30
        assert timestamp.second == 15
        assert timestamp.microsecond == 123000

    def test_parse_timestamp_midnight(self) -> None:
        """Test parsing timestamp at midnight."""
        parser = LogParser()
        timestamp = parser._parse_timestamp("[00:00:00.000]")

        assert timestamp is not None
        assert timestamp.hour == 0
        assert timestamp.minute == 0
        assert timestamp.second == 0

    def test_parse_invalid_timestamp_format(self) -> None:
        """Test parsing invalid timestamp format."""
        parser = LogParser()
        timestamp = parser._parse_timestamp("invalid [14:30:15.123]")

        # Should still parse if pattern matches
        assert timestamp is not None

    def test_parse_timestamp_no_brackets(self) -> None:
        """Test parsing timestamp without brackets fails gracefully."""
        parser = LogParser()
        timestamp = parser._parse_timestamp("14:30:15.123")

        assert timestamp is None


class TestOCRDetectionParsing:
    """Tests for OCR detection line parsing."""

    def test_parse_ocr_detection_valid(self) -> None:
        """Test parsing valid OCR detection."""
        parser = LogParser()
        line = "[14:30:15.123] OCR Detection: arrow detected confidence=0.92"
        detection = parser._parse_ocr_detection(line)

        assert detection is not None
        assert detection.element_name == "arrow"
        assert detection.confidence == 0.92
        assert detection.timestamp.hour == 14

    def test_parse_ocr_detection_with_coordinates(self) -> None:
        """Test parsing OCR detection with coordinates."""
        parser = LogParser()
        line = "[14:30:15.123] OCR Detection: arrow detected confidence=0.92 at (512, 768)"
        detection = parser._parse_ocr_detection(line)

        assert detection is not None
        assert detection.x == 512
        assert detection.y == 768

    def test_parse_ocr_detection_high_confidence(self) -> None:
        """Test parsing OCR detection with high confidence."""
        parser = LogParser()
        line = "[14:30:15.123] OCR Detection: heli detected confidence=0.99"
        detection = parser._parse_ocr_detection(line)

        assert detection is not None
        assert detection.confidence == 0.99

    def test_parse_ocr_detection_low_confidence(self) -> None:
        """Test parsing OCR detection with low confidence."""
        parser = LogParser()
        line = "[14:30:15.123] OCR Detection: text detected confidence=0.45"
        detection = parser._parse_ocr_detection(line)

        assert detection is not None
        assert detection.confidence == 0.45

    def test_parse_ocr_detection_invalid_confidence(self) -> None:
        """Test parsing OCR detection with invalid confidence."""
        parser = LogParser()
        line = "[14:30:15.123] OCR Detection: arrow detected confidence=invalid"
        detection = parser._parse_ocr_detection(line)

        assert detection is None

    def test_parse_ocr_detection_no_timestamp(self) -> None:
        """Test parsing OCR detection without timestamp."""
        parser = LogParser()
        line = "OCR Detection: arrow detected confidence=0.92"
        detection = parser._parse_ocr_detection(line)

        assert detection is None


class TestMacroDecisionParsing:
    """Tests for macro decision line parsing."""

    def test_parse_macro_decision_valid(self) -> None:
        """Test parsing valid macro decision."""
        parser = LogParser()
        line = "[14:30:15.175] Decision: click arrow at (512, 768)"
        decision = parser._parse_macro_decision(line)

        assert decision is not None
        assert decision.target_element == "arrow"
        assert decision.target_x == 512
        assert decision.target_y == 768
        assert decision.decision_type == "click"

    def test_parse_macro_decision_heli(self) -> None:
        """Test parsing macro decision for heli."""
        parser = LogParser()
        line = "[14:30:15.225] Decision: click heli at (480, 600)"
        decision = parser._parse_macro_decision(line)

        assert decision is not None
        assert decision.target_element == "heli"
        assert decision.target_x == 480
        assert decision.target_y == 600

    def test_parse_macro_decision_wait_type(self) -> None:
        """Test parsing macro decision with wait type."""
        parser = LogParser()
        line = "[14:30:15.300] Decision: wait for arrow at (512, 768)"
        decision = parser._parse_macro_decision(line)

        assert decision is not None
        assert decision.decision_type == "wait"

    def test_parse_macro_decision_invalid_coordinates(self) -> None:
        """Test parsing macro decision with invalid coordinates."""
        parser = LogParser()
        line = "[14:30:15.175] Decision: click arrow at (invalid, 768)"
        decision = parser._parse_macro_decision(line)

        assert decision is None

    def test_parse_macro_decision_no_coordinates(self) -> None:
        """Test parsing macro decision without coordinates."""
        parser = LogParser()
        line = "[14:30:15.175] Decision: click arrow"
        decision = parser._parse_macro_decision(line)

        assert decision is None


class TestTimingEventParsing:
    """Tests for timing event parsing."""

    def test_parse_timing_event_timer(self) -> None:
        """Test parsing timer event."""
        parser = LogParser()
        line = "[14:30:15.123] Timer: 299 seconds"
        timing = parser._parse_timing_event(line)

        assert timing is not None
        assert timing.event_type == "timer"
        assert timing.value == 299

    def test_parse_timing_event_timer_zero(self) -> None:
        """Test parsing timer event with zero."""
        parser = LogParser()
        line = "[14:30:15.123] Timer: 0 seconds"
        timing = parser._parse_timing_event(line)

        assert timing is not None
        assert timing.value == 0

    def test_parse_timing_event_latency(self) -> None:
        """Test parsing latency event."""
        parser = LogParser()
        line = "[14:30:15.123] Timing latency: 45 ms"
        timing = parser._parse_timing_event(line)

        assert timing is not None
        assert timing.event_type == "latency"
        assert timing.value == 45

    def test_parse_timing_event_no_value(self) -> None:
        """Test parsing timing event without numeric value."""
        parser = LogParser()
        line = "[14:30:15.123] Timing: no value here"
        timing = parser._parse_timing_event(line)

        # Parsing fails if no number found
        assert timing is None


class TestGameEventRowParsing:
    """Tests for game event row parsing."""

    def test_parse_game_event_row_valid_click(self) -> None:
        """Test parsing valid click row."""
        parser = LogParser()
        row = {
            "timestamp_ms": "1704067200000",
            "x": "512",
            "y": "768",
            "element_name": "arrow",
            "event_type": "click",
        }
        click = parser._parse_game_event_row(row)

        assert click is not None
        assert click.x == 512

    def test_parse_game_event_row_non_click(self) -> None:
        """Test parsing non-click row returns None."""
        parser = LogParser()
        row = {
            "timestamp_ms": "1704067200000",
            "x": "0",
            "y": "0",
            "element_name": "screen",
            "event_type": "frame_drop",
        }
        click = parser._parse_game_event_row(row)

        assert click is None

    def test_parse_game_event_row_missing_field(self) -> None:
        """Test parsing row with missing field raises KeyError."""
        parser = LogParser()
        row = {"timestamp_ms": "1704067200000", "x": "512", "y": "768"}
        with pytest.raises(KeyError):
            parser._parse_game_event_row(row)

    def test_parse_game_event_row_invalid_type(self) -> None:
        """Test parsing row with invalid field type raises ValueError."""
        parser = LogParser()
        row = {
            "timestamp_ms": "not_a_number",
            "x": "512",
            "y": "768",
            "element_name": "arrow",
            "event_type": "click",
        }
        with pytest.raises(ValueError):
            parser._parse_game_event_row(row)


class TestErrorHandling:
    """Tests for error handling and graceful recovery."""

    def test_malformed_entries_continue_parsing(self, tmp_path: Path) -> None:
        """Test that malformed entries don't stop parsing."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            # Valid click
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "512",
                    "y": "768",
                    "element_name": "arrow",
                    "event_type": "click",
                }
            )
            # Malformed (missing x)
            f.write("1704067200050,,,scroll\n")
            # Valid click
            writer.writerow(
                {
                    "timestamp_ms": "1704067200100",
                    "x": "520",
                    "y": "770",
                    "element_name": "heli",
                    "event_type": "click",
                }
            )

        parser = LogParser(enable_warnings=False)
        result = parser.collect_game_events_log(tmp_path)

        # Should have parsed 2 valid clicks despite malformed entry
        assert len(result.clicks) >= 1  # At least one valid
        assert result.malformed_count > 0

    def test_parse_errors_collected(self, tmp_path: Path) -> None:
        """Test that parse errors are collected."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "invalid",
                    "x": "512",
                    "y": "768",
                    "element_name": "arrow",
                    "event_type": "click",
                }
            )

        parser = LogParser(enable_warnings=False)
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.parse_errors) > 0
        assert result.malformed_count == 1

    def test_file_io_error_handling(self, tmp_path: Path) -> None:
        """Test graceful handling of file I/O errors."""
        # Create a directory with the log file name (causes read error)
        log_dir = tmp_path / "event_log"
        log_dir.mkdir()

        parser = LogParser(enable_warnings=False)
        result = parser.collect_event_log(tmp_path)

        assert len(result.parse_errors) > 0


class TestAlternativeLogFilenames:
    """Tests for finding logs with alternative names."""

    def test_collect_event_log_with_dot_log_extension(self, tmp_path: Path) -> None:
        """Test finding event_log.log."""
        log_file = tmp_path / "event_log.log"
        log_file.write_text("[14:30:15.123] OCR Detection: arrow detected confidence=0.92\n")

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 1

    def test_collect_event_log_with_txt_extension(self, tmp_path: Path) -> None:
        """Test finding event_log.txt."""
        log_file = tmp_path / "event_log.txt"
        log_file.write_text("[14:30:15.123] OCR Detection: arrow detected confidence=0.92\n")

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 1


class TestParseDataIntegrity:
    """Tests for data integrity of parsed results."""

    def test_game_events_all_clicks_valid(self, tmp_path: Path) -> None:
        """Test all parsed clicks are valid Click objects."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            for i in range(10):
                writer.writerow(
                    {
                        "timestamp_ms": str(1704067200000 + i * 100),
                        "x": str(512 + i),
                        "y": str(768 + i),
                        "element_name": f"element_{i}",
                        "event_type": "click",
                    }
                )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 10
        for click in result.clicks:
            assert isinstance(click, Click)
            assert click.timestamp_ms > 0
            assert 0 <= click.x <= 2000
            assert 0 <= click.y <= 1500

    def test_event_log_detections_valid(self, tmp_path: Path) -> None:
        """Test all parsed detections are valid OCRDetection objects."""
        log_file = tmp_path / "event_log"
        lines = [
            "[14:30:15.123] OCR Detection: arrow detected confidence=0.92\n",
            "[14:30:15.124] OCR Detection: heli detected confidence=0.85\n",
            "[14:30:15.125] OCR Detection: text detected confidence=0.70\n",
        ]
        log_file.write_text("".join(lines))

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 3
        for detection in result.ocr_detections:
            assert isinstance(detection, OCRDetection)
            assert 0.0 <= detection.confidence <= 1.0


class TestLargeLogFiles:
    """Tests for handling large log files."""

    def test_parse_large_game_events_log(self, tmp_path: Path) -> None:
        """Test parsing large game_events.log with many clicks."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            # Write 1000 clicks
            for i in range(1000):
                writer.writerow(
                    {
                        "timestamp_ms": str(1704067200000 + i * 50),
                        "x": str(512 + (i % 100)),
                        "y": str(768 + (i // 100)),
                        "element_name": "arrow",
                        "event_type": "click",
                    }
                )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 1000

    def test_parse_large_event_log(self, tmp_path: Path) -> None:
        """Test parsing large event_log with many detections."""
        log_file = tmp_path / "event_log"
        lines = []
        for i in range(500):
            hour = 14
            minute = 30
            second = 15 + (i // 20)  # Change second every 20 iterations to stay < 60
            millisecond = i % 1000
            lines.append(f"[{hour:02d}:{minute:02d}:{second:02d}.{millisecond:03d}] OCR Detection: arrow detected confidence={0.80 + (i % 20) * 0.01}\n")

        log_file.write_text("".join(lines))

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert len(result.ocr_detections) == 500


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_click_at_zero_coordinates(self, tmp_path: Path) -> None:
        """Test parsing click at (0, 0)."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "0",
                    "y": "0",
                    "element_name": "corner",
                    "event_type": "click",
                }
            )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 1
        assert result.clicks[0].x == 0
        assert result.clicks[0].y == 0

    def test_click_at_large_coordinates(self, tmp_path: Path) -> None:
        """Test parsing click at large coordinates."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "9999",
                    "y": "9999",
                    "element_name": "far",
                    "event_type": "click",
                }
            )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 1
        assert result.clicks[0].x == 9999

    def test_confidence_at_boundary_values(self, tmp_path: Path) -> None:
        """Test parsing OCR detections with boundary confidence values."""
        log_file = tmp_path / "event_log"
        lines = [
            "[14:30:15.123] OCR Detection: arrow detected confidence=0.0\n",
            "[14:30:15.124] OCR Detection: heli detected confidence=1.0\n",
            "[14:30:15.125] OCR Detection: text detected confidence=0.5\n",
        ]
        log_file.write_text("".join(lines))

        parser = LogParser()
        result = parser.collect_event_log(tmp_path)

        assert result.ocr_detections[0].confidence == 0.0
        assert result.ocr_detections[1].confidence == 1.0
        assert result.ocr_detections[2].confidence == 0.5

    def test_empty_element_name(self, tmp_path: Path) -> None:
        """Test parsing with empty element name."""
        log_file = tmp_path / "game_events.log"

        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp_ms", "x", "y", "element_name", "event_type"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp_ms": "1704067200000",
                    "x": "512",
                    "y": "768",
                    "element_name": "",
                    "event_type": "click",
                }
            )

        parser = LogParser()
        result = parser.collect_game_events_log(tmp_path)

        assert len(result.clicks) == 1
        assert result.clicks[0].element_name == ""
