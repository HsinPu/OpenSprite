"""Container-only repository fault fixture; never a product command."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.agent.plugin import (
    ContextReadRequest, FinalOutput, InputSource, ModelMessage, StepRequest,
    SummarySource, SummaryWriteRequest,
)
from opensprite_backend.execution_plugins.catalog import ExecutionPluginSelection
from opensprite_backend.application.run_preparation import ProductRunExecutor
from opensprite_backend.conversations.models import RunEventType
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.inference.capabilities import ModelCapability
from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta, ModelUsage


def paths():
    assert os.environ.get("OPENSPRITE_CORE_FAULT_FIXTURE") == "1"
    return build_app_paths()


def state_file():
    return paths().state_dir / "core-runtime-fault.json"


def view():
    state = json.loads(state_file().read_text(encoding="utf-8"))
    repository = SqliteConversationRepository(paths().database_file)
    run = repository.get_run(state["runId"])
    return {**state, "run": asdict(run), "steps": [asdict(s) for s in repository.list_run_steps(run.id)],
            "events": [asdict(e) for e in repository.list_run_events(run.id, after_sequence=0, limit=1000)],
            "messages": [asdict(m) for m in repository.list_messages(run.conversation_id, limit=100, before_sequence=None).items],
            "summary": None if repository.get_latest_compaction(run.conversation_id) is None else asdict(repository.get_latest_compaction(run.conversation_id))}


async def actor():
    kind = os.environ["OPENSPRITE_CORE_FAULT_KIND"]
    assert kind in {"answer_stream", "draft_stream", "summary_transaction", "final_transaction"}
    nonce = os.environ["OPENSPRITE_CORE_FAULT_NONCE"]
    assert str(UUID(nonce)) == nonce
    repository = SqliteConversationRepository(paths().database_file)
    conversation = None
    if kind == "summary_transaction":
        seed = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="history:"+nonce,
            provider_id="openrouter", model_id="fixture/model", response_mode="default").run
        repository.mark_run_started(seed.id)
        repository.complete_run(seed.id, "historical answer:"+nonce)
        conversation = seed.conversation_id
    profile = {"pluginId": "fault_probe", "pluginVersion": "1.0.0", "apiVersion": 5}
    run = repository.start_run(conversation_id=conversation, client_request_id=str(uuid4()),
        message="repository fault fixture:"+nonce, provider_id="openrouter", model_id="fixture/model",
        response_mode="default", execution_profile=profile).run
    state = {"kind": kind, "nonce": nonce, "runId": run.id, "conversationId": run.conversation_id,
             "prefix": kind+":"+nonce, "uncommittedTail": "/unflushed-"+nonce}
    state_file().parent.mkdir(parents=True, exist_ok=True)
    state_file().write_text(json.dumps(state), encoding="utf-8")
    def ready():
        print(json.dumps({"ready": True, "kind": kind, "runId": run.id}), flush=True)
    original = repository._append_event
    target = {"summary_transaction": RunEventType.CONTEXT_COMPACTION_COMPLETED,
              "final_transaction": RunEventType.RUN_COMPLETED}.get(kind)
    def blocked_transaction(connection, run_id, conversation_id, event_type, *args, **kwargs):
        if event_type is target and run_id == run.id:
            ready()
            Event().wait()  # killed by the test controller before COMMIT
        return original(connection, run_id, conversation_id, event_type, *args, **kwargs)
    if target is not None:
        repository._append_event = blocked_transaction
    class Capabilities:
        async def resolve(self, provider_id, model_id):
            return ModelCapability(provider_id, model_id, "Fault fixture", 32000, 4096)
    class Gateway:
        async def stream(self, request):
            yield ModelTextDelta(state["prefix"])
            if kind.endswith("stream"):
                yield ModelTextDelta(state["uncommittedTail"])
                ready()
                await asyncio.Event().wait()
            yield ModelUsage(20, 8)
            yield ModelCompleted(ModelFinishReason.FINAL)
    async def loop(host):
        snapshot = await host.read_context(ContextReadRequest(after_sequence=0))
        if kind == "summary_transaction":
            ids = tuple(m.id for m in snapshot.history)
            step = await host.infer(StepRequest(
                (ModelMessage("system", host.run.system_prompt), ModelMessage("user", "summarize fixture history")),
                100, sources=(InputSource(1, snapshot, ids),), channel="draft", purpose="compaction",
                summary_source=SummarySource((snapshot,), ids)))
            await host.save_summary(SummaryWriteRequest(step, step.text))
        else:
            channel = "answer" if kind == "answer_stream" else "draft"
            step = await host.infer(StepRequest(
                (ModelMessage("system", host.run.system_prompt), ModelMessage("user", snapshot.current_user.content)),
                100, sources=(InputSource(1, snapshot, (snapshot.current_user.id,)),), channel=channel))
            return await host.finish(FinalOutput(step.text, (step,)))
    factory = SimpleNamespace(api_version=5, create=lambda: SimpleNamespace(execute=loop))
    selection = ExecutionPluginSelection("fault_probe", "1.0.0", factory)
    executor = ProductRunExecutor(repository=repository, gateway=Gateway(), capability_resolver=Capabilities())
    await executor.execute(run.id, asyncio.Event(), execution_plugin=selection)
    raise AssertionError("The controller should kill the active fixture")


if __name__ == "__main__":
    if os.environ["OPENSPRITE_CORE_FAULT_OPERATION"] == "inspect":
        print(json.dumps(view(), default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)))
    else:
        asyncio.run(actor())
