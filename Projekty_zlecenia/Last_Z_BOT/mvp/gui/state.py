
from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from queue import Queue

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GuiState:
    running: bool = False

    latest_frame: np.ndarray | None = field(default=None, repr=False)

    log_queue: Queue = field(default_factory=lambda: Queue(maxsize=500))

    frame_queue: Queue = field(default_factory=lambda: Queue(maxsize=2))

    ui_queue: Queue = field(default_factory=lambda: Queue(maxsize=500))

    def push_log(self, message: str) -> None:
        self._bounded_put(self.log_queue, message, "log")

    def push_ui(self, event: str, *args, **kwargs) -> None:
        self._bounded_put(self.ui_queue, (event, args, kwargs), "ui")

    @staticmethod
    def _bounded_put(q: Queue, item, kind: str) -> None:
        try:
            q.put_nowait(item)
        except Exception:
            # Queue full: drop the oldest item and retry once so the latest
            # event (e.g. phase_transition → notify) is not lost.
            with contextlib.suppress(Exception):
                q.get_nowait()
            try:
                q.put_nowait(item)
            except Exception:
                logger.warning("GuiState %s queue overflow; dropped message", kind)
