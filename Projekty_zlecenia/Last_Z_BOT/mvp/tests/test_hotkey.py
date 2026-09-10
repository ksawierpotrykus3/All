"""Tests for #19 — the hotkey configurator.

Architecture:
- ``HotkeyConfig`` — dataclass: ``keys: tuple[str, ...]``, ``modifiers: tuple[str, ...]``
- ``parse_hotkey_string("ctrl+shift+k") -> HotkeyConfig``
- ``format_hotkey(hk) -> "Ctrl+Shift+K"``
- ``validate_hotkey(hk) -> list[str]`` — a list of errors (empty = OK)
- ``HotkeyRegistry`` — detects conflicts between hotkeys

Validation:
- Allowed modifiers: ctrl/alt/shift/win/super
- Main key: letters A-Z, digits 0-9, F1-F12, special keys (escape/space/enter)
- Min 1 key, max 1 main key
- An empty modifier means only 1 key
- Conflict: two hotkeys with an identical ``(modifiers, keys)`` pair

Tests:
- ``tmp_path`` is NOT needed — pure logic only.
"""

from __future__ import annotations

import pytest

from mvp.bot.hotkey import (
    HotkeyConfig,
    HotkeyError,
    HotkeyRegistry,
    format_hotkey,
    parse_hotkey_string,
    validate_hotkey,
)

# ── HotkeyConfig ──────────────────────────────────────────────────


class TestHotkeyConfig:
    def test_construction(self):
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        assert hk.keys == ("k",)
        assert hk.modifiers == ("ctrl",)

    def test_construction_no_modifiers(self):
        hk = HotkeyConfig(keys=("escape",), modifiers=())
        assert hk.modifiers == ()

    def test_to_tuple_unique(self):
        """``to_unique()`` returns (frozenset of modifiers, frozenset of keys)."""
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl", "shift"))
        mods, keys = hk.to_unique()
        assert mods == frozenset({"ctrl", "shift"})
        assert keys == frozenset({"k"})

    def test_hashable(self):
        hk1 = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        hk2 = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        assert hash(hk1) == hash(hk2)
        assert hk1 == hk2

    def test_inequality(self):
        hk1 = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        hk2 = HotkeyConfig(keys=("j",), modifiers=("ctrl",))
        assert hk1 != hk2


# ── parse_hotkey_string ──────────────────────────────────────────


class TestParseHotkey:
    def test_single_key(self):
        hk = parse_hotkey_string("k")
        assert hk.keys == ("k",)
        assert hk.modifiers == ()

    def test_with_modifier(self):
        hk = parse_hotkey_string("ctrl+k")
        assert hk.keys == ("k",)
        assert hk.modifiers == ("ctrl",)

    def test_multiple_modifiers(self):
        hk = parse_hotkey_string("ctrl+shift+k")
        assert hk.keys == ("k",)
        assert hk.modifiers == ("ctrl", "shift")

    def test_case_insensitive(self):
        hk = parse_hotkey_string("CTRL+K")
        assert "ctrl" in hk.modifiers
        assert "k" in hk.keys

    def test_function_key(self):
        hk = parse_hotkey_string("ctrl+f5")
        assert hk.keys == ("f5",)
        assert hk.modifiers == ("ctrl",)

    def test_special_key(self):
        hk = parse_hotkey_string("escape")
        assert hk.keys == ("escape",)

    def test_empty_string_raises(self):
        with pytest.raises(HotkeyError):
            parse_hotkey_string("")

    def test_only_modifiers_raises(self):
        """Sam modyfikator bez klawisza → HotkeyError."""
        with pytest.raises(HotkeyError):
            parse_hotkey_string("ctrl+shift")

    def test_multiple_keys_raises(self):
        """Multiple keys (a+b) are not allowed."""
        with pytest.raises(HotkeyError):
            parse_hotkey_string("ctrl+k+j")

    def test_invalid_modifier_raises(self):
        with pytest.raises(HotkeyError):
            parse_hotkey_string("bogus+k")

    def test_whitespace_trimmed(self):
        hk = parse_hotkey_string("  ctrl + k  ")
        assert hk.modifiers == ("ctrl",)
        assert hk.keys == ("k",)


