"""
Canvas Renderer for game state visualization.
Renders the current game state (CHAT, ALERT, TREASURE, etc.) on Tkinter canvas.
"""
import tkinter as tk
from tkinter import PhotoImage
from typing import Tuple, Optional, Any, Dict
import uuid
import logging
from pathlib import Path
from PIL import Image
from mvp.simulator.core import GameState
from mvp.simulator.ui.timer_animator import TimerAnimator
from mvp.simulator.config import STATE_IMAGE_MAPPING

logger = logging.getLogger(__name__)


class CanvasRenderer:
    """Renders game state on Tkinter canvas with state-specific visualizations."""

    def __init__(self, canvas: tk.Canvas = None, width: int = 600, height: int = 700):
        """
        Initialize CanvasRenderer with macro image support.

        Args:
            canvas: Tkinter Canvas widget (optional for testing)
            width: Canvas width in pixels
            height: Canvas height in pixels
        """
        self.canvas = canvas
        self.width = width
        self.height = height
        self.canvas_id = str(uuid.uuid4())[:8]
        
        # For testing: if no canvas provided, create PIL image buffer
        self._use_pil_buffer = canvas is None
        self._pil_buffer = None
        
        # Configure canvas background (only if canvas exists)
        if self.canvas:
            self.canvas.config(bg='#1e1e1e', relief=tk.FLAT, bd=0)
        
        # Load macro images from STATE_IMAGE_MAPPING (will be attempted when rendering)
        self.macro_images = {}  # state -> PhotoImage cache
        self.macro_image_paths = {}  # state -> file path
        
        # Timer animator
        self.timer_animator = TimerAnimator(total_ms=60000)
        self.timer_photo_image = None  # Current timer frame as PhotoImage
        self.last_canvas_image_id = None  # Last drawn image ID for cleanup

    def render_state(self, state: GameState = None, state_name: Optional[str] = None, 
                    animation_frame: int = 0, state_image_path: Optional[str] = None) -> Image.Image:
        """
        Render game state on canvas. Supports all 8 game states with macro images or symbolic rendering.
        Returns PIL Image for testing or renders on Tkinter canvas.

        Supported states:
        - CHAT: text display, chat state symbolic rendering
        - CHAT_FOCUS: arrow pulse animation, focused state
        - ALERT_ANIMATION: alert visual, helicopter appearing
        - TREASURE: treasure box visual, timer overlay ready
        - REWARD_DETAILS: reward details fade-in
        - SCANNING: scanning loop animation
        - CHAT_UNAVAILABLE: pulsing border, unavailable state
        - CHAT_RECOVERY: chat recovery state
        
        Args:
            state: GameState enum value (optional for testing)
            state_name: Optional state name for image lookup (e.g., 'treasure')
            animation_frame: Optional animation frame time (ms)
            state_image_path: Optional custom path to state image
            
        Returns:
            PIL Image if no canvas (testing), True if rendered on canvas
        """
        try:
            if self._use_pil_buffer:
                # Testing mode: return PIL Image
                if state_image_path:
                    # Try custom path first
                    try:
                        img = Image.open(state_image_path)
                        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
                        return img
                    except Exception:
                        pass
                return self._render_state_pil(state_name or 'chat', animation_frame)
            
            # Canvas mode: render on Tkinter canvas
            self.canvas.delete('all')  # Clear canvas
            
            if state_name is None:
                state_name = state.name.lower() if state else 'chat'
            
            # Try to load macro image for this state
            if state_name in STATE_IMAGE_MAPPING:
                if self._load_and_render_image(state_name):
                    return True
            
            # Fallback to symbolic rendering based on state
            self._render_symbolic(state_name)
            return True
        except Exception as e:
            logger.warning(f'Error rendering state {state_name}: {e}')
            if not self._use_pil_buffer:
                self._render_symbolic('error')
            return False

    def _render_state_pil(self, state_name: str, animation_frame: int = 0) -> Image.Image:
        """
        Render state as PIL Image (for testing).
        
        Args:
            state_name: State name
            animation_frame: Animation frame time
            
        Returns:
            PIL Image
        """
        # Create base image
        img = Image.new('RGB', (self.width, self.height), color='#1e1e1e')
        
        # Try to load macro image
        image_filename = STATE_IMAGE_MAPPING.get(state_name)
        if image_filename:
            possible_paths = [
                Path('data/macro_testing') / image_filename,
                Path('mvp/simulator/assets') / image_filename,
                Path('.') / image_filename,
            ]
            
            for path in possible_paths:
                if path.exists():
                    try:
                        img = Image.open(path)
                        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
                        return img
                    except Exception:
                        break
        
        # Fallback to symbolic rendering (on PIL image)
        return self._render_symbolic_pil(state_name, img)

    def _load_and_render_image(self, state_name: str) -> bool:
        """
        Load macro image from macro_testing/ and render on canvas.
        
        Args:
            state_name: State name (e.g., 'treasure')
            
        Returns:
            True if image loaded and rendered successfully
        """
        try:
            image_filename = STATE_IMAGE_MAPPING.get(state_name)
            if not image_filename:
                return False
            
            # Look for image in multiple locations
            possible_paths = [
                Path('data/macro_testing') / image_filename,
                Path('mvp/simulator/assets') / image_filename,
                Path('.') / image_filename,
            ]
            
            image_path = None
            for path in possible_paths:
                if path.exists():
                    image_path = path
                    break
            
            if not image_path:
                logger.debug(f'Image not found: {image_filename}')
                return False
            
            # Load image with PIL
            pil_image = Image.open(image_path)
            pil_image = pil_image.resize((self.width, self.height), Image.Resampling.LANCZOS)
            
            # Convert PIL image to PhotoImage
            if state_name not in self.macro_images:
                self.macro_images[state_name] = ImageTk.PhotoImage(pil_image)
            
            # Render on canvas
            self.last_canvas_image_id = self.canvas.create_image(
                0, 0, anchor=tk.NW, image=self.macro_images[state_name]
            )
            return True
        except Exception as e:
            logger.debug(f'Error loading image {state_name}: {e}')
            return False

    def render_timer_overlay(self, state: str = None, timer_animator: TimerAnimator = None,
                           elapsed_ms: int = None, total_ms: int = 60000,
                           position: str = 'center', effects: Optional[Dict[str, Any]] = None) -> Image.Image:
        """
        Render timer overlay on state image.
        Supports both old signature (elapsed_ms, total_ms, effects) and new signature (state, timer_animator, elapsed_ms, position).
        
        Args:
            state: State name (default 'treasure') — NEW signature
            timer_animator: TimerAnimator instance — NEW signature
            elapsed_ms: Elapsed time in milliseconds
            total_ms: Total phase duration (old signature)
            position: Timer position ('center', 'bottom_right', 'top_left', etc.) — NEW signature
            effects: Optional perturbation effects dict (old signature)
            
        Returns:
            PIL Image with timer overlay (for testing) or True (for canvas)
        """
        # Detect which signature is being used:
        # OLD signature: render_timer_overlay(elapsed_ms=X, [total_ms=Y], [effects=Z])
        # NEW signature: render_timer_overlay(state=X, [timer_animator=Y], [elapsed_ms=Z], [position=W])
        
        is_old_signature = (
            (state is None and elapsed_ms is not None) or  # positional: elapsed_ms
            (effects is not None) or  # effects parameter is old
            (total_ms != 60000)  # custom total_ms is old
        )
        
        if is_old_signature:
            # OLD signature path: render_timer_overlay(elapsed_ms=30000, total_ms=60000, effects={...})
            if self.canvas:
                try:
                    if effects is None:
                        effects = {}
                    
                    # Check if timer should be rendered
                    if not effects.get('render_visible', True):
                        return True  # Skip rendering but don't fail
                    
                    # Generate timer image
                    if timer_animator is None:
                        timer_animator = self.timer_animator
                    timer_image = timer_animator.render_countdown(elapsed_ms or 0, total_ms)
                    
                    # Convert to PhotoImage
                    try:
                        from PIL import ImageTk
                        self.timer_photo_image = ImageTk.PhotoImage(timer_image)
                    except (ImportError, AttributeError):
                        pass
                    
                    # Draw on canvas
                    if self.canvas:
                        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.timer_photo_image)
                    return True
                except Exception as e:
                    logger.warning(f'Error rendering timer overlay: {e}')
                    return False
            else:
                # Testing mode: return PIL Image
                if timer_animator is None:
                    timer_animator = self.timer_animator
                return timer_animator.render_countdown(elapsed_ms or 0, total_ms)
        
        # NEW signature path: render_timer_overlay(state='treasure', timer_animator=X, elapsed_ms=Y, position=Z)
        if timer_animator is None:
            timer_animator = self.timer_animator
        
        if self._use_pil_buffer:
            # Testing mode: render and return PIL Image
            base_img = self._render_state_pil(state or 'treasure', 0)
            return timer_animator.overlay_timer_on_image(base_img, elapsed_ms or 0, position)
        
        # Canvas mode: render on Tkinter canvas (existing implementation)
        return self.render_treasure_with_timer(elapsed_ms or 0, effects={'render_visible': True})

    def render_treasure_with_timer(self, elapsed_ms: int, total_ms: int = 60000,
                                  effects: Optional[Dict[str, Any]] = None) -> bool:
        """
        Render TREASURE state with timer overlay, perturbation effects, and visual feedback.
        
        Combines treasure box image with timer countdown, showing:
        - Timer color progression: green (0-25%) -> yellow (25-75%) -> red (75%+) -> blink (expired)
        - Perturbation effects: chaotic timer jumps, frozen timer, accelerated timer, hidden timer, distracted chat
        - Elapsed time and timer progress
        
        Args:
            elapsed_ms: Milliseconds elapsed since treasure appeared
            total_ms: Total treasure timer duration (default 60s)
            effects: Optional dict with perturbation effects:
                - render_visible (bool): Show timer overlay (default True)
                - chaotic_timer (bool): Random ±5-20s jumps (default False)
                - frozen_timer (bool): Stop timer for N seconds (default False)
                - accelerated_timer (int): Speed multiplier 2x or 4x (default 1x)
                - hidden_timer (bool): Render invisible (default False)
                - distracted_chat (bool): Show chat during timer (default False)
            
        Returns:
            True if rendered successfully
        """
        try:
            if effects is None:
                effects = {}
            
            # First, render the base treasure image (or fallback symbolic)
            if not self._load_and_render_image('treasure'):
                self._render_symbolic('treasure')
            
            # Apply perturbation effects to elapsed time if chaotic or accelerated
            effective_elapsed_ms = elapsed_ms
            
            if effects.get('chaotic_timer', False):
                # Add random perturbation ±5-20 seconds
                import random
                perturbation_ms = random.randint(-20000, 20000)
                effective_elapsed_ms = max(0, elapsed_ms + perturbation_ms)
            
            if effects.get('accelerated_timer'):
                # Speed up timer by multiplier (2x or 4x)
                multiplier = effects['accelerated_timer']
                effective_elapsed_ms = int(elapsed_ms * multiplier)
            
            if effects.get('frozen_timer', False):
                # Freeze timer at current position
                effective_elapsed_ms = elapsed_ms
            
            # Calculate remaining time for color and display
            remaining_ms = max(0, total_ms - effective_elapsed_ms)
            remaining_sec = remaining_ms / 1000.0
            
            # Determine timer color based on remaining time
            if remaining_sec > total_ms * 0.75 / 1000:  # 0-25% elapsed -> green
                timer_color = '#00ff00'
            elif remaining_sec > total_ms * 0.25 / 1000:  # 25-75% elapsed -> yellow
                timer_color = '#ffff00'
            elif remaining_sec > 0:  # 75%+ elapsed -> red
                timer_color = '#ff0000'
            else:  # Expired -> blink
                blink_cycle = (elapsed_ms % 1000) < 500
                timer_color = '#ff0000' if blink_cycle else '#000000'
            
            # Skip if hidden timer
            if effects.get('hidden_timer', False):
                return True
            
            # Draw timer overlay on treasure image
            timer_text = f"{int(remaining_sec // 60)}:{int(remaining_sec % 60):02d}"
            
            # Draw timer background box for visibility
            timer_box_x1 = self.width // 2 - 80
            timer_box_y1 = 50
            timer_box_x2 = self.width // 2 + 80
            timer_box_y2 = 120
            
            self.canvas.create_rectangle(
                timer_box_x1, timer_box_y1, timer_box_x2, timer_box_y2,
                fill='#1a1a1a', outline=timer_color, width=3
            )
            
            # Draw timer text
            self.canvas.create_text(
                self.width // 2, timer_box_y1 + 35,
                text=timer_text,
                fill=timer_color,
                font=('Courier', 32, 'bold')
            )
            
            # Draw timer label
            self.canvas.create_text(
                self.width // 2, timer_box_y2 + 15,
                text=f'Elapsed: {int(elapsed_ms // 1000)}s / {int(total_ms // 1000)}s',
                fill=timer_color,
                font=('Courier', 12)
            )
            
            # If distracted_chat effect, draw chat overlay
            if effects.get('distracted_chat', False):
                self.canvas.create_rectangle(
                    10, self.height - 150, self.width - 10, self.height - 10,
                    fill='#2a2a2a', outline='#00ff00', width=2
                )
                self.canvas.create_text(
                    self.width // 2, self.height - 80,
                    text='⚠ CHAT MESSAGE DISTRACTION',
                    fill='#00ff00',
                    font=('Courier', 12, 'bold')
                )
            
            return True
        except Exception as e:
            logger.warning(f'Error rendering treasure with timer: {e}')
            return False

    def _render_symbolic(self, state_name: str) -> None:
        """
        Render symbolic representation of state (fallback when image unavailable).
        Each state has unique color, symbol, and visualization.
        
        State-specific colors:
        - CHAT: #00ff00 (green) — normal chat state
        - CHAT_FOCUS: #00ff88 (bright green) — focused/arrow state
        - ALERT_ANIMATION: #ff0000 (red) — alert appearing
        - TREASURE: #ffaa00 (orange) — treasure box
        - REWARD_DETAILS: #ffff00 (yellow) — reward screen
        - SCANNING: #00aaff (cyan) — scanning loop
        - CHAT_UNAVAILABLE: #ff5555 (dark red) — unavailable state
        - CHAT_RECOVERY: #88ff00 (lime) — recovering chat state
        
        Args:
            state_name: State name for styling (converted to lowercase)
        """
        state_name = state_name.lower()
        
        # State-specific colors and symbols
        state_styles = {
            'chat': {
                'bg_fill': '#1a3a1a',
                'text_color': '#00ff00',
                'symbol': '💬 [CHAT]',
                'border_color': '#00ff00',
            },
            'chat_focus': {
                'bg_fill': '#1a3a2a',
                'text_color': '#00ff88',
                'symbol': '➜ [FOCUSED]',
                'border_color': '#00ff88',
            },
            'alert_animation': {
                'bg_fill': '#3a1a1a',
                'text_color': '#ff0000',
                'symbol': '⚠ [ALERT]',
                'border_color': '#ff0000',
            },
            'treasure': {
                'bg_fill': '#3a2a1a',
                'text_color': '#ffaa00',
                'symbol': '📦 [TREASURE]',
                'border_color': '#ffaa00',
            },
            'reward_details': {
                'bg_fill': '#3a3a1a',
                'text_color': '#ffff00',
                'symbol': '🎁 [REWARD]',
                'border_color': '#ffff00',
            },
            'scanning': {
                'bg_fill': '#1a2a3a',
                'text_color': '#00aaff',
                'symbol': '🔍 [SCANNING]',
                'border_color': '#00aaff',
            },
            'chat_unavailable': {
                'bg_fill': '#3a1a1a',
                'text_color': '#ff5555',
                'symbol': '✗ [UNAVAILABLE]',
                'border_color': '#ff5555',
            },
            'chat_recovery': {
                'bg_fill': '#2a3a1a',
                'text_color': '#88ff00',
                'symbol': '🔄 [RECOVERING]',
                'border_color': '#88ff00',
            },
            'error': {
                'bg_fill': '#2a1a1a',
                'text_color': '#ff0000',
                'symbol': '❌ [ERROR]',
                'border_color': '#ff0000',
            },
        }
        
        # Get style, fallback to chat if unknown
        style = state_styles.get(state_name, state_styles['chat'])
        
        # Draw background rectangle
        self.canvas.create_rectangle(
            0, 0, self.width, self.height,
            fill=style['bg_fill'],
            outline=style['border_color'],
            width=3
        )
        
        # Draw state symbol/text in center
        self.canvas.create_text(
            self.width // 2,
            self.height // 2,
            text=style['symbol'],
            fill=style['text_color'],
            font=('Courier', 24, 'bold')
        )
        
        # Draw state name below symbol
        self.canvas.create_text(
            self.width // 2,
            self.height // 2 + 50,
            text=f'State: {state_name.replace("_", " ").upper()}',
            fill=style['text_color'],
            font=('Courier', 14)
        )

    def clear(self) -> None:
        """Clear canvas."""
        self.canvas.delete('all')

    def render_state_with_animation(self, state_name: str, animation_frame: int = 0) -> bool:
        """
        Render state with animation frame support.
        
        Args:
            state_name: State name
            animation_frame: Animation frame time in milliseconds
            
        Returns:
            True if rendered successfully
        """
        try:
            self.canvas.delete('all')
            
            # First render base state
            if not self._load_and_render_image(state_name):
                self._render_symbolic(state_name)
            
            # Apply animation effects based on state
            if state_name == 'chat_focus':
                # Arrow pulse animation: scale 1.0 -> 1.2 -> 1.0 over 500ms
                cycle = animation_frame % 500
                scale = 1.0 + (0.2 * (1.0 - abs(cycle - 250) / 250.0))
                self._apply_animation_scale(scale)
            
            elif state_name == 'alert_animation':
                # Fade-in + drop effect over 300ms
                if animation_frame < 300:
                    progress = animation_frame / 300.0
                    alpha = int(255 * progress)  # Fade in
                    drop_offset = int(50 * progress)  # Drop from top
                    self._apply_animation_fade_and_drop(alpha, drop_offset)
            
            elif state_name == 'reward_details':
                # Fade-in over 200ms
                if animation_frame < 200:
                    progress = animation_frame / 200.0
                    alpha = int(255 * progress)
                    self._apply_animation_fade(alpha)
            
            elif state_name == 'chat_unavailable':
                # Red border pulse over 600ms
                cycle = animation_frame % 600
                pulse_width = 1 + int(4 * (1.0 - abs(cycle - 300) / 300.0))
                self._apply_animation_pulse_border(pulse_width, '#ff5555')
            
            return True
        except Exception as e:
            logger.warning(f'Error rendering state with animation: {e}')
            return False

    def render_state_transition(self, from_state: str, to_state: str, progress: float) -> Image.Image:
        """
        Render smooth transition between two states.
        
        Args:
            from_state: Starting state name
            to_state: Ending state name
            progress: Transition progress (0.0 to 1.0)
            
        Returns:
            PIL Image with transition
        """
        try:
            if self._use_pil_buffer:
                # Testing mode: blend two states
                from_img = self._render_state_pil(from_state, 0)
                to_img = self._render_state_pil(to_state, 0)
                
                # Blend images
                from PIL import Image as PILImage
                blended = PILImage.blend(from_img.convert('RGBA'), to_img.convert('RGBA'), progress)
                return blended.convert('RGB')
            
            # Canvas mode: render on Tkinter canvas
            if self.canvas:
                self.canvas.delete('all')
                
                # Render starting state faded out
                if self._load_and_render_image(from_state):
                    pass
                else:
                    self._render_symbolic(from_state)
                
                # Render ending state faded in
                if self._load_and_render_image(to_state):
                    pass
                else:
                    self._render_symbolic(to_state)
            
            return True
        except Exception as e:
            logger.warning(f'Error rendering state transition: {e}')
            return False

    def _apply_animation_scale(self, scale: float) -> None:
        """Apply scale transformation to current canvas (placeholder)."""
        pass

    def _apply_animation_fade_and_drop(self, alpha: int, drop_offset: int) -> None:
        """Apply fade and drop animation effects (placeholder)."""
        pass

    def _apply_animation_fade(self, alpha: int) -> None:
        """Apply fade animation (placeholder)."""
        pass

    def _apply_animation_pulse_border(self, width: int, color: str) -> None:
        """Apply pulsing border animation (placeholder)."""
        pass

    def clear(self) -> None:
        """Clear canvas."""
        if self.canvas:
            self.canvas.delete('all')

    def clear_all(self) -> None:
        """Alias for clear() — clear all canvas items."""
        self.clear()

    def draw_text(self, x: int, y: int, text: str, fill: str = '#fff', font: str = 'Courier 12') -> None:
        """
        Draw text on canvas.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to draw
            fill: Color
            font: Font specification
        """
        if self.canvas:
            self.canvas.create_text(x, y, text=text, fill=fill, font=font)

    def get_center(self) -> Tuple[int, int]:
        """
        Get center coordinates of canvas.
        
        Returns:
            Tuple of (center_x, center_y)
        """
        return (self.width // 2, self.height // 2)

    def _render_symbolic_pil(self, state_name: str, base_image: Image.Image) -> Image.Image:
        """Render symbolic state on PIL Image (for testing)."""
        from PIL import ImageDraw
        
        state_name = state_name.lower()
        
        # State-specific colors and symbols
        state_styles = {
            'chat': {'text_color': '#00ff00', 'symbol': '💬 [CHAT]', 'border_color': '#00ff00'},
            'chat_focus': {'text_color': '#00ff88', 'symbol': '➜ [FOCUSED]', 'border_color': '#00ff88'},
            'alert_animation': {'text_color': '#ff0000', 'symbol': '⚠ [ALERT]', 'border_color': '#ff0000'},
            'treasure': {'text_color': '#ffaa00', 'symbol': '📦 [TREASURE]', 'border_color': '#ffaa00'},
            'reward_details': {'text_color': '#ffff00', 'symbol': '🎁 [REWARD]', 'border_color': '#ffff00'},
            'scanning': {'text_color': '#00aaff', 'symbol': '🔍 [SCANNING]', 'border_color': '#00aaff'},
            'chat_unavailable': {'text_color': '#ff5555', 'symbol': '✗ [UNAVAILABLE]', 'border_color': '#ff5555'},
            'chat_recovery': {'text_color': '#88ff00', 'symbol': '🔄 [RECOVERING]', 'border_color': '#88ff00'},
        }
        
        style = state_styles.get(state_name, state_styles['chat'])
        
        draw = ImageDraw.Draw(base_image)
        
        # Draw border
        border_color = style['border_color']
        draw.rectangle([0, 0, self.width-1, self.height-1], outline=border_color, width=3)
        
        return base_image


# Import ImageTk for PIL-to-Tkinter conversion
try:
    from PIL import ImageTk
except ImportError:
    logger.warning('PIL ImageTk not available - macro images will not be rendered')
    ImageTk = None


__all__ = ['CanvasRenderer']
