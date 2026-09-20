"""DashboardInstrumentor — bridges MetricWriter with WebSocket event emission."""

import asyncio
import time
from typing import Any

from server.dashboard.metric_writer import MetricWriter
from server.dashboard.ws_emitter import emit_event
from server.dashboard.contracts import (
    DashboardEvent,
    emit_conversation_started,
    emit_conversation_metric,
    emit_conversation_completed,
    emit_conversation_error,
    emit_account_status_change,
)
from server.logging import get_logger

logger = get_logger(__name__)


class DashboardInstrumentor:
    """High-level facade that combines metric persistence with live event
    emission via an asyncio queue.

    Every ``on_*`` method writes to the database through the shared
    ``MetricWriter`` and, where appropriate, enqueues a structured event
    dict on ``self._ws_queue`` for later consumption by a WebSocket
    endpoint.
    """

    def __init__(self, writer: MetricWriter | None = None) -> None:
        self._writer = writer or MetricWriter()
        self._ws_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Public event handlers
    # ------------------------------------------------------------------

    def on_conversation_started(
        self,
        conv_id: str,
        chat_id: str,
        account_slot: int,
        user_uuid: str,
        model: str,
    ) -> None:
        """Register a new conversation and mark the account slot as active.

        If another conversation already exists with the same *chat_id*,
        a ``chat_correlations`` link is created automatically so the
        dashboard can display these as a chronological thread.
        """
        self._writer.insert_conversation(conv_id, chat_id, account_slot, user_uuid, model)
        self._writer.increment_account_conversations(account_slot)
        self._writer.update_account_status(account_slot, "active")

        # ── Thread detection via chat_id ─────────────────────────────
        prev_id = self._writer.find_previous_conversation(chat_id)
        if prev_id is not None:
            # Compute depth: how many prior conversations share this chat_id
            depth = 0
            row = self._writer._get_conn().execute(
                "SELECT COUNT(*) FROM conversations WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            if row:
                depth = row[0] - 1  # 0-based: first child has depth 1
            self._writer.insert_correlation(
                correlation_key=chat_id,
                conversation_id=conv_id,
                parent_id=prev_id,
                label=f"continuation",
                depth=depth,
            )

        self._emit(emit_conversation_started(conv_id, chat_id, account_slot, user_uuid, model))

    def on_metric(
        self,
        conv_id: str,
        timestamp: float,
        ttft_ms: float | None = None,
        tokens_per_sec: float | None = None,
        tokens_total: int = 0,
        latency_ms: float | None = None,
        events_count: int = 0,
    ) -> None:
        """Persist a metric sample and push a live update."""
        self._writer.insert_metric(
            conv_id, timestamp,
            ttft_ms=ttft_ms,
            tokens_per_sec=tokens_per_sec,
            tokens_total=tokens_total,
            latency_ms=latency_ms,
            events_count=events_count,
        )

        self._emit(emit_conversation_metric(conv_id, timestamp, ttft_ms, tokens_per_sec, tokens_total, latency_ms, events_count))

    def on_conversation_completed(
        self,
        conv_id: str,
        total_tokens: int,
        duration_ms: int,
    ) -> None:
        """Mark a conversation as successfully completed."""
        self._writer.finalize_conversation(conv_id, total_tokens, duration_ms)

        self._emit(emit_conversation_completed(conv_id, total_tokens, duration_ms))

    def on_conversation_error(
        self,
        conv_id: str,
        error_message: str,
        total_tokens: int,
        duration_ms: int,
    ) -> None:
        """Mark a conversation as errored and record the anomaly."""
        self._writer.finalize_conversation(conv_id, total_tokens, duration_ms, error_message)
        self._writer.insert_anomaly(
            conv_id,
            type_="stream_error",
            severity="critical",
            message=error_message,
        )

        self._emit(emit_conversation_error(conv_id, error_message, total_tokens, duration_ms))

    def on_account_rate_limited(self, slot: int, until: float) -> None:
        """Mark an account as rate-limited and emit the status change."""
        self._writer.update_account_status(slot, "rate_limited", rate_limited_until=until)
        self._writer.insert_anomaly(
            None,
            type_="rate_limit",
            severity="warning",
            message=f"Account slot {slot} rate limited until {until}",
        )

        self._emit(emit_account_status_change(slot, "rate_limited", rate_limited_until=until))

    # ------------------------------------------------------------------
    # WebSocket event emission
    # ------------------------------------------------------------------

    def _emit(self, event: DashboardEvent | dict[str, Any]) -> None:
        """Enqueue a structured event for the WebSocket consumer.

        Also emits via the WS emitter for external dashboard connections.

        Uses ``loop.call_soon_threadsafe`` so this method is safe to call
        from any thread.  If the event loop is not available (e.g. during
        startup / testing) the event is silently dropped.
        """
        event_dict = event.model_dump() if hasattr(event, "model_dump") else event
        emit_event(event_dict)  # also emit via WS
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(self._ws_queue.put_nowait, event_dict)
        except RuntimeError:
            pass
