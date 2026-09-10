from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BUFFER = 5000
_DEFAULT_FLUSH_BACKOFF_S = 5.0


class EventLogger:

    def __init__(
        self,
        log_dir: str = "logs",
        enabled: bool = True,
        maxlen: int = _DEFAULT_MAX_BUFFER,
    ) -> None:
        self.enabled = enabled
        self._dir = Path(log_dir)
        if self.enabled:
            self._dir.mkdir(parents=True, exist_ok=True)
        self._buffer: deque[tuple[str, dict]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._flush_backoff_until: float = 0.0
        self._flush_failures = 0
        self._total_logged = 0
        self._logged_at_last_failure = 0

    def open_log_dir(self, open_in_explorer: bool = False) -> Path:
        if self._dir is None:
            raise ValueError("log_dir is not configured")

        resolved = self._dir.resolve()
        resolved.mkdir(parents=True, exist_ok=True)

        if open_in_explorer:
            try:
                os.startfile(str(resolved))
            except AttributeError:
                logger.debug("os.startfile unavailable — directory returned without opening")
            except OSError as exc:
                logger.warning(
                    "Failed to open the log directory in Explorer (%s); path: %s",
                    exc,
                    resolved,
                )
        return resolved

    def log(self, event: str, data: dict) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._buffer.append((event, data))
            self._total_logged += 1

    def flush(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            if not self._buffer:
                return
            # Backoff only suppresses re-writing the SAME content that failed.
            # If new events arrived since the last failure, retry immediately.
            if (
                self._flush_backoff_until
                and time.monotonic() < self._flush_backoff_until
                and self._total_logged == self._logged_at_last_failure
            ):
                return
            rows = list(self._buffer)
            self._buffer.clear()

        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / time.strftime("session_%Y%m%d.csv")
        new = not path.exists()

        try:
            with path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                if new:
                    writer.writerow(["ts", "event", "data"])
                for event, data in rows:
                    writer.writerow([time.time(), event, json.dumps(data, ensure_ascii=False)])
        except OSError as exc:
            logger.warning(
                "EventLogger.flush() write failed (%s) — %d events re-queued",
                exc,
                len(rows),
            )
            with self._lock:
                # Prepending in reverse keeps original order without O(n^2)
                # list concatenation (rows + buffer creates a brand-new list).
                self._buffer.extendleft(reversed(rows))
                self._flush_failures += 1
                self._flush_backoff_until = time.monotonic() + _DEFAULT_FLUSH_BACKOFF_S
                self._logged_at_last_failure = self._total_logged
        else:
            with self._lock:
                self._flush_failures = 0
                self._flush_backoff_until = 0.0