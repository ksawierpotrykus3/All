"""
Variant configuration definitions for Extended Game Simulator Framework.

Defines:
- VARIANT_DIMENSIONS: 6 test dimensions with valid options
- VARIANT_PRESETS: 3 predefined configurations (default, hard_mode, stress_test)
- STATE_IMAGE_MAPPING: Maps game states to image files from macro_testing/
"""

from typing import Dict, List, Any

# =============================================================================
# VARIANT DIMENSIONS — 6 Critical Test Dimensions
# =============================================================================

VARIANT_DIMENSIONS: Dict[str, List[str]] = {
    "chat_cleanliness": [
        "clean",      # Clean chat window — baseline OCR conditions
        "cluttered",  # Cluttered chat — multiple overlapping elements
        "spam"        # Heavy spam — noise, popups, overlapping alerts
    ],
    "heli_visibility": [
        "visible",    # Helicopter fully visible during alert
        "hidden",     # Helicopter hidden/obscured
        "partial"     # Helicopter partially visible
    ],
    "system_load": [
        "idle",       # Low CPU load (0-10%)
        "medium",     # Medium CPU load (30-50%)
        "high"        # High CPU load (70-90%)
    ],
    "alert_timing": [
        "immediate",  # Alert fires immediately (no delay)
        "delayed",    # Alert delayed by 500-1000ms
        "overlapped"  # Alert overlaps with previous state (edge case)
    ],
    "bot_config": [
        "30_cps",     # 30 clicks per second (slower, 33ms period)
        "38_cps",     # 38 clicks per second (optimized, 26ms period) — BASELINE
        "aggressive"  # Aggressive CPS (50+ CPS or 3ms holds) — STRESS TEST
    ],
    "eye_tracking": [
        "focused",    # Normal eye tracking — bot focused on target
        "distracted", # Eye tracking distracted — saccades, blinks
        "loss_event"  # Loss of eye tracking — recalibration needed
    ]
}

# =============================================================================
# VARIANT PRESETS — 3 Predefined Configurations
# =============================================================================

VARIANT_PRESETS: Dict[str, Dict[str, str]] = {
    # DEFAULT PRESET: Baseline configuration — optimal conditions for testing
    "default": {
        "chat_cleanliness": "clean",
        "heli_visibility": "visible",
        "system_load": "idle",
        "alert_timing": "immediate",
        "bot_config": "38_cps",
        "eye_tracking": "focused"
    },

    # HARD MODE PRESET: Challenging conditions — increased difficulty
    "hard_mode": {
        "chat_cleanliness": "cluttered",
        "heli_visibility": "hidden",
        "system_load": "medium",
        "alert_timing": "delayed",
        "bot_config": "38_cps",
        "eye_tracking": "distracted"
    },

    # STRESS TEST PRESET: Extreme conditions — maximum difficulty
    "stress_test": {
        "chat_cleanliness": "spam",
        "heli_visibility": "partial",
        "system_load": "high",
        "alert_timing": "overlapped",
        "bot_config": "aggressive",
        "eye_tracking": "loss_event"
    }
}

# =============================================================================
# STATE IMAGE MAPPING — Game State to Image Files
# =============================================================================
# Maps game states to PNG images from data/macro_testing/ directory

STATE_IMAGE_MAPPING: Dict[str, str] = {
    "chat": "1_scan_chat_without_arrow.png",
    "chat_focus": "1_scan_chat_with_arrow.png",
    "alert_animation": "1_heli_alert_appearing_in_chat.png",
    "treasure": "helka_scrolled.png",
    "reward_details": "details.png",
    "chat_unavailable": "no_chat.png"
}

# =============================================================================
# BOT CONFIG PARAMETERS — Maps bot_config strings to timing values
# =============================================================================

BOT_CONFIG_PARAMS: Dict[str, Dict[str, Any]] = {
    "30_cps": {
        "cps": 30,
        "period_ms": 33.3,
        "dig_hold_ms": 18.0,
        "description": "30 clicks per second — slower, safer clicking"
    },
    "38_cps": {
        "cps": 38,
        "period_ms": 26.0,
        "dig_hold_ms": 18.0,
        "description": "38 clicks per second — optimized baseline per AGENTS.md"
    },
    "aggressive": {
        "cps": 50,
        "period_ms": 20.0,
        "dig_hold_ms": 3.0,
        "description": "50+ CPS — aggressive clicking, extreme stress test"
    }
}

# =============================================================================
# SYSTEM LOAD PARAMETERS — Maps system_load strings to CPU simulation levels
# =============================================================================

SYSTEM_LOAD_PARAMS: Dict[str, Dict[str, Any]] = {
    "idle": {
        "cpu_percent": 5,
        "description": "Minimal CPU load — baseline performance",
        "simulate_processes": []
    },
    "medium": {
        "cpu_percent": 40,
        "description": "Medium CPU load — simulated background processes",
        "simulate_processes": ["video_codec", "compression"]
    },
    "high": {
        "cpu_percent": 80,
        "description": "High CPU load — heavy background processes",
        "simulate_processes": ["video_codec", "compression", "memory_scan", "encryption"]
    }
}

# =============================================================================
# ALERT TIMING PARAMETERS — Maps alert_timing strings to delay values
# =============================================================================

