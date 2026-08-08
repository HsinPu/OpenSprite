import asyncio
import json

from opensprite.config.schema import Config, DocumentLlmConfig
from opensprite.core.contracts.persistence import StoredMessage
from opensprite.integrations.persistence.memory import MemoryStorage
from opensprite.core.contracts.llm import LLMResponse, ToolCall
from opensprite.modules.documents.user_profile import (
    UserProfileConsolidator,
    consolidate_user_profile,
)


class FakeProfileStore:
    def __init__(self):
        self.managed_block = "### Communication Preferences\n- No learned communication preferences yet."
        self.response_language_block = "- not set"
        self.processed_index = 0
        self.managed_writes: list[str] = []
        self.language_writes: list[str] = []

    def read_response_language_block(self) -> str:
        return self.response_language_block

    def write_response_language_block(self, content: str) -> None:
        self.response_language_block = content
        self.language_writes.append(content)

    def read_managed_block(self) -> str:
        return self.managed_block

    def write_managed_block(self, content: str) -> None:
        self.managed_block = content
        self.managed_writes.append(content)

    def get_processed_index(self, session_id: str) -> int:
        return self.processed_index

    def set_processed_index(self, session_id: str, index: int) -> None:
        self.processed_index = index


class FakeStorage(MemoryStorage):
    def __init__(self, messages_by_session):
        super().__init__()
        for session_id, messages in messages_by_session.items():
            self._messages[session_id].extend(messages)


class ProfileProvider:
    def __init__(self):
        self.prompts: list[str] = []
        self.tools: list[list[dict]] = []

    async def chat(self, messages, tools=None, model=None, **kwargs):
        prompt = messages[1]["content"]
        self.prompts.append(prompt)
        self.tools.append(tools)
        preference = "dark" if "dark mode" in prompt else "light"
        profile_update = f"""### Communication Preferences
- Prefers {preference} mode.

### Work Context
- No learned work context yet.

### Stable Constraints
- No learned stable constraints yet."""
        return LLMResponse(
            content="",
            model=model or "fake-model",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="save_user_profile",
                    arguments={"profile_update": profile_update},
                )
            ],
        )


class StaticProvider:
    def __init__(self, response: LLMResponse):
        self.response = response
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.calls.append({"messages": messages, "tools": tools, "model": model, "kwargs": kwargs})
        return self.response


def _profile_llm() -> DocumentLlmConfig:
    return DocumentLlmConfig(**Config.load_template_data()["user_profile"]["llm"])


def test_user_profile_consolidator_updates_separate_session_stores():
    storage = FakeStorage(
        {
            "telegram:user-a": [
                StoredMessage(role="user", content="I always use dark mode.", timestamp=1.0)
            ],
            "telegram:user-b": [
                StoredMessage(role="user", content="I always use light mode.", timestamp=1.0)
            ],
        }
    )
    stores = {
        "telegram:user-a": FakeProfileStore(),
        "telegram:user-b": FakeProfileStore(),
    }
    provider = ProfileProvider()
    consolidator = UserProfileConsolidator(
        storage=storage,
        provider=provider,
        model="fake-model",
        profile_store_factory=stores.__getitem__,
        threshold=1,
        lookback_messages=10,
        enabled=True,
        llm=_profile_llm(),
    )

    async def scenario():
        await consolidator.maybe_update("telegram:user-a")
        await consolidator.maybe_update("telegram:user-b")

    asyncio.run(scenario())

    assert "- Prefers dark mode." in stores["telegram:user-a"].read_managed_block()
    assert "- Prefers light mode." in stores["telegram:user-b"].read_managed_block()
    assert stores["telegram:user-a"].processed_index == 1
    assert stores["telegram:user-b"].processed_index == 1
    assert "Shared curator rules for USER.md" in provider.prompts[0]
    assert "Document responsibility boundaries:" in provider.prompts[0]
    assert provider.tools[0][0]["function"]["name"] == "save_user_profile"


def test_consolidate_user_profile_accepts_json_arguments_and_updates_response_language():
    store = FakeProfileStore()
    profile_update = "### Communication Preferences\n- Prefers concise answers."
    response = LLMResponse(
        content="",
        model="fake-model",
        tool_calls=[
            ToolCall(
                id="call-1",
                name="save_user_profile",
                arguments=json.dumps(
                    {
                        "profile_update": profile_update,
                        "response_language_update": "- Traditional Chinese (Taiwan)",
                    }
                ),
            )
        ],
    )
    provider = StaticProvider(response)

    result = asyncio.run(
        consolidate_user_profile(
            profile_store=store,
            messages=[{"role": "user", "content": "Always answer in Traditional Chinese."}],
            provider=provider,
            model="fake-model",
            profile_llm=_profile_llm(),
        )
    )

    assert result is True
    assert store.managed_writes == [profile_update]
    assert store.language_writes == ["- Traditional Chinese (Taiwan)"]


def test_user_profile_consolidator_advances_index_only_after_success():
    storage = FakeStorage(
        {
            "telegram:user-a": [
                StoredMessage(role="user", content="Remember this preference.", timestamp=1.0)
            ]
        }
    )
    store = FakeProfileStore()
    provider = StaticProvider(LLMResponse(content="", model="fake-model", tool_calls=[]))
    consolidator = UserProfileConsolidator(
        storage=storage,
        provider=provider,
        model="fake-model",
        profile_store_factory=lambda session_id: store,
        threshold=1,
        lookback_messages=10,
        enabled=True,
        llm=_profile_llm(),
    )

    asyncio.run(consolidator.maybe_update("telegram:user-a"))

    assert store.processed_index == 0
    assert store.managed_writes == []
    assert store.language_writes == []
