"""Macro recording and playback engine"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
from mvp.test.mock_game import MockGameProcess


@dataclass
class ClickWithTiming:
    """Click event with timing information"""
    x: int
    y: int
    timestamp: float
    button: str = "left"


@dataclass
class Macro:
    """Recorded macro with click sequence and timing info"""
    name: str
    clicks: List[Dict] = field(default_factory=list)
    click_timings: List[ClickWithTiming] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    total_duration: float = 0.0
    
    def get_click_count(self) -> int:
        return len(self.clicks)


class MacroEngine:
    """Record and playback click macros with timing"""
    
    def __init__(self):
        self.macros: Dict[str, Macro] = {}
        self.is_recording = False
        self.is_paused = False
        self.recording_start_time: float = 0.0
        self.pause_start_time: float = 0.0
        self.accumulated_pause_time: float = 0.0
        self.current_macro: Optional[Macro] = None
        self.recorded_clicks_during_session: List[ClickWithTiming] = []
    
    def start_recording(self, macro_name: str) -> None:
        """Start recording a new macro"""
        self.is_recording = True
        self.is_paused = False
        self.recording_start_time = time.time()
        self.accumulated_pause_time = 0.0
        self.recorded_clicks_during_session = []
        self.current_macro = Macro(name=macro_name)
    
    def record_click_during_session(self, x: int, y: int) -> None:
        """Record a click during recording session (called by tests/game)"""
        if not self.is_recording or self.is_paused:
            return
        
        click = ClickWithTiming(
            x=x,
            y=y,
            timestamp=time.time(),
            button="left"
        )
        self.recorded_clicks_during_session.append(click)
    
    def stop_recording(self, game: MockGameProcess) -> Macro:
        """Stop recording and save macro"""
        if not self.is_recording or self.current_macro is None:
            raise RuntimeError("Not currently recording")
        
        self.is_recording = False
        
        # Get clicks from game state (for backwards compatibility)
        recorded_clicks = game.state.get('clicks', [])
        
        # Use recorded clicks from session if available, otherwise from game state
        if self.recorded_clicks_during_session:
            # Convert session clicks to dict format and get timing
            clicks_list = []
            click_timings = []
            for click in self.recorded_clicks_during_session:
                clicks_list.append({
                    'x': click.x,
                    'y': click.y,
                    'down': True,
                    'button': click.button
                })
                click_timings.append(click)
            self.current_macro.clicks = clicks_list
            self.current_macro.click_timings = click_timings
            
            # Calculate timing from session
            if click_timings:
                self.current_macro.total_duration = (
                    click_timings[-1].timestamp - click_timings[0].timestamp
                )
        else:
            # Fallback: use game state clicks
            self.current_macro.clicks = recorded_clicks
            recording_end_time = time.time()
            self.current_macro.total_duration = (
                recording_end_time - self.recording_start_time - self.accumulated_pause_time
            )
        
        # Store macro
        macro = self.current_macro
        self.macros[macro.name] = macro
        self.current_macro = None
        
        return macro
    
    def pause_recording(self) -> None:
        """Pause macro recording"""
        if not self.is_recording:
            raise RuntimeError("Not currently recording")
        
        self.is_paused = True
        self.pause_start_time = time.time()
    
    def resume_recording(self) -> None:
        """Resume macro recording"""
        if not self.is_paused:
            raise RuntimeError("Not currently paused")
        
        if self.pause_start_time > 0:
            pause_duration = time.time() - self.pause_start_time
            self.accumulated_pause_time += pause_duration
        
        self.is_paused = False
    
    def playback_macro(
        self, macro_name: str, game: MockGameProcess, delay_multiplier: float = 1.0
    ) -> bool:
        """Playback a recorded macro"""
        if macro_name not in self.macros:
            raise ValueError(f"Macro '{macro_name}' not found")
        
        macro = self.macros[macro_name]
        
        # Use timing info if available, otherwise use fixed delays
        if macro.click_timings and len(macro.click_timings) > 1:
            # Playback with original timing
            base_time = macro.click_timings[0].timestamp
            for i, click_timing in enumerate(macro.click_timings):
                # Send click
                game.send_click(click_timing.x, click_timing.y)
                
                # Calculate delay to next click
                if i < len(macro.click_timings) - 1:
                    next_click_time = macro.click_timings[i + 1].timestamp
                    delay = (next_click_time - click_timing.timestamp) * delay_multiplier
                    if delay > 0:
                        time.sleep(delay)
        else:
            # Fallback: use simple timing
            if len(macro.clicks) < 2:
                # Single or no clicks - just replay
                for click in macro.clicks:
                    game.send_click(click['x'], click['y'])
            else:
                # Replay with fixed timing
                for click in macro.clicks:
                    game.send_click(click['x'], click['y'])
                    time.sleep(0.026 * delay_multiplier)  # 26ms base interval
        
        return True
    
    def get_macro(self, macro_name: str) -> Optional[Macro]:
        """Get a recorded macro by name"""
        return self.macros.get(macro_name)
    
    def list_macros(self) -> List[str]:
        """List all recorded macro names"""
        return list(self.macros.keys())
    
    def delete_macro(self, macro_name: str) -> bool:
        """Delete a recorded macro"""
        if macro_name in self.macros:
            del self.macros[macro_name]
            return True
        return False
    
    def clear_all_macros(self) -> None:
        """Clear all recorded macros"""
        self.macros.clear()
