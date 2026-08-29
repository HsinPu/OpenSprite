"""Select the newest complete persisted conversation that fits one budget."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from opensprite_backend.conversations.models import Message
from opensprite_backend.inference.models import ModelMessage, ModelToolDefinition

from .budget import ContextBudgetPlan
from .counter import ConservativeTokenCounter


class ContextLimitExceeded(Exception):
    """Required recent context cannot fit without silent truncation."""


@dataclass(frozen=True, slots=True)
class AssembledContext:
    messages: tuple[ModelMessage, ...]
    estimated_input_tokens: int
    included_message_count: int
    first_included_sequence: int | None
    omitted_before_sequence: int | None
    needs_compaction: bool


class ContextAssembler:
    def __init__(
        self,
        counter: ConservativeTokenCounter | None = None,
        *,
        recent_message_floor: int = 12,
        max_model_messages: int = 256,
    ) -> None:
        if not 1 <= recent_message_floor <= 64:
            raise ValueError("invalid recent message floor")
        if not 2 <= max_model_messages <= 256:
            raise ValueError("invalid model message bound")
        self._counter = counter or ConservativeTokenCounter()
        self._recent_message_floor = recent_message_floor
        self._max_model_messages = max_model_messages

    def assemble(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        tools: tuple[ModelToolDefinition, ...],
        budget: ContextBudgetPlan,
    ) -> AssembledContext:
        if not system_prompt:
            raise ValueError("system prompt must not be empty")
        if any(
            index > 0 and history[index - 1].sequence >= message.sequence
            for index, message in enumerate(history)
        ):
            raise ValueError("history must be strictly ordered")

        system = ModelMessage(role="system", content=system_prompt)
        converted = tuple(
            ModelMessage(role=message.role, content=message.content)
            for message in history
        )
        floor_start = max(0, len(converted) - self._recent_message_floor)
        required = converted[floor_start:]
        required_messages = (system, *required)
        required_tokens = self._counter.request(required_messages, tools)
        if (
            required_tokens > budget.input_budget_tokens
            or len(required_messages) > self._max_model_messages
        ):
            raise ContextLimitExceeded

        selected_start = floor_start
        selected = list(required)
        estimated = required_tokens
        while selected_start > 0 and len(selected) + 1 < self._max_model_messages:
            candidate = converted[selected_start - 1]
            candidate_tokens = self._counter.message(candidate)
            if estimated + candidate_tokens > budget.compaction_trigger_tokens:
                break
            selected_start -= 1
            selected.insert(0, candidate)
            estimated += candidate_tokens

        first_sequence = history[selected_start].sequence if selected else None
        omitted_before = first_sequence if selected_start > 0 else None
        return AssembledContext(
            messages=(system, *selected),
            estimated_input_tokens=estimated,
            included_message_count=len(selected),
            first_included_sequence=first_sequence,
            omitted_before_sequence=omitted_before,
            needs_compaction=selected_start > 0,
        )
