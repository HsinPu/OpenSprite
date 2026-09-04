from __future__ import annotations

from datetime import UTC, datetime, time
import sqlite3
from pathlib import Path

import pytest

from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.workspaces import UNASSIGNED_WORKSPACE_ID
from opensprite_backend.schedules import (
    Cadence, CadenceType, ExecutionProfile, OccurrenceStatus, OccurrenceTrigger,
    ScheduleDraft, ScheduleFailure, ScheduleStatus, ScheduleStoreError,
    SqliteScheduleRepository, next_occurrence,
)


NOW = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
IDS = tuple(f"00000000-0000-4000-8000-{index:012d}" for index in range(1, 30))


def draft(
    cadence: Cadence | None = None,
    workspace_id: str = UNASSIGNED_WORKSPACE_ID,
) -> ScheduleDraft:
    return ScheduleDraft(
        "Morning brief",
        "Summarize today's priorities.",
        cadence or Cadence(CadenceType.DAILY, local_time=time(9, 30)),
        "Asia/Taipei",
        ExecutionProfile("openrouter", "openrouter/auto", "balanced", "64k", "16k", "5"),
        workspace_id,
    )


def repository(tmp_path: Path) -> SqliteScheduleRepository:
    identifiers = iter(IDS)
    return SqliteScheduleRepository(tmp_path / "opensprite.db", clock=lambda: NOW, identifier_factory=lambda: next(identifiers))


def test_recurrence_handles_daily_weekly_and_dst_edges() -> None:
    assert next_occurrence(Cadence(CadenceType.DAILY, local_time=time(9)), "Asia/Taipei", datetime(2026, 3, 1, 0, 30, tzinfo=UTC)) == datetime(2026, 3, 1, 1, 0, tzinfo=UTC)
    weekly = Cadence(CadenceType.WEEKLY, local_time=time(8), weekdays=(1, 5))
    assert next_occurrence(weekly, "UTC", datetime(2026, 3, 2, 8, 0, tzinfo=UTC)) == datetime(2026, 3, 6, 8, 0, tzinfo=UTC)
    assert next_occurrence(Cadence(CadenceType.DAILY, local_time=time(2, 30)), "America/New_York", datetime(2026, 3, 8, 0, 0, tzinfo=UTC)) == datetime(2026, 3, 8, 7, 0, tzinfo=UTC)
    assert next_occurrence(Cadence(CadenceType.DAILY, local_time=time(1, 30)), "America/New_York", datetime(2026, 11, 1, 0, 0, tzinfo=UTC)) == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_schedule_crud_revision_pagination_and_occurrence_uniqueness(tmp_path: Path) -> None:
    store = repository(tmp_path)
    first_next = datetime(2026, 3, 1, 1, 30, tzinfo=UTC)
    first = store.create(draft(), next_run_at=first_next)
    second = store.create(draft(Cadence(CadenceType.ONCE, run_at=datetime(2026, 3, 2, tzinfo=UTC))), next_run_at=datetime(2026, 3, 2, tzinfo=UTC))
    page = store.list(limit=1, before=None)
    assert len(page.items) == 1 and page.next_cursor is not None
    assert store.list(limit=1, before=page.next_cursor).items[0].id == first.id
    updated = store.update(first.id, 1, ScheduleDraft("Updated", first.prompt, first.cadence, first.time_zone, first.profile), next_run_at=first_next)
    assert updated.revision == 2 and updated.name == "Updated"
    with pytest.raises(ScheduleStoreError) as conflict:
        store.update(first.id, 1, draft(), next_run_at=first_next)
    assert conflict.value.failure is ScheduleFailure.REVISION_CONFLICT
    paused = store.set_status(first.id, 2, ScheduleStatus.PAUSED, next_run_at=None)
    assert paused.status is ScheduleStatus.PAUSED and paused.next_run_at is None
    occurrence = store.create_occurrence(first.id, scheduled_for=first_next, trigger=OccurrenceTrigger.SCHEDULED, status=OccurrenceStatus.SKIPPED, error_code="missed", missed_count=3)
    assert occurrence.missed_count == 3
    assert store.latest_occurrences((first.id, second.id)) == {first.id: occurrence}
    with pytest.raises(ScheduleStoreError):
        store.create_occurrence(first.id, scheduled_for=first_next, trigger=OccurrenceTrigger.SCHEDULED, status=OccurrenceStatus.PENDING)
    assert store.list_occurrences(first.id, limit=10, before=None).items == (occurrence,)
    store.delete(second.id)
    assert store.get(second.id) is None


