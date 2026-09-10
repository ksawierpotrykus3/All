# Mock Game Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\- [ ]\) syntax for tracking.

**Goal:** Implement hybrid mock game environment supporting automated testing of clicking, macros, OCR, and network features (26+ new tests, 100% automated).

**Architecture:** 5-layer abstraction (game process, state, click/macro, OCR, network) with Python MockGameProcess for fast testing + optional mock_game.exe for deep WinAPI validation. All components use common interfaces for easy switching between mock and real.

**Tech Stack:** Python 3.11, pytest, WinAPI ctypes, pillow (image gen), numpy (image data), pytest fixtures

---

## File Structure

\\\
mvp/test/
├── mock_game/                          # NEW: Mock game environment
│   ├── __init__.py
│   ├── game_process.py                 # IGameProcess, MockGameProcess (HWND, click, screenshot)
│   ├── game_state.py                   # GameState (timer, UI, macros, network state)
│   ├── click_handler.py                # ClickHandler (WM_LBUTTONDOWN, position validate)
│   ├── screenshot_generator.py         # Generate test images (timer, chat UI)
│   ├── macro_engine.py                 # Macro recording/playback with timing
│   ├── network_mock.py                 # Fake API responses, error injection
│   └── conftest.py                     # pytest fixtures (mock_game_process, etc)
│
└── test_with_mock_game/                # NEW: Feature tests with mock game
    ├── test_clicking.py                # 6 click tests
    ├── test_macros.py                  # 5 macro tests
    ├── test_ocr_with_game.py           # 6 OCR tests
    ├── test_network_mock.py            # 4 network tests
    └── test_integration_mock.py        # 5 integration tests
\\\

---

## Task Breakdown (6 phases)

### Task 1: Game Process Abstraction & State Management

**Files:**
- Create: \mvp/test/mock_game/game_process.py\
- Create: \mvp/test/mock_game/game_state.py\
- Create: \mvp/test/mock_game/__init__.py\

**Description:** Foundation layer - define IGameProcess interface and MockGameProcess class that emulates game window and state.

- [ ] **Step 1: Write failing test for IGameProcess**

\\\python
# mvp/test/mock_game/conftest.py (create first)
import pytest
from mvp.test.mock_game.game_process import MockGameProcess

def test_mock_game_process_creates_window():
    game = MockGameProcess(title="LastZ Game", width=800, height=600)
    assert game.hwnd is not None
    assert game.hwnd > 0
    assert game.title == "LastZ Game"
    assert game.width == 800
    assert game.height == 600
\\\

- [ ] **Step 2: Run test to verify failure**

\\\ash
cd f:\\PROJEKTY\\joaxx
uv run pytest mvp/test/mock_game/conftest.py::test_mock_game_process_creates_window -v
\\\

Expected: FAIL - "MockGameProcess not defined"

- [ ] **Step 3: Create game_process.py with IGameProcess interface**

\\\python
# mvp/test/mock_game/game_process.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class WindowInfo:
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
    
    def __init__(self, title: str = "LastZ Game", width: int = 1024, height: int = 768):
        self.title = title
        self.width = width
        self.height = height
        self.hwnd = 12345  # Fake HWND
        self.x = 100
        self.y = 100
        self.state = {
            'timer_seconds': 300,  # 5 min default
            'chat_open': False,
            'dialog_open': False,
            'clicks': [],  # Record all clicks
        }
    
    def get_window_info(self) -> WindowInfo:
        return WindowInfo(
            hwnd=self.hwnd,
            title=self.title,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
        )
    
    def send_click(self, x: int, y: int, down: bool = True) -> bool:
        # Validate click is within window
        if not (self.x <= x <= self.x + self.width):
            return False
        if not (self.y <= y <= self.y + self.height):
            return False
        
        self.state['clicks'].append({'x': x, 'y': y, 'down': down})
        return True
    
    def capture_screenshot(self) -> bytes:
        # TODO: Generate mock image (will implement in Task 3)
        return b''
    
    def set_ui_state(self, key: str, value) -> None:
        self.state[key] = value
    
    def get_ui_state(self, key: str):
        return self.state.get(key)
