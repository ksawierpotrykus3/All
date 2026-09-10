"""AGENTS.md §2 input flag invariant — MOUSE_MOVE MUST NOT co-occur with LEFT buttons.

The Unity game engine treats ``MOUSEEVENTF_MOVE`` while the LEFT button is held
as a CAMERA DRAG gesture and sets ``eligibleForClick = false``. Therefore:

- ``spam_down``  MUST send ``MOUSEEVENTF_LEFTDOWN``      WITHOUT ``MOUSEEVENTF_MOVE``.
- ``spam_up``    MUST send ``MOUSEEVENTF_LEFTUP``        WITHOUT ``MOUSEEVENTF_MOVE``.
- ``spam_move``  MUST send ``MOUSEEVENTF_MOVE``           WITHOUT ``MOUSEEVENTF_LEFTDOWN`` / ``MOUSEEVENTF_LEFTUP``.
- All ``spam_*`` MUST use ``MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK`` so the
  coordinates are interpreted in the virtual-desktop space (Unity expects this).

These tests stub ``_send_fast`` (and the coord-normalization helper) to
record the exact ``dwFlags`` value passed to ``SendInput`` so the flag
combinations can be asserted statically.
"""

from __future__ import annotations

from mvp.bot.input.sendinput_backend import (
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MOVE,
    MOUSEEVENTF_VIRTUALDESK,
    SendInputBackend,
)


def _instrument_backend() -> tuple[SendInputBackend, list[int]]:
    """Create a SendInputBackend with ``_send_fast`` and coords stubbed.

    Returns ``(backend, captured_flags)``. ``captured_flags`` is a list of
    the integer ``dwFlags`` values that would have been sent via WinAPI.
    """
    backend = SendInputBackend()
    # Avoid the real ctypes path in _to_normalized_coords.
    backend._user32 = None  # type: ignore[assignment]
    backend._to_normalized_coords = lambda x, y: (int(x), int(y))  # type: ignore[assignment]
    captured: list[int] = []

    def fake_send_fast(flags: int, dx: int = 0, dy: int = 0, mouse_data: int = 0) -> int:
        captured.append(int(flags))
        return 1

    backend._send_fast = fake_send_fast  # type: ignore[assignment]
    return backend, captured


def test_spam_down_does_not_include_move_flag() -> None:
    """AGENTS.md §2: spam_down MUST NOT carry MOUSEEVENTF_MOVE."""
    backend, captured = _instrument_backend()
    backend.spam_down(100, 200)

    assert len(captured) == 1
    flags = captured[0]
    assert (flags & MOUSEEVENTF_MOVE) == 0, (
        f"spam_down MUST NOT set MOUSEEVENTF_MOVE (got flags=0x{flags:x})"
    )
    assert (flags & MOUSEEVENTF_LEFTDOWN) != 0, (
        f"spam_down MUST set MOUSEEVENTF_LEFTDOWN (got flags=0x{flags:x})"
    )


def test_spam_up_does_not_include_move_flag() -> None:
    """AGENTS.md §2: spam_up MUST NOT carry MOUSEEVENTF_MOVE."""
    backend, captured = _instrument_backend()
    backend.spam_up(100, 200)

    assert len(captured) == 1
    flags = captured[0]
    assert (flags & MOUSEEVENTF_MOVE) == 0, (
        f"spam_up MUST NOT set MOUSEEVENTF_MOVE (got flags=0x{flags:x})"
    )
    assert (flags & MOUSEEVENTF_LEFTUP) != 0, (
        f"spam_up MUST set MOUSEEVENTF_LEFTUP (got flags=0x{flags:x})"
    )


