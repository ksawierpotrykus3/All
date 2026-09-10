"""
Unit tests for configuration schema validation (Pydantic v2).

Tests verify that:
- StubConfig validates all parameters correctly
- ScenarioConfig validates scenario-level parameters
- ReportConfig validates reporting settings
- Helpful error messages are provided for invalid inputs
- All edge cases and boundary values are handled
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

pytest.importorskip("macro_test_framework")

from macro_test_framework.config import (
    GameEvent,
    StubConfig,
    ScenarioConfig,
    ReportConfig,
    FrameworkConfig,
    validate_stub_config,
    validate_scenario_config,
    validate_report_config,
)


class TestGameEvent:
    """Tests for GameEvent schema."""

    def test_valid_game_event_chat_scroll(self):
        """Test valid chat_scroll event."""
        event = GameEvent(
            delay_ms=5000,
            event_type="chat_scroll",
            parameters={"magnitude": 20},
        )
        assert event.delay_ms == 5000
        assert event.event_type == "chat_scroll"
        assert event.parameters["magnitude"] == 20

    def test_valid_game_event_heli_appear(self):
        """Test valid heli_appear event."""
        event = GameEvent(
            delay_ms=10000,
            event_type="heli_appear",
            parameters={"scroll_duration": 4000},
        )
        assert event.delay_ms == 10000
        assert event.event_type == "heli_appear"

    def test_valid_game_event_frame_drop(self):
        """Test valid frame_drop event."""
        event = GameEvent(
            delay_ms=0,
            event_type="frame_drop",
        )
        assert event.delay_ms == 0
        assert event.event_type == "frame_drop"

    def test_invalid_event_type(self):
        """Test rejection of invalid event type."""
        with pytest.raises(ValidationError) as exc_info:
            GameEvent(
                delay_ms=5000,
                event_type="invalid_event",
            )
        assert "invalid_event" in str(exc_info.value)

    def test_negative_delay_rejected(self):
        """Test rejection of negative delay."""
        with pytest.raises(ValidationError):
            GameEvent(delay_ms=-100, event_type="chat_scroll")

    def test_zero_delay_allowed(self):
        """Test that zero delay is allowed."""
        event = GameEvent(delay_ms=0, event_type="frame_drop")
        assert event.delay_ms == 0


class TestStubConfig:
    """Tests for StubConfig schema."""

    def test_valid_baseline_stub_config(self):
        """Test valid baseline stub configuration."""
        config = StubConfig(
            template_name="1_scan_chat_with_arrow.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        assert config.template_name == "1_scan_chat_with_arrow.png"
        assert config.timer_seconds == 300
        assert config.timer_jitter_ms == 0
        assert config.window_width == 1024
        assert config.window_height == 768
        assert config.dpi_scale == 1.0
        assert config.glitch_probability == 0.0

    def test_valid_all_templates(self):
        """Test all valid template names."""
        templates = [
            "no_chat.png",
            "1_scan_chat_without_arrow.png",
            "1_scan_chat_with_arrow.png",
            "details.png",
            "helka_scrolled.png",
        ]
        for template in templates:
            config = StubConfig(
                template_name=template,
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
            )
            assert config.template_name == template

    def test_invalid_template_name(self):
        """Test rejection of invalid template name."""
        with pytest.raises(ValidationError) as exc_info:
            StubConfig(
                template_name="invalid_template.png",
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
            )
        errors = exc_info.value.errors()
        assert any("Invalid template name" in str(err) for err in errors)

    def test_timer_seconds_boundary_values(self):
        """Test timer_seconds with boundary values."""
        # Valid minimum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=5,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        assert config.timer_seconds == 5

        # Valid maximum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        assert config.timer_seconds == 300

    def test_timer_seconds_out_of_range_low(self):
        """Test rejection of timer_seconds below minimum."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=4,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
            )

    def test_timer_seconds_out_of_range_high(self):
        """Test rejection of timer_seconds above maximum."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=301,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
            )

    def test_timer_jitter_valid_values(self):
        """Test all valid timer_jitter values."""
        for jitter in [0, 50, 500]:
            config = StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=jitter,
                window_width=1024,
                window_height=768,
            )
            assert config.timer_jitter_ms == jitter

    def test_timer_jitter_invalid_value(self):
        """Test rejection of invalid timer_jitter value."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=25,  # Invalid: should be 0, 50, or 500
                window_width=1024,
                window_height=768,
            )

    def test_window_width_boundary_values(self):
        """Test window_width with boundary values."""
        # Minimum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=640,
            window_height=768,
        )
        assert config.window_width == 640

        # Maximum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1280,
            window_height=768,
        )
        assert config.window_width == 1280

    def test_window_width_out_of_range(self):
        """Test rejection of window_width out of range."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=500,
                window_height=768,
            )

    def test_window_height_boundary_values(self):
        """Test window_height with boundary values."""
        # Minimum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=480,
        )
        assert config.window_height == 480

        # Maximum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=1024,
        )
        assert config.window_height == 1024

    def test_window_height_out_of_range(self):
        """Test rejection of window_height out of range."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=1025,
            )

    def test_dpi_scale_boundary_values(self):
        """Test dpi_scale with boundary values."""
        # Minimum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
            dpi_scale=1.0,
        )
        assert config.dpi_scale == 1.0

        # Maximum
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
            dpi_scale=2.0,
        )
        assert config.dpi_scale == 2.0

    def test_dpi_scale_out_of_range(self):
        """Test rejection of dpi_scale out of range."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
                dpi_scale=2.5,
            )

    def test_glitch_probability_boundary_values(self):
        """Test glitch_probability with boundary values."""
        # 0%
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
            glitch_probability=0.0,
        )
        assert config.glitch_probability == 0.0

        # 100%
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
            glitch_probability=1.0,
        )
        assert config.glitch_probability == 1.0

    def test_glitch_probability_out_of_range(self):
        """Test rejection of glitch_probability out of range."""
        with pytest.raises(ValidationError):
            StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
                glitch_probability=1.5,
            )

    def test_events_with_valid_events(self):
        """Test StubConfig with valid events."""
        events = [
            GameEvent(delay_ms=5000, event_type="chat_scroll"),
            GameEvent(delay_ms=10000, event_type="heli_appear"),
        ]
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
            events=events,
        )
        assert len(config.events) == 2

    def test_events_empty_list(self):
        """Test StubConfig with empty events list."""
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
            events=[],
        )
        assert len(config.events) == 0

    def test_default_boolean_values(self):
        """Test default boolean values."""
        config = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        assert config.chat_visible is True
        assert config.has_arrow is True
        assert config.is_clipped is False


class TestScenarioConfig:
    """Tests for ScenarioConfig schema."""

    def test_valid_baseline_scenario(self):
        """Test valid baseline scenario configuration."""
        stub = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        scenario = ScenarioConfig(
            scenario_id="baseline_001",
            category="baseline",
            stub_config=stub,
        )
        assert scenario.scenario_id == "baseline_001"
        assert scenario.category == "baseline"
        assert scenario.timeout_seconds == 60

    def test_valid_all_categories(self):
        """Test all valid scenario categories."""
        categories = ["baseline", "window", "timer", "event", "stress", "multi_monitor"]
        for category in categories:
            stub = StubConfig(
                template_name="no_chat.png",
                timer_seconds=300,
                timer_jitter_ms=0,
                window_width=1024,
                window_height=768,
            )
            scenario = ScenarioConfig(
                scenario_id=f"test_{category}",
                category=category,
                stub_config=stub,
            )
            assert scenario.category == category

    def test_invalid_category(self):
        """Test rejection of invalid category."""
        stub = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        with pytest.raises(ValidationError):
            ScenarioConfig(
                scenario_id="test_invalid",
                category="invalid_category",
                stub_config=stub,
            )

    def test_empty_scenario_id_rejected(self):
        """Test rejection of empty scenario_id."""
        stub = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        with pytest.raises(ValidationError):
            ScenarioConfig(
                scenario_id="",
                category="baseline",
                stub_config=stub,
            )

    def test_whitespace_only_scenario_id_rejected(self):
        """Test rejection of whitespace-only scenario_id."""
        stub = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        with pytest.raises(ValidationError):
            ScenarioConfig(
                scenario_id="   ",
                category="baseline",
                stub_config=stub,
            )

    def test_timeout_boundary_values(self):
        """Test timeout_seconds with boundary values."""
        stub = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        # Minimum
        scenario = ScenarioConfig(
            scenario_id="test_min_timeout",
            category="baseline",
            stub_config=stub,
            timeout_seconds=1,
        )
        assert scenario.timeout_seconds == 1

        # Maximum
        scenario = ScenarioConfig(
            scenario_id="test_max_timeout",
            category="baseline",
            stub_config=stub,
            timeout_seconds=300,
        )
        assert scenario.timeout_seconds == 300

    def test_timeout_out_of_range(self):
        """Test rejection of timeout_seconds out of range."""
        stub = StubConfig(
            template_name="no_chat.png",
            timer_seconds=300,
            timer_jitter_ms=0,
            window_width=1024,
            window_height=768,
        )
        with pytest.raises(ValidationError):
            ScenarioConfig(
                scenario_id="test_timeout",
                category="baseline",
                stub_config=stub,
                timeout_seconds=301,
            )


class TestReportConfig:
    """Tests for ReportConfig schema."""

    def test_valid_report_config_all_enabled(self):
        """Test valid report config with all reporters enabled."""
        config = ReportConfig(
            output_dir=Path("test_results"),
            console_enabled=True,
            html_enabled=True,
            sqlite_enabled=True,
        )
        assert config.console_enabled is True
        assert config.html_enabled is True
        assert config.sqlite_enabled is True

    def test_console_only_enabled(self):
        """Test valid config with only console enabled."""
        config = ReportConfig(
            console_enabled=True,
            html_enabled=False,
            sqlite_enabled=False,
        )
        assert config.console_enabled is True

    def test_html_only_enabled(self):
        """Test valid config with only HTML enabled."""
        config = ReportConfig(
            console_enabled=False,
            html_enabled=True,
            sqlite_enabled=False,
        )
        assert config.html_enabled is True

    def test_sqlite_only_enabled(self):
        """Test valid config with only SQLite enabled."""
        config = ReportConfig(
            console_enabled=False,
            html_enabled=False,
            sqlite_enabled=True,
        )
        assert config.sqlite_enabled is True

    def test_all_reporters_disabled_rejected(self):
        """Test rejection when all reporters are disabled."""
        with pytest.raises(ValidationError) as exc_info:
            ReportConfig(
                console_enabled=False,
                html_enabled=False,
                sqlite_enabled=False,
            )
        errors = exc_info.value.errors()
        assert any("At least one report type" in str(err) for err in errors)

    def test_default_values(self):
        """Test default report config values."""
        config = ReportConfig()
        assert config.console_enabled is True
        assert config.html_enabled is True
        assert config.sqlite_enabled is True
        assert config.output_dir == Path("test_results")
        assert config.database_path == Path("test_results/test_results.db")
        assert config.html_report_path == Path("test_results/test_report.html")


class TestFrameworkConfig:
    """Tests for top-level FrameworkConfig schema."""

    def test_valid_framework_config(self):
        """Test valid complete framework configuration."""
        stub = StubConfig(
            template_name="1_scan_chat_with_arrow.png",
            timer_seconds=300,
            timer_jitter_ms=50,
            window_width=1024,
            window_height=768,
        )
        scenario = ScenarioConfig(
            scenario_id="test_001",
            category="baseline",
            stub_config=stub,
        )
        report = ReportConfig()

        config = FrameworkConfig(
            stub_config=stub,
            scenario_config=scenario,
            report_config=report,
        )

        assert config.stub_config == stub
        assert config.scenario_config == scenario
        assert config.report_config == report


class TestValidationFunctions:
    """Tests for standalone validation functions."""

    def test_validate_stub_config_success(self):
        """Test validate_stub_config with valid data."""
        data = {
            "template_name": "no_chat.png",
            "timer_seconds": 300,
            "timer_jitter_ms": 0,
            "window_width": 1024,
            "window_height": 768,
        }
        config = validate_stub_config(data)
        assert config.template_name == "no_chat.png"

    def test_validate_stub_config_failure(self):
        """Test validate_stub_config with invalid data."""
        data = {
            "template_name": "invalid.png",
            "timer_seconds": 300,
            "timer_jitter_ms": 0,
            "window_width": 1024,
            "window_height": 768,
        }
        with pytest.raises(ValidationError):
            validate_stub_config(data)

    def test_validate_scenario_config_success(self):
        """Test validate_scenario_config with valid data."""
        data = {
            "scenario_id": "test_001",
            "category": "baseline",
            "stub_config": {
                "template_name": "no_chat.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 0,
                "window_width": 1024,
                "window_height": 768,
            },
        }
        config = validate_scenario_config(data)
        assert config.scenario_id == "test_001"

    def test_validate_report_config_success(self):
        """Test validate_report_config with valid data."""
        data = {
            "console_enabled": True,
            "html_enabled": True,
            "sqlite_enabled": True,
        }
        config = validate_report_config(data)
        assert config.console_enabled is True
