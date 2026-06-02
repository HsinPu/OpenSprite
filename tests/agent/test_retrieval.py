import asyncio

from opensprite.agent.retrieval import ProactiveRetrievalService
from opensprite.search.base import SearchHit


class _SearchStore:
    def __init__(self):
        self.calls = []

    async def search_history(self, session_id: str, query: str, limit: int = 5):
        self.calls.append((session_id, query, limit))
        return [
            SearchHit(
                id="hit-1",
                session_id=session_id,
                source_type="message",
                role="assistant",
                content="The cleanup fix touched src/cleanup.py.",
                created_at=1_700_000_000,
            )
        ]


def test_proactive_retrieval_requires_structured_decision():
    store = _SearchStore()
    service = ProactiveRetrievalService(search_store=store)

    context = asyncio.run(
        service.build_context(
            session_id="web:room-1",
            current_message="Use the earlier fix again.",
            should_retrieve=None,
        )
    )

    assert context == ""
    assert store.calls == []


def test_proactive_retrieval_formats_history_when_requested():
    store = _SearchStore()
    service = ProactiveRetrievalService(search_store=store)

    context = asyncio.run(
        service.build_context(
            session_id="web:room-1",
            current_message="Use the earlier fix again.",
            should_retrieve=True,
        )
    )

    assert "# Proactive Retrieval Context" in context
    assert "## Retrieved History" in context
    assert "src/cleanup.py" in context
    assert store.calls == [("web:room-1", "Use the earlier fix again.", 3)]
