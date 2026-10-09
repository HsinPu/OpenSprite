"""Technology-neutral records owned by the conversation persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from opensprite_backend.workspaces.models import (
    EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH,
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
)


from opensprite_backend.provider_identity import ProviderId
from opensprite_backend.response_modes import HistoricalResponseMode as ResponseMode, HISTORICAL_RESPONSE_MODES, ReasoningResolution
ContextBudget = Literal["auto", "32k", "64k", "128k", "256k", "max"]
OutputBudget = Literal["auto", "8k", "16k", "32k", "64k", "max"]
OutputContinuation = Literal["off", "1", "2", "3", "5", "10", "20", "50", "unlimited"]
MessageRole = Literal["user", "assistant"]
MAX_ASSISTANT_CHARS = 1_048_576


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class CompletionReason(str, Enum):
    STOP = "stop"
    OUTPUT_LIMIT = "output_limit"
    CONTEXT_LIMIT = "context_limit"


class RunEventType(str, Enum):
    RUN_STARTED = "run.started"
    EXECUTION_SELECTED = "execution.selected"
    CONTEXT_COMPACTION_STARTED = "context.compaction.started"
    CONTEXT_COMPACTION_COMPLETED = "context.compaction.completed"
    CONTEXT_COMPACTION_FAILED = "context.compaction.failed"
    CONTEXT_COMPACTION_CANCELLED = "context.compaction.cancelled"
    MODEL_ATTEMPT = "model.attempt"
    MODEL_STARTED = "model.started"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    RESPONSE_CONTINUATION_STARTED = "response.continuation.started"
    ASSISTANT_DELTA = "assistant.delta"
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
    REVISION_CONFLICT = "revision_conflict"
    WORKSPACE_MISMATCH = "workspace_mismatch"


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
    workspace_id: str = DEFAULT_WORKSPACE_ID
    revision: int = 1


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
    context_budget: ContextBudget = "auto"
    output_budget: OutputBudget = "auto"
    output_continuation: OutputContinuation | None = None
    log_full_prompts: bool = False
    completion_reason: CompletionReason | None = None
    workspace_id: str = DEFAULT_WORKSPACE_ID
    workspace_revision: int = 1
    workspace_name_snapshot: str = DEFAULT_WORKSPACE_NAME
    workspace_root_hash: str | None = None
    workspace_mount_manifest_hash: str = EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH
    reasoning_resolution: ReasoningResolution | None = None


@dataclass(frozen=True, slots=True)
class ConversationCompaction:
    id: str
    conversation_id: str
    covers_through_sequence: int
    summary: str
    summary_version: int
    source_hash: str
    provider_id: ProviderId
    model_id: str
    input_tokens: int
    output_tokens: int
    created_at: datetime
    producer_plugin_id: str = "legacy"
    producer_plugin_version: str = "unknown"
    summary_format: str = "opensprite.text.v1"
    source_step_id: str | None = None
    source_first_sequence: int | None = None
    previous_summary_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunStep:
    id: str
    run_id: str
    sequence: int
    label: str
    channel: Literal["draft", "answer"]
    status: Literal["running", "completed", "failed", "cancelled", "interrupted"]
    text: str
    finish_reason: str | None
    error_code: str | None
    input_tokens: int | None
    output_tokens: int | None
    retry_of: str | None
    created_at: datetime
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
