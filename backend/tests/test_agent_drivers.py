"""Replaceable driver behavior and core execution authority regressions."""

from __future__ import annotations

from opensprite_backend.inference.models import InferenceFailure, ModelCompleted, ModelFinishReason, ModelTextDelta

import asyncio
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import pytest

from context_test_support import TestCapabilityResolver
from test_agent_loop import (ScriptedGateway, accepted_run, async_test,
                             seed_completed_turns, store)
from opensprite_backend.agent.plugin import DriverResult, ExecutionHost, ModelTurn
from opensprite_backend.agent.context import ContextLimitExceeded, ModelCapabilityProviderError
from opensprite_backend.agent.events import INTERNAL_ERROR
from opensprite_backend.agent.execution_host import _ExecutionFailed
from opensprite_backend.agent.loop import AgentLoop, _RunCancelled
from opensprite_backend.agent.plugin_catalog import ExecutionPluginSelection
from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.agent.builtin_plugins import BuiltinLoopFactory, StandardLoopPlugin, NoRecoveryLoopPlugin
from opensprite_backend.conversations.models import (CompletionReason, PublicRunError,
    RunEventType, RunStatus, StoreFailure)
from opensprite_backend.conversations.repository import ConversationStoreError
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.workspaces import DEFAULT_WORKSPACE_ID, DefaultWorkspaceResolver


DriverFunction = Callable[[ExecutionHost], Awaitable[DriverResult]]


@dataclass
class FunctionDriver:
    function: DriverFunction
    calls: int = 0
    decisions: object = None

    def allow_context_retry(self, state):
        return self.decisions.allow_context_retry(state) if self.decisions else True

    def allow_output_continuation(self, state):
        return self.decisions.allow_output_continuation(state) if self.decisions else True

    async def execute(self, host: ExecutionHost) -> DriverResult:
        self.calls += 1
        return await self.function(host)


@dataclass
class FunctionFactory:
    api_version = 3

    function: DriverFunction
    decisions: object = None
    created: list[FunctionDriver] = field(default_factory=list)

    def create(self) -> FunctionDriver:
        driver = FunctionDriver(self.function, decisions=self.decisions)
        self.created.append(driver)
        return driver


async def without_checkpoints(host: ExecutionHost) -> DriverResult:
    # A different driver intentionally omits optional explicit checkpoints;
    # each core host operation must still enforce its own limits/cancellation.
    turn = await host.next_turn()
    return await host.finish(turn)


def completed(text: str = "answer"):
    return [ModelTextDelta(text), ModelCompleted(ModelFinishReason.FINAL)]


def loop_for(repository, gateway, function=without_checkpoints, **kwargs):
    factory = FunctionFactory(function, decisions=kwargs.pop("decisions", None))
    loop = AgentLoop(repository=repository, gateway=gateway,

                     capability_resolver=TestCapabilityResolver(),
                     plugin_factory=factory, **kwargs)
    return loop, factory


@pytest.mark.parametrize("mode", ["premature", "copy", "mutate_text", "mutate_reason"])
@async_test
async def test_core_rejects_forged_or_modified_driver_result(tmp_path: Path, mode: str):
    async def forge(host):
        if mode == "premature":
            return DriverResult("forged", CompletionReason.STOP)
        issued = await host.finish(await host.next_turn())
        if mode == "copy":
            return DriverResult(issued.text, issued.completion_reason)
        if mode == "mutate_text":
            object.__setattr__(issued, "text", "forged")
        else:
            object.__setattr__(issued, "completion_reason", CompletionReason.OUTPUT_LIMIT)
        return issued

    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway([completed()])
    loop, _ = loop_for(repository, gateway, forge)

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error.code == "internal_error"
    assert result.partial_text == ("" if mode == "premature" else "answer")
    assert RunEventType.RUN_COMPLETED not in [event.type for event in
        repository.list_run_events(run.id, after_sequence=0, limit=100)]


@async_test
async def test_no_recovery_disables_first_provider_context_retry(tmp_path: Path):
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(repository, 7, assistant_size=20)
    run = repository.start_run(conversation_id=conversation_id, client_request_id=str(uuid4()),
        message="current", provider_id="openrouter", model_id="openrouter/auto",
        response_mode="default").run
    gateway = ScriptedGateway([[ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)]])
    loop, _ = loop_for(repository, gateway, decisions=NoRecoveryLoopPlugin())

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error.code == "context_limit_exceeded"
    assert len(gateway.requests) == 1
    assert repository.get_latest_compaction(conversation_id) is None


