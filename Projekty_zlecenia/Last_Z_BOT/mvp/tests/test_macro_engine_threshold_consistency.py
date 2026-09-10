"""P1-7: AGENTS.md §9 — unified timer-jump threshold constant.

Before this change, ``calculate_avg_delta`` used a literal ``>2.0`` and the
two ``_handle_watch_timer`` paths used a literal ``>last_known_value + 3``.
These three sites MUST now share ``_JUMP_DETECTION_THRESHOLD_S = 2.0`` so
the bot treats refund events, helicopter exits, and OCR misreads the same
way everywhere.
"""

from __future__ import annotations

import inspect

from mvp.bot import macro_engine as me


def test_jump_detection_constant_is_exported() -> None:
    """The constant MUST be exposed at module level with the agreed value."""
    assert hasattr(me, "_JUMP_DETECTION_THRESHOLD_S"), (
        "macro_engine must export _JUMP_DETECTION_THRESHOLD_S (AGENTS.md §9)"
    )
    assert me._JUMP_DETECTION_THRESHOLD_S == 2.0


def test_calculate_avg_delta_uses_constant() -> None:
    """``calculate_avg_delta`` MUST filter jumps using the same constant.

    Feed a history with a 5-second timer drop (clearly above the 2.0 s
    threshold) and verify it is skipped (the function returns the safe
    default ``1.0`` instead of a contaminated average).
    """
    history = [
        {"value": 100, "time": 0.0},
        {"value": 99, "time": 1.0},   # 1 s timer drop in 1 s → 1.0 sec/sec
        {"value": 98, "time": 2.0},   # 1 s timer drop in 1 s → 1.0 sec/sec
        {"value": 90, "time": 3.0},   # 8 s timer drop in 1 s → SKIP (jump)
        {"value": 89, "time": 4.0},   # 1 s timer drop in 1 s → 1.0 sec/sec
    ]
    avg = me.calculate_avg_delta(history)
    # Only three valid deltas, all equal to 1.0; the 8-s jump is skipped.
    assert abs(avg - 1.0) < 1e-9, (
        f"calculate_avg_delta did not skip 8-s jump: avg={avg}"
    )


def test_calculate_avg_delta_all_jumps_returns_default() -> None:
    """If EVERY delta exceeds the threshold, MUST fall back to safe 1.0 default."""
    history = [
        {"value": 100, "time": 0.0},
        {"value": 50, "time": 1.0},   # 50-s jump
        {"value": 10, "time": 2.0},   # 40-s jump
    ]
    assert me.calculate_avg_delta(history) == 1.0


def test_calculate_avg_delta_exactly_at_threshold_is_kept() -> None:
    """A jump EQUAL to the threshold (2.0) is NOT skipped — strict ``>``."""
    history = [
        {"value": 100, "time": 0.0},
        {"value": 98, "time": 1.0},   # exactly 2.0 s drop → KEPT (boundary)
    ]
    avg = me.calculate_avg_delta(history)
    # 1.0 / 2.0 = 0.5 sec/sec — this delta is included.
    assert abs(avg - 0.5) < 1e-9, (
        f"calculate_avg_delta must keep the boundary case (avg={avg})"
    )


def test_calculate_avg_delta_short_history_returns_default() -> None:
    """Empty / single-entry history MUST return the 1.0 safe default."""
    assert me.calculate_avg_delta([]) == 1.0
    assert me.calculate_avg_delta([{"value": 10, "time": 0.0}]) == 1.0


def test_watch_timer_jump_path_uses_same_threshold() -> None:
    """Static check: both branches in ``_handle_watch_timer`` reference the constant."""
    src = inspect.getsource(me.MacroEngine._handle_watch_timer)
    assert src.count("_JUMP_DETECTION_THRESHOLD_S") >= 2, (
        "_handle_watch_timer must reference _JUMP_DETECTION_THRESHOLD_S in both "
        "idle and fast branches (got fewer than 2 references)"
    )


def test_calculate_avg_delta_source_uses_constant() -> None:
    """Static check: ``calculate_avg_delta`` MUST use the constant, not a magic number.

    We strip comments + docstrings so the historical mention in the
    docstring ("jumps |delta|>2.0s") doesn't trip the assertion.
    """
    src = inspect.getsource(me.calculate_avg_delta)
    assert "_JUMP_DETECTION_THRESHOLD_S" in src, (
        "calculate_avg_delta should reference the constant for consistency"
    )
    # Make sure the old magic-number ``> 2.0`` is no longer hard-coded
    # in executable code (docstring mention is fine).
    code_only = _strip_docstrings_and_comments(src)
    assert "> 2.0" not in code_only and ">2.0" not in code_only.replace(" ", ""), (
        "calculate_avg_delta still contains the magic literal '> 2.0' in code"
    )


def _strip_docstrings_and_comments(src: str) -> str:
    """Best-effort strip of triple-quoted strings and ``#`` comments for static checks."""
    import re

    src = re.sub(r'\"\"\"[\s\S]*?\"\"\"', "", src)
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    src = re.sub(r"#.*", "", src)
    return src


def test_no_magic_threshold_3_in_watch_timer() -> None:
    """Static check: ``+ 3`` magic-number MUST be gone from ``_handle_watch_timer``."""
    src = inspect.getsource(me.MacroEngine._handle_watch_timer)
    assert "+ 3" not in src, (
        "_handle_watch_timer still has the legacy '+ 3' literal threshold "
        "— both branches must use _JUMP_DETECTION_THRESHOLD_S instead"
    )


def test_threshold_constant_is_positive_float() -> None:
    """Type check — the constant MUST be a positive float."""
    val = me._JUMP_DETECTION_THRESHOLD_S
    assert isinstance(val, float), f"_JUMP_DETECTION_THRESHOLD_S must be a float, got {type(val)}"
    assert val > 0.0
    assert val < 60.0, "threshold seems unreasonably large for a 1-Hz countdown"
