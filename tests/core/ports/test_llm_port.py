"""Tests for the core's provider-neutral LLM port."""

import asyncio
import inspect
from typing import get_type_hints

from opensprite.core.contracts.llm import ChatMessage, LLMResponse
from opensprite.core.ports.llm import LLMProvider


class _ConcreteProvider(LLMProvider):
    async def chat(self, messages, **kwargs):
        _ = messages, kwargs
        return LLMResponse(content="ok", model=self.get_default_model())

    def get_default_model(self) -> str:
        return "test-model"


def test_llm_provider_keeps_abstract_interface_and_signature():
    assert inspect.isabstract(LLMProvider)
    assert LLMProvider.__abstractmethods__ == {"chat", "get_default_model"}

    parameters = inspect.signature(LLMProvider.chat).parameters
    assert list(parameters) == [
        "self",
        "messages",
        "tools",
        "model",
        "max_tokens",
        "status_callback",
        "response_delta_callback",
        "tool_input_delta_callback",
        "reasoning_delta_callback",
        "request_mode",
        "response_format",
    ]
    assert all(
        parameters[name].default is None
        for name in list(parameters)[2:]
    )

    hints = get_type_hints(LLMProvider.chat)
    assert hints["messages"] == list[ChatMessage]
    assert hints["return"] is LLMResponse


def test_llm_provider_default_hooks_and_concrete_execution_are_stable():
    provider = _ConcreteProvider()

    assert provider.recover_after_error(RuntimeError("temporary")) is False
    assert provider.context_request_kwargs(output_token_reserve=512) == {}
    assert asyncio.run(provider.chat([ChatMessage(role="user", content="hello")])) == LLMResponse(
        content="ok",
        model="test-model",
    )
