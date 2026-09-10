
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class HotkeyError(Exception):
    pass


_MODIFIER_ALIASES: dict[str, str] = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "win",
    "super": "win",
    "cmd": "win",
    "meta": "win",
}

_VALID_MODIFIERS: set[str] = set(_MODIFIER_ALIASES.values())

_FUNCTION_KEYS: set[str] = {f"f{n}" for n in range(1, 13)}
_SPECIAL_KEYS: set[str] = {
    "escape",
    "esc",
    "space",
    "enter",
    "return",
    "tab",
    "backspace",
    "delete",
    "del",
    "home",
    "end",
    "pageup",
    "page_up",
    "pagedown",
    "page_down",
    "up",
    "down",
    "left",
    "right",
}

_VALID_SIMPLE_KEYS: set[str] = set()
for _c in range(ord("a"), ord("z") + 1):
    _VALID_SIMPLE_KEYS.add(chr(_c))
for _c in range(ord("0"), ord("9") + 1):
    _VALID_SIMPLE_KEYS.add(chr(_c))

_VALID_KEYS: set[str] = _VALID_SIMPLE_KEYS | _FUNCTION_KEYS | _SPECIAL_KEYS

_KEY_DISPLAY: dict[str, str] = {
    "escape": "Escape",
    "esc": "Escape",
    "space": "Space",
    "enter": "Enter",
    "return": "Enter",
    "tab": "Tab",
    "backspace": "Backspace",
    "delete": "Delete",
    "del": "Delete",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "page_up": "PageUp",
    "pagedown": "PageDown",
    "page_down": "PageDown",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}

_MODIFIER_DISPLAY: dict[str, str] = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
}


@dataclass(frozen=True)
class HotkeyConfig:

    keys: tuple[str, ...]
    modifiers: tuple[str, ...] = field(default_factory=tuple)

    def to_unique(self) -> tuple[frozenset[str], frozenset[str]]:
        return frozenset(self.modifiers), frozenset(self.keys)




def parse_hotkey_string(text: str) -> HotkeyConfig:
    if not text or not text.strip():
        raise HotkeyError("Empty hotkey")
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        raise HotkeyError("Empty hotkey after normalization")
    if len(parts) > 5:
        raise HotkeyError("Too many segments (max 5: 4 modifiers + 1 key)")
    mods: list[str] = []
    keys: list[str] = []
    for p in parts:
        if p in _MODIFIER_ALIASES:
            canon = _MODIFIER_ALIASES[p]
            if canon in mods:
                raise HotkeyError(f"Duplicate modifier: {p}")
            mods.append(canon)
        elif p in _VALID_KEYS:
            if keys:
                raise HotkeyError(
                    f"Multiple keys ({', '.join(keys)} + {p}) — only one is allowed."
                )
            keys.append(p)
        else:
            raise HotkeyError(f"Unknown key/modifier: {p!r}")
    if not keys:
        raise HotkeyError("Missing main key (e.g. 'k', 'f5', 'escape')")
    return HotkeyConfig(keys=tuple(keys), modifiers=tuple(mods))




def format_hotkey(hk: HotkeyConfig) -> str:
    parts: list[str] = []
    for mod in ("ctrl", "alt", "shift", "win"):
        if mod in hk.modifiers:
            parts.append(_MODIFIER_DISPLAY[mod])
    for key in hk.keys:
        if key in _KEY_DISPLAY:
            parts.append(_KEY_DISPLAY[key])
        elif key in _FUNCTION_KEYS:
            parts.append(key.upper())
        else:
            parts.append(key.upper())
    return "+".join(parts)




def validate_hotkey(hk: HotkeyConfig) -> list[str]:
    errors: list[str] = []
    if not hk.keys:
        errors.append("Hotkey must have at least one main key.")
    if len(hk.keys) > 1:
        errors.append(
            f"Hotkey can have only one main key, "
            f"got {len(hk.keys)}: {', '.join(hk.keys)}."
        )
    for mod in hk.modifiers:
        if mod not in _VALID_MODIFIERS:
            errors.append(f"Unknown modifier: {mod!r}.")
    for key in hk.keys:
        if key in _MODIFIER_ALIASES.values():
            errors.append(f"Main key cannot be only a modifier: {key!r}.")
        if key not in _VALID_KEYS:
            errors.append(f"Invalid key: {key!r}.")
    if len(hk.modifiers) > 4:
        errors.append("Too many modifiers (max 4).")
    return errors




class HotkeyRegistry:

    def __init__(self) -> None:
        self._bindings: dict[str, HotkeyConfig] = {}
        self._by_key: dict[tuple[frozenset[str], frozenset[str]], str] = {}


    def __contains__(self, name: str) -> bool:
        return name in self._bindings

    def __len__(self) -> int:
        return len(self._bindings)

    def __iter__(self):
        return iter(self._bindings)


    def register(self, name: str, hk: HotkeyConfig) -> None:
        mods, keys = hk.to_unique()
        if (mods, keys) in self._by_key:
            existing_name = self._by_key[(mods, keys)]
            if existing_name != name:
                raise HotkeyError(
                    f"Hotkey {format_hotkey(hk)} is already assigned to "
                    f"{existing_name!r} — conflict with {name!r}."
                )
            return
        if name in self._bindings:
            old = self._bindings[name]
            old_mods, old_keys = old.to_unique()
            self._by_key.pop((old_mods, old_keys), None)
        self._bindings[name] = hk
        self._by_key[(mods, keys)] = name

    def unregister(self, name: str) -> None:
        if name not in self._bindings:
            return
        hk = self._bindings.pop(name)
        mods, keys = hk.to_unique()
        self._by_key.pop((mods, keys), None)


    def get(self, name: str) -> HotkeyConfig | None:
        return self._bindings.get(name)

    def list_bindings(self) -> list[str]:
        return list(self._bindings.keys())


__all__ = [
    "HotkeyConfig",
    "HotkeyError",
    "HotkeyRegistry",
    "format_hotkey",
    "parse_hotkey_string",
    "validate_hotkey",
]
