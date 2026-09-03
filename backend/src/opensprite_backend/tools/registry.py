"""Explicit tool composition, validation, policy, timeout, and output caps."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable

from .approval import ToolApprovalAuthorizer, ToolApprovalDenied
from .approval import ToolApprovalGrant
from .availability import ToolAvailabilitySnapshot
from .definition import (
    Tool,
    ToolContext,
    ToolDefinition,
    ToolResult,
    validate_arguments,
)
from .policy import ToolPolicy
from .receipts import ToolReceiptError, ToolReceiptWriter


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
    def __init__(
        self,
        tools: Iterable[Tool],
        *,
        policy: ToolPolicy,
        approval: ToolApprovalAuthorizer | None = None,
        receipts: ToolReceiptWriter | None = None,
    ) -> None:
        self._policy = policy
        self._approval = approval
        self._receipts = receipts
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            definition = tool.definition
            if not isinstance(definition, ToolDefinition):
                raise ToolRegistryError("tool definition is invalid")
            if definition.name in self._tools:
                raise ToolRegistryError("duplicate tool name")
            self._tools[definition.name] = tool

    def extended(self, tools: Iterable[Tool]) -> "ToolRegistry":
        return ToolRegistry(
            (*self._tools.values(), *tuple(tools)),
            policy=self._policy,
            approval=self._approval,
            receipts=self._receipts,
        )

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
        on_authorized: Callable[[], Awaitable[None]] | None = None,
        *,
        allow_approval: bool = True,
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
        if not isinstance(arguments, dict) or not validate_arguments(
            definition.input_schema,
            arguments,
        ):
            raise ToolInvocationError(
                "tool_invalid_arguments",
                "工具參數不符合已註冊的格式。",
            )
        grant: ToolApprovalGrant | None = None
        if not self._policy.allows(definition):
            if not allow_approval:
                raise ToolInvocationError(
                    "scheduled_tool_approval_required",
                    "排程執行不會自動核准這項工具。",
                )
            if self._approval is None:
                raise ToolInvocationError(
                    "tool_denied",
                    "這項工具操作目前不允許執行。",
                )
            try:
                grant = await self._approval.authorize(definition, arguments, context)
            except ToolApprovalDenied as error:
                raise ToolInvocationError(
                    "tool_denied",
                    "使用者未允許這項工具操作。",
                ) from error
            if self._receipts is None:
                raise ToolInvocationError(
                    "tool_denied",
                    "工具執行紀錄目前無法使用。",
                )
            try:
                await self._receipts.record_authorized(definition, context, grant)
            except ToolReceiptError as error:
                raise ToolInvocationError(
                    "tool_failed",
                    "工具執行紀錄目前無法使用。",
                ) from error
        if on_authorized is not None:
            await on_authorized()
        try:
            result = await asyncio.wait_for(
                tool.invoke(dict(arguments), context),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError as error:
            await self._record_result(definition, context, grant, "failed", "tool_timeout")
            raise ToolInvocationError(
                "tool_timeout",
                "工具執行逾時。",
                retryable=True,
            ) from error
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._record_result(definition, context, grant, "failed", "tool_failed")
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
            await self._record_result(definition, context, grant, "failed", "tool_output_invalid")
            raise ToolInvocationError(
                "tool_output_invalid",
                "工具回傳內容無法安全使用。",
            )
        await self._record_result(definition, context, grant, "completed", result.content)
        return result

    async def _record_result(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        grant: ToolApprovalGrant | None,
        status: str,
        result: str,
    ) -> None:
        if grant is None or self._receipts is None:
            return
        try:
            await self._receipts.record_result(
                definition,
                context,
                grant,
                status=status,
                result=result,
            )
        except ToolReceiptError as error:
            raise ToolInvocationError(
                "tool_failed",
                "工具執行紀錄目前無法使用。",
            ) from error
