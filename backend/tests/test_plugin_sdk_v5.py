"""Golden ABI is the pre-refactor v5 contract, not a generated expected answer."""
import ast
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime
from pathlib import Path
import json
from uuid import uuid4
import asyncio

import pytest
from sdk_v5_contract_support import contract
from test_agent_loop import async_test, store
from test_agent_drivers import executor, input_request, completed, ScriptedGateway
from test_host_v5 import accept
from opensprite_backend.agent import plugin as sdk
from opensprite_backend.agent import plugin_conversion as convert
from opensprite_backend.conversations import models as stored
from opensprite_backend.inference import models as inference
from opensprite_backend.inference.gateway import ModelGatewayError


def test_public_v5_matches_the_pinned_pre_refactor_contract():
    path = Path(__file__).resolve().parents[2] / "contracts/agent-loop-v5.sdk.json"
    assert contract() == json.loads(path.read_text(encoding="utf-8"))


def test_sdk_data_imports_no_persistence_transport_or_application_modules():
    import opensprite_backend.agent.plugin as api
    import opensprite_backend.agent.plugin_data as data
    for module in (api, data):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        assert not any(isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            ("opensprite_backend.conversations", "opensprite_backend.inference", "opensprite_backend.application"))
            for node in ast.walk(tree))
    assert sdk.Message is not stored.Message
    assert sdk.ConversationCompaction is not stored.ConversationCompaction
    assert sdk.PublicRunError is not stored.PublicRunError
    assert sdk.ModelMessage is not inference.ModelMessage


def test_explicit_summary_mapping_preserves_every_field_and_detaches_objects():
    original = stored.ConversationCompaction(str(uuid4()), str(uuid4()), 4, str(uuid4()), 3,
        "a"*64, "openrouter", "test/model", 17, 4, datetime.now(UTC),
        "custom_loop", "2.3.4", "custom.format.v1", str(uuid4()), 3, str(uuid4()))
    public = convert.summary(original)
    assert type(public) is sdk.ConversationCompaction and asdict(public) == asdict(original)
    object.__setattr__(public, "summary", "modified plugin view")
    assert original.summary != public.summary
    assert convert.error(None) is None and convert.summary(None) is None
    error = stored.PublicRunError("provider_timeout", "Timeout", True)
    assert asdict(convert.error(error)) == asdict(error)
    assert convert.stored_error(convert.error(error)) == error
    assert convert.completion_reason(sdk.CompletionReason.STOP) is stored.CompletionReason.STOP
    assert convert.finish_reason(inference.ModelFinishReason.FINAL) is sdk.ModelFinishReason.FINAL


@pytest.mark.parametrize("channel", ["draft", "answer"])
@async_test
async def test_host_returns_public_data_and_gateway_receipts_keep_exact_bindings(tmp_path, channel):
    repository = store(tmp_path)
    marker = str(uuid4())
    run = accept(repository, message=marker)
    gateway = ScriptedGateway([completed(marker)])
    async def loop(host):
        context = await host.read_context()
        assert type(context.current_user) is sdk.Message
        assert type(context.history) is tuple
        step = await host.infer(input_request(host, context, channel=channel))
        assert type(step) is sdk.StepResult
        assert step.finish_reason is sdk.ModelFinishReason.FINAL
        return await host.finish(sdk.FinalOutput(step.text, (step,)))
    runtime, _ = executor(repository, gateway, loop)
    result = await runtime.execute(run.id, asyncio.Event())
    assert result.status is stored.RunStatus.COMPLETED and result.completion_reason is stored.CompletionReason.STOP
    assert all(type(message) is inference.ModelMessage for message in gateway.requests[0].messages)
    receipt = next(e.data["context"] for e in repository.list_run_events(run.id, after_sequence=0, limit=100)
                   if e.type is stored.RunEventType.MODEL_ATTEMPT and e.data["status"] == "started")
    assert receipt["historyMessageIds"] == [run.user_message_id]
    assert receipt["components"]["currentUser"] > 0 and receipt["components"]["unattributed"] == 0


@async_test
async def test_public_step_error_round_trips_to_stored_terminal_error(tmp_path):
    repository = store(tmp_path)
    run = accept(repository)
    gateway = ScriptedGateway([[ModelGatewayError(inference.InferenceFailure.PROVIDER_TIMEOUT)]])
    async def loop(host):
        step = await host.infer(input_request(host, await host.read_context(), channel="draft"))
        assert type(step.error) is sdk.PublicRunError and step.error.code == "provider_timeout"
        result = await host.finish(sdk.FinalOutput(error_step=step))
        assert type(result.error) is sdk.PublicRunError
        return result
    runtime, _ = executor(repository, gateway, loop)
    result = await runtime.execute(run.id, asyncio.Event())
    assert type(result.error) is stored.PublicRunError and result.error.code == "provider_timeout"
    assert result.status is stored.RunStatus.FAILED
