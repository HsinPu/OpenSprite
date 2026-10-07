"""Selected third-party drivers exercise the real host and child boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from uuid import uuid4

from context_test_support import TestCapabilityResolver
from test_agent_loop import LookupTool, ScriptedGateway
from test_agent_policy import candidate
from test_child_executor import WriteTool, definition, workspace
from test_child_repository import create, stores
from test_execution_plugin_catalog import InstalledPoint, LOOPS

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog
from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.custom_agents.child_executor import ChildAgentExecutor
from opensprite_backend.custom_agents.child_repository import ChildExecutionRepository
from opensprite_backend.custom_agents.delegation import DelegationCoordinator
from opensprite_backend.custom_agents.models import AgentExecutionSnapshot
from opensprite_backend.inference.models import (
    ModelCompleted, ModelFinishReason, ModelTextDelta, ModelToolCall,
)
from opensprite_backend.skills.models import SkillExecutionSnapshot
from opensprite_backend.tools.availability import ToolAvailabilitySnapshot
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.workspaces import DefaultWorkspaceResolver


@dataclass
class AlternateDriver:
    """A selected plugin implementation, not the built-in driver class."""
    host: object = None
    operations: list[str] = field(default_factory=list)

    async def execute(self, host):
        self.host = host
        while True:
            self.operations.append("checkpoint")
            await host.checkpoint()
            self.operations.append("model")
            turn = await host.next_turn()
            if turn.tool_calls:
                self.operations.append("tools")
                await host.execute_tools(turn)
            else:
                self.operations.append("finish")
                return await host.finish(turn)


@dataclass
class AlternateFactory:
    api_version: int = 1
    instances: list[AlternateDriver] = field(default_factory=list)

    def create(self):
        driver = AlternateDriver()
        self.instances.append(driver)
        return driver


def binding(*, policy="standard"):
    factory = AlternateFactory()
    point = InstalledPoint("alternate", LOOPS, lambda: factory)
    selection = ExecutionPluginCatalog((point,)).resolve("alternate", policy)
    return selection, factory


def accepted(repository):
    return repository.start_run(
        conversation_id=None, client_request_id=str(uuid4()), message="Inspect a note",
        provider_id="openai", model_id="test", response_mode="default",
    ).run


def test_catalog_selected_driver_uses_real_model_tools_events_and_new_instance_per_run(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    selection, factory = binding()
    tool = LookupTool()
    gateway = ScriptedGateway([
        [ModelToolCall("lookup_1", "lookup_note", {"query": "today"}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
        [ModelTextDelta("first answer"), ModelCompleted(ModelFinishReason.FINAL)],
        [ModelToolCall("lookup_2", "lookup_note", {"query": "tomorrow"}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
        [ModelTextDelta("second answer"), ModelCompleted(ModelFinishReason.FINAL)],
    ])

    async def scenario():
        loop = AgentLoop(repository=repository, gateway=gateway,
                         tools=ToolRegistry((tool,), policy=ReadOnlyToolPolicy()),
                         capability_resolver=TestCapabilityResolver())
        manager = RunManager(repository, loop)
        try:
            for expected_text in ("first answer", "second answer"):
                run = accepted(repository)
                fixed_workspace = DefaultWorkspaceResolver().execution_context(run.workspace_id)
                assert await manager.start(run.id, fixed_workspace, execution_plugins=selection)
                result = await manager.wait(run.id)
                assert result.status is RunStatus.COMPLETED
                assert result.partial_text == expected_text
                events = repository.list_run_events(run.id, after_sequence=0, limit=200)
                assert any(event.type is RunEventType.TOOL_COMPLETED for event in events)
                metadata = next(event for event in events if event.type is RunEventType.EXECUTION_SELECTED)
                assert metadata.data == selection.profile()
        finally:
            await manager.close()

    asyncio.run(scenario())
    assert len(factory.instances) == 2
    assert factory.instances[0] is not factory.instances[1]
    assert factory.instances[0].host is not factory.instances[1].host
    assert [driver.operations for driver in factory.instances] == [
        ["checkpoint", "model", "tools", "checkpoint", "model", "finish"],
        ["checkpoint", "model", "tools", "checkpoint", "model", "finish"],
    ]
    assert tool.calls == [{"query": "today"}, {"query": "tomorrow"}]
    assert len(gateway.requests) == 4
    assert gateway.requests[1].messages[-1].role == "tool"


def test_replaced_driver_cannot_expand_host_model_round_limit(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    selection, factory = binding()
    tool = LookupTool()
    gateway = ScriptedGateway([
        [ModelToolCall("lookup", "lookup_note", {"query": "today"}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
        [ModelTextDelta("forbidden extra round"), ModelCompleted(ModelFinishReason.FINAL)],
    ])
    loop = AgentLoop(repository=repository, gateway=gateway,
                     tools=ToolRegistry((tool,), policy=ReadOnlyToolPolicy()),
                     capability_resolver=TestCapabilityResolver(), max_model_rounds=1)
    run = accepted(repository)
    result = asyncio.run(loop.execute(run.id, asyncio.Event(), execution_plugins=selection))
    assert result.status is RunStatus.FAILED
    assert result.error.code == "agent_limit_reached"
    assert len(gateway.requests) == 1
    assert tool.calls == [{"query": "today"}]
    assert len(factory.instances) == 1


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

        manager = RunManager(repository, AgentLoop(
            repository=repository, gateway=Gateway(),
            tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
            capability_resolver=TestCapabilityResolver()))
        run = accepted(repository)
        fixed_workspace = DefaultWorkspaceResolver().execution_context(run.workspace_id)
        try:
            await manager.start(run.id, fixed_workspace, execution_plugins=selection)
            await asyncio.wait_for(started.wait(), 5)
            await manager.cancel(run.id)
            result = await asyncio.wait_for(manager.wait(run.id), 5)
            assert result.status is RunStatus.CANCELLED
            assert result.partial_text == "kept partial output"
        finally:
            await manager.close()

    asyncio.run(scenario())
    assert len(factory.instances) == 1


def test_replaced_child_driver_cannot_request_consequential_tool_approval(stores):
    repository, _, parent, _ = stores
    child, _ = create(repository, parent)
    selection, factory = binding()
    tool = WriteTool()
    gateway = ScriptedGateway([[
        ModelToolCall("write", "write_note", {"text": "unauthorized"}),
        ModelCompleted(ModelFinishReason.TOOL_CALLS),
    ]])
    result = asyncio.run(ChildAgentExecutor(gateway, TestCapabilityResolver(), repository).execute(
        child=child, parent=parent, workspace=workspace(), skills=SkillExecutionSnapshot(),
        definition=definition(), task="bounded child task", tools=ToolRegistry((tool,), policy=ReadOnlyToolPolicy()),
        availability=ToolAvailabilitySnapshot(frozenset({"write_note"})), base_system_prompt="base",
        cancellation_event=asyncio.Event(), execution_plugins=selection,
    ))
    assert len(factory.instances) == 1
    assert result.status is RunStatus.FAILED
    assert result.error.code == "subagent_tool_approval_required"
    assert tool.calls == []
    assert repository.get(parent.id, child.id).error_code == "subagent_tool_approval_required"


def test_parent_and_delegated_child_use_the_same_pinned_plugin_selection(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    run = accepted(repository)
    child_store = ChildExecutionRepository(tmp_path / "chat.sqlite")
    role = candidate()
    selection, factory = binding(policy="no_recovery")
    child_gateway = ScriptedGateway([
        [ModelTextDelta("bounded child report"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
        [ModelTextDelta("must not automatically continue"), ModelCompleted(ModelFinishReason.FINAL)],
    ])

    class ParentGateway:
        step = 0

        async def stream(self, request):
            self.step += 1
            if self.step == 1:
                call = ModelToolCall("spawn", "spawn_agent", {
                    "agentId": role.record.id, "task": "review bounded input",
                    "background": "", "scope": "review only", "expectedOutput": "report",
                })
            elif self.step == 2:
                self.child_id = json.loads(request.messages[-1].content)["childId"]
                call = ModelToolCall("wait", "wait_agents", {"childIds": [self.child_id]})
            elif self.step == 3:
                assert json.loads(request.messages[-1].content)["items"][0]["status"] == "completed"
                call = ModelToolCall("read", "get_agent_result", {"childId": self.child_id, "offset": 0})
            else:
                assert json.loads(request.messages[-1].content)["text"] == "bounded child report"
                yield ModelTextDelta("parent synthesis")
                yield ModelCompleted(ModelFinishReason.FINAL)
                return
            yield call
            yield ModelCompleted(ModelFinishReason.TOOL_CALLS)

    async def scenario():
        resolver = TestCapabilityResolver()
        coordinator = DelegationCoordinator(child_store, ChildAgentExecutor(child_gateway, resolver, child_store))
        loop = AgentLoop(repository=repository, gateway=ParentGateway(),
                         tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
                         capability_resolver=resolver, delegation=coordinator)
        try:
            result = await loop.execute(run.id, asyncio.Event(),
                                        agents=AgentExecutionSnapshot((role,)), execution_plugins=selection)
            assert result.status is RunStatus.COMPLETED
            assert result.partial_text == "parent synthesis"
            children = child_store.list(run.id)
            assert len(children) == 1 and children[0].status == "completed"
            assert children[0].result_text == "bounded child report"
            assert len(factory.instances) == 2
            assert factory.instances[0] is not factory.instances[1]
            assert len(child_gateway.requests) == 1
            assert len(child_gateway.scripts) == 1
            assert all("Inspect a note" not in item.content for item in child_gateway.requests[0].messages)
        finally:
            await coordinator.close()

    asyncio.run(scenario())
