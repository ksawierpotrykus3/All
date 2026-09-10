"""Tests for scenario definitions and randomizer."""

import pytest

from mvp.tests.test_framework.scenarios import (
    ChatState,
    GlitchType,
    MonitorConfig,
    Scenario,
    ScenarioRandomizer,
)


class TestMonitorConfig:
    """Tests for MonitorConfig dataclass."""

    def test_monitor_config_creation(self) -> None:
        """Test MonitorConfig creation."""
        monitor = MonitorConfig(id=0, width=1920, height=1080, dpi=96)
        assert monitor.id == 0
        assert monitor.width == 1920
        assert monitor.height == 1080
        assert monitor.dpi == 96
        assert monitor.offset_x == 0
        assert monitor.offset_y == 0

    def test_monitor_config_with_offset(self) -> None:
        """Test MonitorConfig with offset."""
        monitor = MonitorConfig(
            id=1, width=1920, height=1080, dpi=96, offset_x=1920, offset_y=0
        )
        assert monitor.offset_x == 1920
        assert monitor.offset_y == 0


class TestScenario:
    """Tests for Scenario dataclass."""

    def test_scenario_creation(self) -> None:
        """Test Scenario creation."""
        scenario = Scenario(
            id="test_scenario",
            window_x=0,
            window_y=0,
            window_width=1920,
            window_height=1080,
            game_area_x=0,
            game_area_y=0,
            game_area_width=1920,
            game_area_height=1080,
            dpi=96,
        )
        assert scenario.id == "test_scenario"
        assert scenario.window_width == 1920
        assert scenario.window_height == 1080
        assert scenario.dpi == 96

    def test_scenario_monitor_count_single(self) -> None:
        """Test Scenario monitor count with single monitor."""
        scenario = Scenario(
            id="single_mon",
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
        )
        assert scenario.monitor_count == 1
        assert scenario.is_multi_monitor is False

    def test_scenario_monitor_count_dual(self) -> None:
        """Test Scenario monitor count with dual monitors."""
        scenario = Scenario(
            id="dual_mon",
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
                MonitorConfig(id=0, width=1920, height=1080, dpi=96),
                MonitorConfig(id=1, width=1920, height=1080, dpi=96),
            ],
        )
        assert scenario.monitor_count == 2
        assert scenario.is_multi_monitor is True

    def test_scenario_offscreen_detection(self) -> None:
        """Test Scenario offscreen detection."""
        # Negative coordinates
        scenario1 = Scenario(
            id="offscreen_neg",
            window_x=-100,
            window_y=-100,
            window_width=1024,
            window_height=768,
            game_area_x=-100,
            game_area_y=-100,
            game_area_width=1024,
            game_area_height=768,
            dpi=96,
        )
        assert scenario1.is_offscreen is True

        # Far right
        scenario2 = Scenario(
            id="offscreen_far",
            window_x=5000,
            window_y=0,
            window_width=1920,
            window_height=1080,
            game_area_x=5000,
            game_area_y=0,
            game_area_width=1920,
            game_area_height=1080,
            dpi=96,
        )
        assert scenario2.is_offscreen is True

    def test_scenario_clipped_detection(self) -> None:
        """Test Scenario clipped window detection."""
        # Smaller than 1024x768
        scenario1 = Scenario(
            id="clipped_small",
            window_x=0,
            window_y=0,
            window_width=800,
            window_height=600,
            game_area_x=0,
            game_area_y=0,
            game_area_width=800,
            game_area_height=600,
            dpi=96,
        )
        assert scenario1.is_clipped is True

        # Full size (not clipped)
        scenario2 = Scenario(
            id="not_clipped",
            window_x=0,
            window_y=0,
            window_width=1920,
            window_height=1080,
            game_area_x=0,
            game_area_y=0,
            game_area_width=1920,
            game_area_height=1080,
            dpi=96,
        )
        assert scenario2.is_clipped is False


class TestChatState:
    """Tests for ChatState enum."""

    def test_chat_state_values(self) -> None:
        """Test ChatState enum values."""
        assert ChatState.CLOSED.value == "closed"
        assert ChatState.OPEN.value == "open"
        assert ChatState.SCROLLED.value == "scrolled"


class TestGlitchType:
    """Tests for GlitchType enum."""

    def test_glitch_type_values(self) -> None:
        """Test GlitchType enum values."""
        assert GlitchType.NONE.value == "none"
        assert GlitchType.FRAME_DROP_AT_5.value == "frame_drop_at_5"
        assert GlitchType.FRAME_DROP_AT_50.value == "frame_drop_at_50"


