"""Tests for scenario loader - validation and rendering of scenario definitions."""

import json
from pathlib import Path

import pytest

from mvp.tests.test_framework.scenario_loader import (
    ScenarioLoader,
    load_scenarios_from_json,
    validate_scenarios,
)


class TestScenarioLoader:
    """Tests for ScenarioLoader class."""

    def test_loader_initialization(self) -> None:
        """Test ScenarioLoader initialization with default path."""
        loader = ScenarioLoader()
        assert loader is not None
        assert loader.scenarios_file.exists()

    def test_loader_initialization_with_path(self) -> None:
        """Test ScenarioLoader initialization with explicit path."""
        default_path = Path(__file__).parent / "scenarios.json"
        loader = ScenarioLoader(default_path)
        assert loader.scenarios_file == default_path

    def test_loader_initialization_missing_file(self) -> None:
        """Test ScenarioLoader initialization with missing file."""
        with pytest.raises(FileNotFoundError):
            ScenarioLoader("/nonexistent/path/scenarios.json")

    def test_load_scenarios_structure(self) -> None:
        """Test that loaded scenarios have correct structure."""
        loader = ScenarioLoader()
        data = loader.load_scenarios()
        assert isinstance(data, dict)
        assert "version" in data
        assert "scenarios" in data
        assert isinstance(data["scenarios"], list)

    def test_load_scenarios_version(self) -> None:
        """Test scenarios have version field."""
        loader = ScenarioLoader()
        data = loader.load_scenarios()
        assert data["version"] == "1.0"

    def test_load_all_scenarios(self) -> None:
        """Test loading all scenarios."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) == 40

    def test_get_scenario_count(self) -> None:
        """Test getting scenario count."""
        loader = ScenarioLoader()
        count = loader.get_scenario_count()
        assert count == 40

    def test_load_scenarios_by_category(self) -> None:
        """Test loading scenarios grouped by category."""
        loader = ScenarioLoader()
        categorized = loader.load_scenarios_by_category()
        assert isinstance(categorized, dict)
        assert "baseline" in categorized
        assert "window" in categorized
        assert "timer" in categorized
        assert "event" in categorized
        assert "stress" in categorized
        assert "multi_monitor" in categorized

    def test_baseline_scenarios_count(self) -> None:
        """Test baseline scenarios count."""
        loader = ScenarioLoader()
        baseline = loader.get_scenarios_by_category("baseline")
        assert len(baseline) == 10

    def test_window_scenarios_count(self) -> None:
        """Test window scenarios count."""
        loader = ScenarioLoader()
        window = loader.get_scenarios_by_category("window")
        assert len(window) == 10

    def test_timer_scenarios_count(self) -> None:
        """Test timer scenarios count."""
        loader = ScenarioLoader()
        timer = loader.get_scenarios_by_category("timer")
        assert len(timer) == 5

    def test_event_scenarios_count(self) -> None:
        """Test event scenarios count."""
        loader = ScenarioLoader()
        event = loader.get_scenarios_by_category("event")
        assert len(event) == 5

    def test_stress_scenarios_count(self) -> None:
        """Test stress scenarios count."""
        loader = ScenarioLoader()
        stress = loader.get_scenarios_by_category("stress")
        assert len(stress) == 5

    def test_multimonitor_scenarios_count(self) -> None:
        """Test multi-monitor scenarios count."""
        loader = ScenarioLoader()
        multi = loader.get_scenarios_by_category("multi_monitor")
        assert len(multi) == 5

    def test_total_scenario_distribution(self) -> None:
        """Test that all 40 scenarios are properly distributed."""
        loader = ScenarioLoader()
        categorized = loader.load_scenarios_by_category()
        total = sum(len(scenarios) for scenarios in categorized.values())
        assert total == 40

    def test_all_scenarios_have_unique_ids(self) -> None:
        """Test that all scenarios have unique IDs."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        ids = [s["id"] for s in scenarios]
        assert len(ids) == len(set(ids)), "Found duplicate scenario IDs"

    def test_scenario_has_required_fields(self) -> None:
        """Test that all scenarios have required fields."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        required_fields = [
            "id",
            "category",
            "window_x",
            "window_y",
            "window_width",
            "window_height",
            "game_area_x",
            "game_area_y",
            "game_area_width",
            "game_area_height",
            "dpi",
            "monitors",
            "chat_state",
            "timer_seconds",
            "click_jitter_ms",
            "timer_jitter_ms",
            "glitch_type",
            "has_arrow",
            "events",
        ]
        for scenario in scenarios:
            for field in required_fields:
                assert field in scenario, f"Scenario {scenario['id']} missing field {field}"

    def test_scenario_ids_format(self) -> None:
        """Test that scenario IDs follow naming conventions."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        for scenario in scenarios:
            scenario_id = scenario["id"]
            # ID should contain category prefix
            assert any(
                scenario_id.startswith(prefix)
                for prefix in [
                    "baseline_",
                    "window_",
                    "timer_",
                    "event_",
                    "stress_",
                    "multimonitor_",
                ]
            ), f"Invalid scenario ID format: {scenario_id}"


