"""Tests for game simulator components."""

import pytest
import time
import numpy as np
from pathlib import Path
from PIL import Image
import json
import requests
import threading

from mvp.tests.test_framework.game_simulator import (
    GameStateSimulator,
    GameStateUpdate,
    ClickResult,
    ScreenRenderer,
    MockHTTPServer,
)
from mvp.tests.test_framework.scenarios import (
    Scenario,
    MonitorConfig,
    ChatState,
    GlitchType,
)


class TestGameStateSimulator:
    """Tests for GameStateSimulator class."""

    @pytest.fixture
    def basic_scenario(self) -> Scenario:
        """Create a basic test scenario."""
        return Scenario(
            id="test_scenario",
            window_x=0,
            window_y=0,
            window_width=1024,
            window_height=768,
            game_area_x=0,
            game_area_y=0,
            game_area_width=1024,
            game_area_height=768,
            dpi=96,
            monitors=[MonitorConfig(id=0, width=1024, height=768, dpi=96)],
            chat_state=ChatState.CLOSED,
            timer_seconds=300,
            click_jitter_ms=0,
            timer_jitter_ms=0,
            glitch_type=GlitchType.NONE,
        )

    def test_state_initialization(self, basic_scenario: Scenario) -> None:
        """Test GameStateSimulator initialization."""
        simulator = GameStateSimulator(basic_scenario)
        
        assert simulator.frame_number == 0
        assert simulator.chat_open is False
        assert simulator.timer_seconds == 300
        assert simulator.scroll_position == 0
        assert simulator.heli_alert_active is False
        assert simulator.details_open is False
        assert simulator.click_count == 0

    def test_state_initialization_with_open_chat(self, basic_scenario: Scenario) -> None:
        """Test initialization with open chat."""
        basic_scenario.chat_state = ChatState.OPEN
        simulator = GameStateSimulator(basic_scenario)
        
        assert simulator.chat_open is True

    def test_timer_countdown(self, basic_scenario: Scenario) -> None:
        """Test timer countdown on each tick."""
        basic_scenario.timer_seconds = 5
        simulator = GameStateSimulator(basic_scenario)
        
        # Tick 1
        update1 = simulator.tick()
        assert update1.timer_seconds_current == 4
        assert simulator.timer_seconds == 4
        
        # Tick 2
        update2 = simulator.tick()
        assert update2.timer_seconds_current == 3
        assert simulator.timer_seconds == 3

    def test_timer_never_negative(self, basic_scenario: Scenario) -> None:
        """Test that timer never goes below 0."""
        basic_scenario.timer_seconds = 1
        simulator = GameStateSimulator(basic_scenario)
        
        # Tick 1
        simulator.tick()
        assert simulator.timer_seconds == 0
        
        # Tick 2 (should stay at 0)
        simulator.tick()
        assert simulator.timer_seconds == 0

    def test_heli_alert_activation(self, basic_scenario: Scenario) -> None:
        """Test heli alert triggers when timer < 5s."""
        basic_scenario.timer_seconds = 6
        simulator = GameStateSimulator(basic_scenario)
        
        # Tick down to 5s
        for _ in range(1):  # 6 -> 5
            simulator.tick()
        assert simulator.heli_alert_active is False
        
        # Tick down to 4s (should trigger heli alert)
        update = simulator.tick()
        assert simulator.heli_alert_active is True
        assert "heli_alert_activated" in update.events_triggered

    def test_event_injection(self, basic_scenario: Scenario) -> None:
        """Test injecting events at specified delays."""
        simulator = GameStateSimulator(basic_scenario)
        
        # Inject event at 100ms
        simulator.inject_event("chat_open", 100)
        
        assert len(simulator.events) == 1

    def test_event_triggering(self, basic_scenario: Scenario) -> None:
        """Test that injected events trigger at correct time."""
        simulator = GameStateSimulator(basic_scenario)
        
        # Inject event at ~50ms delay
        simulator.inject_event("test_event", 50)
        
        # Tick several times to let event trigger
        time.sleep(0.06)  # Wait 60ms
        update = simulator.tick()
        
        assert "test_event" in update.events_triggered

    def test_click_processing_timer_area(self, basic_scenario: Scenario) -> None:
        """Test clicking in timer area."""
        simulator = GameStateSimulator(basic_scenario)
        
        result = simulator.process_click(950, 40)
        
        assert result.element_clicked == "timer"
        assert result.success is True
        assert simulator.click_count == 1

    def test_click_processing_chat_area(self, basic_scenario: Scenario) -> None:
        """Test clicking in chat area."""
        simulator = GameStateSimulator(basic_scenario)
        
        result = simulator.process_click(100, 650)
        
        assert result.element_clicked == "chat_area"
        assert result.success is True
        assert simulator.click_count == 1

    def test_click_processing_treasure_area(self, basic_scenario: Scenario) -> None:
        """Test clicking on treasure."""
        simulator = GameStateSimulator(basic_scenario)
        
        result = simulator.process_click(500, 400)
        
        assert result.element_clicked == "treasure"
        assert result.success is True
        assert simulator.treasure_found is True
        assert simulator.treasure_x == 500
        assert simulator.treasure_y == 400

    def test_click_processing_empty_area(self, basic_scenario: Scenario) -> None:
        """Test clicking on empty area."""
        simulator = GameStateSimulator(basic_scenario)
        
        result = simulator.process_click(100, 100)
        
        assert result.element_clicked == "nothing"
        assert result.success is False

    def test_click_count_increment(self, basic_scenario: Scenario) -> None:
        """Test click count increments."""
        simulator = GameStateSimulator(basic_scenario)
        
        assert simulator.click_count == 0
        simulator.process_click(100, 100)
        assert simulator.click_count == 1
        simulator.process_click(200, 200)
        assert simulator.click_count == 2

    def test_frame_glitch_at_5(self, basic_scenario: Scenario) -> None:
        """Test frame drop glitch at frame 5."""
        basic_scenario.glitch_type = GlitchType.FRAME_DROP_AT_5
        simulator = GameStateSimulator(basic_scenario)
        
        # Tick to frame 5
        for i in range(5):
            update = simulator.tick()
            if i == 4:  # Frame 5
                assert "frame_glitch" in update.events_triggered

    def test_frame_glitch_at_50(self, basic_scenario: Scenario) -> None:
        """Test frame drop glitch at frame 50."""
        basic_scenario.glitch_type = GlitchType.FRAME_DROP_AT_50
        simulator = GameStateSimulator(basic_scenario)
        
        # Tick to frame 50
        glitch_found = False
        for i in range(50):
            update = simulator.tick()
            if i == 49:  # Frame 50
                if "frame_glitch" in update.events_triggered:
                    glitch_found = True
        
        assert glitch_found

    def test_get_state_dict(self, basic_scenario: Scenario) -> None:
        """Test get_state_dict method."""
        simulator = GameStateSimulator(basic_scenario)
        
        state_dict = simulator.get_state_dict()
        
        assert "timer_seconds" in state_dict
        assert "click_count" in state_dict
        assert "treasure_count" in state_dict
        assert state_dict["timer_seconds"] == 300
        assert state_dict["click_count"] == 0
        assert state_dict["treasure_count"] == 0

    def test_reset(self, basic_scenario: Scenario) -> None:
        """Test reset functionality."""
        simulator = GameStateSimulator(basic_scenario)
        
        # Modify state
        simulator.tick()
        simulator.process_click(500, 400)
        
        assert simulator.frame_number > 0
        assert simulator.click_count > 0
        
        # Reset
        simulator.reset()
        
        assert simulator.frame_number == 0
        assert simulator.click_count == 0
        assert simulator.treasure_found is False