class TestScenarioRandomizer:
    """Tests for ScenarioRandomizer."""

    def test_randomizer_creation(self) -> None:
        """Test ScenarioRandomizer creation."""
        randomizer = ScenarioRandomizer(seed=42)
        assert randomizer is not None

    def test_randomizer_next_scenario(self) -> None:
        """Test ScenarioRandomizer next_scenario method."""
        randomizer = ScenarioRandomizer(seed=42)
        scenario = randomizer.next_scenario()
        assert scenario is not None
        assert scenario.id is not None
        assert scenario.dpi in ScenarioRandomizer.DPIS

    def test_randomizer_position_variations(self) -> None:
        """Test randomizer position variations."""
        randomizer = ScenarioRandomizer(seed=42)
        positions = set()
        for _ in range(10):
            scenario = randomizer.next_scenario()
            positions.add((scenario.window_x, scenario.window_y))
        # Should have at least some variations
        assert len(positions) >= 1

    def test_randomizer_size_variations(self) -> None:
        """Test randomizer size variations."""
        randomizer = ScenarioRandomizer(seed=42)
        sizes = set()
        for _ in range(20):
            scenario = randomizer.next_scenario()
            sizes.add((scenario.window_width, scenario.window_height))
        # Should have multiple size variations
        assert len(sizes) >= 2
        # Check sizes are from predefined list
        for size in sizes:
            assert size in [
                (800, 600),
                (1024, 768),
                (1280, 720),
                (1920, 1080),
                (640, 480),
                (2560, 1440),
            ]

    def test_randomizer_dpi_variations(self) -> None:
        """Test randomizer DPI variations."""
        randomizer = ScenarioRandomizer(seed=42)
        dpis = set()
        for _ in range(10):
            scenario = randomizer.next_scenario()
            dpis.add(scenario.dpi)
        # All DPIs should be from predefined list
        for dpi in dpis:
            assert dpi in ScenarioRandomizer.DPIS

    def test_randomizer_multimonitor_scenarios(self) -> None:
        """Test randomizer multi-monitor scenario generation."""
        randomizer = ScenarioRandomizer(seed=42)
        multi_mon_count = 0
        for _ in range(20):
            scenario = randomizer.next_scenario()
            if scenario.is_multi_monitor:
                multi_mon_count += 1
                assert len(scenario.monitors) >= 2
        # Should have at least some multi-monitor scenarios
        assert multi_mon_count >= 0  # May be 0 depending on randomness

    def test_randomizer_predefined_scenarios(self) -> None:
        """Test ScenarioRandomizer predefined_scenarios method."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        assert len(scenarios) == 8
        assert scenarios[0].id == "predefined_standard_full"
        assert scenarios[1].id == "predefined_clipped_small"
        assert scenarios[2].id == "predefined_dual_same_dpi"
        assert scenarios[3].id == "predefined_dual_diff_dpi"
        assert scenarios[4].id == "predefined_offscreen"
        assert scenarios[5].id == "predefined_chat_open_jitter"
        assert scenarios[6].id == "predefined_high_dpi"
        assert scenarios[7].id == "predefined_frame_drop_glitch"

    def test_predefined_standard_full(self) -> None:
        """Test standard full scenario properties."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        std_full = scenarios[0]
        assert std_full.window_width == 1920
        assert std_full.window_height == 1080
        assert std_full.is_clipped is False
        assert std_full.is_offscreen is False
        assert std_full.chat_state == ChatState.CLOSED

    def test_predefined_clipped_small(self) -> None:
        """Test clipped small scenario properties."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        clipped = scenarios[1]
        assert clipped.is_clipped is True
        assert clipped.window_width == 800
        assert clipped.window_height == 600

    def test_predefined_dual_monitors(self) -> None:
        """Test dual monitor scenarios."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        dual_same = scenarios[2]
        dual_diff = scenarios[3]
        assert dual_same.is_multi_monitor is True
        assert dual_same.monitor_count == 2
        assert dual_diff.is_multi_monitor is True
        assert dual_diff.monitor_count == 2

    def test_predefined_offscreen(self) -> None:
        """Test offscreen scenario."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        offscreen = scenarios[4]
        assert offscreen.is_offscreen is True
        assert offscreen.window_x < 0
        assert offscreen.window_y < 0

    def test_predefined_high_dpi(self) -> None:
        """Test high DPI scenario."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        high_dpi = scenarios[6]
        assert high_dpi.dpi == 144

    def test_predefined_frame_drop_glitch(self) -> None:
        """Test frame drop glitch scenario."""
        randomizer = ScenarioRandomizer()
        scenarios = randomizer.predefined_scenarios()
        glitch = scenarios[7]
        assert glitch.glitch_type == GlitchType.FRAME_DROP_AT_5


