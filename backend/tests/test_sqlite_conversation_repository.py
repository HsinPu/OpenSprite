"""Durability and state-transition tests for the minimal chat database."""

from __future__ import annotations

import ast
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import (
    CompletionReason,
    OutputContinuation,
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
    context_budget: str = "auto",
    output_budget: str = "auto",
    output_continuation: OutputContinuation = "5",
):
    return store.start_run(
        conversation_id=conversation_id,
        client_request_id=client_request_id or str(uuid4()),
        message=message,
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget=context_budget,
        output_budget=output_budget,
        output_continuation=output_continuation,
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
    assert accepted.run.context_budget == "auto"
    assert accepted.run.output_budget == "auto"
    assert accepted.run.output_continuation == "5"
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


def test_start_snapshots_output_continuation_policy(tmp_path: Path) -> None:
    store = repository(tmp_path)

    accepted = start(store, output_continuation="unlimited")

    assert accepted.run.output_continuation == "unlimited"
    persisted = store.get_run(accepted.run.id)
    assert persisted is not None
    assert persisted.output_continuation == "unlimited"


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
            "maxOutputTokens": 32_768,
        },
    )
    store.append_assistant_delta(accepted.run.id, "完成")
    store.append_assistant_delta(accepted.run.id, "整理")
    completed = store.complete_run(accepted.run.id, "完成整理")

    assert completed.run.status is RunStatus.COMPLETED
    assert completed.run.completion_reason is CompletionReason.STOP
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
    assert events[-1].data == {
        "assistantMessageId": completed.message.id,
        "completionReason": "stop",
    }
    messages = store.list_messages(
        accepted.conversation.id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content) for item in messages.items] == [
        ("user", "整理今天的工作"),
        ("assistant", "完成整理"),
    ]


def test_multibyte_assistant_delta_is_split_to_fit_event_payload(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)
    text = "😀" * 16_384

    store.append_assistant_delta(accepted.run.id, text)

    events = store.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    deltas = [event for event in events if event.type is RunEventType.ASSISTANT_DELTA]
    assert len(deltas) > 1
    assert "".join(str(event.data["text"]) for event in deltas) == text
    assert all(
        len(
            json.dumps(
                event.data,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ) <= 65_536
        for event in deltas
    )
    persisted = store.get_run(accepted.run.id)
    assert persisted is not None
    assert persisted.partial_text == text


def test_model_event_context_usage_is_persisted_and_bounded(tmp_path: Path) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)
    data = {
        "providerId": "openrouter",
        "modelId": "openrouter/auto",
        "responseMode": "default",
        "maxOutputTokens": 32_768,
        "contextTokens": 4_096,
        "contextLimitTokens": 262_144,
        "inputBudgetTokens": 196_608,
    }

    event = store.append_run_event(
        accepted.run.id,
        RunEventType.MODEL_STARTED,
        data,
    )

    assert event.data == data
    for invalid in (
        {**data, "contextTokens": 0},
        {**data, "contextTokens": 200_000, "inputBudgetTokens": 100},
        {**data, "contextLimitTokens": 4_000_001},
    ):
        with pytest.raises(ConversationStoreError) as captured:
            store.append_run_event(
                accepted.run.id,
                RunEventType.MODEL_STARTED,
                invalid,
            )
        assert captured.value.failure is StoreFailure.INVALID_REQUEST


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
                "maxOutputTokens": 32_768,
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


def test_context_budget_and_compactions_are_durable_and_monotonic(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store, context_budget="128k")
    assert accepted.run.context_budget == "128k"

    first = store.append_compaction(
        conversation_id=accepted.conversation.id,
        covers_through_sequence=1,
        summary="Goals and constraints\nKeep the recent conversation.",
        source_hash="a" * 64,
        provider_id="openrouter",
        model_id="openrouter/auto",
        input_tokens=120,
        output_tokens=30,
    )
    assert store.get_latest_compaction(accepted.conversation.id) == first
    assert [
        item.sequence
        for item in store.list_messages_after(
            accepted.conversation.id,
            after_sequence=0,
            limit=10,
        )
    ] == [1]

    with pytest.raises(ConversationStoreError) as captured:
        store.append_compaction(
            conversation_id=accepted.conversation.id,
            covers_through_sequence=1,
            summary="duplicate",
            source_hash="b" * 64,
            provider_id="openrouter",
            model_id="openrouter/auto",
            input_tokens=1,
            output_tokens=1,
        )
    assert captured.value.failure is StoreFailure.INVALID_STATE
    assert store.list_messages(
        accepted.conversation.id,
        limit=100,
        before_sequence=None,
    ).items[0].content == "整理今天的工作"


def test_schema_v1_is_upgraded_narrowly_without_losing_existing_run(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE conversation_compactions")
        connection.execute("ALTER TABLE runs DROP COLUMN output_budget")
        connection.execute("ALTER TABLE runs DROP COLUMN completion_reason")
        connection.execute("ALTER TABLE runs DROP COLUMN context_budget")
        connection.execute("PRAGMA user_version = 1")

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    upgraded.interrupt_incomplete_runs()

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10
        assert connection.execute(
            "SELECT context_budget FROM runs WHERE id = ?",
            (accepted.run.id,),
        ).fetchone()[0] == "auto"
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'conversation_compactions'"
        ).fetchone()[0] == "conversation_compactions"