# ── format_hotkey ────────────────────────────────────────────────


class TestFormatHotkey:
    def test_format_simple(self):
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        assert format_hotkey(hk) == "Ctrl+K"

    def test_format_multiple_modifiers(self):
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl", "shift"))
        assert format_hotkey(hk) == "Ctrl+Shift+K"

    def test_format_no_modifier(self):
        hk = HotkeyConfig(keys=("escape",), modifiers=())
        assert format_hotkey(hk) == "Escape"

    def test_format_function_key(self):
        hk = HotkeyConfig(keys=("f5",), modifiers=("alt",))
        assert format_hotkey(hk) == "Alt+F5"


# ── validate_hotkey ──────────────────────────────────────────────


class TestValidateHotkey:
    def test_valid_returns_empty_list(self):
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        assert validate_hotkey(hk) == []

    def test_unknown_modifier(self):
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl", "bogus"))
        errors = validate_hotkey(hk)
        assert any("bogus" in e for e in errors)

    def test_empty_keys(self):
        hk = HotkeyConfig(keys=(), modifiers=("ctrl",))
        errors = validate_hotkey(hk)
        assert any("key" in e.lower() for e in errors)

    def test_too_many_keys(self):
        hk = HotkeyConfig(keys=("k", "j"), modifiers=("ctrl",))
        errors = validate_hotkey(hk)
        assert any("one" in e.lower() or "1" in e for e in errors)

    def test_modifier_as_key(self):
        """``ctrl`` as the main key (and nothing else) → error."""
        hk = HotkeyConfig(keys=("ctrl",), modifiers=())
        errors = validate_hotkey(hk)
        assert len(errors) > 0


# ── HotkeyRegistry ────────────────────────────────────────────────


class TestHotkeyRegistry:
    def test_register_ok(self):
        reg = HotkeyRegistry()
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        reg.register("start", hk)
        assert "start" in reg

    def test_register_conflict_raises(self):
        reg = HotkeyRegistry()
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        reg.register("start", hk)
        with pytest.raises(HotkeyError):
            reg.register("stop", hk)

    def test_register_different_no_conflict(self):
        reg = HotkeyRegistry()
        reg.register("start", HotkeyConfig(keys=("k",), modifiers=("ctrl",)))
        reg.register("stop", HotkeyConfig(keys=("j",), modifiers=("ctrl",)))
        assert "start" in reg
        assert "stop" in reg

    def test_unregister(self):
        reg = HotkeyRegistry()
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        reg.register("start", hk)
        reg.unregister("start")
        assert "start" not in reg

    def test_unregister_unknown_ok(self):
        """``unregister`` on a missing key — no-op."""
        reg = HotkeyRegistry()
        reg.unregister("doesnt_exist")

    def test_get_hotkey(self):
        reg = HotkeyRegistry()
        hk = HotkeyConfig(keys=("k",), modifiers=("ctrl",))
        reg.register("start", hk)
        assert reg.get("start") == hk

    def test_get_unknown_returns_none(self):
        reg = HotkeyRegistry()
        assert reg.get("missing") is None

    def test_list_bindings(self):
        reg = HotkeyRegistry()
        reg.register("a", HotkeyConfig(keys=("k",), modifiers=("ctrl",)))
        reg.register("b", HotkeyConfig(keys=("j",), modifiers=("ctrl",)))
        assert set(reg.list_bindings()) == {"a", "b"}


# ── HotkeyError ───────────────────────────────────────────────────


class TestHotkeyError:
    def test_is_exception(self):
        assert issubclass(HotkeyError, Exception)
