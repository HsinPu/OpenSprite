"""Domain records for durable scheduled Agent execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum

from ..conversations.models import ContextBudget, OutputBudget, OutputContinuation, ProviderId, ResponseMode


class CadenceType(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


class ScheduleStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class OccurrenceTrigger(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class OccurrenceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    provider_id: ProviderId
    model_id: str
    response_mode: ResponseMode
    context_budget: ContextBudget
    output_budget: OutputBudget
    output_continuation: OutputContinuation


@dataclass(frozen=True, slots=True)
class Cadence:
    type: CadenceType
    run_at: datetime | None = None
    local_time: time | None = None
    weekdays: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ScheduleDraft:
    name: str
    prompt: str
    cadence: Cadence
    time_zone: str
    profile: ExecutionProfile


@dataclass(frozen=True, slots=True)
class Schedule:
    id: str
    name: str
    prompt: str
    cadence: Cadence
    time_zone: str
    profile: ExecutionProfile
    status: ScheduleStatus
    conversation_id: str | None
    next_run_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SchedulePage:
    items: tuple[Schedule, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class Occurrence:
    id: str
    schedule_id: str
    scheduled_for: datetime
    trigger: OccurrenceTrigger
    status: OccurrenceStatus
    run_id: str | None
    error_code: str | None
    missed_count: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OccurrencePage:
    items: tuple[Occurrence, ...]
    next_cursor: str | None
