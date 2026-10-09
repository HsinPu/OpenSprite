"""API v5 flows exercise real SQLite, streaming, cancellation and Host bounds."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from context_test_support import TestCapabilityResolver
from test_agent_loop import ScriptedGateway, accepted_run, async_test, seed_completed_turns, store
from opensprite_backend.agent.plugin import ContextReadRequest, InputSource, SummarySource, SummaryWriteRequest, StepRequest, FinalOutput, RunResult
from opensprite_backend.agent.run_executor import RunExecutor
from opensprite_backend.agent.execution_errors import ExecutionFailed, RunCancelled
from opensprite_backend.agent.events import INTERNAL_ERROR
from opensprite_backend.conversations.models import CompletionReason, RunEventType, RunStatus
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import InferenceFailure, ModelCompleted, ModelFinishReason, ModelTextDelta, ModelMessage, ModelUsage
from opensprite_standard_loop import LoopFactory


def completed(text="answer"):
    return [ModelTextDelta(text), ModelUsage(31, 7), ModelCompleted(ModelFinishReason.FINAL)]


def executor(repository, gateway, function, **bounds):
    instances = []
    class Plugin:
        async def execute(self, host):
            return await function(host)
    def create():
        instance = Plugin()
        instances.append(instance)
        return instance
    factory = SimpleNamespace(api_version=5, create=create)
    return RunExecutor(repository=repository, gateway=gateway,
        capability_resolver=TestCapabilityResolver(), plugin_factory=factory, **bounds), instances


def input_request(host, snapshot, *, instruction="", messages=(), max_output_tokens=1000, **options):
    raw = (*snapshot.history, snapshot.current_user)
    base = (ModelMessage("system", host.run.system_prompt + ("\n\n" + instruction if instruction else "")),
            *(ModelMessage(item.role, item.content) for item in raw), *messages)
    sources = tuple(InputSource(index+1, snapshot, (item.id,)) for index, item in enumerate(raw))
    return StepRequest(base, min(max_output_tokens, host.run.model_limits.output_tokens), sources=sources, **options)


async def one_step(host):
    step = await host.infer(input_request(host, await host.read_context()))
    return await host.finish(FinalOutput(step.text, (step,), error_step=step if step.error else None))


@pytest.mark.parametrize("mode", ["premature", "copy", "mutate_text", "mutate_reason"])
@async_test
async def test_core_rejects_forged_or_modified_result(tmp_path, mode):
    async def forge(host):
        if mode == "premature":
            return RunResult("forged", CompletionReason.STOP)
        result = await one_step(host)
        if mode == "copy":
            return replace(result)
        object.__setattr__(result, "text" if mode == "mutate_text" else "completion_reason",
            "forged" if mode == "mutate_text" else CompletionReason.OUTPUT_LIMIT)
        return result
    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = executor(repository, ScriptedGateway([completed()]), forge)
    result = await loop.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    assert not any(e.type is RunEventType.RUN_COMPLETED for e in repository.list_run_events(run.id, after_sequence=0, limit=100))


@async_test
async def test_three_step_revision_loop_keeps_drafts_out_of_chat(tmp_path):
    nonce = str(uuid4())
    async def review(host):
        context = await host.read_context()
        draft = await host.infer(input_request(host, context, label="draft", channel="draft", instruction="Draft a response"))
        critique = await host.infer(input_request(host, context, label="review", channel="draft",
            messages=(ModelMessage("assistant", draft.text), ModelMessage("user", "Check the draft"))))
        final = await host.infer(input_request(host, context, label="final", channel="answer",
            messages=(ModelMessage("assistant", draft.text), ModelMessage("user", critique.text))))
        return await host.finish(FinalOutput(final.text, (final,)))
    repository = store(tmp_path)
    gateway = ScriptedGateway([completed("draft:"+nonce), completed("critique:"+nonce), completed("final:"+nonce)])
    loop, instances = executor(repository, gateway, review)
    run = accepted_run(repository)
    result = await loop.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED and result.partial_text == "final:"+nonce
    steps = repository.list_run_steps(run.id, after_sequence=0, limit=100)
    assert [s.label for s in steps] == ["draft", "review", "final"]
    assert [s.text for s in steps] == ["draft:"+nonce, "critique:"+nonce, "final:"+nonce]
    assert all(s.status == "completed" and s.input_tokens == 31 for s in steps)
    assert "critique:"+nonce in gateway.requests[2].messages[-1].content
    assert [m.content for m in repository.list_messages(run.conversation_id, limit=100, before_sequence=None).items] == ["整理今天的工作", "final:"+nonce]
    second = accepted_run(repository)
    gateway.scripts.extend([completed("D"), completed("R"), completed("F")])
    await loop.execute(second.id, asyncio.Event())
    assert len(instances) == 2 and instances[0] is not instances[1]


@pytest.mark.parametrize("failure", [InferenceFailure.PROVIDER_RATE_LIMITED, InferenceFailure.PROVIDER_TIMEOUT, InferenceFailure.PROVIDER_UNREACHABLE])
@async_test
async def test_loop_can_retry_recoverable_error_with_attempt_lineage(tmp_path, failure):
    async def retry(host):
        context = await host.read_context()
        failed = await host.infer(input_request(host, context, channel="draft"))
        assert failed.error.retryable
        step = await host.infer(input_request(host, context, retry_of=failed))
        return await host.finish(FinalOutput(step.text, (step,)))
    repository = store(tmp_path)
    gateway = ScriptedGateway([[ModelGatewayError(failure)], completed(str(uuid4()))])
    loop, _ = executor(repository, gateway, retry)
    run = accepted_run(repository)
    result = await loop.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED
    steps = repository.list_run_steps(run.id, after_sequence=0, limit=100)
    assert steps[1].retry_of == steps[0].id
    attempts = [e.data for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
        if e.type is RunEventType.MODEL_ATTEMPT and e.data["status"] == "started"]
    assert attempts[1]["retryOfAttemptId"] == attempts[0]["attemptId"]
    assert attempts[1]["retryCause"] == steps[0].error_code


@async_test
async def test_loop_selects_compaction_range_instruction_and_format(tmp_path):
    async def summarize(host):
        context = await host.read_context(ContextReadRequest(after_sequence=0, limit=2, summary_format="custom.summary.v1"))
        identifiers = tuple(item.id for item in context.history)
        step = await host.infer(StepRequest(
            (ModelMessage("system", host.run.system_prompt + "\nKeep exactly the identifiers"),
             ModelMessage("user", "\n".join(item.content for item in context.history))), 100,
            sources=(InputSource(1, context, identifiers),), channel="draft", purpose="compaction",
            summary_source=SummarySource((context,), identifiers, summary_format="custom.summary.v1")))
        result = await host.save_summary(SummaryWriteRequest(step, step.text))
        assert result.producer_plugin_id == "standard"
        updated = await host.read_context(ContextReadRequest(limit=1, summary_format="custom.summary.v1"))
        assert updated.summary.id == result.id
        step = await host.infer(input_request(host, updated))
        return await host.finish(FinalOutput(step.text, (step,)))
    repository = store(tmp_path)
    conversation = seed_completed_turns(repository, 4, assistant_size=20)
    run = repository.start_run(conversation_id=conversation, client_request_id=str(uuid4()), message="current",
        provider_id="openrouter", model_id="openrouter/auto", response_mode="default").run
    gateway = ScriptedGateway([completed("identifiers"), completed("done")])
    loop, _ = executor(repository, gateway, summarize)
    result = await loop.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED
    assert "Keep exactly the identifiers" in gateway.requests[0].messages[0].content
    assert gateway.requests[0].max_output_tokens == 100
    assert not hasattr(gateway.requests[0], "tools")
    summary = repository.get_latest_compaction(conversation, summary_format="custom.summary.v1")
    assert summary.covers_through_sequence == 2 and summary.producer_plugin_version == "testing"
    assert repository.get_latest_compaction(conversation) is None


@pytest.mark.parametrize("kind", ["context", "step", "exception", "cancel", "self_cancel", "after_finish"])
@async_test
async def test_invalid_plugin_behavior_is_sanitized(tmp_path, kind, caplog):
    async def bad(host):
        if kind == "exception": raise RuntimeError("private-secret-marker")
        if kind == "cancel": raise RunCancelled()
        if kind == "self_cancel": raise asyncio.CancelledError("private-secret-marker")
        context = await host.read_context()
        if kind == "context":
            object.__setattr__(context, "id", str(uuid4()))
            await host.infer(input_request(host, context))
        step = await host.infer(input_request(host, context))
        if kind == "step":
            object.__setattr__(step, "error", INTERNAL_ERROR)
            return await host.finish(FinalOutput(error_step=step))
        if kind == "after_finish":
            result = await host.finish(FinalOutput(step.text, (step,)))
            try: await host.read_context()
            except Exception: pass
            return result
    repository = store(tmp_path)
    loop, _ = executor(repository, ScriptedGateway([completed()]), bad)
    result = await loop.execute(accepted_run(repository).id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    assert "private-secret-marker" not in caplog.text


@async_test
async def test_fatal_host_error_cannot_be_swallowed(tmp_path):
    async def swallow(host):
        try: await host.infer(input_request(host, await host.read_context()))
        except ExecutionFailed: pass
        return RunResult("fake", CompletionReason.STOP)
    repository = store(tmp_path)
    gateway = ScriptedGateway([[ModelGatewayError(InferenceFailure.INVALID_CREDENTIALS)]])
    loop, _ = executor(repository, gateway, swallow)
    result = await loop.execute(accepted_run(repository).id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "invalid_credentials"
    assert len(gateway.requests) == 1


@async_test
async def test_cancellation_during_private_draft_preserves_step_and_one_terminal(tmp_path):
    repository = store(tmp_path)
    started, cancellation = asyncio.Event(), asyncio.Event()
    class Gateway:
        async def stream(self, request):
            yield ModelTextDelta("private draft")
            started.set()
            await asyncio.Event().wait()
    async def swallow(host):
        try: await host.infer(input_request(host, await host.read_context(), channel="draft"))
        except BaseException: pass
        return RunResult("fake", CompletionReason.STOP)
    loop, _ = executor(repository, Gateway(), swallow)
    run = accepted_run(repository)
    task = asyncio.create_task(loop.execute(run.id, cancellation))
    await asyncio.wait_for(started.wait(), 5)
    repository.request_cancel(run.id)
    cancellation.set()
    result = await asyncio.wait_for(task, 5)
    assert result.status is RunStatus.CANCELLED and result.partial_text == ""
    step = repository.list_run_steps(run.id, after_sequence=0, limit=100)[0]
    assert step.status == "cancelled" and step.text == "private draft"
    terminals = [e.type for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
        if e.type in {RunEventType.RUN_CANCELLED, RunEventType.RUN_FAILED, RunEventType.RUN_COMPLETED}]
    assert terminals == [RunEventType.RUN_CANCELLED]


@pytest.mark.parametrize("bound", ["requests", "duration", "text"])
@async_test
async def test_host_hard_limits_stop_custom_loops(tmp_path, bound):
    async def excess(host):
        context = await host.read_context()
        if bound == "duration": await asyncio.sleep(.1)
        step = await host.infer(input_request(host, context, channel="draft"))
        step = await host.infer(input_request(host, context))
        return await host.finish(FinalOutput(step.text, (step,)))
    repository = store(tmp_path)
    bounds = {"max_model_requests":1} if bound == "requests" else {"max_duration_seconds":.01} if bound == "duration" else {"max_assistant_chars":3}
    loop, _ = executor(repository, ScriptedGateway([completed(), completed()]), excess, **bounds)
    result = await loop.execute(accepted_run(repository).id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "agent_limit_reached"


@async_test
async def test_no_recovery_official_wheel_does_not_continue(tmp_path):
    repository = store(tmp_path)
    gateway = ScriptedGateway([[ModelTextDelta("partial"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)]])
    loop = RunExecutor(repository=repository, gateway=gateway, capability_resolver=TestCapabilityResolver(), plugin_factory=LoopFactory(False))
    result = await loop.execute(accepted_run(repository).id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED and result.completion_reason is CompletionReason.OUTPUT_LIMIT
    assert len(gateway.requests) == 1


@async_test
async def test_parallel_host_calls_fail_and_close_pending_stream(tmp_path):
    entered, closed = asyncio.Event(), asyncio.Event()
    class Gateway:
        async def stream(self, request):
            try:
                entered.set()
                await asyncio.Event().wait()
                yield ModelTextDelta("never")
            finally:
                closed.set()
    async def parallel(host):
        context = await host.read_context()
        task = asyncio.create_task(host.infer(input_request(host, context, channel="draft")))
        await entered.wait()
        try:
            await host.infer(input_request(host, context))
        finally:
            # Host owns cancelling/closing the outstanding operation.
            pass
        return await task
    repository = store(tmp_path)
    loop, _ = executor(repository, Gateway(), parallel)
    result = await asyncio.wait_for(loop.execute(accepted_run(repository).id, asyncio.Event()), 5)
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    assert closed.is_set()


@async_test
async def test_published_answer_cannot_be_replaced_with_revised_text(tmp_path):
    async def revise(host):
        step = await host.infer(input_request(host, await host.read_context()))
        return await host.finish(FinalOutput("revised", (step,)))
    repository = store(tmp_path)
    loop, _ = executor(repository, ScriptedGateway([completed("original")]), revise)
    result = await loop.execute(accepted_run(repository).id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.partial_text == "original"


@async_test
async def test_owner_task_cancellation_propagates_and_preserves_private_step(tmp_path):
    entered = asyncio.Event()
    class Gateway:
        async def stream(self, request):
            yield ModelTextDelta("private")
            entered.set()
            await asyncio.Event().wait()
    async def draft(host):
        return await host.infer(input_request(host, await host.read_context(), channel="draft"))
    repository = store(tmp_path)
    run = accepted_run(repository)
    loop, _ = executor(repository, Gateway(), draft)
    task = asyncio.create_task(loop.execute(run.id, asyncio.Event()))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert repository.get_run(run.id).status is RunStatus.RUNNING
    assert repository.list_run_steps(run.id)[0].text == "private"
    # RunManager owns interrupting unfinished Runs during shutdown/restart.
    repository.interrupt_incomplete_runs()
    assert repository.get_run(run.id).status is RunStatus.INTERRUPTED


@async_test
async def test_oversized_plugin_transcript_fails_before_step_or_provider_request(tmp_path):
    async def excess(host):
        context = await host.read_context()
        return await host.infer(input_request(host, context, messages=(ModelMessage("user", "x"),) * 256))
    repository = store(tmp_path)
    gateway = ScriptedGateway([])
    loop, _ = executor(repository, gateway, excess)
    run = accepted_run(repository)
    result = await loop.execute(run.id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    assert not gateway.requests and not repository.list_run_steps(run.id)
