"""Run ownership and terminal transactions, independent of Loop strategy."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from copy import deepcopy
from time import monotonic
from typing import TypeVar

from opensprite_backend.conversations.models import MAX_ASSISTANT_CHARS, RunStatus, StoreFailure
from opensprite_backend.conversations.repository import ConversationStoreError
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.response_modes import resolve_response_mode
from opensprite_backend.workspaces import DEFAULT_WORKSPACE_ID, DefaultWorkspaceResolver
from .context import ModelCapabilityNotFound, ModelCapabilityProviderError
from .events import INTERNAL_ERROR, CONTEXT_PREPARATION_ERROR, WORKSPACE_CONTEXT_ERROR, limit_failure, inference_error
from .execution_errors import ExecutionFailed, RunCancelled
from .execution_host import LoopExecutionHost
from .plugin import ExecutionLimits
from .context.limits import resolve_model_limits
from .plugin_catalog import ExecutionPluginCatalog, ExecutionPluginSelection
from .prompt import StaticSystemPromptProvider
from .request_trace import TracedGateway

_T = TypeVar("_T")


class RunExecutor:
    def __init__(self, *, repository, gateway, capability_resolver,
                 system_prompt_provider=None, max_model_requests=128,
                 max_compactions_per_run=32, max_assistant_chars=MAX_ASSISTANT_CHARS,
                 max_duration_seconds=600, prompt_log_writer=None, plugin_factory=None):
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
        self._capability_resolver = capability_resolver
        self._system_prompt_provider = system_prompt_provider or StaticSystemPromptProvider()
        self._prompt_log_writer = prompt_log_writer
        self._plugin_factory = plugin_factory
        self._limits = ExecutionLimits(max_model_requests, max_compactions_per_run,
                                       max_duration_seconds, max_assistant_chars)

    async def execute(self, run_id, cancellation_event, workspace=None,
                      provider_endpoint=None, *, execution_plugin=None):
        run = await asyncio.to_thread(self._repository.get_run, run_id)
        if run is None:
            raise ConversationStoreError(StoreFailure.NOT_FOUND)
        if run.status is not RunStatus.QUEUED:
            return run
        if cancellation_event.is_set():
            return await asyncio.to_thread(self._repository.request_cancel, run_id)
        if workspace is None:
            if run.workspace_id != DEFAULT_WORKSPACE_ID:
                return await self._fail(run_id, WORKSPACE_CONTEXT_ERROR)
            workspace = DefaultWorkspaceResolver().execution_context(run.workspace_id)
        host = None
        deadline = monotonic() + self._limits.max_duration_seconds
        def deadline_failure():
            used = max(0, monotonic() - deadline + self._limits.max_duration_seconds)
            return limit_failure("duration_seconds", self._limits.max_duration_seconds, round(used, 6))
        try:
            if (workspace.id, workspace.revision, workspace.name, workspace.root_hash,
                workspace.mount_manifest_hash) != (
                    run.workspace_id, run.workspace_revision, run.workspace_name_snapshot,
                    run.workspace_root_hash, run.workspace_mount_manifest_hash):
                return await self._fail(run_id, WORKSPACE_CONTEXT_ERROR)
            if execution_plugin is None:
                execution_plugin = (ExecutionPluginSelection("standard", "testing", self._plugin_factory)
                                    if self._plugin_factory else ExecutionPluginCatalog().resolve("standard"))
            plugin = execution_plugin.create()
            run = await asyncio.to_thread(
                self._repository.mark_run_started, run_id, workspace.availability,
                tuple({"id": mount.id, "alias": mount.alias, "rootHash": mount.root_hash,
                       "accessMode": mount.access_mode.value, "enabled": mount.enabled,
                       "availability": mount.availability.value} for mount in workspace.mounts))
            if deadline <= monotonic():
                raise deadline_failure()
            async with asyncio.timeout(max(0, deadline - monotonic())):
                system_prompt = await self._await_with_cancellation(
                    self._system_prompt_provider.build(run_id=run_id, workspace=workspace), cancellation_event)
                capability = await self._await_with_cancellation(
                    self._resolve_capability(run, provider_endpoint), cancellation_event)
            if run.reasoning_resolution is None:
                run = await asyncio.to_thread(self._repository.set_reasoning_resolution, run.id,
                                              resolve_response_mode(run.response_mode, capability.reasoning_efforts))
            model_limits = resolve_model_limits(run.context_budget, capability, run.output_budget)
            host = LoopExecutionHost(executor=self, run=run, cancellation_event=cancellation_event,
                                     system_prompt=system_prompt, model_limits=model_limits,
                                     limits=deepcopy(self._limits), selection=execution_plugin,
                                     provider_endpoint=provider_endpoint)
            host._deadline = deadline
            execution_timeout = asyncio.timeout(max(0, deadline - monotonic()))
            try:
                async with execution_timeout:
                    result = await self._await_with_cancellation(plugin.execute(host), cancellation_event)
                await host._validate_result(result)
            except TimeoutError:
                raise (deadline_failure() if execution_timeout.expired() else ExecutionFailed(INTERNAL_ERROR)) from None
            except Exception as error:
                if cancellation_event.is_set():
                    raise RunCancelled() from None
                if host._owns_exception(error):
                    raise
                raise ExecutionFailed(INTERNAL_ERROR) from None
            finally:
                await host._close()
            if result.error is not None:
                return await self._fail(run_id, result.error)
            self._raise_if_cancelled(cancellation_event)
            try:
                return (await asyncio.to_thread(self._repository.complete_run, run_id,
                                               result.text, result.completion_reason)).run
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
        except (ModelGatewayError, ModelCapabilityProviderError) as error:
            return await self._fail(run_id, inference_error(error.failure))
        except ModelCapabilityNotFound:
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except ConversationStoreError:
            raise
        except TimeoutError:
            failure = deadline_failure()
            return await self._fail(run_id, failure.error, limit=failure.limit)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            if cancellation_event.is_set():
                return await self._cancel(run_id)
            return await self._fail(run_id, INTERNAL_ERROR)
        except Exception:
            return await self._fail(run_id, INTERNAL_ERROR)

    async def _resolve_capability(self, run, endpoint):
        if endpoint is not None and endpoint.protocol == "openai_chat_completions":
            for model in endpoint.models:
                if model.provider_id == run.provider_id and model.model_id == run.model_id:
                    return model
            raise ModelCapabilityNotFound
        return await self._capability_resolver.resolve(run.provider_id, run.model_id)

    async def _fail(self, run_id, error, *, limit=None):
        current = await asyncio.to_thread(self._repository.get_run, run_id)
        if current and current.status in {RunStatus.CANCELLING, RunStatus.CANCELLED}:
            return await self._cancel(run_id)
        return await asyncio.to_thread(self._repository.fail_run, run_id, error, limit=limit)

    async def _cancel(self, run_id):
        return await asyncio.to_thread(self._repository.mark_run_cancelled, run_id)

    @staticmethod
    def _raise_if_cancelled(event):
        if event.is_set():
            raise RunCancelled()

    @staticmethod
    async def _with_cancellation(iterator: AsyncIterator[_T], event) -> AsyncIterator[_T]:
        try:
            while True:
                next_event = asyncio.create_task(anext(iterator))
                cancelled = asyncio.create_task(event.wait())
                try:
                    done, _ = await asyncio.wait({next_event, cancelled}, return_when=asyncio.FIRST_COMPLETED)
                except BaseException:
                    next_event.cancel()
                    cancelled.cancel()
                    await asyncio.gather(next_event, cancelled, return_exceptions=True)
                    raise
                if cancelled in done and cancelled.result():
                    next_event.cancel()
                    with suppress(asyncio.CancelledError, StopAsyncIteration):
                        await next_event
                    raise RunCancelled()
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
    async def _await_with_cancellation(awaitable: Awaitable[_T], event) -> _T:
        operation = asyncio.ensure_future(awaitable)
        cancelled = asyncio.create_task(event.wait())
        try:
            done, _ = await asyncio.wait({operation, cancelled}, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            operation.cancel()
            cancelled.cancel()
            await asyncio.gather(operation, cancelled, return_exceptions=True)
            raise
        if cancelled in done and cancelled.result():
            operation.cancel()
            with suppress(asyncio.CancelledError):
                await operation
            raise RunCancelled()
        cancelled.cancel()
        with suppress(asyncio.CancelledError):
            await cancelled
        return operation.result()
