"""Tests for the module-owned skill-review use case."""

import asyncio
import json

from opensprite.core.contracts.persistence import StoredMessage
from opensprite.core.contracts.tool_names import SKILL_REVIEW_TOOL_NAMES
from opensprite.modules.documents.skill_review import SkillReviewService
from opensprite.modules.tools.registry import ToolRegistry
from opensprite.core.contracts.tool_results import classify_tool_result_status


def test_skill_review_tool_registry_contains_only_required_tools():
    class NamedTool:
        def __init__(self, name):
            self.name = name

    class Storage:
        async def get_messages(self, session_id, limit=None):
            return []

    async def execute_messages(*_args, **_kwargs):
        return None

    registry = ToolRegistry()
    for tool_name in (*SKILL_REVIEW_TOOL_NAMES, "extra_tool"):
        registry.register(NamedTool(tool_name))

    service = SkillReviewService(
        storage=Storage(),
        tools=registry,
        tool_result_succeeded=lambda _result: True,
        transcript_message_limit_getter=lambda: 10,
        max_tool_iterations_getter=lambda: 2,
        build_system_prompt=lambda _session_id: "system",
        execute_messages=execute_messages,
    )

    restricted = service.tool_registry()

    assert restricted is not None
    assert set(restricted.tool_names) == SKILL_REVIEW_TOOL_NAMES


def test_skill_review_collects_configured_skill_metadata():
    class Storage:
        async def get_messages(self, session_id, limit=None):
            return [
                StoredMessage(role="user", content="Please remember this workflow and make a skill.", timestamp=1.0),
                StoredMessage(role="assistant", content="Sure, I will save it.", timestamp=2.0),
            ]

    async def execute_messages(log_id, messages, **kwargs):
        await kwargs["on_tool_after_execute"](
            "configure_skill",
            {
                "action": "upsert",
                "skill_name": "pytest-helper",
                "description": "Reusable pytest workflow.",
            },
            "Updated skill 'pytest-helper'.",
        )

    service = SkillReviewService(
        storage=Storage(),
        tools=ToolRegistry(),
        tool_result_succeeded=lambda result: classify_tool_result_status(result).ok,
        transcript_message_limit_getter=lambda: 10,
        max_tool_iterations_getter=lambda: 2,
        build_system_prompt=lambda session_id: "system",
        execute_messages=execute_messages,
    )

    touched = asyncio.run(service.run("chat-a", tool_registry=ToolRegistry()))

    assert touched == [
        {
            "skill_name": "pytest-helper",
            "action": "upsert",
            "description": "Reusable pytest workflow.",
        }
    ]


def test_skill_review_ignores_structured_configure_skill_failure():
    class Storage:
        async def get_messages(self, session_id, limit=None):
            return [
                StoredMessage(role="user", content="Please remember this workflow and make a skill.", timestamp=1.0),
                StoredMessage(role="assistant", content="Sure, I will save it.", timestamp=2.0),
            ]

    async def execute_messages(log_id, messages, **kwargs):
        await kwargs["on_tool_after_execute"](
            "configure_skill",
            {
                "action": "upsert",
                "skill_name": "pytest-helper",
                "description": "Reusable pytest workflow.",
            },
            json.dumps({"ok": False, "error": "skill body was invalid"}),
        )

    service = SkillReviewService(
        storage=Storage(),
        tools=ToolRegistry(),
        tool_result_succeeded=lambda result: classify_tool_result_status(result).ok,
        transcript_message_limit_getter=lambda: 10,
        max_tool_iterations_getter=lambda: 2,
        build_system_prompt=lambda session_id: "system",
        execute_messages=execute_messages,
    )

    touched = asyncio.run(service.run("chat-a", tool_registry=ToolRegistry()))

    assert touched == []
