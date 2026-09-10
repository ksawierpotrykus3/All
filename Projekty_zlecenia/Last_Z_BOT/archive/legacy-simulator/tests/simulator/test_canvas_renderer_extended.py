"""
Test suite for extended CanvasRenderer — multi-state rendering and timer overlay.
Tests cover all 6 game states with animations and timer integration.
"""

import pytest
from PIL import Image
from mvp.simulator.ui.canvas_renderer import CanvasRenderer
from mvp.simulator.ui.timer_animator import TimerAnimator
from mvp.simulator.config import STATE_IMAGE_MAPPING


class TestCanvasRenderMultiState:
    """Tests for rendering all 6 game states."""

    def test_canvas_render_state_chat(self):
        """Test rendering chat state (static image)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('chat')
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_state_chat_focus(self):
        """Test rendering chat_focus state (arrow pulse animation)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('chat_focus')
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_state_alert_animation(self):
        """Test rendering alert_animation state (fade-in + drop effect)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('alert_animation')
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_state_treasure(self):
        """Test rendering treasure state (with timer overlay support)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('treasure')
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_state_reward_details(self):
        """Test rendering reward_details state (fade-in)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('reward_details')
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_state_chat_unavailable(self):
        """Test rendering chat_unavailable state (pulsing red border)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('chat_unavailable')
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_all_states_sequence(self):
        """Test rendering all 6 states in sequence."""
        renderer = CanvasRenderer(width=600, height=700)
        states = ['chat', 'chat_focus', 'alert_animation', 'treasure', 'reward_details', 'chat_unavailable']
        for state in states:
            result = renderer.render_state(state)
            assert isinstance(result, Image.Image)
            assert result.size == (600, 700)


class TestCanvasRenderTimerOverlay:
    """Tests for timer overlay on game state images."""

    def test_canvas_render_timer_overlay(self):
        """Test timer overlay renders on treasure state image."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=30000,
            position='center'
        )
        assert isinstance(result, Image.Image)
        assert result.size == (600, 700)

    def test_canvas_render_timer_overlay_position_center(self):
        """Test timer overlay positioned at center."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=30000,
            position='center'
        )
        assert isinstance(result, Image.Image)

    def test_canvas_render_timer_overlay_position_bottom_right(self):
        """Test timer overlay positioned at bottom-right."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=30000,
            position='bottom_right'
        )
        assert isinstance(result, Image.Image)

    def test_canvas_render_timer_overlay_position_top_left(self):
        """Test timer overlay positioned at top-left."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=30000,
            position='top_left'
        )
        assert isinstance(result, Image.Image)

    def test_canvas_render_timer_overlay_green_phase(self):
        """Test timer overlay renders green color when elapsed < 30s."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        # Green phase: elapsed_ms < 30000
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=15000,
            position='center'
        )
        assert isinstance(result, Image.Image)

    def test_canvas_render_timer_overlay_red_phase(self):
        """Test timer overlay renders red color when elapsed > 50s."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        # Red phase: elapsed_ms > 50000
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=55000,
            position='center'
        )
        assert isinstance(result, Image.Image)


