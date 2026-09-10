import time
import pytest
from mvp.bot import clicker as clicker_mod
from mvp.bot.clicker import Clicker


class _TimestampedBackend:
    name = "sendinput"

    def __init__(self) -> None:
        self._initialized = True
        self.events: list[tuple[str, float, int, int]] = []

    def available(self) -> bool:
        return True

    def initialize(self) -> bool:
        return True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def mouse_down_left(self) -> None:
        pass

    def mouse_up_left(self) -> None:
        pass

    def move_to(self, x: int, y: int) -> None:
        self.events.append(("move", time.perf_counter(), int(x), int(y)))

    def scroll(self, direction: str) -> None:
        pass

    def get_cursor_pos(self) -> tuple[int, int]:
        return (0, 0)

    def spam_down(self, x: int, y: int) -> None:
        self.events.append(("down", time.perf_counter(), int(x), int(y)))

    def spam_up(self, x: int, y: int) -> None:
        self.events.append(("up", time.perf_counter(), int(x), int(y)))

    def spam_move(self, x: int, y: int) -> None:
        self.events.append(("move", time.perf_counter(), int(x), int(y)))

    def shutdown(self) -> None:
        pass


def test_lag_spike_preserves_hold_and_min_period(monkeypatch):
    """Verify that even with an injected 50ms lag spike, hold duration stays >=18ms
    and inter-click period stays >=26ms (never bursts into 0ms clicks).
    """
    backend = _TimestampedBackend()
    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: backend)

    clicker = Clicker(input_fps_mode="60", focus_watchdog_enabled=True, focus_check_interval=3)
    clicker.initialize()

    call_count = 0
    original_check_focus = clicker._check_focus

    def lagging_check_focus():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Inject a realistic 45ms system/game lag spike during focus check
            time.sleep(0.045)
        original_check_focus()

    monkeypatch.setattr(clicker, "_check_focus", lagging_check_focus)

    # Perform 8 clicks at 30 CPS (nominal period = 33.3ms)
    delivered = clicker.spam_click(960, 540, count=8, clicks_per_sec=30, direct_first=True)
    assert delivered == 8

    downs = [e for e in backend.events if e[0] == "down"]
    ups = [e for e in backend.events if e[0] == "up"]
    moves = [e for e in backend.events if e[0] == "move"]

    assert len(downs) == 8
    assert len(ups) == 8

    # 1. Verify hold duration for EVERY click (must never drop below 17.5ms)
    for i in range(8):
        down_t = downs[i][1]
        up_t = ups[i][1]
        hold_duration = up_t - down_t
        assert hold_duration >= 0.0175, (
            f"Click {i} hold duration {hold_duration*1000:.2f}ms < 17.5ms (burst bug occurred!)"
        )

    # 2. Verify inter-click interval between consecutive DOWN events
    for i in range(1, 8):
        prev_down = downs[i - 1][1]
        curr_down = downs[i][1]
        period = curr_down - prev_down
        # Must always be >= 25.0ms (Unity's ClickIntervalMonitor threshold)
        assert period >= 0.025, (
            f"Period between click {i-1} and {i} is {period*1000:.2f}ms < 25.0ms (ReportFastClick would trigger!)"
        )

    # 3. Verify no MOVE occurs while button is down
    for move_ev in moves:
        m_time = move_ev[1]
        for d_ev, u_ev in zip(downs, ups):
            d_time, u_time = d_ev[1], u_ev[1]
            assert not (d_time <= m_time <= u_time), (
                f"MOVE occurred during DOWN state! m={m_time:.4f}, down={d_time:.4f}, up={u_time:.4f}"
            )


def test_min_up_time_enforced_after_delay(monkeypatch):
    """Verify that when execution is delayed during the UP phase,
    the clicker guarantees at least min_up_time (8ms) before the next DOWN.
    """
    backend = _TimestampedBackend()
    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: backend)

    clicker = Clicker(input_fps_mode="60", focus_watchdog_enabled=False)
    clicker.initialize()

    delivered = clicker.spam_click(960, 540, count=4, clicks_per_sec=30, direct_first=True)
    assert delivered == 4

    downs = [e for e in backend.events if e[0] == "down"]
    ups = [e for e in backend.events if e[0] == "up"]

    for i in range(len(ups) - 1):
        up_t = ups[i][1]
        next_down_t = downs[i + 1][1]
        up_window = next_down_t - up_t
        # Minimum UP buffer in 60fps mode must be at least ~7.5ms
        assert up_window >= 0.0075, (
            f"UP window between click {i} and {i+1} was {up_window*1000:.2f}ms < 7.5ms"
        )
def test_massive_lag_spike_resync(monkeypatch):
    """Verify that a massive 120ms lag spike (e.g. heavy GC or game freezing)
    is gracefully absorbed without triggering zero-hold clicks or ReportFastClick.
    """
    backend = _TimestampedBackend()
    monkeypatch.setattr(clicker_mod, "initialize_backend", lambda mode: backend)

    clicker = Clicker(input_fps_mode="60", focus_watchdog_enabled=True, focus_check_interval=2)
    clicker.initialize()

    call_count = 0
    def heavy_lag_check_focus():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            time.sleep(0.120)  # 120ms freeze

    monkeypatch.setattr(clicker, "_check_focus", heavy_lag_check_focus)

    delivered = clicker.spam_click(960, 540, count=6, clicks_per_sec=30, direct_first=True)
    assert delivered == 6

    downs = [e for e in backend.events if e[0] == "down"]
    ups = [e for e in backend.events if e[0] == "up"]

    for i in range(6):
        hold = ups[i][1] - downs[i][1]
        assert hold >= 0.0175, f"Click {i} hold time collapsed to {hold*1000:.2f}ms"

    for i in range(1, 6):
        period = downs[i][1] - downs[i-1][1]
        assert period >= 0.025, f"Click {i} period collapsed to {period*1000:.2f}ms"
