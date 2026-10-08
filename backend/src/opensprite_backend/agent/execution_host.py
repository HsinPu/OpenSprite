"""Run-local execution authority used by replaceable trusted Agent Loops."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from opensprite_backend.conversations.models import (
    CompletionReason,
    PublicRunError,
    RunEventType,
)
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import (
    InferenceFailure,
    ModelCompleted,
    ModelFinishReason,
    ModelMessage,
    ModelRequest,
    ModelTextDelta,
    ModelUsage,
)

from .plugin import AgentLoopPlugin, DriverResult, ModelTurn, CompletionState, ContextRetryState
from .events import (
    AGENT_LIMIT_ERROR,
    CONTEXT_LIMIT_ERROR,
    INTERNAL_ERROR,
    INVALID_PROVIDER_RESPONSE,
)
from .request_trace import Attempt

if TYPE_CHECKING:
    from opensprite_backend.conversations.models import RunSnapshot
    from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
    from opensprite_backend.workspaces import WorkspaceExecutionContext

    from .loop import AgentLoop, _AssistantDeltaBuffer, _PreparedContext


_LOGGER = logging.getLogger("opensprite.agent.context")


class _ExecutionFailed(Exception):
    def __init__(self, error: PublicRunError) -> None:
        super().__init__(error.code)
        self.error = error


class _SafePluginDecisions:
    """Convert every plugin callback failure before it enters core error handling."""

    def __init__(self, plugin: AgentLoopPlugin) -> None:
        self._plugin = plugin

    def _decision(self, method: str, state: object) -> bool:
        try:
            decision = getattr(self._plugin, method)(state)
            if type(decision) is not bool:
                if inspect.iscoroutine(decision):
                    decision.close()
                raise ValueError("invalid plugin decision")
            return decision
        except (Exception, asyncio.CancelledError):
            raise _ExecutionFailed(INTERNAL_ERROR) from None

    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return self._decision("allow_context_retry", state)

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return self._decision("allow_output_continuation", state)


class LoopExecutionHost:
    """Keep execution state and all effects in core, behind the plugin Host."""

    def __init__(
        self,
        *,
        loop: AgentLoop,
        run: RunSnapshot,
        cancellation_event: asyncio.Event,
        prepared: _PreparedContext,
        system_prompt: str,
        delta_buffer: _AssistantDeltaBuffer,
        plugin: AgentLoopPlugin,
        provider_endpoint: ProviderEndpointSnapshot | None,
    ) -> None:
        self._loop = loop
        self._run = run
        self._cancellation_event = cancellation_event
        self._prepared = prepared
        self._system_prompt = system_prompt
        self._delta_buffer = delta_buffer
        self._decisions = _SafePluginDecisions(plugin)
        self._provider_endpoint = provider_endpoint
        self._transcript = list(prepared.messages)
        self._accumulated_text = run.partial_text
        self._prompt_log_sequence = [0]
        self._context_retry_used = False
        self._request_id = str(uuid4())
        self._previous_attempt: Attempt | None = None
        self._attempt_count = 0
        self._turn: ModelTurn | None = None
        self._turn_signature: str | None = None
        self._result: DriverResult | None = None
        self._result_signature: tuple[str, CompletionReason] | None = None
        self._failure: Exception | None = None
        self._raised_errors: list[tuple[Exception, tuple[object, ...]]] = []
        self._operations: set[asyncio.Task[object]] = set()
        self._closed = False

    async def checkpoint(self) -> None:
        try:
            self._loop._raise_if_cancelled(self._cancellation_event)
            if self._closed or self._failure is not None:
                raise self._failure or _ExecutionFailed(INTERNAL_ERROR)
        except Exception as error:
            self._record_error(error)
            raise

    @staticmethod
    def _error_signature(error: Exception) -> tuple[object, ...]:
        if type(error) is _ExecutionFailed:
            public = error.error
            detail = (public.code, public.message, public.retryable)
        else:
            detail = getattr(error, "failure", None)
        return type(error), error.args, detail

    def _record_error(self, error: Exception) -> None:
        self._failure = error
        if not any(owned is error for owned, _ in self._raised_errors):
            self._raised_errors.append((error, self._error_signature(error)))

    def _owns_exception(self, error: Exception) -> bool:
        # Matching a class is insufficient: a driver can construct that same
        # class with arbitrary public text. Require the original, unchanged
        # object raised by a core operation.
        try:
            return any(owned is error and signature == self._error_signature(error)
                       for owned, signature in self._raised_errors)
        except Exception:
            return False

    @asynccontextmanager
    async def _operation(self) -> AsyncIterator[None]:
        task = None
        try:
            await self.checkpoint()
            if self._operations or self._result is not None:
                raise _ExecutionFailed(INTERNAL_ERROR)
            task = asyncio.current_task()
            assert task is not None
            self._operations.add(task)
            yield
        except Exception as error:
            self._record_error(error)
            raise
        finally:
            if task is not None:
                self._operations.discard(task)

    @staticmethod
    def _signature(turn: ModelTurn) -> str:
        return json.dumps(
            [turn.text, turn.finish_reason.value],
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )

    def _check_turn(self, turn: ModelTurn) -> None:
        if turn is not self._turn or self._signature(turn) != self._turn_signature:
            raise _ExecutionFailed(INTERNAL_ERROR)

    async def next_turn(self) -> ModelTurn:
        async with self._operation():
            if self._turn is not None:
                raise _ExecutionFailed(INTERNAL_ERROR)
            return await self._next_turn()

    async def _next_turn(self) -> ModelTurn:
        while True:
            _round = self._attempt_count
            if _round >= self._loop._max_model_rounds + int(self._context_retry_used):
                raise _ExecutionFailed(AGENT_LIMIT_ERROR)
            self._attempt_count += 1
            self._loop._raise_if_cancelled(self._cancellation_event)
            estimated_round_tokens = self._loop._counter.request(
                tuple(self._transcript),
            )
            if estimated_round_tokens > self._prepared.budget.input_budget_tokens:
                raise _ExecutionFailed(CONTEXT_LIMIT_ERROR)
            await asyncio.to_thread(
                self._loop._repository.append_run_event,
                self._run.id,
                RunEventType.MODEL_STARTED,
                self._loop._model_started_event_data(
                    run=self._run,
                    budget=self._prepared.budget,
                    context_tokens=estimated_round_tokens,

                ),
            )
            request = ModelRequest(
                provider_id=self._run.provider_id,
                provider_endpoint=self._provider_endpoint,
                model_id=self._run.model_id,
                response_mode=self._run.response_mode,
                reasoning_resolution=self._run.reasoning_resolution,
                messages=tuple(self._transcript),

                max_output_tokens=self._prepared.budget.output_reserve_tokens,
            )
            self._loop._write_prompt_log(
                run=self._run,
                request=request,
                request_kind=f"main-{_round + 1:02d}",
                sequence=self._prompt_log_sequence,
            )
            round_text = ""
            completion: ModelCompleted | None = None
            current_attempt = Attempt(
                self._run.id, self._request_id, "main",
                number=1 if self._previous_attempt is None else self._previous_attempt.number + 1,
                retry_of=None if self._previous_attempt is None else self._previous_attempt.id,
                cause=None if self._previous_attempt is None else "provider_context_limit",
                compaction_id=self._prepared.compaction_id,
                sources=self._prepared.sources,
            )
            stream = self._loop._gateway.stream(request, attempt=current_attempt)
            events = self._loop._with_cancellation(
                stream,
                self._cancellation_event,
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
                        and not self._context_retry_used
                        and not self._accumulated_text
                        and not round_text
                        and self._decisions.allow_context_retry(
                            ContextRetryState("main", "provider_context_limit")
                        )
                    ):
                        self._context_retry_used = True
                        self._previous_attempt = current_attempt
                        _LOGGER.info(
                            "context retrying after provider limit run_id=%s",
                            self._run.id,
                        )
                        self._prepared = await self._loop._prepare_context(
                            run=self._run,
                            provider_endpoint=self._provider_endpoint,
                            system_prompt=self._system_prompt,
                            cancellation_event=self._cancellation_event,


                            force_compaction=True,
                            compaction_limit=1,
                            current_user_message_id=self._run.user_message_id,
                            parent_request_id=self._request_id,
                        )
                        self._transcript = list(self._prepared.messages)
                        retry_with_compaction = True
                        break
                    raise
                if completion is not None:
                    await self._delta_buffer.flush()
                    raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                if isinstance(event, ModelTextDelta):
                    if not event.text or len(event.text) > 16384:
                        await self._delta_buffer.flush()
                        raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE,)
                    if len(self._accumulated_text) + len(event.text) > (
                        self._loop._max_assistant_chars
                    ):
                        await self._delta_buffer.flush()
                        raise _ExecutionFailed(AGENT_LIMIT_ERROR)
                    round_text += event.text
                    self._accumulated_text += event.text
                    await self._delta_buffer.append(event.text)
                elif isinstance(event, ModelCompleted):
                    completion = event
                elif isinstance(event, ModelUsage):
                    _LOGGER.info(
                        "model usage run_id=%s round=%s input_tokens=%s output_tokens=%s",
                        self._run.id,
                        _round + 1,
                        event.input_tokens,
                        event.output_tokens,
                    )
                else:
                    await self._delta_buffer.flush()
                    raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
            await self._delta_buffer.flush()
            if retry_with_compaction:
                continue
            self._request_id = str(uuid4())
            self._previous_attempt = None
            if completion is None:
                await self._delta_buffer.flush()
                raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
            if completion.reason in {ModelFinishReason.FINAL, ModelFinishReason.OUTPUT_LIMIT}:
                if (
                    not self._accumulated_text.strip()
                    or (completion.reason is ModelFinishReason.OUTPUT_LIMIT and not round_text.strip())
                ):
                    raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
            else:
                raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
            self._turn = ModelTurn(round_text, completion.reason)
            self._turn_signature = self._signature(self._turn)
            return self._turn


    async def finish(self, turn: ModelTurn) -> DriverResult:
        async with self._operation():
            self._check_turn(turn)
            if turn.finish_reason not in {
                ModelFinishReason.FINAL, ModelFinishReason.OUTPUT_LIMIT
            }:
                raise _ExecutionFailed(INTERNAL_ERROR)
            await self.checkpoint()
            await self._delta_buffer.flush()
            reason = (
                CompletionReason.STOP if turn.finish_reason is ModelFinishReason.FINAL
                else CompletionReason.OUTPUT_LIMIT
            )
            if (
                reason is CompletionReason.OUTPUT_LIMIT
                and self._run.output_continuation != "off"
                and self._decisions.allow_output_continuation(
                    CompletionState(turn.finish_reason, self._run.output_continuation))
            ):
                self._result = await self._loop._continue_output(
                    run=self._run, system_prompt=self._system_prompt,
                    base_transcript=tuple(self._transcript), prepared=self._prepared,
                    accumulated_text=self._accumulated_text,
                    cancellation_event=self._cancellation_event,
                    prompt_log_sequence=self._prompt_log_sequence,
                    delta_buffer=self._delta_buffer, provider_endpoint=self._provider_endpoint,
                    plugin_decisions=self._decisions)
            else:
                self._result = await self._loop._complete_partial(
                    self._run.id, self._accumulated_text, reason, self._cancellation_event)
            self._result_signature = (self._result.text, self._result.completion_reason)
            return self._result

    async def _validate_result(self, result: DriverResult) -> None:
        await self.checkpoint()
        if (
            self._operations or self._result is None or result is not self._result
            or type(result.text) is not str
            or type(result.completion_reason) is not CompletionReason
            or (result.text, result.completion_reason) != self._result_signature
        ):
            raise _ExecutionFailed(INTERNAL_ERROR)

    async def _close(self) -> None:
        self._closed = True
        operations = tuple(self._operations - {asyncio.current_task()})
        for task in operations:
            task.cancel()
        if operations:
            await asyncio.gather(*operations, return_exceptions=True)