def test_schema_v10_migrates_to_current_without_losing_conversation_data(tmp_path: Path) -> None:
    database = tmp_path / "opensprite.db"
    conversations = SqliteConversationRepository(database)
    accepted = conversations.start_run(conversation_id=None, client_request_id=IDS[20], message="keep", provider_id="openrouter", model_id="openrouter/auto", response_mode="default")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX runs_by_occurrence")
        connection.execute("DROP TABLE schedule_occurrences")
        connection.execute("DROP TABLE schedules")
        connection.execute("ALTER TABLE runs DROP COLUMN occurrence_id")
        connection.execute("ALTER TABLE runs DROP COLUMN source")
        connection.execute("PRAGMA user_version=10")
    schedules = repository(tmp_path)
    created = schedules.create(draft(), next_run_at=datetime(2026, 3, 1, 1, 30, tzinfo=UTC))
    assert created.name == "Morning brief"
    assert conversations.get_run(accepted.run.id) is not None
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 12


def test_schedule_workspace_change_moves_owned_conversation_atomically(
    tmp_path: Path,
) -> None:
    workspace_a = "11111111-1111-4111-8111-111111111111"
    workspace_b = "22222222-2222-4222-8222-222222222222"
    schedules = repository(tmp_path)
    conversations = SqliteConversationRepository(schedules._database_file)
    schedule = schedules.create(
        draft(workspace_id=workspace_a),
        next_run_at=datetime(2026, 3, 1, 1, 30, tzinfo=UTC),
    )
    run = conversations.start_run(
        conversation_id=None,
        client_request_id=IDS[20],
        message="scheduled",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        workspace_id=workspace_a,
        workspace_revision=1,
        workspace_name_snapshot="Alpha",
        workspace_root_hash="a" * 64,
    )
    conversations.mark_run_started(run.run.id)
    conversations.complete_run(run.run.id, "done")
    schedule = schedules.bind_conversation(schedule.id, run.conversation.id)
    managed = conversations.get_conversation(run.conversation.id)
    assert managed is not None and managed.workspace_managed_by_schedule is True

    changed = schedules.update(
        schedule.id,
        schedule.revision,
        draft(workspace_id=workspace_b),
        next_run_at=datetime(2026, 3, 1, 1, 30, tzinfo=UTC),
    )

    assert changed.workspace_id == workspace_b
    conversation = conversations.get_conversation(run.conversation.id)
    assert conversation is not None
    assert conversation.workspace_id == workspace_b
    assert conversation.revision == 2


def test_schedule_workspace_change_rolls_back_while_occurrence_is_pending(
    tmp_path: Path,
) -> None:
    workspace_a = "11111111-1111-4111-8111-111111111111"
    workspace_b = "22222222-2222-4222-8222-222222222222"
    schedules = repository(tmp_path)
    schedule = schedules.create(
        draft(workspace_id=workspace_a),
        next_run_at=datetime(2026, 3, 1, 1, 30, tzinfo=UTC),
    )
    schedules.create_occurrence(
        schedule.id,
        scheduled_for=datetime(2026, 3, 1, 1, 30, tzinfo=UTC),
        trigger=OccurrenceTrigger.MANUAL,
        status=OccurrenceStatus.PENDING,
    )

    with pytest.raises(ScheduleStoreError) as raised:
        schedules.update(
            schedule.id,
            schedule.revision,
            draft(workspace_id=workspace_b),
            next_run_at=datetime(2026, 3, 1, 1, 30, tzinfo=UTC),
        )

    assert raised.value.failure is ScheduleFailure.WORKSPACE_BUSY
    assert schedules.get(schedule.id).workspace_id == workspace_a  # type: ignore[union-attr]
