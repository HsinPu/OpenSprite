from dataclasses import fields

from opensprite.core.contracts.persistence import (
    StoredBackgroundProcess,
    StoredMessage,
    StoredRun,
    StoredRunEvent,
    StoredRunFileChange,
    StoredRunPart,
    StoredRunTrace,
)


def test_persistence_contract_field_order_is_stable():
    expected_fields = {
        StoredMessage: (
            "role",
            "content",
            "timestamp",
            "tool_name",
            "is_consolidated",
            "metadata",
        ),
        StoredRun: (
            "run_id",
            "session_id",
            "status",
            "created_at",
            "updated_at",
            "finished_at",
            "metadata",
        ),
        StoredRunEvent: (
            "run_id",
            "session_id",
            "event_type",
            "payload",
            "created_at",
            "event_id",
        ),
        StoredRunPart: (
            "run_id",
            "session_id",
            "part_type",
            "content",
            "tool_name",
            "metadata",
            "created_at",
            "part_id",
        ),
        StoredRunFileChange: (
            "run_id",
            "session_id",
            "tool_name",
            "path",
            "action",
            "before_sha256",
            "after_sha256",
            "before_content",
            "after_content",
            "diff",
            "metadata",
            "created_at",
            "change_id",
        ),
        StoredRunTrace: ("run", "events", "parts", "file_changes"),
        StoredBackgroundProcess: (
            "process_session_id",
            "owner_session_id",
            "command",
            "state",
            "started_at",
            "updated_at",
            "owner_run_id",
            "owner_channel",
            "owner_external_chat_id",
            "pid",
            "cwd",
            "termination_reason",
            "exit_code",
            "notify_mode",
            "output_tail",
            "output_path",
            "metadata",
            "finished_at",
        ),
    }

    assert {
        contract: tuple(field.name for field in fields(contract))
        for contract in expected_fields
    } == expected_fields


def test_persistence_contract_mutable_defaults_are_isolated():
    first_message = StoredMessage(role="user", content="one", timestamp=1.0)
    second_message = StoredMessage(role="user", content="two", timestamp=2.0)
    first_message.metadata["source"] = "first"

    run = StoredRun(
        run_id="run-1",
        session_id="session-1",
        status="running",
        created_at=1.0,
        updated_at=1.0,
    )
    first_trace = StoredRunTrace(run=run)
    second_trace = StoredRunTrace(run=run)
    first_trace.events.append(
        StoredRunEvent(run_id="run-1", session_id="session-1", event_type="started")
    )

    assert second_message.metadata == {}
    assert second_trace.events == []
