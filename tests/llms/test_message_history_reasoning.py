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


def test_message_history_prepares_prompt_history_without_turn_local_tool_results():
    storage = MemoryStorage()
    for message in [
        StoredMessage(role="user", content="older question", timestamp=1),
        StoredMessage(role="tool", content="old tool result", timestamp=2, tool_name="search_history"),
        StoredMessage(
            role="assistant",
            content="older answer",
            timestamp=3,
            metadata={"llm_reasoning_details": [{"type": "reasoning.text", "text": "prior thinking"}]},
        ),
        StoredMessage(role="user", content="current question", timestamp=4),
    ]:
        asyncio.run(storage.add_message("session-1", message))
    service = MessageHistoryService(storage=storage, search_store=None, max_history_getter=lambda: 10)

    prompt_history = asyncio.run(service.load_prompt_history("session-1", "current question"))

    assert prompt_history.loaded_messages == 4
    assert prompt_history.filtered_tool_messages == 1
    assert prompt_history.messages == [
        {"role": "user", "content": "older question"},
        {
            "role": "assistant",
            "content": "older answer",
            "reasoning_details": [{"type": "reasoning.text", "text": "prior thinking"}],
        },
    ]


def test_message_history_prepare_prompt_history_accepts_dict_messages():
    prompt_history = MessageHistoryService.prepare_prompt_history(
        [
            {"role": "user", "content": "older question"},
            {"role": "tool", "content": "tool result", "tool_call_id": "call-1"},
            {"role": "assistant", "content": "older answer", "reasoning_details": [{"type": "summary"}]},
            {"role": "user", "content": "current question"},
        ],
        current_message="current question",
    )

    assert prompt_history.loaded_messages == 4
    assert prompt_history.filtered_tool_messages == 1
    assert prompt_history.messages == [
        {"role": "user", "content": "older question"},
        {"role": "assistant", "content": "older answer", "reasoning_details": [{"type": "summary"}]},
    ]


def test_message_history_saves_visible_user_and_assistant_messages_to_storage_and_index():
    class RecordingSearchStore:
        def __init__(self):
            self.indexed = []

        async def index_message(self, **kwargs):
            self.indexed.append(kwargs)

    async def scenario():
        storage = MemoryStorage()
        search_store = RecordingSearchStore()
        service = MessageHistoryService(storage=storage, search_store=search_store, max_history_getter=lambda: 10)

        await service.save_user_message("session-1", "hello", metadata={"source": "web"})
        await service.save_assistant_message("session-1", "hi", metadata={"run_id": "run-1"})

        return await storage.get_messages("session-1"), search_store.indexed

    messages, indexed = asyncio.run(scenario())

    assert [(message.role, message.content, message.metadata) for message in messages] == [
        ("user", "hello", {"source": "web"}),
        ("assistant", "hi", {"run_id": "run-1"}),
    ]
    assert [(entry["role"], entry["content"], entry["tool_name"]) for entry in indexed] == [
        ("user", "hello", None),
        ("assistant", "hi", None),
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
