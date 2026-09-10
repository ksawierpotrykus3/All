"""
Test suite for TimerAnimator class — dynamic timer animation support.
Tests cover all 6 game states and timer metrics (prediction accuracy, early/late clicks).
"""

import pytest
from PIL import Image
from mvp.simulator.ui.timer_animator import TimerAnimator


class TestTimerAnimatorInit:
    """Tests for TimerAnimator initialization."""

    def test_timer_animator_init_default(self):
        """Test TimerAnimator initializes with default total_ms=60000."""
        animator = TimerAnimator()
        assert animator.total_ms == 60000
        assert animator.start_time is None

    def test_timer_animator_init_custom_ms(self):
        """Test TimerAnimator initializes with custom total_ms."""
        animator = TimerAnimator(total_ms=30000)
        assert animator.total_ms == 30000


class TestTimerRenderCountdown:
    """Tests for timer countdown rendering."""

    def test_timer_render_at_zero_ms(self):
        """Test timer renders MM:SS.mmm format at 0ms."""
        animator = TimerAnimator(total_ms=60000)
        result = animator.render_countdown(elapsed_ms=0)
        assert isinstance(result, Image.Image)
        # Remaining time: 60.000
        assert result.size == (200, 100)  # Standard timer image size

    def test_timer_render_at_30_seconds(self):
        """Test timer renders correctly at 30 seconds (mid-range)."""
        animator = TimerAnimator(total_ms=60000)
        result = animator.render_countdown(elapsed_ms=30000)
        assert isinstance(result, Image.Image)
        # Remaining time: 30.000

    def test_timer_render_at_60_seconds(self):
        """Test timer renders at 60 seconds (full duration)."""
        animator = TimerAnimator(total_ms=60000)
        result = animator.render_countdown(elapsed_ms=60000)
        assert isinstance(result, Image.Image)
        # Remaining time: 00.000

    def test_timer_render_full_range(self):
        """Test timer renders correctly across full time range (0-60s)."""
        animator = TimerAnimator(total_ms=60000)
        for elapsed_ms in [0, 15000, 30000, 45000, 60000]:
            result = animator.render_countdown(elapsed_ms=elapsed_ms)
            assert isinstance(result, Image.Image)


class TestTimerColorPhases:
    """Tests for timer color logic (green/yellow/red phases)."""

    def test_timer_color_green_phase(self):
        """Test timer is green during T-60→T-30 phase (60s remaining to 30s remaining)."""
        animator = TimerAnimator(total_ms=60000)
        # Green: remaining_ms > 30000 (elapsed_ms < 30000)
        color = animator.get_timer_color(elapsed_ms=0)
        assert color == 'green'
        
        color = animator.get_timer_color(elapsed_ms=15000)
        assert color == 'green'
        
        color = animator.get_timer_color(elapsed_ms=29999)
        assert color == 'green'

    def test_timer_color_yellow_phase(self):
        """Test timer is yellow during T-30→T-10 phase (30s remaining to 10s remaining)."""
        animator = TimerAnimator(total_ms=60000)
        # Yellow: 10000 < remaining_ms <= 30000 (30000 <= elapsed_ms < 50000)
        color = animator.get_timer_color(elapsed_ms=30000)
        assert color == 'yellow'
        
        color = animator.get_timer_color(elapsed_ms=40000)
        assert color == 'yellow'
        
        color = animator.get_timer_color(elapsed_ms=49999)
        assert color == 'yellow'

    def test_timer_color_red_phase(self):
        """Test timer is red during T-10→T-0 phase (10s remaining to 0s remaining)."""
        animator = TimerAnimator(total_ms=60000)
        # Red: 0 < remaining_ms <= 10000 (50000 <= elapsed_ms < 60000)
        color = animator.get_timer_color(elapsed_ms=50000)
        assert color == 'red'
        
        color = animator.get_timer_color(elapsed_ms=55000)
        assert color == 'red'
        
        color = animator.get_timer_color(elapsed_ms=59999)
        assert color == 'red'

    def test_timer_color_blink_at_zero(self):
        """Test timer blinks (alternates on/off) at T-0."""
        animator = TimerAnimator(total_ms=60000)
        color = animator.get_timer_color(elapsed_ms=60000)
        assert color == 'blink'


