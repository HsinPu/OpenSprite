import asyncio

from opensprite.config.schema import Config, DocumentLlmConfig
from opensprite.core.contracts.persistence import StoredMessage
from opensprite.integrations.documents.recent_summary import RecentSummaryStore
from opensprite.integrations.persistence.memory import MemoryStorage
from opensprite.core.contracts.llm import LLMResponse
from opensprite.modules.documents.recent_summary import (
    RecentSummaryConsolidator,
    consolidate_recent_summary,
)


class FakeProvider:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    async def chat(self, messages, tools=None, model=None, temperature=0.7, max_tokens=2048, **kwargs):
        self.calls.append({"messages": messages, "model": model})
        return LLMResponse(content=self.content, model=model or "fake-model")


class FakeStorage(MemoryStorage):
    def __init__(self, messages):
        super().__init__()
        self._messages["chat-1"].extend(messages)


def test_consolidate_recent_summary_uses_structured_prompt(tmp_path):
    app_home = tmp_path / "home"
    store = RecentSummaryStore(
        app_home / "memory",
        app_home=app_home,
        workspace_root=app_home / "workspace",
    )
    provider = FakeProvider("# Active Threads\n- finishing recent summary")

    result = asyncio.run(
        consolidate_recent_summary(
            summary_store=store,
            session_id="chat-1",
            messages=[{"role": "user", "content": "We still need the recent summary layer."}],
            provider=provider,
            model="fake-model",
            summary_llm=DocumentLlmConfig(**Config.load_template_data()["recent_summary"]["llm"]),
        )
    )

    assert result is True
    assert "# Active Threads" in store.read("chat-1")
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "Focus on medium-term context" in prompt
    assert "Shared curator rules for RECENT_SUMMARY.md" in prompt
    assert "Document responsibility boundaries:" in prompt
    assert "# Follow-ups" in prompt


def test_recent_summary_consolidator_leaves_latest_messages_unsummarized(tmp_path):
    app_home = tmp_path / "home"
    store = RecentSummaryStore(
        app_home / "memory",
        app_home=app_home,
        workspace_root=app_home / "workspace",
    )
    provider = FakeProvider("# Active Threads\n- done")
    storage = FakeStorage(
        [
            StoredMessage(role="user", content="older one", timestamp=1.0),
            StoredMessage(role="assistant", content="older two", timestamp=2.0),
            StoredMessage(role="user", content="keep raw", timestamp=3.0),
        ]
    )
    consolidator = RecentSummaryConsolidator(
        storage=storage,
        provider=provider,
        model="fake-model",
        summary_store=store,
        threshold=1,
        token_threshold=0,
        lookback_messages=10,
        keep_last_messages=1,
        enabled=True,
        llm=DocumentLlmConfig(**Config.load_template_data()["recent_summary"]["llm"]),
    )

    asyncio.run(consolidator.maybe_update("chat-1"))

    assert store.get_processed_index("chat-1") == 2
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "older one" in prompt
    assert "older two" in prompt
    assert "keep raw" not in prompt