def test_schema_v2_event_table_is_upgraded_without_losing_events(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE runs DROP COLUMN output_budget")
        connection.execute("ALTER TABLE runs DROP COLUMN completion_reason")
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            ALTER TABLE run_events RENAME TO run_events_v3;
            CREATE TABLE run_events (
                run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                sequence INTEGER NOT NULL CHECK(sequence >= 1),
                type TEXT NOT NULL CHECK(type IN (
                    'run.started', 'model.started', 'assistant.delta',
                    'tool.started', 'tool.completed', 'tool.failed',
                    'run.completed', 'run.failed', 'run.cancelled',
                    'run.interrupted'
                )),
                payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
                created_at TEXT NOT NULL,
                PRIMARY KEY(run_id, sequence)
            ) STRICT;
            INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
            SELECT run_id, sequence, type, payload_json, created_at
            FROM run_events_v3;
            DROP TABLE run_events_v3;
            PRAGMA user_version = 2;
            COMMIT;
            """
        )

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    event = upgraded.append_run_event(
        accepted.run.id,
        RunEventType.CONTEXT_COMPACTION_STARTED,
        {},
    )

    assert event.type is RunEventType.CONTEXT_COMPACTION_STARTED
    assert [
        item.type
        for item in upgraded.list_run_events(
            accepted.run.id,
            after_sequence=0,
            limit=100,
        )
    ] == [
        RunEventType.RUN_STARTED,
        RunEventType.CONTEXT_COMPACTION_STARTED,
    ]
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10


def test_schema_v3_completion_metadata_is_upgraded_without_losing_run(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)
    completed = store.complete_run(accepted.run.id, "existing answer")
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE runs DROP COLUMN output_budget")
        connection.execute("ALTER TABLE runs DROP COLUMN completion_reason")
        connection.execute(
            "UPDATE run_events SET payload_json = ? WHERE run_id = ? AND type = 'run.completed'",
            (
                json.dumps(
                    {"assistantMessageId": completed.message.id},
                    separators=(",", ":"),
                ),
                accepted.run.id,
            ),
        )
        connection.execute("PRAGMA user_version = 3")

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    upgraded.interrupt_incomplete_runs()

    run = upgraded.get_run(accepted.run.id)
    assert run is not None
    assert run.status is RunStatus.COMPLETED
    assert run.completion_reason is CompletionReason.STOP
    events = upgraded.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    assert events[-1].data == {
        "assistantMessageId": completed.message.id,
        "completionReason": "stop",
    }
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10


def test_schema_v4_output_budget_and_model_event_are_upgraded(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    store.mark_run_started(accepted.run.id)
    store.append_run_event(
        accepted.run.id,
        RunEventType.MODEL_STARTED,
        {
            "providerId": "openrouter",
            "modelId": "openrouter/auto",
            "responseMode": "default",
            "maxOutputTokens": 8_192,
        },
    )
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE runs DROP COLUMN output_budget")
        connection.execute(
            "UPDATE run_events SET payload_json = json_remove(payload_json, '$.maxOutputTokens') WHERE type = 'model.started'"
        )
        connection.execute("PRAGMA user_version = 4")

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    upgraded.interrupt_incomplete_runs()

    run = upgraded.get_run(accepted.run.id)
    assert run is not None
    assert run.output_budget == "auto"
    events = upgraded.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    model_event = next(item for item in events if item.type is RunEventType.MODEL_STARTED)
    assert model_event.data["maxOutputTokens"] == 8_192
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10


def test_schema_v5_adds_default_continuation_policy_without_losing_run(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE runs DROP COLUMN output_continuation")
        connection.execute("ALTER TABLE runs DROP COLUMN log_full_prompts")
        connection.execute("PRAGMA user_version = 5")

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    upgraded.interrupt_incomplete_runs()
    run = upgraded.get_run(accepted.run.id)

    assert run is not None
    assert run.output_continuation == "2"
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10


@pytest.mark.parametrize(("enabled", "expected"), [(0, "off"), (1, "2")])
def test_schema_v7_converts_boolean_continuation_without_losing_run(
    tmp_path: Path,
    enabled: int,
    expected: OutputContinuation,
) -> None:
    store = repository(tmp_path)
    accepted = start(store)
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute(
            "ALTER TABLE runs ADD COLUMN auto_continue_output INTEGER NOT NULL "
            f"DEFAULT {enabled} CHECK(auto_continue_output IN (0, 1))"
        )
        connection.execute("ALTER TABLE runs DROP COLUMN output_continuation")
        connection.execute("PRAGMA user_version = 7")

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    upgraded.interrupt_incomplete_runs()
    run = upgraded.get_run(accepted.run.id)

    assert run is not None
    assert run.output_continuation == expected
    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        assert "output_continuation" in columns
        assert "auto_continue_output" not in columns
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10


def test_schema_v9_expands_continuation_values_without_losing_run(
    tmp_path: Path,
) -> None:
    store = repository(tmp_path)
    accepted = start(store, output_continuation="2")
    store.mark_run_started(accepted.run.id)
    store.append_run_event(accepted.run.id, RunEventType.MODEL_STARTED, {
        "providerId": "openrouter",
        "modelId": "openrouter/auto",
        "responseMode": "default",
        "maxOutputTokens": 8192,
    })
    database = store.database_file
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 9")

    upgraded = SqliteConversationRepository(database, clock=lambda: NOW)
    upgraded.interrupt_incomplete_runs()

    preserved = upgraded.get_run(accepted.run.id)
    assert preserved is not None
    assert preserved.output_continuation == "2"
    assert upgraded.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    expanded = start(upgraded, output_continuation="50")
    assert expanded.run.output_continuation == "50"
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10
        runs_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'runs'"
        ).fetchone()[0]
    assert "'10', '20', '50'" in runs_sql


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
        "opensprite_backend.providers.adapters",
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
