"""
Integration tests for loading and validating .config.kiro files.

Tests verify that:
- Configuration files can be loaded from JSON
- Validation errors are reported with helpful messages
- All schemas work together in real-world scenarios
"""

import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("macro_test_framework")

from macro_test_framework.config import (
    load_config_from_file,
    validate_stub_config,
    validate_scenario_config,
    validate_report_config,
    FrameworkConfig,
)
from pydantic import ValidationError


class TestConfigFileLoading:
    """Tests for loading configuration from files."""

    def test_load_valid_stub_config_from_file(self):
        """Test loading valid stub config from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "template_name": "1_scan_chat_with_arrow.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 50,
                "window_width": 1024,
                "window_height": 768,
            }
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            loaded_data = load_config_from_file(temp_path)
            assert loaded_data["template_name"] == "1_scan_chat_with_arrow.png"

            # Validate loaded data
            config = validate_stub_config(loaded_data)
            assert config.timer_seconds == 300
        finally:
            temp_path.unlink()

    def test_load_file_not_found(self):
        """Test that missing file raises FileNotFoundError."""
        nonexistent_path = Path("nonexistent_config.json")
        with pytest.raises(FileNotFoundError):
            load_config_from_file(nonexistent_path)

    def test_load_malformed_json(self):
        """Test that malformed JSON raises JSONDecodeError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            temp_path = Path(f.name)

        try:
            with pytest.raises(json.JSONDecodeError):
                load_config_from_file(temp_path)
        finally:
            temp_path.unlink()


class TestRealWorldScenarios:
    """Tests for real-world configuration scenarios."""

    def test_baseline_scenario_config(self):
        """Test loading and validating a complete baseline scenario."""
        config_data = {
            "scenario_id": "baseline_001",
            "category": "baseline",
            "stub_config": {
                "template_name": "1_scan_chat_with_arrow.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 0,
                "window_width": 1024,
                "window_height": 768,
                "chat_visible": True,
                "has_arrow": True,
                "events": [],
                "dpi_scale": 1.0,
                "glitch_probability": 0.0,
                "is_clipped": False,
            },
            "timeout_seconds": 60,
        }

        config = validate_scenario_config(config_data)
        assert config.scenario_id == "baseline_001"
        assert config.category == "baseline"
        assert config.stub_config.timer_seconds == 300

    def test_stress_scenario_with_events(self):
        """Test loading stress scenario with events."""
        config_data = {
            "scenario_id": "stress_001",
            "category": "stress",
            "stub_config": {
                "template_name": "helka_scrolled.png",
                "timer_seconds": 30,
                "timer_jitter_ms": 500,
                "window_width": 1280,
                "window_height": 1024,
                "chat_visible": True,
                "has_arrow": True,
                "events": [
                    {
                        "delay_ms": 5000,
                        "event_type": "chat_scroll",
                        "parameters": {"magnitude": 30},
                    },
                    {
                        "delay_ms": 10000,
                        "event_type": "heli_appear",
                        "parameters": {"scroll_duration": 4000},
                    },
                    {
                        "delay_ms": 15000,
                        "event_type": "frame_drop",
                        "parameters": {},
                    },
                ],
                "dpi_scale": 1.5,
                "glitch_probability": 0.8,
                "is_clipped": True,
            },
            "timeout_seconds": 120,
        }

        config = validate_scenario_config(config_data)
        assert config.category == "stress"
        assert len(config.stub_config.events) == 3
        assert config.stub_config.glitch_probability == 0.8

    def test_window_variation_scenario(self):
        """Test loading window variation scenario."""
        config_data = {
            "scenario_id": "window_001",
            "category": "window",
            "stub_config": {
                "template_name": "no_chat.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 50,
                "window_width": 640,
                "window_height": 480,
                "window_x": 0,
                "window_y": 0,
            },
            "timeout_seconds": 60,
        }

        config = validate_scenario_config(config_data)
        assert config.stub_config.window_width == 640
        assert config.stub_config.window_height == 480


class TestErrorReporting:
    """Tests for error message quality."""

    def test_multiple_validation_errors(self):
        """Test that multiple errors are all reported."""
        config_data = {
            "scenario_id": "test",
            "category": "baseline",
            "stub_config": {
                "template_name": "invalid_template.png",  # Invalid
                "timer_seconds": 400,  # Out of range
                "timer_jitter_ms": 25,  # Invalid value
                "window_width": 500,  # Out of range
                "window_height": 1500,  # Out of range
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_scenario_config(config_data)

        # Verify multiple errors are collected
        errors = exc_info.value.errors()
        assert len(errors) > 1

    def test_stub_config_error_message_includes_valid_values(self):
        """Test that error messages include what values are allowed."""
        config_data = {
            "template_name": "wrong_template.png",
            "timer_seconds": 300,
            "timer_jitter_ms": 0,
            "window_width": 1024,
            "window_height": 768,
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_stub_config(config_data)

        error_str = str(exc_info.value)
        # Error should indicate what templates are valid
        assert "template" in error_str.lower()

    def test_timer_jitter_error_message_helpful(self):
        """Test that timer_jitter error explains valid values."""
        config_data = {
            "template_name": "no_chat.png",
            "timer_seconds": 300,
            "timer_jitter_ms": 100,  # Invalid: should be 0, 50, or 500
            "window_width": 1024,
            "window_height": 768,
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_stub_config(config_data)

        error_str = str(exc_info.value)
        # Error should mention valid values
        assert "0" in error_str or "50" in error_str or "500" in error_str

    def test_timeout_range_error_message(self):
        """Test that timeout range error is clear."""
        config_data = {
            "scenario_id": "test",
            "category": "baseline",
            "stub_config": {
                "template_name": "no_chat.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 0,
                "window_width": 1024,
                "window_height": 768,
            },
            "timeout_seconds": 999,  # Out of range (1-300)
        }

        with pytest.raises(ValidationError):
            validate_scenario_config(config_data)


class TestCompleteFrameworkConfig:
    """Tests for complete framework configuration."""

    def test_full_framework_config_from_dict(self):
        """Test creating complete FrameworkConfig from dictionary."""
        config_dict = {
            "stub_config": {
                "template_name": "1_scan_chat_with_arrow.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 50,
                "window_width": 1024,
                "window_height": 768,
            },
            "scenario_config": {
                "scenario_id": "test_001",
                "category": "baseline",
                "stub_config": {
                    "template_name": "1_scan_chat_with_arrow.png",
                    "timer_seconds": 300,
                    "timer_jitter_ms": 0,
                    "window_width": 1024,
                    "window_height": 768,
                },
            },
            "report_config": {
                "console_enabled": True,
                "html_enabled": True,
                "sqlite_enabled": True,
            },
        }

        config = FrameworkConfig(**config_dict)
        assert config.scenario_config.scenario_id == "test_001"
        assert config.report_config.console_enabled is True

    def test_framework_config_with_defaults(self):
        """Test FrameworkConfig using default report config."""
        config_dict = {
            "stub_config": {
                "template_name": "no_chat.png",
                "timer_seconds": 300,
                "timer_jitter_ms": 0,
                "window_width": 1024,
                "window_height": 768,
            },
            "scenario_config": {
                "scenario_id": "baseline_001",
                "category": "baseline",
                "stub_config": {
                    "template_name": "no_chat.png",
                    "timer_seconds": 300,
                    "timer_jitter_ms": 0,
                    "window_width": 1024,
                    "window_height": 768,
                },
            },
        }

        config = FrameworkConfig(**config_dict)
        # Should use default report config
        assert config.report_config.console_enabled is True
        assert config.report_config.html_enabled is True
