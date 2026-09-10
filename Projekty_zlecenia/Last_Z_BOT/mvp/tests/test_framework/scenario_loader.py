"""Scenario loader for loading and validating scenario definitions from JSON."""

import json
from pathlib import Path
from typing import Any


class ScenarioLoader:
    """Load and validate scenarios from JSON files."""

    def __init__(self, scenarios_file: str | Path | None = None) -> None:
        """
        Initialize scenario loader.

        Args:
            scenarios_file: Path to scenarios JSON file. If None, uses default location.
        """
        if scenarios_file is None:
            # Default location relative to this file
            scenarios_file = Path(__file__).parent / "scenarios.json"
        else:
            scenarios_file = Path(scenarios_file)

        if not scenarios_file.exists():
            raise FileNotFoundError(f"Scenarios file not found: {scenarios_file}")

        self.scenarios_file = scenarios_file

    def load_scenarios(self) -> dict[str, Any]:
        """
        Load scenarios from JSON file.

        Returns:
            Dictionary containing scenarios data with 'version' and 'scenarios' keys.

        Raises:
            json.JSONDecodeError: If JSON is invalid.
            ValueError: If scenarios data is invalid.
        """
        with open(self.scenarios_file, "r") as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict):
            raise ValueError("Root must be an object")

        if "version" not in data:
            raise ValueError("Missing 'version' field")

        if "scenarios" not in data:
            raise ValueError("Missing 'scenarios' field")

        if not isinstance(data["scenarios"], list):
            raise ValueError("'scenarios' must be an array")

        return data

    def load_all_scenarios(self) -> list[dict[str, Any]]:
        """
        Load all scenarios as a list.

        Returns:
            List of scenario dictionaries.
        """
        data = self.load_scenarios()
        return data["scenarios"]

    def load_scenarios_by_category(self) -> dict[str, list[dict[str, Any]]]:
        """
        Load scenarios grouped by category.

        Returns:
            Dictionary mapping category name to list of scenarios in that category.
        """
        scenarios = self.load_all_scenarios()
        categorized: dict[str, list[dict[str, Any]]] = {}

        for scenario in scenarios:
            category = scenario.get("category", "unknown")
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(scenario)

        return categorized

    def get_scenario_count(self) -> int:
        """
        Get total number of scenarios.

        Returns:
            Count of scenarios.
        """
        scenarios = self.load_all_scenarios()
        return len(scenarios)

    def get_scenarios_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get scenarios for a specific category.

        Args:
            category: Category name (baseline, window, timer, event, stress, multi_monitor).

        Returns:
            List of scenarios in the specified category.
        """
        scenarios = self.load_all_scenarios()
        return [s for s in scenarios if s.get("category") == category]

    def validate_scenario(self, scenario: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate a single scenario.

        Args:
            scenario: Scenario dictionary to validate.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors: list[str] = []

        # Required fields
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

        for field in required_fields:
            if field not in scenario:
                errors.append(f"Missing required field: {field}")

        # Validate field types
        if "id" in scenario and not isinstance(scenario["id"], str):
            errors.append("Field 'id' must be a string")

        if "category" in scenario:
            valid_categories = ["baseline", "window", "timer", "event", "stress", "multi_monitor"]
            if scenario["category"] not in valid_categories:
                errors.append(f"Invalid category: {scenario['category']}")

        # Validate numeric fields
        numeric_fields = [
            "window_x",
            "window_y",
            "window_width",
            "window_height",
            "game_area_x",
            "game_area_y",
            "game_area_width",
            "game_area_height",
            "dpi",
            "timer_seconds",
            "click_jitter_ms",
            "timer_jitter_ms",
        ]

        for field in numeric_fields:
            if field in scenario and not isinstance(scenario[field], int):
                errors.append(f"Field '{field}' must be an integer")

        # Validate window sizes (if not baseline, allow more variation)
        if "window_width" in scenario and scenario["window_width"] < 0:
            errors.append("Field 'window_width' must be non-negative")

        if "window_height" in scenario and scenario["window_height"] < 0:
            errors.append("Field 'window_height' must be non-negative")

        # Validate DPI
        if "dpi" in scenario and scenario["dpi"] not in [96, 120, 144]:
            errors.append(f"DPI must be 96, 120, or 144, got {scenario['dpi']}")

        # Validate timer jitter
        if "timer_jitter_ms" in scenario and scenario["timer_jitter_ms"] not in [0, 50, 500]:
            errors.append(f"Timer jitter must be 0, 50, or 500, got {scenario['timer_jitter_ms']}")

        # Validate click jitter
        if "click_jitter_ms" in scenario and scenario["click_jitter_ms"] not in [0, 50, 500]:
            errors.append(f"Click jitter must be 0, 50, or 500, got {scenario['click_jitter_ms']}")

        # Validate glitch type
        if "glitch_type" in scenario:
            valid_glitches = ["none", "frame_drop_at_5", "frame_drop_at_50"]
            if scenario["glitch_type"] not in valid_glitches:
                errors.append(f"Invalid glitch type: {scenario['glitch_type']}")

        # Validate chat state
        if "chat_state" in scenario:
            valid_states = ["closed", "open", "scrolled"]
            if scenario["chat_state"] not in valid_states:
                errors.append(f"Invalid chat state: {scenario['chat_state']}")

        # Validate boolean fields
        if "has_arrow" in scenario and not isinstance(scenario["has_arrow"], bool):
            errors.append("Field 'has_arrow' must be a boolean")

        # Validate monitors array
        if "monitors" in scenario:
            if not isinstance(scenario["monitors"], list):
                errors.append("Field 'monitors' must be an array")
            elif len(scenario["monitors"]) == 0:
                errors.append("Field 'monitors' must have at least one monitor")

        # Validate events array
        if "events" in scenario:
            if not isinstance(scenario["events"], list):
                errors.append("Field 'events' must be an array")

        return len(errors) == 0, errors

    def validate_all_scenarios(self) -> tuple[bool, dict[str, Any]]:
        """
        Validate all scenarios in the file.

        Returns:
            Tuple of (all_valid, validation_results dictionary).
        """
        scenarios = self.load_all_scenarios()
        results = {
            "total": len(scenarios),
            "valid": 0,
            "invalid": 0,
            "by_category": {},
            "errors": {},
        }

        # Collect results by category
        for scenario in scenarios:
            category = scenario.get("category", "unknown")
            if category not in results["by_category"]:
                results["by_category"][category] = {"total": 0, "valid": 0, "invalid": 0}

            is_valid, errors = self.validate_scenario(scenario)

            results["by_category"][category]["total"] += 1

            if is_valid:
                results["valid"] += 1
                results["by_category"][category]["valid"] += 1
            else:
                results["invalid"] += 1
                results["by_category"][category]["invalid"] += 1
                results["errors"][scenario.get("id", "unknown")] = errors

        return results["invalid"] == 0, results


def load_scenarios_from_json(path: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Convenience function to load scenarios from JSON.

    Args:
        path: Path to scenarios JSON file. If None, uses default location.

    Returns:
        List of scenario dictionaries.
    """
    loader = ScenarioLoader(path)
    return loader.load_all_scenarios()


def validate_scenarios(path: str | Path | None = None) -> tuple[bool, dict[str, Any]]:
    """
    Convenience function to validate scenarios from JSON.

    Args:
        path: Path to scenarios JSON file. If None, uses default location.

    Returns:
        Tuple of (all_valid, validation_results).
    """
    loader = ScenarioLoader(path)
    return loader.validate_all_scenarios()
