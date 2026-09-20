"""Tests for dashboard contracts module."""

import pytest
from datetime import datetime

from server.dashboard.contracts import (
    DashboardEvent,
    EventType,
    AccountStatus,
    ConversationStartedData,
    ConversationMetricData,
    ConversationCompletedData,
    ConversationErrorData,
    AccountStatusChangeData,
    emit_conversation_started,
    emit_conversation_metric,
    emit_conversation_completed,
    emit_conversation_error,
    emit_account_status_change,
)


class TestEventType:
    def test_event_types_are_strings(self):
        assert EventType.CONVERSATION_STARTED == "conversation:started"
        assert EventType.CONVERSATION_METRIC == "conversation:metric"
        assert EventType.CONVERSATION_COMPLETED == "conversation:completed"
        assert EventType.CONVERSATION_ERROR == "conversation:error"
        assert EventType.ACCOUNT_STATUS_CHANGE == "account:status_change"

    def test_all_event_types_present(self):
        expected = {
            "conversation:started",
            "conversation:metric",
            "conversation:completed",
            "conversation:error",
            "account:status_change",
        }
        assert set(e.value for e in EventType) == expected


class TestAccountStatus:
    def test_statuses_are_strings(self):
        assert AccountStatus.ACTIVE == "active"
        assert AccountStatus.INACTIVE == "inactive"
        assert AccountStatus.RATE_LIMITED == "rate_limited"


class TestDashboardEvent:
    def test_base_event_has_required_fields(self):
        event = DashboardEvent(type=EventType.CONVERSATION_STARTED, data={"id": "abc"})
        assert event.type == EventType.CONVERSATION_STARTED
        assert event.data == {"id": "abc"}
        assert isinstance(event.timestamp, float)


class TestEmitFunctions:
    def test_emit_conversation_started(self):
        event = emit_conversation_started("conv1", "chat1", 0, "user1", "deepseek-v4-pro")
        assert event.type == EventType.CONVERSATION_STARTED
        assert event.data["id"] == "conv1"
        assert event.data["chat_id"] == "chat1"
        assert event.data["account_slot"] == 0
        assert event.data["user_uuid"] == "user1"
        assert event.data["model"] == "deepseek-v4-pro"

    def test_emit_conversation_metric(self):
        event = emit_conversation_metric("conv1", 1000.0, ttft_ms=50.0, tokens_total=100)
        assert event.type == EventType.CONVERSATION_METRIC
        assert event.data["id"] == "conv1"
        assert event.data["timestamp"] == 1000.0
        assert event.data["ttft_ms"] == 50.0
        assert event.data["tokens_total"] == 100

    def test_emit_conversation_metric_defaults(self):
        event = emit_conversation_metric("conv1", 1000.0)
        assert event.data["ttft_ms"] is None
        assert event.data["tokens_total"] == 0
        assert event.data["tokens_per_sec"] is None
        assert event.data["latency_ms"] is None
        assert event.data["events_count"] == 0

    def test_emit_conversation_completed(self):
        event = emit_conversation_completed("conv1", 100, 5000)
        assert event.type == EventType.CONVERSATION_COMPLETED
        assert event.data["id"] == "conv1"
        assert event.data["total_tokens"] == 100
        assert event.data["duration_ms"] == 5000

    def test_emit_conversation_error(self):
        event = emit_conversation_error("conv1", "timeout", 50, 2000)
        assert event.type == EventType.CONVERSATION_ERROR
        assert event.data["id"] == "conv1"
        assert event.data["error_message"] == "timeout"
        assert event.data["total_tokens"] == 50
        assert event.data["duration_ms"] == 2000

    def test_emit_account_status_change(self):
        event = emit_account_status_change(1, "rate_limited", rate_limited_until=1234567890.0)
        assert event.type == EventType.ACCOUNT_STATUS_CHANGE
        assert event.data["slot"] == 1
        assert event.data["status"] == "rate_limited"
        assert event.data["rate_limited_until"] == 1234567890.0

    def test_emit_account_status_change_no_rate_limit(self):
        event = emit_account_status_change(0, "active")
        assert event.data["status"] == "active"
        assert event.data["rate_limited_until"] is None


class TestInstrumentorIntegration:
    def test_instrumentor_on_conversation_started(self):
        from server.dashboard.instrumentor import DashboardInstrumentor
        from unittest.mock import MagicMock

        writer = MagicMock()
        instr = DashboardInstrumentor(writer=writer)
        instr.on_conversation_started("conv1", "chat1", 0, "user1", "deepseek-v4-pro")

        writer.insert_conversation.assert_called_once_with("conv1", "chat1", 0, "user1", "deepseek-v4-pro")
        writer.update_account_status.assert_called_once_with(0, "active")
        writer.increment_account_conversations.assert_called_once_with(0)

    def test_instrumentor_on_metric(self):
        from server.dashboard.instrumentor import DashboardInstrumentor
        from unittest.mock import MagicMock

        writer = MagicMock()
        instr = DashboardInstrumentor(writer=writer)
        instr.on_metric("conv1", 1000.0, ttft_ms=50.0, tokens_total=100)

        writer.insert_metric.assert_called_once()

    def test_instrumentor_on_conversation_error(self):
        from server.dashboard.instrumentor import DashboardInstrumentor
        from unittest.mock import MagicMock

        writer = MagicMock()
        instr = DashboardInstrumentor(writer=writer)
        instr.on_conversation_error("conv1", "timeout", 50, 2000)

        writer.finalize_conversation.assert_called_once_with("conv1", 50, 2000, "timeout")
        writer.insert_anomaly.assert_called_once()
