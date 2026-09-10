"""Integration test fixtures for bot framework."""

import queue
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from mvp.config import MVPConfig
from mvp.tests.test_framework.scenarios import Scenario, MonitorConfig, ChatState, GlitchType
from mvp.tests.test_framework.game_simulator import GameStateSimulator, ScreenRenderer, MockHTTPServer
from mvp.tests.test_framework.cpu_profiler import CPUProfiler
from mvp.tests.test_framework.metrics import MetricsCollector

if TYPE_CHECKING:
    from mvp.bot.macro_engine import MacroEngine
    from mvp.tests.test_framework.game_simulator import GameStateSimulator


class FakeWindowContext:
    """Fake WindowContext for testing without WinAPI."""

    def __init__(self, left: int, top: int, width: int, height: int) -> None:
        """Initialize fake window context.
        
        Args:
            left: Window left position
            top: Window top position
            width: Window width
            height: Window height
        """
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    def __iter__(self):
        """Allow unpacking as tuple."""
        return iter((self.left, self.top, self.width, self.height))


@pytest.fixture
def bot_config() -> MVPConfig:
    """Provide default bot configuration for testing.
    
    Returns:
        MVPConfig with testing defaults
    """
    config = MVPConfig()
    config.scan_fps = 30
    config.click_min_delay_ms = 50
    config.click_max_delay_ms = 100
    config.spam_clicks_per_sec = 30
    config.preview_enabled = False
    config.log_verbose = False
    return config


@pytest.fixture
def window_context() -> FakeWindowContext:
    """Provide a fake window context for testing.
    
    Returns:
        FakeWindowContext representing a 1024x768 window at origin
    """
    return FakeWindowContext(left=0, top=0, width=1024, height=768)


@pytest.fixture
def offscreen_window_context() -> FakeWindowContext:
    """Provide an offscreen window context for edge case testing.
    
    Returns:
        FakeWindowContext partially offscreen
    """
    return FakeWindowContext(left=-100, top=-100, width=1024, height=768)


@pytest.fixture
def multi_monitor_window_context() -> FakeWindowContext:
    """Provide a window context on secondary monitor.
    
    Returns:
        FakeWindowContext on secondary monitor (offset by 1920 pixels)
    """
    return FakeWindowContext(left=1920, top=0, width=1024, height=768)


