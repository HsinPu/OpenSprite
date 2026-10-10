"""Dynamic protocol fixture through the real core/SQLite, without product imports.

This repository verification fixture makes no network requests and is not a
model-quality test. Run it only against an explicitly supplied disposable root.
"""
import asyncio
import json
from random import SystemRandom
from uuid import uuid4

from opensprite_backend.agent.execution_input import ExecutionPluginSelection, PreparedRun
from opensprite_backend.agent.plugin import FinalOutput, InputSource, ModelMessage, ModelLimits, StepRequest
from opensprite_backend.agent.run_executor import RunExecutor
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.response_modes import ReasoningResolution


async def exercise_core(root):
    random = SystemRandom()
    payload = {"nonce": str(uuid4()), "values": [random.randrange(1000, 10000) for _ in range(3)]}
    expected = payload["nonce"] + ":" + str(sum(payload["values"]))
    base_prompt = "A product-provided base prefix " + str(uuid4())
    requests = []

    class Gateway:
        async def stream(self, request):
            requests.append(request)
            data = json.loads(request.messages[-1].content)
            yield ModelTextDelta(data["nonce"] + ":" + str(sum(data["values"])))
            yield ModelCompleted(ModelFinishReason.FINAL)

    class Loop:
        async def execute(self, host):
            snapshot = await host.read_context()
            step = await host.infer(StepRequest(
                (ModelMessage("system", host.run.system_prompt), ModelMessage("user", snapshot.current_user.content)),
                1000, (InputSource(1, snapshot, (snapshot.current_user.id,)),),
            ))
            return await host.finish(FinalOutput(step.text, (step,)))

    class Factory:
        api_version = 5
        def create(self):
            return Loop()

    selection = ExecutionPluginSelection("isolated_test", "1.0.0", Factory())
    class Preparation:
        async def prepare(self, run):
            return PreparedRun(run.id, base_prompt, ModelLimits(32000, 4096), selection,
                               ReasoningResolution(run.response_mode, None, "provider_default"))

    paths = build_app_paths(root / ".opensprite")
    repository = SqliteConversationRepository(paths.database_file)
    accepted = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=json.dumps(payload),
        provider_id="openrouter", model_id="fixture/model", response_mode="default", execution_profile=selection.profile())
    result = await RunExecutor(repository=repository, gateway=Gateway()).execute(
        accepted.run.id, asyncio.Event(), preparation=Preparation())
    assert result.status is RunStatus.COMPLETED and result.partial_text == expected
    assert len(requests) == 1 and requests[0].messages[0].content == base_prompt
    reloaded = SqliteConversationRepository(paths.database_file)
    assert reloaded.get_run(result.id) == result
    events = reloaded.list_run_events(result.id, after_sequence=0, limit=100)
    assert sum(event.type is RunEventType.RUN_COMPLETED for event in events) == 1
    assert sum(event.type is RunEventType.MODEL_ATTEMPT and event.data["status"] == "started" for event in events) == 1
    assert not paths.system_prompt_logs_dir.exists() and not paths.prompt_logs_dir.exists()
    return {"kind": "isolated-core-protocol", "status": result.status.value,
            "nonce": payload["nonce"], "answer": result.partial_text, "modelRequests": len(requests),
            "sqliteReloadVerified": True, "pluginId": selection.plugin_id, "hostApiVersion": 5}
