import asyncio
import json

import pytest

from opensprite.agent.task.decision import InitialTaskPlanningError, LLM_TASK_INTENT_METHOD, TurnTaskPlanningService
from opensprite.agent.task.progress import WorkProgressService
from opensprite.bus.message import UserMessage
from opensprite.config import Config
from opensprite.llms.base import LLMResponse


def test_turn_task_planning_builds_intent_context_and_initial_work_state():
    runtime_messages: list[tuple[str, dict | None]] = []
    provider = _JsonProvider(
        {
            "task_intent": {
                "kind": "task",
                "objective": "Please refactor the agent and run tests.",
                "constraints": [],
                "done_criteria": ["agent is refactored", "tests pass"],
                "needs_clarification": False,
                "long_running": False,
                "expects_code_change": True,
                "expects_verification": True,
                "verification_hint": "run focused tests",
            },
            "task_context": {
                "is_follow_up": False,
                "should_inherit_active_task": False,
                "should_seed_active_task": True,
                "should_replace_active_task": False,
                "inherited_task_type": None,
                "inherited_tool_group": None,
                "continuation_type": "new_task",
                "confidence": 0.86,
                "reason": "The user asks for new code work.",
            },
            "confidence": 0.9,
            "reason": "The request is a coding task.",
        }
    )
    service = TurnTaskPlanningService(
        work_progress=WorkProgressService(),
        read_active_task_snapshot=lambda session_id: "",
        build_runtime_message=lambda message, metadata: _record_runtime_message(
            runtime_messages,
            message,
            metadata,
        ),
        llm_config=Config.load_agent_template_config().task_context_llm,
    )

    result = asyncio.run(
        service.plan(
            user_message=UserMessage(
                text="Please refactor the agent and run tests.",
                metadata={"source": "cli_via_web"},
            ),
            session_id="web:browser-1",
            user_metadata={"source": "cli_via_web"},
            existing_work_state=None,
            provider=provider,
            model=provider.get_default_model(),
        )
    )

    assert runtime_messages == [("Please refactor the agent and run tests.", {"source": "cli_via_web"})]
    assert result.task_intent.objective == "Please refactor the agent and run tests."
    assert result.task_intent.kind == "task"
    assert result.task_intent_method == LLM_TASK_INTENT_METHOD
    assert result.task_context_decision.method == "llm"
    assert result.work_plan is not None
    assert result.current_work_state is not None
    assert result.current_work_state.objective == result.task_intent.objective
    prompt = str(provider.calls[0]["messages"][-1].content)
    assert "deterministic_intent" not in prompt
    assert "deterministic_context" not in prompt


def test_turn_task_planning_uses_llm_initial_decision_when_available():
    provider = _JsonProvider(
        {
            "task_intent": {
                "kind": "analysis",
                "objective": "Inspect the task flow and explain the current routing.",
                "constraints": ["do not edit files"],
                "done_criteria": ["task flow is explained"],
                "needs_clarification": False,
                "long_running": False,
                "expects_code_change": False,
                "expects_verification": False,
            },
            "task_context": {
                "is_follow_up": False,
                "should_inherit_active_task": False,
                "should_seed_active_task": True,
                "should_replace_active_task": False,
                "inherited_task_type": None,
                "inherited_tool_group": None,
                "continuation_type": "new_task",
                "confidence": 0.82,
                "reason": "The user asks for a new analysis of the task flow.",
            },
            "confidence": 0.84,
            "reason": "The request is an analysis task.",
        }
    )
    service = TurnTaskPlanningService(
        work_progress=WorkProgressService(),
        read_active_task_snapshot=lambda session_id: "",
        build_runtime_message=lambda message, metadata: message,
        llm_config=Config.load_agent_template_config().task_context_llm,
    )

    result = asyncio.run(
        service.plan(
            user_message=UserMessage(text="Inspect the task flow without editing files."),
            session_id="web:browser-1",
            user_metadata={},
            existing_work_state=None,
            provider=provider,
            model=provider.get_default_model(),
        )
    )

    assert len(provider.calls) == 1
    assert result.task_intent_method == LLM_TASK_INTENT_METHOD
    assert result.task_intent.kind == "analysis"
    assert result.task_intent.objective == "Inspect the task flow and explain the current routing."
    assert result.task_intent.constraints == ("do not edit files",)
    assert result.task_context_decision.method == "llm"
    assert result.task_context_decision.continuation_type == "new_task"
    assert result.task_intent_confidence == 0.84


def test_turn_task_planning_raises_without_configured_llm():
    service = TurnTaskPlanningService(
        work_progress=WorkProgressService(),
        read_active_task_snapshot=lambda session_id: "",
        build_runtime_message=lambda message, metadata: message,
        llm_config=Config.load_agent_template_config().task_context_llm,
    )

    with pytest.raises(InitialTaskPlanningError, match="requires a configured LLM provider"):
        asyncio.run(
            service.plan(
                user_message=UserMessage(text="Please summarize the current task flow."),
                session_id="web:browser-1",
                user_metadata={},
                existing_work_state=None,
                provider=None,
                model=None,
            )
        )


def test_turn_task_planning_raises_when_llm_returns_non_json():
    provider = _TextProvider("not json")
    service = TurnTaskPlanningService(
        work_progress=WorkProgressService(),
        read_active_task_snapshot=lambda session_id: "",
        build_runtime_message=lambda message, metadata: message,
        llm_config=Config.load_agent_template_config().task_context_llm,
    )

    with pytest.raises(InitialTaskPlanningError, match="valid JSON"):
        asyncio.run(
            service.plan(
                user_message=UserMessage(text="Please summarize the current task flow."),
                session_id="web:browser-1",
                user_metadata={},
                existing_work_state=None,
                provider=provider,
                model=provider.get_default_model(),
            )
        )

    assert len(provider.calls) == 1


def test_turn_task_planning_raises_when_llm_omits_required_fields():
    provider = _JsonProvider(
        {
            "task_intent": {
                "kind": "task",
                "objective": "Please summarize the current task flow.",
            },
            "task_context": {
                "continuation_type": "new_task",
                "confidence": 0.8,
            },
            "confidence": 0.8,
        }
    )
    service = TurnTaskPlanningService(
        work_progress=WorkProgressService(),
        read_active_task_snapshot=lambda session_id: "",
        build_runtime_message=lambda message, metadata: message,
        llm_config=Config.load_agent_template_config().task_context_llm,
    )

    with pytest.raises(InitialTaskPlanningError, match="task_intent.done_criteria"):
        asyncio.run(
            service.plan(
                user_message=UserMessage(text="Please summarize the current task flow."),
                session_id="web:browser-1",
                user_metadata={},
                existing_work_state=None,
                provider=provider,
                model=provider.get_default_model(),
            )
        )


class _JsonProvider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools, "model": model, **kwargs})
        return LLMResponse(content=json.dumps(self.payload), model=model or "fake-model")

    def get_default_model(self) -> str:
        return "fake-model"


class _TextProvider:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools, "model": model, **kwargs})
        return LLMResponse(content=self.content, model=model or "fake-model")

    def get_default_model(self) -> str:
        return "fake-model"


def _record_runtime_message(
    calls: list[tuple[str, dict | None]],
    message: str,
    metadata: dict | None,
) -> str:
    calls.append((message, metadata))
    return f"{message}\n\n[Runtime context]\n- test"
