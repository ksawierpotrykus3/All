"""
Macro step event logger for test orchestration.

Logs macro steps in a format compatible with BotStepMonitor (C# test framework).
Format: MACRO_STEP: step=N, type=TYPE, status=STATUS, ...
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class MacroStepLogger:
    """Logs macro steps to a dedicated file for test monitoring."""

    def __init__(
        self,
        log_path: str | Path = "bot_macro.log",
        enabled: bool = True,
        flush_every_event: bool = False,
        flush_interval_s: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.log_path = Path(log_path)
        self.flush_every_event = flush_every_event
        self.flush_interval_s = max(0.0, float(flush_interval_s))
        self._lock = threading.Lock()
        self._fh = None
        self._buffer: list[str] = []
        self._last_flush = 0.0

    def _ensure_open(self) -> None:
        if self._fh is not None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.log_path.open("a", encoding="utf-8")

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        self._ensure_open()
        if self._fh is None:
            return
        self._fh.write("".join(self._buffer))
        self._fh.flush()
        self._buffer.clear()
        self._last_flush = time.monotonic()

    def log_step_event(
        self,
        step_num: int,
        step_type: str,
        status: str,
        latency_ms: int | None = None,
        cps: float | None = None,
        clicks: int | None = None,
        text: str | None = None,
        x: int | None = None,
        y: int | None = None,
        error: str | None = None,
    ) -> None:
        """
        Log a macro step event in C#-compatible format.

        Args:
            step_num: Step number (1-indexed)
            step_type: Step type (e.g., SCROLL_LISTEN_CHAT, CLICK, WAIT, WATCH_TIMER)
            status: Status (start, complete, error)
            latency_ms: Reaction latency in milliseconds (optional)
            cps: Clicks per second during spam (optional)
            clicks: Total clicks in this step (optional)
            text: Detected text (optional)
            x: Click X coordinate (optional)
            y: Click Y coordinate (optional)
            error: Error message (optional)
        """
        if not self.enabled:
            return

        # Build log line
        parts = [
            f"step={step_num}",
            f"type={step_type}",
            f"status={status}",
        ]

        if latency_ms is not None:
            parts.append(f"latency_ms={latency_ms}")
        if cps is not None:
            parts.append(f"cps={cps:.2f}")
        if clicks is not None:
            parts.append(f"clicks={clicks}")
        if text is not None:
            parts.append(f"text={text}")
        if x is not None and y is not None:
            parts.append(f"x={x}")
            parts.append(f"y={y}")
        if error is not None:
            parts.append(f"error={error}")

        log_line = f"MACRO_STEP: {', '.join(parts)}\n"

        with self._lock:
            self._buffer.append(log_line)
            try:
                if self.flush_every_event:
                    self._flush_locked()
                elif time.monotonic() - self._last_flush >= self.flush_interval_s:
                    self._flush_locked()
            except OSError as exc:
                logger.warning("MacroStepLogger.log_step_event() write failed (%s)", exc)

    def on_step_event(
        self, event: str, step_num: int, step, **kwargs
    ) -> None:
        """Handle step event callbacks from MacroEngine._emit()."""
        if not self.enabled:
            return

        step_type = str(getattr(step, "type", "UNKNOWN")).split(".")[-1]  # Extract enum name

        if event == "running":
            self.log_step_event(step_num, step_type, "start")
        elif event == "success":
            self.log_step_event(step_num, step_type, "complete")
        elif event == "error":
            error_msg = kwargs.get("error", "Unknown error")
            self.log_step_event(step_num, step_type, "error", error=error_msg)
        # phase_transition events are informational, not logged as step events

    def close(self) -> None:
        """Flush any buffered lines and close the underlying file handle."""
        with self._lock:
            try:
                self._flush_locked()
            except OSError as exc:
                logger.warning("MacroStepLogger.close() flush failed (%s)", exc)
            fh = self._fh
            self._fh = None
            if fh is not None:
                try:
                    fh.close()
                except OSError as exc:
                    logger.warning("MacroStepLogger.close() close failed (%s)", exc)