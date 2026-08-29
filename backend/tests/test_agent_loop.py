"""Behavior tests for the one-path bounded structured-tool Agent loop."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from uuid import uuid4

import pytest

from context_test_support import TestCapabilityResolver

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.conversations.sqlite_repository import (
    SqliteConversationRepository,
)
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import (
    InferenceFailure,
    ModelCompleted,
    ModelFinishReason,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCall,
    ModelUsage,
)
from opensprite_backend.tools.definition import (
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
)
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolRegistry


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class ScriptedGateway:
    def __init__(
        self,
        scripts: list[list[ModelStreamEvent | Exception]],
    ) -> None:
        self.scripts = deque(scripts)
        self.requests: list[ModelRequest] = []

    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelStreamEvent]:
        self.requests.append(request)
        script = self.scripts.popleft()
        for item in script:
            if isinstance(item, Exception):
                raise item
            yield item


class RecordingSystemPromptProvider:
    def __init__(self, content: str = "dynamic system prompt") -> None:
        self.content = content
        self.run_ids: list[str] = []

    async def build(self, *, run_id: str) -> str:
        self.run_ids.append(run_id)
        return self.content


class FailingSystemPromptProvider:
    async def build(self, *, run_id: str) -> str:
        del run_id
        raise RuntimeError("prompt log failed")


@dataclass
class LookupTool:
    definition: ToolDefinition = field(
        default_factory=lambda: ToolDefinition(
            name="lookup_note",
            description="Look up a local note.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 50}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            effect=ToolEffect.READ_ONLY,
            timeout_seconds=1,
            max_output_chars=1024,
        )
    )
    calls: list[dict[str, object]] = field(default_factory=list)

    async def invoke(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult:
        del context
        self.calls.append(arguments)
        return ToolResult(content="今天有 3 項工作", summary="找到 3 項工作")


def store(tmp_path: Path) -> SqliteConversationRepository:
    return SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file
    )


def accepted_run(repository: SqliteConversationRepository):
    return repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="整理今天的工作",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run


def seed_completed_turns(
    repository: SqliteConversationRepository,
    count: int,
    *,
    assistant_size: int,
) -> str:
    conversation_id: str | None = None
    for index in range(count):
        accepted = repository.start_run(
            conversation_id=conversation_id,
            client_request_id=str(uuid4()),
            message=f"seed {index}",
            provider_id="openrouter",
            model_id="openrouter/auto",
            response_mode="default",
            context_budget="auto",
        )
        conversation_id = accepted.conversation.id
        repository.mark_run_started(accepted.run.id)
        repository.complete_run(accepted.run.id, "x" * assistant_size)
    assert conversation_id is not None
    return conversation_id


@async_test
async def test_final_text_uses_one_agent_path_and_persists_visible_answer(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [
            [
                ModelTextDelta("整理完成"),
                ModelCompleted(ModelFinishReason.FINAL),
            ]
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "整理完成"
    messages = repository.list_messages(
        run.conversation_id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content) for item in messages.items] == [
        ("user", "整理今天的工作"),
        ("assistant", "整理完成"),
    ]
    assert [message.role for message in gateway.requests[0].messages] == [
        "system",
        "user",
    ]
    assert gateway.requests[0].tools == ()
    assert [
        event.type
        for event in repository.list_run_events(
            run.id,
            after_sequence=0,
            limit=100,
        )
    ] == [
        RunEventType.RUN_STARTED,
        RunEventType.MODEL_STARTED,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.RUN_COMPLETED,
    ]


@async_test
async def test_structured_tool_call_returns_to_same_loop_before_final_answer(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    tool = LookupTool()
    prompt_provider = RecordingSystemPromptProvider()
    gateway = ScriptedGateway(
        [
            [
                ModelTextDelta("我先查詢。"),
                ModelToolCall("call-1", "lookup_note", {"query": "today"}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
            [
                ModelTextDelta("今天共有 3 項工作。"),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([tool], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
        system_prompt_provider=prompt_provider,
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "我先查詢。今天共有 3 項工作。"
    assert tool.calls == [{"query": "today"}]
    assert prompt_provider.run_ids == [run.id]
    assert [request.messages[0].content for request in gateway.requests] == [
        "dynamic system prompt",
        "dynamic system prompt",
    ]
    second_roles = [message.role for message in gateway.requests[1].messages]
    assert second_roles == ["system", "user", "assistant", "tool"]
    assistant = gateway.requests[1].messages[-2]
    assert assistant.tool_calls[0].name == "lookup_note"
    tool_result = gateway.requests[1].messages[-1]
    assert tool_result.tool_call_id == "call-1"
    assert tool_result.content == "今天有 3 項工作"
    events = repository.list_run_events(run.id, after_sequence=0, limit=100)
    assert [event.type for event in events] == [
        RunEventType.RUN_STARTED,
        RunEventType.MODEL_STARTED,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.TOOL_STARTED,
        RunEventType.TOOL_COMPLETED,
        RunEventType.MODEL_STARTED,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.RUN_COMPLETED,
    ]
    assert events[4].data == {
        "callId": "call-1",
        "toolName": "lookup_note",
        "summary": "找到 3 項工作",
    }
    database_bytes = repository.database_file.read_bytes()
    assert b'"query"' not in database_bytes
    assert b'"today"' not in database_bytes


@async_test
async def test_repeated_identical_tool_failure_stops_bounded_loop(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [
            [
                ModelToolCall("call-1", "missing_tool", {"query": "today"}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
            [
                ModelToolCall("call-2", "missing_tool", {"query": "today"}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "agent_limit_reached"
    assert len(gateway.requests) == 2
    assert [
        event.type
        for event in repository.list_run_events(
            run.id,
            after_sequence=0,
            limit=100,
        )
    ].count(RunEventType.TOOL_FAILED) == 2


@async_test
async def test_model_round_limit_stops_infinite_tool_loop(tmp_path: Path) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [
            [
                ModelToolCall("call-1", "missing_one", {}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
            [
                ModelToolCall("call-2", "missing_two", {}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
        max_model_rounds=2,
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "agent_limit_reached"


@async_test
async def test_assistant_output_limit_fails_run_before_repository_overflow(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)

    class OversizedGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            yield ModelTextDelta("1234")
            yield ModelTextDelta("56")
            yield ModelCompleted(ModelFinishReason.FINAL)

    result = await AgentLoop(
        repository=repository,
        gateway=OversizedGateway(),
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
        max_assistant_chars=5,
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "agent_limit_reached"


@async_test
async def test_provider_failure_maps_to_safe_run_error(tmp_path: Path) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [[ModelGatewayError(InferenceFailure.PROVIDER_TIMEOUT)]]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "provider_timeout"
    assert result.error.retryable is True
    assert "private" not in result.error.message.lower()


@async_test
async def test_long_history_is_compacted_without_deleting_raw_messages(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(
        repository,
        14,
        assistant_size=30_000,
    )
    current = repository.start_run(
        conversation_id=conversation_id,
        client_request_id=str(uuid4()),
        message="current request",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget="auto",
    ).run
    gateway = ScriptedGateway(
        [
            [
                ModelTextDelta(
                    "Goals and constraints\nKeep context.\nDecisions\nNone.\n"
                    "Facts and artifacts\nNone.\nOpen questions\nNone.\n"
                    "Next actions\nAnswer the current request."
                ),
                ModelUsage(80_000, 60),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
            [
                ModelTextDelta("final answer"),
                ModelUsage(61_000, 3),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(current.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "final answer"
    assert len(gateway.requests) == 2
    assert gateway.requests[0].max_output_tokens == 2_048
    assert gateway.requests[1].max_output_tokens == 8_192
    assert any(
        message.content.startswith("Earlier conversation summary")
        for message in gateway.requests[1].messages
    )
    compaction = repository.get_latest_compaction(conversation_id)
    assert compaction is not None
    assert compaction.covers_through_sequence < 18
    assert len(
        repository.list_messages(
            conversation_id,
            limit=100,
            before_sequence=None,
        ).items
    ) == 30


@async_test
async def test_required_recent_history_overflow_fails_without_model_request(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(
        repository,
        6,
        assistant_size=30_000,
    )
    current = repository.start_run(
        conversation_id=conversation_id,
        client_request_id=str(uuid4()),
        message="current request",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget="auto",
    ).run
    gateway = ScriptedGateway([])
    result = await AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(32_768),
    ).execute(current.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "context_limit_exceeded"
    assert gateway.requests == []


@async_test
async def test_first_request_context_rejection_compacts_once_and_retries(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(repository, 7, assistant_size=20)
    current = repository.start_run(
        conversation_id=conversation_id,
        client_request_id=str(uuid4()),
        message="current request",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget="auto",
    ).run
    gateway = ScriptedGateway(
        [
            [ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)],
            [
                ModelTextDelta(
                    "Goals and constraints\nKeep context.\nDecisions\nNone.\n"
                    "Facts and artifacts\nNone.\nOpen questions\nNone.\n"
                    "Next actions\nAnswer the current request."
                ),
                ModelUsage(100, 40),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
            [
                ModelTextDelta("final answer"),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
        max_model_rounds=1,
    ).execute(current.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "final answer"
    assert len(gateway.requests) == 3
    assert gateway.requests[1].max_output_tokens == 2_048
    assert repository.get_latest_compaction(conversation_id) is not None
    visible = repository.list_messages(
        conversation_id,
        limit=100,
        before_sequence=None,
    ).items
    assert [message.content for message in visible].count("final answer") == 1


@async_test
async def test_context_rejection_after_partial_output_is_not_retried(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [[
            ModelTextDelta("partial"),
            ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED),
        ]]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "context_limit_exceeded"
    assert result.partial_text == "partial"
    assert len(gateway.requests) == 1


@async_test
async def test_second_context_rejection_stops_after_one_compaction_retry(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(repository, 7, assistant_size=20)
    current = repository.start_run(
        conversation_id=conversation_id,
        client_request_id=str(uuid4()),
        message="current request",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget="auto",
    ).run
    gateway = ScriptedGateway(
        [
            [ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)],
            [
                ModelTextDelta(
                    "Goals and constraints\nKeep context.\nDecisions\nNone.\n"
                    "Facts and artifacts\nNone.\nOpen questions\nNone.\n"
                    "Next actions\nAnswer the current request."
                ),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
            [ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)],
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    ).execute(current.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "context_limit_exceeded"
    assert len(gateway.requests) == 3


@async_test
async def test_prompt_log_failure_stops_before_any_model_request(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [[ModelTextDelta("must not run"), ModelCompleted(ModelFinishReason.FINAL)]]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
        system_prompt_provider=FailingSystemPromptProvider(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "internal_error"
    assert gateway.requests == []


@async_test
async def test_cancellation_interrupts_a_blocked_model_stream(tmp_path: Path) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    entered = asyncio.Event()

    class BlockingGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            entered.set()
            await asyncio.Event().wait()
            if False:
                yield ModelCompleted(ModelFinishReason.FINAL)

    loop = AgentLoop(
        repository=repository,
        gateway=BlockingGateway(),
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=TestCapabilityResolver(),
    )
    cancellation = asyncio.Event()
    task = asyncio.create_task(loop.execute(run.id, cancellation))
    await asyncio.wait_for(entered.wait(), timeout=1)

    cancellation.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result.status is RunStatus.CANCELLED
    assert repository.list_run_events(run.id, after_sequence=0, limit=100)[
        -1
    ].type is RunEventType.RUN_CANCELLED


@async_test
async def test_cancellation_interrupts_context_compaction_request(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(
        repository,
        14,
        assistant_size=30_000,
    )
    run = repository.start_run(
        conversation_id=conversation_id,
        client_request_id=str(uuid4()),
        message="current request",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget="auto",
    ).run
    entered = asyncio.Event()

    class BlockingSummaryGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            assert request.max_output_tokens == 2_048
            entered.set()
            await asyncio.Event().wait()
            if False:
                yield ModelCompleted(ModelFinishReason.FINAL)

    cancellation = asyncio.Event()
    task = asyncio.create_task(
        AgentLoop(
            repository=repository,
            gateway=BlockingSummaryGateway(),
            tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
            capability_resolver=TestCapabilityResolver(),
        ).execute(run.id, cancellation)
    )
    await asyncio.wait_for(entered.wait(), timeout=1)

    cancellation.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result.status is RunStatus.CANCELLED
    assert repository.get_latest_compaction(conversation_id) is None