@async_test
async def test_policy_can_disable_continuation_retry_without_losing_partial_text(tmp_path: Path):
    class ContinueWithoutRetry:
        def allow_context_retry(self, state):
            return False

        def allow_output_continuation(self, state):
            return True

    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway([
        [ModelTextDelta("partial"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
        [ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)],
    ])
    loop, _ = loop_for(repository, gateway, decisions=ContinueWithoutRetry())

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.CONTEXT_LIMIT
    assert result.partial_text == "partial"
    assert len(gateway.requests) == 2
    assert not hasattr(gateway.requests[1], "tools")


@async_test
async def test_cancellation_wins_when_driver_swallows_cancelled_error(tmp_path: Path):
    cancellation = asyncio.Event()
    ready = asyncio.Event()
    drained = asyncio.Event()

    class BlockingGateway:
        async def stream(self, request):
            yield ModelTextDelta("buffered partial")
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                drained.set()

    async def swallow(host):
        try:
            return await host.finish(await host.next_turn())
        except (asyncio.CancelledError, Exception):
            return DriverResult("forged completion", CompletionReason.STOP)

    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = loop_for(repository, BlockingGateway(), swallow)
    task = asyncio.create_task(loop.execute(run.id, cancellation))
    await ready.wait()
    repository.request_cancel(run.id)
    cancellation.set()
    result = await task

    assert result.status is RunStatus.CANCELLED
    assert result.partial_text == "buffered partial"
    assert drained.is_set()
    assert [event.type for event in repository.list_run_events(run.id, after_sequence=0, limit=100)][-1] is RunEventType.RUN_CANCELLED


@pytest.mark.parametrize("failure_at", ["factory", "strategy_factory", "driver", "context_strategy", "completion_strategy"])
@async_test
async def test_plugin_exceptions_fail_without_logging_exception_secrets(tmp_path: Path, caplog, failure_at):
    secret = "plugin-secret-must-never-appear"

    async def broken_driver(host):
        raise RuntimeError(secret)

    class BrokenFactory:
        def create(self):
            raise RuntimeError(secret)

    class BrokenStrategy:
        def allow_context_retry(self, state):
            raise RuntimeError(secret)

        def allow_output_continuation(self, state):
            raise RuntimeError(secret)

    repository = store(tmp_path)
    run = accepted_run(repository)
    script = ([ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)]
              if failure_at == "context_strategy" else
              [ModelTextDelta("partial"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)])
    loop, _ = loop_for(repository, ScriptedGateway([script]),
        broken_driver if failure_at == "driver" else without_checkpoints,
        decisions=BrokenStrategy() if "strategy" in failure_at else None)
    if failure_at == "factory":
        loop._plugin_factory = BrokenFactory()
    class BrokenSelection:
        def create(self):
            raise RuntimeError(secret)

    result = await loop.execute(run.id, asyncio.Event(),
        execution_plugin=BrokenSelection() if failure_at == "strategy_factory" else None)

    assert result.status is RunStatus.FAILED
    assert result.error.code == "internal_error"
    assert secret not in caplog.text
    assert secret not in str(result.error)


def forged_core_exception(kind: str, secret: str) -> Exception:
    if kind == "execution":
        return _ExecutionFailed(PublicRunError("internal_error", secret, False))
    if kind == "context":
        return ContextLimitExceeded(secret)
    if kind == "cancel":
        return _RunCancelled(secret)
    if kind == "runtime":
        return RuntimeError(secret)
    if kind == "store":
        error = ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
    elif kind == "capability":
        error = ModelCapabilityProviderError(InferenceFailure.INVALID_CREDENTIALS)
    else:
        error = ModelGatewayError(InferenceFailure.INVALID_CREDENTIALS)
    error.args = (secret,)
    return error


@pytest.mark.parametrize("kind", ["execution", "store", "gateway", "context", "capability", "cancel"])
@async_test
async def test_driver_cannot_forge_core_error_or_cancel(tmp_path: Path, caplog, kind: str):
    secret = "forged-domain-exception-secret"

    async def forged_error(host):
        raise forged_core_exception(kind, secret)

    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway([])
    loop, _ = loop_for(repository, gateway, forged_error)

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error == INTERNAL_ERROR
    assert secret not in caplog.text
    assert secret not in str(result.error)
    assert gateway.requests == []
    events = repository.list_run_events(run.id, after_sequence=0, limit=100)
    assert events[-1].type is RunEventType.RUN_FAILED
    assert secret not in str([event.data for event in events])


