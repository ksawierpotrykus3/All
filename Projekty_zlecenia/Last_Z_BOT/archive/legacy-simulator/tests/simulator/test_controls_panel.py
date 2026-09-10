# tests/simulator/test_controls_panel.py
"""
Unit tests for ControlsPanel: hotkey handling, button clicks, perturbation menu.

Tests:
- Initialization
- Button click callbacks (pause, skip, reset, variant)
- Hotkey registration and invocation
- Perturbation registration and application
- Status display updates
- Callback unregistration
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch, call

from mvp.simulator.ui.controls_panel import ControlsPanel


class TestControlsPanelInit:
    """Test ControlsPanel initialization."""

    def test_init_creates_frame(self):
        """ControlsPanel should create Tkinter frame."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            assert cp.frame is not None
            assert cp.parent == root
        finally:
            root.destroy()

    def test_init_with_empty_callbacks(self):
        """ControlsPanel should initialize with empty callback lists."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            assert cp.button_callbacks == {
                'pause': [],
                'skip': [],
                'reset': [],
                'variant': [],
            }
            assert cp.hotkey_callbacks == {}
            assert cp.perturb_callbacks == {}
        finally:
            root.destroy()

    def test_init_with_perturbation_definitions(self):
        """ControlsPanel should define all perturbation types."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            assert 'block_clicks' in cp.perturbations
            assert 'inject_cpu' in cp.perturbations
            assert 'change_chat' in cp.perturbations
            assert 'delay_alert' in cp.perturbations
            assert 'add_ocr_noise' in cp.perturbations
        finally:
            root.destroy()

    def test_init_creates_buttons(self):
        """ControlsPanel should create button widgets."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            assert cp.pause_button is not None
            assert cp.skip_button is not None
            assert cp.reset_button is not None
            assert cp.variant_button is not None
            assert cp.perturb_button is not None
        finally:
            root.destroy()


class TestButtonCallbacks:
    """Test button click callbacks."""

    def test_pause_button_callback(self):
        """Pause button should invoke registered pause callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_button_callback('pause', callback)
            
            cp.on_pause_clicked()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_skip_button_callback(self):
        """Skip button should invoke registered skip callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_button_callback('skip', callback)
            
            cp.on_skip_clicked()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_reset_button_callback(self):
        """Reset button should invoke registered reset callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_button_callback('reset', callback)
            
            cp.on_reset_clicked()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_variant_button_callback(self):
        """Variant button should invoke registered variant callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_button_callback('variant', callback)
            
            cp.on_variant_clicked()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_multiple_button_callbacks(self):
        """Button should invoke multiple registered callbacks in order."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback1 = Mock()
            callback2 = Mock()
            callback3 = Mock()
            
            cp.register_button_callback('pause', callback1)
            cp.register_button_callback('pause', callback2)
            cp.register_button_callback('pause', callback3)
            
            cp.on_pause_clicked()
            
            callback1.assert_called_once()
            callback2.assert_called_once()
            callback3.assert_called_once()
        finally:
            root.destroy()

    def test_button_callback_exception_handling(self):
        """Button should handle exceptions in callbacks gracefully."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback_error = Mock(side_effect=Exception('Test error'))
            callback_ok = Mock()
            
            cp.register_button_callback('pause', callback_error)
            cp.register_button_callback('pause', callback_ok)
            
            # Should not raise
            cp.on_pause_clicked()
            
            callback_error.assert_called_once()
            callback_ok.assert_called_once()
        finally:
            root.destroy()


class TestHotkeyCallbacks:
    """Test hotkey registration and invocation."""

    def test_register_hotkey_space(self):
        """Register space hotkey callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            callback_id = cp.register_hotkey_callback('space', callback)
            
            assert callback_id is not None
            assert 'space' in cp.hotkey_callbacks
            assert callback in cp.hotkey_callbacks['space']
        finally:
            root.destroy()

    def test_invoke_space_hotkey(self):
        """Space hotkey should invoke registered callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_hotkey_callback('space', callback)
            
            cp.on_hotkey_space()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_invoke_p_hotkey(self):
        """P hotkey should invoke pause callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_hotkey_callback('p', callback)
            
            cp.on_hotkey_p()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_invoke_r_hotkey(self):
        """R hotkey should invoke reset callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_hotkey_callback('r', callback)
            
            cp.on_hotkey_r()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_invoke_c_hotkey(self):
        """C hotkey should invoke change_variant callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_hotkey_callback('c', callback)
            
            cp.on_hotkey_c()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_invoke_s_hotkey(self):
        """S hotkey should invoke CPU spike callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_hotkey_callback('s', callback)
            
            cp.on_hotkey_s()
            
            callback.assert_called_once()
        finally:
            root.destroy()

    def test_multiple_hotkey_callbacks(self):
        """Hotkey should invoke multiple registered callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback1 = Mock()
            callback2 = Mock()
            
            cp.register_hotkey_callback('space', callback1)
            cp.register_hotkey_callback('space', callback2)
            
            cp.on_hotkey_space()
            
            callback1.assert_called_once()
            callback2.assert_called_once()
        finally:
            root.destroy()

    def test_hotkey_callback_exception_handling(self):
        """Hotkey should handle exceptions in callbacks gracefully."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback_error = Mock(side_effect=Exception('Test error'))
            callback_ok = Mock()
            
            cp.register_hotkey_callback('space', callback_error)
            cp.register_hotkey_callback('space', callback_ok)
            
            # Should not raise
            cp.on_hotkey_space()
            
            callback_error.assert_called_once()
            callback_ok.assert_called_once()
        finally:
            root.destroy()


class TestPerturbationCallbacks:
    """Test perturbation registration and application."""

    def test_register_perturbation_callback(self):
        """Register perturbation callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            callback_id = cp.register_perturb_callback('block_clicks', callback)
            
            assert callback_id is not None
            assert 'block_clicks' in cp.perturb_callbacks
        finally:
            root.destroy()

    def test_apply_chaotic_timer_perturbation(self):
        """Apply block_clicks perturbation."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_perturb_callback('block_clicks', callback)
            
            result = cp.apply_perturbation('block_clicks')
            
            assert result is True
            callback.assert_called_once()
            assert 'Block Clicks' in cp.get_status()
        finally:
            root.destroy()

    def test_apply_frozen_timer_perturbation(self):
        """Apply inject_cpu perturbation."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_perturb_callback('inject_cpu', callback)
            
            result = cp.apply_perturbation('inject_cpu')
            
            assert result is True
            callback.assert_called_once()
            assert 'Inject CPU' in cp.get_status()
        finally:
            root.destroy()

    def test_apply_accelerated_timer_perturbation(self):
        """Apply change_chat perturbation."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_perturb_callback('change_chat', callback)
            
            result = cp.apply_perturbation('change_chat')
            
            assert result is True
            callback.assert_called_once()
            assert 'Change Chat' in cp.get_status()
        finally:
            root.destroy()

    def test_apply_hidden_timer_perturbation(self):
        """Apply delay_alert perturbation."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_perturb_callback('delay_alert', callback)
            
            result = cp.apply_perturbation('delay_alert')
            
            assert result is True
            callback.assert_called_once()
            assert 'Delay Alert' in cp.get_status()
        finally:
            root.destroy()

    def test_apply_distracted_chat_perturbation(self):
        """Apply add_ocr_noise perturbation."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            cp.register_perturb_callback('add_ocr_noise', callback)
            
            result = cp.apply_perturbation('add_ocr_noise')
            
            assert result is True
            callback.assert_called_once()
            assert 'Add OCR Noise' in cp.get_status()
        finally:
            root.destroy()

    def test_multiple_perturbation_callbacks(self):
        """Perturbation should invoke multiple registered callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback1 = Mock()
            callback2 = Mock()
            
            cp.register_perturb_callback('block_clicks', callback1)
            cp.register_perturb_callback('block_clicks', callback2)
            
            cp.apply_perturbation('block_clicks')
            
            callback1.assert_called_once()
            callback2.assert_called_once()
        finally:
            root.destroy()

    def test_perturbation_callback_exception_handling(self):
        """Perturbation should handle exceptions in callbacks gracefully."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback_error = Mock(side_effect=Exception('Test error'))
            callback_ok = Mock()
            
            cp.register_perturb_callback('block_clicks', callback_error)
            cp.register_perturb_callback('block_clicks', callback_ok)
            
            result = cp.apply_perturbation('block_clicks')
            
            assert result is True
            callback_error.assert_called_once()
            callback_ok.assert_called_once()
        finally:
            root.destroy()


class TestCallbackUnregistration:
    """Test callback unregistration."""

    def test_unregister_button_callback(self):
        """Unregister button callback."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            callback_id = cp.register_button_callback('pause', callback)
            
            # Unregister
            result = cp.unregister_button_callback('pause', callback_id)
            
            assert result is True
            
            # Callback should not be invoked
            cp.on_pause_clicked()
            callback.assert_not_called()
        finally:
            root.destroy()

    def test_unregister_invalid_callback(self):
        """Unregister with invalid ID should return False."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            result = cp.unregister_button_callback('pause', 'invalid_id')
            assert result is False
        finally:
            root.destroy()


class TestStatusDisplay:
    """Test status display updates."""

    def test_set_status(self):
        """Set status should update status label."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            result = cp.set_status('Test Status')
            
            assert result is True
            assert cp.get_status() == 'Test Status'
            assert cp.status_label.cget('text') == 'Test Status'
        finally:
            root.destroy()

    def test_get_status_initial(self):
        """get_status should return initial status."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            status = cp.get_status()
            assert status == 'Ready'
        finally:
            root.destroy()

    def test_set_status_exception_handling(self):
        """set_status should handle exceptions gracefully."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            # Destroy label to cause error
            cp.status_label.destroy()
            
            result = cp.set_status('New Status')
            
            # Should return False on error
            assert result is False
        finally:
            root.destroy()


