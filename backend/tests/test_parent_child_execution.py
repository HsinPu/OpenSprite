import asyncio
import json
from uuid import uuid4

from context_test_support import TestCapabilityResolver
from test_agent_loop import ScriptedGateway
from test_agent_policy import candidate
from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.custom_agents.child_executor import ChildAgentExecutor
from opensprite_backend.custom_agents.child_repository import ChildExecutionRepository
from opensprite_backend.custom_agents.delegation import DelegationCoordinator
from opensprite_backend.custom_agents.models import AgentExecutionSnapshot
from opensprite_backend.inference.models import ModelToolCall, ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.tools.policy import ReadOnlyToolPolicy


def test_parent_discovers_delegates_and_reads_real_child_loop_result(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()),
                               message="original parent request", provider_id="openai",
                               model_id="test", response_mode="default").run
    store = ChildExecutionRepository(tmp_path / "chat.sqlite")
    role = candidate()
    child_gateway = ScriptedGateway([[ModelTextDelta("verified child report"), ModelCompleted(ModelFinishReason.FINAL)]])

    class ParentGateway:
        step = 0
        async def stream(self, request):
            self.step += 1
            if self.step == 1:
                assert "spawn_agent" in {tool.name for tool in request.tools}
                call = ModelToolCall("discover", "discover_agents", {"query": "", "offset": 0})
            elif self.step == 2:
                found = json.loads(request.messages[-1].content)
                call = ModelToolCall("spawn", "spawn_agent", {
                    "agentId": found["items"][0]["id"], "task": "review bounded input",
                    "background": "", "scope": "review only", "expectedOutput": "report",
                })
            elif self.step == 3:
                self.child_id = json.loads(request.messages[-1].content)["childId"]
                call = ModelToolCall("wait", "wait_agents", {"childIds": [self.child_id]})
            elif self.step == 4:
                assert json.loads(request.messages[-1].content)["items"][0]["status"] == "completed"
                call = ModelToolCall("read", "get_agent_result", {"childId": self.child_id, "offset": 0})
            else:
                assert json.loads(request.messages[-1].content)["text"] == "verified child report"
                yield ModelTextDelta("parent synthesis")
                yield ModelCompleted(ModelFinishReason.FINAL)
                return
            yield call
            yield ModelCompleted(ModelFinishReason.TOOL_CALLS)

    async def scenario():
        resolver = TestCapabilityResolver()
        coordinator = DelegationCoordinator(store, ChildAgentExecutor(child_gateway, resolver, store))
        loop = AgentLoop(repository=repository, gateway=ParentGateway(),
                         tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
                         capability_resolver=resolver, delegation=coordinator)
        result = await loop.execute(run.id, asyncio.Event(), agents=AgentExecutionSnapshot((role,)))
        assert result.status == RunStatus.COMPLETED
        assert result.partial_text == "parent synthesis"
        children = store.list(run.id)
        assert len(children) == 1 and children[0].status == "completed"
        assert all("original parent request" not in message.content for message in child_gateway.requests[0].messages)
        assert not {"spawn_agent", "discover_agents"} & {tool.name for tool in child_gateway.requests[0].tools}
        assert coordinator._parents == {} and coordinator._inputs == {}
        await coordinator.close()
    asyncio.run(scenario())


def test_parent_does_not_finish_or_leave_child_when_cancelled(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()),
                               message="parent", provider_id="openai", model_id="test",
                               response_mode="default").run
    store = ChildExecutionRepository(tmp_path / "chat.sqlite")
    role = candidate()

    async def scenario():
        child_started, child_cleaned, parent_final = asyncio.Event(), asyncio.Event(), asyncio.Event()
        class ChildGateway:
            async def stream(self, request):
                child_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    child_cleaned.set()
                yield ModelCompleted(ModelFinishReason.FINAL)
        class ParentGateway:
            step = 0
            async def stream(self, request):
                self.step += 1
                if self.step == 1:
                    yield ModelToolCall("spawn", "spawn_agent", {"agentId": role.record.id,
                        "task": "bounded task", "background": "", "scope": "", "expectedOutput": "report"})
                    yield ModelCompleted(ModelFinishReason.TOOL_CALLS)
                else:
                    parent_final.set()
                    yield ModelTextDelta("parent wants to finish")
                    yield ModelCompleted(ModelFinishReason.FINAL)
        resolver = TestCapabilityResolver()
        coordinator = DelegationCoordinator(store, ChildAgentExecutor(ChildGateway(), resolver, store))
        loop = AgentLoop(repository=repository, gateway=ParentGateway(),
                         tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
                         capability_resolver=resolver, delegation=coordinator)
        cancellation = asyncio.Event()
        task = asyncio.create_task(loop.execute(run.id, cancellation, agents=AgentExecutionSnapshot((role,))))
        await asyncio.wait_for(child_started.wait(), 5)
        await asyncio.wait_for(parent_final.wait(), 5)
        assert repository.get_run(run.id).status == RunStatus.RUNNING
        cancellation.set()
        result = await asyncio.wait_for(task, 5)
        assert result.status == RunStatus.CANCELLED
        assert child_cleaned.is_set()
        assert store.list(run.id)[0].status == "cancelled"
        assert coordinator._parents == {}
        await coordinator.close()
    asyncio.run(scenario())
