"""LLM provider instance builders."""

from __future__ import annotations

from ..auth.copilot import copilot_request_headers
from .base import LLMProvider
from .minimax import MiniMaxLLM
from .openai import OpenAILLM, OpenAIResponsesLLM
from .openrouter import OpenRouterLLM
from .provider_specs import ProviderSpec, provider_name_default_base_url, provider_spec_default_base_url


def create_responses_llm(
    *,
    api_key: str,
    model: str,
    base_url: str,
    provider_name: str,
    reasoning_effort: str,
) -> LLMProvider:
    return OpenAIResponsesLLM(
        api_key=api_key,
        base_url=base_url or provider_name_default_base_url(provider_name),
        default_model=model,
        reasoning_effort=reasoning_effort,
    )


def create_llm_for_spec(
    spec: ProviderSpec,
    *,
    api_key: str,
    model: str,
    base_url: str,
    api_mode: str | None,
    reasoning_effort: str,
) -> LLMProvider:
    if api_mode == "anthropic_messages":
        if spec.name != "minimax":
            raise ValueError("api_mode='anthropic_messages' is only supported by the MiniMax provider")
        return MiniMaxLLM(
            api_key=api_key,
            base_url=base_url or provider_spec_default_base_url(spec, api_mode=api_mode),
            default_model=model,
            reasoning_effort=reasoning_effort,
        )

    if spec.name == "openrouter":
        return OpenRouterLLM(
            api_key=api_key,
            default_model=model,
            base_url=base_url or provider_spec_default_base_url(spec),
            reasoning_effort=reasoning_effort,
        )

    if spec.name == "minimax":
        return OpenAILLM(
            api_key=api_key,
            base_url=base_url or provider_spec_default_base_url(spec, api_mode=api_mode),
            default_model=model,
        )

    if spec.name == "copilot":
        return OpenAILLM(
            api_key=api_key,
            base_url=base_url or provider_spec_default_base_url(spec),
            default_model=model,
            default_headers=copilot_request_headers(),
        )

    return OpenAILLM(
        api_key=api_key,
        base_url=base_url or provider_spec_default_base_url(spec),
        default_model=model,
        reasoning_effort=reasoning_effort,
    )
