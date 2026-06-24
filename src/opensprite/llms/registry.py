"""opensprite/llms/registry.py - LLM Provider Registry

用 Registry 模式管理所有 LLM Provider，方便擴充。
"""

from .base import LLMProvider
from .provider_builders import create_llm_for_spec, create_responses_llm, provider_spec_default_base_url
from .provider_specs import PROVIDERS, ProviderSpec, find_provider


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
    """建立 LLM Provider"""
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
