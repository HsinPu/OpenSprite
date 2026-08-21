"""Technology-neutral records owned by the conversation persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


ProviderId = Literal["openai", "anthropic", "openrouter"]
ResponseMode = Literal["default", "fast", "balanced", "deep"]
MessageRole = Literal["user", "assistant"]


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class RunEventType(str, Enum):
    RUN_STARTED = "run.started"
    MODEL_STARTED = "model.started"
    ASSISTANT_DELTA = "assistant.delta"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    RUN_INTERRUPTED = "run.interrupted"


class StoreFailure(str, Enum):
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    RUN_BUSY = "run_busy"
    RUN_NOT_ACTIVE = "run_not_active"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INVALID_STATE = "invalid_state"
    DATABASE_UNAVAILABLE = "database_unavailable"


@dataclass(frozen=True, slots=True)
class PublicRunError:
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    id: str
    title: str
    latest_message_preview: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationPage:
    items: tuple[ConversationSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    conversation_id: str
    run_id: str
    role: MessageRole
    content: str
    sequence: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessagePage:
    items: tuple[Message, ...]
    next_before_sequence: int | None


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str | None
    provider_id: ProviderId
    model_id: str
    response_mode: ResponseMode
    status: RunStatus
    error: PublicRunError | None
    partial_text: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunEvent:
    sequence: int
    type: RunEventType
    run_id: str
    conversation_id: str
    created_at: datetime
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class StartRunResult:
    conversation: ConversationSummary
    run: RunSnapshot
    replayed: bool


@dataclass(frozen=True, slots=True)
class CompletedRun:
    run: RunSnapshot
    message: Message
