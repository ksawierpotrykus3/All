"""Mock game environment package for testing"""

from mvp.test.mock_game.game_process import (
    IGameProcess,
    MockGameProcess,
    WindowInfo,
)
from mvp.test.mock_game.game_state import GameState, UIState, ClickRecord
from mvp.test.mock_game.macro_engine import MacroEngine, Macro
from mvp.test.mock_game.network_mock import (
    NetworkMock,
    APIResponse,
    ErrorInjection,
    APIClient,
    ResponseStatus,
)

__all__ = [
    "IGameProcess",
    "MockGameProcess",
    "WindowInfo",
    "GameState",
    "UIState",
    "ClickRecord",
    "MacroEngine",
    "Macro",
    "NetworkMock",
    "APIResponse",
    "ErrorInjection",
    "APIClient",
    "ResponseStatus",
]
