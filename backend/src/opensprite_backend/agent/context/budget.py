"""Resolve user-facing context choices into deterministic token budgets."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Final

from opensprite_backend.inference.capabilities import ModelCapability
from opensprite_backend.models import ContextBudget, OutputBudget

_FIXED_LIMITS: Final = {
    "32k": 32_768,
    "64k": 65_536,
    "128k": 131_072,
    "256k": 262_144,
}
_FIXED_OUTPUT_LIMITS: Final = {
    "8k": 8_192,
    "16k": 16_384,
    "32k": 32_768,
    "64k": 65_536,
}
_AUTO_OUTPUT_CAP: Final = 32_768


@dataclass(frozen=True, slots=True)
class ContextBudgetPlan:
    requested: ContextBudget
    context_limit_tokens: int
    output_reserve_tokens: int
    safety_reserve_tokens: int
    input_budget_tokens: int
    compaction_trigger_tokens: int
    compaction_target_tokens: int
    output_requested: OutputBudget = "auto"


def _automatic_limit(model_maximum: int) -> int:
    if model_maximum <= 32_768:
        return model_maximum
    if model_maximum <= 65_536:
        return min(49_152, model_maximum)
    if model_maximum <= 131_072:
        return min(98_304, model_maximum)
    if model_maximum <= 262_144:
        return min(196_608, model_maximum)
    return min(262_144, model_maximum)


def resolve_context_budget(
    requested: ContextBudget,
    capability: ModelCapability,
    output_requested: OutputBudget = "auto",
) -> ContextBudgetPlan:
    if requested == "auto":
        context_limit = _automatic_limit(capability.context_window_tokens)
    elif requested == "max":
        context_limit = capability.context_window_tokens
    else:
        context_limit = min(_FIXED_LIMITS[requested], capability.context_window_tokens)

    safety_reserve = max(4_096, (context_limit + 9) // 10)
    minimum_input_reserve = max(1, (context_limit + 3) // 4)
    maximum_safe_output = max(
        1,
        context_limit - safety_reserve - minimum_input_reserve,
    )
    if output_requested == "auto":
        output_target = min(
            _AUTO_OUTPUT_CAP,
            max(8_192, context_limit // 4),
        )
    elif output_requested == "max":
        output_target = capability.max_output_tokens
    else:
        output_target = _FIXED_OUTPUT_LIMITS[output_requested]
    output_reserve = min(
        output_target,
        capability.max_output_tokens,
        maximum_safe_output,
    )
    input_budget = context_limit - output_reserve - safety_reserve
    if input_budget < 1:
        raise ValueError("context budget leaves no input capacity")
    return ContextBudgetPlan(
        requested=requested,
        context_limit_tokens=context_limit,
        output_reserve_tokens=output_reserve,
        safety_reserve_tokens=safety_reserve,
        input_budget_tokens=input_budget,
        compaction_trigger_tokens=max(1, floor(input_budget * 0.75)),
        compaction_target_tokens=max(1, floor(input_budget * 0.55)),
        output_requested=output_requested,
    )
