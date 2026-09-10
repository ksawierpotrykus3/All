"""Timer animator for countdown overlay with prediction accuracy metrics."""

from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Optional, Tuple
import math

class TimerAnimator:
    """
    Renders dynamic timer animation with color phases (green/yellow/red/blink).
    Supports all 6 game states and timer prediction accuracy metrics.
    """

    # Timer image dimensions
    TIMER_IMAGE_WIDTH = 200
    TIMER_IMAGE_HEIGHT = 100

    def __init__(self, total_ms: int = 60000):
        """
        Initialize TimerAnimator.
        
        Args:
            total_ms: Total timer duration in milliseconds (default 60000ms = 60s)
        """
        self.total_ms = total_ms
        self.start_time = None
        
        # Load font for timer text
        try:
            self.font_large = ImageFont.truetype("arial.ttf", 48)
            self.font_small = ImageFont.truetype("arial.ttf", 24)
        except (IOError, OSError):
            self.font_large = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def render_countdown(self, elapsed_ms: int) -> Image.Image:
        """
        Render timer countdown as PIL Image with MM:SS.mmm format.
        
        Args:
            elapsed_ms: Elapsed time in milliseconds
            
        Returns:
            PIL Image with timer text overlay (200x100 pixels)
        """
        # Clamp elapsed time to [0, total_ms]
        clamped_elapsed_ms = max(0, min(elapsed_ms, self.total_ms))
        remaining_ms = self.total_ms - clamped_elapsed_ms
        
        # Create image
        img = Image.new('RGB', (self.TIMER_IMAGE_WIDTH, self.TIMER_IMAGE_HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # Format: MM:SS.mmm
        minutes = remaining_ms // 60000
        seconds = (remaining_ms % 60000) // 1000
        milliseconds = remaining_ms % 1000
        timer_text = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
        # Get color based on remaining time
        color = self._get_rgb_color(self.get_timer_color(clamped_elapsed_ms))
        
        # Draw timer text centered
        text_bbox = draw.textbbox((0, 0), timer_text, font=self.font_large)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (self.TIMER_IMAGE_WIDTH - text_width) // 2
        text_y = (self.TIMER_IMAGE_HEIGHT - text_height) // 2
        
        draw.text((text_x, text_y), timer_text, font=self.font_large, fill=color)
        
        return img

    def get_timer_color(self, elapsed_ms: int) -> str:
        """
        Determine timer color based on elapsed time.
        
        Color phases:
        - Green: T-60 → T-30 (30000ms to 60000ms elapsed)
        - Yellow: T-30 → T-10 (10000ms to 30000ms elapsed)
        - Red: T-10 → T-0 (0ms to 10000ms elapsed)
        - Blink: T-0 (exactly at or past 60000ms)
        
        Args:
            elapsed_ms: Elapsed time in milliseconds
            
        Returns:
            Color name: 'green', 'yellow', 'red', or 'blink'
        """
        if elapsed_ms >= self.total_ms:
            return 'blink'
        
        remaining_ms = self.total_ms - elapsed_ms
        
        if remaining_ms > 30000:
            return 'green'
        elif remaining_ms > 10000:
            return 'yellow'
        else:
            return 'red'

    def _get_rgb_color(self, color_name: str) -> Tuple[int, int, int]:
        """Convert color name to RGB tuple."""
        color_map = {
            'green': (0, 255, 0),
            'yellow': (255, 255, 0),
            'red': (255, 0, 0),
            'blink': (255, 0, 0),  # Blinks between red and off
        }
        return color_map.get(color_name, (255, 255, 255))

    def calculate_prediction_accuracy(self, predicted_click_ms: int, actual_click_ms: int) -> float:
        """
        Calculate prediction accuracy percentage.
        
        Accuracy = (1 - |predicted - actual| / total_ms) * 100
        
        Args:
            predicted_click_ms: Predicted click time in ms
            actual_click_ms: Actual click time in ms
            
        Returns:
            Accuracy percentage (0-100)
        """
        error_ms = abs(predicted_click_ms - actual_click_ms)
        accuracy = (1.0 - min(error_ms / self.total_ms, 1.0)) * 100.0
        return max(0.0, accuracy)

    def get_timer_metrics(self, predicted_ms: int, actual_ms: int, click_hit: bool) -> Dict[str, any]:
        """
        Get complete timer metrics for this iteration.
        
        Args:
            predicted_ms: Predicted click time in milliseconds
            actual_ms: Actual click time in milliseconds
            click_hit: Whether the click was a hit
            
        Returns:
            Dictionary with timer metrics:
            - timer_accuracy_percent: Prediction accuracy (0-100)
            - timer_is_early_click: True if click before expiry
            - timer_is_late_click: True if click after expiry
            - timer_prediction_offset_ms: Predicted - Actual
        """
        accuracy = self.calculate_prediction_accuracy(predicted_ms, actual_ms)
        is_early = actual_ms < self.total_ms
        is_late = actual_ms > self.total_ms
        offset = predicted_ms - actual_ms
        
        return {
            'timer_accuracy_percent': accuracy,
            'timer_is_early_click': is_early,
            'timer_is_late_click': is_late,
            'timer_prediction_offset_ms': offset,
        }

    def overlay_timer_on_image(self, base_image: Image.Image, elapsed_ms: int, 
                               position: str = 'center') -> Image.Image:
        """
        Overlay timer countdown on base image (e.g., treasure state).
        
        Args:
            base_image: PIL Image to overlay timer on
            elapsed_ms: Elapsed time in milliseconds
            position: Timer position ('center', 'bottom_right', 'top_left', etc.)
            
        Returns:
            PIL Image with timer overlay
        """
        # Render timer image
        timer_img = self.render_countdown(elapsed_ms)
        
        # Create a copy of base image
        result = base_image.copy()
        
        # Calculate position
        base_width, base_height = result.size
        timer_width, timer_height = timer_img.size
        
        position_map = {
            'center': (
                (base_width - timer_width) // 2,
                (base_height - timer_height) // 2
            ),
            'bottom_right': (
                base_width - timer_width - 20,
                base_height - timer_height - 20
            ),
            'top_left': (20, 20),
            'top_right': (base_width - timer_width - 20, 20),
            'bottom_left': (20, base_height - timer_height - 20),
        }
        
        pos = position_map.get(position, position_map['center'])
        
        # Paste timer onto base image
        result.paste(timer_img, pos)
        
        return result

    def is_expired(self, elapsed_ms: int) -> bool:
        """
        Check if timer has expired.
        
        Args:
            elapsed_ms: Elapsed time in milliseconds
            
        Returns:
            True if elapsed_ms >= total_ms
        """
        return elapsed_ms >= self.total_ms
