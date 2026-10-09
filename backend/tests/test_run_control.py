"""Shared enforcement, real deadlines and explicit Host composition."""
import asyncio
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_agent_loop import async_test, store
from test_agent_drivers import input_request, completed, ScriptedGateway
from test_host_v5 import accept, make_executor
from opensprite_backend.agent.execution_errors import ExecutionFailed, RunCancelled
from opensprite_backend.agent.execution_host import LoopExecutionHost
from opensprite_backend.agent.plugin import ExecutionLimits, ModelLimits, FinalOutput
from opensprite_backend.agent.request_trace import TracedGateway
from opensprite_backend.agent.run_control import RunControl
from opensprite_backend.agent.run_executor import RunExecutor
from opensprite_backend.conversations.models import RunStatus, RunEventType
from context_test_support import TestCapabilityResolver


@async_test
async def test_host_runs_without_executor_or_private_dependency_access(tmp_path):
    repository = store(tmp_path)
    run = repository.mark_run_started(accept(repository).id)
    marker = str(uuid4())
    gateway = ScriptedGateway([completed(marker)])
    control = RunControl(asyncio.Event(), ExecutionLimits())
    host = LoopExecutionHost(repository=repository, gateway=TracedGateway(gateway, repository),
        control=control, run=run, system_prompt="fixed system", model_limits=ModelLimits(128000, 8192),
        selection=SimpleNamespace(plugin_id="test", plugin_version="1.0.0"), provider_endpoint=None)
    context = await host.read_context()
    step = await host.infer(input_request(host, context))
    result = await host.finish(FinalOutput(step.text, (step,)))
    await host._validate_result(result)
    await host._close()
    repository.complete_run(run.id, result.text, result.completion_reason)
    assert repository.get_run(run.id).partial_text == marker
    assert not hasattr(host, "_executor")


@async_test
async def test_all_awaits_use_original_deadline_and_close_blocked_task():
    control = RunControl(asyncio.Event(), ExecutionLimits(max_duration_seconds=.1))
    started = monotonic()
    closed = asyncio.Event()
    await control.wait(asyncio.sleep(.04))
    control.consume_request(summary=True)
    control.consume_text(1)
    async def blocked():
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()
    with pytest.raises(ExecutionFailed) as caught:
        await control.wait(blocked())
    assert caught.value.error.code == "run_deadline_exceeded"
    assert caught.value.limit.maximum == .1 and caught.value.limit.used >= .1
    assert monotonic() - started < 1 and closed.is_set()


def test_counters_are_shared_within_one_run_and_fresh_for_the_next():
    limits = ExecutionLimits(max_model_requests=2, max_compactions=1, max_text_chars=5)
    first = RunControl(asyncio.Event(), limits)
    first.consume_request(summary=True)
    first.consume_request()
    with pytest.raises(ExecutionFailed) as failure:
        first.consume_request()
    assert failure.value.limit.used == 2
    with pytest.raises(ExecutionFailed):
        first.consume_text(6)
    first.consume_text(5)
    second = RunControl(asyncio.Event(), limits)
    second.consume_request(summary=True)
    second.consume_text(5)


@pytest.mark.parametrize("stage", ["prompt", "capability", "loop"])
@async_test
async def test_raw_timeout_is_not_misreported_as_core_deadline(tmp_path, stage):
    repository = store(tmp_path)
    gateway = ScriptedGateway([])
    async def fake_timeout(**kwargs):
        raise TimeoutError("private timeout message")
    class Capability:
        async def resolve(self, *_):
            raise TimeoutError("private timeout message")
    async def plugin(host):
        raise TimeoutError("private timeout message")
    runtime = RunExecutor(repository=repository, gateway=gateway,
        capability_resolver=Capability() if stage == "capability" else TestCapabilityResolver(),
        system_prompt_provider=SimpleNamespace(build=fake_timeout) if stage == "prompt" else None,
        plugin_factory=SimpleNamespace(api_version=5, create=lambda: SimpleNamespace(execute=plugin)) if stage == "loop" else None)
    run = accept(repository)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    failed = next(e for e in repository.list_run_events(run.id, after_sequence=0, limit=100) if e.type is RunEventType.RUN_FAILED)
    assert "limit" not in failed.data and "private" not in str(failed.data)


@async_test
async def test_factory_time_is_charged_to_run_deadline(tmp_path):
    repository = store(tmp_path)
    gateway = ScriptedGateway([])
    async def execute(host):
        await asyncio.sleep(0)
    def create():
        sleep(.04)
        return SimpleNamespace(execute=execute)
    runtime = RunExecutor(repository=repository, gateway=gateway, capability_resolver=TestCapabilityResolver(),
        plugin_factory=SimpleNamespace(api_version=5, create=create), max_duration_seconds=.02)
    result = await runtime.execute(accept(repository).id, asyncio.Event())
    assert result.error.code == "run_deadline_exceeded" and not gateway.requests


@async_test
async def test_cancel_wins_when_deadline_has_also_expired():
    cancellation = asyncio.Event()
    control = RunControl(cancellation, ExecutionLimits(max_duration_seconds=.01))
    await asyncio.sleep(.02)
    cancellation.set()
    with pytest.raises(RunCancelled):
        await control.wait(asyncio.sleep(0))