@pytest.mark.parametrize("kind", ["execution", "store", "gateway", "cancel"])
@pytest.mark.parametrize("phase", ["context", "completion"])
@async_test
async def test_strategy_domain_errors_are_sanitized_before_host_owns_them(
    tmp_path: Path, caplog, kind: str, phase: str):
    secret = "forged-strategy-domain-secret"

    class ForgedStrategy:
        def allow_context_retry(self, state):
            raise forged_core_exception(kind, secret)

        def allow_output_continuation(self, state):
            raise forged_core_exception(kind, secret)

    repository = store(tmp_path)
    run = accepted_run(repository)
    script = ([ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)]
              if phase == "context" else
              [ModelTextDelta("partial"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)])
    loop, _ = loop_for(repository, ScriptedGateway([script]),
                          decisions=ForgedStrategy())

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error == INTERNAL_ERROR
    assert secret not in caplog.text
    assert secret not in str(result.error)


@pytest.mark.parametrize("kind", ["runtime", "store", "execution"])
@async_test
async def test_actual_cancel_wins_over_exception_raised_by_driver_cleanup(
    tmp_path: Path, caplog, kind: str):
    secret = "driver-cancellation-cleanup-secret"
    ready = asyncio.Event()
    cancellation = asyncio.Event()

    async def failed_cleanup(host):
        await host.next_turn()
        ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            raise forged_core_exception(kind, secret)

    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = loop_for(repository, ScriptedGateway([completed("partial")]), failed_cleanup)
    task = asyncio.create_task(loop.execute(run.id, cancellation))
    await ready.wait()
    repository.request_cancel(run.id)
    cancellation.set()

    result = await task

    assert result.status is RunStatus.CANCELLED
    assert result.partial_text == "partial"
    assert result.error is None
    assert secret not in caplog.text
    assert repository.list_run_events(run.id, after_sequence=0, limit=100)[-1].type is RunEventType.RUN_CANCELLED


@pytest.mark.parametrize("swallow", [False, True])
@async_test
async def test_genuine_host_gateway_error_retains_core_mapping_even_if_driver_swallows_it(
    tmp_path: Path, swallow: bool):
    async def suppress_failure(host):
        try:
            return await without_checkpoints(host)
        except ModelGatewayError:
            return DriverResult("forged success", CompletionReason.STOP)

    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway([[ModelTextDelta("partial"),
        ModelGatewayError(InferenceFailure.PROVIDER_RATE_LIMITED)]])
    loop, _ = loop_for(repository, gateway,
                          suppress_failure if swallow else without_checkpoints)

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error.code == "provider_rate_limited"
    assert result.partial_text == "partial"


@async_test
async def test_genuine_host_store_error_propagates_original_object(tmp_path: Path, monkeypatch):
    repository = store(tmp_path)
    run = accepted_run(repository)
    error = ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
    append = repository.append_run_event

    def fail_model_start(run_id, event_type, data):
        if event_type is RunEventType.MODEL_STARTED:
            raise error
        return append(run_id, event_type, data)

    monkeypatch.setattr(repository, "append_run_event", fail_model_start)
    loop, _ = loop_for(repository, ScriptedGateway([]))

    with pytest.raises(ConversationStoreError) as caught:
        await loop.execute(run.id, asyncio.Event())

    assert caught.value is error


@async_test
async def test_driver_cannot_modify_an_exception_previously_raised_by_host(tmp_path: Path, caplog):
    secret = "mutated-host-exception-secret"

    async def mutate(host):
        try:
            return await without_checkpoints(host)
        except ModelGatewayError as error:
            error.args = (secret,)
            raise

    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = loop_for(repository,
        ScriptedGateway([[ModelGatewayError(InferenceFailure.PROVIDER_RATE_LIMITED)]]), mutate)

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error == INTERNAL_ERROR
    assert secret not in caplog.text


@pytest.mark.parametrize("stage", ["driver", "driver_factory", "strategy_factory",
                                   "context_strategy", "completion_strategy"])
