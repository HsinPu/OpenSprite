"""Composition-boundary tests for isolated custom Agent child execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from context_test_support import TestCapabilityResolver
from test_agent_loop import ScriptedGateway
from test_child_repository import create, stores

from opensprite_backend.custom_agents.child_executor import ChildAgentExecutor
from opensprite_backend.custom_agents.definition import AgentDefinition
from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta, ModelToolCall
from opensprite_backend.skills.models import SkillContent, SkillExecutionSnapshot
from opensprite_backend.tools.availability import ToolAvailabilitySnapshot
from opensprite_backend.tools.definition import ToolContext, ToolDefinition, ToolEffect, ToolResult
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.workspaces import DEFAULT_WORKSPACE_ID, DefaultWorkspaceResolver


def definition() -> AgentDefinition:
    return AgentDefinition(
        name="reviewer",
        description="Review delegated work.",
        developer_instructions="Check the result and report concrete findings.",
        content_hash="a" * 64,
    )


def workspace():
    return DefaultWorkspaceResolver().execution_context(DEFAULT_WORKSPACE_ID)


def run_executor(
    stores,
    *,
    gateway,
    tools,
    availability,
    skills=None,
    task="child task only",
):
    repository, _, parent, _ = stores
    child, replayed = create(repository, parent)
    assert not replayed
    executor = ChildAgentExecutor(
        gateway,
        TestCapabilityResolver(),
        repository,
    )
    result = asyncio.run(
        executor.execute(
            child=child,
            parent=parent,
            workspace=workspace(),
            skills=skills or SkillExecutionSnapshot(),
            definition=definition(),
            task=task,
            tools=tools,
            availability=availability,
            base_system_prompt="base system prompt",
            cancellation_event=asyncio.Event(),
        )
    )
    return repository, parent, child, result


def test_child_has_its_own_task_and_role_json_without_parent_history(stores):
    skill = SkillContent(
        "00000000-0000-4000-8000-000000000001",
        "global",
        "Review",
        "Review source changes.",
        1,
        "b" * 64,
        "UNIQUE_FULL_SKILL_INSTRUCTIONS",
    )
    skills = SkillExecutionSnapshot((skill,), (skill.id,))
    gateway = ScriptedGateway(
        [[ModelTextDelta("child answer"), ModelCompleted(ModelFinishReason.FINAL)]]
    )
    repository, parent, child, result = run_executor(
        stores,
        gateway=gateway,
        tools=ToolRegistry((), policy=ReadOnlyToolPolicy()),
        availability=ToolAvailabilitySnapshot(frozenset()),
        skills=skills,
    )

    assert result.status.value == "completed"
    assert repository.get(parent.id, child.id).result_text == "child answer"
    request = gateway.requests[0]
    user_messages = [message.content for message in request.messages if message.role == "user"]
    assert user_messages == ["child task only"]
    assert "parent" not in str(request.messages)
    system = next(message.content for message in request.messages if message.role == "system")
    assert '<child_agent_role>\n{"name":"reviewer"' in system
    assert "developer_instructions" in system
    assert "Check the result" in system
    assert "UNIQUE_FULL_SKILL_INSTRUCTIONS" not in system
    assert '"loadedSkills": []' in system
    assert {tool.name for tool in request.tools} == {"discover_skills", "load_skill"}
    assert "discover_agents" not in {tool.name for tool in request.tools}
    assert "spawn_agent" not in {tool.name for tool in request.tools}


@dataclass
class WriteTool:
    definition: ToolDefinition = field(
        default_factory=lambda: ToolDefinition(
            name="write_note",
            description="Write a note.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 40}},
                "required": ["text"],
                "additionalProperties": False,
            },
            effect=ToolEffect.LOCAL_WRITE,
        )
    )
    calls: list[dict[str, object]] = field(default_factory=list)

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        self.calls.append(arguments)
        return ToolResult("written", "written")


def test_child_never_requests_approval_for_a_consequential_tool(stores):
    tool = WriteTool()
    gateway = ScriptedGateway(
        [[
            ModelToolCall("write", "write_note", {"text": "unsafe"}),
            ModelCompleted(ModelFinishReason.TOOL_CALLS),
        ]]
    )
    repository, parent, child, result = run_executor(
        stores,
        gateway=gateway,
        tools=ToolRegistry([tool], policy=ReadOnlyToolPolicy()),
        availability=ToolAvailabilitySnapshot(frozenset({"write_note"})),
    )

    assert result.status.value == "failed"
    assert result.error is not None
    assert result.error.code == "subagent_tool_approval_required"
    assert tool.calls == []
    assert repository.get(parent.id, child.id).error_code == "subagent_tool_approval_required"


@dataclass
class WorkspaceProbeTool:
    definition: ToolDefinition = field(
        default_factory=lambda: ToolDefinition(
            name="probe_workspace",
            description="Record the execution workspace.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            effect=ToolEffect.READ_ONLY,
        )
    )
    seen: list[object] = field(default_factory=list)

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        del arguments
        self.seen.append(context.workspace)
        return ToolResult("ok", "ok")


def test_child_passes_the_exact_workspace_snapshot_to_tools(stores):
    tool = WorkspaceProbeTool()
    gateway = ScriptedGateway(
        [
            [
                ModelToolCall("probe", "probe_workspace", {}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
            [ModelTextDelta("done"), ModelCompleted(ModelFinishReason.FINAL)],
        ]
    )
    # run_executor creates the object internally, so use an explicit executor
    # invocation here to assert object identity rather than value equality.
    repository, _, parent, _ = stores
    child, _ = create(repository, parent)
    fixed_workspace = workspace()
    result = asyncio.run(
        ChildAgentExecutor(gateway, TestCapabilityResolver(), repository).execute(
            child=child,
            parent=parent,
            workspace=fixed_workspace,
            skills=SkillExecutionSnapshot(),
            definition=definition(),
            task="inspect workspace",
            tools=ToolRegistry([tool], policy=ReadOnlyToolPolicy()),
            availability=ToolAvailabilitySnapshot(frozenset({"probe_workspace"})),
            base_system_prompt="base",
            cancellation_event=asyncio.Event(),
        )
    )
    assert result.status.value == "completed"
    assert tool.seen == [fixed_workspace]
