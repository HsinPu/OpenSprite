"""API v5 behavior against real SQLite and a deterministic protocol fixture."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from context_test_support import TestCapabilityResolver
from test_agent_loop import async_test, store, ScriptedGateway, seed_completed_turns
from opensprite_backend.agent.plugin import (
    ContextReadRequest, InputSource, ModelMessage, StepRequest, FinalOutput,
    SummarySource, SummaryWriteRequest,
)
from opensprite_backend.application.run_preparation import ProductRunExecutor
from opensprite_backend.conversations.models import RunStatus, RunEventType
from opensprite_backend.inference.models import ModelTextDelta, ModelCompleted, ModelFinishReason, ModelUsage


def accept(repository, *, conversation=None, message=None):
    return repository.start_run(conversation_id=conversation, client_request_id=str(uuid4()),
        message=message or str(uuid4()), provider_id="openrouter", model_id="openrouter/auto",
        response_mode="default").run


def make_executor(repository, gateway, function=None, **limits):
    factory = None if function is None else SimpleNamespace(api_version=5,
        create=lambda: SimpleNamespace(execute=function))
    return ProductRunExecutor(repository=repository, gateway=gateway, capability_resolver=TestCapabilityResolver(),
                       plugin_factory=factory, **limits)


def events(text, reason=ModelFinishReason.FINAL):
    return [ModelTextDelta(text), ModelUsage(20, 8), ModelCompleted(reason)]


def request(host, snapshot, *, label="answer", channel="answer"):
    return StepRequest((ModelMessage("system", host.run.system_prompt),
                        ModelMessage("user", snapshot.current_user.content)), 100,
                       sources=(InputSource(1, snapshot, (snapshot.current_user.id,)),),
                       label=label, channel=channel)


@async_test
async def test_full_input_is_owned_by_loop_and_saved_once(tmp_path):
    marker = str(uuid4())
    repository = store(tmp_path)
    run = accept(repository, message=marker)
    gateway = ScriptedGateway([events(marker+"/answer")])
    async def loop(host):
        snapshot = await host.read_context()
        assert snapshot.history == () and snapshot.current_user.content == marker
        assembled = request(host, snapshot)
        assert await host.estimate_input(assembled.messages) > 0
        step = await host.infer(assembled)
        return await host.finish(FinalOutput(step.text, (step,)))
    result = await make_executor(repository, gateway, loop).execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED
    assert gateway.requests[0].messages[-1].content == marker
    assert len(gateway.requests[0].messages) == 2
    assert repository.get_run(run.id).output_continuation is None
    assert repository.list_run_steps(run.id)[0].text == marker+"/answer"
    terminal = [e for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
                if e.type is RunEventType.RUN_COMPLETED]
    assert len(terminal) == 1


@async_test
async def test_official_loop_automatically_continues_beyond_five_requests(tmp_path):
    marker = str(uuid4())
    repository = store(tmp_path)
    run = accept(repository)
    pieces = [f"{marker}/part-{index}|" for index in range(8)]
    gateway = ScriptedGateway([events(part, ModelFinishReason.OUTPUT_LIMIT if index < 7 else ModelFinishReason.FINAL)
                               for index, part in enumerate(pieces)])
    result = await make_executor(repository, gateway).execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED and result.partial_text == "".join(pieces)
    assert len(gateway.requests) == 8
    assert pieces[0].strip() in gateway.requests[1].messages[-1].content
    continuation = [e.data for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
                    if e.type is RunEventType.RESPONSE_CONTINUATION_STARTED]
    assert len(continuation) == 7 and all(item["maxAttempts"] is None for item in continuation)


@async_test
async def test_summary_generation_is_generic_inference_and_save_is_idempotent(tmp_path):
    repository = store(tmp_path)
    conversation = seed_completed_turns(repository, 3, assistant_size=20)
    run = accept(repository, conversation=conversation)
    marker = str(uuid4())
    gateway = ScriptedGateway([events("summary:"+marker), events("answer:"+marker)])
    async def loop(host):
        snapshot = await host.read_context(ContextReadRequest(after_sequence=0))
        selected = snapshot.history[:2]
        identifiers = tuple(item.id for item in selected)
        source = SummarySource((snapshot,), identifiers, summary_format="example.json.v1")
        summary = await host.infer(StepRequest(
            (ModelMessage("system", host.run.system_prompt+"\nCustom summary policy"),
             ModelMessage("user", "\n".join(item.content for item in selected))), 100,
            sources=(InputSource(1, snapshot, identifiers),), channel="draft", purpose="compaction",
            summary_source=source))
        saved = await host.save_summary(SummaryWriteRequest(summary, summary.text))
        assert saved.source_step_id == summary.id and saved.source_first_sequence == 1
        again = await host.save_summary(SummaryWriteRequest(summary, summary.text))
        assert again.id == saved.id
        final = await host.infer(request(host, snapshot))
        return await host.finish(FinalOutput(final.text, (final,)))
    result = await make_executor(repository, gateway, loop).execute(run.id, asyncio.Event())
    assert result.status is RunStatus.COMPLETED
    assert len(gateway.requests) == 2
    saved = repository.get_latest_compaction(conversation, summary_format="example.json.v1")
    assert saved.covers_through_sequence == 2
    done = [e for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
            if e.type is RunEventType.CONTEXT_COMPACTION_COMPLETED]
    assert len(done) == 1


@pytest.mark.parametrize("kind", ["copy_snapshot", "mutate_snapshot", "unknown_id", "copy_step"])
@async_test
async def test_source_ownership_rejects_copied_mutated_or_unknown_objects(tmp_path, kind):
    from dataclasses import replace
    repository = store(tmp_path)
    run = accept(repository)
    gateway = ScriptedGateway([events("private")])
    async def loop(host):
        snapshot = await host.read_context()
        if kind == "copy_snapshot": snapshot = replace(snapshot)
        elif kind == "mutate_snapshot": object.__setattr__(snapshot.current_user, "content", "forged")
        elif kind == "unknown_id":
            return await host.infer(StepRequest(
                (ModelMessage("system", host.run.system_prompt), ModelMessage("user", "forged")), 100,
                sources=(InputSource(1, snapshot, (str(uuid4()),)),)))
        elif kind == "copy_step":
            step = await host.infer(request(host, snapshot, channel="draft"))
            return await host.finish(FinalOutput(step.text, (replace(step),)))
        return await host.infer(request(host, snapshot))
    result = await make_executor(repository, gateway, loop).execute(run.id, asyncio.Event())
    assert result.status is RunStatus.FAILED and result.error.code == "internal_error"
    assert len(gateway.requests) == (1 if kind == "copy_step" else 0)


@async_test
async def test_raw_pagination_and_admission_boundary_have_no_model_side_effect(tmp_path):
    repository = store(tmp_path)
    conversation = seed_completed_turns(repository, 7, assistant_size=20)
    run = accept(repository, conversation=conversation)
    gateway = ScriptedGateway([events("done")])
    async def loop(host):
        latest = await host.read_context(ContextReadRequest(limit=3))
        assert [m.sequence for m in latest.history] == [12,13,14]
        assert latest.current_user.sequence == 15 and latest.next_before_sequence == 12
        older = await host.read_context(ContextReadRequest(before_sequence=latest.next_before_sequence, limit=3))
        assert [m.sequence for m in older.history] == [9,10,11]
        seen, cursor = [], 0
        while True:
            page = await host.read_context(ContextReadRequest(after_sequence=cursor, limit=4))
            seen.extend(m.sequence for m in page.history)
            if page.next_after_sequence is None: break
            cursor = page.next_after_sequence
        assert seen == list(range(1,15)) and not gateway.requests
        step = await host.infer(request(host, latest))
        return await host.finish(FinalOutput(step.text, (step,)))
    assert (await make_executor(repository,gateway,loop).execute(run.id,asyncio.Event())).status is RunStatus.COMPLETED


@pytest.mark.parametrize("mode", ["missing_oldest", "gap", "current_user"])
@async_test
async def test_summary_sources_reject_missing_or_non_contiguous_history(tmp_path, mode):
    repository = store(tmp_path)
    conversation = seed_completed_turns(repository, 3, assistant_size=20)
    run = accept(repository, conversation=conversation)
    gateway = ScriptedGateway([])
    async def loop(host):
        page = await host.read_context(ContextReadRequest(after_sequence=0))
        selected = page.history[2:4] if mode == "missing_oldest" else (page.history[0],page.history[2]) if mode == "gap" else (*page.history,page.current_user)
        identifiers = tuple(m.id for m in selected)
        return await host.infer(StepRequest(
            (ModelMessage("system",host.run.system_prompt),ModelMessage("user","custom summary")),100,
            sources=(InputSource(1,page,identifiers),),channel="draft",purpose="compaction",
            summary_source=SummarySource((page,),identifiers)))
    result = await make_executor(repository,gateway,loop).execute(run.id,asyncio.Event())
    assert result.status is RunStatus.FAILED and not gateway.requests
    assert repository.get_latest_compaction(conversation) is None


@async_test
async def test_summary_and_completion_event_roll_back_together(tmp_path, monkeypatch):
    from opensprite_backend.conversations.repository import ConversationStoreError
    from opensprite_backend.conversations.models import StoreFailure
    repository = store(tmp_path)
    conversation = seed_completed_turns(repository,2,assistant_size=20)
    run = accept(repository,conversation=conversation)
    original = repository._append_event
    def fail_summary_event(connection,run_id,conversation_id,event_type,*args,**kwargs):
        if event_type is RunEventType.CONTEXT_COMPACTION_COMPLETED:
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
        return original(connection,run_id,conversation_id,event_type,*args,**kwargs)
    async def loop(host):
        page = await host.read_context(ContextReadRequest(after_sequence=0,limit=2))
        ids = tuple(m.id for m in page.history)
        step = await host.infer(StepRequest(
            (ModelMessage("system",host.run.system_prompt),ModelMessage("user","summarize")),100,
            sources=(InputSource(1,page,ids),),channel="draft",purpose="compaction",
            summary_source=SummarySource((page,),ids)))
        monkeypatch.setattr(repository,"_append_event",fail_summary_event)
        await host.save_summary(SummaryWriteRequest(step,step.text))
    with pytest.raises(ConversationStoreError):
        await make_executor(repository,ScriptedGateway([events("summary")]),loop).execute(run.id,asyncio.Event())
    assert repository.get_latest_compaction(conversation) is None
    assert not any(e.type is RunEventType.CONTEXT_COMPACTION_COMPLETED for e in repository.list_run_events(run.id,after_sequence=0,limit=100))


@async_test
async def test_repeated_output_limit_segment_stops_without_another_call(tmp_path):
    repository = store(tmp_path)
    marker = str(uuid4())
    gateway = ScriptedGateway([events(marker,ModelFinishReason.OUTPUT_LIMIT)]*2)
    result = await make_executor(repository,gateway).execute(accept(repository).id,asyncio.Event())
    assert result.status is RunStatus.COMPLETED and result.completion_reason.value == "output_limit"
    assert len(gateway.requests) == 2 and result.partial_text == marker*2


@async_test
async def test_actual_receipts_preserve_all_step_sources_without_diagnostics_warning(tmp_path,caplog):
    repository = store(tmp_path)
    gateway = ScriptedGateway([events("a",ModelFinishReason.OUTPUT_LIMIT),events("b",ModelFinishReason.OUTPUT_LIMIT),events("c")])
    run = accept(repository)
    result = await make_executor(repository,gateway).execute(run.id,asyncio.Event())
    assert result.status is RunStatus.COMPLETED
    started = [e.data for e in repository.list_run_events(run.id,after_sequence=0,limit=100)
               if e.type is RunEventType.MODEL_ATTEMPT and e.data["status"] == "started"]
    assert len(started) == 3 and all(e["context"]["schemaVersion"] == 3 for e in started)
    steps = repository.list_run_steps(run.id)
    assert started[-1]["context"]["stepIds"] == [steps[0].id,steps[1].id]
    assert "diagnostics unavailable" not in caplog.text
