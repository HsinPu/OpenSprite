from datetime import UTC, datetime

import pytest

from opensprite_backend.agent.context import (
    ConservativeTokenCounter,
    ContextAssembler,
    ContextBudgetPlan,
    ContextLimitExceeded,
    resolve_context_budget,
)
from opensprite_backend.conversations.models import Message
from opensprite_backend.inference.capabilities import ModelCapability
from opensprite_backend.inference.models import (
    ModelMessage,
    ModelToolCall,
    ModelToolDefinition,
)


def capability(maximum: int = 262_144) -> ModelCapability:
    return ModelCapability(
        provider_id="openai",
        model_id="test",
        name="Test",
        context_window_tokens=maximum,
        max_output_tokens=min(128_000, maximum),
    )


def plan(*, input_budget: int, trigger: int) -> ContextBudgetPlan:
    return ContextBudgetPlan(
        requested="auto",
        context_limit_tokens=input_budget + 10_000,
        output_reserve_tokens=8_192,
        safety_reserve_tokens=1_808,
        input_budget_tokens=input_budget,
        compaction_trigger_tokens=trigger,
        compaction_target_tokens=max(1, trigger // 2),
    )


def message(sequence: int, content: str | None = None) -> Message:
    return Message(
        id=f"message-{sequence}",
        conversation_id="conversation",
        run_id=f"run-{sequence}",
        role="user" if sequence % 2 else "assistant",
        content=content or f"message {sequence}",
        sequence=sequence,
        created_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("requested", "maximum", "expected"),
    [
        ("auto", 32_768, 32_768),
        ("auto", 65_536, 49_152),
        ("auto", 131_072, 98_304),
        ("auto", 262_144, 196_608),
        ("auto", 1_050_000, 262_144),
        ("128k", 65_536, 65_536),
        ("max", 200_000, 200_000),
    ],
)
def test_budget_resolves_user_choices_with_output_and_safety_reserves(
    requested: str,
    maximum: int,
    expected: int,
) -> None:
    result = resolve_context_budget(requested, capability(maximum))  # type: ignore[arg-type]

    assert result.context_limit_tokens == expected
    assert result.output_reserve_tokens <= 8_192
    assert result.safety_reserve_tokens >= 4_096
    assert result.input_budget_tokens > 0
    assert result.compaction_target_tokens < result.compaction_trigger_tokens
    assert result.compaction_trigger_tokens < result.input_budget_tokens


def test_counter_includes_tool_definitions_calls_and_results() -> None:
    counter = ConservativeTokenCounter()
    tool = ModelToolDefinition(
        name="search",
        description="Search local records",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    plain = (ModelMessage(role="system", content="System"),)
    with_tools = (
        *plain,
        ModelMessage(
            role="assistant",
            content="Searching",
            tool_calls=(ModelToolCall(call_id="call-1", name="search", arguments={"query": "工作"}),),
        ),
        ModelMessage(
            role="tool",
            content="結果",
            tool_call_id="call-1",
            tool_name="search",
        ),
    )

    assert counter.request(with_tools, (tool,)) > counter.request(plain, ())


def test_assembler_keeps_recent_messages_and_marks_older_context_for_compaction() -> None:
    history = tuple(message(sequence, "x" * 90) for sequence in range(1, 21))
    assembler = ContextAssembler(recent_message_floor=4)
    counter = ConservativeTokenCounter()
    required_tokens = counter.request(
        (ModelMessage(role="system", content="System"), *(
            ModelMessage(role=item.role, content=item.content) for item in history[-4:]
        )),
        (),
    )
    result = assembler.assemble(
        system_prompt="System",
        history=history,
        tools=(),
        budget=plan(input_budget=required_tokens + 200, trigger=required_tokens + 1),
    )

    assert [item.content for item in result.messages[-4:]] == [
        item.content for item in history[-4:]
    ]
    assert result.included_message_count == 4
    assert result.first_included_sequence == 17
    assert result.omitted_before_sequence == 17
    assert result.needs_compaction is True


def test_assembler_fails_instead_of_silently_dropping_required_recent_context() -> None:
    history = tuple(message(sequence, "重要" * 100) for sequence in range(1, 5))

    with pytest.raises(ContextLimitExceeded):
        ContextAssembler(recent_message_floor=4).assemble(
            system_prompt="System",
            history=history,
            tools=(),
            budget=plan(input_budget=20, trigger=15),
        )


def test_assembler_rejects_unordered_history() -> None:
    with pytest.raises(ValueError, match="strictly ordered"):
        ContextAssembler().assemble(
            system_prompt="System",
            history=(message(2), message(1)),
            tools=(),
            budget=plan(input_budget=1000, trigger=750),
        )
