"""High-level LLM provider factory."""

from __future__ import annotations

from .base import LLMProvider
from .provider_builders import create_llm_for_spec, create_responses_llm
from .provider_specs import find_provider


def create_llm(
    api_key: str,
    model: str,
    base_url: str = "",
    provider_name: str = "",
    enabled: bool = True,
    api_mode: str | None = None,
    auth_type: str = "api_key",
    reasoning_effort: str = "",
) -> LLMProvider:
    """Create an LLM provider from runtime config values."""

    if not enabled:
        raise ValueError(f"Provider {provider_name} is disabled")

    if api_mode == "responses" or auth_type == "openai_codex_oauth":
        return create_responses_llm(
            api_key=api_key,
            model=model,
            base_url=base_url,
            provider_name=provider_name,
            reasoning_effort=reasoning_effort,
        )
    spec = find_provider(api_key, base_url, model, provider_name)
    return create_llm_for_spec(
        spec,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        reasoning_effort=reasoning_effort,
    )
