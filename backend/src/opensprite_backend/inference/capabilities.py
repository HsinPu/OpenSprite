"""Authoritative model capabilities used by context budgeting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from opensprite_backend.models import ProviderId


@dataclass(frozen=True, slots=True)
class ModelCapability:
    provider_id: ProviderId
    model_id: str
    name: str
    context_window_tokens: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        if not self.model_id or not self.name:
            raise ValueError("model identity must not be empty")
        if self.context_window_tokens < 1:
            raise ValueError("context window must be positive")
        if not 1 <= self.max_output_tokens <= self.context_window_tokens:
            raise ValueError("max output must fit within the context window")


_FIXED_CAPABILITIES: Final = {
    ("openai", "gpt-5.6"): ModelCapability(
        provider_id="openai",
        model_id="gpt-5.6",
        name="GPT-5.6",
        context_window_tokens=1_050_000,
        max_output_tokens=128_000,
    ),
    ("openai", "gpt-5.6-luna"): ModelCapability(
        provider_id="openai",
        model_id="gpt-5.6-luna",
        name="GPT-5.6 Luna",
        context_window_tokens=1_050_000,
        max_output_tokens=128_000,
    ),
    ("anthropic", "claude-sonnet-4-6"): ModelCapability(
        provider_id="anthropic",
        model_id="claude-sonnet-4-6",
        name="Claude Sonnet 4.6",
        context_window_tokens=1_000_000,
        max_output_tokens=128_000,
    ),
    ("anthropic", "claude-haiku-4-5"): ModelCapability(
        provider_id="anthropic",
        model_id="claude-haiku-4-5",
        name="Claude Haiku 4.5",
        context_window_tokens=200_000,
        max_output_tokens=64_000,
    ),
}


def fixed_model_capability(
    provider_id: ProviderId,
    model_id: str,
) -> ModelCapability | None:
    """Return one approved direct-provider capability, if known."""

    return _FIXED_CAPABILITIES.get((provider_id, model_id))


def fixed_model_catalog(provider_id: ProviderId) -> tuple[ModelCapability, ...]:
    """Return the stable catalog order for one direct provider."""

    return tuple(
        capability
        for capability in _FIXED_CAPABILITIES.values()
        if capability.provider_id == provider_id
    )
