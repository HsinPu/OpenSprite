"""One deterministic bounded path for every user-message Agent run."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from dataclasses import dataclass
from typing import TypeVar

from opensprite_backend.conversations.models import (
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
from opensprite_backend.tools.definition import ToolContext
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


class _RunCancelled(Exception):
    pass


class _ContextPreparationFailed(Exception):
    pass


_Result = TypeVar("_Result")
_LOGGER = logging.getLogger("opensprite.agent.context")


@dataclass(frozen=True, slots=True)
class _PreparedContext:
    messages: tuple[ModelMessage, ...]
    tools: tuple[ModelToolDefinition, ...]
    budget: ContextBudgetPlan


class AgentLoop:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        gateway: ModelGateway,
        tools: ToolRegistry,
        capability_resolver: ModelCapabilityResolver,
        system_prompt_provider: SystemPromptProvider | None = None,
        max_model_rounds: int = 8,
        max_tool_calls: int = 16,
        max_compactions_per_run: int = 8,
        max_assistant_chars: int = MAX_ASSISTANT_CHARS,
    ) -> None:
        if not 1 <= max_model_rounds <= 32:
            raise ValueError("invalid model round bound")
        if not 0 <= max_tool_calls <= 64:
            raise ValueError("invalid tool call bound")
        if not 1 <= max_compactions_per_run <= 32:
            raise ValueError("invalid compaction bound")
        if not 1 <= max_assistant_chars <= MAX_ASSISTANT_CHARS:
            raise ValueError("invalid assistant output bound")
        self._repository = repository
        self._gateway = gateway
        self._tools = tools
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
            system_prompt = await self._system_prompt_provider.build(run_id=run_id)
            prepared = await self._prepare_context(
                run=run,
                system_prompt=system_prompt,
                cancellation_event=cancellation_event,
            )
            transcript = list(prepared.messages)
            tool_definitions = prepared.tools
            accumulated_text = run.partial_text
            tool_call_count = 0
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
                    tools=tool_definitions,
                    max_output_tokens=prepared.budget.output_reserve_tokens,
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
                                force_compaction=True,
                                compaction_limit=1,
                            )
                            transcript = list(prepared.messages)
                            tool_definitions = prepared.tools
                            retry_with_compaction = True
                            break
                        raise
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
                        _LOGGER.info(
                            "model usage run_id=%s round=%s input_tokens=%s output_tokens=%s",
                            run_id,
                            _round + 1,
                            event.input_tokens,
                            event.output_tokens,
                        )
                    else:
                        return await self._fail(run_id, INVALID_PROVIDER_RESPONSE)
                if retry_with_compaction:
                    continue
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
        except ContextLimitExceeded:
            return await self._fail(run_id, CONTEXT_LIMIT_ERROR)
        except ModelCapabilityNotFound:
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except _ContextPreparationFailed:
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except ModelCapabilityProviderError as error:
            return await self._fail(run_id, inference_error(error.failure))
        except asyncio.CancelledError:
            raise
        except ConversationStoreError:
            raise
        except Exception:
            return await self._fail(run_id, INTERNAL_ERROR)

    async def _prepare_context(
        self,
        *,
        run: RunSnapshot,
        system_prompt: str,
        cancellation_event: asyncio.Event,
        force_compaction: bool = False,
        compaction_limit: int | None = None,
    ) -> _PreparedContext:
        self._raise_if_cancelled(cancellation_event)
        limit = (
            self._max_compactions_per_run
            if compaction_limit is None
            else compaction_limit
        )
        if not 0 <= limit <= self._max_compactions_per_run:
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
        budget = resolve_context_budget(run.context_budget, capability)
        tool_definitions = tuple(
            ModelToolDefinition(
                name=definition.name,
                description=definition.description,
                input_schema=dict(definition.input_schema),
            )
            for definition in self._tools.definitions()
        )
        page = await asyncio.to_thread(
            self._repository.list_messages,
            run.conversation_id,
            limit=200,
            before_sequence=None,
        )
        summary = await asyncio.to_thread(
            self._repository.get_latest_compaction,
            run.conversation_id,
        )

        force_compaction_pending = force_compaction
        for compaction_index in range(limit + 1):
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
            if compaction_index >= limit:
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
                limit=200,
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
                force_compaction_pending = False
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