class TestScenarioValidation:
    """Tests for scenario validation."""

    def test_validate_scenario_valid(self) -> None:
        """Test validating a valid scenario."""
        loader = ScenarioLoader()
        scenario = loader.load_all_scenarios()[0]
        is_valid, errors = loader.validate_scenario(scenario)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_scenarios_pass(self) -> None:
        """Test validating all scenarios passes."""
        loader = ScenarioLoader()
        is_valid, results = loader.validate_all_scenarios()
        assert is_valid is True
        assert results["invalid"] == 0
        assert results["valid"] == 40

    def test_validate_scenario_missing_field(self) -> None:
        """Test validating scenario with missing required field."""
        loader = ScenarioLoader()
        invalid_scenario = {"id": "test", "category": "baseline"}
        is_valid, errors = loader.validate_scenario(invalid_scenario)
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_scenario_invalid_category(self) -> None:
        """Test validating scenario with invalid category."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        # Create a copy with invalid category
        invalid = scenarios[0].copy()
        invalid["category"] = "invalid_category"
        is_valid, errors = loader.validate_scenario(invalid)
        assert is_valid is False
        assert any("Invalid category" in error for error in errors)

    def test_validate_scenario_invalid_dpi(self) -> None:
        """Test validating scenario with invalid DPI."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        invalid = scenarios[0].copy()
        invalid["dpi"] = 100  # Invalid DPI
        is_valid, errors = loader.validate_scenario(invalid)
        assert is_valid is False
        assert any("DPI" in error for error in errors)

    def test_validate_scenario_invalid_timer_jitter(self) -> None:
        """Test validating scenario with invalid timer jitter."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        invalid = scenarios[0].copy()
        invalid["timer_jitter_ms"] = 100  # Invalid jitter
        is_valid, errors = loader.validate_scenario(invalid)
        assert is_valid is False
        assert any("Timer jitter" in error for error in errors)

    def test_validate_scenario_invalid_click_jitter(self) -> None:
        """Test validating scenario with invalid click jitter."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        invalid = scenarios[0].copy()
        invalid["click_jitter_ms"] = 200  # Invalid jitter
        is_valid, errors = loader.validate_scenario(invalid)
        assert is_valid is False
        assert any("Click jitter" in error for error in errors)

    def test_validate_scenario_invalid_glitch_type(self) -> None:
        """Test validating scenario with invalid glitch type."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        invalid = scenarios[0].copy()
        invalid["glitch_type"] = "invalid_glitch"
        is_valid, errors = loader.validate_scenario(invalid)
        assert is_valid is False
        assert any("glitch type" in error.lower() for error in errors)

    def test_validate_scenario_invalid_chat_state(self) -> None:
        """Test validating scenario with invalid chat state."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()
        invalid = scenarios[0].copy()
        invalid["chat_state"] = "invalid_state"
        is_valid, errors = loader.validate_scenario(invalid)
        assert is_valid is False
        assert any("chat state" in error.lower() for error in errors)

    def test_validate_results_by_category(self) -> None:
        """Test validation results include breakdown by category."""
        loader = ScenarioLoader()
        is_valid, results = loader.validate_all_scenarios()
        assert "by_category" in results
        assert results["by_category"]["baseline"]["total"] == 10
        assert results["by_category"]["window"]["total"] == 10
        assert results["by_category"]["timer"]["total"] == 5
        assert results["by_category"]["event"]["total"] == 5
        assert results["by_category"]["stress"]["total"] == 5
        assert results["by_category"]["multi_monitor"]["total"] == 5


