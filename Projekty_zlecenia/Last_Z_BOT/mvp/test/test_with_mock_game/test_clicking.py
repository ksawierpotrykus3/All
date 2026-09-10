"""Tests for clicking system with mock game"""

import pytest
import time
from mvp.test.mock_game import MockGameProcess


def test_single_click_recognized():
    """Test that a single click is recorded"""
    game = MockGameProcess()
    result = game.send_click(150, 150)
    assert result is True
    assert len(game.state['clicks']) == 1
    assert game.state['clicks'][0]['x'] == 150
    assert game.state['clicks'][0]['y'] == 150


def test_multiple_clicks_in_sequence():
    """Test recording multiple clicks in sequence"""
    game = MockGameProcess()
    clicks = [(150, 150), (200, 200), (250, 250)]
    
    for x, y in clicks:
        result = game.send_click(x, y)
        assert result is True
    
    assert len(game.state['clicks']) == 3
    for i, (x, y) in enumerate(clicks):
        assert game.state['clicks'][i]['x'] == x
        assert game.state['clicks'][i]['y'] == y


def test_click_timing_verification():
    """Test that click timing can be measured"""
    game = MockGameProcess()
    
    # Simulate clicks with 26ms interval (38 CPS)
    click_interval = 0.026  # 26ms
    start_time = time.time()
    
    game.send_click(150, 150)
    time.sleep(click_interval)
    game.send_click(200, 200)
    time.sleep(click_interval)
    game.send_click(250, 250)
    
    elapsed = time.time() - start_time
    
    # Should have 3 clicks
    assert len(game.state['clicks']) == 3
    # Elapsed time should be approximately 52ms (2 intervals)
    assert elapsed >= 0.05  # At least 50ms


def test_click_outside_window_rejected():
    """Test that clicks outside window bounds are rejected"""
    game = MockGameProcess(width=800, height=600)
    # Window is at (100, 100) to (900, 700)
    
    # Try to click outside window
    result_left = game.send_click(50, 150)  # x too small
    result_top = game.send_click(150, 50)   # y too small
    result_right = game.send_click(950, 150)  # x too large
    result_bottom = game.send_click(150, 750)  # y too large
    
    assert result_left is False
    assert result_top is False
    assert result_right is False
    assert result_bottom is False
    assert len(game.state['clicks']) == 0


def test_rapid_clicks_38_cps():
    """Test rapid clicking at 38 CPS (26ms interval)"""
    game = MockGameProcess()
    click_interval = 0.026  # 26ms per click for 38 CPS
    
    # Send 10 rapid clicks
    for i in range(10):
        x = 150 + (i % 5) * 50
        y = 150 + (i // 5) * 50
        result = game.send_click(x, y)
        assert result is True
        time.sleep(click_interval)
    
    assert len(game.state['clicks']) == 10


def test_click_with_focus_change():
    """Test clicking after losing and regaining focus"""
    game = MockGameProcess()
    
    # Initial click
    result1 = game.send_click(150, 150)
    assert result1 is True
    
    # Simulate focus loss by changing window position
    game.x = 200
    game.y = 200
    
    # Click should be evaluated against new position
    result2 = game.send_click(250, 250)  # (200,200) to (1000,968) with new position
    assert result2 is True
    
    assert len(game.state['clicks']) == 2
