"""Durability and state-transition tests for the minimal chat database."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import (
    PublicRunError,
    RunEventType,
    RunStatus,
    StoreFailure,
)
from opensprite_backend.conversations.repository import ConversationStoreError
from opensprite_backend.conversations.sqlite_repository import (
    SqliteConversationRepository,
)


NOW = datetime(2026, 8, 21, 8, 30, tzinfo=UTC)


def repository(tmp_path: Path) -> SqliteConversationRepository:
    return SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file,
        clock=lambda: NOW,
    )


def start(
    store: SqliteConversationRepository,
    *,
    conversation_id: str | None = None,
    client_request_id: str | None = None,
    message: str = "整理今天的工作",
):
    return store.start_run(
        conversation_id=conversation_id,
        client_request_id=client_request_id or str(uuid4()),
        message=message,
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    )


def test_construction_and_empty_reads_have_no_filesystem_side_effects(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = SqliteConversationRepository(paths.database_file, clock=lambda: NOW)

    assert store.list_conversations(limit=50, before=None).items == ()
    assert store.get_run(str(uuid4())) is None
    assert store.get_conversation(str(uuid4())) is None
    assert not paths.home.exists()


def test_first_start_is_one_durable_conversation_message_and_run(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = SqliteConversationRepository(paths.database_file, clock=lambda: NOW)

    accepted = start(
        store,
        message="  整理   今天的工作與後續安排  ",
        client_request_id="8b2bd588-b0bd-4ac6-a55e-e21b5715d39c",
    )

    assert accepted.replayed is False
    assert accepted.run.status is RunStatus.QUEUED
    assert accepted.run.provider_id == "openrouter"
    assert accepted.run.model_id == "openrouter/auto"
    assert accepted.run.response_mode == "default"
    assert accepted.run.partial_text == ""
    conversation = store.get_conversation(accepted.conversation.id)
    assert conversation is not None
    assert conversation.title == "整理 今天的工作與後續安排"
    assert conversation.latest_message_preview == "整理 今天的工作與後續安排"
    messages = store.list_messages(
        accepted.conversation.id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content, item.sequence) for item in messages.items] == [
        ("user", "整理   今天的工作與後續安排", 1)
    ]
    assert paths.database_file.is_file()
    assert {path.name for path in paths.home.iterdir()} == {"data"}
    assert not paths.credential_file.exists()
    assert not paths.conversations_dir.exists()


def test_client_request_id_replays_exact_request_without_duplicates(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    request_id = "8b2bd588-b0bd-4ac6-a55e-e21b5715d39c"

    first = start(store, client_request_id=request_id)
    replay = start(store, client_request_id=request_id)

    assert replay.replayed is True
    assert replay.conversation.id == first.conversation.id
    assert replay.run.id == first.run.id
    assert len(store.list_conversations(limit=50, before=None).items) == 1
    assert len(
        store.list_messages(
            first.conversation.id,
            limit=100,
            before_sequence=None,
        ).items
    ) == 1


def test_reused_request_id_with_different_input_fails_closed(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    request_id = "8b2bd588-b0bd-4ac6-a55e-e21b5715d39c"
    start(store, client_request_id=request_id, message="first")

    with pytest.raises(ConversationStoreError) as captured:
        start(store, client_request_id=request_id, message="different")

    assert captured.value.failure is StoreFailure.IDEMPOTENCY_CONFLICT


def test_one_conversation_rejects_a_second_active_run(tmp_path: Path) -> None:
    store = repository(tmp_path)
    first = start(store)

    with pytest.raises(ConversationStoreError) as captured:
        start(store, conversation_id=first.conversation.id, message="second")

    assert captured.value.failure is StoreFailure.RUN_BUSY


def test_run_events_deltas_and_completion_are_atomic_visible_state(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)

    started = store.mark_run_started(accepted.run.id)
    assert started.status is RunStatus.RUNNING
    store.append_run_event(
        accepted.run.id,
        RunEventType.MODEL_STARTED,
        {
            "providerId": "openrouter",
            "modelId": "openrouter/auto",
            "responseMode": "default",
        },
    )
    store.append_assistant_delta(accepted.run.id, "完成")
    store.append_assistant_delta(accepted.run.id, "整理")
    completed = store.complete_run(accepted.run.id, "完成整理")

    assert completed.run.status is RunStatus.COMPLETED
    assert completed.run.partial_text == "完成整理"
    assert completed.run.assistant_message_id == completed.message.id
    assert completed.message.role == "assistant"
    assert completed.message.sequence == 2
    events = store.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    assert [event.type for event in events] == [
        RunEventType.RUN_STARTED,
        RunEventType.MODEL_STARTED,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.RUN_COMPLETED,
    ]
    assert events[2].data == {"text": "完成"}
    assert events[-1].data == {"assistantMessageId": completed.message.id}
    messages = store.list_messages(
        accepted.conversation.id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content) for item in messages.items] == [
        ("user", "整理今天的工作"),
        ("assistant", "完成整理"),
    ]


def test_event_payloads_reject_extra_secret_or_uncontracted_fields(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)

    with pytest.raises(ConversationStoreError) as captured:
        store.append_run_event(
            accepted.run.id,
            RunEventType.MODEL_STARTED,
            {
                "providerId": "openrouter",
                "modelId": "openrouter/auto",
                "responseMode": "default",
                "apiKey": "must-never-persist",
            },
        )

    assert captured.value.failure is StoreFailure.INVALID_REQUEST
    events = store.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    assert [event.type for event in events] == [RunEventType.RUN_STARTED]
    assert b"must-never-persist" not in store.database_file.read_bytes()


def test_terminal_run_allows_next_message_with_monotonic_sequence(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    first = start(store)
    store.mark_run_started(first.run.id)
    store.complete_run(first.run.id, "first answer")

    second = start(
        store,
        conversation_id=first.conversation.id,
        message="follow up",
    )

    messages = store.list_messages(
        first.conversation.id,
        limit=100,
        before_sequence=None,
    )
    assert [item.sequence for item in messages.items] == [1, 2, 3]
    assert messages.items[-1].run_id == second.run.id


def test_failure_persists_safe_error_without_assistant_message(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)
    error = PublicRunError(
        code="provider_timeout",
        message="模型廠家回應逾時。",
        retryable=True,
    )

    failed = store.fail_run(accepted.run.id, error)

    assert failed.status is RunStatus.FAILED
    assert failed.error == error
    assert failed.finished_at == NOW
    messages = store.list_messages(
        accepted.conversation.id,
        limit=100,
        before_sequence=None,
    )
    assert [item.role for item in messages.items] == ["user"]
    assert store.list_run_events(accepted.run.id, after_sequence=0, limit=100)[
        -1
    ].data == {
        "error": {
            "code": "provider_timeout",
            "message": "模型廠家回應逾時。",
            "retryable": True,
        }
    }


def test_cancel_transitions_queued_immediately_and_running_via_cancelling(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    queued = start(store)
    queued_result = store.request_cancel(queued.run.id)
    assert queued_result.status is RunStatus.CANCELLED

    running = start(store, message="another conversation")
    store.mark_run_started(running.run.id)
    cancelling = store.request_cancel(running.run.id)
    assert cancelling.status is RunStatus.CANCELLING
    cancelled = store.mark_run_cancelled(running.run.id)
    assert cancelled.status is RunStatus.CANCELLED

    with pytest.raises(ConversationStoreError) as captured:
        store.request_cancel(running.run.id)
    assert captured.value.failure is StoreFailure.RUN_NOT_ACTIVE


def test_restart_marks_every_non_terminal_run_interrupted(tmp_path: Path) -> None:
    store = repository(tmp_path)
    queued = start(store, message="queued")
    running = start(store, message="running")
    store.mark_run_started(running.run.id)
    cancelling = start(store, message="cancelling")
    store.mark_run_started(cancelling.run.id)
    store.request_cancel(cancelling.run.id)

    interrupted = store.interrupt_incomplete_runs()

    assert set(interrupted) == {queued.run.id, running.run.id, cancelling.run.id}
    for run_id in interrupted:
        run = store.get_run(run_id)
        assert run is not None
        assert run.status is RunStatus.INTERRUPTED
        assert run.error is not None
        assert run.error.retryable is True
        assert store.list_run_events(run_id, after_sequence=0, limit=100)[
            -1
        ].type is RunEventType.RUN_INTERRUPTED
    assert store.interrupt_incomplete_runs() == ()


def test_conversation_and_message_pagination_are_stable(tmp_path: Path) -> None:
    tick = iter(
        datetime(2026, 8, 21, 8, minute, tzinfo=UTC) for minute in range(10)
    )
    store = SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file,
        clock=lambda: next(tick),
    )
    created = [start(store, message=f"conversation {index}") for index in range(3)]

    first_page = store.list_conversations(limit=2, before=None)
    second_page = store.list_conversations(limit=2, before=first_page.next_cursor)

    assert [item.id for item in first_page.items] == [
        created[2].conversation.id,
        created[1].conversation.id,
    ]
    assert [item.id for item in second_page.items] == [created[0].conversation.id]
    assert second_page.next_cursor is None

    first = created[0]
    store.mark_run_started(first.run.id)
    store.complete_run(first.run.id, "answer one")
    follow = start(store, conversation_id=first.conversation.id, message="follow")
    store.mark_run_started(follow.run.id)
    store.complete_run(follow.run.id, "answer two")
    newest = store.list_messages(
        first.conversation.id,
        limit=2,
        before_sequence=None,
    )
    older = store.list_messages(
        first.conversation.id,
        limit=2,
        before_sequence=newest.next_before_sequence,
    )
    assert [item.sequence for item in newest.items] == [3, 4]
    assert [item.sequence for item in older.items] == [1, 2]
    assert older.next_before_sequence is None


def test_unknown_schema_version_and_corrupt_database_fail_closed(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    paths.data_dir.mkdir(parents=True)
    with sqlite3.connect(paths.database_file) as connection:
        connection.execute("PRAGMA user_version = 99")
    store = SqliteConversationRepository(paths.database_file, clock=lambda: NOW)

    with pytest.raises(ConversationStoreError) as captured:
        store.list_conversations(limit=50, before=None)
    assert captured.value.failure is StoreFailure.DATABASE_UNAVAILABLE

    paths.database_file.write_bytes(b"not a sqlite database")
    with pytest.raises(ConversationStoreError) as corrupt:
        store.get_run(str(uuid4()))
    assert corrupt.value.failure is StoreFailure.DATABASE_UNAVAILABLE


def test_concurrent_starts_on_distinct_conversations_do_not_lose_updates(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda index: start(store, message=f"parallel {index}"),
                range(8),
            )
        )

    assert len({result.run.id for result in results}) == 8
    assert len(store.list_conversations(limit=50, before=None).items) == 8


def test_conversation_boundary_does_not_import_api_provider_or_runtime_modules() -> None:
    source_root = (
        Path(__file__).parents[1]
        / "src"
        / "opensprite_backend"
        / "conversations"
    )
    forbidden = {
        "opensprite_backend.app",
        "opensprite_backend.runtime",
        "opensprite_backend.provider_adapters",
        "opensprite_backend.provider_connections",
        "opensprite_backend.ai_settings",
    }
    violations: list[str] = []

    for source_path in source_root.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(f"{source_path.name}: {node.module}")
            if isinstance(node, ast.Import):
                violations.extend(
                    f"{source_path.name}: {alias.name}"
                    for alias in node.names
                    if alias.name in forbidden
                )

    assert violations == []
