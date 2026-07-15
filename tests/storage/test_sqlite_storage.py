import asyncio

from opensprite.runs.lifecycle import RUN_STARTED_EVENT
from opensprite.storage.base import (
    StoredBackgroundProcess,
    StoredMessage,
)
from opensprite.storage.sqlite import SQLiteStorage


def test_sqlite_storage_supports_count_and_slice_reads(tmp_path):
    db_path = tmp_path / "sessions.db"
    storage = SQLiteStorage(db_path)

    async def scenario():
        for index in range(5):
            await storage.add_message(
                "chat-1",
                StoredMessage(role="user", content=f"m{index}", timestamp=float(index + 1)),
            )

        count = await storage.get_message_count("chat-1")
        middle = await storage.get_messages_slice("chat-1", start_index=1, end_index=4)
        tail = await storage.get_messages_slice("chat-1", start_index=3)
        return count, middle, tail

    count, middle, tail = asyncio.run(scenario())

    assert count == 5
    assert [message.content for message in middle] == ["m1", "m2", "m3"]
    assert [message.content for message in tail] == ["m3", "m4"]


def test_sqlite_storage_returns_recent_sessions(tmp_path):
    db_path = tmp_path / "sessions.db"
    storage = SQLiteStorage(db_path)

    async def scenario():
        await storage.add_message("web:old", StoredMessage(role="user", content="old", timestamp=10.0))
        await storage.add_message("web:new", StoredMessage(role="user", content="new", timestamp=30.0))
        await storage.create_run("web:run-latest", "run-1", status="completed", created_at=20.0)
        await storage.update_run_status("web:run-latest", "run-1", "completed", finished_at=40.0)
        all_sessions = await storage.get_recent_sessions()
        limited_sessions = await storage.get_recent_sessions(limit=2)
        return all_sessions, limited_sessions

    all_sessions, limited_sessions = asyncio.run(scenario())

    assert all_sessions == ["web:run-latest", "web:new", "web:old"]
    assert limited_sessions == ["web:run-latest", "web:new"]


def test_sqlite_storage_persists_runs_and_events(tmp_path):
    db_path = tmp_path / "runs.db"
    storage = SQLiteStorage(db_path)

    async def scenario():
        created = await storage.create_run(
            "chat-1",
            "run-1",
            status="running",
            metadata={"channel": "web"},
            created_at=10.0,
        )
        event = await storage.add_run_event(
            "chat-1",
            "run-1",
            RUN_STARTED_EVENT,
            payload={"status": "running"},
            created_at=11.0,
        )
        part = await storage.add_run_part(
            "chat-1",
            "run-1",
            "tool_call",
            content='{"action": "auto"}',
            tool_name="verify",
            metadata={"args": {"action": "auto"}},
            created_at=11.5,
        )
        file_change = await storage.add_run_file_change(
            "chat-1",
            "run-1",
            "write_file",
            "notes.txt",
            "add",
            before_sha256=None,
            after_sha256="abc123",
            before_content=None,
            after_content="hello\n",
            diff="--- /dev/null\n+++ b/notes.txt\n@@\n+hello",
            metadata={"diff_len": 42},
            created_at=11.75,
        )
        updated = await storage.update_run_status(
            "chat-1",
            "run-1",
            "completed",
            metadata={"executed_tool_calls": 0},
            finished_at=12.0,
        )
        latest = await storage.get_latest_run("chat-1")
        single_run = await storage.get_run("chat-1", "run-1")
        events = await storage.get_run_events("chat-1", "run-1")
        parts = await storage.get_run_parts("chat-1", "run-1")
        file_changes = await storage.get_run_file_changes("chat-1", "run-1")
        single_change = await storage.get_run_file_change("chat-1", "run-1", file_change.change_id)
        trace = await storage.get_run_trace("chat-1", "run-1")
        chats = await storage.get_all_sessions()
        return created, event, part, file_change, updated, latest, single_run, events, parts, file_changes, single_change, trace, chats

    created, event, part, file_change, updated, latest, single_run, events, parts, file_changes, single_change, trace, chats = asyncio.run(scenario())

    assert created is not None
    assert created.status == "running"
    assert created.metadata == {"channel": "web"}
    assert event is not None
    assert event.event_type == RUN_STARTED_EVENT
    assert event.payload == {"status": "running"}
    assert part is not None
    assert part.part_type == "tool_call"
    assert part.tool_name == "verify"
    assert part.metadata == {"args": {"action": "auto"}}
    assert file_change is not None
    assert file_change.tool_name == "write_file"
    assert file_change.path == "notes.txt"
    assert file_change.action == "add"
    assert file_change.before_sha256 is None
    assert file_change.after_sha256 == "abc123"
    assert file_change.before_content is None
    assert file_change.after_content == "hello\n"
    assert updated is not None
    assert updated.status == "completed"
    assert updated.finished_at == 12.0
    assert updated.metadata == {"channel": "web", "executed_tool_calls": 0}
    assert latest is not None
    assert latest.run_id == "run-1"
    assert latest.status == "completed"
    assert single_run is not None
    assert single_run.run_id == "run-1"
    assert [entry.event_type for entry in events] == [RUN_STARTED_EVENT]
    assert [entry.part_type for entry in parts] == ["tool_call"]
    assert parts[0].content == '{"action": "auto"}'
    assert [entry.path for entry in file_changes] == ["notes.txt"]
    assert file_changes[0].diff.startswith("--- /dev/null")
    assert file_changes[0].metadata == {"diff_len": 42}
    assert file_changes[0].after_content == "hello\n"
    assert single_change is not None
    assert single_change.path == "notes.txt"
    assert trace is not None
    assert trace.run.run_id == "run-1"
    assert [entry.event_type for entry in trace.events] == [RUN_STARTED_EVENT]
    assert [entry.part_type for entry in trace.parts] == ["tool_call"]
    assert [entry.path for entry in trace.file_changes] == ["notes.txt"]
    assert chats == ["chat-1"]


