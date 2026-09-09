import asyncio

import pytest
from test_child_repository import stores
from test_agent_policy import candidate
from opensprite_backend.custom_agents.delegation import DelegationCoordinator, ParentDelegation
from opensprite_backend.custom_agents.models import AgentExecutionSnapshot, AgentError
from opensprite_backend.skills.models import SkillExecutionSnapshot
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.availability import ToolAvailabilitySnapshot
from opensprite_backend.workspaces import DefaultWorkspaceResolver


def setup(repository, parent, executor):
    role = candidate("review")
    coordinator = DelegationCoordinator(repository, executor)
    coordinator.register(ParentDelegation(
        parent, DefaultWorkspaceResolver().execution_context(parent.workspace_id),
        SkillExecutionSnapshot(), AgentExecutionSnapshot((role,)),
        ToolRegistry((), policy=ReadOnlyToolPolicy()), ToolAvailabilitySnapshot(frozenset()), "base",
    ))
    arguments = {"agentId": role.record.id, "task": "Review", "background": "",
                 "scope": "One task", "expectedOutput": "Report"}
    return coordinator, arguments


def test_spawn_wait_and_result_are_owned_and_idempotent(stores):
    repository, _, parent, _ = stores

    class Executor:
        calls = 0
        async def execute(self, **inputs):
            self.calls += 1
            child = inputs["child"]
            repository.transition(parent.id, child.id, "running")
            repository.transition(parent.id, child.id, "completed", result_text="x" * 5000)

    async def scenario():
        executor = Executor()
        coordinator, arguments = setup(repository, parent, executor)
        child = await coordinator.invoke(parent.id, "call", "spawn_agent", arguments)
        replay = await coordinator.invoke(parent.id, "call", "spawn_agent", arguments)
        assert child["childId"] == replay["childId"] and replay["replayed"]
        await coordinator.invoke(parent.id, "wait", "wait_agents", {"childIds": [child["childId"]]})
        result = await coordinator.invoke(parent.id, "result", "get_agent_result", {"childId": child["childId"], "offset": 0})
        assert result["status"] == "completed" and len(result["text"]) == 4000
        assert result["nextOffset"] == 4000 and executor.calls == 1
        await coordinator.settle(parent.id)
        await coordinator.close()
    asyncio.run(scenario())


def test_parent_cancel_waits_for_executor_cleanup(stores):
    repository, _, parent, _ = stores

    async def scenario():
        started, cleaned = asyncio.Event(), asyncio.Event()
        class Executor:
            async def execute(self, **inputs):
                repository.transition(parent.id, inputs["child"].id, "running")
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
        coordinator, arguments = setup(repository, parent, Executor())
        child = await coordinator.invoke(parent.id, "call", "spawn_agent", arguments)
        await started.wait()
        await coordinator.settle(parent.id, cancel=True)
        assert cleaned.is_set()
        assert repository.get(parent.id, child["childId"]).status == "cancelled"
        await coordinator.close()
    asyncio.run(scenario())


def test_spawn_cannot_override_model_or_permissions(stores):
    repository, _, parent, _ = stores
    async def scenario():
        coordinator, arguments = setup(repository, parent, object())
        with pytest.raises(AgentError, match="invalid_request"):
            await coordinator.invoke(parent.id, "call", "spawn_agent", {**arguments, "model": "override"})
        assert repository.list(parent.id) == ()
        await coordinator.close()
    asyncio.run(scenario())


def test_wait_does_not_block_cancel_and_release(stores):
    repository, _, parent, _ = stores
    async def scenario():
        started = asyncio.Event()
        class Executor:
            async def execute(self, **inputs):
                repository.transition(parent.id, inputs["child"].id, "running")
                started.set()
                await asyncio.Event().wait()
        coordinator, arguments = setup(repository, parent, Executor())
        child = await coordinator.invoke(parent.id, "call", "spawn_agent", arguments)
        await started.wait()
        waiting = asyncio.create_task(coordinator.invoke(parent.id, "wait", "wait_agents", {"childIds": [child["childId"]]}))
        await asyncio.sleep(0)
        cancelled = await asyncio.wait_for(coordinator.cancel_child(parent.id, child["childId"]), 2)
        assert cancelled.status == "cancelled"
        await asyncio.wait_for(waiting, 2)
        await asyncio.gather(coordinator.cancel_child(parent.id, child["childId"]), coordinator.release(parent.id))
        assert not coordinator._inputs and not coordinator._parents
        await coordinator.close()
    asyncio.run(scenario())


def test_pool_rejection_compensates_durable_child_and_close_rejects_create(stores):
    repository, _, parent, _ = stores
    async def scenario():
        coordinator, arguments = setup(repository, parent, object())
        await coordinator._pool.close()
        with pytest.raises(AgentError, match="pool_closed"):
            await coordinator.invoke(parent.id, "call", "spawn_agent", arguments)
        assert repository.list(parent.id)[0].status == "cancelled"
        await coordinator.close()
        with pytest.raises(AgentError, match="agent_unavailable"):
            await coordinator.invoke(parent.id, "other", "spawn_agent", arguments)
        assert len(repository.list(parent.id)) == 1
        assert not coordinator._inputs and not coordinator._parents
    asyncio.run(scenario())


def test_observer_failure_is_safe_and_release_still_frees_memory(stores, monkeypatch):
    repository, _, parent, _ = stores
    async def scenario():
        class Executor:
            async def execute(self, **inputs):
                raise ValueError("private information")
        coordinator, arguments = setup(repository, parent, Executor())
        child = await coordinator.invoke(parent.id, "call", "spawn_agent", arguments)
        original = repository.transition
        def broken(*args, **kwargs):
            raise AgentError("store_unavailable")
        monkeypatch.setattr(repository, "transition", broken)
        with pytest.raises(AgentError, match="store_unavailable"):
            await coordinator.settle(parent.id)
        monkeypatch.setattr(repository, "transition", original)
        await coordinator.release(parent.id)
        assert repository.get(parent.id, child["childId"]).status == "cancelled"
        assert not coordinator._parents and not coordinator._inputs and not coordinator._watchers
        await coordinator.close()
    asyncio.run(scenario())
