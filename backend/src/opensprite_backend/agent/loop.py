"""One deterministic bounded path for every user-message Agent run."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from collections import Counter
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from dataclasses import dataclass
from typing import Final, TypeVar

from opensprite_backend.conversations.models import (
    CompletionReason,
    ConversationCompaction,
    MAX_ASSISTANT_CHARS,
    Message,
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
    InferenceFailure,
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
from opensprite_backend.tools.availability import (
    ToolAvailabilityProvider,
    ToolAvailabilitySnapshot,
)
from opensprite_backend.tools.definition import ToolContext
from opensprite_backend.tools.dynamic import DynamicToolProvider
from opensprite_backend.tools.registry import ToolInvocationError, ToolRegistry

from .events import (
    AGENT_LIMIT_ERROR,
    CONTEXT_LIMIT_ERROR,
    CONTEXT_PREPARATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PROVIDER_RESPONSE,
    inference_error,
)
from .context import (
    ConservativeTokenCounter,
    ContextAssembler,
    ContextBudgetPlan,
    ContextLimitExceeded,
    ConversationCompactionService,
    GatewaySummaryGenerator,
    ModelCapabilityNotFound,
    ModelCapabilityProviderError,
    ModelCapabilityResolver,
    prepare_compaction_source,
    resolve_context_budget,
)
from .prompt import StaticSystemPromptProvider, SystemPromptProvider
from ..prompt_logging import PromptLogError, PromptLogWriter


class _RunCancelled(Exception):
    pass


class _ContextPreparationFailed(Exception):
    pass


_Result = TypeVar("_Result")
_LOGGER = logging.getLogger("opensprite.agent.context")
_MAX_UNLIMITED_CONTINUATIONS = 64
_BOUNDED_CONTINUATIONS = {"1": 1, "2": 2, "3": 3, "5": 5}
_CONTINUATION_TAIL_TOKENS = 4_096
_CONTEXT_PAGE_SIZE: Final = 200
_ASSISTANT_DELTA_BATCH_CHARS: Final = 4_096
_CONTINUATION_INSTRUCTION = (
    "Continue the assistant response from the exact point where it stopped. "
    "Do not repeat or summarize text that was already produced. Do not call "
    "tools. Return only the continuation of the response."
)


@dataclass(frozen=True, slots=True)
class _PreparedContext:
    messages: tuple[ModelMessage, ...]
    tools: tuple[ModelToolDefinition, ...]
    budget: ContextBudgetPlan


class _AssistantDeltaBuffer:
    """Coalesce fast model chunks before persisting them to SQLite."""

    def __init__(
        self,
        repository: ConversationRepository,
        run_id: str,
        *,
        batch_chars: int = _ASSISTANT_DELTA_BATCH_CHARS,
    ) -> None:
        self._repository = repository
        self._run_id = run_id
        self._batch_chars = batch_chars
        self._pending: list[str] = []
        self._pending_chars = 0

    async def append(self, text: str) -> None:
        self._pending.append(text)
        self._pending_chars += len(text)
        if self._pending_chars >= self._batch_chars:
            await self.flush()

    async def flush(self) -> None:
        if not self._pending:
            return
        text = "".join(self._pending)
        await asyncio.to_thread(
            self._repository.append_assistant_delta,
            self._run_id,
            text,
        )
        self._pending.clear()
        self._pending_chars = 0


class AgentLoop:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        gateway: ModelGateway,
        tools: ToolRegistry,
        tool_availability: ToolAvailabilityProvider | None = None,
        dynamic_tools: DynamicToolProvider | None = None,
        capability_resolver: ModelCapabilityResolver,
        system_prompt_provider: SystemPromptProvider | None = None,
        max_model_rounds: int = 8,
        max_tool_calls: int = 16,
        max_compactions_per_run: int | None = None,
        max_assistant_chars: int = MAX_ASSISTANT_CHARS,
        prompt_log_writer: PromptLogWriter | None = None,
    ) -> None:
        if not 1 <= max_model_rounds <= 32:
            raise ValueError("invalid model round bound")
        if not 0 <= max_tool_calls <= 64:
            raise ValueError("invalid tool call bound")
        if max_compactions_per_run is not None and not 1 <= max_compactions_per_run <= 32:
            raise ValueError("invalid compaction bound")
        if not 1 <= max_assistant_chars <= MAX_ASSISTANT_CHARS:
            raise ValueError("invalid assistant output bound")
        self._repository = repository
        self._gateway = gateway
        self._tools = tools
        self._tool_availability = tool_availability
        self._dynamic_tools = dynamic_tools
        self._capability_resolver = capability_resolver
        self._counter = ConservativeTokenCounter()
        self._context_assembler = ContextAssembler(self._counter)
        self._compaction_service = ConversationCompactionService(
            repository,
            GatewaySummaryGenerator(gateway),
        )
        self._system_prompt_provider = (
            system_prompt_provider
            if system_prompt_provider is not None
            else StaticSystemPromptProvider()
        )
        self._max_model_rounds = max_model_rounds
        self._max_tool_calls = max_tool_calls
        self._max_compactions_per_run = max_compactions_per_run
        self._max_assistant_chars = max_assistant_chars
        self._prompt_log_writer = prompt_log_writer

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
        delta_buffer = _AssistantDeltaBuffer(self._repository, run_id)
        try:
            run = await asyncio.to_thread(self._repository.mark_run_started, run_id)
            run_tools = (
                self._tools.extended(await self._dynamic_tools.snapshot_tools())
                if self._dynamic_tools is not None
                else self._tools
            )
            availability = (
                await self._tool_availability.snapshot()
                if self._tool_availability is not None
                else ToolAvailabilitySnapshot(
                    frozenset(
                        definition.name for definition in run_tools.definitions()
                    )
                )
            )
            system_prompt = await self._system_prompt_provider.build(run_id=run_id)
            prepared = await self._prepare_context(
                run=run,
                system_prompt=system_prompt,
                cancellation_event=cancellation_event,
                availability=availability,
                tools=run_tools,
                current_user_message_id=run.user_message_id,
            )
            transcript = list(prepared.messages)
            tool_definitions = prepared.tools
            accumulated_text = run.partial_text
            tool_call_count = 0
            prompt_log_sequence = [0]
            context_retry_used = False
            failed_calls: Counter[str] = Counter()
            used_call_ids: set[str] = set()

            for _round in range(self._max_model_rounds + 1):
                if _round >= self._max_model_rounds and not context_retry_used:
                    break
                self._raise_if_cancelled(cancellation_event)
                estimated_round_tokens = self._counter.request(
                    tuple(transcript),
                    tool_definitions,
                )
                if estimated_round_tokens > prepared.budget.input_budget_tokens:
                    return await self._fail(run_id, CONTEXT_LIMIT_ERROR)
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run_id,
                    RunEventType.MODEL_STARTED,
                    self._model_started_event_data(
                        run=run,
                        budget=prepared.budget,
                        context_tokens=estimated_round_tokens,
                        tool_definitions=tool_definitions,
                    ),
                )
                request = ModelRequest(
                    provider_id=run.provider_id,
                    model_id=run.model_id,
                    response_mode=run.response_mode,
                    messages=tuple(transcript),
                    tools=tool_definitions,
                    max_output_tokens=prepared.budget.output_reserve_tokens,
                )
                self._write_prompt_log(
                    run=run,
                    request=request,
                    request_kind=f"main-{_round + 1:02d}",
                    sequence=prompt_log_sequence,
                )
                round_text = ""
                tool_calls: list[ModelToolCall] = []
                completion: ModelCompleted | None = None
                stream = self._gateway.stream(request)
                events = self._with_cancellation(
                    stream,
                    cancellation_event,
                )
                retry_with_compaction = False
                while True:
                    try:
                        event = await anext(events)
                    except StopAsyncIteration:
                        break
                    except ModelGatewayError as error:
                        if (
                            error.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED
                            and _round == 0
                            and not context_retry_used
                            and not accumulated_text
                            and not round_text
                            and not tool_calls
                        ):
                            context_retry_used = True
                            _LOGGER.info(
                                "context retrying after provider limit run_id=%s",
                                run_id,
                            )
                            prepared = await self._prepare_context(
                                run=run,
                                system_prompt=system_prompt,
                                cancellation_event=cancellation_event,
                                availability=availability,
                                tools=run_tools,
                                force_compaction=True,
                                compaction_limit=1,
                                current_user_message_id=run.user_message_id,
                            )
                            transcript = list(prepared.messages)
                            tool_definitions = prepared.tools
                            retry_with_compaction = True
                            break
                        raise
                    if completion is not None:
                        await delta_buffer.flush()
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                    if isinstance(event, ModelTextDelta):
                        if not event.text or len(event.text) > 16384:
                            await delta_buffer.flush()
                            return await self._fail(
                                run_id,
                                INVALID_PROVIDER_RESPONSE,
                            )
                        if len(accumulated_text) + len(event.text) > (
                            self._max_assistant_chars
                        ):
                            await delta_buffer.flush()
                            return await self._fail(run_id, AGENT_LIMIT_ERROR)
                        round_text += event.text
                        accumulated_text += event.text
                        await delta_buffer.append(event.text)
                    elif isinstance(event, ModelToolCall):
                        if event.call_id in used_call_ids:
                            await delta_buffer.flush()
                            return await self._fail(
                                run_id,
                                INVALID_PROVIDER_RESPONSE,
                            )
                        used_call_ids.add(event.call_id)
                        tool_calls.append(event)
                    elif isinstance(event, ModelCompleted):
                        completion = event
                    elif isinstance(event, ModelUsage):
                        _LOGGER.info(
                            "model usage run_id=%s round=%s input_tokens=%s output_tokens=%s",
                            run_id,
                            _round + 1,
                            event.input_tokens,
                            event.output_tokens,
                        )
                    else:
                        await delta_buffer.flush()
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                await delta_buffer.flush()
                if retry_with_compaction:
                    continue
                if completion is None:
                    await delta_buffer.flush()
                    return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)

                if completion.reason in {
                    ModelFinishReason.FINAL,
                    ModelFinishReason.OUTPUT_LIMIT,
                }:
                    if (
                        tool_calls
                        or not accumulated_text.strip()
                        or (
                            completion.reason is ModelFinishReason.OUTPUT_LIMIT
                            and not round_text.strip()
                        )
                    ):
                        await delta_buffer.flush()
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                    self._raise_if_cancelled(cancellation_event)
                    await delta_buffer.flush()
                    completion_reason = (
                        CompletionReason.STOP
                        if completion.reason is ModelFinishReason.FINAL
                        else CompletionReason.OUTPUT_LIMIT
                    )
                    if completion_reason is CompletionReason.OUTPUT_LIMIT:
                        _LOGGER.info(
                            "model output limit reached run_id=%s chars=%s",
                            run_id,
                            len(accumulated_text),
                        )
                        if run.output_continuation != "off":
                            return await self._continue_output(
                                run=run,
                                system_prompt=system_prompt,
                                base_transcript=tuple(transcript),
                                prepared=prepared,
                                accumulated_text=accumulated_text,
                                cancellation_event=cancellation_event,
                                availability=availability,
                                tools=run_tools,
                                prompt_log_sequence=prompt_log_sequence,
                                delta_buffer=delta_buffer,
                            )
                    completed = await asyncio.to_thread(
                        self._repository.complete_run,
                        run_id,
                        accumulated_text,
                        completion_reason,
                    )
                    return completed.run

                if (
                    completion.reason is not ModelFinishReason.TOOL_CALLS
                    or not tool_calls
                ):
                    await delta_buffer.flush()
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
                        await delta_buffer.flush()
                        return await self._fail(run_id, AGENT_LIMIT_ERROR)
                    self._raise_if_cancelled(cancellation_event)
                    context = ToolContext(
                        run_id=run.id,
                        conversation_id=run.conversation_id,
                        cancellation_event=cancellation_event,
                    )

                    async def record_tool_started() -> None:
                        await asyncio.to_thread(
                            self._repository.append_run_event,
                            run_id,
                            RunEventType.TOOL_STARTED,
                            {"callId": call.call_id, "toolName": call.name},
                        )

                    try:
                        result = await self._await_with_cancellation(
                            run_tools.invoke(
                                call.name,
                                call.arguments,
                                context,
                                availability,
                                record_tool_started,
                            ),
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
                            await delta_buffer.flush()
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
            await delta_buffer.flush()
            return await self._fail(run_id, AGENT_LIMIT_ERROR)
        except _RunCancelled:
            await delta_buffer.flush()
            return await self._cancel(run_id)
        except ModelGatewayError as error:
            await delta_buffer.flush()
            return await self._fail(run_id, inference_error(error.failure))
        except ContextLimitExceeded:
            await delta_buffer.flush()
            return await self._fail(run_id, CONTEXT_LIMIT_ERROR)
        except ModelCapabilityNotFound:
            await delta_buffer.flush()
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except _ContextPreparationFailed:
            await delta_buffer.flush()
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except ModelCapabilityProviderError as error:
            await delta_buffer.flush()
            return await self._fail(run_id, inference_error(error.failure))
        except asyncio.CancelledError:
            raise
        except ConversationStoreError:
            raise
        except Exception:
            await delta_buffer.flush()
            _LOGGER.exception("agent run failed run_id=%s", run_id)
            return await self._fail(run_id, INTERNAL_ERROR)

    async def _continue_output(
        self,
        *,
        run: RunSnapshot,
        system_prompt: str,
        base_transcript: tuple[ModelMessage, ...],
        prepared: _PreparedContext,
        accumulated_text: str,
        cancellation_event: asyncio.Event,
        availability: ToolAvailabilitySnapshot,
        tools: ToolRegistry,
        prompt_log_sequence: list[int],
        delta_buffer: _AssistantDeltaBuffer,
    ) -> RunSnapshot:
        continuation_base = base_transcript
        configured_max = (
            None
            if run.output_continuation == "unlimited"
            else _BOUNDED_CONTINUATIONS[run.output_continuation]
        )
        attempt_limit = configured_max or _MAX_UNLIMITED_CONTINUATIONS
        for attempt in range(1, attempt_limit + 1):
            self._raise_if_cancelled(cancellation_event)
            await asyncio.to_thread(
                self._repository.append_run_event,
                run.id,
                RunEventType.RESPONSE_CONTINUATION_STARTED,
                {"attempt": attempt, "maxAttempts": configured_max},
            )
            context_retry_used = False
            while True:
                try:
                    transcript = self._continuation_transcript(
                        continuation_base,
                        accumulated_text,
                        prepared.budget,
                    )
                except ContextLimitExceeded:
                    if context_retry_used:
                        return await self._complete_partial(
                            run.id,
                            accumulated_text,
                            CompletionReason.CONTEXT_LIMIT,
                            cancellation_event,
                        )
                    context_retry_used = True
                    try:
                        prepared = await self._prepare_context(
                            run=run,
                            system_prompt=system_prompt,
                            cancellation_event=cancellation_event,
                            availability=availability,
                            tools=tools,
                            force_compaction=True,
                            compaction_limit=1,
                            current_user_message_id=run.user_message_id,
                        )
                    except ContextLimitExceeded:
                        return await self._complete_partial(
                            run.id,
                            accumulated_text,
                            CompletionReason.CONTEXT_LIMIT,
                            cancellation_event,
                        )
                    continuation_base = prepared.messages
                    continue

                estimated_round_tokens = self._counter.request(transcript, ())
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run.id,
                    RunEventType.MODEL_STARTED,
                    self._model_started_event_data(
                        run=run,
                        budget=prepared.budget,
                        context_tokens=estimated_round_tokens,
                        tool_definitions=(),
                    ),
                )
                request = ModelRequest(
                    provider_id=run.provider_id,
                    model_id=run.model_id,
                    response_mode=run.response_mode,
                    messages=transcript,
                    tools=(),
                    max_output_tokens=prepared.budget.output_reserve_tokens,
                )
                self._write_prompt_log(
                    run=run,
                    request=request,
                    request_kind=f"continuation-{attempt:02d}",
                    sequence=prompt_log_sequence,
                )
                round_text = ""
                completion: ModelCompleted | None = None
                events = self._with_cancellation(
                    self._gateway.stream(request),
                    cancellation_event,
                )
                retry_with_compaction = False
                while True:
                    try:
                        event = await anext(events)
                    except StopAsyncIteration:
                        break
                    except ModelGatewayError as error:
                        if (
                            error.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED
                            and not round_text
                            and not context_retry_used
                        ):
                            context_retry_used = True
                            try:
                                prepared = await self._prepare_context(
                                    run=run,
                                    system_prompt=system_prompt,
                                    cancellation_event=cancellation_event,
                                    availability=availability,
                                    tools=tools,
                                    force_compaction=True,
                                    compaction_limit=1,
                                    current_user_message_id=run.user_message_id,
                                )
                            except ContextLimitExceeded:
                                return await self._complete_partial(
                                    run.id,
                                    accumulated_text,
                                    CompletionReason.CONTEXT_LIMIT,
                                    cancellation_event,
                                )
                            continuation_base = prepared.messages
                            retry_with_compaction = True
                            break
                        if error.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED:
                            return await self._complete_partial(
                                run.id,
                                accumulated_text,
                                CompletionReason.CONTEXT_LIMIT,
                                cancellation_event,
                            )
                        raise
                    if completion is not None:
                        await delta_buffer.flush()
                        return await self._fail(run.id, INVALID_PROVIDER_RESPONSE)
                    if isinstance(event, ModelTextDelta):
                        if not event.text or len(event.text) > 16384:
                            await delta_buffer.flush()
                            return await self._fail(
                                run.id,
                                INVALID_PROVIDER_RESPONSE,
                            )
                        if len(accumulated_text) + len(event.text) > self._max_assistant_chars:
                            await delta_buffer.flush()
                            return await self._fail(run.id, AGENT_LIMIT_ERROR)
                        round_text += event.text
                        accumulated_text += event.text
                        await delta_buffer.append(event.text)
                    elif isinstance(event, ModelCompleted):
                        completion = event
                    elif isinstance(event, ModelUsage):
                        _LOGGER.info(
                            "model continuation usage run_id=%s attempt=%s input_tokens=%s output_tokens=%s",
                            run.id,
                            attempt,
                            event.input_tokens,
                            event.output_tokens,
                        )
                    else:
                        await delta_buffer.flush()
                        return await self._fail(run.id, INVALID_PROVIDER_RESPONSE)
                if retry_with_compaction:
                    continue
                if completion is None or not round_text.strip():
                    await delta_buffer.flush()
                    return await self._fail(run.id, INVALID_PROVIDER_RESPONSE)
                if completion.reason is ModelFinishReason.FINAL:
                    await delta_buffer.flush()
                    return await self._complete_partial(
                        run.id,
                        accumulated_text,
                        CompletionReason.STOP,
                        cancellation_event,
                    )
                if completion.reason is not ModelFinishReason.OUTPUT_LIMIT:
                    await delta_buffer.flush()
                    return await self._fail(run.id, INVALID_PROVIDER_RESPONSE)
                await delta_buffer.flush()
                break
        if configured_max is None:
            _LOGGER.warning(
                "unlimited continuation safety cap reached run_id=%s attempts=%s",
                run.id,
                attempt_limit,
            )
        await delta_buffer.flush()
        return await self._complete_partial(
            run.id,
            accumulated_text,
            CompletionReason.OUTPUT_LIMIT,
            cancellation_event,
        )

    async def _complete_partial(
        self,
        run_id: str,
        accumulated_text: str,
        reason: CompletionReason,
        cancellation_event: asyncio.Event,
    ) -> RunSnapshot:
        self._raise_if_cancelled(cancellation_event)
        completed = await asyncio.to_thread(
            self._repository.complete_run,
            run_id,
            accumulated_text,
            reason,
        )
        return completed.run

    def _write_prompt_log(
        self,
        *,
        run: RunSnapshot,
        request: ModelRequest,
        request_kind: str,
        sequence: list[int],
    ) -> None:
        if not run.log_full_prompts or self._prompt_log_writer is None:
            return
        sequence[0] += 1
        try:
            self._prompt_log_writer.write(
                run_id=run.id,
                created_at=datetime.now(UTC),
                request_kind=request_kind,
                request_sequence=sequence[0],
                provider_id=request.provider_id,
                model_id=request.model_id,
                response_mode=request.response_mode,
                max_output_tokens=request.max_output_tokens,
                messages=request.messages,
                tools=request.tools,
            )
        except PromptLogError:
            _LOGGER.warning(
                "full prompt log failed run_id=%s request_kind=%s",
                run.id,
                request_kind,
            )

    @staticmethod
    def _model_started_event_data(
        *,
        run: RunSnapshot,
        budget: ContextBudgetPlan,
        context_tokens: int,
        tool_definitions: tuple[ModelToolDefinition, ...],
    ) -> dict[str, object]:
        return {
            "providerId": run.provider_id,
            "modelId": run.model_id,
            "responseMode": run.response_mode,
            "maxOutputTokens": budget.output_reserve_tokens,
            "contextTokens": context_tokens,
            "contextLimitTokens": budget.context_limit_tokens,
            "inputBudgetTokens": budget.input_budget_tokens,
            "toolNames": [tool.name for tool in tool_definitions],
        }

    def _continuation_transcript(
        self,
        base_transcript: tuple[ModelMessage, ...],
        accumulated_text: str,
        budget: ContextBudgetPlan,
    ) -> tuple[ModelMessage, ...]:
        if not base_transcript or base_transcript[0].role != "system":
            raise ContextLimitExceeded
        instructed = (
            ModelMessage(
                role="system",
                content=f"{base_transcript[0].content}\n\n{_CONTINUATION_INSTRUCTION}",
            ),
            *base_transcript[1:],
        )
        base_tokens = self._counter.request(instructed, ())
        available = min(
            _CONTINUATION_TAIL_TOKENS,
            budget.input_budget_tokens - base_tokens - 8,
        )
        if available < 1:
            raise ContextLimitExceeded
        low = 1
        high = len(accumulated_text)
        best: str | None = None
        while low <= high:
            middle = (low + high) // 2
            candidate_text = accumulated_text[-middle:]
            candidate = ModelMessage(role="assistant", content=candidate_text)
            if self._counter.message(candidate) <= available:
                best = candidate_text
                low = middle + 1
            else:
                high = middle - 1
        if best is None:
            raise ContextLimitExceeded
        result = (*instructed, ModelMessage(role="assistant", content=best))
        if self._counter.request(result, ()) > budget.input_budget_tokens:
            raise ContextLimitExceeded
        return result

    async def _prepare_context(
        self,
        *,
        run: RunSnapshot,
        system_prompt: str,
        cancellation_event: asyncio.Event,
        availability: ToolAvailabilitySnapshot | None = None,
        tools: ToolRegistry | None = None,
        force_compaction: bool = False,
        compaction_limit: int | None = None,
        current_user_message_id: str | None = None,
    ) -> _PreparedContext:
        self._raise_if_cancelled(cancellation_event)
        limit = (
            self._max_compactions_per_run
            if compaction_limit is None
            else compaction_limit
        )
        if limit is not None and not 0 <= limit <= 32:
            raise ValueError("invalid Context compaction limit")
        _LOGGER.info(
            "context preparing run_id=%s provider_id=%s model_id=%s budget=%s force_compaction=%s",
            run.id,
            run.provider_id,
            run.model_id,
            run.context_budget,
            force_compaction,
        )
        capability = await self._await_with_cancellation(
            self._capability_resolver.resolve(
                run.provider_id,
                run.model_id,
            ),
            cancellation_event,
        )
        budget = resolve_context_budget(
            run.context_budget,
            capability,
            run.output_budget,
        )
        resolved_tools = tools or self._tools
        resolved_availability = availability or ToolAvailabilitySnapshot(
            frozenset(definition.name for definition in resolved_tools.definitions())
        )
        tool_definitions = tuple(
            ModelToolDefinition(
                name=definition.name,
                description=definition.description,
                input_schema=dict(definition.input_schema),
            )
            for definition in resolved_tools.definitions(resolved_availability)
        )
        page = await asyncio.to_thread(
            self._repository.list_messages,
            run.conversation_id,
            limit=_CONTEXT_PAGE_SIZE,
            before_sequence=None,
        )
        summary = await asyncio.to_thread(
            self._repository.get_latest_compaction,
            run.conversation_id,
        )

        force_compaction_pending = force_compaction
        compaction_index = 0
        while True:
            coverage = 0 if summary is None else summary.covers_through_sequence
            uncovered = tuple(
                message for message in page.items if message.sequence > coverage
            )
            has_older = bool(
                page.next_before_sequence is not None
                and page.items
                and coverage < page.items[0].sequence - 1
            )
            try:
                assembled = self._context_assembler.assemble(
                    system_prompt=system_prompt,
                    history=uncovered,
                    tools=tool_definitions,
                    budget=budget,
                    summary=summary,
                    has_older_history=has_older,
                    current_user_message_id=current_user_message_id,
                )
            except ContextLimitExceeded:
                raise
            except ValueError as error:
                raise _ContextPreparationFailed from error
            if not assembled.needs_compaction and not force_compaction_pending:
                _LOGGER.info(
                    "context prepared run_id=%s context_limit=%s input_budget=%s estimated_input=%s messages=%s compacted_through=%s",
                    run.id,
                    budget.context_limit_tokens,
                    budget.input_budget_tokens,
                    assembled.estimated_input_tokens,
                    assembled.included_message_count,
                    coverage,
                )
                return _PreparedContext(
                    messages=assembled.messages,
                    tools=tool_definitions,
                    budget=budget,
                )
            if limit is not None and compaction_index >= limit:
                raise ContextLimitExceeded

            protected_sequence = (
                uncovered[-12].sequence
                if len(uncovered) >= 12
                else uncovered[0].sequence
                if uncovered
                else page.items[-1].sequence + 1
            )
            candidates = await asyncio.to_thread(
                self._repository.list_messages_after,
                run.conversation_id,
                after_sequence=coverage,
                limit=_CONTEXT_PAGE_SIZE,
            )
            candidates = tuple(
                message
                for message in candidates
                if message.sequence < protected_sequence
            )
            if not candidates:
                raise ContextLimitExceeded
            try:
                self._raise_if_cancelled(cancellation_event)
                candidates = self._fit_compaction_source(
                    summary,
                    candidates,
                    budget.input_budget_tokens,
                )
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run.id,
                    RunEventType.CONTEXT_COMPACTION_STARTED,
                    {},
                )
                summary = await self._await_with_cancellation(
                    self._compaction_service.compact(
                        conversation_id=run.conversation_id,
                        provider_id=run.provider_id,
                        model_id=run.model_id,
                        previous=summary,
                        messages=candidates,
                    ),
                    cancellation_event,
                )
                if summary.covers_through_sequence <= coverage:
                    raise _ContextPreparationFailed
                force_compaction_pending = False
                compaction_index += 1
            except ContextLimitExceeded:
                raise
            except ValueError as error:
                raise _ContextPreparationFailed from error
            _LOGGER.info(
                "context compacted run_id=%s through_sequence=%s input_tokens=%s output_tokens=%s",
                run.id,
                summary.covers_through_sequence,
                summary.input_tokens,
                summary.output_tokens,
            )
        raise ContextLimitExceeded  # pragma: no cover

    def _fit_compaction_source(
        self,
        previous: ConversationCompaction | None,
        candidates: tuple[Message, ...],
        input_budget_tokens: int,
    ) -> tuple[Message, ...]:
        selected: list[Message] = []
        source_characters = 0 if previous is None else len(previous.summary)
        for candidate in candidates:
            if source_characters + len(candidate.content) > 400_000:
                break
            selected.append(candidate)
            source_characters += len(candidate.content)
        while selected:
            source = prepare_compaction_source(previous, tuple(selected))
            if (
                len(source.prompt) <= 1_000_000
                and self._counter.text(source.prompt) + 64 <= input_budget_tokens
            ):
                return tuple(selected)
            selected.pop()
        raise ContextLimitExceeded


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
