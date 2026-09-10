"""
Test suite for timer perturbations — stress testing bot prediction accuracy.
Tests cover all 6 perturbation types and their combinations.
"""

import pytest
from mvp.simulator.config import TIMER_PERTURBATIONS
from mvp.simulator.variants import VariantExecutor


class TestTimerPerturbationDefinitions:
    """Tests for timer perturbation configuration."""

    def test_perturbation_config_exists(self):
        """Test TIMER_PERTURBATIONS config is defined."""
        assert TIMER_PERTURBATIONS is not None
        assert isinstance(TIMER_PERTURBATIONS, dict)

    def test_perturbation_chaotic_timer_config(self):
        """Test chaotic_timer perturbation configuration."""
        assert 'chaotic_timer' in TIMER_PERTURBATIONS
        config = TIMER_PERTURBATIONS['chaotic_timer']
        assert 'description' in config
        assert 'enabled' in config
        assert config['enabled'] is False

    def test_perturbation_frozen_timer_config(self):
        """Test frozen_timer perturbation configuration."""
        assert 'frozen_timer' in TIMER_PERTURBATIONS
        config = TIMER_PERTURBATIONS['frozen_timer']
        assert 'description' in config
        assert 'freeze_duration_ms' in config

    def test_perturbation_accelerated_timer_config(self):
        """Test accelerated_timer perturbation configuration."""
        assert 'accelerated_timer' in TIMER_PERTURBATIONS
        config = TIMER_PERTURBATIONS['accelerated_timer']
        assert 'description' in config
        assert 'speed_multiplier' in config

    def test_perturbation_hidden_timer_config(self):
        """Test hidden_timer perturbation configuration."""
        assert 'hidden_timer' in TIMER_PERTURBATIONS
        config = TIMER_PERTURBATIONS['hidden_timer']
        assert 'description' in config
        assert 'opacity' in config

    def test_perturbation_distracted_chat_config(self):
        """Test distracted_chat perturbation configuration."""
        assert 'distracted_chat' in TIMER_PERTURBATIONS
        config = TIMER_PERTURBATIONS['distracted_chat']
        assert 'description' in config

    def test_perturbation_timer_glitch_config(self):
        """Test timer_glitch perturbation configuration."""
        assert 'timer_glitch' in TIMER_PERTURBATIONS
        config = TIMER_PERTURBATIONS['timer_glitch']
        assert 'description' in config
        assert 'flicker_frequency_hz' in config


