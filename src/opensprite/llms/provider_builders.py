"""LLM provider instance builders."""

from __future__ import annotations

from ..auth.copilot import copilot_request_headers
from ..config.provider_api_modes import ANTHROPIC_MESSAGES_API_MODE, RESPONSES_API_MODE
from ..config.provider_auth_types import OPENAI_CODEX_OAUTH_AUTH_TYPE
from .base import LLMProvider
from .minimax import MiniMaxLLM
from .openai import OpenAILLM, OpenAIResponsesLLM
from .openrouter import OpenRouterLLM
from .provider_specs import (
    COPILOT_RUNTIME_KIND,
    MINIMAX_RUNTIME_KIND,
    OPENROUTER_RUNTIME_KIND,
    ProviderSpec,
    provider_name_default_base_url,
    provider_spec_default_base_url,
)


def should_use_responses_llm(*, api_mode: str | None, auth_type: str) -> bool:
    return api_mode == RESPONSES_API_MODE or auth_type == OPENAI_CODEX_OAUTH_AUTH_TYPE


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
    if api_mode == ANTHROPIC_MESSAGES_API_MODE and not spec.supports_anthropic_messages:
        raise ValueError("api_mode='anthropic_messages' is only supported by the MiniMax provider")

    kwargs = _openai_compatible_kwargs(
        spec,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )
    if api_mode == ANTHROPIC_MESSAGES_API_MODE and spec.runtime_kind == MINIMAX_RUNTIME_KIND:
        return MiniMaxLLM(**kwargs, reasoning_effort=reasoning_effort)

    if spec.runtime_kind == OPENROUTER_RUNTIME_KIND:
        return OpenRouterLLM(**kwargs, reasoning_effort=reasoning_effort)

    if spec.runtime_kind == COPILOT_RUNTIME_KIND:
        kwargs["default_headers"] = copilot_request_headers()
    if spec.passes_reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return OpenAILLM(**kwargs)