\\\

- [ ] **Step 4: Run test to verify it passes**

\\\ash
uv run pytest mvp/test/mock_game/conftest.py::test_mock_game_process_creates_window -v
\\\

Expected: PASS

- [ ] **Step 5: Create game_state.py for comprehensive state management**

\\\python
# mvp/test/mock_game/game_state.py
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime

@dataclass
class UIState:
    timer_seconds: int = 300
    chat_open: bool = False
    dialog_open: bool = False
    macro_recording: bool = False

@dataclass
class ClickRecord:
    x: int
    y: int
    timestamp: datetime
    button: str = 'left'

@dataclass
class GameState:
    \"\"\"Central game state management\"\"\"
    ui: UIState = field(default_factory=UIState)
    clicks: List[ClickRecord] = field(default_factory=list)
    macros: Dict[str, List[ClickRecord]] = field(default_factory=dict)
    network_responses: Dict[str, Any] = field(default_factory=dict)
    
    def record_click(self, x: int, y: int) -> None:
        self.clicks.append(ClickRecord(
            x=x, y=y, 
            timestamp=datetime.now()
        ))
    
    def record_macro(self, name: str, clicks: List[ClickRecord]) -> None:
        self.macros[name] = clicks
    
    def get_macro(self, name: str) -> List[ClickRecord]:
        return self.macros.get(name, [])
\\\

- [ ] **Step 6: Create __init__.py exports**

\\\python
# mvp/test/mock_game/__init__.py
from mvp.test.mock_game.game_process import IGameProcess, MockGameProcess, WindowInfo
from mvp.test.mock_game.game_state import GameState, UIState, ClickRecord

__all__ = [
    'IGameProcess',
    'MockGameProcess',
    'WindowInfo',
    'GameState',
    'UIState',
    'ClickRecord',
]
\\\

- [ ] **Step 7: Commit**

\\\ash
git add mvp/test/mock_game/game_process.py mvp/test/mock_game/game_state.py mvp/test/mock_game/__init__.py
git commit -m "feat: add game process abstraction and state management for mock testing"
\\\

---

### Task 2: Click Handler & Window Detection

**Files:**
- Create: \mvp/test/mock_game/click_handler.py\
- Modify: \mvp/test/mock_game/game_process.py\ (add click validation)
- Create: \mvp/test/test_with_mock_game/test_clicking.py\

**Description:** Click input system with WinAPI emulation, position validation, and timing.

[Similar structure with 7 steps: test, implement, verify, commit]

---

### Task 3: Screenshot Generation & OCR Integration

**Files:**
- Create: \mvp/test/mock_game/screenshot_generator.py\
- Create: \mvp/test/test_with_mock_game/test_ocr_with_game.py\

**Description:** Generate mock game screenshots (timer images, UI) for OCR testing.

---

### Task 4: Macro Engine (Record & Playback)

**Files:**
- Create: \mvp/test/mock_game/macro_engine.py\
- Create: \mvp/test/test_with_mock_game/test_macros.py\

**Description:** Record click sequences and playback with timing verification.

---

### Task 5: Network Mock & API Simulation

**Files:**
- Create: \mvp/test/mock_game/network_mock.py\
- Create: \mvp/test/test_with_mock_game/test_network_mock.py\

**Description:** Fake API responses, error injection, timeout simulation.

---

### Task 6: Integration Tests & Automation Script

**Files:**
- Create: \mvp/test/test_with_mock_game/test_integration_mock.py\
- Create: \uto-test-dev-build-WITH-MOCK.ps1\

**Description:** End-to-end tests combining clicking, macros, OCR, network. Update auto-test to include Tier 4.

---

## Execution Notes

- Each task produces working, testable code independently
- Use pytest fixtures from conftest.py for mock_game_process
- All tests must pass before committing
- Total implementation: 2-3 hours
- Creates 26 new automated tests
- Increases total from 32 to 58 tests

---