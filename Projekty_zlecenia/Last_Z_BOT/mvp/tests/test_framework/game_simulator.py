"""Game state simulator for hybrid integration test framework."""

from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime
import threading
import time


@dataclass
class GameStateUpdate:
    """Represents a state update from a single tick."""

    frame_number: int
    timer_seconds_current: int
    chat_open: bool
    heli_alert_active: bool
    details_open: bool
    events_triggered: list[str] = field(default_factory=list)
    timestamp_ms: float = 0.0


@dataclass
class ClickResult:
    """Result of a click in the game."""

    element_clicked: str  # e.g., "timer", "chat_area", "treasure", "nothing"
    success: bool
    message: str
    coordinates: tuple[int, int] = (0, 0)


@dataclass
class ScreenRenderConfig:
    """Configuration for screen rendering."""

    template_path: object  # Path to template file
    window_size: tuple[int, int]  # (width, height)
    is_clipped: bool  # True if window size requires clipping
    dpi_scaling: float = 1.0  # DPI scaling factor


class GameStateSimulator:
    """Simulates game state for testing."""

    def __init__(self, scenario):
        """Initialize with a test scenario.
        
        Args:
            scenario: Scenario object with test configuration
        """
        self.scenario = scenario
        self.frame_number = 0
        self.chat_open = scenario.chat_state.value == "open"
        self.timer_seconds = scenario.timer_seconds
        self.scroll_position = 0
        self.heli_alert_active = False
        self.details_open = False
        self.events = []  # List of (delay_ms, event_type)
        self.click_count = 0
        self.treasure_found = False
        self.treasure_x = 0
        self.treasure_y = 0
        self._lock = threading.Lock()
        self._start_time_ms = time.time() * 1000

    def tick(self) -> GameStateUpdate:
        """Simulate one frame tick.
        
        Returns:
            GameStateUpdate with state changes
        """
        with self._lock:
            self.frame_number += 1
            current_time_ms = (time.time() * 1000) - self._start_time_ms
            
            # Decrement timer
            timer_before = self.timer_seconds
            self.timer_seconds = max(0, self.timer_seconds - 1)
            
            # Check for timer expiration
            events_triggered = []
            if self.timer_seconds == 0 and timer_before > 0:
                events_triggered.append("timer_expired")
            
            # Trigger heli alert when timer < 5s
            if self.timer_seconds < 5 and not self.heli_alert_active:
                self.heli_alert_active = True
                events_triggered.append("heli_alert_activated")
            
            # Check for injected events
            events_to_remove = []
            for i, (delay_ms, event_type) in enumerate(self.events):
                if current_time_ms >= delay_ms:
                    events_triggered.append(event_type)
                    events_to_remove.append(i)
            
            # Remove triggered events
            for i in reversed(events_to_remove):
                self.events.pop(i)
            
            # Handle frame glitches
            glitch_triggered = False
            if self.scenario.glitch_type.value == "frame_drop_at_5" and self.frame_number == 5:
                glitch_triggered = True
                events_triggered.append("frame_glitch")
            elif self.scenario.glitch_type.value == "frame_drop_at_50" and self.frame_number == 50:
                glitch_triggered = True
                events_triggered.append("frame_glitch")
            
            return GameStateUpdate(
                frame_number=self.frame_number,
                timer_seconds_current=self.timer_seconds,
                chat_open=self.chat_open,
                heli_alert_active=self.heli_alert_active,
                details_open=self.details_open,
                events_triggered=events_triggered,
                timestamp_ms=current_time_ms,
            )

    def process_click(self, px: int, py: int) -> ClickResult:
        """Determine what UI element was clicked.
        
        Args:
            px: X coordinate
            py: Y coordinate
            
        Returns:
            ClickResult with element clicked and outcome
        """
        with self._lock:
            self.click_count += 1
            
            # Define clickable regions (1024x768 baseline)
            # Timer area: roughly (900, 20) to (1000, 60)
            # Chat area: roughly (0, 600) to (200, 768)
            # Treasure area: random, varies per scenario
            
            # Check timer area
            if 900 <= px <= 1000 and 20 <= py <= 60:
                return ClickResult(
                    element_clicked="timer",
                    success=True,
                    message="Clicked timer area",
                    coordinates=(px, py),
                )
            
            # Check chat area
            if 0 <= px <= 200 and 600 <= py <= 768:
                return ClickResult(
                    element_clicked="chat_area",
                    success=True,
                    message="Clicked chat area",
                    coordinates=(px, py),
                )
            
            # Check treasure area (random for now)
            if 400 <= px <= 600 and 300 <= py <= 500:
                self.treasure_found = True
                self.treasure_x = px
                self.treasure_y = py
                return ClickResult(
                    element_clicked="treasure",
                    success=True,
                    message="Treasure found!",
                    coordinates=(px, py),
                )
            
            # No hit
            return ClickResult(
                element_clicked="nothing",
                success=False,
                message="Clicked empty area",
                coordinates=(px, py),
            )

    def inject_event(self, event_type: str, delay_ms: int) -> None:
        """Inject an event at a specified delay.
        
        Args:
            event_type: Type of event (e.g., "chat_open", "heli_alert")
            delay_ms: Delay before event triggers (in milliseconds)
        """
        with self._lock:
            current_time_ms = (time.time() * 1000) - self._start_time_ms
            trigger_time_ms = current_time_ms + delay_ms
            self.events.append((trigger_time_ms, event_type))

    def get_state_dict(self) -> dict:
        """Get current state as dictionary (for HTTP API).
        
        Returns:
            Dictionary with current game state
        """
        with self._lock:
            return {
                "timer_seconds": self.timer_seconds,
                "click_count": self.click_count,
                "treasure_count": 1 if self.treasure_found else 0,
                "chat_open": self.chat_open,
                "heli_alert_active": self.heli_alert_active,
                "frame_number": self.frame_number,
            }

    def reset(self) -> None:
        """Reset simulator to initial state."""
        with self._lock:
            self.frame_number = 0
            self.chat_open = self.scenario.chat_state.value == "open"
            self.timer_seconds = self.scenario.timer_seconds
            self.scroll_position = 0
            self.heli_alert_active = False
            self.details_open = False
            self.click_count = 0
            self.treasure_found = False
            self.treasure_x = 0
            self.treasure_y = 0
            self.events = []
            self._start_time_ms = time.time() * 1000


