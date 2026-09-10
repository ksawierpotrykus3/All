"""
Pytest fixtures for game simulator window integration tests.
"""
import time
from pathlib import Path

import numpy as np
import pytest

from mvp.bot.ocr import ChatOCR, TimerOCR
from mvp.tests.game_window.simulator_window import GameSimulatorWindow


@pytest.fixture
def game_window():
    if not (Path("data/macro_testing") / "no_chat.png").exists():
        pytest.skip("data/macro_testing assets not available")
    simulator = GameSimulatorWindow(data_dir=Path("data/macro_testing"))
    thread = simulator.run_async()
    # The render loop starts with a black frame and publishes the first real
    # frame ~16 ms later. Under full-suite CPU load that first publish can be
    # delayed, so wait until the initial black frame is gone instead of letting
    # tests race it.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if np.any(simulator.get_current_frame()):
            break
        time.sleep(0.005)
    yield simulator
    simulator.stop()
    thread.join(timeout=1.0)


@pytest.fixture
def game_state_monitor(game_window):
    class GameStateMonitor:
        def __init__(self, window):
            self.window = window
            self.state_history = []
            self.alert_history = []

        def record_state(self):
            state = self.window.get_state()
            self.state_history.append(state)
            return state

        def record_alert_trigger(self):
            self.window.trigger_alert()
            self.alert_history.append({"event": "trigger", "state": self.window.get_state()})

        def record_alert_dismiss(self):
            self.window.dismiss_alert()
            self.alert_history.append({"event": "dismiss", "state": self.window.get_state()})

        def assert_alert_triggered(self):
            assert any(h["event"] == "trigger" for h in self.alert_history)

        def assert_alert_dismissed(self):
            assert any(h["event"] == "dismiss" for h in self.alert_history)

        def get_timer_progression(self):
            return [s["timer_seconds"] for s in self.state_history]

    monitor = GameStateMonitor(game_window)
    yield monitor


@pytest.fixture
def bot_with_window(game_window):
    class MockBot:
        def __init__(self, window):
            self.window = window
            self.frame_captures = []
            self.ocr_results = []
            self.timer_ocr = TimerOCR()
            self.chat_ocr = ChatOCR()

        def capture_frame(self):
            frame = self.window.get_current_frame()
            self.frame_captures.append(frame)
            return frame

        def ocr(self, frame):
            timer_seconds = self.timer_ocr.read_timer(frame)
            result = (f"{timer_seconds}s", 0.95) if timer_seconds is not None else ("", 0.0)
            self.ocr_results.append(result)
            return result

        def find_helicopter_alert(self, frame):
            return self.chat_ocr.find_helicopter_alert(frame)

        def is_chat_open(self, frame):
            return self.chat_ocr.is_chat_window_open(frame)

        def click(self, x=500, y=400, times=1):
            pass

        def is_alert_active(self):
            return self.window.get_state()["alert_active"]

        def get_frame_count(self):
            return len(self.frame_captures)

    bot = MockBot(game_window)
    yield bot


@pytest.fixture(autouse=True)
def suppress_display(monkeypatch):
    import cv2
    original_namedWindow = cv2.namedWindow
    original_imshow = cv2.imshow
    original_destroyAllWindows = cv2.destroyAllWindows
    original_waitKey = cv2.waitKey

    def mock_namedWindow(*args, **kwargs):
        pass

    def mock_imshow(*args, **kwargs):
        pass

    def mock_destroyAllWindows(*args, **kwargs):
        pass

    def mock_waitKey(*args, **kwargs):
        return 255

    monkeypatch.setattr(cv2, "namedWindow", mock_namedWindow)
    monkeypatch.setattr(cv2, "imshow", mock_imshow)
    monkeypatch.setattr(cv2, "destroyAllWindows", mock_destroyAllWindows)
    monkeypatch.setattr(cv2, "waitKey", mock_waitKey)

    yield

    cv2.namedWindow = original_namedWindow
    cv2.imshow = original_imshow
    cv2.destroyAllWindows = original_destroyAllWindows
    cv2.waitKey = original_waitKey
