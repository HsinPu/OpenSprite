import asyncio

from opensprite.core.contracts.llm import ChatMessage, LLMResponse
from opensprite.modules.subagents.model_routing import ModelRoutedProvider


class _Provider:
    def __init__(self):
        self.requests = []
        self.provider_name = "fake"

    async def chat(self, **kwargs):
        self.requests.append(kwargs)
        return LLMResponse(content="ok", model=kwargs["model"])

    def get_default_model(self):
        return "base-model"

    def context_request_kwargs(self, *, output_token_reserve):
        return {"max_tokens": output_token_reserve}


def test_model_routed_provider_injects_delegated_model_and_forwards_request():
    provider = _Provider()
    routed = ModelRoutedProvider(provider, model="delegate-model")
    messages = [ChatMessage(role="user", content="hello")]

    response = asyncio.run(routed.chat(messages, max_tokens=128, request_mode="chat"))

    assert response.model == "delegate-model"
    assert provider.requests == [
        {
            "messages": messages,
            "tools": None,
            "model": "delegate-model",
            "max_tokens": 128,
            "status_callback": None,
            "response_delta_callback": None,
            "tool_input_delta_callback": None,
            "reasoning_delta_callback": None,
            "request_mode": "chat",
            "response_format": None,
        }
    ]


def test_model_routed_provider_preserves_explicit_model_and_provider_capabilities():
    provider = _Provider()
    routed = ModelRoutedProvider(provider, model="delegate-model")

    response = asyncio.run(routed.chat([], model="explicit-model"))

    assert response.model == "explicit-model"
    assert routed.get_default_model() == "delegate-model"
    assert routed.context_request_kwargs(output_token_reserve=64) == {"max_tokens": 64}
    assert routed.provider_name == "fake"


def test_model_routed_provider_falls_back_when_optional_context_hook_is_absent():
    provider = _Provider()
    provider.context_request_kwargs = None
    routed = ModelRoutedProvider(provider, model="")

    assert routed.get_default_model() == "base-model"
    assert routed.context_request_kwargs(output_token_reserve=64) == {}
