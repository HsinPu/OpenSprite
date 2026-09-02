"""Bounded decimal arithmetic without code evaluation or external access."""

from __future__ import annotations

import ast
import asyncio
from decimal import Decimal, DecimalException, ROUND_FLOOR, localcontext
from typing import Final

from ..definition import (
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
)


_MAX_EXPRESSION_CHARS: Final = 256
_MAX_AST_NODES: Final = 64
_MAX_AST_DEPTH: Final = 16
_MAX_EXPONENT: Final = 100
_MAX_MAGNITUDE: Final = Decimal("1e100")
_MAX_RESULT_CHARS: Final = 512


class CalculatorError(ValueError):
    """The expression is outside the calculator's safe arithmetic subset."""


class CalculatorTool:
    definition = ToolDefinition(
        name="calculator",
        description=(
            "Evaluate one bounded arithmetic expression with decimal numbers, "
            "+, -, *, /, //, %, **, unary signs, and parentheses. Functions, "
            "variables, units, code, files, and network access are unsupported."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The arithmetic expression to evaluate.",
                    "minLength": 1,
                    "maxLength": _MAX_EXPRESSION_CHARS,
                },
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
        effect=ToolEffect.READ_ONLY,
        timeout_seconds=1,
        max_output_chars=_MAX_RESULT_CHARS,
    )

    async def invoke(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult:
        if context.cancellation_event.is_set():
            raise asyncio.CancelledError
        expression = arguments.get("expression")
        if not isinstance(expression, str):
            raise CalculatorError("expression must be text")
        result = _evaluate_expression(expression)
        if context.cancellation_event.is_set():
            raise asyncio.CancelledError
        return ToolResult(
            content=result,
            summary=f"Calculator result: {result}",
        )


def _evaluate_expression(expression: str) -> str:
    if not expression or len(expression) > _MAX_EXPRESSION_CHARS:
        raise CalculatorError("invalid expression length")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, TypeError) as error:
        raise CalculatorError("invalid expression") from error
    if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
        raise CalculatorError("expression is too complex")

    try:
        with localcontext() as decimal_context:
            decimal_context.prec = 50
            decimal_context.Emax = 1_000
            decimal_context.Emin = -1_000
            value = _evaluate_node(tree, expression, depth=0)
    except (DecimalException, ArithmeticError) as error:
        raise CalculatorError("arithmetic operation failed") from error
    result = _format_result(_bounded(value))
    if len(result) > _MAX_RESULT_CHARS:
        raise CalculatorError("result is too large")
    return result


def _evaluate_node(node: ast.AST, expression: str, *, depth: int) -> Decimal:
    if depth > _MAX_AST_DEPTH:
        raise CalculatorError("expression is too deep")
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, expression, depth=depth + 1)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError("only decimal numbers are supported")
        source = ast.get_source_segment(expression, node)
        if source is None:
            raise CalculatorError("number source is unavailable")
        try:
            value = Decimal(source.replace("_", ""))
        except DecimalException as error:
            raise CalculatorError("invalid decimal number") from error
        return _bounded(value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate_node(node.operand, expression, depth=depth + 1)
        return _bounded(value if isinstance(node.op, ast.UAdd) else -value)
    if not isinstance(node, ast.BinOp):
        raise CalculatorError("unsupported expression")

    left = _evaluate_node(node.left, expression, depth=depth + 1)
    right = _evaluate_node(node.right, expression, depth=depth + 1)
    if isinstance(node.op, ast.Add):
        result = left + right
    elif isinstance(node.op, ast.Sub):
        result = left - right
    elif isinstance(node.op, ast.Mult):
        result = left * right
    elif isinstance(node.op, ast.Div):
        result = left / _nonzero(right)
    elif isinstance(node.op, ast.FloorDiv):
        divisor = _nonzero(right)
        result = (left / divisor).to_integral_value(rounding=ROUND_FLOOR)
    elif isinstance(node.op, ast.Mod):
        divisor = _nonzero(right)
        quotient = (left / divisor).to_integral_value(rounding=ROUND_FLOOR)
        result = left - quotient * divisor
    elif isinstance(node.op, ast.Pow):
        integral = right.to_integral_value()
        if right != integral or abs(integral) > _MAX_EXPONENT:
            raise CalculatorError("exponent is outside the supported range")
        result = left ** int(integral)
    else:
        raise CalculatorError("unsupported operator")
    return _bounded(result)


def _nonzero(value: Decimal) -> Decimal:
    if value == 0:
        raise CalculatorError("division by zero")
    return value


def _bounded(value: Decimal) -> Decimal:
    if not value.is_finite() or abs(value) > _MAX_MAGNITUDE:
        raise CalculatorError("number is outside the supported range")
    return value


def _format_result(value: Decimal) -> str:
    if value == 0:
        return "0"
    normalized = value.normalize()
    if -12 <= normalized.adjusted() <= 30:
        return format(normalized, "f")
    return format(normalized, "E")
