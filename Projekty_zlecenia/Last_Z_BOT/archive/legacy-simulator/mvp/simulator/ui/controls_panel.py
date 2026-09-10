"""
Controls Panel for simulator control and perturbation.
Provides buttons, hotkey bindings, and perturbation menu.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Any
import uuid
import logging

logger = logging.getLogger(__name__)


class ControlsPanel:
    """
    Control panel with buttons, hotkeys, and perturbation menu.
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize ControlsPanel.

        Args:
            parent: Parent Tkinter widget
        """
        self.parent = parent
        
        # Callback registries
        self.button_callbacks: Dict[str, List[Callable]] = {
            'pause': [],
            'skip': [],
            'reset': [],
            'variant': [],
        }
        self.hotkey_callbacks: Dict[str, List[Callable]] = {}
        self.perturb_callbacks: Dict[str, List[Callable]] = {}
        
        # Callback IDs for unregistration
        self.callback_ids: Dict[str, str] = {}
        
        # Status
        self.status = 'Ready'
        
        # Perturbations (5 core perturbation types)
        self.perturbations = {
            'block_clicks': 'Block Clicks (3 sec)',
            'inject_cpu': 'Inject CPU (80% spike)',
            'change_chat': 'Change Chat (randomize)',
            'delay_alert': 'Delay Alert (+2s)',
            'add_ocr_noise': 'Add OCR Noise (-20%)',
        }
        
        # Create UI
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_button_panel()
        self._create_perturbation_panel()
        self._create_status_panel()

    def _create_button_panel(self) -> None:
        """Create button panel with control buttons."""
        button_frame = ttk.LabelFrame(self.frame, text='Controls', padding=10)
        button_frame.pack(fill=tk.X, pady=5)
        
        # Row 1
        row1 = ttk.Frame(button_frame)
        row1.pack(fill=tk.X, pady=3)
        
        self.pause_button = ttk.Button(
            row1, text='Pause (P)', width=14,
            command=self.on_pause_clicked
        )
        self.pause_button.pack(side=tk.LEFT, padx=2)
        
        self.skip_button = ttk.Button(
            row1, text='Skip (S)', width=14,
            command=self.on_skip_clicked
        )
        self.skip_button.pack(side=tk.LEFT, padx=2)
        
        # Row 2
        row2 = ttk.Frame(button_frame)
        row2.pack(fill=tk.X, pady=3)
        
        self.reset_button = ttk.Button(
            row2, text='Reset (R)', width=14,
            command=self.on_reset_clicked
        )
        self.reset_button.pack(side=tk.LEFT, padx=2)
        
        self.variant_button = ttk.Button(
            row2, text='Change Variant (C)', width=14,
            command=self.on_variant_clicked
        )
        self.variant_button.pack(side=tk.LEFT, padx=2)

    def _create_perturbation_panel(self) -> None:
        """Create perturbation menu panel."""
        perturb_frame = ttk.LabelFrame(self.frame, text='Perturbations', padding=10)
        perturb_frame.pack(fill=tk.X, pady=5)
        
        # Perturb menu button
        self.perturb_button = ttk.Button(
            perturb_frame, text='Apply Perturbation ▼',
            command=self._show_perturb_menu
        )
        self.perturb_button.pack(fill=tk.X, pady=3)
        
        # Perturb options (initially hidden)
        options_frame = ttk.Frame(perturb_frame)
        options_frame.pack(fill=tk.X)
        
        self.perturb_buttons = {}
        for perturb_key, perturb_label in self.perturbations.items():
            btn = ttk.Button(
                options_frame, text=perturb_label, width=20,
                command=lambda k=perturb_key: self.apply_perturbation(k)
            )
            btn.pack(fill=tk.X, pady=1)
            self.perturb_buttons[perturb_key] = btn

    def _create_status_panel(self) -> None:
        """Create status display panel."""
        status_frame = ttk.LabelFrame(self.frame, text='Status', padding=10)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = tk.Label(
            status_frame, text=self.status,
            fg='#4caf50', font=('Courier', 11, 'bold'),
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X)
        
        # Hotkey info
        info_frame = ttk.Frame(status_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        
        info_text = tk.Label(
            info_frame,
            text='Hotkeys: Space=Alert | P=Pause | S=Skip | R=Reset | C=Variant | Q=Quit',
            fg='#666', font=('Helvetica', 8)
        )
        info_text.pack(anchor=tk.W)

    def _show_perturb_menu(self) -> None:
        """Show perturbation menu (no-op for now - buttons always visible)."""
        pass

    def on_pause_clicked(self) -> None:
        """Handle pause button click."""
        self._invoke_button_callbacks('pause')

    def on_skip_clicked(self) -> None:
        """Handle skip button click."""
        self._invoke_button_callbacks('skip')

    def on_reset_clicked(self) -> None:
        """Handle reset button click."""
        self._invoke_button_callbacks('reset')

    def on_variant_clicked(self) -> None:
        """Handle variant button click."""
        self._invoke_button_callbacks('variant')

    def on_hotkey_space(self) -> None:
        """Handle Space hotkey (trigger alert)."""
        self._invoke_hotkey_callbacks('space')

    def on_hotkey_p(self) -> None:
        """Handle P hotkey (pause)."""
        self._invoke_hotkey_callbacks('p')

    def on_hotkey_r(self) -> None:
        """Handle R hotkey (reset)."""
        self._invoke_hotkey_callbacks('r')

    def on_hotkey_c(self) -> None:
        """Handle C hotkey (change variant)."""
        self._invoke_hotkey_callbacks('c')

    def on_hotkey_s(self) -> None:
        """Handle S hotkey (CPU spike)."""
        self._invoke_hotkey_callbacks('s')

    def register_button_callback(self, button: str, callback: Callable) -> str:
        """
        Register callback for button.

        Args:
            button: Button name ('pause', 'skip', 'reset', 'variant')
            callback: Callable to invoke

        Returns:
            Callback ID for unregistration
        """
        if button in self.button_callbacks:
            self.button_callbacks[button].append(callback)
            callback_id = str(uuid.uuid4())[:8]
            self.callback_ids[callback_id] = (button, callback)
            return callback_id
        return None

    def register_hotkey_callback(self, hotkey: str, callback: Callable) -> str:
        """
        Register callback for hotkey.

        Args:
            hotkey: Hotkey name ('space', 'p', 'r', 'c', 's')
            callback: Callable to invoke

        Returns:
            Callback ID for unregistration
        """
        if hotkey not in self.hotkey_callbacks:
            self.hotkey_callbacks[hotkey] = []
        
        self.hotkey_callbacks[hotkey].append(callback)
        callback_id = str(uuid.uuid4())[:8]
        self.callback_ids[callback_id] = (hotkey, callback)
        return callback_id

    def register_perturb_callback(self, perturb: str, callback: Callable) -> str:
        """
        Register callback for perturbation.

        Args:
            perturb: Perturbation name
            callback: Callable to invoke

        Returns:
            Callback ID for unregistration
        """
        if perturb not in self.perturb_callbacks:
            self.perturb_callbacks[perturb] = []
        
        self.perturb_callbacks[perturb].append(callback)
        callback_id = str(uuid.uuid4())[:8]
        self.callback_ids[callback_id] = (perturb, callback)
        return callback_id

    def unregister_button_callback(self, button: str, callback_id: str) -> bool:
        """
        Unregister button callback.

        Args:
            button: Button name
            callback_id: Callback ID returned from register

        Returns:
            True if successful
        """
        try:
            if callback_id in self.callback_ids:
                _, callback = self.callback_ids[callback_id]
                if callback in self.button_callbacks.get(button, []):
                    self.button_callbacks[button].remove(callback)
                    del self.callback_ids[callback_id]
                    return True
            return False
        except Exception as e:
            logger.error(f"Error unregistering callback: {e}")
            return False

    def apply_perturbation(self, perturb: str) -> bool:
        """
        Apply perturbation.

        Args:
            perturb: Perturbation name

        Returns:
            True if successful
        """
        self._invoke_perturb_callbacks(perturb)
        self.set_status(f'Perturb: {self.perturbations.get(perturb, perturb)}')
        return True

    def set_status(self, status: str) -> bool:
        """
        Set status text.

        Args:
            status: Status text

        Returns:
            True if successful
        """
        try:
            self.status = status
            self.status_label.config(text=status)
            return True
        except Exception as e:
            logger.error(f"Error setting status: {e}")
            return False

    def get_status(self) -> str:
        """Get current status."""
        return self.status

    def _invoke_button_callbacks(self, button: str) -> None:
        """Invoke all callbacks for button."""
        for callback in self.button_callbacks.get(button, []):
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in button callback: {e}")

    def _invoke_hotkey_callbacks(self, hotkey: str) -> None:
        """Invoke all callbacks for hotkey."""
        for callback in self.hotkey_callbacks.get(hotkey, []):
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in hotkey callback: {e}")

    def _invoke_perturb_callbacks(self, perturb: str) -> None:
        """Invoke all callbacks for perturbation."""
        for callback in self.perturb_callbacks.get(perturb, []):
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in perturb callback: {e}")


__all__ = ['ControlsPanel']