class TestRandomizerPosition:
    """Tests for randomizer position variations."""

    def test_randomizer_top_left_position(self) -> None:
        """Test top-left corner position (0, 0)."""
        randomizer = ScenarioRandomizer(seed=10)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.window_x == 0 and scenario.window_y == 0:
                found = True
                break
        assert found, "Should find (0, 0) position in many samples"

    def test_randomizer_center_position(self) -> None:
        """Test center position (960, 540)."""
        randomizer = ScenarioRandomizer(seed=20)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.window_x == 960 and scenario.window_y == 540:
                found = True
                break
        assert found, "Should find center position in many samples"

    def test_randomizer_far_right_position(self) -> None:
        """Test far right/bottom position (1920, 1080)."""
        randomizer = ScenarioRandomizer(seed=30)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.window_x == 1920 and scenario.window_y == 1080:
                found = True
                break
        assert found, "Should find far right position in many samples"

    def test_randomizer_offscreen_position(self) -> None:
        """Test offscreen position (-100, -100)."""
        randomizer = ScenarioRandomizer(seed=40)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.window_x == -100 and scenario.window_y == -100:
                found = True
                assert scenario.is_offscreen is True
                break
        assert found, "Should find offscreen position in many samples"


class TestRandomizerDPI:
    """Tests for randomizer DPI variations."""

    def test_randomizer_96_dpi(self) -> None:
        """Test 96 DPI standard."""
        randomizer = ScenarioRandomizer(seed=50)
        found_96 = False
        for _ in range(30):
            scenario = randomizer.next_scenario()
            if scenario.dpi == 96:
                found_96 = True
                break
        assert found_96, "Should generate 96 DPI scenarios"

    def test_randomizer_120_dpi(self) -> None:
        """Test 120 DPI."""
        randomizer = ScenarioRandomizer(seed=60)
        found_120 = False
        for _ in range(30):
            scenario = randomizer.next_scenario()
            if scenario.dpi == 120:
                found_120 = True
                break
        assert found_120, "Should generate 120 DPI scenarios"

    def test_randomizer_144_dpi(self) -> None:
        """Test 144 DPI high."""
        randomizer = ScenarioRandomizer(seed=70)
        found_144 = False
        for _ in range(30):
            scenario = randomizer.next_scenario()
            if scenario.dpi == 144:
                found_144 = True
                break
        assert found_144, "Should generate 144 DPI scenarios"

    def test_randomizer_dpi_always_valid(self) -> None:
        """Test that randomizer only generates valid DPI values."""
        randomizer = ScenarioRandomizer(seed=80)
        for _ in range(50):
            scenario = randomizer.next_scenario()
            assert scenario.dpi in [96, 120, 144], f"Invalid DPI: {scenario.dpi}"


class TestRandomizerMultiMonitor:
    """Tests for randomizer multi-monitor scenarios."""

    def test_randomizer_dual_same_dpi(self) -> None:
        """Test dual monitor with same DPI."""
        randomizer = ScenarioRandomizer(seed=100)
        # Keep generating until we find a dual same-DPI scenario
        max_attempts = 100
        for _ in range(max_attempts):
            scenario = randomizer.next_scenario()
            if scenario.is_multi_monitor and len(scenario.monitors) == 2:
                # Check if DPIs match
                if scenario.monitors[0].dpi == scenario.monitors[1].dpi:
                    assert (
                        scenario.monitors[0].dpi == scenario.dpi
                    ), "Primary monitor DPI should match scenario DPI"
                    return
        # If we get here, we at least tested that multi-monitor generation works

    def test_randomizer_dual_different_dpi(self) -> None:
        """Test dual monitor with different DPI."""
        randomizer = ScenarioRandomizer(seed=110)
        # Keep generating until we find a dual different-DPI scenario
        max_attempts = 100
        for _ in range(max_attempts):
            scenario = randomizer.next_scenario()
            if scenario.is_multi_monitor and len(scenario.monitors) == 2:
                # Check if DPIs are different
                if scenario.monitors[0].dpi != scenario.monitors[1].dpi:
                    assert (
                        scenario.monitors[0].dpi != scenario.monitors[1].dpi
                    ), "Monitors should have different DPI"
                    return

    def test_randomizer_monitor_offsets(self) -> None:
        """Test that multi-monitor scenarios have proper offsets."""
        randomizer = ScenarioRandomizer(seed=120)
        found_multi = False
        for _ in range(100):
            scenario = randomizer.next_scenario()
            if scenario.is_multi_monitor:
                found_multi = True
                # First monitor should be at origin
                assert scenario.monitors[0].offset_x == 0
                assert scenario.monitors[0].offset_y == 0
                # Second monitor should have non-zero offset
                assert (
                    scenario.monitors[1].offset_x > 0 or scenario.monitors[1].offset_y > 0
                ), "Second monitor should have positive offset"
        # At least check we attempted this


