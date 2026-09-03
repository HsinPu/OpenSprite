"""Single-owner runtime coordinator for durable scheduled occurrences."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
import logging

from ..application.chat_service import AgentChatError, AgentChatService
from ..conversations.models import RunStatus
from .models import CadenceType, Occurrence, OccurrenceStatus, ScheduleStatus
from .recurrence import RecurrenceError, next_occurrence, occurrences_between
from .repository import ScheduleRepository, ScheduleStoreError


_LOGGER = logging.getLogger("opensprite.schedules")
_GRACE = timedelta(minutes=15)


class ScheduleCoordinator:
    def __init__(
        self,
        repository: ScheduleRepository,
        chat: AgentChatService,
        *,
        clock=None,
        maximum_wait_seconds: float = 30.0,
    ) -> None:
        self._repository = repository
        self._chat = chat
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_wait = maximum_wait_seconds
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._closed = False

    def wake(self) -> None:
        self._wake.set()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._closed = False
        await self._reconcile_incomplete()
        self._task = asyncio.create_task(
            self._run(),
            name="opensprite-schedule-coordinator",
        )

    async def close(self) -> None:
        self._closed = True
        self._wake.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def process_once(self) -> bool:
        pending = await asyncio.to_thread(
            self._repository.list_incomplete_occurrences,
            limit=100,
        )
        next_pending = next(
            (item for item in pending if item.status is OccurrenceStatus.PENDING),
            None,
        )
        if next_pending is not None:
            await self._execute(next_pending)
            return True
        now = self._now()
        due = await asyncio.to_thread(
            self._repository.list_due,
            now=now,
            limit=1,
        )
        if not due:
            return False
        schedule = due[0]
        try:
            candidates = (
                occurrences_between(
                    schedule.cadence,
                    schedule.time_zone,
                    schedule.next_run_at - timedelta(microseconds=1),
                    now,
                )
                if schedule.next_run_at
                else ()
            )
            scheduled_for = candidates[-1] if candidates else schedule.next_run_at
            if scheduled_for is None:
                return False
            following = (
                None
                if schedule.cadence.type is CadenceType.ONCE
                else next_occurrence(schedule.cadence, schedule.time_zone, now)
            )
            next_status = (
                ScheduleStatus.COMPLETED
                if schedule.cadence.type is CadenceType.ONCE
                else ScheduleStatus.ACTIVE
            )
            too_old = now - scheduled_for > _GRACE
            occurrence = await asyncio.to_thread(
                self._repository.claim_scheduled,
                schedule,
                scheduled_for=scheduled_for,
                next_run_at=following,
                next_status=next_status,
                missed_count=max(0, len(candidates) - 1),
                skipped_error="missed" if too_old else None,
            )
        except (ScheduleStoreError, RecurrenceError):
            _LOGGER.exception("schedule claim failed schedule_id=%s", schedule.id)
            return False
        if occurrence.status is OccurrenceStatus.PENDING:
            await self._execute(occurrence)
        return True

    async def _run(self) -> None:
        while not self._closed:
            progressed = await self.process_once()
            if progressed:
                continue
            self._wake.clear()
            try:
                await asyncio.wait_for(
                    self._wake.wait(),
                    timeout=self._maximum_wait,
                )
            except TimeoutError:
                pass

    async def _reconcile_incomplete(self) -> None:
        occurrences = await asyncio.to_thread(
            self._repository.list_incomplete_occurrences,
            limit=100,
        )
        for occurrence in occurrences:
            if occurrence.status is OccurrenceStatus.RUNNING and occurrence.run_id:
                try:
                    run = await self._chat.get_run(occurrence.run_id)
                except AgentChatError:
                    await asyncio.to_thread(
                        self._repository.finish_occurrence,
                        occurrence.id,
                        OccurrenceStatus.FAILED,
                        "run_unavailable",
                    )
                    continue
                if run.status in {
                    RunStatus.COMPLETED,
                    RunStatus.FAILED,
                    RunStatus.CANCELLED,
                    RunStatus.INTERRUPTED,
                }:
                    status = (
                        OccurrenceStatus.COMPLETED
                        if run.status is RunStatus.COMPLETED
                        else OccurrenceStatus.FAILED
                    )
                    error_code = (
                        None
                        if status is OccurrenceStatus.COMPLETED
                        else (run.error.code if run.error else run.status.value)
                    )
                    await asyncio.to_thread(
                        self._repository.finish_occurrence,
                        occurrence.id,
                        status,
                        error_code,
                    )

    async def _execute(self, occurrence: Occurrence) -> None:
        schedule = await asyncio.to_thread(
            self._repository.get,
            occurrence.schedule_id,
        )
        if schedule is None:
            return
        overlap = await asyncio.to_thread(
            self._repository.has_running_occurrence,
            schedule.id,
        )
        if overlap:
            await asyncio.to_thread(
                self._repository.finish_occurrence,
                occurrence.id,
                OccurrenceStatus.SKIPPED,
                "overlap",
            )
            return
        try:
            accepted = await self._chat.start_scheduled_run(
                conversation_id=schedule.conversation_id,
                occurrence_id=occurrence.id,
                message=schedule.prompt,
                profile=schedule.profile,
            )
            if schedule.conversation_id is None:
                await asyncio.to_thread(
                    self._repository.bind_conversation,
                    schedule.id,
                    accepted.conversation.id,
                )
            await asyncio.to_thread(
                self._repository.mark_occurrence_running,
                occurrence.id,
                accepted.run.id,
            )
            run = await self._chat.wait_run(accepted.run.id)
            if run is None:
                await asyncio.to_thread(
                    self._repository.finish_occurrence,
                    occurrence.id,
                    OccurrenceStatus.FAILED,
                    "run_unavailable",
                )
                return
            status = (
                OccurrenceStatus.COMPLETED
                if run.status is RunStatus.COMPLETED
                else OccurrenceStatus.FAILED
            )
            error_code = (
                None
                if status is OccurrenceStatus.COMPLETED
                else (run.error.code if run.error else run.status.value)
            )
            await asyncio.to_thread(
                self._repository.finish_occurrence,
                occurrence.id,
                status,
                error_code,
            )
        except (AgentChatError, ScheduleStoreError) as error:
            code = (
                error.code.value
                if isinstance(error, AgentChatError)
                else error.failure.value
            )
            with suppress(ScheduleStoreError):
                await asyncio.to_thread(
                    self._repository.finish_occurrence,
                    occurrence.id,
                    OccurrenceStatus.FAILED,
                    code,
                )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("schedule clock must be timezone-aware")
        return value.astimezone(UTC)
