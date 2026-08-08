"""Provider-neutral LLM interface owned by the core."""

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from ..contracts import llm as llm_contracts


class LLMProvider(ABC):
    """Abstract interface implemented by every LLM provider."""

    @abstractmethod
    async def chat(
        self,
        messages: list[llm_contracts.ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
        response_delta_callback: Callable[[str], Awaitable[None]] | None = None,
        tool_input_delta_callback: Callable[[str, str, str, int], Awaitable[None]] | None = None,
        reasoning_delta_callback: Callable[[str], Awaitable[None]] | None = None,
        request_mode: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> llm_contracts.LLMResponse:
        """Send a provider-neutral chat request and return its response."""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Return the provider's default model name."""
        pass

    def recover_after_error(self, error: BaseException) -> bool:
        """Best-effort hook for transient provider recovery before one retry."""
        _ = error
        return False

    def context_request_kwargs(self, *, output_token_reserve: int) -> dict[str, Any]:
        """Provider-required request kwargs derived from centralized context config."""
        _ = output_token_reserve
        return {}