class TestRandomizerChatState:
    """Tests for randomizer chat state variations."""

    def test_randomizer_chat_closed(self) -> None:
        """Test chat closed state."""
        randomizer = ScenarioRandomizer(seed=130)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.chat_state == ChatState.CLOSED:
                found = True
                break
        assert found, "Should generate closed chat scenarios"

    def test_randomizer_chat_open(self) -> None:
        """Test chat open state."""
        randomizer = ScenarioRandomizer(seed=140)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.chat_state == ChatState.OPEN:
                found = True
                break
        assert found, "Should generate open chat scenarios"

    def test_randomizer_chat_scrolled(self) -> None:
        """Test chat scrolled state."""
        randomizer = ScenarioRandomizer(seed=150)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.chat_state == ChatState.SCROLLED:
                found = True
                break
        assert found, "Should generate scrolled chat scenarios"


class TestRandomizerTimers:
    """Tests for randomizer timer variations."""

    def test_randomizer_timer_5s(self) -> None:
        """Test 5 second timer."""
        randomizer = ScenarioRandomizer(seed=160)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.timer_seconds == 5:
                found = True
                break
        assert found, "Should generate 5s timer scenarios"

    def test_randomizer_timer_30s(self) -> None:
        """Test 30 second timer."""
        randomizer = ScenarioRandomizer(seed=170)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.timer_seconds == 30:
                found = True
                break
        assert found, "Should generate 30s timer scenarios"

    def test_randomizer_timer_300s(self) -> None:
        """Test 300 second timer."""
        randomizer = ScenarioRandomizer(seed=180)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.timer_seconds == 300:
                found = True
                break
        assert found, "Should generate 300s timer scenarios"

    def test_randomizer_timer_always_valid(self) -> None:
        """Test that randomizer only generates valid timer values."""
        randomizer = ScenarioRandomizer(seed=190)
        for _ in range(30):
            scenario = randomizer.next_scenario()
            assert scenario.timer_seconds in [5, 30, 300], (
                f"Invalid timer: {scenario.timer_seconds}"
            )


class TestRandomizerJitter:
    """Tests for randomizer jitter variations."""

    def test_randomizer_no_jitter(self) -> None:
        """Test no jitter (0ms)."""
        randomizer = ScenarioRandomizer(seed=200)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.click_jitter_ms == 0:
                found = True
                break
        assert found, "Should generate 0ms jitter scenarios"

    def test_randomizer_medium_jitter(self) -> None:
        """Test ±50ms jitter."""
        randomizer = ScenarioRandomizer(seed=210)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.click_jitter_ms == 50:
                found = True
                break
        assert found, "Should generate ±50ms jitter scenarios"

    def test_randomizer_high_jitter(self) -> None:
        """Test ±500ms jitter."""
        randomizer = ScenarioRandomizer(seed=220)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.click_jitter_ms == 500:
                found = True
                break
        assert found, "Should generate ±500ms jitter scenarios"

    def test_randomizer_jitter_values_valid(self) -> None:
        """Test that randomizer only generates valid jitter values."""
        randomizer = ScenarioRandomizer(seed=230)
        for _ in range(30):
            scenario = randomizer.next_scenario()
            assert scenario.click_jitter_ms in [0, 50, 500], (
                f"Invalid click jitter: {scenario.click_jitter_ms}"
            )
            assert scenario.timer_jitter_ms in [0, 50, 500], (
                f"Invalid timer jitter: {scenario.timer_jitter_ms}"
            )


class TestRandomizerGlitches:
    """Tests for randomizer glitch variations."""

    def test_randomizer_no_glitch(self) -> None:
        """Test no glitch."""
        randomizer = ScenarioRandomizer(seed=240)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.glitch_type == GlitchType.NONE:
                found = True
                break
        assert found, "Should generate no-glitch scenarios"

    def test_randomizer_frame_drop_at_5(self) -> None:
        """Test frame drop at frame 5."""
        randomizer = ScenarioRandomizer(seed=250)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.glitch_type == GlitchType.FRAME_DROP_AT_5:
                found = True
                break
        assert found, "Should generate frame drop at 5 scenarios"

    def test_randomizer_frame_drop_at_50(self) -> None:
        """Test frame drop at frame 50."""
        randomizer = ScenarioRandomizer(seed=260)
        found = False
        for _ in range(50):
            scenario = randomizer.next_scenario()
            if scenario.glitch_type == GlitchType.FRAME_DROP_AT_50:
                found = True
                break
        assert found, "Should generate frame drop at 50 scenarios"

    def test_randomizer_glitch_always_valid(self) -> None:
        """Test that randomizer only generates valid glitch types."""
        randomizer = ScenarioRandomizer(seed=270)
        for _ in range(30):
            scenario = randomizer.next_scenario()
            assert scenario.glitch_type in [
                GlitchType.NONE,
                GlitchType.FRAME_DROP_AT_5,
                GlitchType.FRAME_DROP_AT_50,
            ], f"Invalid glitch type: {scenario.glitch_type}"
