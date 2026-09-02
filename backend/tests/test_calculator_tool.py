from __future__ import annotations

import asyncio
from functools import wraps

import pytest

from opensprite_backend.tools import (
    ToolContext,
    ToolEffect,
    ToolInvocationError,
    create_production_tool_registry,
)
from opensprite_backend.tools.builtins import CalculatorTool


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def tool_context(*, cancelled: bool = False) -> ToolContext:
    cancellation_event = asyncio.Event()
    if cancelled:
        cancellation_event.set()
    return ToolContext(
        run_id="11111111-1111-4111-8111-111111111111",
        conversation_id="22222222-2222-4222-8222-222222222222",
        cancellation_event=cancellation_event,
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", "14"),
        ("(10 - 2) / 4", "2"),
        ("7 // 3", "2"),
        ("-7 // 3", "-3"),
        ("-7 % 3", "2"),
        ("2 ** 10", "1024"),
        ("0.1 + 0.2", "0.3"),
        ("1 / 8", "0.125"),
    ],
)
def test_calculator_evaluates_supported_decimal_arithmetic(
    expression: str,
    expected: str,
) -> None:
    async def scenario() -> None:
        result = await CalculatorTool().invoke(
            {"expression": expression},
            tool_context(),
        )
        assert result.content == expected
        assert result.summary == f"Calculator result: {expected}"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "expression",
    [
        "1 / 0",
        "2 ** 101",
        "True + 1",
        "sum([1, 2])",
        "__import__('os').system('whoami')",
        "[1, 2]",
        "1e101",
    ],
)
def test_calculator_rejects_unsafe_or_unbounded_expressions(
    expression: str,
) -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError):
            await CalculatorTool().invoke(
                {"expression": expression},
                tool_context(),
            )

    asyncio.run(scenario())


@async_test
async def test_production_registry_exposes_only_the_read_only_calculator() -> None:
    registry = create_production_tool_registry()

    assert [definition.name for definition in registry.definitions()] == [
        "calculator"
    ]
    assert registry.definitions()[0].effect is ToolEffect.READ_ONLY
    result = await registry.invoke(
        "calculator",
        {"expression": "6 * 7"},
        tool_context(),
    )

    assert result.content == "42"


@async_test
async def test_registry_hides_calculator_failures_from_the_model() -> None:
    registry = create_production_tool_registry()

    with pytest.raises(ToolInvocationError) as captured:
        await registry.invoke(
            "calculator",
            {"expression": "1 / 0"},
            tool_context(),
        )

    assert captured.value.code == "tool_failed"
    assert captured.value.message == "工具執行失敗。"
    assert "division" not in str(captured.value)


@async_test
async def test_calculator_honours_preexisting_cancellation() -> None:
    with pytest.raises(asyncio.CancelledError):
        await CalculatorTool().invoke(
            {"expression": "40 + 2"},
            tool_context(cancelled=True),
        )
