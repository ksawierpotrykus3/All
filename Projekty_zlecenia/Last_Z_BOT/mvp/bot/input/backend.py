
from __future__ import annotations

import contextlib
import importlib
from abc import ABC, abstractmethod

with contextlib.suppress(ImportError):
    import mvp.bot.input.sendinput_backend

BACKEND_ORDER: tuple[str, ...] = (
    "mvp.bot.input.sendinput_backend:SendInputBackend",
)

BACKEND_BY_NAME: dict[str, str] = {
    "sendinput": BACKEND_ORDER[0],
}


class InputBackend(ABC):

    name: str = "base"

    @abstractmethod
    def available(self) -> bool:
        pass

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        pass

    @abstractmethod
    def mouse_down_left(self) -> None:
        pass

    @abstractmethod
    def mouse_up_left(self) -> None:
        pass

    @abstractmethod
    def move_to(self, x: int, y: int) -> None:
        pass

    @abstractmethod
    def scroll(self, direction: str) -> None:
        pass

    @abstractmethod
    def get_cursor_pos(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def spam_down(self, x: int, y: int) -> None:
        pass

    @abstractmethod
    def spam_up(self, x: int, y: int) -> None:
        pass

    @abstractmethod
    def spam_move(self, x: int, y: int) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass


def _import_backend(qualname: str) -> type[InputBackend]:
    module_name, _, cls_name = qualname.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, cls_name)


def detect_backend(mode: str = "auto") -> InputBackend | None:
    if mode == "auto":
        for qualname in BACKEND_ORDER:
            try:
                cls = _import_backend(qualname)
            except Exception:
                continue
            backend = cls()
            if backend.available():
                return backend
        return None

    qualname = BACKEND_BY_NAME.get(mode)
    if qualname is None:
        raise ValueError(f"unknown input backend mode: {mode!r}")
    cls = _import_backend(qualname)
    return cls()


def initialize_backend(mode: str = "auto") -> InputBackend | None:
    if mode == "auto":
        for qualname in BACKEND_ORDER:
            try:
                cls = _import_backend(qualname)
            except Exception:
                continue
            backend = cls()
            if not backend.available():
                continue
            if backend.initialize():
                return backend
            backend.shutdown()
        return None

    backend = detect_backend(mode)
    if backend is None:
        return None
    if backend.initialize():
        return backend
    backend.shutdown()
    return None