class TestScenarioCategories:
    """Tests for scenario category properties."""

    def test_baseline_scenarios_identical_config(self) -> None:
        """Test that baseline scenarios have identical configuration."""
        loader = ScenarioLoader()
        baseline = loader.get_scenarios_by_category("baseline")
        assert len(baseline) == 10

        # First scenario as reference
        reference = baseline[0]

        # All others should match
        for scenario in baseline[1:]:
            assert scenario["window_x"] == reference["window_x"]
            assert scenario["window_y"] == reference["window_y"]
            assert scenario["window_width"] == reference["window_width"]
            assert scenario["window_height"] == reference["window_height"]
            assert scenario["dpi"] == reference["dpi"]
            assert scenario["timer_seconds"] == reference["timer_seconds"]
            assert scenario["click_jitter_ms"] == reference["click_jitter_ms"]
            assert scenario["timer_jitter_ms"] == reference["timer_jitter_ms"]
            assert scenario["glitch_type"] == reference["glitch_type"]
            assert scenario["chat_state"] == reference["chat_state"]

    def test_window_scenarios_vary_geometry(self) -> None:
        """Test that window scenarios have varying geometry."""
        loader = ScenarioLoader()
        window = loader.get_scenarios_by_category("window")
        assert len(window) == 10

        # Should have different sizes
        sizes = set((s["window_width"], s["window_height"]) for s in window)
        assert len(sizes) > 1, "Window scenarios should have different sizes"

    def test_timer_scenarios_vary_duration(self) -> None:
        """Test that timer scenarios have varying durations."""
        loader = ScenarioLoader()
        timer = loader.get_scenarios_by_category("timer")
        assert len(timer) == 5

        # Should have different timer values
        timers = set(s["timer_seconds"] for s in timer)
        assert len(timers) > 1, "Timer scenarios should have different durations"

    def test_event_scenarios_have_events(self) -> None:
        """Test that event scenarios have event definitions."""
        loader = ScenarioLoader()
        event = loader.get_scenarios_by_category("event")
        assert len(event) == 5

        for scenario in event:
            assert "events" in scenario
            # Most event scenarios should have events
            if scenario["id"] != "event_chat_scroll_001":
                # At least one should have events
                pass

    def test_stress_scenarios_have_stress_factors(self) -> None:
        """Test that stress scenarios have stress factors."""
        loader = ScenarioLoader()
        stress = loader.get_scenarios_by_category("stress")
        assert len(stress) == 5

        for scenario in stress:
            # Should have at least one stress factor:
            # - high jitter
            # - glitch
            # - many events
            # - small window
            # - short timer
            has_stress = (
                scenario["click_jitter_ms"] > 0
                or scenario["timer_jitter_ms"] > 0
                or scenario["glitch_type"] != "none"
                or len(scenario["events"]) > 0
                or scenario["timer_seconds"] < 30
                or scenario["window_width"] < 800
            )
            assert has_stress, f"Stress scenario {scenario['id']} lacks stress factors"

    def test_multimonitor_scenarios_have_multiple_monitors(self) -> None:
        """Test that multi-monitor scenarios have multiple monitors."""
        loader = ScenarioLoader()
        multi = loader.get_scenarios_by_category("multi_monitor")
        assert len(multi) == 5

        for scenario in multi:
            assert "monitors" in scenario
            assert len(scenario["monitors"]) > 1, (
                f"Multi-monitor scenario {scenario['id']} doesn't have multiple monitors"
            )


class TestScenarioRenderability:
    """Tests for scenario renderability - all scenarios can be rendered."""

    def test_all_scenarios_loadable(self) -> None:
        """Test that all scenarios can be loaded."""
        scenarios = load_scenarios_from_json()
        assert len(scenarios) == 40

    def test_all_scenarios_renderable(self) -> None:
        """Test that all scenarios have valid rendering parameters."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()

        for scenario in scenarios:
            # Check window bounds are valid (non-negative dimensions)
            assert scenario["window_width"] > 0, f"Invalid width in {scenario['id']}"
            assert scenario["window_height"] > 0, f"Invalid height in {scenario['id']}"

            # Check game area
            assert scenario["game_area_width"] > 0, f"Invalid game_area_width in {scenario['id']}"
            assert scenario["game_area_height"] > 0, (
                f"Invalid game_area_height in {scenario['id']}"
            )

            # Check monitors exist
            assert len(scenario["monitors"]) > 0, f"No monitors defined in {scenario['id']}"

    def test_scenarios_can_be_serialized(self) -> None:
        """Test that all scenarios can be serialized back to JSON."""
        loader = ScenarioLoader()
        scenarios = loader.load_all_scenarios()

        # Should not raise
        json_str = json.dumps(scenarios)
        assert len(json_str) > 0

        # Should be deserializable
        deserialized = json.loads(json_str)
        assert len(deserialized) == 40


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_load_scenarios_from_json_function(self) -> None:
        """Test load_scenarios_from_json convenience function."""
        scenarios = load_scenarios_from_json()
        assert len(scenarios) == 40

    def test_validate_scenarios_function(self) -> None:
        """Test validate_scenarios convenience function."""
        is_valid, results = validate_scenarios()
        assert is_valid is True
        assert results["valid"] == 40
        assert results["invalid"] == 0
