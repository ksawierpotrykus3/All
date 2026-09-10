"""Tests for the pluggable input backend layer (mvp.bot.input).

These tests never emit real input: the SendInput backend is mocked at
the import boundaries.
"""

from __future__ import annotations

import pytest

from mvp.bot.clicker import Clicker
from mvp.bot.input import InputBackend, detect_backend, initialize_backend


class _StubBackend(InputBackend):
    name = "stub"

    def __init__(self, ok: bool = True) -> None:
        self._initialized = False
        self._ok = ok

    def available(self) -> bool:
        return self._ok

    def initialize(self) -> bool:
        if not self._ok:
            return False
        self._initialized = True
        return True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def mouse_down_left(self) -> None:
        pass

    def mouse_up_left(self) -> None:
        pass

    def move_to(self, x: int, y: int) -> None:
        pass

    def scroll(self, direction: str) -> None:
        pass

    def get_cursor_pos(self) -> tuple[int, int]:
        return (0, 0)

    def spam_down(self, x: int, y: int) -> None:
        pass

    def spam_up(self, x: int, y: int) -> None:
        pass

    def spam_move(self, x: int, y: int) -> None:
        pass

    def shutdown(self) -> None:
        self._initialized = False


def test_detect_backend_auto_uses_sendinput(monkeypatch):
    """auto resolves to the single SendInput backend."""
    from mvp.bot.input import backend as backend_mod

    order = (
        "mvp.bot.input.sendinput_backend:SendInputBackend",
    )
    seen = []

    def fake_import(qualname):
        seen.append(qualname)

        class _Available:
            def __init__(self):
                self.name = "sendinput"

            def available(self):
                return True

        return _Available

    monkeypatch.setattr(backend_mod, "BACKEND_ORDER", order)
    monkeypatch.setattr(backend_mod, "_import_backend", fake_import)

    backend = detect_backend("auto")
    assert backend is not None
    assert backend.name == "sendinput"
    assert seen == list(order)


def test_detect_backend_explicit(monkeypatch):
    from mvp.bot.input import backend as backend_mod

    monkeypatch.setattr(
        backend_mod,
        "BACKEND_BY_NAME",
        {"sendinput": "mod:Cls"},
    )
    monkeypatch.setattr(backend_mod, "_import_backend", lambda q: _StubBackend)

    backend = detect_backend("sendinput")
    assert backend is not None
    assert backend.name == "stub"


def test_detect_backend_unknown_mode_raises():
    with pytest.raises(ValueError):
        detect_backend("nonsense")


def test_initialize_backend_auto_prefers_first_available(monkeypatch):
    from mvp.bot.input import backend as backend_mod

    order = (
        "m1:BackendOne",
        "m2:SendInput",
    )
    monkeypatch.setattr(backend_mod, "BACKEND_ORDER", order)

    def fake_import(qualname):
        return _StubBackend

    monkeypatch.setattr(backend_mod, "_import_backend", fake_import)

    backend = initialize_backend("auto")
    assert backend is not None
    assert backend.is_initialized


def test_initialize_backend_auto_skips_failed_init(monkeypatch):
    from mvp.bot.input import backend as backend_mod

    order = ("m1:Broken", "m2:Good")
    monkeypatch.setattr(backend_mod, "BACKEND_ORDER", order)

    class Broken(_StubBackend):
        def initialize(self):
            return False

    def fake_import(qualname):
        return Broken if qualname == "m1:Broken" else _StubBackend

    monkeypatch.setattr(backend_mod, "_import_backend", fake_import)

    backend = initialize_backend("auto")
    assert backend is not None
    assert backend.name == "stub"
    assert backend.is_initialized


def test_clicker_raises_when_no_backend(monkeypatch):
    """Without any backend, spam_click must raise ClickerError (old contract)."""
    from mvp.bot.exceptions import ClickerError

    monkeypatch.setattr(Clicker, "initialize", lambda self: None)
    clicker = Clicker(input_backend="auto")
    clicker._backend = None

    with pytest.raises(ClickerError):
        clicker.spam_click(960, 520, count=1, direct_first=True)


