"""
Game simulator window with real-time timer and event handling.
Used for bot integration testing without requiring actual game.
"""

import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class GameSimulatorWindow:
    """
    Simulates game window for testing bot behavior.
    Renders base screen, timer overlay, and alert notifications.
    Thread-safe state management for concurrent bot testing.
    """

    DISPLAY_NAME = "Game Simulator - Press Q to quit, SPACE for alert, A to dismiss, +/- for timer"

    def __init__(self, data_dir: Path = Path("data/macro_testing")):
        """
        Initialize simulator with PNG assets.

        Args:
            data_dir: Path to directory containing macro test PNGs
        """
        self.data_dir = Path(data_dir)
        
        # Thread-safe state
        self._lock = threading.Lock()
        
        # Load base image first to get dynamic window dimensions (Task 3.1)
        base_filepath = self.data_dir / "no_chat.png"
        if not base_filepath.exists():
            raise FileNotFoundError(f"Missing base asset: {base_filepath}")
        
        base_img = cv2.imread(str(base_filepath))
        if base_img is None:
            raise ValueError(f"Failed to load base image: {base_filepath}")
        
        # Set dynamic window dimensions from base image (Task 3.1)
        self.window_height, self.window_width = base_img.shape[:2]
        
        # Load all images with crop logic
        self._load_images()

        self.timer_seconds = 0.0
        self.alert_active = False
        self.running = True

        # Display state - initialize after _load_images() to have window dimensions (Task 6)
        self.current_frame = np.zeros(
            (self.window_height, self.window_width, 3), dtype=np.uint8
        )
        self.start_time = time.time()
        self.frame_count = 0
        self.fps = 0.0

        # Input handling
        self._create_window()

    def _load_images(self) -> None:
        """
        Load all PNG images from data directory with aspect-ratio-preserving crop.
        
        Task 3.2: Crop logic (not resize) to maintain aspect ratio
        Task 3.3: Use cv2.INTER_AREA for downscaling interpolation
        """
        required_images = {
            "base": "no_chat.png",
            "alert": "1_heli_alert_appearing_in_chat.png",
            "scan_with_arrow": "1_scan_chat_with_arrow.png",
            "scan_without_arrow": "1_scan_chat_without_arrow.png",
            "details": "details.png",
            "helka_scrolled": "helka_scrolled.png",
        }

        self.images = {}
        for key, filename in required_images.items():
            filepath = self.data_dir / filename
            if not filepath.exists():
                raise FileNotFoundError(f"Missing asset: {filepath}")

            img = cv2.imread(str(filepath))
            if img is None:
                raise ValueError(f"Failed to load image: {filepath}")

            # Aspect-ratio-preserving crop (Task 3.2)
            img_cropped = self._crop_to_aspect_ratio(
                img, self.window_width, self.window_height
            )
            
            # If crop result differs from target size, resize with INTER_AREA (Task 3.3)
            if img_cropped.shape != (self.window_height, self.window_width, 3):
                img_cropped = cv2.resize(
                    img_cropped,
                    (self.window_width, self.window_height),
                    interpolation=cv2.INTER_AREA
                )
            
            self.images[key] = img_cropped

    def _crop_to_aspect_ratio(
        self, img: np.ndarray, target_width: int, target_height: int
    ) -> np.ndarray:
        """
        Crop image to match target aspect ratio while preserving content.
        
        Args:
            img: Input image (BGR numpy array)
            target_width: Target width in pixels
            target_height: Target height in pixels
            
        Returns:
            Cropped image centered at original aspect ratio
        """
        img_h, img_w = img.shape[:2]
        target_aspect = target_width / target_height
        img_aspect = img_w / img_h

        if img_aspect > target_aspect:
            # Image is wider than target: crop left and right
            new_width = int(img_h * target_aspect)
            left_crop = (img_w - new_width) // 2
            right_crop = left_crop + new_width
            cropped = img[:, left_crop:right_crop]
        else:
            # Image is taller than target: crop top and bottom
            new_height = int(img_w / target_aspect)
            top_crop = (img_h - new_height) // 2
            bottom_crop = top_crop + new_height
            cropped = img[top_crop:bottom_crop, :]

        return cropped

    def _create_window(self) -> None:
        """Create OpenCV window for display with dynamic dimensions (Task 5)."""
        # Skip window creation in headless mode (Task 7)
        try:
            cv2.namedWindow(self.DISPLAY_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.DISPLAY_NAME, self.window_width, self.window_height)
            cv2.setMouseCallback(self.DISPLAY_NAME, self._mouse_callback)
        except Exception:
            # Headless mode or display unavailable (Task 7)
            pass

    def _mouse_callback(self, event, x, y, flags, param) -> None:
        """Handle mouse events in window."""
        # Reserved for future interaction
        pass

    def get_current_frame(self) -> np.ndarray:
        """
        Get current rendered frame for bot capture.

        Returns:
            Current frame as BGR numpy array (1024x768x3)
        """
        with self._lock:
            return self.current_frame.copy()

    def set_timer(self, seconds: float) -> None:
        """Set timer to specified seconds."""
        with self._lock:
            self.timer_seconds = seconds

    def adjust_timer(self, delta: float) -> None:
        """Adjust timer by delta seconds."""
        with self._lock:
            self.timer_seconds = max(0, self.timer_seconds + delta)

    def trigger_alert(self) -> None:
        """Trigger helicopter alert notification."""
        with self._lock:
            self.alert_active = True

    def dismiss_alert(self) -> None:
        """Dismiss active alert."""
        with self._lock:
            self.alert_active = False

    def _render_frame(self) -> np.ndarray:
        """
        Render current frame with overlays.
        
        Task 4.1 + 4.2: Use dynamic window dimensions for alert and timer positioning

        Returns:
            Rendered frame with timer and alert overlays
        """
        with self._lock:
            # Start with base screen
            frame = self.images["base"].copy()

            # Render timer overlay (top-right corner, green text) - Task 4.2
            timer_text = f"{self.timer_seconds:.0f}s"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.5
            font_thickness = 2
            font_color = (0, 255, 0)  # Green in BGR

            text_size = cv2.getTextSize(timer_text, font, font_scale, font_thickness)[0]
            text_x = self.window_width - text_size[0] - 10
            text_y = 30

            cv2.putText(
                frame,
                timer_text,
                (text_x, text_y),
                font,
                font_scale,
                font_color,
                font_thickness,
            )

            # Render alert overlay if active - Task 4.1
            if self.alert_active:
                alert_img = self.images["alert"]
                # Center alert image on frame using dynamic dimensions
                alert_h, alert_w = alert_img.shape[:2]
                frame_h, frame_w = frame.shape[:2]

                x_offset = (frame_w - alert_w) // 2
                y_offset = (frame_h - alert_h) // 2

                # Blend alert with frame (alpha blending)
                x_start = max(0, x_offset)
                y_start = max(0, y_offset)
                x_end = min(frame_w, x_offset + alert_w)
                y_end = min(frame_h, y_offset + alert_h)

                # Adjust source coordinates if offset is negative
                src_x_start = max(0, -x_offset)
                src_y_start = max(0, -y_offset)
                src_x_end = src_x_start + (x_end - x_start)
                src_y_end = src_y_start + (y_end - y_start)

                if x_end > x_start and y_end > y_start:
                    alpha = 0.8  # Alert transparency (unchanged - Task 3.6)
                    frame[y_start:y_end, x_start:x_end] = cv2.addWeighted(
                        alert_img[src_y_start:src_y_end, src_x_start:src_x_end],
                        alpha,
                        frame[y_start:y_end, x_start:x_end],
                        1 - alpha,
                        0,
                    )

            return frame

    def _handle_input(self) -> bool:
        """
        Handle keyboard input.

        Returns:
            False if user quit, True to continue
        """
        try:
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == ord("Q"):
                return False
            elif key == ord(" "):  # SPACE
                self.trigger_alert()
            elif key == ord("a") or key == ord("A"):
                self.dismiss_alert()
            elif key == ord("+") or key == ord("="):
                self.adjust_timer(1.0)
            elif key == ord("-") or key == ord("_"):
                self.adjust_timer(-1.0)
        except Exception:
            # Display not available (headless mode)
            pass

        return True

    def run(self) -> None:
        """
        Main simulator loop (blocking).
        Renders frames and handles input until user quits.
        """
        fps_update_time = time.time()
        fps_frame_count = 0

        try:
            while self.running:
                # Render current frame
                frame = self._render_frame()

                # Update FPS calculation
                fps_frame_count += 1
                current_time = time.time()
                elapsed = current_time - fps_update_time

                if elapsed >= 1.0:
                    with self._lock:
                        self.fps = fps_frame_count / elapsed
                    fps_update_time = current_time
                    fps_frame_count = 0

                # Display frame
                with self._lock:
                    self.current_frame = frame.copy()
                    self.frame_count += 1

                cv2.imshow(self.DISPLAY_NAME, frame)

                # Handle input
                if not self._handle_input():
                    break

                time.sleep(0.016)  # ~60 FPS

        finally:
            cv2.destroyWindow(self.DISPLAY_NAME)

    def run_async(self) -> threading.Thread:
        """
        Start simulator in background thread.

        Returns:
            Thread object (running)
        """

        def run_with_timeout():
            """Run simulator with timeout to prevent hanging in tests."""
            max_runtime = 30.0  # Max 30 seconds per test
            start_time = time.time()

            while self.running and (time.time() - start_time) < max_runtime:
                frame = self._render_frame()
                with self._lock:
                    self.current_frame = frame.copy()
                    self.frame_count += 1

                try:
                    cv2.imshow(self.DISPLAY_NAME, frame)
                except Exception:
                    # Display not available
                    pass

                if not self._handle_input():
                    break

                time.sleep(0.016)  # ~60 FPS

            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

        thread = threading.Thread(target=run_with_timeout, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        """Stop simulator."""
        with self._lock:
            self.running = False

    def get_state(self) -> dict:
        """
        Get current simulator state (thread-safe).

        Returns:
            Dictionary with timer_seconds, alert_active, fps, frame_count
        """
        with self._lock:
            return {
                "timer_seconds": self.timer_seconds,
                "alert_active": self.alert_active,
                "fps": self.fps,
                "frame_count": self.frame_count,
            }
