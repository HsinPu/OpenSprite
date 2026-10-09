"""Real Host/SQLite limit evidence; protocol fixtures never claim model quality."""
import asyncio
from uuid import uuid4

import pytest
from test_agent_loop import async_test, store, seed_completed_turns
from test_agent_drivers import executor, input_request, completed, ScriptedGateway
from test_host_v5 import accept
from opensprite_backend.agent.plugin import (
    ContextReadRequest, FinalOutput, InputSource, ModelMessage, StepRequest,
    SummarySource, SummaryWriteRequest,
)
from opensprite_backend.agent.execution_errors import ExecutionFailed
from opensprite_backend.conversations.models import RunEventType, RunStatus, PublicRunError
from opensprite_backend.conversations.run_limits import RunLimitEvidence
from opensprite_backend.conversations.repository import ConversationStoreError


def failure_event(repository, run):
    terminals = [e for e in repository.list_run_events(run.id, after_sequence=0, limit=1000)
                 if e.type in {RunEventType.RUN_FAILED, RunEventType.RUN_CANCELLED, RunEventType.RUN_COMPLETED}]
    assert len(terminals) == 1
    return terminals[0]


@pytest.mark.parametrize("kind", ["model_requests", "generated_chars", "host_operations", "duration_seconds"])
@async_test
async def test_limit_evidence_counts_accepted_usage_and_survives_reload(tmp_path, kind):
    nonce = str(uuid4())
    repository = store(tmp_path)
    run = accept(repository, message=nonce)
    gateway = ScriptedGateway([completed(nonce), completed(nonce)])
    async def loop(host):
        context = await host.read_context()
        if kind == "host_operations":
            for _ in range(2048):
                await host.estimate_input((ModelMessage("user", nonce),))
        if kind == "duration_seconds":
            await asyncio.Event().wait()
        step = await host.infer(input_request(host, context, channel="draft"))
        step = await host.infer(input_request(host, context))
        return await host.finish(FinalOutput(step.text, (step,)))
    bounds = {"model_requests": {"max_model_requests": 1}, "generated_chars": {"max_assistant_chars": len(nonce)-1},
              "host_operations": {}, "duration_seconds": {"max_duration_seconds": .5}}[kind]
    runtime, _ = executor(repository, gateway, loop, **bounds)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.FAILED
    data = failure_event(store(tmp_path), run).data
    assert data["error"]["code"] == result.error.code
    assert data["limit"]["kind"] == kind
    if kind == "model_requests":
        assert data["limit"] == {"kind": kind, "maximum": 1, "used": 1}
        assert len(gateway.requests) == 1
    elif kind == "generated_chars":
        assert data["limit"] == {"kind": kind, "maximum": len(nonce)-1, "used": 0}
        assert len(gateway.requests) == 1 and repository.list_run_steps(run.id)[0].text == ""
    elif kind == "host_operations":
        assert data["limit"] == {"kind": kind, "maximum": 2048, "used": 2048}
        assert not gateway.requests
    else:
        assert data["limit"]["maximum"] == .5 and data["limit"]["used"] >= .5
        assert not gateway.requests


@async_test
async def test_summary_budget_is_shared_and_rejected_request_is_not_sent(tmp_path):
    repository = store(tmp_path)
    run = accept(repository, conversation=seed_completed_turns(repository, 3, assistant_size=20))
    gateway = ScriptedGateway([completed(str(uuid4())), completed("must not be called")])
    async def loop(host):
        for _ in range(2):
            snapshot = await host.read_context(ContextReadRequest(after_sequence=0))
            after = snapshot.summary.covers_through_sequence if snapshot.summary else 0
            selected = tuple(m for m in snapshot.history if m.sequence > after)[:2]
            ids = tuple(m.id for m in selected)
            step = await host.infer(StepRequest(
                (ModelMessage("system", host.run.system_prompt), ModelMessage("user", "\n".join(m.content for m in selected))),
                100, sources=(InputSource(1, snapshot, ids),), purpose="compaction", channel="draft",
                summary_source=SummarySource((snapshot,), ids, previous_summary_id=snapshot.summary.id if snapshot.summary else None)))
            await host.save_summary(SummaryWriteRequest(step, step.text))
    runtime, _ = executor(repository, gateway, loop, max_compactions_per_run=1)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.error.code == "summary_request_limit_reached"
    assert failure_event(repository, run).data["limit"] == {"kind": "summary_requests", "maximum": 1, "used": 1}
    assert len(gateway.requests) == len(repository.list_run_steps(run.id)) == 1


@pytest.mark.parametrize("again", [False, True])
@async_test
async def test_mutated_host_limit_cannot_be_resealed(tmp_path, again):
    repository = store(tmp_path)
    run = accept(repository)
    async def loop(host):
        context = await host.read_context()
        await host.infer(input_request(host, context, channel="draft"))
        try:
            await host.infer(input_request(host, context))
        except ExecutionFailed as error:
            error.limit = RunLimitEvidence("duration_seconds", 10, 10)
            if again:
                await host.checkpoint()
            raise
    runtime, _ = executor(repository, ScriptedGateway([completed()]), loop, max_model_requests=1)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.error.code == "internal_error"
    assert "limit" not in failure_event(repository, run).data


def test_legacy_limit_history_does_not_invent_evidence(tmp_path):
    repository = store(tmp_path)
    run = accept(repository)
    repository.fail_run(run.id, PublicRunError("agent_limit_reached", "Legacy limit", False))
    assert failure_event(store(tmp_path), run).data == {"error": {"code": "agent_limit_reached", "message": "Legacy limit", "retryable": False}}


def test_limit_metadata_must_match_the_error_before_any_write(tmp_path):
    repository = store(tmp_path)
    run = accept(repository)
    with pytest.raises(ConversationStoreError):
        repository.fail_run(run.id, PublicRunError("model_request_limit_reached", "Limit", False),
                            limit=RunLimitEvidence("duration_seconds", 10, 10))
    assert repository.get_run(run.id).status is RunStatus.QUEUED
    assert not repository.list_run_events(run.id, after_sequence=0, limit=100)