def test_sqlite_storage_persists_background_processes(tmp_path):
    async def scenario():
        storage = SQLiteStorage(tmp_path / "background-processes.db")
        started = await storage.upsert_background_process(
            StoredBackgroundProcess(
                process_session_id="proc-1",
                owner_session_id="chat-1",
                owner_run_id="run-1",
                owner_channel="web",
                owner_external_chat_id="external-1",
                pid=1234,
                command="python -m pytest",
                cwd="C:/repo",
                state="running",
                notify_mode="agent_summary",
                output_tail="collecting tests",
                output_path="C:/repo/.opensprite/proc-1.log",
                metadata={"source": "shell"},
                started_at=10.0,
                updated_at=11.0,
            )
        )
        finished = await storage.upsert_background_process(
            StoredBackgroundProcess(
                process_session_id="proc-1",
                owner_session_id="chat-1",
                owner_run_id="run-1",
                owner_channel="web",
                owner_external_chat_id="external-1",
                pid=1234,
                command="python -m pytest",
                cwd="C:/repo",
                state="completed",
                termination_reason="exited",
                exit_code=0,
                notify_mode="agent_summary",
                output_tail="2 passed",
                output_path="C:/repo/.opensprite/proc-1.log",
                metadata={"source": "shell", "summary_requested": True},
                started_at=12.0,
                updated_at=13.0,
                finished_at=14.0,
            )
        )
        await storage.upsert_background_process(
            StoredBackgroundProcess(
                process_session_id="proc-2",
                owner_session_id="chat-2",
                command="npm run build",
                state="running",
                started_at=20.0,
                updated_at=21.0,
            )
        )
        loaded = await storage.get_background_process("proc-1")
        owner_processes = await storage.list_background_processes(owner_session_id="chat-1")
        running_processes = await storage.list_background_processes(states=("running",))
        limited_processes = await storage.list_background_processes(limit=1)
        chats = await storage.get_all_sessions()
        return started, finished, loaded, owner_processes, running_processes, limited_processes, chats

    started, finished, loaded, owner_processes, running_processes, limited_processes, chats = asyncio.run(scenario())

    assert started is not None
    assert started.state == "running"
    assert started.started_at == 10.0
    assert finished is not None
    assert finished.state == "completed"
    assert finished.started_at == 10.0
    assert finished.finished_at == 14.0
    assert loaded is not None
    assert loaded.exit_code == 0
    assert loaded.output_tail == "2 passed"
    assert loaded.metadata == {"source": "shell", "summary_requested": True}
    assert [process.process_session_id for process in owner_processes] == ["proc-1"]
    assert [process.process_session_id for process in running_processes] == ["proc-2"]
    assert [process.process_session_id for process in limited_processes] == ["proc-2"]
    assert chats == ["chat-1", "chat-2"]
