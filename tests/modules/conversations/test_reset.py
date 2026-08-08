import asyncio

from opensprite.core.contracts.persistence import StoredMessage
from opensprite.integrations.persistence.memory import MemoryStorage
from opensprite.modules.conversations.reset import HistoryResetService


class RecordingStorage(MemoryStorage):
    def __init__(self, events):
        super().__init__()
        self.events = events

    async def clear_messages(self, session_id: str) -> None:
        self.events.append(("storage", session_id))
        await super().clear_messages(session_id)


class RecordingSearchStore:
    def __init__(self, events):
        self.events = events

    async def clear_session(self, session_id: str) -> None:
        self.events.append(("search", session_id))


def test_history_reset_quiesces_runtime_before_clearing_persistence():
    async def scenario():
        events = []
        storage = RecordingStorage(events)
        await storage.add_message(
            "web:chat-1",
            StoredMessage(role="user", content="hello", timestamp=1.0),
        )

        async def clear_artifacts(session_id: str) -> None:
            events.append(("runtime", session_id))

        service = HistoryResetService(
            storage=storage,
            history_search_store=RecordingSearchStore(events),
            clear_session_artifacts=clear_artifacts,
        )
        await service.reset("web:chat-1")
        return events, await storage.get_messages("web:chat-1")

    events, messages = asyncio.run(scenario())

    assert events == [
        ("runtime", "web:chat-1"),
        ("storage", "web:chat-1"),
        ("search", "web:chat-1"),
    ]
    assert messages == []
