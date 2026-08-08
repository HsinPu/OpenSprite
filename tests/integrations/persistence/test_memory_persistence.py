"""Behavior checks for the in-memory persistence adapter."""

import asyncio
from types import SimpleNamespace

from opensprite.app.agent.agent import AgentLoop
from opensprite.app.storage import create_storage
from opensprite.core.contracts.persistence import (
    StoredBackgroundProcess,
    StoredMessage,
)
from opensprite.core.ports.storage import StorageProvider
from opensprite.integrations.persistence.memory import MemoryStorage


def test_memory_storage_implements_core_port_and_composition_uses_canonical_adapter():
    config = SimpleNamespace(storage=SimpleNamespace(type="memory", path="unused"))

    configured_storage = create_storage(config)
    fallback_storage = AgentLoop.__new__(AgentLoop)._setup_storage(None)

    assert type(configured_storage) is MemoryStorage
    assert isinstance(configured_storage, StorageProvider)
    assert type(fallback_storage) is MemoryStorage
    assert isinstance(fallback_storage, StorageProvider)


def test_memory_storage_preserves_order_and_clears_session_owned_state():
    async def scenario():
        storage = MemoryStorage()
        await storage.add_message(
            "web:chat-1",
            StoredMessage(role="user", content="first", timestamp=10.0),
        )
        await storage.add_message(
            "web:chat-1",
            StoredMessage(role="assistant", content="second", timestamp=20.0),
        )
        await storage.set_consolidated_index("web:chat-1", 1)
        await storage.create_run(
            "web:chat-1",
            "run-1",
            metadata={"channel": "web"},
            created_at=30.0,
        )
        await storage.add_run_event(
            "web:chat-1",
            "run-1",
            "run.started",
            payload={"status": "running"},
            created_at=31.0,
        )
        await storage.add_run_part(
            "web:chat-1",
            "run-1",
            "assistant_text",
            content="working",
            created_at=32.0,
        )
        await storage.add_run_file_change(
            "web:chat-1",
            "run-1",
            "write_file",
            "notes.txt",
            "add",
            after_content="hello\n",
            created_at=33.0,
        )
        await storage.upsert_background_process(
            StoredBackgroundProcess(
                process_session_id="process-1",
                owner_session_id="web:chat-1",
                owner_run_id="run-1",
                command="python -m pytest",
                state="running",
                started_at=34.0,
                updated_at=35.0,
            )
        )

        before_clear = {
            "messages": await storage.get_messages("web:chat-1"),
            "count": await storage.get_message_count("web:chat-1"),
            "slice": await storage.get_messages_slice(
                "web:chat-1",
                start_index=1,
            ),
            "consolidated_index": await storage.get_consolidated_index("web:chat-1"),
            "trace": await storage.get_run_trace("web:chat-1", "run-1"),
            "process": await storage.get_background_process("process-1"),
            "sessions": await storage.get_all_sessions(),
        }

        await storage.clear_messages("web:chat-1")

        after_clear = {
            "messages": await storage.get_messages("web:chat-1"),
            "count": await storage.get_message_count("web:chat-1"),
            "consolidated_index": await storage.get_consolidated_index("web:chat-1"),
            "run": await storage.get_run("web:chat-1", "run-1"),
            "process": await storage.get_background_process("process-1"),
            "sessions": await storage.get_all_sessions(),
        }
        return before_clear, after_clear

    before_clear, after_clear = asyncio.run(scenario())

    assert [message.content for message in before_clear["messages"]] == ["first", "second"]
    assert before_clear["count"] == 2
    assert [message.content for message in before_clear["slice"]] == ["second"]
    assert before_clear["consolidated_index"] == 1
    assert before_clear["trace"] is not None
    assert [event.event_type for event in before_clear["trace"].events] == ["run.started"]
    assert [part.content for part in before_clear["trace"].parts] == ["working"]
    assert [change.path for change in before_clear["trace"].file_changes] == ["notes.txt"]
    assert before_clear["process"] is not None
    assert before_clear["sessions"] == ["web:chat-1"]

    assert after_clear == {
        "messages": [],
        "count": 0,
        "consolidated_index": 0,
        "run": None,
        "process": None,
        "sessions": [],
    }
