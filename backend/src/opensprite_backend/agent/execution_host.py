"""Run-local effects for API v4. Every inference is a single bounded operation."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import json
import logging
import re
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from opensprite_backend.conversations.models import CompletionReason, RunEventType
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import (
    InferenceFailure, ModelCompleted, ModelFinishReason, ModelMessage,
    ModelRequest, ModelTextDelta, ModelUsage,
)
from opensprite_backend.prompt_logging import PromptLogError
from .context import ConservativeTokenCounter, ContextAssembler, ContextLimitExceeded
from .context.compactor import prepare_compaction_source
from .context.receipt import ReceiptSources
from .events import AGENT_LIMIT_ERROR, CONTEXT_LIMIT_ERROR, CONTEXT_PREPARATION_ERROR, INTERNAL_ERROR, INVALID_PROVIDER_RESPONSE, inference_error
from .execution_errors import ExecutionFailed, RunCancelled
from .plugin import (
    CompactionResult, CompactionSpec, ContextResult, ContextSpec,
    FinalOutput, RunContext, RunResult, StepRequest, StepResult,
)
from .request_trace import Attempt


class _StepDeltaBuffer:
    def __init__(self, repository, step_id):
        self._repository, self._step_id = repository, step_id
        self._pending = ""
        self._first = True
        self._last = monotonic()

    async def append(self, text):
        self._pending += text
        if self._first or len(self._pending) >= 4096 or monotonic() - self._last >= .1:
            await self.flush()

    async def flush(self):
        while self._pending:
            part = self._pending[:4096]
            await asyncio.to_thread(self._repository.append_step_delta, self._step_id, part)
            self._pending = self._pending[len(part):]
        self._first = False
        self._last = monotonic()


class LoopExecutionHost:
    def __init__(self, *, executor, run, cancellation_event, system_prompt,
                 budget, limits, selection, provider_endpoint):
        self._executor = executor
        self._repository = executor._repository
        self._run = deepcopy(run)
        self._budget = deepcopy(budget)
        self._limits = deepcopy(limits)
        self._selection = selection
        self._cancellation = cancellation_event
        self._system_prompt = system_prompt
        self._endpoint = provider_endpoint
        self._deadline = monotonic() + limits.max_duration_seconds
        self._requests = self._compactions = self._generated_chars = self._operation_count = 0
        self._contexts = {}
        self._steps = {}
        self._attempts = {}
        self._operations = set()
        self._result = None
        self._result_signature = None
        self._fatal = None
        self._errors = []
        self._closed = False
        self._public_text = run.partial_text
        self._counter = ConservativeTokenCounter()
        self._log_sequence = 0
        self._new_summaries = set()
        self._continuations = 0

    @property
    def run(self):
        return RunContext(self._run.id, self._run.conversation_id, self._run.user_message_id,
                          self._run.provider_id, self._run.model_id, self._run.output_continuation,
                          deepcopy(self._budget), deepcopy(self._limits),
                          self._selection.plugin_id, self._selection.plugin_version)

    @staticmethod
    def _signature(value):
        return json.dumps(asdict(value), ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)

    def _record_error(self, error):
        self._fatal = error
        self._errors.append((error, (type(error), error.args,
                             self._signature(error.error) if isinstance(error, ExecutionFailed) else None)))

    def _owns_exception(self, error):
        try:
            signature = (type(error), error.args,
                         self._signature(error.error) if isinstance(error, ExecutionFailed) else None)
            return any(owned is error and saved == signature for owned, saved in self._errors)
        except Exception:
            return False

    async def checkpoint(self):
        try:
            self._executor._raise_if_cancelled(self._cancellation)
            if monotonic() > self._deadline:
                raise ExecutionFailed(AGENT_LIMIT_ERROR)
            if self._closed or self._result is not None or self._fatal is not None:
                raise self._fatal or ExecutionFailed(INTERNAL_ERROR)
            await asyncio.sleep(0)
            self._executor._raise_if_cancelled(self._cancellation)
        except Exception as error:
            self._record_error(error)
            raise

    @asynccontextmanager
    async def _operation(self):
        task = None
        try:
            await self.checkpoint()
            if self._operations:
                raise ExecutionFailed(INTERNAL_ERROR)
            self._operation_count += 1
            if self._operation_count > 2048:
                raise ExecutionFailed(AGENT_LIMIT_ERROR)
            task = asyncio.current_task()
            self._operations.add(task)
            yield
        except Exception as error:
            self._record_error(error)
            raise
        finally:
            if task is not None:
                self._operations.discard(task)

    def _context_sources(self, context):
        stored = self._contexts.get(id(context))
        if stored is None or stored[0] is not context or stored[1] != self._signature(context):
            raise ExecutionFailed(INTERNAL_ERROR)
        return stored[2]

    def _check_step(self, step):
        stored = self._steps.get(id(step))
        if stored is None or stored[0] is not step or stored[1] != self._signature(step):
            raise ExecutionFailed(INTERNAL_ERROR)
        return stored[2]

    async def context(self, spec=ContextSpec()):
        async with self._operation():
            if (type(spec) is not ContextSpec or type(spec.recent_messages) is not int
                    or not 1 <= spec.recent_messages <= 64 or type(spec.use_summary) is not bool
                    or not isinstance(spec.summary_format, str)
                    or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", spec.summary_format) is None
                    or spec.selection_tokens is not None and (
                        type(spec.selection_tokens) is not int or not 1 <= spec.selection_tokens <= self._budget.input_budget_tokens)
                    or spec.history_ids is not None and (type(spec.history_ids) is not tuple or len(spec.history_ids) > 200
                        or len(set(spec.history_ids)) != len(spec.history_ids))):
                raise ExecutionFailed(INTERNAL_ERROR)
            page = await asyncio.to_thread(self._repository.list_messages, self._run.conversation_id,
                                           limit=200, before_sequence=None)
            # Freeze admission's history even if a future store allows a newer turn.
            current = next((message for message in page.items if message.id == self._run.user_message_id), None)
            if current is None:
                raise ExecutionFailed(INTERNAL_ERROR)
            summary = (await asyncio.to_thread(self._repository.get_latest_compaction,
                       self._run.conversation_id, summary_format=spec.summary_format)) if spec.use_summary else None
            coverage = 0 if summary is None else summary.covers_through_sequence
            history = tuple(message for message in page.items if coverage < message.sequence <= current.sequence)
            has_older = bool(page.next_before_sequence is not None and page.items
                             and coverage < page.items[0].sequence - 1)
            if spec.history_ids is not None:
                allowed = {message.id for message in history}
                if any(identifier not in allowed for identifier in spec.history_ids):
                    raise ExecutionFailed(INTERNAL_ERROR)
                chosen = set(spec.history_ids) | {current.id}
                history = tuple(message for message in history if message.id in chosen)
                has_older = False
            floor = history[max(0, len(history) - spec.recent_messages):]
            protected = floor[0].sequence if floor else current.sequence
            candidates = await asyncio.to_thread(self._repository.list_messages_after, self._run.conversation_id,
                                                after_sequence=coverage, limit=200)
            candidates = tuple(message for message in candidates if message.sequence < protected)
            error = None
            try:
                assembled = ContextAssembler(self._counter, recent_message_floor=spec.recent_messages).assemble(
                    system_prompt=self._system_prompt, history=history, budget=self._budget,
                    summary=summary, has_older_history=has_older,
                    current_user_message_id=current.id, selection_tokens=spec.selection_tokens)
                messages, needs, estimate = assembled.messages, assembled.needs_compaction, assembled.estimated_input_tokens
            except ContextLimitExceeded:
                messages, needs, estimate, error = (), False, 0, CONTEXT_LIMIT_ERROR
            result = ContextResult(str(uuid4()), messages, deepcopy(self._budget), history,
                                   summary, candidates, needs, estimate, error)
            bindings = []
            # Bind by position; repeated identical historical text has different IDs.
            suffix = messages[-assembled.included_message_count:] if error is None and assembled.included_message_count else ()
            for message, original in zip(suffix, history[-len(suffix):] if suffix else ()):
                bindings.append((message, "currentUser" if original.id == current.id else "history",
                                 original.id, original.sequence))
            sources = ReceiptSources(bindings=tuple(bindings),
                summary=None if summary is None else {"id": summary.id, "version": summary.summary_version,
                    "sourceHash": summary.source_hash, "throughSequence": summary.covers_through_sequence},
                workspace={"id": self._run.workspace_id, "revision": self._run.workspace_revision,
                           "mountManifestHash": self._run.workspace_mount_manifest_hash},
                context_limit=self._budget.context_limit_tokens, input_budget=self._budget.input_budget_tokens)
            if summary is not None and messages and len(messages) > 1:
                sources = replace(sources, bindings=sources.bindings + ((messages[1], "summary", summary.id, summary.covers_through_sequence),))
            self._contexts[id(result)] = (result, self._signature(result), sources)
            return result

    async def infer(self, request):
        async with self._operation():
            if (type(request) is not StepRequest or request.channel not in {"draft", "answer"}
                or request.purpose not in {"main", "continuation"} or type(request.messages) is not tuple
                or not isinstance(request.label, str) or not 1 <= len(request.label) <= 64
                or not isinstance(request.instruction, str) or len(request.instruction) > 65536
                or any(type(message) is not ModelMessage or message.role not in {"user", "assistant"} for message in request.messages)):
                raise ExecutionFailed(INTERNAL_ERROR)
            sources = self._context_sources(request.context)
            if request.context.error is not None:
                return await self._perform(request, (), sources, preflight_error=request.context.error)
            messages = request.context.messages
            if request.instruction:
                messages = (ModelMessage("system", messages[0].content + "\n\nLoop instruction:\n" + request.instruction), *messages[1:])
            messages = (*messages, *request.messages)
            return await self._perform(request, messages, sources)

    async def _perform(self, spec, messages, sources, *, preflight_error=None,
                       purpose=None, compaction_id=None, parent_request_id=None):
        purpose = purpose or spec.purpose
        output_tokens = self._budget.output_reserve_tokens if spec.max_output_tokens is None else spec.max_output_tokens
        if type(output_tokens) is not int or not 1 <= output_tokens <= self._budget.output_reserve_tokens:
            raise ExecutionFailed(INTERNAL_ERROR)
        previous = None
        if spec.retry_of is not None:
            channel = self._check_step(spec.retry_of)
            if spec.retry_of.error is None or not spec.retry_of.error.retryable or channel == "answer" and spec.retry_of.text:
                raise ExecutionFailed(INTERNAL_ERROR)
            previous = self._attempts.get(spec.retry_of.id)
        if len(messages) > 256:
            raise ExecutionFailed(INTERNAL_ERROR)
        if not messages or self._counter.request(messages) > self._budget.input_budget_tokens:
            preflight_error = preflight_error or CONTEXT_LIMIT_ERROR
        if preflight_error is None and self._requests >= self._limits.max_model_requests:
            raise ExecutionFailed(AGENT_LIMIT_ERROR)
        if purpose == "continuation" and spec.retry_of is None and preflight_error is None:
            configured = self._run.output_continuation
            maximum = 64 if configured == "unlimited" else 0 if configured == "off" else int(configured)
            if self._continuations >= maximum:
                raise ExecutionFailed(AGENT_LIMIT_ERROR)
            self._continuations += 1
            await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.RESPONSE_CONTINUATION_STARTED,
                {"attempt": self._continuations, "maxAttempts": None if configured == "unlimited" else maximum})
        row = await asyncio.to_thread(self._repository.start_step, self._run.id,
                                      label=spec.label, channel=spec.channel,
                                      retry_of=None if spec.retry_of is None else spec.retry_of.id)
        buffer = _StepDeltaBuffer(self._repository, row.id)
        text = ""
        input_usage = output_usage = None
        completion = None
        error = preflight_error
        if error is None:
            self._requests += 1
            request = ModelRequest(provider_id=self._run.provider_id, model_id=self._run.model_id,
                provider_endpoint=self._endpoint, response_mode=self._run.response_mode,
                reasoning_resolution=self._run.reasoning_resolution,
                messages=messages, max_output_tokens=output_tokens)
            try:
                self._write_prompt(request, row.sequence)
                await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.MODEL_STARTED,
                    {"providerId": self._run.provider_id, "modelId": self._run.model_id, "responseMode": self._run.response_mode,
                     "maxOutputTokens": output_tokens, "contextTokens": self._counter.request(messages),
                     "contextLimitTokens": self._budget.context_limit_tokens, "inputBudgetTokens": self._budget.input_budget_tokens})
                attempt = Attempt(self._run.id, row.id, purpose,
                    number=1 if previous is None else previous.number + 1,
                    retry_of=None if previous is None else previous.id,
                    cause=None if previous is None else ("provider_context_limit" if spec.retry_of.error.code == "context_limit_exceeded" else spec.retry_of.error.code),
                    compaction_id=compaction_id or (spec.context.summary.id if spec.context.summary is not None and spec.context.summary.id in self._new_summaries else None),
                    parent_request_id=parent_request_id, sources=sources)
                self._attempts[row.id] = attempt
                events = self._executor._with_cancellation(self._executor._gateway.stream(request, attempt=attempt), self._cancellation)
                try:
                    async for event in events:
                        if completion is not None:
                            raise ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                        if isinstance(event, ModelTextDelta):
                            if not event.text or len(event.text) > 16384:
                                raise ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                            if self._generated_chars + len(event.text) > self._limits.max_text_chars:
                                raise ExecutionFailed(AGENT_LIMIT_ERROR)
                            self._generated_chars += len(event.text)
                            text += event.text
                            if spec.channel == "answer":
                                self._public_text += event.text
                            await buffer.append(event.text)
                        elif isinstance(event, ModelCompleted):
                            completion = event.reason
                        elif isinstance(event, ModelUsage):
                            input_usage, output_usage = event.input_tokens, event.output_tokens
                        else:
                            raise ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                finally:
                    await events.aclose()
                if completion not in {ModelFinishReason.FINAL, ModelFinishReason.OUTPUT_LIMIT} or not text.strip():
                    raise ExecutionFailed(INVALID_PROVIDER_RESPONSE)
            except ModelGatewayError as failure:
                error = inference_error(failure.failure)
                if failure.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED:
                    error = replace(error, retryable=True)
                if failure.failure in {InferenceFailure.INVALID_CREDENTIALS, InferenceFailure.PROVIDER_NOT_CONNECTED,
                                       InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE, InferenceFailure.INVALID_PROVIDER_RESPONSE}:
                    await buffer.flush()
                    await asyncio.to_thread(self._repository.finish_step, row.id, status="failed", error_code=error.code)
                    raise ExecutionFailed(error) from None
            except (RunCancelled, asyncio.CancelledError):
                await buffer.flush()
                await asyncio.to_thread(self._repository.finish_step, row.id, status="cancelled")
                raise
            except ExecutionFailed as failure:
                await buffer.flush()
                await asyncio.to_thread(self._repository.finish_step, row.id, status="failed", error_code=failure.error.code)
                raise
            except Exception:
                await buffer.flush()
                await asyncio.to_thread(self._repository.finish_step, row.id, status="failed", error_code="internal_error")
                raise
        await buffer.flush()
        await asyncio.to_thread(self._repository.finish_step, row.id,
            status="failed" if error else "completed",
            finish_reason=None if completion is None else completion.value,
            error_code=None if error is None else error.code, input_tokens=input_usage, output_tokens=output_usage)
        result = StepResult(row.id, text, completion, input_usage, output_usage, error)
        self._steps[id(result)] = (result, self._signature(result), spec.channel)
        await self.checkpoint()
        return result

    def _write_prompt(self, request, sequence):
        if self._run.log_full_prompts and self._executor._prompt_log_writer is not None:
            try:
                self._executor._prompt_log_writer.write(
                    run_id=self._run.id, created_at=datetime.now(UTC), request_sequence=sequence,
                    request_kind=f"step-{sequence:03d}", provider_id=request.provider_id,
                    model_id=request.model_id, response_mode=request.response_mode,
                    reasoning_effort=request.reasoning_resolution.effective if request.reasoning_resolution else None,
                    max_output_tokens=request.max_output_tokens, messages=request.messages)
            except PromptLogError:
                logging.getLogger("opensprite.agent.context").warning("prompt logging unavailable run_id=%s", self._run.id)
                raise ExecutionFailed(INTERNAL_ERROR) from None

    async def compact(self, spec):
        async with self._operation():
            if (type(spec) is not CompactionSpec or type(spec.messages) is not tuple or not spec.messages
                or not isinstance(spec.instruction, str) or not 1 <= len(spec.instruction) <= 65536
                or not isinstance(spec.summary_format, str)
                or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", spec.summary_format) is None
                or type(spec.max_output_tokens) is not int or not 1 <= spec.max_output_tokens <= 65536
                or spec.reason not in {"local_budget", "provider_context_limit"}):
                raise ExecutionFailed(INTERNAL_ERROR)
            self._context_sources(spec.context)
            if spec.parent_request_id is not None and spec.parent_request_id not in self._attempts:
                raise ExecutionFailed(INTERNAL_ERROR)
            latest = await asyncio.to_thread(self._repository.get_latest_compaction,
                self._run.conversation_id, summary_format=spec.summary_format)
            if latest != spec.context.summary:
                raise ExecutionFailed(INTERNAL_ERROR)
            if self._compactions >= self._limits.max_compactions:
                raise ExecutionFailed(AGENT_LIMIT_ERROR)
            allowed = {id(message): message for message in spec.context.compaction_candidates}
            if any(id(message) not in allowed or allowed[id(message)] != message for message in spec.messages):
                raise ExecutionFailed(INTERNAL_ERROR)
            previous = spec.context.summary
            if previous is not None and previous.summary_format != spec.summary_format:
                raise ExecutionFailed(INTERNAL_ERROR)
            source = prepare_compaction_source(previous, spec.messages)
            self._compactions += 1
            compaction_id = str(uuid4())
            await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.CONTEXT_COMPACTION_STARTED,
                {"schemaVersion": 1, "compactionId": compaction_id, "reason": spec.reason,
                 "fromSequence": spec.messages[0].sequence, "throughSequence": spec.messages[-1].sequence,
                 "estimatedBeforeTokens": spec.context.estimated_input_tokens, "inputBudgetTokens": self._budget.input_budget_tokens})
            try:
                messages = (ModelMessage("system", self._system_prompt + "\n\n" + spec.instruction),
                            ModelMessage("user", source.prompt))
                sources = ReceiptSources(history_ids=tuple(message.id for message in spec.messages),
                    workspace={"id": self._run.workspace_id, "revision": self._run.workspace_revision,
                               "mountManifestHash": self._run.workspace_mount_manifest_hash},
                    context_limit=self._budget.context_limit_tokens, input_budget=self._budget.input_budget_tokens)
                request = StepRequest(spec.context, label="summary", channel="draft", max_output_tokens=min(spec.max_output_tokens, self._budget.output_reserve_tokens))
                step = await self._perform(request, messages, sources, purpose="compaction", compaction_id=compaction_id,
                                           parent_request_id=spec.parent_request_id)
                if step.error is not None or step.finish_reason is not ModelFinishReason.FINAL or len(step.text) > 262144:
                    await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.CONTEXT_COMPACTION_FAILED,
                        {"schemaVersion": 1, "compactionId": compaction_id, "errorCode": "provider_failed" if step.error else "preparation_failed"})
                    return CompactionResult(step, None)
                summary = await asyncio.to_thread(self._repository.append_compaction,
                    conversation_id=self._run.conversation_id, covers_through_sequence=source.covers_through_sequence,
                    summary=step.text, source_hash=source.source_hash, provider_id=self._run.provider_id, model_id=self._run.model_id,
                    input_tokens=step.input_tokens or 0, output_tokens=step.output_tokens or 0,
                    producer_plugin_id=self._selection.plugin_id, producer_plugin_version=self._selection.plugin_version,
                    summary_format=spec.summary_format, compaction_id=compaction_id)
                self._new_summaries.add(summary.id)
                await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.CONTEXT_COMPACTION_COMPLETED,
                    {"schemaVersion": 1, "compactionId": compaction_id, "throughSequence": summary.covers_through_sequence,
                     "inputTokens": summary.input_tokens, "outputTokens": summary.output_tokens})
                return CompactionResult(step, summary)
            except (RunCancelled, asyncio.CancelledError):
                await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.CONTEXT_COMPACTION_CANCELLED,
                    {"schemaVersion": 1, "compactionId": compaction_id, "reason": "cancelled"})
                raise
            except Exception:
                await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.CONTEXT_COMPACTION_FAILED,
                    {"schemaVersion": 1, "compactionId": compaction_id, "errorCode": "preparation_failed"})
                raise

    async def finish(self, output):
        async with self._operation():
            if type(output) is not FinalOutput or type(output.sources) is not tuple or type(output.completion_reason) is not CompletionReason:
                raise ExecutionFailed(INTERNAL_ERROR)
            for step in output.sources:
                self._check_step(step)
            error = None
            if output.failure is not None:
                error = {"context_limit_exceeded": CONTEXT_LIMIT_ERROR,
                         "context_preparation_failed": CONTEXT_PREPARATION_ERROR,
                         "loop_failed": INTERNAL_ERROR}.get(output.failure)
                if error is None or output.error_step is not None or output.context_error is not None:
                    raise ExecutionFailed(INTERNAL_ERROR)
            if output.error_step is not None:
                self._check_step(output.error_step)
                error = output.error_step.error
                if error is None:
                    raise ExecutionFailed(INTERNAL_ERROR)
            if output.context_error is not None:
                self._context_sources(output.context_error)
                if error is not None or output.context_error.error is None:
                    raise ExecutionFailed(INTERNAL_ERROR)
                error = output.context_error.error
            if error is None:
                if not output.sources or not isinstance(output.text, str) or not output.text.strip() or len(output.text) > self._limits.max_text_chars:
                    raise ExecutionFailed(INTERNAL_ERROR)
                # Public output is append-only. Revision Loops keep drafts private.
                if not output.text.startswith(self._public_text):
                    raise ExecutionFailed(INTERNAL_ERROR)
                remaining = output.text[len(self._public_text):]
                for index in range(0, len(remaining), 4096):
                    self._executor._raise_if_cancelled(self._cancellation)
                    await asyncio.to_thread(self._repository.append_assistant_delta, self._run.id, remaining[index:index+4096])
                self._public_text = output.text
            self._result = RunResult(self._public_text, output.completion_reason, error)
            self._result_signature = self._signature(self._result)
            return self._result

    async def _validate_result(self, result):
        self._executor._raise_if_cancelled(self._cancellation)
        if monotonic() > self._deadline:
            error = ExecutionFailed(AGENT_LIMIT_ERROR)
            self._record_error(error)
            raise error
        if (self._fatal is not None or self._operations
            or self._result is None or result is not self._result or self._signature(result) != self._result_signature):
            error = self._fatal or ExecutionFailed(INTERNAL_ERROR)
            self._record_error(error)
            raise error

    async def _close(self):
        self._closed = True
        operations = tuple(self._operations - {asyncio.current_task()})
        for task in operations:
            task.cancel()
        if operations:
            await asyncio.gather(*operations, return_exceptions=True)
