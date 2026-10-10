"""Verify the repository example from an installed wheel, without app mutation.

Run in the backend development environment. OPENSPRITE_PLUGIN_WHEEL is the
absolute built-wheel path; OPENSPRITE_TEST_UV optionally selects a uv executable.
This is repository verification automation, not an application installer or CLI.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


INSTALLED_CHECK = r'''
import asyncio
from dataclasses import dataclass
from importlib import metadata
import json
import os
from pathlib import Path
import sys

target = Path(os.environ["OPENSPRITE_PLUGIN_VERIFY_TARGET"]).resolve()
sys.path.insert(0, str(target))
from opensprite_backend.execution_plugins.catalog import ExecutionPluginCatalog
from opensprite_backend.agent.plugin import CompletionReason, ModelFinishReason
import opensprite_execution_example.plugin as example

distribution = metadata.distribution("opensprite-execution-example")
assert distribution.version == "0.5.0"
assert Path(example.__file__).resolve().is_relative_to(target)
assert Path(distribution.locate_file("opensprite_execution_example/plugin.py")).resolve() == Path(example.__file__).resolve()
assert any("opensprite-backend" in requirement and ">=0.21.35" in requirement and "<0.22" in requirement
           for requirement in distribution.requires or ())
points = {(point.group, point.name): point for point in distribution.entry_points}
assert set(points) == {("opensprite_backend.agent_loops.v5", "example_review")}
catalog = ExecutionPluginCatalog()
selection = catalog.resolve("example_review")
assert selection.plugin_version == "0.5.0"
plugin = selection.create()
assert type(plugin) is example.ReviewLoop
assert plugin is not selection.create()
# Exercise the installed plugin through the actual core and provider adapter.
from uuid import uuid4
import httpx
from opensprite_backend.application.run_preparation import ProductRunExecutor
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.inference.native_gateway import NativeModelGateway
from opensprite_backend.providers.operation_locks import ProviderOperationLocks
from opensprite_backend.inference.capabilities import ModelCapability

nonce = str(uuid4())
captured = []
class Capabilities:
    async def resolve(self, provider_id, model_id):
        return ModelCapability(provider_id, model_id, "Protocol fixture", 32000, 4096)
class Credentials:
    def get(self, provider_id):
        assert provider_id == "openrouter"
        return "isolated-fixture-token"
def wire(request):
    body = json.loads(request.content)
    captured.append(body)
    assert any(message["content"] == nonce for message in body["messages"])
    stage = ["draft", "review", "final"][len(captured)-1]
    assert "tools" not in body and "tool_choice" not in body
    frames = [
        {"choices": [{"index": 0, "delta": {"content": stage + ":" + nonce}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]
    data = "".join("data: " + json.dumps(frame) + "\n\n" for frame in frames) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=data)
async def execute():
    repository = SqliteConversationRepository(Path("verification-core.sqlite"))
    accepted = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=nonce,
                                    provider_id="openrouter", model_id="fixture/model", response_mode="default", execution_profile=selection.profile())
    async with httpx.AsyncClient(transport=httpx.MockTransport(wire)) as client:
        loop = ProductRunExecutor(repository=repository, gateway=NativeModelGateway(Credentials(), client, ProviderOperationLocks()),
                         capability_resolver=Capabilities())
        await loop.execute(accepted.run.id, asyncio.Event(), execution_plugin=selection)
    result = repository.get_run(accepted.run.id)
    assert result.status is RunStatus.COMPLETED and result.partial_text == "final:" + nonce
    events = repository.list_run_events(result.id, after_sequence=0, limit=200)
    assert next(event.data for event in events if event.type is RunEventType.EXECUTION_SELECTED) == selection.profile()
    assert any(event.type is RunEventType.ASSISTANT_DELTA for event in events)
    steps = repository.list_run_steps(result.id, after_sequence=0, limit=100)
    assert [step.text for step in steps] == [stage + ":" + nonce for stage in ("draft", "review", "final")]
    assert [step.channel for step in steps] == ["draft", "draft", "answer"]
    assert len(captured) == 3
    messages = repository.list_messages(result.conversation_id, limit=100, before_sequence=None).items
    assert [message.content for message in messages] == [nonce, "final:" + nonce]
    assert captured[1]["messages"][-1]["content"] == "draft:" + nonce
    assert captured[2]["messages"][-1]["content"] == "Draft review:\nreview:" + nonce
asyncio.run(execute())

# A real Host cancellation must preserve the private step and stop requests.
async def cancel_execute():
    repository = SqliteConversationRepository(Path("verification-cancel.sqlite"))
    run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=nonce,
        provider_id="openrouter", model_id="fixture/model", response_mode="default").run
    cancellation, started = asyncio.Event(), asyncio.Event()
    class BlockedGateway:
        async def stream(self, request):
            from opensprite_backend.inference.models import ModelTextDelta
            yield ModelTextDelta("private-" + nonce)
            started.set()
            await asyncio.Event().wait()
    loop = ProductRunExecutor(repository=repository, gateway=BlockedGateway(), capability_resolver=Capabilities())
    task = asyncio.create_task(loop.execute(run.id, cancellation, execution_plugin=selection))
    await asyncio.wait_for(started.wait(), 5)
    repository.request_cancel(run.id)
    cancellation.set()
    result = await asyncio.wait_for(task, 5)
    assert result.status is RunStatus.CANCELLED and result.partial_text == ""
    steps = repository.list_run_steps(run.id, after_sequence=0, limit=100)
    assert len(steps) == 1 and steps[0].status == "cancelled" and steps[0].text == "private-" + nonce
asyncio.run(cancel_execute())
print(json.dumps({"installedDistribution": distribution.metadata["Name"],
                  "version": distribution.version, "entryPointCount": len(points),
                  "profile": selection.profile(), "installedPathVerified": True,
                  "coreRunCompleted": True, "variableWireOutputVerified": True,
                  "providerRequestCount": len(captured), "cancellationPreserved": True}))

'''


def main() -> None:
    raw = os.environ.get("OPENSPRITE_PLUGIN_WHEEL")
    if not raw:
        raise SystemExit("Set OPENSPRITE_PLUGIN_WHEEL to the absolute example wheel path.")
    supplied = Path(raw)
    if not supplied.is_absolute():
        raise SystemExit("OPENSPRITE_PLUGIN_WHEEL must be absolute.")
    wheel = supplied.resolve(strict=True)
    if wheel.name != "opensprite_execution_example-0.5.0-py3-none-any.whl":
        raise SystemExit("This verifier accepts only the repository's 0.5.0 pure-Python example wheel.")
    version = tuple(int(part) for part in metadata.version("opensprite-backend").split("."))
    if not (0, 21, 35) <= version < (0, 22, 0):
        raise SystemExit("The example requires opensprite-backend>=0.21.35,<0.22.")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        wheel_info = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(wheel_info) != 1:
            raise SystemExit("Invalid example wheel metadata.")
        text = archive.read(wheel_info[0]).decode("utf-8")
        if "Root-Is-Purelib: true" not in text or "Tag: py3-none-any" not in text:
            raise SystemExit("The example wheel must be pure Python.")
    uv = os.environ.get("OPENSPRITE_TEST_UV") or shutil.which("uv")
    if not uv:
        raise SystemExit("Install uv or set OPENSPRITE_TEST_UV for repository verification.")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="opensprite-example-wheel-") as temporary:
        temporary_root = Path(temporary).resolve()
        target = temporary_root / "installed"
        subprocess.run([uv, "pip", "install", "--python", sys.executable,
                        "--target", str(target), "--no-deps", "--no-index", str(wheel)], check=True)
        environment = dict(os.environ)
        environment["OPENSPRITE_PLUGIN_VERIFY_TARGET"] = str(target)
        verified = subprocess.run([sys.executable, "-I", "-c", INSTALLED_CHECK],
                                  cwd=temporary_root, env=environment, check=True,
                                  text=True, capture_output=True)
        result = json.loads(verified.stdout)
        print(json.dumps({"wheel": wheel.name, "sha256": digest,
                          "coreVersion": metadata.version("opensprite-backend"), **result}))


if __name__ == "__main__":
    main()
