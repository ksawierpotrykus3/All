
from __future__ import annotations

import logging
import winsound

logger = logging.getLogger(__name__)


def notify_alert(enabled: bool = True, sound_path: str = "") -> None:
    if not enabled:
        return
    if sound_path:
        try:
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception as exc:
            logger.warning("Failed to play sound %s: %s", sound_path, exc)
    winsound.MessageBeep(winsound.MB_ICONASTERISK)
