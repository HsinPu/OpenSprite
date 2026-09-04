from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from functools import wraps
from pathlib import Path

import pytest

from opensprite_backend.conversations.models import (
    ConversationSummary,
    PublicRunError,
    RunSnapshot,
    RunStatus,
    StartRunResult,
)
from opensprite_backend.conversations.sqlite_repository import (
    SqliteConversationRepository,
)
from opensprite_backend.schedules.coordinator import ScheduleCoordinator
from opensprite_backend.schedules.models import (
    Cadence,
    CadenceType,
    ExecutionProfile,
    OccurrenceStatus,
    OccurrenceTrigger,
    ScheduleDraft,
    ScheduleStatus,
)
from opensprite_backend.schedules.service import ScheduleService
from opensprite_backend.schedules.sqlite_repository import SqliteScheduleRepository


NOW = datetime(2026, 3, 5, 3, 0, tzinfo=UTC)
IDS = tuple(
    f"10000000-0000-4000-8000-{index:012d}" for index in range(1, 100)
)


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def _profile() -> ExecutionProfile:
    return ExecutionProfile(
        "openrouter",
        "openrouter/auto",
        "balanced",
        "64k",
        "16k",
        "5",
    )


def _draft(cadence: Cadence) -> ScheduleDraft:
    return ScheduleDraft(
        "Daily brief",
        "Summarize the latest state.",
        cadence,
        "UTC",
        _profile(),
    )


def _repository(tmp_path: Path) -> SqliteScheduleRepository:
    identifiers = iter(IDS)
    return SqliteScheduleRepository(
        tmp_path / "opensprite.db",
        clock=lambda: NOW,
        identifier_factory=lambda: next(identifiers),
    )


class FakeChat:
    def __init__(
        self,
        schedules: SqliteScheduleRepository,
        status: RunStatus = RunStatus.COMPLETED,
    ) -> None:
        self.repository = SqliteConversationRepository(schedules._database_file)
        self.status = status
        self.starts: list[dict[str, object]] = []

    async def start_scheduled_run(self, **kwargs) -> StartRunResult:
        self.starts.append(kwargs)
        profile = kwargs["profile"]
        return self.repository.start_run(
            conversation_id=kwargs["conversation_id"],
            client_request_id=str(kwargs["occurrence_id"]),
            message=str(kwargs["message"]),
            provider_id=profile.provider_id,
            model_id=profile.model_id,
            response_mode=profile.response_mode,
            context_budget=profile.context_budget,
            output_budget=profile.output_budget,
            output_continuation=profile.output_continuation,
            source="schedule",
            occurrence_id=str(kwargs["occurrence_id"]),
            workspace_id=str(kwargs["workspace_id"]),
        )

    async def wait_run(self, run_id: str) -> RunSnapshot:
        self.repository.mark_run_started(run_id)
        if self.status is RunStatus.COMPLETED:
            self.repository.complete_run(run_id, "done")
        else:
            self.repository.fail_run(
                run_id,
                PublicRunError("scheduled_failure", "failed", False),
            )
        run = self.repository.get_run(run_id)
        assert run is not None
        return run

    async def get_run(self, run_id: str) -> RunSnapshot:
        return await self.wait_run(run_id)


@async_test
async def test_service_wakes_coordinator_and_resume_uses_future_time(
    tmp_path: Path,
) -> None:
    store = _repository(tmp_path)
    wake_count = 0

    def wake() -> None:
        nonlocal wake_count
        wake_count += 1

    service = ScheduleService(store, clock=lambda: NOW, on_change=wake)
    schedule = await service.create(
        _draft(Cadence(CadenceType.DAILY, local_time=time(4)))
    )
    paused = await service.pause(schedule.id, schedule.revision)
    edited_while_paused = await service.update(
        paused.id,
        paused.revision,
        ScheduleDraft(
            "Updated while paused",
            paused.prompt,
            paused.cadence,
            paused.time_zone,
            paused.profile,
        ),
    )
    assert edited_while_paused.status is ScheduleStatus.PAUSED
    assert edited_while_paused.next_run_at is None
    resumed = await service.resume(edited_while_paused.id, edited_while_paused.revision)
    manual = await service.run_now(resumed.id)

    assert resumed.next_run_at == datetime(2026, 3, 5, 4, tzinfo=UTC)
    assert manual.trigger is OccurrenceTrigger.MANUAL
    assert manual.status is OccurrenceStatus.PENDING
    assert wake_count == 5


