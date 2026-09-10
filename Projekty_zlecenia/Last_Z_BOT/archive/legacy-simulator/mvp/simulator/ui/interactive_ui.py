"""
Interactive UI for Extended Game Simulator.
Tkinter-based interface with game canvas, metrics dashboard, timeline, and controls.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Any, Dict
import threading
from queue import Queue
from mvp.simulator.ui.canvas_renderer import CanvasRenderer
from mvp.simulator.ui.controls_panel import ControlsPanel
from mvp.simulator.ui.metrics_dashboard import MetricsDashboard
from mvp.simulator.core import GameState
import logging

logger = logging.getLogger(__name__)


class InteractiveUI:
    """
    Main Tkinter UI window for extended game simulator.
    Layout: Left panel (600x700) for game canvas, right panel (400x700) for metrics.
    """

    def __init__(self, width: int = 1400, height: int = 900):
        """
        Initialize InteractiveUI.

        Args:
            width: Window width
            height: Window height
        """
        self.width = width
        self.height = height
        self.is_running = False
        
        # Create root window
        self.root = tk.Tk()
        self.root.title('Extended Game Simulator - Interactive UI')
        self.root.geometry(f'{width}x{height}')
        self.root.resizable(False, False)
        
        # Configure colors
        self.root.config(bg='#1e1e1e')
        
        # Create main frames
        self._create_layout()
        
        # Event queues
        self.metrics_queue: Queue = Queue()
        self.state_queue: Queue = Queue()
        self.event_queue: Queue = Queue()
        
        # Callbacks
        self.on_hotkey_callbacks: Dict[str, Callable] = {}
        self.on_state_change_callback: Optional[Callable] = None
        
        # Timeline events buffer
        self.timeline_events = []
        
        # Current metrics
        self.current_metrics = {}
        
        # Initialize button references (will be set in _create_right_panel)
        self.pause_button: Optional[tk.Button] = None
        self.skip_button: Optional[tk.Button] = None
        self.reset_button: Optional[tk.Button] = None
        self.variant_button: Optional[tk.Button] = None
        self.cpu_spike_button: Optional[tk.Button] = None
        self.quit_button: Optional[tk.Button] = None
        self.active_variant_label: Optional[tk.Label] = None
        
        # Macro image preloading for Task 5
        self._preload_macro_images()

    def _create_layout(self) -> None:
        """
        Create UI layout with left and right panels.
        
        Layout:
        - Left panel (600x700): Game canvas
        - Right panel (400x700): Metrics, timeline, controls
        - Total width: 1000px (600 + 400), Height: 700px
        """
        # Main container - no padding for tight layout
        main_container = tk.Frame(self.root, bg='#1e1e1e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # LEFT PANEL (600x700) - Game Canvas
        # Dark background (#1a1a1a) for contrast with green metrics
        self.left_panel = tk.Frame(main_container, width=600, height=700, bg='#1a1a1a')
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=0, pady=0)
        self.left_panel.pack_propagate(False)  # Fixed size
        
        # Game canvas (600x700) - No padding
        self.game_canvas = tk.Canvas(
            self.left_panel, 
            width=600, height=700,
            bg='#1a1a1a', 
            relief=tk.FLAT, 
            bd=0,
            highlightthickness=0  # Remove border
        )
        self.game_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Create canvas renderer
        self.canvas_renderer = CanvasRenderer(self.game_canvas, width=600, height=700)
        
        # RIGHT PANEL (400x700) - Metrics Dashboard
        # Darker background (#1e1e1e) for metrics panel
        self.right_panel = tk.Frame(main_container, width=400, height=700, bg='#1e1e1e')
        self.right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.right_panel.pack_propagate(False)  # Fixed size
        
        # Create right panel sections
        self._create_right_panel()
        
        # Bind window close
        self.root.protocol('WM_DELETE_WINDOW', self._on_window_close)

    def _create_right_panel(self) -> None:
        """
        Create right panel with three sections:
        1. Metrics Dashboard (using MetricsDashboard widget) - Real-time metrics
        2. Timeline Events (350px) - Scrollable event list
        3. Controls (200px) - Buttons, labels, perturbation menu
        
        Layout: Vertical stacking, total height 700px
        """
        # SECTION 1: Metrics Dashboard (Real-time metrics with process_queue)
        # ===================================================================
        metrics_frame = tk.Frame(
            self.right_panel, 
            width=400, height=200,
            bg='#1e1e1e', 
            relief=tk.SUNKEN, bd=1
        )
        metrics_frame.pack(side=tk.TOP, fill=tk.X, expand=False, padx=5, pady=5)
        metrics_frame.pack_propagate(False)
        
        # Create MetricsDashboard widget
        self.metrics_dashboard = MetricsDashboard(
            parent=metrics_frame,
            width=400, 
            height=200
        )
        self.metrics_dashboard.frame.pack(fill=tk.BOTH, expand=True)
        
        # Legacy support: store metric labels (deprecated but kept for compatibility)
        self.metrics_labels = {}
        
        # SECTION 2: Timeline Events (350px height)
        # =========================================
        timeline_frame = tk.Frame(
            self.right_panel,
            width=400, height=350,
            bg='#1e1e1e',
            relief=tk.SUNKEN, bd=1
        )
        timeline_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        timeline_frame.pack_propagate(False)
        
        # Timeline title
        timeline_title = tk.Label(
            timeline_frame, text='Timeline Events',
            bg='#1e1e1e', fg='#00ff00',
            font=('Courier', 10, 'bold')
        )
        timeline_title.pack(anchor=tk.W, padx=5, pady=2)
        
        # Timeline scrollbar
        scrollbar = tk.Scrollbar(timeline_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        
        # Timeline listbox - max 20 events
        self.timeline_listbox = tk.Listbox(
            timeline_frame,
            width=50, height=18,  # ~18 lines visible
            bg='#2e2e2e', fg='#aaa',
            yscrollcommand=scrollbar.set,
            font=('Courier', 8),
            relief=tk.FLAT, bd=1,
            highlightthickness=0
        )
        self.timeline_listbox.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True,
            padx=5, pady=5
        )
        scrollbar.config(command=self.timeline_listbox.yview)
        
        # SECTION 3: Controls (200px height)
        # ==================================
        controls_frame = tk.Frame(
            self.right_panel,
            width=400, height=200,
            bg='#1e1e1e',
            relief=tk.SUNKEN, bd=1
        )
        controls_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=5, pady=5)
        controls_frame.pack_propagate(False)
        
        # Controls title
        controls_title = tk.Label(
            controls_frame, text='Controls & Perturbations',
            bg='#1e1e1e', fg='#00ff00',
            font=('Courier', 10, 'bold')
        )
        controls_title.pack(anchor=tk.W, padx=5, pady=2)
        
        # Controls content frame
        controls_content = tk.Frame(controls_frame, bg='#1e1e1e')
        controls_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button row 1: Pause, Skip, Reset
        button_row1 = tk.Frame(controls_content, bg='#1e1e1e')
        button_row1.pack(fill=tk.X, pady=2)
        
        self.pause_button = tk.Button(
            button_row1, text='Pause (P)', width=12,
            bg='#444', fg='#fff', font=('Courier', 8),
            relief=tk.RAISED, bd=1,
            activebackground='#555', activeforeground='#0f0'
        )
        self.pause_button.pack(side=tk.LEFT, padx=1)
        
        self.skip_button = tk.Button(
            button_row1, text='Skip (S)', width=12,
            bg='#444', fg='#fff', font=('Courier', 8),
            relief=tk.RAISED, bd=1,
            activebackground='#555', activeforeground='#0f0'
        )
        self.skip_button.pack(side=tk.LEFT, padx=1)
        
        self.reset_button = tk.Button(
            button_row1, text='Reset (R)', width=12,
            bg='#444', fg='#fff', font=('Courier', 8),
            relief=tk.RAISED, bd=1,
            activebackground='#555', activeforeground='#0f0'
        )
        self.reset_button.pack(side=tk.LEFT, padx=1)
        
        # Button row 2: Change Variant, Quit
        button_row2 = tk.Frame(controls_content, bg='#1e1e1e')
        button_row2.pack(fill=tk.X, pady=2)
        
        self.variant_button = tk.Button(
            button_row2, text='Variant (C)', width=12,
            bg='#444', fg='#fff', font=('Courier', 8),
            relief=tk.RAISED, bd=1,
            activebackground='#555', activeforeground='#0f0'
        )
        self.variant_button.pack(side=tk.LEFT, padx=1)
        
        self.cpu_spike_button = tk.Button(
            button_row2, text='CPU Spike', width=12,
            bg='#444', fg='#fff', font=('Courier', 8),
            relief=tk.RAISED, bd=1,
            activebackground='#555', activeforeground='#0f0'
        )
        self.cpu_spike_button.pack(side=tk.LEFT, padx=1)
        
        self.quit_button = tk.Button(
            button_row2, text='Quit (Q)', width=12,
            bg='#c41c3b', fg='#fff', font=('Courier', 8),
            relief=tk.RAISED, bd=1,
            activebackground='#e63260', activeforeground='#fff'
        )
        self.quit_button.pack(side=tk.LEFT, padx=1)
        
        # Current state display
        state_label = tk.Label(
            controls_content, text='Active Variant:',
            bg='#1e1e1e', fg='#888',
            font=('Courier', 8)
        )
        state_label.pack(anchor=tk.W, pady=(5, 2))
        
        self.active_variant_label = tk.Label(
            controls_content, text='default',
            bg='#1e1e1e', fg='#00ff00',
            font=('Courier', 8, 'bold')
        )
        self.active_variant_label.pack(anchor=tk.W)
        
        # Hotkeys info
        info_text = tk.Label(
            controls_content,
            text='Space=Alert | Q=Quit',
            bg='#1e1e1e', fg='#666',
            font=('Courier', 7)
        )
        info_text.pack(anchor=tk.W, pady=(2, 0))

    def render_game_state(self, state: GameState) -> bool:
        """
        Render game state on canvas.

        Args:
            state: Current GameState

        Returns:
            True if successful
        """
        try:
            return self.canvas_renderer.render_state(state)
        except Exception as e:
            logger.error(f"Error rendering state: {e}")
            return False

    def update_metrics_display(self, metrics: Dict[str, Any]) -> bool:
        """
        Update metrics display.

        Args:
            metrics: Dictionary with metric values

        Returns:
            True if successful
        """
        try:
            self.current_metrics = metrics
            
            # Update accuracy
            if 'accuracy' in metrics:
                acc_val = metrics['accuracy']
                self.metrics_labels['Accuracy'].config(
                    text=f'{acc_val:.1f}%',
                    fg='#4caf50' if acc_val > 80 else '#fdd835'
                )
            
            # Update latency
            if 'latency_ms' in metrics:
                lat_val = metrics['latency_ms']
                self.metrics_labels['Latency (ms)'].config(
                    text=f'{lat_val:.0f}ms',
                    fg='#4caf50' if lat_val < 100 else '#f44336'
                )
            
            # Update CPU
            if 'cpu_percent' in metrics:
                cpu_val = metrics['cpu_percent']
                self.metrics_labels['CPU (%)'].config(
                    text=f'{cpu_val:.0f}%',
                    fg='#4caf50' if cpu_val < 50 else '#f44336'
                )
            
            # Update state
            if 'current_state' in metrics:
                self.metrics_labels['State'].config(
                    text=str(metrics['current_state'])
                )
            
            return True
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            return False

    def add_timeline_event(self, timestamp: str, phase: str, status: str) -> bool:
        """
        Add event to timeline.

        Args:
            timestamp: Event timestamp string (HH:MM:SS.mmm)
            phase: Phase name
            status: Status description

        Returns:
            True if successful
        """
        try:
            event_text = f'[{timestamp}] {phase} -> {status}'
            self.timeline_listbox.insert(tk.END, event_text)
            self.timeline_listbox.see(tk.END)  # Auto-scroll to end
            return True
        except Exception as e:
            logger.error(f"Error adding timeline event: {e}")
            return False

    def register_hotkey_callback(self, key: str, callback: Callable) -> None:
        """
        Register callback for hotkey.

        Args:
            key: Hotkey name (e.g., 'space', 'p', 'r')
            callback: Callable to invoke
        """
        self.on_hotkey_callbacks[key] = callback

    def register_state_change_callback(self, callback: Callable) -> None:
        """Register callback for state changes."""
        self.on_state_change_callback = callback

    def bind_hotkeys(self) -> None:
        """Bind hotkeys to callbacks."""
        self.root.bind('<space>', lambda e: self._on_hotkey('space'))
        self.root.bind('<p>', lambda e: self._on_hotkey('p'))
        self.root.bind('<r>', lambda e: self._on_hotkey('r'))
        self.root.bind('<c>', lambda e: self._on_hotkey('c'))
        self.root.bind('<s>', lambda e: self._on_hotkey('s'))
        self.root.bind('<q>', lambda e: self._on_hotkey('q'))

    def _on_hotkey(self, key: str) -> None:
        """Handle hotkey press."""
        if key in self.on_hotkey_callbacks:
            callback = self.on_hotkey_callbacks[key]
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in hotkey callback for '{key}': {e}")

    def _on_window_close(self) -> None:
        """Handle window close event."""
        self.is_running = False
        self.root.destroy()

    def show(self) -> None:
        """Show and run the UI with integrated update loop."""
        self.is_running = True
        self.bind_hotkeys()
        self._schedule_update_loop()
        self.root.mainloop()

    def _schedule_update_loop(self) -> None:
        """
        Schedule update_loop() to run every 50ms from Tkinter mainloop.
        
        This integrates queue processing into the main UI thread, ensuring
        metrics_dashboard.process_queue() is called at 50ms interval (20 FPS UI update rate).
        """
        if self.is_running:
            try:
                self.update_loop()
            except Exception as e:
                logger.warning(f'Error in scheduled update_loop: {e}')
            
            # Schedule next update in 50ms
            self.root.after(self.refresh_interval_ms, self._schedule_update_loop)

    def hide(self) -> None:
        """Hide the UI."""
        self._on_window_close()

    def update(self) -> None:
        """Update UI (call from main thread periodically)."""
        try:
            # Process state updates with validation (Issue #4)
            while not self.state_queue.empty():
                try:
                    state = self.state_queue.get_nowait()
                    if isinstance(state, GameState):
                        self.render_game_state(state)
                    elif isinstance(state, dict) and 'state' in state:
                        self.render_game_state(state['state'])
                except Exception as e:
                    logger.warning(f'Error processing state item: {e}')
            
            # Process metrics updates with validation (Issue #4)
            while not self.metrics_queue.empty():
                try:
                    metrics = self.metrics_queue.get_nowait()
                    if isinstance(metrics, dict):
                        self.update_metrics_display(metrics)
                except Exception as e:
                    logger.warning(f'Error processing metrics item: {e}')
            
            # Process events with validation (Issue #4)
            while not self.event_queue.empty():
                try:
                    event = self.event_queue.get_nowait()
                    if isinstance(event, dict):
                        timestamp = event.get('timestamp', '')
                        phase = event.get('phase', '')
                        status = event.get('status', '')
                        self.add_timeline_event(timestamp, phase, status)
                except Exception as e:
                    logger.warning(f'Error processing event item: {e}')
            
            self.root.update()
        except tk.TclError:
            # Window closed
            self.is_running = False
        except Exception as e:
            logger.error(f"Error in UI update: {e}")

    # =========================================================================
    # UI Update Loop - Background Processing
    # =========================================================================

    # UI refresh rate: 50ms for 20 FPS UI updates
    refresh_interval_ms = 50

    def update_loop(self) -> None:
        """
        Main UI update loop for processing queue events.

        Called from background UI thread; processes all pending queue items
        without blocking main simulation.
        """
        self.process_metrics_queue()
        self.process_state_queue()
        self.process_event_queue()

    def process_metrics_queue(self) -> None:
        """
        Process all pending metrics updates from queue.

        Uses MetricsDashboard.process_queue() for non-blocking batch processing
        of all pending metrics with Queue.get_nowait() and graceful Queue.Empty handling.
        
        Called from update_loop every 50ms.
        """
        try:
            if hasattr(self, 'metrics_dashboard') and self.metrics_dashboard:
                # Use MetricsDashboard's thread-safe queue processing
                self.metrics_dashboard.process_queue(self.metrics_queue)
            else:
                # Fallback: direct queue processing (legacy mode)
                while not self.metrics_queue.empty():
                    metrics = self.metrics_queue.get_nowait()
                    self.update_metrics_display(metrics)
        except Exception as e:
            logger.warning(f'Error processing metrics queue: {e}')

    def process_state_queue(self) -> None:
        """
        Process all pending state changes from queue.

        Drains state queue and renders all state transitions.
        """
        try:
            while not self.state_queue.empty():
                state = self.state_queue.get_nowait()
                if isinstance(state, GameState):
                    self.render_game_state(state)
                elif isinstance(state, dict) and 'state' in state:
                    self.render_game_state(state['state'])
        except Exception as e:
            logger.warning(f'Error processing state queue: {e}')

    def process_event_queue(self) -> None:
        """
        Process all pending timeline events from queue.

        Drains event queue and adds all events to timeline display.
        """
        try:
            while not self.event_queue.empty():
                event = self.event_queue.get_nowait()
                if isinstance(event, dict):
                    timestamp = event.get('timestamp', '')
                    phase = event.get('phase', '')
                    status = event.get('status', '')
                    self.add_timeline_event(timestamp, phase, status)
        except Exception as e:
            logger.warning(f'Error processing event queue: {e}')

    def _preload_macro_images(self) -> None:
        """
        Pre-load all macro images from data/macro_testing/ directory.
        
        Task 5: Pre-load macro images to prevent garbage collection during rendering.
        Called during initialization to cache all state images.
        """
        try:
            from pathlib import Path
            from PIL import Image, ImageTk
            
            macro_dir = Path('data/macro_testing')
            if not macro_dir.exists():
                logger.debug('Macro testing directory not found')
                return
            
            # Load all PNG files
            for image_file in macro_dir.glob('*.png'):
                try:
                    pil_image = Image.open(image_file)
                    pil_image = pil_image.resize((600, 700), Image.Resampling.LANCZOS)
                    tk_image = ImageTk.PhotoImage(pil_image)
                    
                    # Cache in canvas_renderer
                    state_name = image_file.stem.lower()
                    self.canvas_renderer.macro_images[state_name] = tk_image
                    self.canvas_renderer.macro_image_paths[state_name] = str(image_file)
                    
                    logger.debug(f'Preloaded macro image: {image_file.name}')
                except Exception as e:
                    logger.warning(f'Failed to preload image {image_file.name}: {e}')
        except Exception as e:
            logger.warning(f'Error preloading macro images: {e}')

    def render_treasure_with_timer(self, elapsed_ms: int, total_ms: int = 60000, 
                                  perturbation_effects: Optional[Dict[str, Any]] = None) -> bool:
        """
        Render treasure state with timer overlay.
        
        Task 4: Integrate timer animation in canvas updates.
        
        Args:
            elapsed_ms: Milliseconds elapsed in treasure phase
            total_ms: Total treasure phase duration
            perturbation_effects: Optional timer perturbation effects
            
        Returns:
            True if rendered successfully
        """
        try:
            if perturbation_effects is None:
                perturbation_effects = {}
            
            # Render treasure state first
            self.canvas_renderer.render_state(GameState.TREASURE, 'treasure')
            
            # Then overlay timer
            self.canvas_renderer.render_timer_overlay(elapsed_ms, total_ms, perturbation_effects)
            self.root.update_idletasks()
            return True
        except Exception as e:
            logger.warning(f'Error rendering treasure with timer: {e}')
            return False


__all__ = ['InteractiveUI']
