"""Tests for game state management"""

import pytest
from datetime import datetime
from mvp.test.mock_game.game_state import GameState, UIState, ClickRecord


def test_ui_state_default_values():
    """Test UIState has correct default values"""
    ui = UIState()
    assert ui.timer_seconds == 300
    assert ui.chat_open is False
    assert ui.dialog_open is False
    assert ui.macro_recording is False


def test_ui_state_custom_values():
    """Test UIState can be initialized with custom values"""
    ui = UIState(timer_seconds=100, chat_open=True, dialog_open=True)
    assert ui.timer_seconds == 100
    assert ui.chat_open is True
    assert ui.dialog_open is True


def test_click_record_creation():
    """Test ClickRecord stores click information"""
    now = datetime.now()
    click = ClickRecord(x=150, y=200, timestamp=now, button="left")
    assert click.x == 150
    assert click.y == 200
    assert click.timestamp == now
    assert click.button == "left"


def test_game_state_initialization():
    """Test GameState initializes with empty collections"""
    state = GameState()
    assert isinstance(state.ui, UIState)
    assert len(state.clicks) == 0
    assert len(state.macros) == 0
    assert len(state.network_responses) == 0


def test_record_click():
    """Test recording a click in game state"""
    state = GameState()
    state.record_click(100, 200)
    assert len(state.clicks) == 1
    assert state.clicks[0].x == 100
    assert state.clicks[0].y == 200
    assert isinstance(state.clicks[0].timestamp, datetime)


def test_record_multiple_clicks():
    """Test recording multiple clicks"""
    state = GameState()
    state.record_click(100, 200)
    state.record_click(150, 250)
    state.record_click(200, 300)
    assert len(state.clicks) == 3


def test_record_macro():
    """Test recording a macro"""
    state = GameState()
    clicks = [
        ClickRecord(x=100, y=200, timestamp=datetime.now()),
        ClickRecord(x=150, y=250, timestamp=datetime.now()),
    ]
    state.record_macro("click_sequence", clicks)
    assert "click_sequence" in state.macros
    assert state.macros["click_sequence"] == clicks


def test_get_macro():
    """Test retrieving a recorded macro"""
    state = GameState()
    clicks = [ClickRecord(x=100, y=200, timestamp=datetime.now())]
    state.record_macro("test_macro", clicks)
    retrieved = state.get_macro("test_macro")
    assert retrieved == clicks


def test_get_macro_not_found():
    """Test getting non-existent macro returns empty list"""
    state = GameState()
    retrieved = state.get_macro("nonexistent")
    assert retrieved == []


def test_game_state_ui_manipulation():
    """Test manipulating UI state through GameState"""
    state = GameState()
    state.ui.timer_seconds = 100
    state.ui.chat_open = True
    assert state.ui.timer_seconds == 100
    assert state.ui.chat_open is True


def test_network_responses_storage():
    """Test storing network responses in game state"""
    state = GameState()
    state.network_responses["get_treasure"] = {"success": True, "treasure_id": 123}
    assert state.network_responses["get_treasure"]["treasure_id"] == 123