ALERT_TIMING_PARAMS: Dict[str, Dict[str, Any]] = {
    "immediate": {
        "delay_ms": 0,
        "description": "Alert fires immediately — no delay"
    },
    "delayed": {
        "delay_ms": 750,
        "description": "Alert delayed by ~750ms — moderate reaction time test"
    },
    "overlapped": {
        "delay_ms": -500,
        "description": "Alert overlaps with previous state (edge case, timing conflict)"
    }
}

# =============================================================================
# CHAT CLEANLINESS PARAMETERS — Maps chat_cleanliness strings to visual configs
# =============================================================================

CHAT_CLEANLINESS_PARAMS: Dict[str, Dict[str, Any]] = {
    "clean": {
        "noise_level": 0,
        "description": "Clean chat window — baseline OCR conditions",
        "overlay_elements": []
    },
    "cluttered": {
        "noise_level": 2,
        "description": "Cluttered chat — multiple overlapping UI elements",
        "overlay_elements": ["badges", "emotes", "buttons"]
    },
    "spam": {
        "noise_level": 5,
        "description": "Spam chat — heavy noise, popups, extreme OCR difficulty",
        "overlay_elements": ["badges", "emotes", "buttons", "notifications", "popups"]
    }
}

# =============================================================================
# MOCK PHASE PARAMETERS (Issue #6) — Configurable mock values for testing
# =============================================================================
# When bot_integration is disabled or data unavailable, use these mock values
# to simulate realistic phase timings and metrics

MOCK_PHASE_PARAMS: Dict[str, Any] = {
    # Phase 2: Alert Detection
    "alert_detection": {
        "detection_time_ms": 145,
        "ocr_confidence": 0.92,
    },
    # Phase 3: Click
    "click": {
        "latency_ms": 78,
        "click_position_x": 320,
        "click_position_y": 450,
        "ocr_confidence": 0.92,
        "hit_rate": 0.90,  # 90% hit rate in default variant
    },
    # Phase 4: Treasure
    "treasure": {
        "cpu_spike_percent": 45,
        "animation_duration_ms": 500,
    },
    # Phase 5: Chat Recovery
    "chat_recovery": {
        "recovery_time_ms": 890,
        "ocr_confidence": 0.87,
        "state_verified": True,
    },
    # Phase 6: Finalize
    "finalize": {
        "total_iteration_ms": 1356,
        "cpu_avg": 42,
        "ram_mb": 256,
    }
}

# =============================================================================
# TIMER CONFIGURATION — Timer animation and phase colors
# =============================================================================

TIMER_CONFIG: Dict[str, Any] = {
    "total_ms": 60000,  # 60 second timer default
    "color_phases": [
        {"phase": "green", "start_ms": 30000, "end_ms": 60000},   # T-60 → T-30
        {"phase": "yellow", "start_ms": 10000, "end_ms": 30000},  # T-30 → T-10
        {"phase": "red", "start_ms": 0, "end_ms": 10000},         # T-10 → T-0
    ],
    "blink_frequency_hz": 2.0,  # 2 blinks per second at T-0
    "timer_text_format": "MM:SS.mmm",  # e.g., "01:30.450"
}

# =============================================================================
# TIMER PERTURBATIONS — Stress testing timer prediction accuracy
# =============================================================================
# Perturbations alter timer behavior to test bot robustness

TIMER_PERTURBATIONS: Dict[str, Dict[str, Any]] = {
    "chaotic_timer": {
        "description": "Timer jumps ±5-20 seconds randomly",
        "enabled": False,
        "jump_range_ms": (5000, 20000),  # ±5-20 sec
        "jump_frequency_hz": 0.5,  # Every 2 seconds
    },
    "frozen_timer": {
        "description": "Timer stops for N seconds",
        "enabled": False,
        "freeze_duration_ms": 2000,  # Halt for 2 sec
        "freeze_probability": 0.1,  # 10% chance each frame
    },
    "accelerated_timer": {
        "description": "Timer runs faster (2x or 4x speed)",
        "enabled": False,
        "speed_multiplier": 2.0,  # 2x, 4x, or 0.5x
    },
    "hidden_timer": {
        "description": "Timer invisible on screen",
        "enabled": False,
        "opacity": 0.0,  # Fully transparent
    },
    "distracted_chat": {
        "description": "Chat overlay appears during timer",
        "enabled": False,
        "overlay_opacity": 0.5,  # 50% opacity
    },
    "timer_glitch": {
        "description": "Timer flickers on/off rapidly",
        "enabled": False,
        "flicker_frequency_hz": 10.0,  # 10 Hz = 100ms cycle
    },
}

# =============================================================================
# Helper functions for variant management
# =============================================================================

def get_variant_preset(preset_name: str) -> Dict[str, str]:
    """
    Retrieve a predefined variant preset.

    Args:
        preset_name: One of "default", "hard_mode", "stress_test"

    Returns:
        Dictionary with variant configuration

    Raises:
        ValueError: If preset_name not found in VARIANT_PRESETS
    """
    if preset_name not in VARIANT_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Valid presets: {list(VARIANT_PRESETS.keys())}")
    return VARIANT_PRESETS[preset_name].copy()


def is_valid_variant(variant: Dict[str, str]) -> bool:
    """
    Check if variant configuration is valid.

    Args:
        variant: Dictionary with variant dimensions

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check all required dimensions present
        if set(variant.keys()) != set(VARIANT_DIMENSIONS.keys()):
            return False

        # Check all values are valid for their dimensions
        for dim_name, dim_value in variant.items():
            if dim_value not in VARIANT_DIMENSIONS[dim_name]:
                return False

        return True
    except (KeyError, TypeError):
        return False
