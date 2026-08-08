"""Application fallback used until an LLM provider is configured."""

from typing import Any, Awaitable, Callable

from ..core.contracts.llm import ChatMessage, LLMResponse
from ..core.ports.llm import LLMProvider


_UNCONFIGURED_MODEL = "unconfigured"


class UnconfiguredLLM(LLMProvider):
    """Return an empty response while the application has no configured LLM."""

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
        response_delta_callback: Callable[[str], Awaitable[None]] | None = None,
        tool_input_delta_callback: Callable[[str, str, str, int], Awaitable[None]] | None = None,
        reasoning_delta_callback: Callable[[str], Awaitable[None]] | None = None,
        request_mode: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="", model=self.get_default_model())

    def get_default_model(self) -> str:
        return _UNCONFIGURED_MODEL