class TestIntegration:
    """Integration tests for ControlsPanel."""

    def test_button_and_hotkey_same_callback(self):
        """Same callback can be registered for button and hotkey."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            callback = Mock()
            
            cp.register_button_callback('pause', callback)
            cp.register_hotkey_callback('p', callback)
            
            cp.on_pause_clicked()
            assert callback.call_count == 1
            
            cp.on_hotkey_p()
            assert callback.call_count == 2
        finally:
            root.destroy()

    def test_perturbation_applies_without_callback(self):
        """Perturbation should apply even without registered callbacks."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            
            result = cp.apply_perturbation('block_clicks')
            
            assert result is True
            assert 'Block Clicks' in cp.get_status()
        finally:
            root.destroy()

    def test_status_updates_after_perturbation(self):
        """Status should update after perturbation application."""
        root = tk.Tk()
        try:
            cp = ControlsPanel(root)
            initial_status = cp.get_status()
            
            cp.apply_perturbation('block_clicks')
            
            new_status = cp.get_status()
            assert new_status != initial_status
            assert 'Block Clicks' in new_status
        finally:
            root.destroy()


__all__ = ['TestControlsPanelInit', 'TestButtonCallbacks', 'TestHotkeyCallbacks',
           'TestPerturbationCallbacks', 'TestCallbackUnregistration', 'TestStatusDisplay',
           'TestIntegration']
