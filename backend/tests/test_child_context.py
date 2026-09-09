import asyncio
from contextlib import closing
import sqlite3
import pytest

from context_test_support import TestCapabilityResolver
from test_child_repository import stores, create
from test_agent_loop import ScriptedGateway
from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.custom_agents.child_context import ChildContextRepository
from opensprite_backend.inference.models import ModelTextDelta, ModelCompleted, ModelFinishReason
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.conversations.repository import ConversationStoreError


def test_child_runs_existing_loop_without_reading_or_writing_parent_messages(stores):
    repository, _, parent, database = stores
    child, _ = create(repository, parent)
    context = ChildContextRepository(repository, child, parent, "delegated task only")
    gateway = ScriptedGateway([[ModelTextDelta("child answer"), ModelCompleted(ModelFinishReason.FINAL)]])
    loop = AgentLoop(repository=context, gateway=gateway, tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
                     capability_resolver=TestCapabilityResolver(), allow_tool_approval=False)
    result = asyncio.run(loop.execute(child.id, asyncio.Event()))
    assert result.status == RunStatus.COMPLETED
    assert repository.get(parent.id, child.id).result_text == "child answer"
    user_messages = [message.content for message in gateway.requests[0].messages if message.role == "user"]
    assert user_messages == ["delegated task only"]
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT content FROM messages").fetchall() == [("parent",)]
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM agent_execution_events").fetchone()[0] >= 1


def test_child_continuation_reuses_its_isolated_context(stores):
    repository, _, parent, _ = stores
    child, _ = create(repository, parent)
    context = ChildContextRepository(repository, child, parent, "continue the delegated task")
    gateway = ScriptedGateway([
        [ModelTextDelta("first "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
        [ModelTextDelta("second"), ModelCompleted(ModelFinishReason.FINAL)],
    ])
    loop = AgentLoop(repository=context, gateway=gateway, tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
                     capability_resolver=TestCapabilityResolver(), allow_tool_approval=False)
    result = asyncio.run(loop.execute(child.id, asyncio.Event()))
    assert result.status == RunStatus.COMPLETED
    assert repository.get(parent.id, child.id).result_text == "first second"
    assert len(gateway.requests) == 2


def test_terminal_child_cannot_start_again(stores):
    repository, _, parent, _ = stores
    child, _ = create(repository, parent)
    context = ChildContextRepository(repository, child, parent, "task")
    repository.transition(parent.id, child.id, "cancelled")
    with pytest.raises(ConversationStoreError):
        context.mark_run_started(child.id)
    assert context.get_run(child.id).status == RunStatus.QUEUED
    assert repository.get(parent.id, child.id).status == "cancelled"
