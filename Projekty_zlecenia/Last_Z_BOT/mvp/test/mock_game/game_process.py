from abc import ABC, abstractmethod
from dataclasses import dataclass
from mvp.test.mock_game.screenshot_generator import ScreenshotGenerator


@dataclass
class WindowInfo:
    """Information about game window"""
    hwnd: int
    title: str
    x: int
    y: int
    width: int
    height: int


class IGameProcess(ABC):
    """Abstract game process interface - can be mock or real"""

    @abstractmethod
    def get_window_info(self) -> WindowInfo:
        """Get window information"""
        pass

    @abstractmethod
    def send_click(self, x: int, y: int, down: bool = True) -> bool:
        """Send click to game window"""
        pass

    @abstractmethod
    def capture_screenshot(self) -> bytes:
        """Capture screenshot as PNG bytes"""
        pass

    @abstractmethod
    def set_ui_state(self, key: str, value) -> None:
        """Set game state (timer, dialog open, etc)"""
        pass

    @abstractmethod
    def get_ui_state(self, key: str):
        """Get game state"""
        pass


class MockGameProcess(IGameProcess):
    """Mock game process that simulates game.exe without actual game"""

    def __init__(
        self, title: str = "LastZ Game", width: int = 1024, height: int = 768
    ):
        self.title = title
        self.width = width
        self.height = height
        self.hwnd = 12345  # Fake HWND
        self.x = 100
        self.y = 100
        self.screenshot_generator = ScreenshotGenerator(width=width, height=height)
        self.state = {
            "timer_seconds": 300,  # 5 min default
            "chat_open": False,
            "dialog_open": False,
            "clicks": [],  # Record all clicks
        }

    def get_window_info(self) -> WindowInfo:
        """Get window information"""
        return WindowInfo(
            hwnd=self.hwnd,
            title=self.title,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
        )

    def send_click(self, x: int, y: int, down: bool = True) -> bool:
        """Send click to game window, validate position is within window bounds"""
        # Validate click is within window
        if not (self.x <= x <= self.x + self.width):
            return False
        if not (self.y <= y <= self.y + self.height):
            return False

        self.state["clicks"].append({"x": x, "y": y, "down": down})
        return True

    def capture_screenshot(self) -> bytes:
        """Capture screenshot as PNG bytes"""
        timer_seconds = self.state.get("timer_seconds", 300)
        minutes = timer_seconds // 60
        seconds = timer_seconds % 60
        chat_open = self.state.get("chat_open", False)

        return self.screenshot_generator.generate_game_screenshot(
            timer_minutes=minutes,
            timer_seconds=seconds,
            chat_messages=["Sample message"] if chat_open else None,
        )

    def set_ui_state(self, key: str, value) -> None:
        """Set game state value"""
        self.state[key] = value

    def get_ui_state(self, key: str):
        """Get game state value"""
        return self.state.get(key)
