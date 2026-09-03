"""Schedule application behavior independent of HTTP and runtime waiting."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Callable, Protocol

from .models import CadenceType, Occurrence, OccurrencePage, OccurrenceStatus, OccurrenceTrigger, Schedule, ScheduleDraft, SchedulePage, ScheduleStatus
from .recurrence import RecurrenceError, next_occurrence
from .repository import ScheduleFailure, ScheduleRepository, ScheduleStoreError


class ScheduleOperations(Protocol):
    async def create(self, draft: ScheduleDraft) -> Schedule: ...
    async def get(self, schedule_id: str) -> Schedule: ...
    async def list(self, *, limit: int, before: str | None) -> SchedulePage: ...
    async def update(
        self,
        schedule_id: str,
        revision: int,
        draft: ScheduleDraft,
    ) -> Schedule: ...
    async def pause(self, schedule_id: str, revision: int) -> Schedule: ...
    async def resume(self, schedule_id: str, revision: int) -> Schedule: ...
    async def delete(self, schedule_id: str) -> None: ...
    async def run_now(self, schedule_id: str) -> Occurrence: ...
    async def occurrences(
        self,
        schedule_id: str,
        *,
        limit: int,
        before: str | None,
    ) -> OccurrencePage: ...
    async def latest_occurrences(
        self,
        schedule_ids: tuple[str, ...],
    ) -> dict[str, Occurrence]: ...


class UnavailableSchedules:
    @staticmethod
    def _raise():
        raise ScheduleStoreError(ScheduleFailure.DATABASE_UNAVAILABLE)

    async def create(self, draft):
        del draft
        self._raise()

    async def get(self, schedule_id):
        del schedule_id
        self._raise()

    async def list(self, *, limit, before):
        del limit, before
        self._raise()

    async def update(self, schedule_id, revision, draft):
        del schedule_id, revision, draft
        self._raise()

    async def pause(self, schedule_id, revision):
        del schedule_id, revision
        self._raise()

    async def resume(self, schedule_id, revision):
        del schedule_id, revision
        self._raise()

    async def delete(self, schedule_id):
        del schedule_id
        self._raise()

    async def run_now(self, schedule_id):
        del schedule_id
        self._raise()

    async def occurrences(self, schedule_id, *, limit, before):
        del schedule_id, limit, before
        self._raise()

    async def latest_occurrences(self, schedule_ids):
        del schedule_ids
        self._raise()


class ScheduleService:
    def __init__(
        self,
        repository: ScheduleRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._on_change = on_change or (lambda: None)

    async def create(self, draft: ScheduleDraft) -> Schedule:
        next_run = self._next(draft, self._now())
        if next_run is None:
            raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        item = await asyncio.to_thread(
            self.repository.create,
            draft,
            next_run_at=next_run,
        )
        self._on_change()
        return item

    async def get(self, schedule_id: str) -> Schedule:
        item = await asyncio.to_thread(self.repository.get, schedule_id)
        if item is None:
            raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
        return item

    async def list(self, *, limit: int, before: str | None) -> SchedulePage:
        return await asyncio.to_thread(
            self.repository.list,
            limit=limit,
            before=before,
        )

    async def update(
        self,
        schedule_id: str,
        revision: int,
        draft: ScheduleDraft,
    ) -> Schedule:
        next_run = self._next(draft, self._now())
        if next_run is None:
            raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        item = await asyncio.to_thread(
            self.repository.update,
            schedule_id,
            revision,
            draft,
            next_run_at=next_run,
        )
        self._on_change()
        return item

    async def pause(self, schedule_id: str, revision: int) -> Schedule:
        item = await asyncio.to_thread(
            self.repository.set_status,
            schedule_id,
            revision,
            ScheduleStatus.PAUSED,
            next_run_at=None,
        )
        self._on_change()
        return item

    async def resume(self, schedule_id: str, revision: int) -> Schedule:
        current = await self.get(schedule_id)
        next_run = self._next(
            ScheduleDraft(
                current.name,
                current.prompt,
                current.cadence,
                current.time_zone,
                current.profile,
            ),
            self._now(),
        )
        if next_run is None:
            raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        item = await asyncio.to_thread(
            self.repository.set_status,
            schedule_id,
            revision,
            ScheduleStatus.ACTIVE,
            next_run_at=next_run,
        )
        self._on_change()
        return item

    async def delete(self, schedule_id: str) -> None:
        await asyncio.to_thread(self.repository.delete, schedule_id)
        self._on_change()

    async def run_now(self, schedule_id: str) -> Occurrence:
        await self.get(schedule_id)
        item = await asyncio.to_thread(
            self.repository.create_occurrence,
            schedule_id,
            scheduled_for=self._now(),
            trigger=OccurrenceTrigger.MANUAL,
            status=OccurrenceStatus.PENDING,
        )
        self._on_change()
        return item

    async def occurrences(
        self,
        schedule_id: str,
        *,
        limit: int,
        before: str | None,
    ) -> OccurrencePage:
        return await asyncio.to_thread(
            self.repository.list_occurrences,
            schedule_id,
            limit=limit,
            before=before,
        )

    async def latest_occurrences(
        self,
        schedule_ids: tuple[str, ...],
    ) -> dict[str, Occurrence]:
        return await asyncio.to_thread(
            self.repository.latest_occurrences,
            schedule_ids,
        )

    def _next(self, draft: ScheduleDraft, after: datetime) -> datetime | None:
        try:
            return next_occurrence(draft.cadence, draft.time_zone, after)
        except RecurrenceError as error:
            raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST) from error

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        return value.astimezone(UTC)