class TestTimerPerturbationApplication:
    """Tests for applying perturbations via VariantExecutor."""

    def test_apply_chaotic_timer_perturbation(self):
        """Test applying chaotic_timer perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('chaotic_timer', variant)
        assert result['timer_perturbation'] == 'chaotic_timer'
        assert result['timer_mode'] == 'chaotic'
        assert 'timer_jump_range_ms' in result

    def test_apply_frozen_timer_perturbation(self):
        """Test applying frozen_timer perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('frozen_timer', variant)
        assert result['timer_perturbation'] == 'frozen_timer'
        assert result['timer_mode'] == 'frozen'
        assert result['freeze_duration_ms'] == 2000

    def test_apply_accelerated_timer_perturbation(self):
        """Test applying accelerated_timer perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('accelerated_timer', variant)
        assert result['timer_perturbation'] == 'accelerated_timer'
        assert result['timer_mode'] == 'accelerated'
        assert result['speed_multiplier'] == 2.0

    def test_apply_hidden_timer_perturbation(self):
        """Test applying hidden_timer perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('hidden_timer', variant)
        assert result['timer_perturbation'] == 'hidden_timer'
        assert result['timer_mode'] == 'hidden'
        assert result['render_timer'] is False

    def test_apply_distracted_chat_perturbation(self):
        """Test applying distracted_chat perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('distracted_chat', variant)
        assert result['timer_perturbation'] == 'distracted_chat'
        assert result['timer_mode'] == 'distracted'
        assert result['show_chat_during_timer'] is True


class TestTimerPerturbationDetection:
    """Tests for detecting active perturbations."""

    def test_has_timer_perturbation_true(self):
        """Test has_timer_perturbation returns True when perturbation active."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('chaotic_timer', variant)
        assert executor.has_timer_perturbation(result) is True

    def test_has_timer_perturbation_false(self):
        """Test has_timer_perturbation returns False when no perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        assert executor.has_timer_perturbation(variant) is False

    def test_get_timer_perturbation_returns_name(self):
        """Test get_timer_perturbation returns perturbation name."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('frozen_timer', variant)
        perturbation_name = executor.get_timer_perturbation(result)
        assert perturbation_name == 'frozen_timer'

    def test_get_timer_perturbation_returns_none(self):
        """Test get_timer_perturbation returns None when no perturbation."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        perturbation_name = executor.get_timer_perturbation(variant)
        assert perturbation_name is None


class TestTimerPerturbationCombinations:
    """Tests for combining multiple perturbations."""

    def test_combined_chaotic_and_accelerated(self):
        """Test combining chaotic + accelerated perturbations."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        # Apply chaotic first
        variant = executor.apply_timer_perturbation('chaotic_timer', variant)
        assert variant['timer_perturbation'] == 'chaotic_timer'
        
        # Apply accelerated (overwrites)
        variant = executor.apply_timer_perturbation('accelerated_timer', variant)
        assert variant['timer_perturbation'] == 'accelerated_timer'

    def test_perturbation_invalid_name(self):
        """Test applying invalid perturbation name."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        # Invalid perturbation should not be added
        result = executor.apply_timer_perturbation('invalid_perturbation', variant)
        assert 'timer_perturbation' not in result or result.get('timer_perturbation') != 'invalid_perturbation'


class TestTimerPerturbationParameters:
    """Tests for perturbation-specific parameters."""

    def test_chaotic_timer_jump_range(self):
        """Test chaotic_timer has jump_range_ms parameter."""
        config = TIMER_PERTURBATIONS['chaotic_timer']
        assert 'jump_range_ms' in config
        assert isinstance(config['jump_range_ms'], tuple)
        assert len(config['jump_range_ms']) == 2
        assert config['jump_range_ms'][0] == 5000  # 5 seconds
        assert config['jump_range_ms'][1] == 20000  # 20 seconds

    def test_frozen_timer_duration(self):
        """Test frozen_timer has freeze_duration_ms parameter."""
        config = TIMER_PERTURBATIONS['frozen_timer']
        assert 'freeze_duration_ms' in config
        assert config['freeze_duration_ms'] == 2000  # 2 seconds

    def test_accelerated_timer_multiplier(self):
        """Test accelerated_timer has speed_multiplier parameter."""
        config = TIMER_PERTURBATIONS['accelerated_timer']
        assert 'speed_multiplier' in config
        assert config['speed_multiplier'] in [2.0, 4.0, 0.5]  # 2x, 4x, or 0.5x

    def test_timer_glitch_frequency(self):
        """Test timer_glitch has flicker_frequency_hz parameter."""
        config = TIMER_PERTURBATIONS['timer_glitch']
        assert 'flicker_frequency_hz' in config
        assert config['flicker_frequency_hz'] == 10.0  # 10 Hz = 100ms cycle

    def test_distracted_chat_overlay_opacity(self):
        """Test distracted_chat has overlay_opacity parameter."""
        config = TIMER_PERTURBATIONS['distracted_chat']
        assert 'overlay_opacity' in config
        assert 0.0 <= config['overlay_opacity'] <= 1.0


class TestTimerPerturbationMetrics:
    """Tests for tracking perturbation impact on metrics."""

    def test_perturbation_logged_in_variant(self):
        """Test perturbation name logged in variant config."""
        executor = VariantExecutor()
        executor.apply_preset('default')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('hidden_timer', variant)
        state_params = executor.get_state_params()
        
        # Perturbation info should be available for logging
        assert 'timer_perturbation' in result or result.get('render_timer') is False

    def test_multiple_perturbations_sequential(self):
        """Test applying perturbations sequentially."""
        executor = VariantExecutor()
        executor.apply_preset('hard_mode')
        variant = executor.current_variant.copy()
        
        # First perturbation
        variant = executor.apply_timer_perturbation('chaotic_timer', variant)
        assert executor.has_timer_perturbation(variant)
        
        # Sequential variants with different perturbations
        variant2 = variant.copy()
        variant2 = executor.apply_timer_perturbation('accelerated_timer', variant2)
        assert executor.get_timer_perturbation(variant2) == 'accelerated_timer'


class TestTimerPerturbationEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_perturbation_on_stress_test_preset(self):
        """Test applying perturbations to stress_test preset."""
        executor = VariantExecutor()
        executor.apply_preset('stress_test')
        variant = executor.current_variant.copy()
        
        result = executor.apply_timer_perturbation('accelerated_timer', variant)
        assert result['timer_perturbation'] == 'accelerated_timer'
        # Stress test variant should remain intact
        assert result['bot_config'] == 'aggressive'

    def test_perturbation_empty_variant(self):
        """Test applying perturbation to empty variant."""
        executor = VariantExecutor()
        empty_variant = {}
        
        result = executor.apply_timer_perturbation('frozen_timer', empty_variant)
        assert result['timer_perturbation'] == 'frozen_timer'

    def test_all_perturbations_defined(self):
        """Test that all perturbations have required fields."""
        required_fields = ['description', 'enabled']
        
        for perturb_name, perturb_config in TIMER_PERTURBATIONS.items():
            for field in required_fields:
                assert field in perturb_config, f"Missing '{field}' in {perturb_name}"
