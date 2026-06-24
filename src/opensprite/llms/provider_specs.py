"""LLM provider specs and detection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..auth.copilot import COPILOT_BASE_URL


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
    "openai",
    ("gpt", "openai"),
    default_base_url="https://api.openai.com/v1",
    detect_by_model_keywords=("gpt",),
)
PROVIDERS = (
    ProviderSpec("openrouter", ("openrouter",), "sk-or-", "openrouter", "https://openrouter.ai/api/v1"),
    OPENAI_PROVIDER,
    ProviderSpec(
        "minimax",
        ("minimax",),
        detect_by_base_keyword="minimax",
        default_base_url="https://api.minimax.io/v1",
        detect_by_model_keywords=("minimax",),
    ),
    ProviderSpec("copilot", ("copilot",), detect_by_base_keyword="githubcopilot", default_base_url=COPILOT_BASE_URL),
)


def _first_detected_provider(
    predicate,
) -> ProviderSpec | None:
    return next((spec for spec in PROVIDERS if predicate(spec)), None)


def find_provider(api_key: str = "", base_url: str = "", model: str = "", provider_name: str = "") -> ProviderSpec:
    """Detect the provider from explicit config and runtime hints."""

    provider = _first_detected_provider(lambda spec: provider_name == spec.name)
    if provider:
        return provider

    provider = _first_detected_provider(
        lambda spec: bool(spec.detect_by_key_prefix and api_key.startswith(spec.detect_by_key_prefix))
    )
    if provider:
        return provider

    provider = _first_detected_provider(
        lambda spec: bool(spec.detect_by_base_keyword and spec.detect_by_base_keyword in base_url)
    )
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