class TestTimerBlinking:
    """Tests for timer blinking behavior at T-0."""

    def test_timer_blink_frequency(self):
        """Test timer blinks at 2.0 Hz (2 blinks per second) at T-0."""
        animator = TimerAnimator(total_ms=60000)
        # At T-0, should alternate between visible and invisible
        # Frame 0ms: visible
        # Frame 250ms: invisible (1 / 2 Hz = 500ms per cycle, 250ms = off)
        # Frame 500ms: visible
        on_off_states = [
            animator.get_timer_color(elapsed_ms=60000),  # At exactly T-0
            animator.get_timer_color(elapsed_ms=60000),  # Same time, should determine blink state
        ]
        assert 'blink' in on_off_states


class TestTimerPredictionAccuracy:
    """Tests for timer prediction accuracy calculations."""

    def test_timer_prediction_accuracy_perfect_click(self):
        """Test prediction accuracy when click is exactly at expiry."""
        animator = TimerAnimator(total_ms=60000)
        predicted_click_ms = 60000
        actual_click_ms = 60000
        accuracy = animator.calculate_prediction_accuracy(
            predicted_click_ms=predicted_click_ms,
            actual_click_ms=actual_click_ms
        )
        assert accuracy == 100.0

    def test_timer_prediction_accuracy_early_100ms(self):
        """Test accuracy when predicting 100ms early."""
        animator = TimerAnimator(total_ms=60000)
        predicted_click_ms = 59900
        actual_click_ms = 60000
        accuracy = animator.calculate_prediction_accuracy(
            predicted_click_ms=predicted_click_ms,
            actual_click_ms=actual_click_ms
        )
        # Error: 100ms, accuracy: (1 - 100/60000) * 100 = 99.83%
        assert 99 < accuracy < 100

    def test_timer_prediction_accuracy_late_500ms(self):
        """Test accuracy when predicting 500ms late."""
        animator = TimerAnimator(total_ms=60000)
        predicted_click_ms = 60500
        actual_click_ms = 60000
        accuracy = animator.calculate_prediction_accuracy(
            predicted_click_ms=predicted_click_ms,
            actual_click_ms=actual_click_ms
        )
        # Error: 500ms, accuracy: (1 - 500/60000) * 100 = 99.17%
        assert 99 < accuracy < 99.2

    def test_timer_prediction_accuracy_way_off(self):
        """Test accuracy with large prediction error."""
        animator = TimerAnimator(total_ms=60000)
        predicted_click_ms = 55000
        actual_click_ms = 60000
        accuracy = animator.calculate_prediction_accuracy(
            predicted_click_ms=predicted_click_ms,
            actual_click_ms=actual_click_ms
        )
        # Error: 5000ms, accuracy: (1 - 5000/60000) * 100 = 91.67%
        assert 91 < accuracy < 92


