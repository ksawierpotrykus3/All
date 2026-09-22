"""Shared types and contracts for the dashboard subsystem.

Defines Pydantic models for dashboard events, metric payloads, and
type aliases used across instrumentor, ws_emitter, and metric_writer.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    CONVERSATION_STARTED = "conversation:started"
    CONVERSATION_METRIC = "conversation:metric"
    CONVERSATION_COMPLETED = "conversation:completed"
    CONVERSATION_ERROR = "conversation:error"
    ACCOUNT_STATUS_CHANGE = "account:status_change"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RATE_LIMITED = "rate_limited"


class DashboardEvent(BaseModel):
    """Base event type emitted to the WebSocket/SSE endpoint."""

    type: EventType
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


class ConversationStartedData(BaseModel):
    id: str
    chat_id: str
    account_slot: int
    user_uuid: str
    model: str


class ConversationMetricData(BaseModel):
    id: str
    timestamp: float
    ttft_ms: float | None = None
    tokens_per_sec: float | None = None
    tokens_total: int = 0
    latency_ms: float | None = None
    events_count: int = 0


class ConversationCompletedData(BaseModel):
    id: str
    total_tokens: int | float
    duration_ms: int | float


class ConversationErrorData(BaseModel):
    id: str
    error_message: str
    total_tokens: int | float
    duration_ms: int | float


class AccountStatusChangeData(BaseModel):
    slot: int
    status: AccountStatus
    rate_limited_until: float | None = None


def emit_conversation_started(
    conv_id: str,
    chat_id: str,
    account_slot: int,
    user_uuid: str,
    model: str,
) -> DashboardEvent:
    return DashboardEvent(
        type=EventType.CONVERSATION_STARTED,
        data=ConversationStartedData(
            id=conv_id,
            chat_id=chat_id,
            account_slot=account_slot,
            user_uuid=user_uuid,
            model=model,
        ).model_dump(),
    )


def emit_conversation_metric(
    conv_id: str,
    timestamp: float,
    ttft_ms: float | None = None,
    tokens_per_sec: float | None = None,
    tokens_total: int = 0,
    latency_ms: float | None = None,
    events_count: int = 0,
) -> DashboardEvent:
    return DashboardEvent(
        type=EventType.CONVERSATION_METRIC,
        data=ConversationMetricData(
            id=conv_id,
            timestamp=timestamp,
            ttft_ms=ttft_ms,
            tokens_per_sec=tokens_per_sec,
            tokens_total=tokens_total,
            latency_ms=latency_ms,
            events_count=events_count,
        ).model_dump(),
    )


def emit_conversation_completed(
    conv_id: str,
    total_tokens: int,
    duration_ms: int,
) -> DashboardEvent:
    return DashboardEvent(
        type=EventType.CONVERSATION_COMPLETED,
        data=ConversationCompletedData(
            id=conv_id,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        ).model_dump(),
    )


def emit_conversation_error(
    conv_id: str,
    error_message: str,
    total_tokens: int,
    duration_ms: int,
) -> DashboardEvent:
    return DashboardEvent(
        type=EventType.CONVERSATION_ERROR,
        data=ConversationErrorData(
            id=conv_id,
            error_message=error_message,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        ).model_dump(),
    )


def emit_account_status_change(
    slot: int,
    status: str,
    rate_limited_until: float | None = None,
) -> DashboardEvent:
    return DashboardEvent(
        type=EventType.ACCOUNT_STATUS_CHANGE,
        data=AccountStatusChangeData(
            slot=slot,
            status=AccountStatus(status),
            rate_limited_until=rate_limited_until,
        ).model_dump(),
    )
