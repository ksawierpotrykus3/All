"""
VariantExecutor — Manages test variant configurations for Extended Game Simulator.

Responsibilities:
- Apply predefined variant presets (default, hard_mode, stress_test)
- Apply custom variant configurations with validation
- Convert variant config to game state parameters
- Validate all variant dimensions and values
"""

from typing import Dict, Any, Optional
from pathlib import Path

from mvp.simulator.config import (
    VARIANT_DIMENSIONS,
    VARIANT_PRESETS,
    BOT_CONFIG_PARAMS,
    SYSTEM_LOAD_PARAMS,
    ALERT_TIMING_PARAMS,
    CHAT_CLEANLINESS_PARAMS,
)

class VariantExecutor:
    """
    Manages test variant configuration and application.

    A variant is a complete configuration across 6 dimensions:
    - chat_cleanliness: clean, cluttered, spam
    - heli_visibility: visible, hidden, partial
    - system_load: idle, medium, high
    - alert_timing: immediate, delayed, overlapped
    - bot_config: 30_cps, 38_cps, aggressive
    - eye_tracking: focused, distracted, loss_event

    Methods:
    - apply_preset(name): Apply named preset configuration
    - apply_variant(config): Apply custom variant with validation
    - get_state_params(): Get game state parameters for current variant
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize VariantExecutor.

        Args:
            session_id: Optional session identifier for logging/tracking
        """
        self.session_id = session_id
        self.current_variant: Dict[str, str] = {}

    def apply_preset(self, preset_name: str) -> None:
        """
        Apply a predefined variant preset.

        Valid presets: "default", "hard_mode", "stress_test"

        Args:
            preset_name: Name of preset to apply

        Raises:
            ValueError: If preset_name is not recognized
        """
        if preset_name not in VARIANT_PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Valid presets: {list(VARIANT_PRESETS.keys())}"
            )

        self.current_variant = VARIANT_PRESETS[preset_name].copy()

    def apply_variant(self, variant_config: Dict[str, str]) -> None:
        """
        Apply a custom variant configuration with validation.

        Validates:
        1. All 6 required dimensions are present
        2. All values are valid for their dimensions
        3. No unknown dimensions are provided
        4. (Cross-dimension constraints removed — see Issue #9)

        Args:
            variant_config: Dictionary with variant configuration

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate: no extra dimensions
        extra_dims = set(variant_config.keys()) - set(VARIANT_DIMENSIONS.keys())
        if extra_dims:
            raise ValueError(
                f"Unknown dimension(s): {extra_dims}. "
                f"Valid dimensions: {list(VARIANT_DIMENSIONS.keys())}"
            )

        # Validate: all required dimensions present
        missing_dims = set(VARIANT_DIMENSIONS.keys()) - set(variant_config.keys())
        if missing_dims:
            raise ValueError(
                f"Missing dimensions: {missing_dims}. "
                f"Required: {list(VARIANT_DIMENSIONS.keys())}"
            )

        # Validate: all values are valid for their dimensions
        for dim_name, dim_value in variant_config.items():
            valid_values = VARIANT_DIMENSIONS[dim_name]
            if dim_value not in valid_values:
                raise ValueError(
                    f"Invalid value '{dim_value}' for dimension '{dim_name}'. "
                    f"Valid values: {valid_values}"
                )

        # All validation passed — apply variant
        self.current_variant = variant_config.copy()

    def get_state_params(self) -> Dict[str, Any]:
        """
        Convert current variant configuration to game state parameters.

        Returns dictionary with:
        - Basic variant dimensions (as strings)
        - Computed parameters from BOT_CONFIG_PARAMS, SYSTEM_LOAD_PARAMS, etc.
        - Timing values, CPU load levels, visual configurations

        Returns:
            Dictionary with game state parameters

        Raises:
            RuntimeError: If no variant has been applied yet
        """
        if not self.current_variant:
            raise RuntimeError("No variant applied. Call apply_preset() or apply_variant() first.")

        params = {}

        # 1. Copy all variant dimensions
        params.update(self.current_variant)

        # 2. Add bot config parameters
        bot_config_name = self.current_variant["bot_config"]
        bot_params = BOT_CONFIG_PARAMS[bot_config_name]
        params["bot_config_params"] = {
            "cps": bot_params["cps"],
            "period_ms": bot_params["period_ms"],
            "dig_hold_ms": bot_params["dig_hold_ms"]
        }

        # 3. Add system load parameters
        system_load_name = self.current_variant["system_load"]
        load_params = SYSTEM_LOAD_PARAMS[system_load_name]
        params["system_load_params"] = {
            "cpu_percent": load_params["cpu_percent"],
            "simulate_processes": load_params["simulate_processes"]
        }

        # 4. Add alert timing parameters
        alert_timing_name = self.current_variant["alert_timing"]
        timing_params = ALERT_TIMING_PARAMS[alert_timing_name]
        params["alert_timing_params"] = {
            "delay_ms": timing_params["delay_ms"]
        }

        # 5. Add chat cleanliness parameters
        chat_cleanliness_name = self.current_variant["chat_cleanliness"]
        chat_params = CHAT_CLEANLINESS_PARAMS[chat_cleanliness_name]
        params["chat_cleanliness_params"] = {
            "noise_level": chat_params["noise_level"],
            "overlay_elements": chat_params["overlay_elements"]
        }

        # 6. Add timer parameters (Task 3b)
        from mvp.simulator.config import TIMER_CONFIG
        params["timer_expiry_ms"] = TIMER_CONFIG["total_ms"]
        params["timer_offset_ms"] = self.current_variant.get("timer_offset_ms", 0.0)  # Offset for prediction mode
        params["timer_blink_frequency_hz"] = TIMER_CONFIG["blink_frequency_hz"]

        return params

    def get_variant_name(self) -> str:
        """
        Generate a human-readable name for current variant.

        Format: "{chat}_{heli}_{load}_{timing}_{cps}_{eye}"

        Returns:
            Human-readable variant name, or "unconfigured" if no variant applied
        """
        if not self.current_variant:
            return "unconfigured"

        # Abbreviate dimension values for readability
        abbrev = {
            "clean": "c",
            "cluttered": "cl",
            "spam": "s",
            "visible": "v",
            "hidden": "h",
            "partial": "p",
            "idle": "i",
            "medium": "m",
            "high": "h",
            "immediate": "im",
            "delayed": "d",
            "overlapped": "o",
            "30_cps": "30",
            "38_cps": "38",
            "aggressive": "ag",
            "focused": "f",
            "distracted": "di",
            "loss_event": "l"
        }

        parts = [
            abbrev.get(self.current_variant["chat_cleanliness"], "?"),
            abbrev.get(self.current_variant["heli_visibility"], "?"),
            abbrev.get(self.current_variant["system_load"], "?"),
            abbrev.get(self.current_variant["alert_timing"], "?"),
            abbrev.get(self.current_variant["bot_config"], "?"),
            abbrev.get(self.current_variant["eye_tracking"], "?")
        ]
        return "_".join(parts)

    def describe_variant(self) -> str:
        """
        Generate a detailed description of current variant.

        Returns:
            Multi-line description with all dimensions and their values
        """
        if not self.current_variant:
            return "No variant configured"

        lines = ["Variant Configuration:"]
        for dim_name, dim_value in self.current_variant.items():
            lines.append(f"  {dim_name}: {dim_value}")

        return "\n".join(lines)


    def apply_timer_perturbation(self, perturbation_name: str, current_variant: Dict[str, str]) -> Dict[str, Any]:
        """
        Apply timer perturbation mode to current variant.
        
        Perturbations:
        - chaotic_timer: Random timer jumps ±5-20 seconds
        - frozen_timer: Timer halts for N seconds
        - accelerated_timer: 2x or 4x countdown speed
        - hidden_timer: Timer invisible but counting
        - distracted_chat: Chat visible during timer
        
        Args:
            perturbation_name: Name of perturbation
            current_variant: Current variant config
            
        Returns:
            Modified variant config with perturbation applied
        """
        variant = current_variant.copy()
        
        perturbation_params = {
            'chaotic_timer': {
                'timer_mode': 'chaotic',
                'timer_jump_range_ms': (5000, 20000),  # ±5-20 sec
            },
            'frozen_timer': {
                'timer_mode': 'frozen',
                'freeze_duration_ms': 2000,  # Halt for 2 sec
            },
            'accelerated_timer': {
                'timer_mode': 'accelerated',
                'speed_multiplier': 2.0,  # 2x or 4x
            },
            'hidden_timer': {
                'timer_mode': 'hidden',
                'render_timer': False,
            },
            'distracted_chat': {
                'timer_mode': 'distracted',
                'show_chat_during_timer': True,
            },
        }
        
        if perturbation_name in perturbation_params:
            variant['timer_perturbation'] = perturbation_name
            variant.update(perturbation_params[perturbation_name])
        
        return variant

    def get_timer_perturbation(self, variant: Dict[str, str]) -> Optional[str]:
        """Get active timer perturbation mode from variant."""
        return variant.get('timer_perturbation', None)

    def has_timer_perturbation(self, variant: Dict[str, str]) -> bool:
        """Check if variant has active timer perturbation."""
        return 'timer_perturbation' in variant
