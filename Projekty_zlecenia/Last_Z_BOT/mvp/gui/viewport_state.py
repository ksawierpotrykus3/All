
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080

_OFFSCREEN_TOLERANCE = 20


@dataclass
class ViewportState:

    x: int = 100
    y: int = 100
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    maximized: bool = False


def save_viewport_state(path: Path | str, state: ViewportState) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(state)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_viewport_state(path: Path | str) -> ViewportState | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("load_viewport_state: read failed for %s: %s", path, exc)
        return None

    if not raw.strip():
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.debug("load_viewport_state: JSON decode failed for %s: %s", path, exc)
        return None

    if not isinstance(data, dict):
        return None

    required = ("x", "y", "width", "height", "maximized")
    if not all(key in data for key in required):
        return None

    try:
        return ViewportState(
            x=int(data["x"]),
            y=int(data["y"]),
            width=int(data["width"]),
            height=int(data["height"]),
            maximized=bool(data["maximized"]),
        )
    except (TypeError, ValueError) as exc:
        logger.debug("load_viewport_state: type mismatch in %s: %s", path, exc)
        return None


def validate_viewport_state(
    state: ViewportState,
    screen_width: int,
    screen_height: int,
) -> bool:
    if state.maximized:
        return True
    if state.width <= 0 or state.height <= 0:
        return False
    if screen_width <= 0 or screen_height <= 0:
        return False
    if state.x < -_OFFSCREEN_TOLERANCE:
        return False
    if state.y < -_OFFSCREEN_TOLERANCE:
        return False
    return (state.x + state.width) <= screen_width + _OFFSCREEN_TOLERANCE and (
        state.y + state.height
    ) <= screen_height + _OFFSCREEN_TOLERANCE
