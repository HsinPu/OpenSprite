"""Tool registration, schema, policy, timeout, and output-bound tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import wraps

import pytest

from opensprite_backend.tools.definition import (
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
)
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import (
    ToolInvocationError,
    ToolRegistry,
    ToolRegistryError,
)


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def query_definition(
    *,
    name: str = "lookup_note",
    effect: ToolEffect = ToolEffect.READ_ONLY,
    timeout_seconds: float = 1,
    max_output_chars: int = 1024,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="Read one note by query.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 50,
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        effect=effect,
        timeout_seconds=timeout_seconds,
        max_output_chars=max_output_chars,
    )


@dataclass
class RecordingTool:
    definition: ToolDefinition
    result: ToolResult = ToolResult(content="note body", summary="找到 1 筆筆記")
    calls: int = 0

    async def invoke(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult:
        assert arguments == {"query": "today"}
        assert context.run_id == "run-id"
        self.calls += 1
        return self.result


def context() -> ToolContext:
    return ToolContext(
        run_id="run-id",
        conversation_id="conversation-id",
        cancellation_event=asyncio.Event(),
    )


@async_test
async def test_explicit_read_only_tool_invocation_returns_bounded_result() -> None:
    tool = RecordingTool(query_definition())
    registry = ToolRegistry([tool], policy=ReadOnlyToolPolicy())

    result = await registry.invoke("lookup_note", {"query": "today"}, context())

    assert result == ToolResult(content="note body", summary="找到 1 筆筆記")
    assert tool.calls == 1
    assert [item.name for item in registry.definitions()] == ["lookup_note"]


@async_test
async def test_unknown_tool_and_extra_arguments_fail_before_execution() -> None:
    tool = RecordingTool(query_definition())
    registry = ToolRegistry([tool], policy=ReadOnlyToolPolicy())

    with pytest.raises(ToolInvocationError) as unknown:
        await registry.invoke("missing", {}, context())
    with pytest.raises(ToolInvocationError) as invalid:
        await registry.invoke(
            "lookup_note",
            {"query": "today", "apiKey": "must-not-pass"},
            context(),
        )

    assert unknown.value.code == "tool_not_found"
    assert invalid.value.code == "tool_invalid_arguments"
    assert tool.calls == 0
    assert "must-not-pass" not in str(invalid.value)


@async_test
async def test_default_policy_denies_write_effect_without_invoking_tool() -> None:
    tool = RecordingTool(query_definition(effect=ToolEffect.LOCAL_WRITE))
    registry = ToolRegistry([tool], policy=ReadOnlyToolPolicy())

    with pytest.raises(ToolInvocationError) as captured:
        await registry.invoke("lookup_note", {"query": "today"}, context())

    assert captured.value.code == "tool_denied"
    assert tool.calls == 0


@async_test
async def test_tool_timeout_and_oversized_output_fail_closed() -> None:
    class SlowTool(RecordingTool):
        async def invoke(
            self,
            arguments: dict[str, object],
            context: ToolContext,
        ) -> ToolResult:
            del arguments, context
            await asyncio.sleep(1)
            return self.result

    slow = SlowTool(query_definition(name="slow_note", timeout_seconds=0.01))
    oversized = RecordingTool(
        query_definition(name="large_note", max_output_chars=4),
        result=ToolResult(content="too large", summary="large"),
    )
    registry = ToolRegistry([slow, oversized], policy=ReadOnlyToolPolicy())

    with pytest.raises(ToolInvocationError) as timeout:
        await registry.invoke("slow_note", {"query": "today"}, context())
    with pytest.raises(ToolInvocationError) as output:
        await registry.invoke("large_note", {"query": "today"}, context())

    assert timeout.value.code == "tool_timeout"
    assert output.value.code == "tool_output_invalid"


def test_registry_rejects_duplicate_names_and_non_strict_schema() -> None:
    tool = RecordingTool(query_definition())
    with pytest.raises(ToolRegistryError):
        ToolRegistry([tool, tool], policy=ReadOnlyToolPolicy())

    with pytest.raises(ValueError):
        ToolDefinition(
            name="loose_tool",
            description="Invalid loose schema.",
            input_schema={"type": "object", "properties": {}},
            effect=ToolEffect.READ_ONLY,
        )
