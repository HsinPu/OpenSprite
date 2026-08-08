"""Application-provided LLM runtime factory contract."""

from pathlib import Path
from typing import Any, Protocol


class ResolvedLlmRuntime(Protocol):
    """Runtime metadata consumed by the agent without owning its implementation."""

    context_window_tokens: int | None


class LlmRuntimeFactory(Protocol):
    """Create configured LLM providers at the application boundary."""

    def create_configured(
        self,
        config: Any,
        *,
        fallback_app_home: str | Path | None = None,
    ) -> tuple[Any, ResolvedLlmRuntime]:
        ...

    def create_provider(
        self,
        provider_config: Any,
        *,
        provider_name: str,
        app_home: str | Path | None = None,
    ) -> tuple[Any, ResolvedLlmRuntime]:
        ...
