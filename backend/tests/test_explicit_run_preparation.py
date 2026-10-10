"""Core lifetime controls also cover externally composed preparation."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import PropertyMock, patch

from test_agent_loop import async_test, store, ScriptedGateway
from opensprite_backend.agent.execution_input import ExecutionPluginSelection, PreparedRun
from opensprite_backend.agent.plugin import ModelLimits
from opensprite_backend.agent.run_executor import RunExecutor
from opensprite_backend.agent.run_control import RunControl
from opensprite_backend.conversations.models import RunStatus, RunEventType
from opensprite_backend.response_modes import ReasoningResolution


def accept(repository):
    return repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=str(uuid4()),
        provider_id="openrouter", model_id="fixture/model", response_mode="default").run


@async_test
async def test_cancellation_interrupts_product_preparation_without_inference(tmp_path):
    repository, entered = store(tmp_path), asyncio.Event()
    run, cancellation = accept(repository), asyncio.Event()
    gateway = ScriptedGateway([])
    class Preparation:
        async def prepare(self, snapshot):
            entered.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(RunExecutor(repository=repository, gateway=gateway).execute(
        run.id, cancellation, preparation=Preparation()))
    await asyncio.wait_for(entered.wait(), timeout=2)
    cancellation.set()
    result = await asyncio.wait_for(task, timeout=2)
    assert result.status is RunStatus.CANCELLED
    assert gateway.requests == []
    assert sum(e.type is RunEventType.RUN_CANCELLED for e in repository.list_run_events(run.id, after_sequence=0, limit=100)) == 1


@async_test
async def test_deadline_is_not_restarted_between_preparation_and_loop(tmp_path):
    repository, gateway = store(tmp_path), ScriptedGateway([])
    run = accept(repository)
    class Loop:
        async def execute(self, host):
            await asyncio.sleep(.3)
            await host.checkpoint()
            raise AssertionError("deadline must include preparation")
    class Preparation:
        async def prepare(self, snapshot):
            await asyncio.sleep(.3)
            return PreparedRun(snapshot.id, "neutral base prefix", ModelLimits(32000, 4096),
                ExecutionPluginSelection("test", "1.0", SimpleNamespace(api_version=5, create=Loop)),
                ReasoningResolution(snapshot.response_mode, None, "provider_default"))
    result = await RunExecutor(repository=repository, gateway=gateway, max_duration_seconds=.5).execute(
        run.id, asyncio.Event(), preparation=Preparation())
    assert result.status is RunStatus.FAILED and result.error.code == "run_deadline_exceeded"
    assert gateway.requests == []
    terminal = [e for e in repository.list_run_events(run.id, after_sequence=0, limit=100) if e.type is RunEventType.RUN_FAILED]
    assert len(terminal) == 1 and terminal[0].data['limit']['kind'] == 'duration_seconds'


@async_test
async def test_prepared_inputs_for_another_run_are_rejected_before_model_use(tmp_path):
    repository, gateway = store(tmp_path), ScriptedGateway([])
    run = accept(repository)
    class Preparation:
        async def prepare(self, snapshot):
            return PreparedRun(str(uuid4()), "neutral prefix", ModelLimits(32000, 4096),
                ExecutionPluginSelection("test", "1.0", None),
                ReasoningResolution(snapshot.response_mode, None, "provider_default"))
    result = await RunExecutor(repository=repository, gateway=gateway).execute(
        run.id, asyncio.Event(), preparation=Preparation())
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    assert gateway.requests == []


@async_test
async def test_owned_timeout_keeps_specific_error_when_timer_precedes_clock_check(tmp_path):
    repository, gateway = store(tmp_path), ScriptedGateway([])
    run = accept(repository)
    class Loop:
        async def execute(self, host):
            await asyncio.Event().wait()
    class Preparation:
        async def prepare(self, snapshot):
            return PreparedRun(snapshot.id, 'neutral prefix', ModelLimits(32000, 4096),
                ExecutionPluginSelection('test', '1.0', SimpleNamespace(api_version=5, create=Loop)),
                ReasoningResolution(snapshot.response_mode, None, 'provider_default'))
    # Deterministic timer/clock disagreement; the issued error's identity, not
    # an arbitrary plugin exception with the same code, establishes ownership.
    with patch.object(RunControl, 'expired', new_callable=PropertyMock, return_value=False):
        result = await RunExecutor(repository=repository, gateway=gateway, max_duration_seconds=.1).execute(
            run.id, asyncio.Event(), preparation=Preparation())
    assert result.status is RunStatus.FAILED and result.error.code == 'run_deadline_exceeded'
    assert gateway.requests == []
