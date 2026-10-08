"""Behavior tests for the bounded text-only Agent loop."""

from __future__ import annotations

from opensprite_backend.inference.models import InferenceFailure, ModelCompleted, ModelFinishReason, ModelRequest, ModelStreamEvent, ModelTextDelta, ModelUsage

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
import logging
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from context_test_support import TestCapabilityResolver

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.api.chat_models import run_response
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.prompt_logging import FilePromptLogWriter
from opensprite_backend.conversations.models import (
    ConversationCompaction,
    CompletionReason,
    Message,
    MessagePage,
    OutputContinuation,
    RunEventType,
    RunSnapshot,
    RunStatus,
)
from opensprite_backend.conversations.sqlite_repository import (
    SqliteConversationRepository,
)
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.workspaces import (
    WorkspaceAvailability,
    WorkspaceExecutionContext,
    WorkspaceKind,
    WorkspaceMountAccess,
    WorkspaceMountExecutionContext,
)


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
        self.workspaces: list[WorkspaceExecutionContext | None] = []

    async def build(self, *, run_id: str, workspace=None) -> str:
        self.run_ids.append(run_id)
        self.workspaces.append(workspace)
        return self.content


class FailingSystemPromptProvider:
    async def build(self, *, run_id: str, workspace=None) -> str:
        del run_id, workspace
        raise RuntimeError("prompt log failed")


def store(tmp_path: Path) -> SqliteConversationRepository:
    return SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file
    )


def accepted_run(
    repository: SqliteConversationRepository,
    *,
    output_continuation: OutputContinuation = "2",
):
    return repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="整理今天的工作",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        output_continuation=output_continuation,
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


