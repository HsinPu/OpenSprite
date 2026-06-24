"""Provider profile defaults for LLM runtime resolution."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import ProviderConfig
from ..config.llm_presets import provider_profile_defaults


@dataclass(frozen=True)
class RuntimeProviderProfile:
    provider_name: str
    auth_type: str
    api_mode: str | None
    profile_base_url: str


def resolve_runtime_provider_profile(
    provider: ProviderConfig,
    *,
    provider_name: str,
) -> RuntimeProviderProfile:
    configured_provider = str(provider.provider or provider_name or "").strip()
    defaults = provider_profile_defaults(
        configured_provider,
        auth_type=provider.auth_type,
        api_mode=provider.api_mode,
    )
    return RuntimeProviderProfile(
        provider_name=defaults.provider_id,
        auth_type=defaults.auth_type,
        api_mode=defaults.api_mode,
        profile_base_url=defaults.default_base_url,
    )
