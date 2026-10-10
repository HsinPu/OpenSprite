"""Run ownership and terminal transactions, independent of Loop strategy."""
from __future__ import annotations

import asyncio
from dataclasses import asdict

from opensprite_backend.conversations.models import MAX_ASSISTANT_CHARS, RunStatus, StoreFailure
from opensprite_backend.conversations.repository import ConversationStoreError
from opensprite_backend.inference.gateway import ModelGatewayError
from .events import INTERNAL_ERROR, inference_error
from .execution_errors import ExecutionFailed, RunCancelled
from .execution_host import LoopExecutionHost
from .plugin import ExecutionLimits
from opensprite_backend.agent import plugin_conversion as convert
from .run_control import RunControl
from .execution_input import PreparedRun, RunPreparation
from .request_trace import TracedGateway

class RunExecutor:
    def __init__(self, *, repository, gateway, max_model_requests=128,
                 max_compactions_per_run=32, max_assistant_chars=MAX_ASSISTANT_CHARS,
                 max_duration_seconds=600):
        if type(max_model_requests) is not int or not 1 <= max_model_requests <= 128:
            raise ValueError("invalid request bound")
        if max_compactions_per_run is None:
            max_compactions_per_run = 32
        if type(max_compactions_per_run) is not int or not 1 <= max_compactions_per_run <= 32:
            raise ValueError("invalid compaction bound")
        if type(max_assistant_chars) is not int or not 1 <= max_assistant_chars <= MAX_ASSISTANT_CHARS:
            raise ValueError("invalid output bound")
        if type(max_duration_seconds) not in (int, float) or not 0 < max_duration_seconds <= 3600:
            raise ValueError("invalid duration bound")
        self._repository = repository
        self._gateway = TracedGateway(gateway, repository)
        self._limits = ExecutionLimits(max_model_requests, max_compactions_per_run,
                                       max_duration_seconds, max_assistant_chars)

    async def execute(self, run_id, cancellation_event, *, preparation: RunPreparation):
        run = await asyncio.to_thread(self._repository.get_run, run_id)
        if run is None:
            raise ConversationStoreError(StoreFailure.NOT_FOUND)
        if run.status is not RunStatus.QUEUED:
            return run
        if cancellation_event.is_set():
            return await asyncio.to_thread(self._repository.request_cancel, run_id)
        host = None
        control = RunControl(cancellation_event, self._limits)
        try:
            prepared = await control.wait(preparation.prepare(run))
            if (type(prepared) is not PreparedRun or prepared.run_id != run.id
                or not isinstance(prepared.system_prompt, str) or not 1 <= len(prepared.system_prompt) <= 128 * 1024
                or not prepared.system_prompt.strip()
                or type(prepared.model_limits.context_tokens) is not int or prepared.model_limits.context_tokens < 2
                or type(prepared.model_limits.output_tokens) is not int
                or not 1 <= prepared.model_limits.output_tokens < prepared.model_limits.context_tokens):
                raise ExecutionFailed(INTERNAL_ERROR)
            plugin = prepared.selection.create()
            run = await asyncio.to_thread(
                self._repository.mark_run_started, run_id, prepared.workspace_availability,
                tuple(asdict(mount) for mount in prepared.workspace_mounts))
            control.check()
            if run.reasoning_resolution is None:
                run = await asyncio.to_thread(self._repository.set_reasoning_resolution, run.id,
                                              prepared.reasoning_resolution)
            host = LoopExecutionHost(repository=self._repository, gateway=self._gateway, control=control,
                                     run=run, system_prompt=prepared.system_prompt, model_limits=prepared.model_limits,
                                     selection=prepared.selection, provider_endpoint=prepared.provider_endpoint,
                                     request_observer=prepared.request_observer)
            try:
                result = await control.wait(plugin.execute(host))
                await host._validate_result(result)
            except Exception as error:
                if cancellation_event.is_set():
                    raise RunCancelled() from None
                if control.owns_deadline_failure(error):
                    raise
                control.check()
                if host._owns_exception(error):
                    raise
                raise ExecutionFailed(INTERNAL_ERROR) from None
            finally:
                await host._close()
            if result.error is not None:
                return await self._fail(run_id, convert.stored_error(result.error))
            control.check()
            try:
                return (await asyncio.to_thread(self._repository.complete_run, run_id,
                                               result.text, convert.completion_reason(result.completion_reason))).run
            except ConversationStoreError as error:
                if error.failure is StoreFailure.INVALID_STATE:
                    current = await asyncio.to_thread(self._repository.get_run, run_id)
                    if current and current.status in {RunStatus.CANCELLING, RunStatus.CANCELLED}:
                        return await self._cancel(run_id)
                raise
        except RunCancelled:
            return await self._cancel(run_id)
        except ExecutionFailed as error:
            return await self._fail(run_id, error.error, limit=error.limit)
        except ModelGatewayError as error:
            return await self._fail(run_id, inference_error(error.failure))
        except ConversationStoreError:
            raise
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            if cancellation_event.is_set():
                return await self._cancel(run_id)
            return await self._fail(run_id, INTERNAL_ERROR)
        except Exception:
            return await self._fail(run_id, INTERNAL_ERROR)

    async def _fail(self, run_id, error, *, limit=None):
        current = await asyncio.to_thread(self._repository.get_run, run_id)
        if current and current.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED}:
            return current
        if current and current.status is RunStatus.CANCELLING:
            return await self._cancel(run_id)
        return await asyncio.to_thread(self._repository.fail_run, run_id, error, limit=limit)

    async def _cancel(self, run_id):
        current = await asyncio.to_thread(self._repository.get_run, run_id)
        if current and current.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED}:
            return current
        if current and current.status is RunStatus.QUEUED:
            current = await asyncio.to_thread(self._repository.request_cancel, run_id)
            if current.status is RunStatus.CANCELLED:
                return current
        try:
            return await asyncio.to_thread(self._repository.mark_run_cancelled, run_id)
        except ConversationStoreError as error:
            if error.failure is StoreFailure.INVALID_STATE:
                current = await asyncio.to_thread(self._repository.get_run, run_id)
                if current and current.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED}:
                    return current
            raise