def test_clicker_mode_forces_sendinput(monkeypatch):
    """input_backend='sendinput' must select SendInputBackend."""
    from mvp.bot.input import sendinput_backend

    def fake_initialize(self):
        # Simulate successful user-mode init without touching real WinAPI.
        self._initialized = True
        return True

    monkeypatch.setattr(sendinput_backend.SendInputBackend, "initialize", fake_initialize)
    # forcing sendinput must resolve through BACKEND_BY_NAME and return
    # the SendInputBackend class.
    clicker = Clicker(input_backend="sendinput")
    clicker.initialize()

    assert clicker.is_initialized
    assert type(clicker._backend).__name__ == "SendInputBackend"


def test_sendinput_backend_delivers_atomic_clicks(monkeypatch):
    """SendInput spam_down must atomically combine move, absolute, virtualdesk, and leftdown flags."""
    from mvp.bot.input.sendinput_backend import (
        MOUSEEVENTF_ABSOLUTE,
        MOUSEEVENTF_LEFTDOWN,
        MOUSEEVENTF_MOVE,
        MOUSEEVENTF_VIRTUALDESK,
        SendInputBackend,
    )

    backend = SendInputBackend()
    backend._initialized = True
    sent_inputs = []

    class FakeUser32:
        def GetSystemMetrics(self, idx):
            # Virtual screen: 0, 0, 1920, 1080
            metrics = {76: 0, 77: 0, 78: 1920, 79: 1080}
            return metrics.get(idx, 0)

        def SendInput(self, n, arr, sz):
            for i in range(n):
                inp = arr[i]
                sent_inputs.append((inp.union.mi.dwFlags, inp.union.mi.dx, inp.union.mi.dy))
            return n

    backend._user32 = FakeUser32()
    backend.spam_down(960, 540)

    assert len(sent_inputs) == 1
    flags, dx, dy = sent_inputs[0]
    # MOUSEEVENTF_MOVE must NOT be present during spam_down: movement during a press
    # cancels eligibleForClick in Unity and starts a camera drag (Delta r must be 0).
    expected_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTDOWN
    assert flags == expected_flags
    # 960/1920 * 65536 = 32768, 540/1080 * 65536 = 32768
    assert dx == 32768
    assert dy == 32768


def test_sendinput_backend_spam_up_preserves_coords():
    """spam_up must emit left up at the EXACT given coordinates (Delta r = 0)."""
    from mvp.bot.input.sendinput_backend import (
        MOUSEEVENTF_ABSOLUTE,
        MOUSEEVENTF_LEFTUP,
        MOUSEEVENTF_MOVE,
        MOUSEEVENTF_VIRTUALDESK,
        SendInputBackend,
    )

    backend = SendInputBackend()
    backend._initialized = True
    sent_inputs = []

    class FakeUser32:
        def GetSystemMetrics(self, idx):
            metrics = {76: 0, 77: 0, 78: 1920, 79: 1080}
            return metrics.get(idx, 0)

        def SendInput(self, n, arr, sz):
            for i in range(n):
                inp = arr[i]
                sent_inputs.append((inp.union.mi.dwFlags, inp.union.mi.dx, inp.union.mi.dy))
            return n

    backend._user32 = FakeUser32()
    backend.spam_up(960, 540)

    assert len(sent_inputs) == 1
    flags, dx, dy = sent_inputs[0]
    # UP must land at the EXACT same coordinates as DOWN (Delta r = 0), so no MOVE flag.
    expected_flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTUP
    assert flags == expected_flags
    assert dx == 32768
    assert dy == 32768


def test_sendinput_backend_multi_monitor_normalization():
    """Normalized coordinates must handle multi-monitor setups with negative coordinates."""
    from mvp.bot.input.sendinput_backend import SendInputBackend

    backend = SendInputBackend()
    backend._initialized = True

    class FakeUser32:
        def GetSystemMetrics(self, idx):
            # Virtual screen spanned over 2 monitors: left monitor (-1920, 0), right (0, 0)
            # Total width = 3840, v_left = -1920
            metrics = {76: -1920, 77: 0, 78: 3840, 79: 1080}
            return metrics.get(idx, 0)

    backend._user32 = FakeUser32()

    # Center of left monitor: x = -960, y = 540
    # ((-960 - (-1920)) * 65536) / 3840 = (960 * 65536) / 3840 = 16384 (1/4 of total virtual width)
    nx, ny = backend._to_normalized_coords(-960, 540)
    assert nx == 16384
    assert ny == 32768
