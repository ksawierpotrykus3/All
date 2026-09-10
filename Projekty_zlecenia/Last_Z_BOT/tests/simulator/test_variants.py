"""
Tests for VariantExecutor and variant configuration management.

Validates: Task 3 - Implement VariantExecutor
- 6 test dimensions: chat_cleanliness, heli_visibility, system_load, alert_timing, bot_config, eye_tracking
- 3 presets: default, hard_mode, stress_test
- apply_preset(), apply_variant(), get_state_params()
- Validation of variant dimensions
"""

import pytest
from pathlib import Path
from typing import Dict, Any

# Import will work after creating variants.py
# from mvp.simulator.variants import VariantExecutor
# from mvp.simulator.config import VARIANT_DIMENSIONS, VARIANT_PRESETS


class TestVariantExecutorInit:
    """Test VariantExecutor initialization."""

    def test_init_creates_empty_variant_state(self):
        """VariantExecutor initializes with empty variant state."""
        from mvp.simulator.variants import VariantExecutor
        executor = VariantExecutor()
        assert executor.current_variant == {}

    def test_init_session_id_optional(self):
        """VariantExecutor accepts optional session_id."""
        from mvp.simulator.variants import VariantExecutor
        executor = VariantExecutor(session_id="test_session_123")
        assert executor.session_id == "test_session_123"


class TestVariantPresets:
    """Test VARIANT_PRESETS configuration."""

    def test_config_has_required_presets(self):
        """VARIANT_PRESETS contains default, hard_mode, stress_test."""
        from mvp.simulator.config import VARIANT_PRESETS
        assert "default" in VARIANT_PRESETS
        assert "hard_mode" in VARIANT_PRESETS
        assert "stress_test" in VARIANT_PRESETS

    def test_default_preset_structure(self):
        """default preset has all 6 dimensions with valid values."""
        from mvp.simulator.config import VARIANT_PRESETS
        preset = VARIANT_PRESETS["default"]
        assert "chat_cleanliness" in preset
        assert "heli_visibility" in preset
        assert "system_load" in preset
        assert "alert_timing" in preset
        assert "bot_config" in preset
        assert "eye_tracking" in preset

    def test_hard_mode_preset_is_challenging(self):
        """hard_mode preset contains challenging configurations."""
        from mvp.simulator.config import VARIANT_PRESETS, VARIANT_DIMENSIONS
        preset = VARIANT_PRESETS["hard_mode"]
        # hard_mode should have different values than default
        default = VARIANT_PRESETS["default"]
        assert preset != default

    def test_stress_test_preset_is_extreme(self):
        """stress_test preset contains extreme configurations."""
        from mvp.simulator.config import VARIANT_PRESETS
        preset = VARIANT_PRESETS["stress_test"]
        # stress_test should have different values than default and hard_mode
        assert preset != VARIANT_PRESETS["default"]
        assert preset != VARIANT_PRESETS["hard_mode"]


class TestVariantDimensions:
    """Test VARIANT_DIMENSIONS configuration."""

    def test_variant_dimensions_defined(self):
        """VARIANT_DIMENSIONS has exactly 6 dimensions."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        assert len(VARIANT_DIMENSIONS) == 6

    def test_each_dimension_has_valid_options(self):
        """Each dimension has 2-3 valid options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        for dim_name, options in VARIANT_DIMENSIONS.items():
            assert isinstance(options, (list, tuple))
            assert 2 <= len(options) <= 3
            assert all(isinstance(opt, str) for opt in options)

    def test_dimension_names(self):
        """Dimensions are: chat_cleanliness, heli_visibility, system_load, alert_timing, bot_config, eye_tracking."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        expected_dims = {
            "chat_cleanliness",
            "heli_visibility",
            "system_load",
            "alert_timing",
            "bot_config",
            "eye_tracking"
        }
        assert set(VARIANT_DIMENSIONS.keys()) == expected_dims

    def test_chat_cleanliness_options(self):
        """chat_cleanliness has clean, cluttered, spam options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        options = set(VARIANT_DIMENSIONS["chat_cleanliness"])
        expected = {"clean", "cluttered", "spam"}
        assert expected.issubset(options)

    def test_heli_visibility_options(self):
        """heli_visibility has visible, hidden, partial options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        options = set(VARIANT_DIMENSIONS["heli_visibility"])
        expected = {"visible", "hidden", "partial"}
        assert expected.issubset(options)

    def test_system_load_options(self):
        """system_load has idle, medium, high options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        options = set(VARIANT_DIMENSIONS["system_load"])
        expected = {"idle", "medium", "high"}
        assert expected.issubset(options)

    def test_alert_timing_options(self):
        """alert_timing has immediate, delayed, overlapped options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        options = set(VARIANT_DIMENSIONS["alert_timing"])
        expected = {"immediate", "delayed", "overlapped"}
        assert expected.issubset(options)

    def test_bot_config_options(self):
        """bot_config has 30_cps, 38_cps, aggressive options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        options = set(VARIANT_DIMENSIONS["bot_config"])
        expected = {"30_cps", "38_cps", "aggressive"}
        assert expected.issubset(options)

    def test_eye_tracking_options(self):
        """eye_tracking has focused, distracted, loss_event options."""
        from mvp.simulator.config import VARIANT_DIMENSIONS
        options = set(VARIANT_DIMENSIONS["eye_tracking"])
        expected = {"focused", "distracted", "loss_event"}
        assert expected.issubset(options)


