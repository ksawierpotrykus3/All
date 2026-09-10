from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class UIState:
    """UI state of the game"""
    timer_seconds: int = 300
    chat_open: bool = False
    dialog_open: bool = False
    macro_recording: bool = False


@dataclass
class ClickRecord:
    """Record of a single click event"""
    x: int
    y: int
    timestamp: datetime
    button: str = "left"


@dataclass
class GameState:
    """Central game state management"""
    ui: UIState = field(default_factory=UIState)
    clicks: List[ClickRecord] = field(default_factory=list)
    macros: Dict[str, List[ClickRecord]] = field(default_factory=dict)
    network_responses: Dict[str, Any] = field(default_factory=dict)

    def record_click(self, x: int, y: int) -> None:
        """Record a click event in game state"""
        self.clicks.append(
            ClickRecord(
                x=x,
                y=y,
                timestamp=datetime.now()
            )
        )

    def record_macro(self, name: str, clicks: List[ClickRecord]) -> None:
        """Record a macro with given name and click sequence"""
        self.macros[name] = clicks

    def get_macro(self, name: str) -> List[ClickRecord]:
        """Get a recorded macro by name"""
        return self.macros.get(name, [])
