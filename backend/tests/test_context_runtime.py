import asyncio
from collections.abc import AsyncIterator

import pytest

from opensprite_backend.agent.context import (
    GatewaySummaryGenerator,
    ModelCapabilityNotFound,
)
from opensprite_backend.model_capability_resolver import ProviderModelCapabilityResolver
from opensprite_backend.inference.models import (
    ModelCompleted,
    ModelFinishReason,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelUsage,
)
from opensprite_backend.models import OpenRouterModel, OpenRouterModelListResponse


class RecordingConnections:
    def __init__(self) -> None:
        self.calls = 0

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
        self.calls += 1
        return OpenRouterModelListResponse(
            models=[
                OpenRouterModel(
                    id="acme/model",
                    name="Acme",
                    contextWindowTokens=131_072,
                    maxOutputTokens=None,
                )
            ]
        )


def test_capability_resolver_uses_fixed_catalog_and_session_cache() -> None:
    async def scenario() -> None:
        connections = RecordingConnections()
        resolver = ProviderModelCapabilityResolver(connections)  # type: ignore[arg-type]

        fixed = await resolver.resolve("openai", "gpt-5.6")
        first = await resolver.resolve("openrouter", "acme/model")
        second = await resolver.resolve("openrouter", "acme/model")

        assert fixed.context_window_tokens == 1_050_000
        assert first == second
        assert first.context_window_tokens == 131_072
        assert first.max_output_tokens == 8_192
        assert connections.calls == 1

    asyncio.run(scenario())


def test_capability_resolver_rejects_unknown_models() -> None:
    async def scenario() -> None:
        resolver = ProviderModelCapabilityResolver(RecordingConnections())  # type: ignore[arg-type]
        with pytest.raises(ModelCapabilityNotFound):
            await resolver.resolve("anthropic", "unknown")
        with pytest.raises(ModelCapabilityNotFound):
            await resolver.resolve("openrouter", "unknown")

    asyncio.run(scenario())


class SummaryGateway:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        self.requests.append(request)
        yield ModelTextDelta("Goals and constraints\nKeep context.")
        yield ModelUsage(120, 20)
        yield ModelCompleted(ModelFinishReason.FINAL)


def test_summary_generator_is_bounded_and_never_exposes_tools() -> None:
    async def scenario() -> None:
        gateway = SummaryGateway()
        result = await GatewaySummaryGenerator(gateway).generate(
            provider_id="openai",
            model_id="gpt-5.6",
            prompt="historical data",
        )

        assert result.summary.startswith("Goals and constraints")
        assert result.input_tokens == 120
        assert result.output_tokens == 20
        assert gateway.requests[0].tools == ()
        assert gateway.requests[0].max_output_tokens == 2_048
        assert gateway.requests[0].response_mode == "default"

    asyncio.run(scenario())
