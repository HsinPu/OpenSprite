"""One deterministic bounded path for every user-message Agent run."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from typing import TypeVar

from opensprite_backend.conversations.models import (
    MAX_ASSISTANT_CHARS,
    PublicRunError,
    RunEventType,
    RunSnapshot,
    RunStatus,
    StoreFailure,
)
from opensprite_backend.conversations.repository import (
    ConversationRepository,
    ConversationStoreError,
)
from opensprite_backend.inference.gateway import ModelGateway, ModelGatewayError
from opensprite_backend.inference.models import (
    ModelCompleted,
    ModelFinishReason,
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)
from opensprite_backend.tools.definition import ToolContext
from opensprite_backend.tools.registry import ToolInvocationError, ToolRegistry

from .events import (
    AGENT_LIMIT_ERROR,
    INTERNAL_ERROR,
    INVALID_PROVIDER_RESPONSE,
    inference_error,
)
from .prompt import SYSTEM_PROMPT


class _RunCancelled(Exception):
    pass


_Result = TypeVar("_Result")


class AgentLoop:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        gateway: ModelGateway,
        tools: ToolRegistry,
        max_model_rounds: int = 8,
        max_tool_calls: int = 16,
        max_history_messages: int = 100,
        max_assistant_chars: int = MAX_ASSISTANT_CHARS,
    ) -> None:
        if not 1 <= max_model_rounds <= 32:
            raise ValueError("invalid model round bound")
        if not 0 <= max_tool_calls <= 64:
            raise ValueError("invalid tool call bound")
        if not 1 <= max_history_messages <= 200:
            raise ValueError("invalid history bound")
        if not 1 <= max_assistant_chars <= MAX_ASSISTANT_CHARS:
            raise ValueError("invalid assistant output bound")
        self._repository = repository
        self._gateway = gateway
        self._tools = tools
        self._max_model_rounds = max_model_rounds
        self._max_tool_calls = max_tool_calls
        self._max_history_messages = max_history_messages
        self._max_assistant_chars = max_assistant_chars

    async def execute(
        self,
        run_id: str,
        cancellation_event: asyncio.Event,
    ) -> RunSnapshot:
        run = await asyncio.to_thread(self._repository.get_run, run_id)
        if run is None:
            raise ConversationStoreError(StoreFailure.NOT_FOUND)
        if run.status is not RunStatus.QUEUED:
            return run
        if cancellation_event.is_set():
            return await asyncio.to_thread(self._repository.request_cancel, run_id)
        try:
            run = await asyncio.to_thread(self._repository.mark_run_started, run_id)
            page = await asyncio.to_thread(
                self._repository.list_messages,
                run.conversation_id,
                limit=self._max_history_messages,
                before_sequence=None,
            )
            transcript = [ModelMessage(role="system", content=SYSTEM_PROMPT)]
            transcript.extend(
                ModelMessage(role=message.role, content=message.content)
                for message in page.items
            )
            accumulated_text = run.partial_text
            tool_call_count = 0
            failed_calls: Counter[str] = Counter()
            used_call_ids: set[str] = set()

            for _round in range(self._max_model_rounds):
                self._raise_if_cancelled(cancellation_event)
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run_id,
                    RunEventType.MODEL_STARTED,
                    {
                        "providerId": run.provider_id,
                        "modelId": run.model_id,
                        "responseMode": run.response_mode,
                    },
                )
                request = ModelRequest(
                    provider_id=run.provider_id,
                    model_id=run.model_id,
                    response_mode=run.response_mode,
                    messages=tuple(transcript),
                    tools=tuple(
                        ModelToolDefinition(
                            name=definition.name,
                            description=definition.description,
                            input_schema=dict(definition.input_schema),
                        )
                        for definition in self._tools.definitions()
                    ),
                )
                round_text = ""
                tool_calls: list[ModelToolCall] = []
                completion: ModelCompleted | None = None
                stream = self._gateway.stream(request)
                async for event in self._with_cancellation(
                    stream,
                    cancellation_event,
                ):
                    if completion is not None:
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                    if isinstance(event, ModelTextDelta):
                        if not event.text or len(event.text) > 16384:
                            return await self._fail(
                                run_id,
                                INVALID_PROVIDER_RESPONSE,
                            )
                        if len(accumulated_text) + len(event.text) > (
                            self._max_assistant_chars
                        ):
                            return await self._fail(run_id, AGENT_LIMIT_ERROR)
                        round_text += event.text
                        accumulated_text += event.text
                        await asyncio.to_thread(
                            self._repository.append_assistant_delta,
                            run_id,
                            event.text,
                        )
                    elif isinstance(event, ModelToolCall):
                        if event.call_id in used_call_ids:
                            return await self._fail(
                                run_id,
                                INVALID_PROVIDER_RESPONSE,
                            )
                        used_call_ids.add(event.call_id)
                        tool_calls.append(event)
                    elif isinstance(event, ModelCompleted):
                        completion = event
                    elif isinstance(event, ModelUsage):
                        continue
                    else:
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                if completion is None:
                    return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)

                if completion.reason is ModelFinishReason.FINAL:
                    if tool_calls or not accumulated_text.strip():
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                    self._raise_if_cancelled(cancellation_event)
                    completed = await asyncio.to_thread(
                        self._repository.complete_run,
                        run_id,
                        accumulated_text,
                    )
                    return completed.run

                if (
                    completion.reason is not ModelFinishReason.TOOL_CALLS
                    or not tool_calls
                ):
                    return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                transcript.append(
                    ModelMessage(
                        role="assistant",
                        content=round_text,
                        tool_calls=tuple(tool_calls),
                    )
                )
                for call in tool_calls:
                    tool_call_count += 1
                    if tool_call_count > self._max_tool_calls:
                        return await self._fail(run_id, AGENT_LIMIT_ERROR)
                    self._raise_if_cancelled(cancellation_event)
                    await asyncio.to_thread(
                        self._repository.append_run_event,
                        run_id,
                        RunEventType.TOOL_STARTED,
                        {"callId": call.call_id, "toolName": call.name},
                    )
                    context = ToolContext(
                        run_id=run.id,
                        conversation_id=run.conversation_id,
                        cancellation_event=cancellation_event,
                    )
                    try:
                        result = await self._await_with_cancellation(
                            self._tools.invoke(call.name, call.arguments, context),
                            cancellation_event,
                        )
                    except ToolInvocationError as error:
                        public_error = PublicRunError(
                            code="tool_failure",
                            message=error.message,
                            retryable=error.retryable,
                        )
                        await asyncio.to_thread(
                            self._repository.append_run_event,
                            run_id,
                            RunEventType.TOOL_FAILED,
                            {
                                "callId": call.call_id,
                                "toolName": call.name,
                                "error": {
                                    "code": public_error.code,
                                    "message": public_error.message,
                                    "retryable": public_error.retryable,
                                },
                            },
                        )
                        fingerprint = self._tool_fingerprint(call)
                        failed_calls[fingerprint] += 1
                        transcript.append(
                            ModelMessage(
                                role="tool",
                                content=f"Tool failed: {public_error.message}",
                                tool_call_id=call.call_id,
                                tool_name=call.name,
                            )
                        )
                        if failed_calls[fingerprint] >= 2:
                            return await self._fail(run_id, AGENT_LIMIT_ERROR)
                    else:
                        await asyncio.to_thread(
                            self._repository.append_run_event,
                            run_id,
                            RunEventType.TOOL_COMPLETED,
                            {
                                "callId": call.call_id,
                                "toolName": call.name,
                                "summary": result.summary,
                            },
                        )
                        transcript.append(
                            ModelMessage(
                                role="tool",
                                content=result.content,
                                tool_call_id=call.call_id,
                                tool_name=call.name,
                            )
                        )
            return await self._fail(run_id, AGENT_LIMIT_ERROR)
        except _RunCancelled:
            return await self._cancel(run_id)
        except ModelGatewayError as error:
            return await self._fail(run_id, inference_error(error.failure))
        except asyncio.CancelledError:
            raise
        except ConversationStoreError:
            raise
        except Exception:
            return await self._fail(run_id, INTERNAL_ERROR)

    async def _fail(
        self,
        run_id: str,
        error: PublicRunError,
    ) -> RunSnapshot:
        return await asyncio.to_thread(self._repository.fail_run, run_id, error)

    async def _cancel(self, run_id: str) -> RunSnapshot:
        requested = await asyncio.to_thread(self._repository.request_cancel, run_id)
        if requested.status is RunStatus.CANCELLED:
            return requested
        return await asyncio.to_thread(self._repository.mark_run_cancelled, run_id)

    @staticmethod
    def _raise_if_cancelled(cancellation_event: asyncio.Event) -> None:
        if cancellation_event.is_set():
            raise _RunCancelled

    @staticmethod
    async def _with_cancellation(
        stream: AsyncIterator[ModelStreamEvent],
        cancellation_event: asyncio.Event,
    ) -> AsyncIterator[ModelStreamEvent]:
        iterator = stream.__aiter__()
        try:
            while True:
                next_event = asyncio.create_task(anext(iterator))
                cancelled = asyncio.create_task(cancellation_event.wait())
                try:
                    done, _pending = await asyncio.wait(
                        {next_event, cancelled},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                except BaseException:
                    next_event.cancel()
                    cancelled.cancel()
                    await asyncio.gather(
                        next_event,
                        cancelled,
                        return_exceptions=True,
                    )
                    raise
                if cancelled in done and cancelled.result():
                    next_event.cancel()
                    with suppress(asyncio.CancelledError, StopAsyncIteration):
                        await next_event
                    raise _RunCancelled
                cancelled.cancel()
                with suppress(asyncio.CancelledError):
                    await cancelled
                try:
                    yield next_event.result()
                except StopAsyncIteration:
                    return
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                with suppress(Exception):
                    await close()

    @staticmethod
    async def _await_with_cancellation(
        awaitable: Awaitable[_Result],
        cancellation_event: asyncio.Event,
    ) -> _Result:
        operation = asyncio.ensure_future(awaitable)
        cancelled = asyncio.create_task(cancellation_event.wait())
        try:
            done, _pending = await asyncio.wait(
                {operation, cancelled},
                return_when=asyncio.FIRST_COMPLETED,
            )
        except BaseException:
            operation.cancel()
            cancelled.cancel()
            await asyncio.gather(operation, cancelled, return_exceptions=True)
            raise
        if cancelled in done and cancelled.result():
            operation.cancel()
            with suppress(asyncio.CancelledError):
                await operation
            raise _RunCancelled
        cancelled.cancel()
        with suppress(asyncio.CancelledError):
            await cancelled
        return operation.result()

    @staticmethod
    def _tool_fingerprint(call: ModelToolCall) -> str:
        return json.dumps(
            {"name": call.name, "arguments": call.arguments},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
