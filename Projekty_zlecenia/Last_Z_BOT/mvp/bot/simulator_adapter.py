"""Adapter connecting GameSimulator to BotRunner for testing"""
from pathlib import Path
from typing import Optional
import threading
import queue

from mvp.tests.game_window.simulator_window import GameSimulatorWindow


class SimulatorAdapter:
    """Provides game window simulation for bot testing"""
    
    def __init__(self, data_dir: Path = Path("data/macro_testing")):
        self.simulator = GameSimulatorWindow(data_dir=data_dir)
        self.frame_queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread = None
        
    def get_current_frame(self):
        return self.simulator.get_current_frame()
    
    def trigger_alert(self):
        self.simulator.trigger_alert()
    
    def dismiss_alert(self):
        self.simulator.dismiss_alert()
        
    def set_timer(self, seconds: float):
        self.simulator.set_timer(seconds)
    
    def start_streaming(self):
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_frames, daemon=True)
        self._thread.start()
    
    def _stream_frames(self):
        import time
        while not self._stop_event.is_set():
            frame = self.simulator.get_current_frame()
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass
            time.sleep(0.016)
    
    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.simulator.stop()