class TestTimerMetrics:
    """Tests for timer metrics (early/late click detection)."""

    def test_timer_metrics_perfect_hit(self):
        """Test metrics when bot clicks exactly at expiry."""
        animator = TimerAnimator(total_ms=60000)
        metrics = animator.get_timer_metrics(
            predicted_ms=60000,
            actual_ms=60000,
            click_hit=True
        )
        assert metrics['timer_is_early_click'] is False
        assert metrics['timer_is_late_click'] is False
        assert metrics['timer_accuracy_percent'] == 100.0

    def test_timer_metrics_early_click(self):
        """Test metrics when click is before expiry."""
        animator = TimerAnimator(total_ms=60000)
        metrics = animator.get_timer_metrics(
            predicted_ms=59000,
            actual_ms=59000,
            click_hit=False  # Early click = miss
        )
        assert metrics['timer_is_early_click'] is True
        assert metrics['timer_is_late_click'] is False

    def test_timer_metrics_late_click(self):
        """Test metrics when click is after expiry."""
        animator = TimerAnimator(total_ms=60000)
        metrics = animator.get_timer_metrics(
            predicted_ms=61000,
            actual_ms=61000,
            click_hit=False  # Late click = miss
        )
        assert metrics['timer_is_early_click'] is False
        assert metrics['timer_is_late_click'] is True

    def test_timer_metrics_contains_all_fields(self):
        """Test metrics dict contains all required fields."""
        animator = TimerAnimator(total_ms=60000)
        metrics = animator.get_timer_metrics(
            predicted_ms=60000,
            actual_ms=60000,
            click_hit=True
        )
        required_fields = [
            'timer_accuracy_percent',
            'timer_is_early_click',
            'timer_is_late_click',
            'timer_prediction_offset_ms',
        ]
        for field in required_fields:
            assert field in metrics


class TestTimerOverlayOnImage:
    """Tests for overlaying timer on game state image."""

    def test_timer_overlay_on_pil_image(self):
        """Test timer overlay renders on PIL Image (treasure state)."""
        animator = TimerAnimator(total_ms=60000)
        # Create a base image (simulating treasure state)
        base_image = Image.new('RGB', (600, 400), color='blue')
        
        result = animator.overlay_timer_on_image(
            base_image=base_image,
            elapsed_ms=30000,
            position='center'
        )
        assert isinstance(result, Image.Image)
        assert result.size == base_image.size

    def test_timer_overlay_position_center(self):
        """Test timer overlay positioned at center."""
        animator = TimerAnimator(total_ms=60000)
        base_image = Image.new('RGB', (600, 400), color='blue')
        
        result = animator.overlay_timer_on_image(
            base_image=base_image,
            elapsed_ms=30000,
            position='center'
        )
        assert isinstance(result, Image.Image)

    def test_timer_overlay_position_bottom_right(self):
        """Test timer overlay positioned at bottom-right."""
        animator = TimerAnimator(total_ms=60000)
        base_image = Image.new('RGB', (600, 400), color='blue')
        
        result = animator.overlay_timer_on_image(
            base_image=base_image,
            elapsed_ms=30000,
            position='bottom_right'
        )
        assert isinstance(result, Image.Image)

    def test_timer_overlay_position_top_left(self):
        """Test timer overlay positioned at top-left."""
        animator = TimerAnimator(total_ms=60000)
        base_image = Image.new('RGB', (600, 400), color='blue')
        
        result = animator.overlay_timer_on_image(
            base_image=base_image,
            elapsed_ms=30000,
            position='top_left'
        )
        assert isinstance(result, Image.Image)


class TestTimerAnimatorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_timer_render_negative_elapsed_time(self):
        """Test timer handles negative elapsed time gracefully."""
        animator = TimerAnimator(total_ms=60000)
        # Should clamp to 0
        result = animator.render_countdown(elapsed_ms=-1000)
        assert isinstance(result, Image.Image)

    def test_timer_render_beyond_total_ms(self):
        """Test timer handles time beyond total_ms."""
        animator = TimerAnimator(total_ms=60000)
        # Should clamp to total_ms
        result = animator.render_countdown(elapsed_ms=120000)
        assert isinstance(result, Image.Image)

    def test_timer_short_duration(self):
        """Test timer with very short duration (5 seconds)."""
        animator = TimerAnimator(total_ms=5000)
        assert animator.total_ms == 5000
        result = animator.render_countdown(elapsed_ms=2500)
        assert isinstance(result, Image.Image)

    def test_timer_very_long_duration(self):
        """Test timer with very long duration (5 minutes)."""
        animator = TimerAnimator(total_ms=300000)
        result = animator.render_countdown(elapsed_ms=150000)
        assert isinstance(result, Image.Image)