class TestApplyPreset:
    """Test VariantExecutor.apply_preset() method."""

    def test_apply_default_preset(self):
        """apply_preset('default') sets variant to default configuration."""
        from mvp.simulator.variants import VariantExecutor
        from mvp.simulator.config import VARIANT_PRESETS

        executor = VariantExecutor()
        executor.apply_preset("default")

        expected = VARIANT_PRESETS["default"]
        assert executor.current_variant == expected

    def test_apply_hard_mode_preset(self):
        """apply_preset('hard_mode') sets variant to hard_mode configuration."""
        from mvp.simulator.variants import VariantExecutor
        from mvp.simulator.config import VARIANT_PRESETS

        executor = VariantExecutor()
        executor.apply_preset("hard_mode")

        expected = VARIANT_PRESETS["hard_mode"]
        assert executor.current_variant == expected

    def test_apply_stress_test_preset(self):
        """apply_preset('stress_test') sets variant to stress_test configuration."""
        from mvp.simulator.variants import VariantExecutor
        from mvp.simulator.config import VARIANT_PRESETS

        executor = VariantExecutor()
        executor.apply_preset("stress_test")

        expected = VARIANT_PRESETS["stress_test"]
        assert executor.current_variant == expected

    def test_apply_invalid_preset_raises_error(self):
        """apply_preset() raises ValueError for invalid preset name."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        with pytest.raises(ValueError, match="Unknown preset"):
            executor.apply_preset("invalid_preset")

    def test_apply_preset_replaces_previous_variant(self):
        """Applying new preset replaces previous variant configuration."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")
        default_variant = executor.current_variant.copy()

        executor.apply_preset("hard_mode")
        hard_mode_variant = executor.current_variant

        assert hard_mode_variant != default_variant


