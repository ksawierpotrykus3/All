"""Tests for macro recording and playback"""

import pytest
import time
from mvp.test.mock_game import MockGameProcess
from mvp.test.mock_game.macro_engine import MacroEngine, Macro


def test_record_macro_sequence():
    """Test recording a macro sequence"""
    engine = MacroEngine()
    game = MockGameProcess()
    
    # Record clicks
    engine.start_recording("test_macro")
    engine.record_click_during_session(150, 150)
    time.sleep(0.026)
    engine.record_click_during_session(200, 200)
    time.sleep(0.026)
    engine.record_click_during_session(250, 250)
    macro = engine.stop_recording(game)
    
    assert macro is not None
    assert macro.name == "test_macro"
    assert len(macro.clicks) == 3
    assert macro.clicks[0]['x'] == 150
    assert macro.clicks[1]['x'] == 200
    assert macro.clicks[2]['x'] == 250


def test_playback_macro():
    """Test playing back a recorded macro"""
    engine = MacroEngine()
    game = MockGameProcess()
    
    # Record macro
    engine.start_recording("click_three")
    game.send_click(100, 100)
    time.sleep(0.026)
    game.send_click(150, 150)
    time.sleep(0.026)
    game.send_click(200, 200)
    macro = engine.stop_recording(game)
    
    # Clear game state
    game.state['clicks'] = []
    
    # Playback macro
    engine.playback_macro("click_three", game)
    
    # Should have 3 clicks
    assert len(game.state['clicks']) == 3


def test_macro_timing_precision():
    """Test that macro playback respects timing"""
    engine = MacroEngine()
    game = MockGameProcess()
    
    # Record macro with specific timing
    engine.start_recording("timed_macro")
    start = time.time()
    engine.record_click_during_session(150, 150)
    time.sleep(0.026)  # 26ms interval
    engine.record_click_during_session(200, 200)
    time.sleep(0.026)
    engine.record_click_during_session(250, 250)
    macro = engine.stop_recording(game)
    
    # Verify timing was captured
    assert macro.total_duration >= 0.050  # At least 50ms (2 x 26ms)
    
    # Playback and verify similar timing
    game.state['clicks'] = []
    playback_start = time.time()
    engine.playback_macro("timed_macro", game)
    playback_duration = time.time() - playback_start
    
    # Playback should take similar time (within 20% tolerance)
    assert abs(playback_duration - macro.total_duration) < 0.020


def test_pause_resume_macro():
    """Test pausing and resuming macro recording"""
    engine = MacroEngine()
    game = MockGameProcess()
    
    # Start recording
    engine.start_recording("pause_macro")
    engine.record_click_during_session(100, 100)
    time.sleep(0.01)
    
    # Pause
    engine.pause_recording()
    time.sleep(0.050)  # This delay should NOT be recorded
    engine.record_click_during_session(200, 200)  # This click should NOT be recorded (paused)
    
    # Resume
    engine.resume_recording()
    time.sleep(0.01)
    engine.record_click_during_session(300, 300)
    macro = engine.stop_recording(game)
    
    # Should have only 2 clicks (first and third, not second)
    assert len(macro.clicks) == 2
    assert macro.clicks[0]['x'] == 100
    assert macro.clicks[1]['x'] == 300


def test_macro_with_delay_injection():
    """Test adding delays between macro actions"""
    engine = MacroEngine()
    game = MockGameProcess()
    
    # Record simple macro WITH timing between clicks
    engine.start_recording("simple")
    engine.record_click_during_session(150, 150)
    time.sleep(0.026)  # Add timing
    engine.record_click_during_session(200, 200)
    macro = engine.stop_recording(game)
    
    # Playback with extra delay multiplier
    game.state['clicks'] = []
    start = time.time()
    engine.playback_macro("simple", game, delay_multiplier=2.0)
    duration = time.time() - start
    
    # Should take longer due to multiplier (2x the original ~26ms)
    assert len(game.state['clicks']) == 2
    assert duration > 0.04  # Should have delays (original ~26ms * 2 = 52ms)
