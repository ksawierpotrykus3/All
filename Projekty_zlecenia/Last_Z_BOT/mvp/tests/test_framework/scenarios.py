"""Scenario definitions and randomizer for test framework."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
import random


class ChatState(Enum):
    """Chat window state."""

    CLOSED = "closed"
    OPEN = "open"
    SCROLLED = "scrolled"


class GlitchType(Enum):
    """Frame glitch type."""

    NONE = "none"
    FRAME_DROP_AT_5 = "frame_drop_at_5"
    FRAME_DROP_AT_50 = "frame_drop_at_50"


@dataclass
class MonitorConfig:
    """Single monitor configuration."""

    id: int
    width: int
    height: int
    dpi: int
    offset_x: int = 0
    offset_y: int = 0


@dataclass
class Scenario:
    """Test scenario configuration."""

    id: str
    # Window geometry
    window_x: int
    window_y: int
    window_width: int
    window_height: int
    # Game area position and size
    game_area_x: int
    game_area_y: int
    game_area_width: int
    game_area_height: int
    # DPI and monitor
    dpi: int
    monitors: list[MonitorConfig] = field(default_factory=list)
    # Game state
    chat_state: ChatState = ChatState.CLOSED
    timer_seconds: int = 300
    # Input jitter
    click_jitter_ms: int = 0
    timer_jitter_ms: int = 0
    # Glitches
    glitch_type: GlitchType = GlitchType.NONE

    @property
    def monitor_count(self) -> int:
        """Return number of monitors."""
        return len(self.monitors) if self.monitors else 1

    @property
    def is_multi_monitor(self) -> bool:
        """Return True if multi-monitor setup."""
        return len(self.monitors) > 1

    @property
    def is_offscreen(self) -> bool:
        """Return True if window is offscreen or partially offscreen."""
        return (
            self.window_x < 0
            or self.window_y < 0
            or self.window_x + self.window_width > 5000
            or self.window_y + self.window_height > 5000
        )

    @property
    def is_clipped(self) -> bool:
        """Return True if window is smaller than 1024x768."""
        return self.window_width < 1024 or self.window_height < 768


class ScenarioRandomizer:
    """Generate random test scenarios."""

    POSITIONS = [
        (0, 0),  # Top-left
        (960, 540),  # Center (relative to 1920x1080)
        (1920, 1080),  # Far right/bottom
        (-100, -100),  # Offscreen
    ]

    SIZES = [
        (800, 600),
        (1024, 768),
        (1280, 720),
        (1920, 1080),
        (640, 480),
        (2560, 1440),
    ]

    DPIS = [96, 120, 144]

    CHAT_STATES = [ChatState.CLOSED, ChatState.OPEN, ChatState.SCROLLED]

    TIMERS = [5, 30, 300]

    JITTERS = [0, 50, 500]

    GLITCHES = [GlitchType.NONE, GlitchType.FRAME_DROP_AT_5, GlitchType.FRAME_DROP_AT_50]

    def __init__(self, seed: int | None = None) -> None:
        """Initialize randomizer with optional seed."""
        if seed is not None:
            random.seed(seed)

    def next_scenario(self) -> Scenario:
        """Generate next random scenario."""
        position = random.choice(self.POSITIONS)
        size = random.choice(self.SIZES)
        dpi = random.choice(self.DPIS)
        chat_state = random.choice(self.CHAT_STATES)
        timer = random.choice(self.TIMERS)
        click_jitter = random.choice(self.JITTERS)
        timer_jitter = random.choice(self.JITTERS)
        glitch = random.choice(self.GLITCHES)

        # Determine monitors config
        multi_monitor = random.choice([True, False])
        monitors = self._generate_monitor_config(dpi, multi_monitor)

        scenario_id = (
            f"scenario_{position}_{size}_{dpi}dpi_{chat_state.value}"
            f"_{timer}s_{random.randint(0, 9999)}"
        )

        return Scenario(
            id=scenario_id,
            window_x=position[0],
            window_y=position[1],
            window_width=size[0],
            window_height=size[1],
            game_area_x=position[0],
            game_area_y=position[1],
            game_area_width=size[0],
            game_area_height=size[1],
            dpi=dpi,
            monitors=monitors,
            chat_state=chat_state,
            timer_seconds=timer,
            click_jitter_ms=click_jitter,
            timer_jitter_ms=timer_jitter,
            glitch_type=glitch,
        )

    def predefined_scenarios(self) -> list[Scenario]:
        """Return list of predefined key scenarios."""
        scenarios = []

        # Scenario 1: Standard full-size single monitor
        scenarios.append(
            Scenario(
                id="predefined_standard_full",
                window_x=0,
                window_y=0,
                window_width=1920,
                window_height=1080,
                game_area_x=0,
                game_area_y=0,
                game_area_width=1920,
                game_area_height=1080,
                dpi=96,
                monitors=[MonitorConfig(id=0, width=1920, height=1080, dpi=96)],
                chat_state=ChatState.CLOSED,
                timer_seconds=300,
                click_jitter_ms=0,
                timer_jitter_ms=0,
                glitch_type=GlitchType.NONE,
            )
        )

        # Scenario 2: Small clipped window
        scenarios.append(
            Scenario(
                id="predefined_clipped_small",
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
        )

        # Scenario 3: Dual monitor same DPI
        scenarios.append(
            Scenario(
                id="predefined_dual_same_dpi",
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
                    MonitorConfig(id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0),
                ],
                chat_state=ChatState.CLOSED,
                timer_seconds=300,
                click_jitter_ms=0,
                timer_jitter_ms=0,
                glitch_type=GlitchType.NONE,
            )
        )

        # Scenario 4: Dual monitor different DPI
        scenarios.append(
            Scenario(
                id="predefined_dual_diff_dpi",
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
        )

        # Scenario 5: Offscreen window
        scenarios.append(
            Scenario(
                id="predefined_offscreen",
                window_x=-100,
                window_y=-100,
                window_width=1024,
                window_height=768,
                game_area_x=-100,
                game_area_y=-100,
                game_area_width=1024,
                game_area_height=768,
                dpi=96,
                monitors=[MonitorConfig(id=0, width=1920, height=1080, dpi=96)],
                chat_state=ChatState.CLOSED,
                timer_seconds=300,
                click_jitter_ms=0,
                timer_jitter_ms=0,
                glitch_type=GlitchType.NONE,
            )
        )

        # Scenario 6: Chat open with jitter
        scenarios.append(
            Scenario(
                id="predefined_chat_open_jitter",
                window_x=0,
                window_y=0,
                window_width=1920,
                window_height=1080,
                game_area_x=0,
                game_area_y=0,
                game_area_width=1920,
                game_area_height=1080,
                dpi=96,
                monitors=[MonitorConfig(id=0, width=1920, height=1080, dpi=96)],
                chat_state=ChatState.OPEN,
                timer_seconds=30,
                click_jitter_ms=50,
                timer_jitter_ms=50,
                glitch_type=GlitchType.NONE,
            )
        )

        # Scenario 7: High DPI (144 DPI)
        scenarios.append(
            Scenario(
                id="predefined_high_dpi",
                window_x=0,
                window_y=0,
                window_width=1920,
                window_height=1080,
                game_area_x=0,
                game_area_y=0,
                game_area_width=1920,
                game_area_height=1080,
                dpi=144,
                monitors=[MonitorConfig(id=0, width=2560, height=1440, dpi=144)],
                chat_state=ChatState.CLOSED,
                timer_seconds=300,
                click_jitter_ms=0,
                timer_jitter_ms=0,
                glitch_type=GlitchType.NONE,
            )
        )

        # Scenario 8: Frame drop glitch
        scenarios.append(
            Scenario(
                id="predefined_frame_drop_glitch",
                window_x=0,
                window_y=0,
                window_width=1920,
                window_height=1080,
                game_area_x=0,
                game_area_y=0,
                game_area_width=1920,
                game_area_height=1080,
                dpi=96,
                monitors=[MonitorConfig(id=0, width=1920, height=1080, dpi=96)],
                chat_state=ChatState.CLOSED,
                timer_seconds=300,
                click_jitter_ms=0,
                timer_jitter_ms=0,
                glitch_type=GlitchType.FRAME_DROP_AT_5,
            )
        )

        return scenarios

    @staticmethod
    def _generate_monitor_config(dpi: int, multi_monitor: bool) -> list[MonitorConfig]:
        """Generate monitor configuration."""
        if not multi_monitor:
            return [MonitorConfig(id=0, width=1920, height=1080, dpi=dpi)]

        # Multi-monitor: either same or different DPI
        if random.choice([True, False]):
            # Dual same DPI
            return [
                MonitorConfig(id=0, width=1920, height=1080, dpi=dpi, offset_x=0, offset_y=0),
                MonitorConfig(id=1, width=1920, height=1080, dpi=dpi, offset_x=1920, offset_y=0),
            ]
        else:
            # Dual different DPI
            other_dpi = random.choice([d for d in ScenarioRandomizer.DPIS if d != dpi])
            return [
                MonitorConfig(id=0, width=1920, height=1080, dpi=dpi, offset_x=0, offset_y=0),
                MonitorConfig(id=1, width=2560, height=1440, dpi=other_dpi, offset_x=1920, offset_y=0),
            ]