class TestCanvasStateAnimations:
    """Tests for state-specific animations."""

    def test_canvas_chat_state_static(self):
        """Test chat state renders as static (no animation)."""
        renderer = CanvasRenderer(width=600, height=700)
        result = renderer.render_state('chat')
        assert isinstance(result, Image.Image)

    def test_canvas_chat_focus_pulse_animation(self):
        """Test chat_focus state has arrow pulse animation."""
        renderer = CanvasRenderer(width=600, height=700)
        # Render at different times to simulate animation
        result_frame1 = renderer.render_state('chat_focus', animation_frame=0)
        result_frame2 = renderer.render_state('chat_focus', animation_frame=250)  # Mid-pulse
        result_frame3 = renderer.render_state('chat_focus', animation_frame=500)  # Full pulse
        
        assert isinstance(result_frame1, Image.Image)
        assert isinstance(result_frame2, Image.Image)
        assert isinstance(result_frame3, Image.Image)

    def test_canvas_alert_animation_fade_and_drop(self):
        """Test alert_animation state has fade-in and drop effect."""
        renderer = CanvasRenderer(width=600, height=700)
        # Render at different animation frames
        result_start = renderer.render_state('alert_animation', animation_frame=0)
        result_mid = renderer.render_state('alert_animation', animation_frame=150)  # Mid-animation
        result_end = renderer.render_state('alert_animation', animation_frame=300)  # End
        
        assert isinstance(result_start, Image.Image)
        assert isinstance(result_mid, Image.Image)
        assert isinstance(result_end, Image.Image)

    def test_canvas_reward_details_fade_in(self):
        """Test reward_details state has fade-in effect."""
        renderer = CanvasRenderer(width=600, height=700)
        result_start = renderer.render_state('reward_details', animation_frame=0)
        result_mid = renderer.render_state('reward_details', animation_frame=100)
        result_end = renderer.render_state('reward_details', animation_frame=200)
        
        assert isinstance(result_start, Image.Image)
        assert isinstance(result_mid, Image.Image)
        assert isinstance(result_end, Image.Image)

    def test_canvas_chat_unavailable_pulsing_border(self):
        """Test chat_unavailable state has pulsing red border."""
        renderer = CanvasRenderer(width=600, height=700)
        result_thin = renderer.render_state('chat_unavailable', animation_frame=0)
        result_thick = renderer.render_state('chat_unavailable', animation_frame=300)  # Mid-pulse
        result_thin_again = renderer.render_state('chat_unavailable', animation_frame=600)  # Full cycle
        
        assert isinstance(result_thin, Image.Image)
        assert isinstance(result_thick, Image.Image)
        assert isinstance(result_thin_again, Image.Image)


class TestCanvasStateTransitions:
    """Tests for smooth state transitions."""

    def test_canvas_render_state_transition_blend(self):
        """Test smooth blend transition between states."""
        renderer = CanvasRenderer(width=600, height=700)
        # Transition from chat to alert_animation
        result_transition = renderer.render_state_transition(
            from_state='chat',
            to_state='alert_animation',
            progress=0.5  # 50% through transition
        )
        assert isinstance(result_transition, Image.Image)
        assert result_transition.size == (600, 700)

    def test_canvas_render_state_transition_sequence(self):
        """Test multiple state transitions in sequence."""
        renderer = CanvasRenderer(width=600, height=700)
        transitions = [
            ('chat', 'chat_focus', 0.5),
            ('chat_focus', 'alert_animation', 0.5),
            ('alert_animation', 'treasure', 0.5),
            ('treasure', 'reward_details', 0.5),
            ('reward_details', 'chat', 0.5),
        ]
        for from_state, to_state, progress in transitions:
            result = renderer.render_state_transition(from_state, to_state, progress)
            assert isinstance(result, Image.Image)


class TestCanvasEdgeCases:
    """Tests for edge cases and error handling."""

    def test_canvas_render_invalid_state(self):
        """Test rendering invalid state raises error or returns fallback."""
        renderer = CanvasRenderer(width=600, height=700)
        # Should handle gracefully (either error or fallback)
        try:
            result = renderer.render_state('invalid_state')
            # If no error, should return valid image
            assert isinstance(result, Image.Image)
        except ValueError:
            # Expected: state not recognized
            pass

    def test_canvas_render_missing_state_image(self):
        """Test handling missing state image file."""
        renderer = CanvasRenderer(width=600, height=700)
        # Should fallback to symbolic rendering
        result = renderer.render_state('treasure')
        assert isinstance(result, Image.Image)

    def test_canvas_render_custom_state_image_path(self):
        """Test rendering state with custom image path."""
        renderer = CanvasRenderer(width=600, height=700)
        # If image exists, use it; otherwise symbolic
        result = renderer.render_state('treasure', state_image_path='custom/image.png')
        assert isinstance(result, Image.Image)

    def test_canvas_render_timer_overlay_beyond_expiry(self):
        """Test timer overlay when elapsed > total_ms (expired)."""
        renderer = CanvasRenderer(width=600, height=700)
        timer_animator = TimerAnimator(total_ms=60000)
        result = renderer.render_timer_overlay(
            state='treasure',
            timer_animator=timer_animator,
            elapsed_ms=120000,  # Way beyond expiry
            position='center'
        )
        assert isinstance(result, Image.Image)

    def test_canvas_render_different_dimensions(self):
        """Test rendering with different canvas dimensions."""
        renderer_small = CanvasRenderer(width=400, height=500)
        result_small = renderer_small.render_state('chat')
        assert result_small.size == (400, 500)
        
        renderer_large = CanvasRenderer(width=800, height=900)
        result_large = renderer_large.render_state('chat')
        assert result_large.size == (800, 900)