class TestScreenRenderer:
    """Tests for ScreenRenderer class."""

    @pytest.fixture
    def test_data_dir(self, tmp_path: Path) -> Path:
        """Create temporary test data directory with dummy templates."""
        # Create dummy PNG templates
        template_names = [
            "no_chat.png",
            "1_scan_chat_with_arrow.png",
            "1_scan_chat_without_arrow.png",
            "details.png",
            "1_heli_alert_appearing_in_chat.png",
            "helka_scrolled.png",
        ]
        
        for name in template_names:
            # Create 1024x768 PNG template
            img = Image.new("RGB", (1024, 768), color=(0, 0, 0))
            img.save(tmp_path / name)
        
        return tmp_path

    @pytest.fixture
    def basic_scenario(self) -> Scenario:
        """Create basic scenario."""
        return Scenario(
            id="test_scenario",
            window_x=0,
            window_y=0,
            window_width=1024,
            window_height=768,
            game_area_x=0,
            game_area_y=0,
            game_area_width=1024,
            game_area_height=768,
            dpi=96,
            monitors=[MonitorConfig(id=0, width=1024, height=768, dpi=96)],
            chat_state=ChatState.CLOSED,
            timer_seconds=300,
            click_jitter_ms=0,
            timer_jitter_ms=0,
            glitch_type=GlitchType.NONE,
        )

    def test_renderer_initialization(self, test_data_dir: Path) -> None:
        """Test ScreenRenderer initialization."""
        renderer = ScreenRenderer(test_data_dir)
        
        assert renderer.test_data_dir == test_data_dir
        assert len(renderer.templates) > 0

    def test_render_full_size(self, test_data_dir: Path, basic_scenario: Scenario) -> None:
        """Test rendering at full size (1024x768)."""
        renderer = ScreenRenderer(test_data_dir)
        simulator = GameStateSimulator(basic_scenario)
        
        frame = renderer.render(simulator, (1024, 768))
        
        assert frame.shape == (768, 1024, 3)
        assert frame.dtype == np.uint8
        assert frame.min() >= 0
        assert frame.max() <= 255

    def test_render_clipped_800x600(self, test_data_dir: Path, basic_scenario: Scenario) -> None:
        """Test rendering with clipping to 800x600."""
        renderer = ScreenRenderer(test_data_dir)
        simulator = GameStateSimulator(basic_scenario)
        
        frame = renderer.render(simulator, (800, 600))
        
        # Should still return 1024x768 but with clipped content
        assert frame.shape == (768, 1024, 3)
        
        # Check that bottom-right area is black (padding)
        # Bottom part should be black
        assert np.all(frame[600:, :, :] == 0)
        # Right part should be black
        assert np.all(frame[:, 800:, :] == 0)

    def test_render_with_timer_text(self, test_data_dir: Path, basic_scenario: Scenario) -> None:
        """Test that timer text is rendered."""
        renderer = ScreenRenderer(test_data_dir)
        simulator = GameStateSimulator(basic_scenario)
        simulator.timer_seconds = 150
        
        frame = renderer.render(simulator, (1024, 768))
        
        # Frame should have some non-zero values (text)
        assert frame.max() > 0

    def test_render_scrolled(self, test_data_dir: Path, basic_scenario: Scenario) -> None:
        """Test rendering with scroll."""
        renderer = ScreenRenderer(test_data_dir)
        simulator = GameStateSimulator(basic_scenario)
        simulator.scroll_position = 50
        
        frame = renderer.render(simulator, (1024, 768))
        
        assert frame.shape == (768, 1024, 3)
        # Top portion should be black due to scroll
        assert np.all(frame[0:50, :, :] == 0)

    def test_render_small_window_clipping(self, test_data_dir: Path, basic_scenario: Scenario) -> None:
        """Test clipping for very small window."""
        renderer = ScreenRenderer(test_data_dir)
        simulator = GameStateSimulator(basic_scenario)
        
        frame = renderer.render(simulator, (640, 480))
        
        assert frame.shape == (768, 1024, 3)
        # Right and bottom should be black
        assert np.all(frame[480:, :, :] == 0)
        assert np.all(frame[:, 640:, :] == 0)