import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


class ScreenRenderer:
    """Renders synthetic game screens from PNG templates."""

    # Standard game screen size
    BASELINE_WIDTH = 1024
    BASELINE_HEIGHT = 768

    def __init__(self, test_data_dir: Path):
        """Initialize renderer with test data directory.
        
        Args:
            test_data_dir: Path to directory containing PNG templates
        """
        self.test_data_dir = Path(test_data_dir)
        self.templates = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load PNG templates from test_data_dir."""
        template_names = [
            "no_chat.png",
            "1_scan_chat_with_arrow.png",
            "1_scan_chat_without_arrow.png",
            "details.png",
            "1_heli_alert_appearing_in_chat.png",
            "helka_scrolled.png",
        ]
        
        for name in template_names:
            path = self.test_data_dir / name
            if path.exists():
                try:
                    img = Image.open(path).convert("RGB")
                    # Ensure it's 1024x768
                    if img.size != (self.BASELINE_WIDTH, self.BASELINE_HEIGHT):
                        img = img.resize((self.BASELINE_WIDTH, self.BASELINE_HEIGHT))
                    self.templates[name] = img
                except Exception as e:
                    # Template not available, will create placeholder
                    pass

    def render(self, state: GameStateSimulator, window_size: tuple[int, int]) -> np.ndarray:
        """Render current game state to screen frame.
        
        Args:
            state: Current GameStateSimulator state
            window_size: Target window size (width, height)
            
        Returns:
            RGB numpy array (1024x768, uint8 0-255)
        """
        # Select template based on game state
        template_key = self._select_template(state)
        
        # Get or create template
        if template_key in self.templates:
            frame = self.templates[template_key].copy()
        else:
            # Create placeholder if template not found
            frame = Image.new("RGB", (self.BASELINE_WIDTH, self.BASELINE_HEIGHT), color=(0, 0, 0))
        
        # Inject dynamic content (timer text)
        frame = self._inject_dynamic_content(frame, state)
        
        # Handle scrolling
        if state.scroll_position > 0:
            frame = self._apply_scroll(frame, state.scroll_position)
        
        # Convert to numpy array
        frame_array = np.array(frame, dtype=np.uint8)
        
        # Handle clipping: crop to window_size, then pad with black
        if window_size[0] < self.BASELINE_WIDTH or window_size[1] < self.BASELINE_HEIGHT:
            frame_array = self._apply_clipping(frame_array, window_size)
        
        return frame_array

    def _select_template(self, state: GameStateSimulator) -> str:
        """Select appropriate template based on game state.
        
        Args:
            state: Current GameStateSimulator state
            
        Returns:
            Template name (key for self.templates)
        """
        if state.heli_alert_active:
            return "1_heli_alert_appearing_in_chat.png"
        
        if state.details_open:
            return "details.png"
        
        if state.chat_open:
            if state.scroll_position > 0:
                return "helka_scrolled.png"
            else:
                # Assume chat with arrow for now
                return "1_scan_chat_with_arrow.png"
        
        return "no_chat.png"

    def _inject_dynamic_content(self, frame: Image.Image, state: GameStateSimulator) -> Image.Image:
        """Inject dynamic content (timer text, etc.) into frame.
        
        Args:
            frame: Current frame image
            state: Current GameStateSimulator state
            
        Returns:
            Updated frame with injected content
        """
        draw = ImageDraw.Draw(frame)
        
        # Inject timer text
        # Timer position: roughly (920, 30)
        timer_text = f"{state.timer_seconds}s"
        
        # Try to use a font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # Draw timer
        draw.text((920, 30), timer_text, fill=(255, 255, 255), font=font)
        
        return frame

    def _apply_scroll(self, frame: Image.Image, scroll_position: int) -> Image.Image:
        """Apply vertical scrolling to frame.
        
        Args:
            frame: Current frame
            scroll_position: Pixels to scroll down
            
        Returns:
            Scrolled frame (same size, content shifted)
        """
        frame_array = np.array(frame)
        
        # Crop frame from scroll_position downward
        if scroll_position < frame_array.shape[0]:
            scrolled = frame_array[scroll_position:, :, :]
            # Pad top with black
            padding = np.zeros((scroll_position, frame_array.shape[1], 3), dtype=np.uint8)
            frame_array = np.vstack([padding, scrolled])
        else:
            # Fully scrolled, return black frame
            frame_array = np.zeros_like(frame_array)
        
        return Image.fromarray(frame_array)

    def _apply_clipping(self, frame_array: np.ndarray, window_size: tuple[int, int]) -> np.ndarray:
        """Apply viewport clipping for smaller windows.
        
        Args:
            frame_array: Current frame array (1024x768)
            window_size: Target window size
            
        Returns:
            Frame array padded/clipped to 1024x768 with visible portion top-left
        """
        # Crop to window_size from top-left
        clipped_height = min(window_size[1], self.BASELINE_HEIGHT)
        clipped_width = min(window_size[0], self.BASELINE_WIDTH)
        
        clipped = frame_array[0:clipped_height, 0:clipped_width, :]
        
        # Pad with black to restore to 1024x768
        padded = np.zeros((self.BASELINE_HEIGHT, self.BASELINE_WIDTH, 3), dtype=np.uint8)
        padded[0:clipped_height, 0:clipped_width, :] = clipped
        
        return padded


import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Optional


class MockHTTPServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock game server."""

    game_state: Optional[GameStateSimulator] = None

    def do_GET(self) -> None:
        """Handle GET requests."""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == "/api/game/state":
                self._handle_game_state()
            elif path == "/api/treasure/check":
                self._handle_treasure_check()
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "Not found"}')
        except Exception:
            # Silently handle errors
            pass

    def _handle_game_state(self) -> None:
        """Handle GET /api/game/state."""
        if self.game_state is None:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "Game state not initialized"}')
            return
        
        state_dict = self.game_state.get_state_dict()
        state_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        response_json = json.dumps(state_dict)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json.encode())

    def _handle_treasure_check(self) -> None:
        """Handle GET /api/treasure/check."""
        if self.game_state is None:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "Game state not initialized"}')
            return
        
        if self.game_state.treasure_found:
            response = {
                "found": True,
                "x": self.game_state.treasure_x,
                "y": self.game_state.treasure_y,
                "message": "Treasure discovered!",
            }
        else:
            response = {
                "found": False,
                "message": "No treasure at current location",
            }
        
        response_json = json.dumps(response)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json.encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class MockHTTPServer(threading.Thread):
    """Mock HTTP server for game API."""

    def __init__(self, game_state: GameStateSimulator, port: int = 8888):
        """Initialize mock server.
        
        Args:
            game_state: GameStateSimulator instance
            port: Port to listen on (default 8888)
        """
        super().__init__(daemon=True)
        self.game_state = game_state
        self.port = port
        self.server = None
        self._running = False
        self._lock = threading.Lock()

    def run(self) -> None:
        """Start HTTP server (runs in background thread)."""
        try:
            # Set class-level reference for handler
            MockHTTPServerHandler.game_state = self.game_state
            
            self.server = HTTPServer(
                ("localhost", self.port), 
                MockHTTPServerHandler
            )
            self.server.timeout = 0.5  # Set timeout for handle_request
            
            with self._lock:
                self._running = True
            
            # Run server until stopped
            while True:
                with self._lock:
                    if not self._running:
                        break
                
                try:
                    self.server.handle_request()
                except Exception:
                    pass
        except Exception as e:
            print(f"MockHTTPServer error: {e}")
        finally:
            if self.server:
                try:
                    self.server.server_close()
                except Exception:
                    pass
            with self._lock:
                self._running = False

    def stop(self) -> None:
        """Stop the server."""
        with self._lock:
            self._running = False
        # Give thread time to stop
        time.sleep(0.2)

    def is_running(self) -> bool:
        """Check if server is running."""
        with self._lock:
            return self._running
