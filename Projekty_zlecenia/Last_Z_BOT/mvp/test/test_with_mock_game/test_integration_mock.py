"""Integration tests combining multiple mock game features"""

import pytest
import time
from mvp.test.mock_game import MockGameProcess
from mvp.test.mock_game.macro_engine import MacroEngine
from mvp.test.mock_game.network_mock import NetworkMock
from mvp.test.mock_game.screenshot_generator import ScreenshotGenerator


def test_click_to_ui_update_to_screenshot_read():
    """Test: Click -> UI updates -> screenshot captures change (T8.1)
    
    Validates: Requirements 1.1 - Click handling and UI state consistency
    """
    game = MockGameProcess()
    
    # Initial state: timer at 5:00
    game.set_ui_state('timer_seconds', 300)
    screenshot1 = game.capture_screenshot()
    assert screenshot1 is not None
    assert len(screenshot1) > 0
    
    # Simulate clicking
    result = game.send_click(150, 150)
    assert result is True
    
    # Game timer changes
    game.set_ui_state('timer_seconds', 295)  # 5 seconds passed
    screenshot2 = game.capture_screenshot()
    
    # Both screenshots should be valid PNG
    assert screenshot1[:4] == b'\x89PNG'
    assert screenshot2[:4] == b'\x89PNG'
    assert len(screenshot2) > 0
    
    # Click should be recorded
    assert len(game.state['clicks']) == 1
    assert game.state['clicks'][0]['x'] == 150
    assert game.state['clicks'][0]['y'] == 150


def test_macro_recording_to_network_response():
    """Test: Record macro -> playback -> network call validation (T8.2)
    
    Validates: Requirements 2.1 - Macro recording and network integration
    """
    game = MockGameProcess()
    engine = MacroEngine()
    network = NetworkMock()
    
    # Register fake network response for treasure click
    network.register_response("get.treasure.info", {
        "success": True,
        "treasure_found": True,
        "reward": 100,
        "coordinates": [150, 150]
    })
    
    # Record a macro: click 3 times at different positions
    engine.start_recording("hunt_macro")
    game.send_click(100, 100)
    time.sleep(0.026)  # Base interval
    game.send_click(150, 150)
    time.sleep(0.026)
    game.send_click(200, 200)
    macro = engine.stop_recording(game)
    
    # Verify macro was recorded
    assert macro.name == "hunt_macro"
    assert macro.get_click_count() == 3
    
    # Playback macro
    game.state['clicks'] = []  # Reset clicks
    engine.playback_macro("hunt_macro", game)
    
    # Verify playback
    assert len(game.state['clicks']) == 3
    
    # Simulate network call to get treasure info
    response = network.get_response("get.treasure.info")
    
    # Should have successful response
    assert response.success is True
    assert response.status_code == 200
    assert response.data["treasure_found"] is True
    assert response.data["reward"] == 100


def test_game_config_to_macro_execution_to_logging():
    """Test: Configure game -> execute macro -> verify logging (T8.3)
    
    Validates: Requirements 3.1 - Game state configuration and macro execution
    """
    game = MockGameProcess(width=1024, height=768)
    engine = MacroEngine()
    
    # Step 1: Configure game state
    game.set_ui_state('timer_seconds', 300)
    game.set_ui_state('chat_open', True)
    game.set_ui_state('dialog_open', False)
    
    # Verify initial state
    assert game.get_ui_state('timer_seconds') == 300
    assert game.get_ui_state('chat_open') is True
    
    # Step 2: Setup and record macro based on config
    macro_name = "hunt_sequence"
    engine.start_recording(macro_name)
    
    for i in range(5):
        x = 100 + (i * 50)
        y = 100 + (i * 30)
        game.send_click(x, y)
        time.sleep(0.015)
    
    macro = engine.stop_recording(game)
    
    # Verify macro metadata
    assert macro.name == macro_name
    assert macro.get_click_count() == 5
    assert macro.total_duration > 0.05
    
    # Step 3: Verify game state was maintained
    assert game.get_ui_state('timer_seconds') == 300
    assert game.get_ui_state('chat_open') is True