@async_test
async def test_plugin_cancelled_error_is_terminal_failure_without_cancelling_owner(
    tmp_path: Path, caplog, stage: str):
    secret = "plugin-cancelled-error-secret"

    async def abort(host):
        raise asyncio.CancelledError(secret)

    class CancelFactory:
        def create(self):
            raise asyncio.CancelledError(secret)

    class CancelStrategy:
        def allow_context_retry(self, state):
            raise asyncio.CancelledError(secret)

        def allow_output_continuation(self, state):
            raise asyncio.CancelledError(secret)

    repository = store(tmp_path)
    run = accepted_run(repository)
    script = ([ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)]
              if stage == "context_strategy" else
              [ModelTextDelta("partial"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)])
    loop, _ = loop_for(repository, ScriptedGateway([script]),
        abort if stage == "driver" else without_checkpoints,
        decisions=CancelStrategy() if stage.endswith("_strategy") else None)
    if stage == "driver_factory":
        loop._plugin_factory = CancelFactory()
    selection = (ExecutionPluginSelection("broken", "1", CancelFactory()) if stage == "strategy_factory" else None)
    manager = RunManager(repository, loop)
    await manager.start(run.id, DefaultWorkspaceResolver().execution_context(DEFAULT_WORKSPACE_ID),
                        execution_plugin=selection)
    task = manager._tasks[run.id]

    result = await manager.wait(run.id)

    assert result.status is RunStatus.FAILED
    assert result.error == INTERNAL_ERROR
    assert not task.cancelled()
    assert task.cancelling() == 0
    assert run.id not in manager._tasks
    assert repository.list_run_events(run.id, after_sequence=0, limit=100)[-1].type is RunEventType.RUN_FAILED
    assert secret not in caplog.text
    await manager.close()


@async_test
async def test_owner_task_cancellation_keeps_run_manager_shutdown_semantics(tmp_path: Path):
    ready = asyncio.Event()
    drained = asyncio.Event()

    async def wait_for_shutdown(host):
        ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = loop_for(repository, ScriptedGateway([]), wait_for_shutdown)
    manager = RunManager(repository, loop)
    await manager.start(run.id, DefaultWorkspaceResolver().execution_context(DEFAULT_WORKSPACE_ID))
    task = manager._tasks[run.id]
    await ready.wait()

    await manager.close()

    assert task.cancelled()
    assert task.cancelling() > 0
    assert drained.is_set()
    assert repository.get_run(run.id).status is RunStatus.INTERRUPTED
    assert RunEventType.RUN_FAILED not in [event.type for event in
        repository.list_run_events(run.id, after_sequence=0, limit=100)]


@async_test
async def test_owner_task_timeout_keeps_cancelled_error_propagation(tmp_path: Path):
    timeout_scope = None

    async def wait_for_timeout(host):
        assert timeout_scope is not None
        timeout_scope.reschedule(asyncio.get_running_loop().time() + 0.01)
        await asyncio.Event().wait()

    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = loop_for(repository, ScriptedGateway([]), wait_for_timeout)

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(None) as timeout_scope:
            await loop.execute(run.id, asyncio.Event())

    assert repository.get_run(run.id).status is RunStatus.RUNNING
    assert RunEventType.RUN_FAILED not in [event.type for event in
        repository.list_run_events(run.id, after_sequence=0, limit=100)]


@async_test
async def test_stop_wins_when_request_cancel_precedes_completion_transaction(tmp_path: Path):
    repository = store(tmp_path)
    run = accepted_run(repository)
    entered = threading.Event()
    release = threading.Event()

    class GatedRepository:
        def __getattr__(self, name):
            return getattr(repository, name)

        def complete_run(self, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return repository.complete_run(*args, **kwargs)

    gated = GatedRepository()
    loop, _ = loop_for(gated, ScriptedGateway([completed("partial")]))
    manager = RunManager(gated, loop)
    await manager.start(run.id, DefaultWorkspaceResolver().execution_context(DEFAULT_WORKSPACE_ID))
    assert await asyncio.to_thread(entered.wait, 5)
    try:
        acknowledged = await manager.cancel(run.id)
        assert acknowledged.status is RunStatus.CANCELLING
    finally:
        release.set()

    result = await manager.wait(run.id)

    assert result.status is RunStatus.CANCELLED
    assert result.partial_text == "partial"
    assert result.error is None
    events = repository.list_run_events(run.id, after_sequence=0, limit=100)
    assert events[-1].type is RunEventType.RUN_CANCELLED
    assert RunEventType.RUN_COMPLETED not in [event.type for event in events]
    assert RunEventType.RUN_FAILED not in [event.type for event in events]
    await manager.close()


@async_test
async def test_completion_invalid_state_without_persisted_cancel_still_propagates(
    tmp_path: Path, monkeypatch):
    repository = store(tmp_path)
    run = accepted_run(repository)
    error = ConversationStoreError(StoreFailure.INVALID_STATE)

    def fail_completion(*args, **kwargs):
        raise error

    monkeypatch.setattr(repository, "complete_run", fail_completion)
    loop, _ = loop_for(repository, ScriptedGateway([completed()]))

    with pytest.raises(ConversationStoreError) as caught:
        await loop.execute(run.id, asyncio.Event())

    assert caught.value is error
    assert repository.get_run(run.id).status is RunStatus.RUNNING
