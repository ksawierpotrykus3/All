"""Tests for game process abstraction layer"""

import pytest
from mvp.test.mock_game.game_process import MockGameProcess, WindowInfo


def test_mock_game_process_creates_window():
    """Test that MockGameProcess creates a valid game window"""
    game = MockGameProcess(title="LastZ Game", width=800, height=600)
    assert game.hwnd is not None
    assert game.hwnd > 0
    assert game.title == "LastZ Game"
    assert game.width == 800
    assert game.height == 600


def test_mock_game_process_default_values():
    """Test that MockGameProcess uses default values when not specified"""
    game = MockGameProcess()
    assert game.title == "LastZ Game"
    assert game.width == 1024
    assert game.height == 768


def test_get_window_info():
    """Test get_window_info returns correct WindowInfo"""
    game = MockGameProcess(title="Test", width=640, height=480)
    info = game.get_window_info()
    assert isinstance(info, WindowInfo)
    assert info.hwnd == game.hwnd
    assert info.title == "Test"
    assert info.width == 640
    assert info.height == 480


def test_send_click_within_bounds():
    """Test sending click within window bounds"""
    game = MockGameProcess(width=800, height=600)
    # Window is at (100, 100) to (100+800, 100+600)
    result = game.send_click(150, 150)
    assert result is True
    assert len(game.state["clicks"]) == 1
    assert game.state["clicks"][0]["x"] == 150
    assert game.state["clicks"][0]["y"] == 150


def test_send_click_outside_bounds_x():
    """Test sending click outside window bounds (x-axis)"""
    game = MockGameProcess(width=800, height=600)
    # Try to click before window (x=50 < window.x=100)
    result = game.send_click(50, 150)
    assert result is False
    assert len(game.state["clicks"]) == 0


def test_send_click_outside_bounds_y():
    """Test sending click outside window bounds (y-axis)"""
    game = MockGameProcess(width=800, height=600)
    # Try to click above window
    result = game.send_click(150, 50)
    assert result is False
    assert len(game.state["clicks"]) == 0


def test_ui_state_get_set():
    """Test getting and setting UI state"""
    game = MockGameProcess()
    game.set_ui_state("timer_seconds", 100)
    assert game.get_ui_state("timer_seconds") == 100

    game.set_ui_state("chat_open", True)
    assert game.get_ui_state("chat_open") is True


def test_ui_state_missing_key():
    """Test getting missing UI state key returns None"""
    game = MockGameProcess()
    assert game.get_ui_state("nonexistent_key") is None