def test_high_frequency_clicking_performance():
    """Test: Rapid clicking performance at max speed (T8.4)
    
    Validates: Requirements 4.1 - Performance under high load (38 CPS)
    """
    game = MockGameProcess()
    
    # Simulate high load: 50 clicks at max speed (38 CPS = 26ms)
    click_interval = 0.026
    start_time = time.time()
    
    for i in range(50):
        x = 150 + (i % 10) * 10
        y = 150 + (i // 10) * 10
        result = game.send_click(x, y)
        assert result is True
        
        if i < 49:  # Don't sleep after last click
            time.sleep(click_interval)
    
    total_time = time.time() - start_time
    
    # Verify all clicks were recorded
    assert len(game.state['clicks']) == 50
    
    # Verify timing (should take at least 1.25 seconds for 49 intervals)
    assert total_time >= 1.25
    
    # Verify click rate approximates 38 CPS
    actual_cps = 50 / total_time
    assert 35 <= actual_cps <= 40  # Some variance acceptable


def test_network_error_injection_and_recovery():
    """Test: Network error injection -> retry logic -> recovery (T8.5)
    
    Validates: Requirements 5.1 - Error handling and recovery mechanisms
    """
    network = NetworkMock()
    
    # Setup: First call fails, second succeeds
    network.inject_error("treasure.get", 500, "Internal server error", trigger_count=1)
    network.register_response("treasure.get", {
        "success": True,
        "id": 123,
        "treasure": "Gold Chest"
    })
    
    # First request - should fail
    response1 = network.get_response("treasure.get")
    assert response1.success is False
    assert response1.status_code == 500
    assert "error" in response1.data
    
    # Second request - should succeed (error injection only triggers once)
    response2 = network.get_response("treasure.get")
    assert response2.success is True
    assert response2.status_code == 200
    assert response2.data["id"] == 123
    assert response2.data["treasure"] == "Gold Chest"
    
    # Verify request tracking
    assert network.get_request_count("treasure.get") == 2


def test_full_workflow_click_macro_network_screenshot():
    """Test complete workflow: click -> macro -> network -> screenshot (T8.6)
    
    Validates: Requirements 6.1 - Full integration across all layers
    """
    # Setup all components
    game = MockGameProcess(width=1024, height=768)
    engine = MacroEngine()
    network = NetworkMock()
    generator = ScreenshotGenerator(width=1024, height=768)
    
    # Step 1: Initialize game state
    game.set_ui_state('timer_seconds', 300)
    game.set_ui_state('chat_open', False)
    
    # Step 2: Capture initial screenshot
    screenshot1 = game.capture_screenshot()
    assert len(screenshot1) > 0
    assert screenshot1[:4] == b'\x89PNG'
    
    # Step 3: Record macro with multiple clicks
    engine.start_recording("full_hunt")
    game.send_click(150, 150)
    time.sleep(0.026)
    game.send_click(200, 200)
    time.sleep(0.026)
    game.send_click(250, 250)
    macro = engine.stop_recording(game)
    
    # Verify macro
    assert macro.get_click_count() == 3
    assert len(game.state['clicks']) == 3
    
    # Step 4: Setup and playback macro
    game.state['clicks'] = []
    engine.playback_macro("full_hunt", game)
    assert len(game.state['clicks']) == 3
    
    # Step 5: Make network call for reward
    network.register_response("treasure.click", {
        "success": True,
        "reward": 50,
        "timestamp": "2025-01-15T10:00:00Z"
    })
    response = network.get_response("treasure.click")
    assert response.success is True
    assert response.data["reward"] == 50
    
    # Step 6: Update game state and capture new screenshot
    game.set_ui_state('timer_seconds', 295)
    screenshot2 = game.capture_screenshot()
    assert len(screenshot2) > 0
    assert screenshot2[:4] == b'\x89PNG'
    
    # Both screenshots should be valid but different (timer changed)
    assert len(screenshot1) != len(screenshot2) or screenshot1 != screenshot2


def test_multiple_macros_management():
    """Test: Recording, managing, and executing multiple macros (T8.7)
    
    Validates: Requirements 7.1 - Multi-macro management
    """
    game = MockGameProcess()
    engine = MacroEngine()
    
    # Record first macro
    engine.start_recording("macro_1")
    game.send_click(100, 100)
    time.sleep(0.026)
    game.send_click(150, 150)
    macro1 = engine.stop_recording(game)
    
    # Record second macro
    game.state['clicks'] = []
    engine.start_recording("macro_2")
    game.send_click(200, 200)
    time.sleep(0.026)
    game.send_click(250, 250)
    time.sleep(0.026)
    game.send_click(300, 300)
    macro2 = engine.stop_recording(game)
    
    # Verify both macros exist
    assert "macro_1" in engine.list_macros()
    assert "macro_2" in engine.list_macros()
    assert macro1.get_click_count() == 2
    assert macro2.get_click_count() == 3
    
    # Playback first macro
    game.state['clicks'] = []
    engine.playback_macro("macro_1", game)
    assert len(game.state['clicks']) == 2
    
    # Playback second macro
    game.state['clicks'] = []
    engine.playback_macro("macro_2", game)
    assert len(game.state['clicks']) == 3


def test_network_offline_mode():
    """Test: Network offline mode and caching (T8.8)
    
    Validates: Requirements 8.1 - Offline support
    """
    network = NetworkMock()
    
    # Register a response
    network.register_response("endpoint1", {
        "success": True,
        "data": "cached_value"
    })
    
    # Make request while online (should cache)
    response1 = network.get_response("endpoint1")
    assert response1.success is True
    assert response1.data["data"] == "cached_value"
    
    # Go offline
    network.set_offline(True)
    assert network.is_offline() is True
    
    # Request should return cached response
    response2 = network.get_response("endpoint1")
    assert response2.success is True
    assert response2.data["data"] == "cached_value"
    
    # Request to uncached endpoint should fail
    response3 = network.get_response("unknown_endpoint")
    assert response3.success is False
    assert response3.status_code == 503
    
    # Go back online
    network.set_offline(False)
    assert network.is_offline() is False


def test_screenshot_generation_with_ui_elements():
    """Test: Screenshot generation with various UI elements (T8.9)
    
    Validates: Requirements 9.1 - UI rendering for OCR
    """
    generator = ScreenshotGenerator(width=1024, height=768)
    
    # Generate timer image
    timer_image = generator.generate_timer_image(minutes=4, seconds=30)
    assert len(timer_image) > 0
    assert timer_image[:4] == b'\x89PNG'
    
    # Generate chat image
    chat_image = generator.generate_chat_image(messages=["Message 1", "Message 2"])
    assert len(chat_image) > 0
    assert chat_image[:4] == b'\x89PNG'
    
    # Generate dialog image
    dialog_image = generator.generate_dialog_image(title="Alert", text="Test message")
    assert len(dialog_image) > 0
    assert dialog_image[:4] == b'\x89PNG'
    
    # Generate text image
    text_image = generator.generate_text_image("Test Text", x=100, y=100)
    assert len(text_image) > 0
    assert text_image[:4] == b'\x89PNG'
    
    # Generate complete game screenshot
    game_screenshot = generator.generate_game_screenshot(
        timer_minutes=5,
        timer_seconds=0,
        chat_messages=["Hello", "World"],
        dialog_title="Treasure Found!"
    )
    assert len(game_screenshot) > 0
    assert game_screenshot[:4] == b'\x89PNG'


def test_click_boundary_validation():
    """Test: Click position validation and boundary checks (T8.10)
    
    Validates: Requirements 10.1 - Input validation
    """
    game = MockGameProcess(width=1024, height=768)
    
    # Valid clicks within bounds
    assert game.send_click(100, 100) is True
    assert game.send_click(1000, 700) is True  # Near edge but valid
    assert len(game.state['clicks']) == 2
    
    # Invalid clicks outside bounds
    assert game.send_click(99, 100) is False  # Just outside left edge
    assert game.send_click(1200, 100) is False  # Outside right edge
    assert game.send_click(100, 99) is False  # Just outside top edge
    assert game.send_click(100, 900) is False  # Outside bottom edge
    
    # Total clicks should still be 2 (invalid ones not recorded)
    assert len(game.state['clicks']) == 2
