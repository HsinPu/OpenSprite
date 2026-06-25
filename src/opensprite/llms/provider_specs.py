"""LLM provider specs and detection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..auth.copilot import COPILOT_BASE_URL
from ..config.llm_presets import provider_default_base_url as profile_default_base_url
from ..config.provider_api_modes import ANTHROPIC_MESSAGES_API_MODE
from ..config.provider_ids import COPILOT_PROVIDER_ID, MINIMAX_PROVIDER_ID, OPENAI_PROVIDER_ID, OPENROUTER_PROVIDER_ID


@dataclass(frozen=True)
class ProviderSpec:
    """Metadata for one LLM provider."""

    name: str
    keywords: tuple[str, ...]
    detect_by_key_prefix: str = ""
    detect_by_base_keyword: str = ""
    default_base_url: str = ""
    detect_by_model_keywords: tuple[str, ...] = ()


OPENAI_PROVIDER = ProviderSpec(
    OPENAI_PROVIDER_ID,
    ("gpt", "openai"),
    default_base_url="https://api.openai.com/v1",
    detect_by_model_keywords=("gpt",),
)
PROVIDERS = (
    ProviderSpec(OPENROUTER_PROVIDER_ID, ("openrouter",), "sk-or-", "openrouter", "https://openrouter.ai/api/v1"),
    OPENAI_PROVIDER,
    ProviderSpec(
        MINIMAX_PROVIDER_ID,
        ("minimax",),
        detect_by_base_keyword="minimax",
        default_base_url="https://api.minimax.io/v1",
        detect_by_model_keywords=("minimax",),
    ),
    ProviderSpec(COPILOT_PROVIDER_ID, ("copilot",), detect_by_base_keyword="githubcopilot", default_base_url=COPILOT_BASE_URL),
)


def _first_detected_provider(
    predicate,
) -> ProviderSpec | None:
    return next((spec for spec in PROVIDERS if predicate(spec)), None)


def find_provider(api_key: str = "", base_url: str = "", model: str = "", provider_name: str = "") -> ProviderSpec:
    """Detect the provider from explicit config and runtime hints."""

    detectors = (
        lambda spec: provider_name == spec.name,
        lambda spec: bool(spec.detect_by_key_prefix and api_key.startswith(spec.detect_by_key_prefix)),
        lambda spec: bool(spec.detect_by_base_keyword and spec.detect_by_base_keyword in base_url),
    )
    for detector in detectors:
        provider = _first_detected_provider(detector)
        if provider:
            return provider

    model_name = model.lower()
    provider = _first_detected_provider(
        lambda spec: bool(
            spec.detect_by_model_keywords
            and any(keyword in model_name for keyword in spec.detect_by_model_keywords)
        )
    )
    return provider or OPENAI_PROVIDER


def provider_name_default_base_url(provider_name: str) -> str:
    """Return the configured default URL for a provider name."""

    return profile_default_base_url(provider_name)


def provider_spec_default_base_url(spec: ProviderSpec, *, api_mode: str | None = None) -> str:
    """Return the runtime default URL for a provider spec."""

    profile_url = provider_name_default_base_url(spec.name)
    if spec.name == MINIMAX_PROVIDER_ID and api_mode != ANTHROPIC_MESSAGES_API_MODE:
        return spec.default_base_url
    return profile_url or spec.default_base_url