class TestApplyVariant:
    """Test VariantExecutor.apply_variant() method."""

    def test_apply_valid_custom_variant(self):
        """apply_variant() accepts valid custom configuration."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        custom_variant = {
            "chat_cleanliness": "clean",
            "heli_visibility": "visible",
            "system_load": "idle",
            "alert_timing": "immediate",
            "bot_config": "38_cps",
            "eye_tracking": "focused"
        }
        executor.apply_variant(custom_variant)
        assert executor.current_variant == custom_variant

    def test_apply_variant_validates_all_dimensions_present(self):
        """apply_variant() raises ValueError if dimension missing."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        incomplete_variant = {
            "chat_cleanliness": "clean",
            "heli_visibility": "visible",
            # Missing other dimensions
        }
        with pytest.raises(ValueError, match="Missing dimensions"):
            executor.apply_variant(incomplete_variant)

    def test_apply_variant_validates_dimension_values(self):
        """apply_variant() raises ValueError if dimension value is invalid."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        invalid_variant = {
            "chat_cleanliness": "invalid_value",
            "heli_visibility": "visible",
            "system_load": "idle",
            "alert_timing": "immediate",
            "bot_config": "38_cps",
            "eye_tracking": "focused"
        }
        with pytest.raises(ValueError, match="Invalid value"):
            executor.apply_variant(invalid_variant)

    def test_apply_variant_validates_unknown_dimension(self):
        """apply_variant() raises ValueError if unknown dimension provided."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        invalid_variant = {
            "chat_cleanliness": "clean",
            "heli_visibility": "visible",
            "system_load": "idle",
            "alert_timing": "immediate",
            "bot_config": "38_cps",
            "eye_tracking": "focused",
            "unknown_dimension": "some_value"  # Extra dimension
        }
        with pytest.raises(ValueError, match="Unknown dimension"):
            executor.apply_variant(invalid_variant)

    def test_apply_variant_multiple_times(self):
        """apply_variant() can be called multiple times with different configs."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()

        variant1 = {
            "chat_cleanliness": "clean",
            "heli_visibility": "visible",
            "system_load": "idle",
            "alert_timing": "immediate",
            "bot_config": "38_cps",
            "eye_tracking": "focused"
        }
        executor.apply_variant(variant1)
        assert executor.current_variant == variant1

        variant2 = {
            "chat_cleanliness": "cluttered",
            "heli_visibility": "hidden",
            "system_load": "high",
            "alert_timing": "delayed",
            "bot_config": "aggressive",
            "eye_tracking": "distracted"
        }
        executor.apply_variant(variant2)
        assert executor.current_variant == variant2


class TestGetStateParams:
    """Test VariantExecutor.get_state_params() method."""

    def test_get_state_params_returns_game_state_dict(self):
        """get_state_params() returns dict with game state parameters."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")

        params = executor.get_state_params()
        assert isinstance(params, dict)

    def test_get_state_params_contains_required_keys(self):
        """get_state_params() contains keys for each variant dimension."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")

        params = executor.get_state_params()
        expected_keys = {
            "chat_cleanliness",
            "heli_visibility",
            "system_load",
            "alert_timing",
            "bot_config",
            "eye_tracking"
        }
        assert expected_keys.issubset(set(params.keys()))

    def test_get_state_params_for_default_preset(self):
        """get_state_params() returns sensible defaults for default preset."""
        from mvp.simulator.variants import VariantExecutor
        from mvp.simulator.config import VARIANT_PRESETS

        executor = VariantExecutor()
        executor.apply_preset("default")

        params = executor.get_state_params()
        preset = VARIANT_PRESETS["default"]

        # State params should contain values from the preset
        assert params["chat_cleanliness"] == preset["chat_cleanliness"]
        assert params["heli_visibility"] == preset["heli_visibility"]
        assert params["system_load"] == preset["system_load"]
        assert params["alert_timing"] == preset["alert_timing"]
        assert params["bot_config"] == preset["bot_config"]
        assert params["eye_tracking"] == preset["eye_tracking"]

    def test_get_state_params_includes_timing_values(self):
        """get_state_params() includes timing configuration from bot_config."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")

        params = executor.get_state_params()
        # Should have timing-related fields
        assert "bot_config" in params

    def test_get_state_params_includes_cpu_load_settings(self):
        """get_state_params() includes CPU load settings."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")

        params = executor.get_state_params()
        assert "system_load" in params

    def test_get_state_params_hard_mode_differs_from_default(self):
        """get_state_params() for hard_mode differs significantly from default."""
        from mvp.simulator.variants import VariantExecutor

        executor1 = VariantExecutor()
        executor1.apply_preset("default")
        default_params = executor1.get_state_params()

        executor2 = VariantExecutor()
        executor2.apply_preset("hard_mode")
        hard_mode_params = executor2.get_state_params()

        # At least some params should differ
        assert default_params != hard_mode_params


class TestVariantValidation:
    """Test variant validation logic."""

    def test_validate_dimension_names(self):
        """Validation checks that all required dimensions are present."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        incomplete = {
            "chat_cleanliness": "clean",
            "heli_visibility": "visible",
        }
        with pytest.raises(ValueError):
            executor.apply_variant(incomplete)

    def test_validate_dimension_values(self):
        """Validation rejects invalid values for dimensions."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        invalid = {
            "chat_cleanliness": "ultracluttered",  # Invalid
            "heli_visibility": "visible",
            "system_load": "idle",
            "alert_timing": "immediate",
            "bot_config": "38_cps",
            "eye_tracking": "focused"
        }
        with pytest.raises(ValueError):
            executor.apply_variant(invalid)

    def test_validate_no_extra_dimensions(self):
        """Validation rejects extra unknown dimensions."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        extra = {
            "chat_cleanliness": "clean",
            "heli_visibility": "visible",
            "system_load": "idle",
            "alert_timing": "immediate",
            "bot_config": "38_cps",
            "eye_tracking": "focused",
            "extra_dimension": "value"
        }
        with pytest.raises(ValueError):
            executor.apply_variant(extra)

    def test_preset_validation_passes(self):
        """All presets pass validation when applied."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        # Should not raise any errors
        executor.apply_preset("default")
        executor.apply_preset("hard_mode")
        executor.apply_preset("stress_test")


class TestVariantExecutorIntegration:
    """Integration tests for VariantExecutor."""

    def test_workflow_preset_then_custom(self):
        """Can apply preset then override with custom variant."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")
        default_variant = executor.current_variant.copy()

        custom = {
            "chat_cleanliness": "cluttered",
            "heli_visibility": "hidden",
            "system_load": "high",
            "alert_timing": "delayed",
            "bot_config": "aggressive",
            "eye_tracking": "distracted"
        }
        executor.apply_variant(custom)
        assert executor.current_variant != default_variant
        assert executor.current_variant == custom

    def test_get_state_params_after_apply_variant(self):
        """get_state_params() reflects custom variant configuration."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        custom = {
            "chat_cleanliness": "spam",
            "heli_visibility": "partial",
            "system_load": "medium",
            "alert_timing": "overlapped",
            "bot_config": "30_cps",
            "eye_tracking": "loss_event"
        }
        executor.apply_variant(custom)
        params = executor.get_state_params()

        assert params["chat_cleanliness"] == "spam"
        assert params["heli_visibility"] == "partial"
        assert params["system_load"] == "medium"
        assert params["alert_timing"] == "overlapped"
        assert params["bot_config"] == "30_cps"
        assert params["eye_tracking"] == "loss_event"

    def test_multiple_preset_applications(self):
        """Can apply presets sequentially."""
        from mvp.simulator.variants import VariantExecutor

        executor = VariantExecutor()
        executor.apply_preset("default")
        params1 = executor.get_state_params()

        executor.apply_preset("hard_mode")
        params2 = executor.get_state_params()

        executor.apply_preset("stress_test")
        params3 = executor.get_state_params()

        # All three should be different
        assert params1 != params2
        assert params2 != params3
        assert params1 != params3