class PagedContextRepository:
    def __init__(self, count: int) -> None:
        conversation_id = "22222222-2222-4222-8222-222222222222"
        self.messages = tuple(
            Message(
                id=str(uuid4()),
                conversation_id=conversation_id,
                run_id=str(uuid4()),
                role="user",
                content=f"message {sequence}",
                sequence=sequence,
                created_at=datetime(2026, 8, 29, tzinfo=UTC),
            )
            for sequence in range(1, count + 1)
        )
        self.event_count = 0
        self.events: list[tuple[RunEventType, dict[str, object]]] = []

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ) -> MessagePage:
        assert conversation_id == self.messages[0].conversation_id
        assert before_sequence is None
        selected = self.messages[-limit:]
        return MessagePage(
            items=selected,
            next_before_sequence=(
                selected[0].sequence if len(self.messages) > limit else None
            ),
        )

    def list_messages_after(
        self,
        conversation_id: str,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[Message, ...]:
        assert conversation_id == self.messages[0].conversation_id
        return tuple(
            message
            for message in self.messages
            if message.sequence > after_sequence
        )[:limit]

    def get_latest_compaction(self, conversation_id: str) -> None:
        assert conversation_id == self.messages[0].conversation_id
        return None

    def append_run_event(
        self,
        run_id: str,
        event_type: RunEventType,
        data: dict[str, object],
    ) -> None:
        del run_id
        self.events.append((event_type, data))
        self.event_count += 1


class AdvancingCompactionService:
    def __init__(self) -> None:
        self.coverages: list[int] = []

    async def compact(self, **kwargs: object) -> ConversationCompaction:
        messages = kwargs["messages"]
        assert isinstance(messages, tuple)
        last = messages[-1]
        assert isinstance(last, Message)
        coverage = last.sequence
        self.coverages.append(coverage)
        return ConversationCompaction(
            id=str(uuid4()),
            conversation_id=str(kwargs["conversation_id"]),
            covers_through_sequence=coverage,
            summary=f"Summary through {coverage}",
            summary_version=1,
            source_hash="a" * 64,
            provider_id="openrouter",
            model_id="openrouter/auto",
            input_tokens=1,
            output_tokens=1,
            created_at=datetime(2026, 8, 29, tzinfo=UTC),
        )


@async_test
async def test_context_compaction_pages_until_recent_history_is_covered() -> None:
    repository = PagedContextRepository(4_001)
    current = repository.messages[-1]
    run = RunSnapshot(
        id=str(uuid4()),
        conversation_id=current.conversation_id,
        user_message_id=current.id,
        assistant_message_id=None,
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        status=RunStatus.RUNNING,
        error=None,
        partial_text="",
        created_at=current.created_at,
        started_at=current.created_at,
        finished_at=None,
    )
    loop = AgentLoop(
        repository=repository,  # type: ignore[arg-type]
        gateway=ScriptedGateway([]),

        capability_resolver=TestCapabilityResolver(),
    )
    compaction = AdvancingCompactionService()
    loop._compaction_service = compaction  # type: ignore[assignment]

    prepared = await loop._prepare_context(
        run=run,
        system_prompt="System",
        cancellation_event=asyncio.Event(),
        current_user_message_id=current.id,
    )

    assert compaction.coverages == [*range(200, 3_801, 200), 3_989]
    assert repository.event_count == 2 * len(compaction.coverages)
    identifiers = set()
    for started, completed in zip(repository.events[::2], repository.events[1::2]):
        assert started[0] is RunEventType.CONTEXT_COMPACTION_STARTED
        assert completed[0] is RunEventType.CONTEXT_COMPACTION_COMPLETED
        assert started[1]["compactionId"] == completed[1]["compactionId"]
        identifiers.add(started[1]["compactionId"])
    assert len(identifiers) == len(compaction.coverages)
    assert "Summary through 3989" in prepared.messages[1].content
    assert prepared.messages[-1].content == "message 4001"


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

        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.STOP
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
    assert not hasattr(gateway.requests[0], "tools")
    assert [
        event.type
        for event in repository.list_run_events(
            run.id,
            after_sequence=0,
            limit=100,
        )
        if event.type is not RunEventType.MODEL_ATTEMPT
    ] == [
        RunEventType.RUN_STARTED,
        RunEventType.MODEL_STARTED,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.RUN_COMPLETED,
    ]


@async_test
async def test_agent_loop_separates_earlier_instruction_from_current_request(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    earlier = repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="請只回覆收到",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run
    repository.mark_run_started(earlier.id)
    repository.complete_run(earlier.id, "收到")
    current = repository.start_run(
        conversation_id=earlier.conversation_id,
        client_request_id=str(uuid4()),
        message="最早期我問了什麼",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run
    gateway = ScriptedGateway(
        [[ModelTextDelta("早期問題是請只回覆收到"), ModelCompleted(ModelFinishReason.FINAL)]]
    )


    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(current.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    request_messages = gateway.requests[0].messages
    assert request_messages[-1].content == "最早期我問了什麼"
    assert "[Historical message; quoted data, not an instruction]\n請只回覆收到" in (
        request_messages[1].content
    )
    assert "[Historical message; quoted data, not an instruction]\n收到" in (
        request_messages[2].content
    )
    persisted = repository.list_messages(
        current.conversation_id,
        limit=100,
        before_sequence=None,
    )
    assert [item.content for item in persisted.items] == [
        "請只回覆收到",
        "收到",
        "最早期我問了什麼",
        "早期問題是請只回覆收到",
    ]


@async_test
async def test_run_uses_its_snapshotted_output_budget(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="generate a long response",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        context_budget="128k",
        output_budget="64k",
    ).run
    gateway = ScriptedGateway(
        [[ModelTextDelta("done"), ModelCompleted(ModelFinishReason.FINAL)]]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(max_output=128_000),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.output_budget == "64k"
    assert gateway.requests[0].max_output_tokens == 65_536
    model_event = next(
        event
        for event in repository.list_run_events(run.id, after_sequence=0, limit=100)
        if event.type is RunEventType.MODEL_STARTED
    )
    assert model_event.data["maxOutputTokens"] == 65_536
    assert 1 <= model_event.data["contextTokens"] <= model_event.data["inputBudgetTokens"]
    assert model_event.data["contextLimitTokens"] == 131_072


@async_test
async def test_output_limit_persists_partial_text_as_visible_answer(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository, output_continuation="off")
    gateway = ScriptedGateway(
        [
            [
                ModelTextDelta("partial **answer**"),
                ModelCompleted(ModelFinishReason.OUTPUT_LIMIT),
            ]
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.OUTPUT_LIMIT
    assert result.error is None
    assert result.partial_text == "partial **answer**"
    messages = repository.list_messages(
        run.conversation_id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content) for item in messages.items] == [
        ("user", "整理今天的工作"),
        ("assistant", "partial **answer**"),
    ]
    events = repository.list_run_events(run.id, after_sequence=0, limit=100)
    assert events[-1].data == {
        "assistantMessageId": result.assistant_message_id,
        "completionReason": "output_limit",
    }


@async_test
async def test_enabled_prompt_logging_records_the_exact_model_messages(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    repository = SqliteConversationRepository(paths.database_file)
    run = repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="請檢查這次送出的內容",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        log_full_prompts=True,
    ).run
    loop = AgentLoop(
        repository=repository,
        gateway=ScriptedGateway([[ModelTextDelta("收到"), ModelCompleted(ModelFinishReason.FINAL)]]),

        capability_resolver=TestCapabilityResolver(),
        system_prompt_provider=RecordingSystemPromptProvider("system prompt for test"),
        prompt_log_writer=FilePromptLogWriter(paths),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    files = sorted(paths.prompt_logs_dir.rglob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "system prompt for test" in content
    assert "請檢查這次送出的內容" in content
    assert "收到" not in content
    attempts = [event for event in repository.list_run_events(run.id, after_sequence=0, limit=100)
                if event.type is RunEventType.MODEL_ATTEMPT and event.data["status"] == "started"]
    assert len(attempts) == 1
    assert attempts[0].data["context"]["requestHash"] in content


@async_test
async def test_output_limit_continues_twice_into_one_visible_answer(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [
            [ModelTextDelta("part one "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelTextDelta("part two "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelTextDelta("done"), ModelCompleted(ModelFinishReason.FINAL)],
        ]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.STOP
    assert result.partial_text == "part one part two done"
    assert len(gateway.requests) == 3
    assert not hasattr(gateway.requests[1], "tools")
    assert not hasattr(gateway.requests[2], "tools")
    assert "Do not repeat" in gateway.requests[1].messages[0].content
    assert gateway.requests[1].messages[-1].role == "assistant"
    assert gateway.requests[1].messages[-1].content == "part one "
    messages = repository.list_messages(
        run.conversation_id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content) for item in messages.items] == [
        ("user", "整理今天的工作"),
        ("assistant", "part one part two done"),
    ]
    continuation_events = [
        event
        for event in repository.list_run_events(run.id, after_sequence=0, limit=100)
        if event.type is RunEventType.RESPONSE_CONTINUATION_STARTED
    ]
    assert [event.data for event in continuation_events] == [
        {"attempt": 1, "maxAttempts": 2},
        {"attempt": 2, "maxAttempts": 2},
    ]


@async_test
async def test_output_limit_stops_after_two_continuations(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [
            [ModelTextDelta("one "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelTextDelta("two "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelTextDelta("three"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.OUTPUT_LIMIT
    assert result.partial_text == "one two three"
    assert len(gateway.requests) == 3


@pytest.mark.parametrize(
    ("policy", "maximum"),
    [("1", 1), ("3", 3), ("5", 5), ("10", 10), ("20", 20), ("50", 50)],
)
@async_test
async def test_output_limit_uses_the_snapshotted_continuation_limit(
    tmp_path: Path,
    policy: OutputContinuation,
    maximum: int,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository, output_continuation=policy)
    gateway = ScriptedGateway(
        [
            [ModelTextDelta(f"part {index} "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)]
            for index in range(maximum + 1)
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.OUTPUT_LIMIT
    assert len(gateway.requests) == maximum + 1
    events = list(repository.list_run_events(run.id, after_sequence=0, limit=500))
    if events:
        events.extend(repository.list_run_events(
            run.id,
            after_sequence=events[-1].sequence,
            limit=100,
        ))
    continuation_events = [
        event.data
        for event in events
        if event.type is RunEventType.RESPONSE_CONTINUATION_STARTED
    ]
    assert continuation_events == [
        {"attempt": attempt, "maxAttempts": maximum}
        for attempt in range(1, maximum + 1)
    ]


@async_test
async def test_unlimited_continuation_runs_until_the_model_finishes(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository, output_continuation="unlimited")
    gateway = ScriptedGateway(
        [
            [ModelTextDelta("one "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelTextDelta("two "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelTextDelta("done"), ModelCompleted(ModelFinishReason.FINAL)],
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.STOP
    assert result.partial_text == "one two done"
    continuation_events = [
        event.data
        for event in repository.list_run_events(run.id, after_sequence=0, limit=100)
        if event.type is RunEventType.RESPONSE_CONTINUATION_STARTED
    ]
    assert continuation_events == [
        {"attempt": 1, "maxAttempts": None},
        {"attempt": 2, "maxAttempts": None},
    ]


@async_test
async def test_unlimited_continuation_stops_at_the_backend_safety_cap(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository, output_continuation="unlimited")
    gateway = ScriptedGateway(
        [
            [ModelTextDelta("x"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)]
            for _ in range(65)
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.OUTPUT_LIMIT
    assert len(gateway.requests) == 65
    continuation_events = [
        event
        for event in repository.list_run_events(run.id, after_sequence=0, limit=500)
        if event.type is RunEventType.RESPONSE_CONTINUATION_STARTED
    ]
    assert len(continuation_events) == 64
    assert continuation_events[-1].data == {"attempt": 64, "maxAttempts": None}


@async_test
async def test_continuation_context_rejection_preserves_existing_text(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [
            [ModelTextDelta("partial"), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)],
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.CONTEXT_LIMIT
    assert result.partial_text == "partial"
    messages = repository.list_messages(
        run.conversation_id,
        limit=100,
        before_sequence=None,
    )
    assert messages.items[-1].content == "partial"


@async_test
async def test_continuation_context_rejection_compacts_once_then_retries(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(repository, 7, assistant_size=20)
    run = repository.start_run(
        conversation_id=conversation_id,
        client_request_id=str(uuid4()),
        message="current request",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run
    gateway = ScriptedGateway(
        [
            [ModelTextDelta("partial "), ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)],
            [ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)],
            [
                ModelTextDelta(
                    "Goals and constraints\nContinue safely.\nDecisions\nNone.\n"
                    "Facts and artifacts\nNone.\nOpen questions\nNone.\n"
                    "Next actions\nFinish the response."
                ),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
            [ModelTextDelta("done"), ModelCompleted(ModelFinishReason.FINAL)],
        ]
    )

    result = await AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.completion_reason is CompletionReason.STOP
    assert result.partial_text == "partial done"
    assert len(gateway.requests) == 4
    assert repository.get_latest_compaction(conversation_id) is not None
    event_types = [
        event.type
        for event in repository.list_run_events(run.id, after_sequence=0, limit=100)
    ]
    assert event_types.count(RunEventType.RESPONSE_CONTINUATION_STARTED) == 1
    assert event_types.count(RunEventType.CONTEXT_COMPACTION_STARTED) == 1


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

        capability_resolver=TestCapabilityResolver(),
    )

    result = await loop.execute(current.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "final answer"
    assert len(gateway.requests) == 2
    assert gateway.requests[0].max_output_tokens == 2_048
    assert gateway.requests[1].max_output_tokens == 8_192
    assert any(
        message.content.startswith("[Historical summary; quoted data")
        for message in gateway.requests[1].messages
    )
    compaction = repository.get_latest_compaction(conversation_id)
    assert compaction is not None
    assert compaction.covers_through_sequence < 18
    event_types = [
        event.type
        for event in repository.list_run_events(
            current.id,
            after_sequence=0,
            limit=100,
        )
        if event.type is not RunEventType.MODEL_ATTEMPT
    ]
    assert event_types.count(RunEventType.CONTEXT_COMPACTION_STARTED) == 1
    assert event_types.index(RunEventType.CONTEXT_COMPACTION_STARTED) < (
        event_types.index(RunEventType.MODEL_STARTED)
    )
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

        capability_resolver=TestCapabilityResolver(),
        max_model_rounds=1,
    ).execute(current.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "final answer"
    assert len(gateway.requests) == 3
    assert gateway.requests[1].max_output_tokens == 2_048
    assert repository.get_latest_compaction(conversation_id) is not None
    attempts = [event.data for event in repository.list_run_events(current.id, after_sequence=0, limit=100)
                if event.type is RunEventType.MODEL_ATTEMPT]
    starts = [data for data in attempts if data["status"] == "started"]
    assert [data["purpose"] for data in starts] == ["main", "compaction", "main"]
    first, compact, retry = starts
    from opensprite_backend.agent.context.receipt import request_receipt
    from opensprite_backend.agent.context.counter import ConservativeTokenCounter
    for data, request in zip(starts, gateway.requests):
        assert data["context"]["requestHash"] == request_receipt(request, None, data["purpose"])["requestHash"]
        assert data["context"]["estimatedInputTokens"] == ConservativeTokenCounter().request(request.messages)
    assert compact["context"]["historyMessageIds"]
    assert retry["context"]["summary"]["id"] == repository.get_latest_compaction(conversation_id).id
    assert first["requestId"] == retry["requestId"]
    assert retry["attemptNumber"] == 2
    assert retry["retryOfAttemptId"] == first["attemptId"]
    assert retry["retryCause"] == "provider_context_limit"
    assert compact["parentRequestId"] == first["requestId"]
    assert compact["compactionId"] == retry["compactionId"]
    assert len({data["attemptId"] for data in starts}) == 3
    assert [data["status"] for data in attempts] == ["started", "failed", "started", "completed", "started", "completed"]
    event_types = [
        event.type
        for event in repository.list_run_events(
            current.id,
            after_sequence=0,
            limit=100,
        )
    ]
    assert [kind for kind in event_types if kind is not RunEventType.MODEL_ATTEMPT] == [
        RunEventType.RUN_STARTED,
        RunEventType.MODEL_STARTED,
        RunEventType.CONTEXT_COMPACTION_STARTED,
        RunEventType.CONTEXT_COMPACTION_COMPLETED,
        RunEventType.MODEL_STARTED,
        RunEventType.ASSISTANT_DELTA,
        RunEventType.RUN_COMPLETED,
    ]
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

        capability_resolver=TestCapabilityResolver(),
    ).execute(current.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "context_limit_exceeded"
    assert len(gateway.requests) == 3


@async_test
async def test_prompt_log_failure_stops_before_any_model_request(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    gateway = ScriptedGateway(
        [[ModelTextDelta("must not run"), ModelCompleted(ModelFinishReason.FINAL)]]
    )
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
        system_prompt_provider=FailingSystemPromptProvider(),
    )

    with caplog.at_level(logging.ERROR, logger="opensprite.agent.context"):
        result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "internal_error"
    assert gateway.requests == []
    records = [
        record
        for record in caplog.records
        if record.name == "opensprite.agent.context"
        and record.getMessage() == f"agent run failed run_id={run.id}"
    ]
    assert len(records) == 1
    assert records[0].exc_info is not None


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

            capability_resolver=TestCapabilityResolver(),
        ).execute(run.id, cancellation)
    )
    await asyncio.wait_for(entered.wait(), timeout=1)

    cancellation.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result.status is RunStatus.CANCELLED
    assert repository.get_latest_compaction(conversation_id) is None
    assert [
        event.type
        for event in repository.list_run_events(
            run.id,
            after_sequence=0,
            limit=100,
        )
        if event.type is not RunEventType.MODEL_ATTEMPT
    ] == [
        RunEventType.RUN_STARTED,
        RunEventType.CONTEXT_COMPACTION_STARTED,
        RunEventType.CONTEXT_COMPACTION_CANCELLED,
        RunEventType.RUN_CANCELLED,
    ]


@async_test
async def test_failed_compaction_has_one_safe_terminal_event(tmp_path: Path) -> None:
    repository = store(tmp_path)
    conversation_id = seed_completed_turns(repository, 14, assistant_size=30_000)
    run = repository.start_run(
        conversation_id=conversation_id, client_request_id=str(uuid4()),
        message="current request", provider_id="openrouter", model_id="openrouter/auto",
        response_mode="default", context_budget="auto",
    ).run
    gateway = ScriptedGateway([[ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)]])
    result = await AgentLoop(
        repository=repository, gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event())
    events = repository.list_run_events(run.id, after_sequence=0, limit=100)
    compactions = [event for event in events if event.type.value.startswith("context.compaction.")]
    assert result.status is RunStatus.FAILED
    assert [event.type for event in compactions] == [
        RunEventType.CONTEXT_COMPACTION_STARTED, RunEventType.CONTEXT_COMPACTION_FAILED,
    ]
    assert compactions[0].data["compactionId"] == compactions[1].data["compactionId"]
    assert set(compactions[1].data) == {"schemaVersion", "compactionId", "errorCode"}
    assert len(gateway.requests) == 1


@async_test
async def test_fast_text_deltas_are_coalesced_before_persistence(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    chunks = [ModelTextDelta("a" * 1_000) for _ in range(8)]
    gateway = ScriptedGateway([[*chunks, ModelCompleted(ModelFinishReason.FINAL)]])
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,

        capability_resolver=TestCapabilityResolver(),
    )

    with patch.object(
        repository,
        "append_assistant_delta",
        wraps=repository.append_assistant_delta,
    ) as append_delta, patch("opensprite_backend.agent.loop.monotonic", return_value=0.0):
        result = await loop.execute(run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "a" * 8_000
    assert [len(call.args[1]) for call in append_delta.call_args_list] == [1_000, 5_000, 2_000]


@async_test
async def test_first_short_chunk_is_persisted_before_the_model_finishes(tmp_path: Path) -> None:
    repository = store(tmp_path)
    run = accepted_run(repository)
    first = "live-" + uuid4().hex
    final = "tail-" + uuid4().hex
    paused = asyncio.Event()
    release = asyncio.Event()

    class PausedGateway:
        async def stream(self, request):
            yield ModelTextDelta(first)
            paused.set()
            await release.wait()
            yield ModelTextDelta(final)
            yield ModelCompleted(ModelFinishReason.FINAL)

    task = asyncio.create_task(AgentLoop(
        repository=repository, gateway=PausedGateway(), capability_resolver=TestCapabilityResolver(),
    ).execute(run.id, asyncio.Event()))
    try:
        await asyncio.wait_for(paused.wait(), timeout=5)
        active = repository.get_run(run.id)
        assert active.status is RunStatus.RUNNING and active.partial_text == first
        assert not task.done()
    finally:
        release.set()
        result = await task
    assert result.status is RunStatus.COMPLETED and result.partial_text == first + final


@async_test
async def test_slow_short_chunks_flush_on_elapsed_time(tmp_path: Path) -> None:
    from opensprite_backend.agent.loop import _AssistantDeltaBuffer

    repository = store(tmp_path)
    run = accepted_run(repository)
    repository.mark_run_started(run.id)
    tick = [0.0]
    chunks = [uuid4().hex for _ in range(3)]
    buffer = _AssistantDeltaBuffer(repository, run.id)
    with patch("opensprite_backend.agent.loop.monotonic", side_effect=lambda: tick[0]):
        await buffer.append(chunks[0])
        tick[0] = 0.05
        await buffer.append(chunks[1])
        assert repository.get_run(run.id).partial_text == chunks[0]
        tick[0] = 0.101
        await buffer.append(chunks[2])
    assert repository.get_run(run.id).partial_text == "".join(chunks)
    deltas = [event.data["text"] for event in repository.list_run_events(run.id, after_sequence=0, limit=100)
              if event.type is RunEventType.ASSISTANT_DELTA]
    assert deltas == [chunks[0], chunks[1] + chunks[2]]