@async_test
async def test_due_once_executes_and_binds_dedicated_conversation(
    tmp_path: Path,
) -> None:
    store = _repository(tmp_path)
    schedule = store.create(
        _draft(Cadence(CadenceType.ONCE, run_at=NOW - timedelta(minutes=5))),
        next_run_at=NOW - timedelta(minutes=5),
    )
    chat = FakeChat(store)
    coordinator = ScheduleCoordinator(store, chat, clock=lambda: NOW)

    assert await coordinator.process_once() is True

    occurrence = store.list_occurrences(schedule.id, limit=10, before=None).items[0]
    refreshed = store.get(schedule.id)
    assert occurrence.status is OccurrenceStatus.COMPLETED
    assert occurrence.run_id is not None
    assert refreshed is not None
    assert refreshed.status is ScheduleStatus.COMPLETED
    assert refreshed.conversation_id is not None
    assert chat.starts[0]["profile"] == schedule.profile
    assert chat.starts[0]["workspace_id"] == schedule.workspace_id


@async_test
async def test_old_missed_occurrences_are_collapsed_without_execution(
    tmp_path: Path,
) -> None:
    store = _repository(tmp_path)
    first_due = NOW - timedelta(days=3, minutes=30)
    schedule = store.create(
        _draft(Cadence(CadenceType.DAILY, local_time=time(2, 30))),
        next_run_at=first_due,
    )
    chat = FakeChat(store)
    coordinator = ScheduleCoordinator(store, chat, clock=lambda: NOW)

    assert await coordinator.process_once() is True

    occurrence = store.list_occurrences(schedule.id, limit=10, before=None).items[0]
    refreshed = store.get(schedule.id)
    assert occurrence.status is OccurrenceStatus.SKIPPED
    assert occurrence.error_code == "missed"
    assert occurrence.missed_count == 3
    assert chat.starts == []
    assert refreshed is not None
    assert refreshed.next_run_at == datetime(2026, 3, 6, 2, 30, tzinfo=UTC)


@async_test
async def test_pending_occurrence_is_skipped_when_same_schedule_is_running(
    tmp_path: Path,
) -> None:
    store = _repository(tmp_path)
    schedule = store.create(
        _draft(Cadence(CadenceType.DAILY, local_time=time(4))),
        next_run_at=NOW + timedelta(hours=1),
    )
    running = store.create_occurrence(
        schedule.id,
        scheduled_for=NOW - timedelta(minutes=1),
        trigger=OccurrenceTrigger.MANUAL,
        status=OccurrenceStatus.PENDING,
    )
    conversations = SqliteConversationRepository(store._database_file)
    accepted = conversations.start_run(
        conversation_id=None,
        client_request_id=IDS[90],
        message="already running",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="balanced",
    )
    store.mark_occurrence_running(running.id, accepted.run.id)
    pending = store.create_occurrence(
        schedule.id,
        scheduled_for=NOW,
        trigger=OccurrenceTrigger.MANUAL,
        status=OccurrenceStatus.PENDING,
    )
    chat = FakeChat(store)
    coordinator = ScheduleCoordinator(store, chat, clock=lambda: NOW)

    assert await coordinator.process_once() is True

    items = store.list_occurrences(schedule.id, limit=10, before=None).items
    skipped = next(item for item in items if item.id == pending.id)
    assert skipped.status is OccurrenceStatus.SKIPPED
    assert skipped.error_code == "overlap"
    assert chat.starts == []


@async_test
async def test_coordinator_close_cancels_background_task(tmp_path: Path) -> None:
    store = _repository(tmp_path)
    coordinator = ScheduleCoordinator(
        store,
        FakeChat(store),
        clock=lambda: NOW,
        maximum_wait_seconds=60,
    )
    await coordinator.start()
    assert coordinator._task is not None
    await coordinator.close()
    assert coordinator._task is None
