import asyncio

from opensprite.context.message_history import MessageHistoryService
from opensprite.llms import ChatMessage
from opensprite.runs.events import SEARCH_INDEX_MESSAGE_FAILED_EVENT
from opensprite.storage import MemoryStorage, StoredMessage


def test_message_history_restores_reasoning_details_from_metadata():
    storage = MemoryStorage()
    asyncio.run(
        storage.add_message(
            "session-1",
            StoredMessage(
                role="assistant",
                content="final answer",
                timestamp=1,
                metadata={"llm_reasoning_details": [{"type": "reasoning.text", "text": "thinking"}]},
            ),
        )
    )
    service = MessageHistoryService(storage=storage, search_store=None, max_history_getter=lambda: 10)

    history = asyncio.run(service.load_history("session-1"))

    assert history == [
        ChatMessage(
            role="assistant",
            content="final answer",
            reasoning_details=[{"type": "reasoning.text", "text": "thinking"}],
        )
    ]


def test_message_history_emits_search_index_failure_event():
    class FailingSearchStore:
        async def index_message(self, **kwargs):
            raise RuntimeError("index down")

    async def scenario():
        storage = MemoryStorage()
        events = []

        async def emit_index_failure(session_id, event_type, payload):
            events.append((session_id, event_type, payload))

        service = MessageHistoryService(
            storage=storage,
            search_store=FailingSearchStore(),
            max_history_getter=lambda: 10,
            emit_index_failure=emit_index_failure,
        )
        await service.save_message("session-1", "user", "hello", tool_name=None)
        return events

    events = asyncio.run(scenario())

    assert len(events) == 1
    assert events[0][0] == "session-1"
    assert events[0][1] == SEARCH_INDEX_MESSAGE_FAILED_EVENT
    assert events[0][2]["role"] == "user"
    assert events[0][2]["content_len"] == 5
    assert events[0][2]["error"] == "index down"