def test_spam_move_does_not_include_left_buttons() -> None:
    """AGENTS.md §2: spam_move MUST NOT carry LEFTDOWN or LEFTUP."""
    backend, captured = _instrument_backend()
    backend.spam_move(100, 200)

    assert len(captured) == 1
    flags = captured[0]
    assert (flags & MOUSEEVENTF_LEFTDOWN) == 0, (
        f"spam_move MUST NOT set MOUSEEVENTF_LEFTDOWN (got flags=0x{flags:x})"
    )
    assert (flags & MOUSEEVENTF_LEFTUP) == 0, (
        f"spam_move MUST NOT set MOUSEEVENTF_LEFTUP (got flags=0x{flags:x})"
    )
    assert (flags & MOUSEEVENTF_MOVE) != 0, (
        f"spam_move MUST set MOUSEEVENTF_MOVE (got flags=0x{flags:x})"
    )


def test_spam_down_and_up_use_absolute_virtual_desk() -> None:
    """AGENTS.md §2: All spam_* MUST use ABSOLUTE + VIRTUALDESK coordinates."""
    backend, captured = _instrument_backend()
    backend.spam_down(100, 200)
    backend.spam_up(100, 200)
    backend.spam_move(100, 200)

    assert len(captured) == 3
    for kind, flags in zip(("down", "up", "move"), captured, strict=False):
        assert (flags & MOUSEEVENTF_ABSOLUTE) != 0, (
            f"spam_{kind} MUST set MOUSEEVENTF_ABSOLUTE (got flags=0x{flags:x})"
        )
        assert (flags & MOUSEEVENTF_VIRTUALDESK) != 0, (
            f"spam_{kind} MUST set MOUSEEVENTF_VIRTUALDESK (got flags=0x{flags:x})"
        )


def test_click_at_down_up_consistency() -> None:
    """Sanity: click_at path's mouse_down_left / mouse_up_left use the same invariant."""
    backend, captured = _instrument_backend()
    backend.mouse_down_left()
    backend.mouse_up_left()

    assert len(captured) == 2
    down_flags, up_flags = captured
    assert (down_flags & MOUSEEVENTF_MOVE) == 0
    assert (up_flags & MOUSEEVENTF_MOVE) == 0
    assert (down_flags & MOUSEEVENTF_LEFTDOWN) != 0
    assert (up_flags & MOUSEEVENTF_LEFTUP) != 0


def test_no_down_up_event_combines_move_and_button() -> None:
    """A full spam cycle MUST NEVER combine MOUSEEVENTF_MOVE with LEFTDOWN/LEFTUP."""
    backend, captured = _instrument_backend()
    # 3-click spam cycle (down, up, move, down, up, move, down, up).
    backend.spam_down(100, 100)
    backend.spam_up(100, 100)
    backend.spam_move(110, 110)
    backend.spam_down(100, 100)
    backend.spam_up(100, 100)
    backend.spam_move(90, 90)
    backend.spam_down(100, 100)
    backend.spam_up(100, 100)

    assert len(captured) == 8
    for flags in captured:
        has_move = bool(flags & MOUSEEVENTF_MOVE)
        has_button = bool(flags & (MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP))
        assert not (has_move and has_button), (
            f"event with flags=0x{flags:x} illegally combines MOVE and button"
        )


def test_flag_constants_are_distinct() -> None:
    """Sanity: the flag constants MUST be distinct bits so masking is unambiguous."""
    bits = {
        "MOVE": MOUSEEVENTF_MOVE,
        "LEFTDOWN": MOUSEEVENTF_LEFTDOWN,
        "LEFTUP": MOUSEEVENTF_LEFTUP,
        "ABSOLUTE": MOUSEEVENTF_ABSOLUTE,
        "VIRTUALDESK": MOUSEEVENTF_VIRTUALDESK,
    }
    # All distinct (no two flags share the same bit).
    values = list(bits.values())
    assert len(set(values)) == len(values), f"duplicate flag bits: {bits}"
    # ABSOLUTE/VIRTUALDESK/MOVE/LEFTDOWN/LEFTUP must be non-zero.
    for name, value in bits.items():
        assert value != 0, f"{name} flag constant is zero"
