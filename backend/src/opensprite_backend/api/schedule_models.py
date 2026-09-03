"""Strict public models for durable schedule management."""

from __future__ import annotations

from datetime import datetime, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from opensprite_backend.schedules.models import (
    Cadence,
    CadenceType,
    ExecutionProfile,
    Occurrence,
    OccurrencePage,
    Schedule,
    ScheduleDraft,
    SchedulePage,
)


class ScheduleContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionProfileModel(ScheduleContractModel):
    providerId: Literal["openai", "anthropic", "openrouter"]
    modelId: str = Field(min_length=1, max_length=200)
    responseMode: Literal["default", "fast", "balanced", "deep"]
    contextBudget: Literal["auto", "32k", "64k", "128k", "256k", "max"]
    outputBudget: Literal["auto", "8k", "16k", "32k", "64k", "max"]
    outputContinuation: Literal[
        "off", "1", "2", "3", "5", "10", "20", "50", "unlimited"
    ]

    def domain(self) -> ExecutionProfile:
        return ExecutionProfile(
            self.providerId,
            self.modelId,
            self.responseMode,
            self.contextBudget,
            self.outputBudget,
            self.outputContinuation,
        )


class OnceCadenceModel(ScheduleContractModel):
    type: Literal["once"]
    runAt: datetime

    def domain(self) -> Cadence:
        return Cadence(CadenceType.ONCE, run_at=self.runAt)


class DailyCadenceModel(ScheduleContractModel):
    type: Literal["daily"]
    localTime: time

    def domain(self) -> Cadence:
        return Cadence(CadenceType.DAILY, local_time=self.localTime)


class WeeklyCadenceModel(ScheduleContractModel):
    type: Literal["weekly"]
    localTime: time
    weekdays: list[int] = Field(min_length=1, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if any(type(day) is not int or day < 1 or day > 7 for day in value):
            raise ValueError("invalid weekday")
        if value != sorted(set(value)):
            raise ValueError("weekdays must be unique and sorted")
        return value

    def domain(self) -> Cadence:
        return Cadence(
            CadenceType.WEEKLY,
            local_time=self.localTime,
            weekdays=tuple(self.weekdays),
        )


CadenceModel = Annotated[
    OnceCadenceModel | DailyCadenceModel | WeeklyCadenceModel,
    Field(discriminator="type"),
]


class ScheduleFields(ScheduleContractModel):
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=32768)
    timeZone: str = Field(min_length=1, max_length=100)
    cadence: CadenceModel
    executionProfile: ExecutionProfileModel

    @field_validator("name", "prompt")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank value")
        return value

    def draft(self) -> ScheduleDraft:
        return ScheduleDraft(
            self.name,
            self.prompt,
            self.cadence.domain(),
            self.timeZone,
            self.executionProfile.domain(),
        )


class CreateScheduleRequest(ScheduleFields):
    pass


class UpdateScheduleRequest(ScheduleFields):
    revision: int = Field(ge=1)


class RevisionRequest(ScheduleContractModel):
    revision: int = Field(ge=1)


class ScheduleResponse(ScheduleContractModel):
    id: UUID
    name: str
    prompt: str
    timeZone: str
    cadence: dict[str, object]
    executionProfile: ExecutionProfileModel
    status: Literal["active", "paused", "completed"]
    conversationId: UUID | None
    nextRunAt: datetime | None
    revision: int
    createdAt: datetime
    updatedAt: datetime
    latestOccurrence: OccurrenceResponse | None = None


class ScheduleListResponse(ScheduleContractModel):
    schedules: list[ScheduleResponse] = Field(max_length=100)
    nextCursor: str | None


class OccurrenceResponse(ScheduleContractModel):
    id: UUID
    scheduleId: UUID
    scheduledFor: datetime
    trigger: Literal["manual", "scheduled"]
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    runId: UUID | None
    errorCode: str | None
    missedCount: int = Field(ge=0)
    startedAt: datetime | None
    finishedAt: datetime | None
    createdAt: datetime


class OccurrenceListResponse(ScheduleContractModel):
    occurrences: list[OccurrenceResponse] = Field(max_length=100)
    nextCursor: str | None


class RuntimeStatusResponse(ScheduleContractModel):
    platform: str
    continuity: Literal["linger_enabled", "login_only", "unknown"]


class ScheduleErrorDetail(ScheduleContractModel):
    code: Literal[
        "invalid_request",
        "not_found",
        "revision_conflict",
        "database_unavailable",
    ]
    message: str
    retryable: bool


class ScheduleErrorEnvelope(ScheduleContractModel):
    error: ScheduleErrorDetail


def schedule_response(
    item: Schedule,
    latest_occurrence: Occurrence | None = None,
) -> ScheduleResponse:
    cadence: dict[str, object] = {"type": item.cadence.type.value}
    if item.cadence.run_at is not None:
        cadence["runAt"] = item.cadence.run_at
    if item.cadence.local_time is not None:
        cadence["localTime"] = item.cadence.local_time.isoformat(timespec="minutes")
    if item.cadence.weekdays:
        cadence["weekdays"] = list(item.cadence.weekdays)
    return ScheduleResponse(
        id=item.id,
        name=item.name,
        prompt=item.prompt,
        timeZone=item.time_zone,
        cadence=cadence,
        executionProfile=ExecutionProfileModel(
            providerId=item.profile.provider_id,
            modelId=item.profile.model_id,
            responseMode=item.profile.response_mode,
            contextBudget=item.profile.context_budget,
            outputBudget=item.profile.output_budget,
            outputContinuation=item.profile.output_continuation,
        ),
        status=item.status.value,
        conversationId=item.conversation_id,
        nextRunAt=item.next_run_at,
        revision=item.revision,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
        latestOccurrence=(
            None
            if latest_occurrence is None
            else occurrence_response(latest_occurrence)
        ),
    )


def schedule_list_response(
    page: SchedulePage,
    latest_occurrences: dict[str, Occurrence] | None = None,
) -> ScheduleListResponse:
    latest_occurrences = latest_occurrences or {}
    return ScheduleListResponse(
        schedules=[
            schedule_response(item, latest_occurrences.get(item.id))
            for item in page.items
        ],
        nextCursor=page.next_cursor,
    )


def occurrence_response(item: Occurrence) -> OccurrenceResponse:
    return OccurrenceResponse(
        id=item.id,
        scheduleId=item.schedule_id,
        scheduledFor=item.scheduled_for,
        trigger=item.trigger.value,
        status=item.status.value,
        runId=item.run_id,
        errorCode=item.error_code,
        missedCount=item.missed_count,
        startedAt=item.started_at,
        finishedAt=item.finished_at,
        createdAt=item.created_at,
    )


def occurrence_list_response(page: OccurrencePage) -> OccurrenceListResponse:
    return OccurrenceListResponse(
        occurrences=[occurrence_response(item) for item in page.items],
        nextCursor=page.next_cursor,
    )
