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


def _openai_compatible_kwargs(
    spec: ProviderSpec,
    *,
    api_key: str,
    model: str,
    base_url: str,
    api_mode: str | None,
) -> dict[str, object]:
    return {
        "api_key": api_key,
        "base_url": base_url or provider_spec_default_base_url(spec, api_mode=api_mode),
        "default_model": model,
    }


def create_llm_for_spec(
    spec: ProviderSpec,
    *,
    api_key: str,
    model: str,
    base_url: str,
    api_mode: str | None,
    reasoning_effort: str,
) -> LLMProvider:
    if api_mode == "anthropic_messages" and spec.name != "minimax":
        raise ValueError("api_mode='anthropic_messages' is only supported by the MiniMax provider")

    kwargs = _openai_compatible_kwargs(
        spec,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )
    if api_mode == "anthropic_messages":
        return MiniMaxLLM(**kwargs, reasoning_effort=reasoning_effort)

    if spec.name == "openrouter":
        return OpenRouterLLM(**kwargs, reasoning_effort=reasoning_effort)

    if spec.name == "copilot":
        kwargs["default_headers"] = copilot_request_headers()
    if spec.name not in {"minimax", "copilot"}:
        kwargs["reasoning_effort"] = reasoning_effort
    return OpenAILLM(**kwargs)