@pytest.fixture
def mock_screen_renderer():
    """Provide a mock screen renderer for synthetic frame generation.
    
    Returns:
        MagicMock that generates synthetic frames
    """
    renderer = MagicMock()

    def generate_frame(width: int, height: int) -> np.ndarray:
        """Generate synthetic frame with gradient pattern."""
        # Create a simple gradient pattern frame for testing
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            frame[y, :] = (y * 255 // height, 128, 255 - (y * 255 // height))
        return frame

    renderer.render = MagicMock(side_effect=lambda w, h: generate_frame(w, h))
    return renderer


@pytest.fixture
def macro_engine() -> MagicMock:
    """Provide a MacroEngine instance with mocked dependencies.
        
    Returns:
        Mocked MacroEngine for testing
    """
    engine = MagicMock()

    # Mock Clicker methods
    engine.clicker = MagicMock()
    engine.clicker.click = MagicMock()
    engine.clicker.scroll = MagicMock()

    # Mock OCR methods
    engine.ocr = MagicMock()
    engine.ocr.detect_timer = MagicMock(return_value="00:05:00")
    engine.ocr.detect_chat = MagicMock(return_value=False)

    # Mock execution
    engine.run = MagicMock(return_value=MagicMock(success=True))

    return engine


@pytest.fixture
def game_state_simulator() -> MagicMock:
    """Provide a mock game state simulator.
    
    Returns:
        MagicMock simulating game state changes
    """
    simulator = MagicMock()
    simulator.update_state = MagicMock()
    simulator.get_current_state = MagicMock(return_value={"timer": "00:05:00", "chat_open": False})
    return simulator


@pytest.fixture
def mock_bot_runner(bot_config, window_context) -> MagicMock:
    """Provide a mock BotRunner for testing.
    
    Args:
        bot_config: Bot configuration
        window_context: Window context
        
    Returns:
        Mocked BotRunner instance
    """
    runner = MagicMock()
    runner.config = bot_config
    runner.macro_engine = MagicMock()
    runner.macro_engine.run = MagicMock(return_value=MagicMock(success=True))
    runner.is_running = MagicMock(return_value=True)
    runner.start = MagicMock()
    runner.stop = MagicMock()
    runner._window_monitor_thread = None
    return runner


@pytest.fixture
def test_scenario() -> Scenario:
    """Provide a standard test scenario for integration testing.
    
    Returns:
        Scenario with 1024x768 window at origin, 96 DPI
    """
    return Scenario(
        id="integration_test_scenario",
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


@pytest.fixture
def multi_monitor_scenario() -> Scenario:
    """Provide a multi-monitor test scenario.
    
    Returns:
        Scenario with dual monitors (96 and 144 DPI)
    """
    return Scenario(
        id="integration_multi_monitor_scenario",
        window_x=0,
        window_y=0,
        window_width=1920,
        window_height=1080,
        game_area_x=0,
        game_area_y=0,
        game_area_width=1920,
        game_area_height=1080,
        dpi=96,
        monitors=[
            MonitorConfig(id=0, width=1920, height=1080, dpi=96, offset_x=0, offset_y=0),
            MonitorConfig(id=1, width=2560, height=1440, dpi=144, offset_x=1920, offset_y=0),
        ],
        chat_state=ChatState.CLOSED,
        timer_seconds=300,
        click_jitter_ms=0,
        timer_jitter_ms=0,
        glitch_type=GlitchType.NONE,
    )


@pytest.fixture
def clipped_scenario() -> Scenario:
    """Provide a clipped window test scenario.
    
    Returns:
        Scenario with 800x600 window (clipped)
    """
    return Scenario(
        id="integration_clipped_scenario",
        window_x=100,
        window_y=100,
        window_width=800,
        window_height=600,
        game_area_x=100,
        game_area_y=100,
        game_area_width=800,
        game_area_height=600,
        dpi=96,
        monitors=[MonitorConfig(id=0, width=1920, height=1080, dpi=96)],
        chat_state=ChatState.CLOSED,
        timer_seconds=300,
        click_jitter_ms=0,
        timer_jitter_ms=0,
        glitch_type=GlitchType.NONE,
    )


@pytest.fixture
def fixtures_exist(
    bot_config,
    window_context,
    mock_screen_renderer,
    macro_engine,
    game_state_simulator,
    mock_bot_runner,
    test_scenario,
) -> bool:
    """Verify that all required fixtures exist and are properly initialized.
    
    Returns:
        True if all fixtures are properly set up
    """
    assert bot_config is not None
    assert window_context is not None
    assert window_context.width == 1024
    assert window_context.height == 768
    assert mock_screen_renderer is not None
    assert macro_engine is not None
    assert game_state_simulator is not None
    assert mock_bot_runner is not None
    assert test_scenario is not None
    assert test_scenario.id == "integration_test_scenario"
    return True



@pytest.fixture
def screen_capture_mock(screen_renderer_fixture, game_state_simulator_fixture) -> MagicMock:
    """Provide a mock ScreenCapture that returns synthetic frames.
    
    This fixture:
    - Returns synthetic frames from ScreenRenderer
    - Increments GameStateSimulator tick each call
    - Simulates real frame capture behavior
    
    Args:
        screen_renderer_fixture: ScreenRenderer for frame generation
        game_state_simulator_fixture: GameStateSimulator for state updates
    
    Returns:
        MagicMock with mocked get_frame() method
    """
    capture = MagicMock()
    
    def mock_get_frame(window_size=(1024, 768)) -> np.ndarray:
        """Mock frame capture returning synthetic frame."""
        # Tick game state
        game_state_simulator_fixture.tick()
        
        # Render frame from current state
        frame = screen_renderer_fixture.render(
            game_state_simulator_fixture, 
            window_size
        )
        
        return frame
    
    capture.get_frame = MagicMock(side_effect=mock_get_frame)
    capture.grab = MagicMock(side_effect=lambda: mock_get_frame())
    
    return capture


@pytest.fixture
def screen_renderer_fixture() -> ScreenRenderer:
    """Provide a ScreenRenderer for synthetic frame generation.
    
    Returns:
        ScreenRenderer instance (loads templates from test_data/)
    """
    # Get test_framework data directory
    test_framework_dir = Path(__file__).parent.parent / "test_framework"
    test_data_dir = test_framework_dir / "test_data"
    
    # Create test_data directory if it doesn't exist
    test_data_dir.mkdir(exist_ok=True)
    
    return ScreenRenderer(test_data_dir)


@pytest.fixture
def game_state_simulator_fixture(test_scenario) -> GameStateSimulator:
    """Provide a GameStateSimulator initialized with test scenario.
    
    Args:
        test_scenario: Scenario fixture for initialization
    
    Returns:
        GameStateSimulator instance
    """
    return GameStateSimulator(test_scenario)


@pytest.fixture
def mock_http_server_fixture(game_state_simulator_fixture) -> MockHTTPServer:
    """Provide a MockHTTPServer running in background thread.
    
    This fixture:
    - Starts MockHTTPServer with game_state_simulator
    - Runs on a free port (8889+)
    - Yields server instance
    - Stops server after test
    
    Args:
        game_state_simulator_fixture: GameStateSimulator to serve
    
    Yields:
        MockHTTPServer instance (running)
    """
    import time
    
    # Find a free port
    port = 8889
    server = MockHTTPServer(game_state_simulator_fixture, port=port)
    
    # Start server in background
    server.start()
    
    # Wait a bit for server to start
    time.sleep(0.1)
    
    yield server
    
    # Stop server after test
    server.stop()


@pytest.fixture
def cpu_profiler_fixture() -> CPUProfiler:
    """Provide a CPUProfiler instance for profiling tests.
    
    Returns:
        CPUProfiler with scalene disabled (for test speed)
    """
    # Create profiler without scalene for testing
    return CPUProfiler(enable_scalene=False)


@pytest.fixture
def metrics_collector_fixture(test_scenario, cpu_profiler_fixture) -> MetricsCollector:
    """Provide a MetricsCollector for measuring run metrics.
    
    Args:
        test_scenario: Scenario for context
        cpu_profiler_fixture: CPUProfiler for CPU profiling
    
    Returns:
        MetricsCollector instance
    """
    return MetricsCollector(test_scenario, cpu_profiler_fixture)


@pytest.fixture
def orchestrator_fixture():
    """Provide a Orchestrator with default configuration.
    
    Returns:
        Orchestrator instance
    """
    from mvp.tests.test_framework.orchestrator import Orchestrator, OrchestratorConfig
    from mvp.tests.test_framework.scenarios import ScenarioRandomizer
    
    config = OrchestratorConfig(
        max_runs=50,
        timeout_per_run=15.0,
        target_pass_rate=0.95,
        baseline_run_count=5,
        sampling_run_count=5,
        cpu_critical_threshold=5,
        min_pass_rate_before_sampling=0.95,
    )
    
    randomizer = ScenarioRandomizer()
    return Orchestrator(config, randomizer)


@pytest.fixture
def bot_runner_fixture(macro_engine, window_context) -> MagicMock:
    """Provide a BotRunner wrapper around MacroEngine.
    
    Args:
        macro_engine: MacroEngine instance
        window_context: Window context fixture
    
    Returns:
        BotRunner-like mock with dispatch_macro() method
    """
    runner = MagicMock()
    runner.macro_engine = macro_engine
    runner.window_context = window_context
    
    def dispatch_macro(macro_steps: list, timeout_s: float = 10.0) -> dict:
        """Dispatch macro execution."""
        return {
            "success": True,
            "steps_executed": len(macro_steps),
            "duration_ms": 1000.0,
        }
    
    runner.dispatch_macro = MagicMock(side_effect=dispatch_macro)
    runner.is_running = MagicMock(return_value=True)
    runner.start = MagicMock()
    runner.stop = MagicMock()
    
    return runner
