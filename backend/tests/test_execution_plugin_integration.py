"""Selected third-party drivers exercise the real host and child boundary."""

from __future__ import annotations

from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta

import asyncio
from dataclasses import dataclass, field
import json
from uuid import uuid4

from context_test_support import TestCapabilityResolver
from test_agent_loop import ScriptedGateway
from test_execution_plugin_catalog import InstalledPoint, LOOPS

from opensprite_backend.application.run_preparation import ProductRunExecutor
from opensprite_backend.execution_plugins.catalog import ExecutionPluginCatalog
from opensprite_backend.application.run_manager import RunManager
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.workspaces.service import DefaultWorkspaceResolver


@dataclass
class AlternateDriver:
    """A selected plugin implementation, not the built-in driver class."""
    host: object = None
    operations: list[str] = field(default_factory=list)

    async def execute(self, host):
        self.host = host
        self.operations.append("checkpoint")
        await host.checkpoint()
        self.operations.append("model")
        from opensprite_backend.agent.plugin import StepRequest, FinalOutput, InputSource, ModelMessage
        snapshot = await host.read_context()
        turn = await host.infer(StepRequest((ModelMessage("system", host.run.system_prompt), ModelMessage("user", snapshot.current_user.content)), 1000,
            sources=(InputSource(1, snapshot, (snapshot.current_user.id,)),)))
        self.operations.append("finish")
        return await host.finish(FinalOutput(turn.text, (turn,)))


@dataclass
class AlternateFactory:
    api_version: int = 5
    instances: list[AlternateDriver] = field(default_factory=list)

    def create(self):
        driver = AlternateDriver()
        self.instances.append(driver)
        return driver


def binding(*, policy="standard"):
    factory = AlternateFactory()
    point = InstalledPoint("alternate", LOOPS, lambda: factory)
    selection = ExecutionPluginCatalog((point,)).resolve("alternate")
    return selection, factory


def accepted(repository):
    return repository.start_run(
        conversation_id=None, client_request_id=str(uuid4()), message="Inspect a note",
        provider_id="openai", model_id="test", response_mode="default",
    ).run


def test_replaced_driver_preserves_cancellation_and_partial_output(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    selection, factory = binding()

    async def scenario():
        started = asyncio.Event()

        class Gateway:
            async def stream(self, request):
                yield ModelTextDelta("kept partial output")
                started.set()
                await asyncio.Event().wait()
                yield ModelCompleted(ModelFinishReason.FINAL)

        manager = RunManager(repository, ProductRunExecutor(
            repository=repository, gateway=Gateway(),

            capability_resolver=TestCapabilityResolver()))
        run = accepted(repository)
        fixed_workspace = DefaultWorkspaceResolver().execution_context(run.workspace_id)
        try:
            await manager.start(run.id, fixed_workspace, execution_plugin=selection)
            await asyncio.wait_for(started.wait(), 5)
            await manager.cancel(run.id)
            result = await asyncio.wait_for(manager.wait(run.id), 5)
            assert result.status is RunStatus.CANCELLED
            assert result.partial_text == "kept partial output"
        finally:
            await manager.close()

    asyncio.run(scenario())
    assert len(factory.instances) == 1
