"""Explicit tool composition, validation, policy, timeout, and output caps."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from .availability import ToolAvailabilitySnapshot
from .definition import (
    Tool,
    ToolContext,
    ToolDefinition,
    ToolResult,
    validate_arguments,
)
from .policy import ToolPolicy


class ToolRegistryError(Exception):
    pass


class ToolInvocationError(Exception):
    """Safe failure passed to the Agent without tool exception detail."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(code)


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool], *, policy: ToolPolicy) -> None:
        self._policy = policy
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            definition = tool.definition
            if not isinstance(definition, ToolDefinition):
                raise ToolRegistryError("tool definition is invalid")
            if definition.name in self._tools:
                raise ToolRegistryError("duplicate tool name")
            self._tools[definition.name] = tool

    def definitions(
        self,
        availability: ToolAvailabilitySnapshot | None = None,
    ) -> tuple[ToolDefinition, ...]:
        return tuple(
            self._tools[name].definition
            for name in sorted(self._tools)
            if availability is None or availability.allows(name)
        )

    async def invoke(
        self,
        name: str,
        arguments: dict[str, object],
        context: ToolContext,
        availability: ToolAvailabilitySnapshot | None = None,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolInvocationError(
                "tool_not_found",
                "要求的工具目前未註冊。",
            )
        if availability is not None and not availability.allows(name):
            raise ToolInvocationError(
                "tool_denied",
                "這項工具操作目前不允許執行。",
            )
        definition = tool.definition
        if not self._policy.allows(definition):
            raise ToolInvocationError(
                "tool_denied",
                "這項工具操作目前不允許執行。",
            )
        if not isinstance(arguments, dict) or not validate_arguments(
            definition.input_schema,
            arguments,
        ):
            raise ToolInvocationError(
                "tool_invalid_arguments",
                "工具參數不符合已註冊的格式。",
            )
        try:
            result = await asyncio.wait_for(
                tool.invoke(dict(arguments), context),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError as error:
            raise ToolInvocationError(
                "tool_timeout",
                "工具執行逾時。",
                retryable=True,
            ) from error
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise ToolInvocationError(
                "tool_failed",
                "工具執行失敗。",
                retryable=False,
            ) from error
        if (
            not isinstance(result, ToolResult)
            or not isinstance(result.content, str)
            or not result.content
            or len(result.content) > definition.max_output_chars
            or not isinstance(result.summary, str)
            or not result.summary
            or len(result.summary) > 4096
        ):
            raise ToolInvocationError(
                "tool_output_invalid",
                "工具回傳內容無法安全使用。",
            )
        return result
