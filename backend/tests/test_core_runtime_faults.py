"""Transaction faults and cancellation races use the actual SQLite boundary."""
import asyncio
from uuid import uuid4

import pytest
from test_agent_loop import async_test, store
from test_agent_drivers import executor, input_request, completed, ScriptedGateway, one_step
from test_host_v5 import accept
from opensprite_backend.agent.events import limit_failure, INTERNAL_ERROR
from opensprite_backend.agent.plugin import RunResult, CompletionReason
from opensprite_backend.conversations.models import RunStatus, RunEventType, StoreFailure
from opensprite_backend.conversations.repository import ConversationStoreError


def terminals(repository, run):
    return [e for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
            if e.type in {RunEventType.RUN_FAILED, RunEventType.RUN_COMPLETED, RunEventType.RUN_CANCELLED}]


@pytest.mark.parametrize("limited", [False, True])
@async_test
async def test_cancel_committed_after_executor_read_wins_atomic_failure(tmp_path, monkeypatch, limited):
    repository = store(tmp_path)
    run = accept(repository)
    async def loop(host):
        if not limited:
            raise RuntimeError("private failure")
        snapshot = await host.read_context()
        await host.infer(input_request(host, snapshot, channel="draft"))
        await host.infer(input_request(host, snapshot))
    original = repository.fail_run
    def cancellation_race(run_id, error, **kwargs):
        repository.request_cancel(run_id)
        return original(run_id, error, **kwargs)
    monkeypatch.setattr(repository, "fail_run", cancellation_race)
    runtime, _ = executor(repository, ScriptedGateway([completed()]), loop, max_model_requests=1)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.CANCELLED and result.error is None
    assert [e.type for e in terminals(repository, run)] == [RunEventType.RUN_CANCELLED]
    assert terminals(repository, run)[0].data == {}


@async_test
async def test_error_after_completed_transaction_does_not_add_another_terminal(tmp_path, monkeypatch):
    repository = store(tmp_path)
    marker = str(uuid4())
    run = accept(repository)
    original = repository.complete_run
    def committed_then_failed(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("post-commit notification failure")
    monkeypatch.setattr(repository, "complete_run", committed_then_failed)
    gateway = ScriptedGateway([completed(marker)])
    runtime, _ = executor(repository, gateway, one_step)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED and result.partial_text == marker
    assert [e.type for e in terminals(repository, run)] == [RunEventType.RUN_COMPLETED]
    assert len(gateway.requests) == 1
    assert len(repository.list_messages(run.conversation_id, limit=100, before_sequence=None).items) == 2


@pytest.mark.parametrize("kind", ["duration_seconds", "model_requests", "summary_requests", "generated_chars", "host_operations"])
@async_test
async def test_plugin_cannot_forge_a_core_limit(tmp_path, kind):
    repository = store(tmp_path)
    run = accept(repository)
    async def loop(host):
        raise limit_failure(kind, 1, 1)
    runtime, _ = executor(repository, ScriptedGateway([]), loop)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.error.code == "internal_error"
    assert "limit" not in terminals(repository, run)[0].data


@pytest.mark.parametrize("target", [RunEventType.RUN_FAILED, RunEventType.RUN_COMPLETED])
def test_terminal_event_failure_rolls_back_status_message_and_evidence(tmp_path, monkeypatch, target):
    repository = store(tmp_path)
    run = repository.mark_run_started(accept(repository).id)
    marker = str(uuid4())
    repository.append_assistant_delta(run.id, marker)
    before = repository.list_run_events(run.id, after_sequence=0, limit=100)
    original = repository._append_event
    def fail(connection, run_id, conversation_id, event_type, *args, **kwargs):
        if event_type is target:
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
        return original(connection, run_id, conversation_id, event_type, *args, **kwargs)
    monkeypatch.setattr(repository, "_append_event", fail)
    with pytest.raises(ConversationStoreError):
        if target is RunEventType.RUN_COMPLETED:
            repository.complete_run(run.id, marker)
        else:
            failure = limit_failure("model_requests", 7, 7)
            repository.fail_run(run.id, failure.error, limit=failure.limit)
    restored = store(tmp_path)
    assert restored.get_run(run.id).status is RunStatus.RUNNING
    assert restored.get_run(run.id).assistant_message_id is None
    assert restored.get_run(run.id).partial_text == marker
    assert restored.list_run_events(run.id, after_sequence=0, limit=100) == before
    assert len(restored.list_messages(run.conversation_id, limit=100, before_sequence=None).items) == 1


@async_test
async def test_cancel_cleanup_returns_an_already_committed_terminal(tmp_path):
    repository = store(tmp_path)
    run = repository.mark_run_started(accept(repository).id)
    repository.mark_run_cancelled(run.id)
    from opensprite_backend.agent.run_executor import RunExecutor
    runtime = RunExecutor(repository=repository, gateway=ScriptedGateway([]))
    assert (await runtime._cancel(run.id)).status is RunStatus.CANCELLED
    assert (await runtime._fail(run.id, INTERNAL_ERROR)).status is RunStatus.CANCELLED
    assert len(terminals(repository, run)) == 1