class TestMockHTTPServer:
    """Tests for MockHTTPServer."""

    @pytest.fixture
    def basic_scenario(self) -> Scenario:
        """Create basic scenario."""
        return Scenario(
            id="test_scenario",
            window_x=0,
            window_y=0,
            window_width=1024,
            window_height=768,
            game_area_x=0,
            game_area_y=0,
            game_area_width=1024,
            game_area_height=768,
            dpi=96,
            monitors=[MonitorConfig(id=0, width=1024, height=768, dpi=96)],
            chat_state=ChatState.CLOSED,
            timer_seconds=300,
            click_jitter_ms=0,
            timer_jitter_ms=0,
            glitch_type=GlitchType.NONE,
        )

    def test_http_server_initialization(self, basic_scenario: Scenario) -> None:
        """Test MockHTTPServer initialization."""
        simulator = GameStateSimulator(basic_scenario)
        server = MockHTTPServer(simulator, port=9999)
        
        assert server.game_state is simulator
        assert server.port == 9999
        assert server._running is False

    def test_http_server_start_stop(self, basic_scenario: Scenario) -> None:
        """Test starting and stopping the server."""
        simulator = GameStateSimulator(basic_scenario)
        server = MockHTTPServer(simulator, port=9998)
        
        server.start()
        time.sleep(0.5)  # Let server start
        
        # Check if thread is alive
        assert server.is_alive() is True
        
        server.stop()
        time.sleep(0.3)  # Let server stop
        
        assert server.is_running() is False

    def test_api_game_state_response(self, basic_scenario: Scenario) -> None:
        """Test /api/game/state endpoint."""
        simulator = GameStateSimulator(basic_scenario)
        server = MockHTTPServer(simulator, port=9997)
        
        server.start()
        time.sleep(0.5)  # Let server start
        
        try:
            response = requests.get("http://localhost:9997/api/game/state", timeout=3)
            assert response.status_code == 200
            
            data = response.json()
            assert "timer_seconds" in data
            assert "click_count" in data
            assert "treasure_count" in data
            assert data["timer_seconds"] == 300
            assert data["click_count"] == 0
        finally:
            server.stop()
            time.sleep(0.3)

    def test_api_treasure_not_found(self, basic_scenario: Scenario) -> None:
        """Test /api/treasure/check when treasure not found."""
        simulator = GameStateSimulator(basic_scenario)
        server = MockHTTPServer(simulator, port=9996)
        
        server.start()
        time.sleep(0.5)
        
        try:
            response = requests.get("http://localhost:9996/api/treasure/check", timeout=3)
            assert response.status_code == 200
            
            data = response.json()
            assert "found" in data
            assert data["found"] is False
        finally:
            server.stop()
            time.sleep(0.3)

    def test_api_treasure_found(self, basic_scenario: Scenario) -> None:
        """Test /api/treasure/check when treasure found."""
        simulator = GameStateSimulator(basic_scenario)
        server = MockHTTPServer(simulator, port=9995)
        
        # Find treasure
        simulator.process_click(500, 400)
        
        server.start()
        time.sleep(0.5)
        
        try:
            response = requests.get("http://localhost:9995/api/treasure/check", timeout=3)
            assert response.status_code == 200
            
            data = response.json()
            assert data["found"] is True
            assert "x" in data
            assert "y" in data
            assert data["x"] == 500
            assert data["y"] == 400
        finally:
            server.stop()
            time.sleep(0.3)

    def test_api_state_updates(self, basic_scenario: Scenario) -> None:
        """Test that API returns updated state."""
        simulator = GameStateSimulator(basic_scenario)
        server = MockHTTPServer(simulator, port=9994)
        
        server.start()
        time.sleep(0.5)
        
        try:
            # Get initial state
            response1 = requests.get("http://localhost:9994/api/game/state", timeout=3)
            data1 = response1.json()
            initial_clicks = data1["click_count"]
            
            # Process a click
            simulator.process_click(500, 400)
            
            # Get updated state
            response2 = requests.get("http://localhost:9994/api/game/state", timeout=3)
            data2 = response2.json()
            updated_clicks = data2["click_count"]
            
            assert updated_clicks > initial_clicks
        finally:
            server.stop()
            time.sleep(0.3)
