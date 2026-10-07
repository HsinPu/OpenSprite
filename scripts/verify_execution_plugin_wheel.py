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
from dataclasses import dataclass, field
from importlib import metadata
import json
import os
from pathlib import Path
import sys

target = Path(os.environ["OPENSPRITE_PLUGIN_VERIFY_TARGET"]).resolve()
sys.path.insert(0, str(target))
from opensprite_backend.agent.driver import DriverResult, ModelTurn
from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog
from opensprite_backend.agent.strategies import CompletionState, ContextRetryState
from opensprite_backend.conversations.models import CompletionReason
from opensprite_backend.inference.models import ModelFinishReason, ModelToolCall
import opensprite_execution_example.plugin as example

distribution = metadata.distribution("opensprite-execution-example")
assert distribution.version == "0.1.0"
assert Path(example.__file__).resolve().is_relative_to(target)
assert Path(distribution.locate_file("opensprite_execution_example/plugin.py")).resolve() == Path(example.__file__).resolve()
assert any("opensprite-backend" in requirement and ">=0.21.27" in requirement and "<0.22" in requirement
           for requirement in distribution.requires or ())
points = {(point.group, point.name): point for point in distribution.entry_points}
assert set(points) == {
    ("opensprite_backend.agent_loops.v1", "example_checkpointed"),
    ("opensprite_backend.execution_policies.v1", "example_main_retry_only"),
}
catalog = ExecutionPluginCatalog()
selection = catalog.resolve("example_checkpointed", "example_main_retry_only")
assert selection.loop_version == selection.policy_version == "0.1.0"
assert type(selection.driver_factory.create()) is example.CheckpointedDriver
assert selection.driver_factory.create() is not selection.driver_factory.create()
policy = selection.make_strategy()
assert policy is not selection.make_strategy()
assert policy.allow_context_retry(ContextRetryState("main", "provider_context_limit")) is True
assert policy.allow_context_retry(ContextRetryState("continuation", "provider_context_limit")) is False
assert policy.allow_output_continuation(CompletionState(ModelFinishReason.OUTPUT_LIMIT, "2")) is False

@dataclass
class Host:
    turns: list
    cancelled: bool = False
    tools: list = field(default_factory=list)
    result: object = None
    checkpoints: int = 0

    async def checkpoint(self):
        self.checkpoints += 1
        if self.cancelled and self.checkpoints == 2:
            raise asyncio.CancelledError

    async def next_turn(self):
        return self.turns.pop(0)

    async def execute_tools(self, turn):
        self.tools.append(turn)

    async def finish(self, turn):
        self.result = DriverResult(turn.text, CompletionReason.STOP)
        return self.result

tool = ModelTurn("", ModelFinishReason.TOOL_CALLS, (ModelToolCall("fixture-call", "calculator", {"expression": "1+1"}),))
host = Host([tool, ModelTurn("answer from fixture host", ModelFinishReason.FINAL)])
result = asyncio.run(selection.driver_factory.create().execute(host))
assert result is host.result and result.text == "answer from fixture host"
assert host.tools == [tool]
cancelled = Host([tool], cancelled=True)
try:
    asyncio.run(selection.driver_factory.create().execute(cancelled))
except asyncio.CancelledError:
    pass
else:
    raise AssertionError("driver swallowed cancellation")
assert not cancelled.tools and cancelled.result is None
print(json.dumps({"installedDistribution": distribution.metadata["Name"],
                  "version": distribution.version, "entryPointCount": len(points),
                  "profile": selection.profile(), "installedPathVerified": True,
                  "fixtureToolsResolved": len(host.tools), "fixtureCancellationPreserved": True}))
'''


def main() -> None:
    raw = os.environ.get("OPENSPRITE_PLUGIN_WHEEL")
    if not raw:
        raise SystemExit("Set OPENSPRITE_PLUGIN_WHEEL to the absolute example wheel path.")
    supplied = Path(raw)
    if not supplied.is_absolute():
        raise SystemExit("OPENSPRITE_PLUGIN_WHEEL must be absolute.")
    wheel = supplied.resolve(strict=True)
    if wheel.name != "opensprite_execution_example-0.1.0-py3-none-any.whl":
        raise SystemExit("This verifier accepts only the repository's 0.1.0 pure-Python example wheel.")
    version = tuple(int(part) for part in metadata.version("opensprite-backend").split("."))
    if not (0, 21, 27) <= version < (0, 22, 0):
        raise SystemExit("The example requires opensprite-backend>=0.21.27,<0.22.")
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
