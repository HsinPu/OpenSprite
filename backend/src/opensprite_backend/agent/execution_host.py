"""Run-local effects for API v5. Every inference is a single bounded operation."""
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

from opensprite_backend.conversations.models import RunEventType, RunSnapshot
from opensprite_backend.conversations.repository import ConversationRepository
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import (
    InferenceFailure, ModelCompleted, ModelFinishReason,
    ModelRequest, ModelTextDelta, ModelUsage,
)
from .context.counter import ConservativeTokenCounter
from .summary_sources import summary_coverage
from opensprite_backend.agent import plugin_conversion as convert
from .context.receipt import ReceiptSources
from .events import CONTEXT_LIMIT_ERROR, CONTEXT_PREPARATION_ERROR, INTERNAL_ERROR, INVALID_PROVIDER_RESPONSE, inference_error
from .execution_errors import ExecutionFailed, RunCancelled
from .run_control import RunControl
from .execution_input import ExecutionPluginSelection
from .plugin import (
    ContextReadRequest, ContextSnapshot, InputSource, SummarySource, SummaryWriteRequest,
    FinalOutput, RunContext, RunResult, StepRequest, StepResult, ModelLimits, CompletionReason, ModelMessage,
)
from .request_trace import Attempt, TracedGateway
from .request_observer import ModelRequestObserver


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
    def __init__(self, *, repository: ConversationRepository, gateway: TracedGateway,
                 control: RunControl, run: RunSnapshot, system_prompt: str,
                 model_limits: ModelLimits, selection: ExecutionPluginSelection,
                 provider_endpoint: ProviderEndpointSnapshot | None,
                 request_observer: ModelRequestObserver | None = None):
        self._repository = repository
        self._gateway = gateway
        self._control = control
        self._request_observer = request_observer
        self._run = deepcopy(run)
        self._model_limits = deepcopy(model_limits)
        self._limits = control.limits
        self._selection = selection
        self._system_prompt = system_prompt
        self._endpoint = provider_endpoint
        self._contexts = {}
        self._summary_steps = {}
        self._current_user = None
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
                          self._run.provider_id, self._run.model_id,
                          self._run.context_budget, self._run.output_budget,
                          deepcopy(self._model_limits), self._system_prompt, deepcopy(self._limits),
                          self._selection.plugin_id, self._selection.plugin_version)

    @staticmethod
    def _signature(value):
        return json.dumps(asdict(value), ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)

    def _record_error(self, error):
        if any(owned is error for owned, _ in self._errors):
            return
        self._fatal = error
        self._errors.append((error, (type(error), error.args,
                             (self._signature(error.error), None if error.limit is None else self._signature(error.limit)) if isinstance(error, ExecutionFailed) else None)))

    def _owns_exception(self, error):
        try:
            signature = (type(error), error.args,
                         (self._signature(error.error), None if error.limit is None else self._signature(error.limit)) if isinstance(error, ExecutionFailed) else None)
            return any(owned is error and saved == signature for owned, saved in self._errors)
        except Exception:
            return False

    async def checkpoint(self):
        try:
            await self._control.checkpoint()
            if self._closed or self._result is not None or self._fatal is not None:
                raise self._fatal or ExecutionFailed(INTERNAL_ERROR)
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
            self._control.consume_operation()
            task = asyncio.current_task()
            self._operations.add(task)
            yield
        except Exception as error:
            self._record_error(error)
            raise
        finally:
            if task is not None:
                self._operations.discard(task)

    def _owned_snapshot(self, snapshot):
        stored = self._contexts.get(id(snapshot))
        if stored is None or stored[0] is not snapshot or stored[1] != self._signature(snapshot):
            raise ExecutionFailed(INTERNAL_ERROR)
        return stored[2]

    def _check_step(self, step):
        stored = self._steps.get(id(step))
        if stored is None or stored[0] is not step or stored[1] != self._signature(step):
            raise ExecutionFailed(INTERNAL_ERROR)
        return stored[2]

    async def read_context(self, request=ContextReadRequest()):
        async with self._operation():
            if (type(request) is not ContextReadRequest or type(request.limit) is not int
                or not 1 <= request.limit <= 200
                or request.before_sequence is not None and (type(request.before_sequence) is not int or request.before_sequence < 1)
                or request.after_sequence is not None and (type(request.after_sequence) is not int or request.after_sequence < 0)
                or request.before_sequence is not None and request.after_sequence is not None
                or request.summary_format is not None and (not isinstance(request.summary_format, str)
                    or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", request.summary_format) is None)):
                raise ExecutionFailed(INTERNAL_ERROR)
            if self._current_user is None:
                self._current_user = await asyncio.to_thread(self._repository.get_message, self._run.user_message_id)
            current = self._current_user
            if current is None or current.conversation_id != self._run.conversation_id or current.run_id != self._run.id:
                raise ExecutionFailed(INTERNAL_ERROR)
            before = after = None
            if request.after_sequence is None:
                page = await asyncio.to_thread(self._repository.list_messages, self._run.conversation_id,
                    limit=request.limit, before_sequence=min(request.before_sequence or current.sequence, current.sequence))
                history, before = page.items, page.next_before_sequence
            else:
                history = await asyncio.to_thread(self._repository.list_messages_after, self._run.conversation_id,
                    after_sequence=request.after_sequence, limit=request.limit)
                history = tuple(item for item in history if item.sequence < current.sequence)
                if history and len(history) == request.limit and history[-1].sequence < current.sequence - 1:
                    after = history[-1].sequence
            summary = (None if request.summary_format is None else await asyncio.to_thread(
                self._repository.get_latest_compaction, self._run.conversation_id,
                summary_format=request.summary_format, before_sequence=current.sequence))
            snapshot = ContextSnapshot(str(uuid4()), convert.message(current), tuple(convert.message(item) for item in history), convert.summary(summary), before, after)
            self._contexts[id(snapshot)] = (snapshot, self._signature(snapshot),
                                           {item.id: item for item in (*snapshot.history, snapshot.current_user)})
            return snapshot

    @staticmethod
    def _validate_messages(messages):
        if (type(messages) is not tuple or not 1 <= len(messages) <= 256
            or any(type(item) is not ModelMessage or item.role not in {"system", "user", "assistant"}
                   or not isinstance(item.content, str) or not 1 <= len(item.content) <= 1048576 for item in messages)):
            raise ExecutionFailed(INTERNAL_ERROR)

    async def estimate_input(self, messages):
        async with self._operation():
            self._validate_messages(messages)
            return self._counter.request(messages)

    def _input_sources(self, request, messages):
        if type(request.sources) is not tuple or len(request.sources) > 256:
            raise ExecutionFailed(INTERNAL_ERROR)
        bindings, history_ids, step_ids, used_positions, summary_meta = [], [], [], set(), None
        for source in request.sources:
            if (type(source) is not InputSource or type(source.message_index) is not int
                or not 0 <= source.message_index < len(request.messages) or source.message_index in used_positions
                or type(source.message_ids) is not tuple or len(source.message_ids) > 200
                or len(set(source.message_ids)) != len(source.message_ids)):
                raise ExecutionFailed(INTERNAL_ERROR)
            used_positions.add(source.message_index)
            if source.snapshot is None and (source.message_ids or source.summary_id is not None):
                raise ExecutionFailed(INTERNAL_ERROR)
            kind, identifier, sequence = None, None, 0
            if source.snapshot is not None:
                owned = self._owned_snapshot(source.snapshot)
                for identifier in source.message_ids:
                    if identifier not in owned:
                        raise ExecutionFailed(INTERNAL_ERROR)
                    item = owned[identifier]
                    history_ids.append(identifier)
                    kind = "currentUser" if identifier == self._run.user_message_id else "history"
                    sequence = item.sequence
                if source.summary_id is not None:
                    summary = source.snapshot.summary
                    if summary is None or source.summary_id != summary.id:
                        raise ExecutionFailed(INTERNAL_ERROR)
                    kind, identifier, sequence = "summary", summary.id, summary.covers_through_sequence
                    metadata = {"id": summary.id, "version": summary.summary_version,
                                "sourceHash": summary.source_hash, "throughSequence": summary.covers_through_sequence}
                    if summary_meta is not None and summary_meta != metadata:
                        raise ExecutionFailed(INTERNAL_ERROR)
                    summary_meta = metadata
            if type(source.steps) is not tuple or len(source.steps) > 128:
                raise ExecutionFailed(INTERNAL_ERROR)
            for step in source.steps:
                self._check_step(step)
                step_ids.append(step.id)
                kind, identifier = "assistant", step.id
            if kind is None:
                raise ExecutionFailed(INTERNAL_ERROR)
            bindings.append((messages[source.message_index], kind, identifier, sequence))
        if request.purpose != "compaction" and self._run.user_message_id not in history_ids:
            raise ExecutionFailed(INTERNAL_ERROR)
        return ReceiptSources(bindings=tuple(bindings), history_ids=tuple(dict.fromkeys(history_ids)),
            step_ids=tuple(dict.fromkeys(step_ids)),
            summary=summary_meta, workspace={"id": self._run.workspace_id, "revision": self._run.workspace_revision,
                "mountManifestHash": self._run.workspace_mount_manifest_hash},
            context_limit=self._model_limits.context_tokens,
            input_budget=request.input_limit_tokens or self._model_limits.context_tokens - request.max_output_tokens)

    async def _summary_details(self, source):
        if (type(source) is not SummarySource or type(source.snapshots) is not tuple or not source.snapshots
            or len(source.snapshots) > 200 or type(source.message_ids) is not tuple or not source.message_ids
            or len(source.message_ids) > 200 or len(set(source.message_ids)) != len(source.message_ids)
            or not isinstance(source.summary_format, str)
            or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", source.summary_format) is None
            or source.reason not in {"local_budget", "provider_context_limit"}
            or type(source.estimated_before_tokens) is not int or not 0 <= source.estimated_before_tokens <= 2**53-1):
            raise ExecutionFailed(INTERNAL_ERROR)
        owned, previous = {}, None
        for snapshot in source.snapshots:
            owned.update(self._owned_snapshot(snapshot))
            if snapshot.summary is not None and snapshot.summary.id == source.previous_summary_id:
                previous = snapshot.summary
        if source.previous_summary_id is not None and (previous is None or previous.summary_format != source.summary_format):
            raise ExecutionFailed(INTERNAL_ERROR)
        if any(identifier not in owned for identifier in source.message_ids):
            raise ExecutionFailed(INTERNAL_ERROR)
        messages = tuple(owned[identifier] for identifier in source.message_ids)
        if any(item.sequence >= self._current_user.sequence for item in messages):
            raise ExecutionFailed(INTERNAL_ERROR)
        latest = await asyncio.to_thread(self._repository.get_latest_compaction, self._run.conversation_id,
            summary_format=source.summary_format, before_sequence=self._current_user.sequence)
        if convert.summary(latest) != previous:
            raise ExecutionFailed(INTERNAL_ERROR)
        try:
            coverage = summary_coverage(previous, messages)
        except ValueError:
            raise ExecutionFailed(INTERNAL_ERROR) from None
        return {"coverage": coverage, "previous": deepcopy(previous), "format": source.summary_format,
                "reason": source.reason, "estimate": source.estimated_before_tokens,
                "id": str(uuid4()), "ended": False}

    async def infer(self, request):
        async with self._operation():
            if (type(request) is not StepRequest or request.channel not in {"draft", "answer"}
                or request.purpose not in {"main", "continuation", "compaction"}
                or not isinstance(request.label, str) or not 1 <= len(request.label) <= 64
                or type(request.max_output_tokens) is not int or not 1 <= request.max_output_tokens <= self._model_limits.output_tokens
                or request.input_limit_tokens is not None and (type(request.input_limit_tokens) is not int
                    or not 1 <= request.input_limit_tokens <= self._model_limits.context_tokens - request.max_output_tokens)):
                raise ExecutionFailed(INTERNAL_ERROR)
            self._validate_messages(request.messages)
            if request.messages[0].role != "system" or not request.messages[0].content.startswith(self._system_prompt):
                raise ExecutionFailed(INTERNAL_ERROR)
            if request.parent_request_id is not None and request.parent_request_id not in self._attempts:
                raise ExecutionFailed(INTERNAL_ERROR)
            messages = convert.model_messages(request.messages)
            sources = self._input_sources(request, messages)
            details = None
            if request.purpose == "compaction":
                if request.channel != "draft" or request.summary_source is None:
                    raise ExecutionFailed(INTERNAL_ERROR)
                details = await self._summary_details(request.summary_source)
                if tuple(sources.history_ids) != request.summary_source.message_ids:
                    raise ExecutionFailed(INTERNAL_ERROR)
            elif request.summary_source is not None:
                raise ExecutionFailed(INTERNAL_ERROR)
            return await self._perform(request, messages, sources, summary_details=details,
                parent_request_id=request.parent_request_id)

    async def _perform(self, spec, messages, sources, *, preflight_error=None,
                       purpose=None, summary_details=None, parent_request_id=None):
        purpose = purpose or spec.purpose
        output_tokens = spec.max_output_tokens
        input_budget = spec.input_limit_tokens or self._model_limits.context_tokens - output_tokens
        compaction_id = None if summary_details is None else summary_details["id"]
        if type(output_tokens) is not int or not 1 <= output_tokens <= self._model_limits.output_tokens:
            raise ExecutionFailed(INTERNAL_ERROR)
        previous = None
        if spec.retry_of is not None:
            channel = self._check_step(spec.retry_of)
            if spec.retry_of.error is None or not spec.retry_of.error.retryable or channel == "answer" and spec.retry_of.text:
                raise ExecutionFailed(INTERNAL_ERROR)
            previous = self._attempts.get(spec.retry_of.id)
        if len(messages) > 256:
            raise ExecutionFailed(INTERNAL_ERROR)
        if not messages or self._counter.request(messages) > input_budget:
            preflight_error = preflight_error or CONTEXT_LIMIT_ERROR
        if preflight_error is None:
            self._control.check_request(summary=summary_details is not None)
        if summary_details is not None and preflight_error is None:
            coverage = summary_details["coverage"]
            await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.CONTEXT_COMPACTION_STARTED,
                {"schemaVersion": 1, "compactionId": compaction_id, "reason": summary_details["reason"],
                 "fromSequence": coverage.first_sequence, "throughSequence": coverage.through_sequence,
                 "estimatedBeforeTokens": summary_details["estimate"], "inputBudgetTokens": input_budget})
        if purpose == "continuation" and spec.retry_of is None and preflight_error is None:
            self._continuations += 1
            await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.RESPONSE_CONTINUATION_STARTED,
                {"attempt": self._continuations, "maxAttempts": None})
        row = await asyncio.to_thread(self._repository.start_step, self._run.id,
                                      label=spec.label, channel=spec.channel,
                                      retry_of=None if spec.retry_of is None else spec.retry_of.id)
        if summary_details is not None and preflight_error is None:
            self._summary_steps[row.id] = summary_details
        buffer = _StepDeltaBuffer(self._repository, row.id)
        text = ""
        input_usage = output_usage = None
        completion = None
        error = preflight_error
        if error is None:
            request = ModelRequest(provider_id=self._run.provider_id, model_id=self._run.model_id,
                provider_endpoint=self._endpoint, response_mode=self._run.response_mode,
                reasoning_resolution=self._run.reasoning_resolution,
                messages=messages, max_output_tokens=output_tokens)
            try:
                self._observe_request(request, row.sequence)
                await asyncio.to_thread(self._repository.append_run_event, self._run.id, RunEventType.MODEL_STARTED,
                    {"providerId": self._run.provider_id, "modelId": self._run.model_id, "responseMode": self._run.response_mode,
                     "maxOutputTokens": output_tokens, "contextTokens": self._counter.request(messages),
                     "contextLimitTokens": self._model_limits.context_tokens, "inputBudgetTokens": input_budget})
                attempt = Attempt(self._run.id, row.id, purpose,
                    number=1 if previous is None else previous.number + 1,
                    retry_of=None if previous is None else previous.id,
                    cause=None if previous is None else ("provider_context_limit" if spec.retry_of.error.code == "context_limit_exceeded" else spec.retry_of.error.code),
                    compaction_id=compaction_id or (sources.summary["id"] if sources.summary and sources.summary["id"] in self._new_summaries else None),
                    parent_request_id=parent_request_id, sources=sources)
                self._attempts[row.id] = attempt
                self._control.consume_request(summary=summary_details is not None)
                events = self._control.stream(self._gateway.stream(request, attempt=attempt))
                try:
                    async for event in events:
                        if completion is not None:
                            raise ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                        if isinstance(event, ModelTextDelta):
                            if not event.text or len(event.text) > 16384:
                                raise ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                            self._control.consume_text(len(event.text))
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
                if summary_details is not None:
                    summary_details["failure"] = "provider_failed"
                error = inference_error(failure.failure)
                if failure.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED:
                    error = replace(error, retryable=True)
                if failure.failure in {InferenceFailure.INVALID_CREDENTIALS, InferenceFailure.PROVIDER_NOT_CONNECTED,
                                       InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE, InferenceFailure.INVALID_PROVIDER_RESPONSE}:
                    await buffer.flush()
                    await asyncio.to_thread(self._repository.finish_step, row.id, status="failed", error_code=error.code)
                    raise ExecutionFailed(error) from None
            except (RunCancelled, asyncio.CancelledError):
                if summary_details is not None:
                    summary_details["cancelled"] = self._control.cancellation_requested or not self._control.expired
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
        result = StepResult(row.id, text, convert.finish_reason(completion), input_usage, output_usage, convert.error(error))
        self._steps[id(result)] = (result, self._signature(result), spec.channel)
        await self.checkpoint()
        return result

    def _observe_request(self, request, sequence):
        if self._request_observer is not None:
            try:
                self._request_observer.record_request(run_id=self._run.id, created_at=datetime.now(UTC),
                                                      request_sequence=sequence, request=deepcopy(request))
            except Exception:
                logging.getLogger("opensprite.agent.context").warning("request_observer_unavailable run_id=%s", self._run.id)

    async def save_summary(self, request):
        async with self._operation():
            if (type(request) is not SummaryWriteRequest or not isinstance(request.text, str)
                or not 1 <= len(request.text) <= 262144 or not request.text.strip()):
                raise ExecutionFailed(INTERNAL_ERROR)
            self._check_step(request.step)
            details = self._summary_steps.get(request.step.id)
            if details is None or request.step.error is not None:
                raise ExecutionFailed(INTERNAL_ERROR)
            coverage, previous = details["coverage"], details["previous"]
            summary = await asyncio.to_thread(self._repository.append_compaction,
                conversation_id=self._run.conversation_id, covers_through_sequence=coverage.through_sequence,
                summary=request.text, source_hash=coverage.source_hash,
                provider_id=self._run.provider_id, model_id=self._run.model_id,
                input_tokens=request.step.input_tokens or 0, output_tokens=request.step.output_tokens or 0,
                producer_plugin_id=self._selection.plugin_id, producer_plugin_version=self._selection.plugin_version,
                summary_format=details["format"], compaction_id=details["id"],
                source_step_id=request.step.id, source_first_sequence=coverage.first_sequence,
                expected_previous_summary_id=None if previous is None else previous.id, run_id=self._run.id)
            details["ended"] = True
            self._new_summaries.add(summary.id)
            return convert.summary(summary)

    async def _end_pending_summaries(self):
        for details in self._summary_steps.values():
            if details["ended"]:
                continue
            cancelled = self._control.cancellation_requested or details.get("cancelled", False)
            event = RunEventType.CONTEXT_COMPACTION_CANCELLED if cancelled else RunEventType.CONTEXT_COMPACTION_FAILED
            data = {"schemaVersion": 1, "compactionId": details["id"],
                    **({"reason": "cancelled"} if cancelled else {"errorCode": details.get("failure", "preparation_failed")})}
            await asyncio.to_thread(self._repository.append_run_event, self._run.id, event, data)
            details["ended"] = True

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
                if error is None or output.error_step is not None:
                    raise ExecutionFailed(INTERNAL_ERROR)
            if output.error_step is not None:
                self._check_step(output.error_step)
                error = convert.stored_error(output.error_step.error) if output.error_step.error else None
                if error is None:
                    raise ExecutionFailed(INTERNAL_ERROR)
            if error is None:
                if not output.sources or not isinstance(output.text, str) or not output.text.strip() or len(output.text) > self._limits.max_text_chars:
                    raise ExecutionFailed(INTERNAL_ERROR)
                # Public output is append-only. Revision Loops keep drafts private.
                if not output.text.startswith(self._public_text):
                    raise ExecutionFailed(INTERNAL_ERROR)
                remaining = output.text[len(self._public_text):]
                for index in range(0, len(remaining), 4096):
                    self._control.check()
                    await asyncio.to_thread(self._repository.append_assistant_delta, self._run.id, remaining[index:index+4096])
                self._public_text = output.text
            self._result = RunResult(self._public_text, output.completion_reason, convert.error(error))
            self._result_signature = self._signature(self._result)
            return self._result

    async def _validate_result(self, result):
        try:
            self._control.check()
        except Exception as error:
            self._record_error(error)
            raise
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
        await self._end_pending_summaries()
