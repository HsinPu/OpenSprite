"""Human approval contract tests for consequential MCP Tool calls."""

from __future__ import annotations

import asyncio
import hmac
import json
from hashlib import sha256
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.models import (
    ToolApprovalDecision,
    ToolApprovalDecisionResponse,
    ToolApprovalDetail,
    ToolApprovalErrorCode,
)
from opensprite_backend.conversations.models import RunEventType
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.tools.approval import ToolApprovalError, ToolApprovalGrant, ToolApprovalManager
from opensprite_backend.tools.availability import ToolAvailabilitySnapshot
from opensprite_backend.tools.definition import (
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSource,
)
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolInvocationError, ToolRegistry
from opensprite_backend.tools.receipts import FileToolReceiptWriter, verify_tool_receipts
from opensprite_backend.workspaces import (
    WorkspaceAvailability,
    WorkspaceExecutionContext,
    WorkspaceKind,
    WorkspaceUnavailableReason,
)


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


@dataclass
class SensitiveTool:
    definition: ToolDefinition
    calls: int = 0

    async def invoke(self, arguments, context) -> ToolResult:
        del arguments, context
        self.calls += 1
        return ToolResult(content="approved result", summary="approved")


def repository_and_run(tmp_path: Path):
    repository = SqliteConversationRepository(build_app_paths(tmp_path / ".opensprite").database_file)
    run = repository.start_run(
        conversation_id=None,
        client_request_id="11111111-1111-4111-8111-111111111111",
        message="approval test",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run
    repository.mark_run_started(run.id)
    return repository, run


def tool() -> SensitiveTool:
    return SensitiveTool(
        ToolDefinition(
            name="mcp_12345678_echo_abcdef12",
            description="A sensitive MCP tool.",
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            effect=ToolEffect.SENSITIVE,
            source=ToolSource.MCP,
            source_id="12345678-1234-4234-8234-123456789012",
            display_name="Echo",
        )
    )


async def approval_id(repository, run_id: str, task: asyncio.Task[object]) -> str:
    for _ in range(100):
        events = repository.list_run_events(run_id, after_sequence=0, limit=100)
        requested = [event for event in events if event.type is RunEventType.TOOL_APPROVAL_REQUESTED]
        if requested:
            return str(requested[-1].data["approvalId"])
        if task.done():
            task.result()
        await asyncio.sleep(0.01)
    raise AssertionError("approval event was not created")


@async_test
async def test_allow_once_exposes_arguments_then_executes(tmp_path: Path) -> None:
    repository, run = repository_and_run(tmp_path)
    approval = ToolApprovalManager(repository)
    sensitive = tool()
    paths = build_app_paths(tmp_path / ".opensprite")
    registry = ToolRegistry(
        [sensitive],
        policy=ReadOnlyToolPolicy(),
        approval=approval,
        receipts=FileToolReceiptWriter(paths),
    )
    started: list[bool] = []
    context = ToolContext(run.id, run.conversation_id, asyncio.Event())
    task = asyncio.create_task(
        registry.invoke(
            sensitive.definition.name,
            {"value": "hello"},
            context,
            ToolAvailabilitySnapshot(frozenset({sensitive.definition.name})),
            lambda: _mark_started(started),
        )
    )

    pending_id = await approval_id(repository, run.id, task)
    detail = await approval.get(pending_id)
    assert detail.arguments == {"value": "hello"}
    assert len(detail.argumentHash) == 64
    assert sensitive.calls == 0
    assert started == []

    decision = await approval.decide(pending_id, ToolApprovalDecision.ALLOW_ONCE)
    result = await task

    assert decision.decision == "allow_once"
    assert result.content == "approved result"
    assert sensitive.calls == 1
    assert started == [True]
    assert verify_tool_receipts(paths) is True
    receipt_text = next(paths.tool_receipts_dir.glob("*.jsonl")).read_text(
        encoding="utf-8"
    )
    assert "hello" not in receipt_text
    receipts = [json.loads(line) for line in receipt_text.splitlines()]
    assert all(item["version"] == 3 for item in receipts)
    assert all(item["workspaceId"] == context.workspace.id for item in receipts)
    assert all(item["workspaceRevision"] == 1 for item in receipts)
    assert all(item["workspaceRootHash"] is None for item in receipts)
    assert all(item["workspaceAvailability"] == "not_applicable" for item in receipts)
    events = repository.list_run_events(run.id, after_sequence=0, limit=100)
    assert [event.type for event in events[-2:]] == [
        RunEventType.TOOL_APPROVAL_REQUESTED,
        RunEventType.TOOL_APPROVAL_DECIDED,
    ]
    assert "hello" not in repository.database_file.read_text(encoding="utf-8", errors="ignore")


@async_test
async def test_denial_never_invokes_tool(tmp_path: Path) -> None:
    repository, run = repository_and_run(tmp_path)
    approval = ToolApprovalManager(repository)
    sensitive = tool()
    registry = ToolRegistry([sensitive], policy=ReadOnlyToolPolicy(), approval=approval)
    context = ToolContext(run.id, run.conversation_id, asyncio.Event())
    task = asyncio.create_task(
        registry.invoke(
            sensitive.definition.name,
            {"value": "denied"},
            context,
            ToolAvailabilitySnapshot(frozenset({sensitive.definition.name})),
        )
    )

    pending_id = await approval_id(repository, run.id, task)
    await approval.decide(pending_id, ToolApprovalDecision.DENY)

    with pytest.raises(ToolInvocationError) as captured:
        await task
    assert captured.value.code == "tool_denied"
    assert sensitive.calls == 0


@async_test
async def test_approval_is_single_use_and_rejects_a_second_decision(tmp_path: Path) -> None:
    repository, run = repository_and_run(tmp_path)
    approval = ToolApprovalManager(repository)
    sensitive = tool()
    registry = ToolRegistry([sensitive], policy=ReadOnlyToolPolicy(), approval=approval)
    context = ToolContext(run.id, run.conversation_id, asyncio.Event())
    task = asyncio.create_task(registry.invoke(
        sensitive.definition.name,
        {"value": "denied"},
        context,
        ToolAvailabilitySnapshot(frozenset({sensitive.definition.name})),
    ))

    pending_id = await approval_id(repository, run.id, task)
    await approval.decide(pending_id, ToolApprovalDecision.DENY)
    with pytest.raises(ToolApprovalError) as captured:
        await approval.decide(pending_id, ToolApprovalDecision.ALLOW_ONCE)
    assert captured.value.code is ToolApprovalErrorCode.APPROVAL_ALREADY_DECIDED
    with pytest.raises(ToolInvocationError):
        await task


@async_test
async def test_expired_approval_never_invokes_tool(tmp_path: Path) -> None:
    repository, run = repository_and_run(tmp_path)
    now = [datetime(2026, 9, 2, tzinfo=UTC)]
    approval = ToolApprovalManager(repository, clock=lambda: now[0])
    sensitive = tool()
    registry = ToolRegistry([sensitive], policy=ReadOnlyToolPolicy(), approval=approval)
    context = ToolContext(run.id, run.conversation_id, asyncio.Event())
    task = asyncio.create_task(registry.invoke(
        sensitive.definition.name,
        {"value": "expired"},
        context,
        ToolAvailabilitySnapshot(frozenset({sensitive.definition.name})),
    ))

    pending_id = await approval_id(repository, run.id, task)
    now[0] += timedelta(minutes=11)
    with pytest.raises(ToolApprovalError) as captured:
        await approval.get(pending_id)
    assert captured.value.code is ToolApprovalErrorCode.APPROVAL_EXPIRED
    with pytest.raises(ToolApprovalError) as captured:
        await approval.decide(pending_id, ToolApprovalDecision.ALLOW_ONCE)
    assert captured.value.code is ToolApprovalErrorCode.APPROVAL_EXPIRED
    assert sensitive.calls == 0
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_receipt_verification_detects_tampering(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    writer = FileToolReceiptWriter(paths)
    definition = tool().definition
    root = str((tmp_path / "workspace-root").resolve())
    context = ToolContext(
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        asyncio.Event(),
        WorkspaceExecutionContext(
            id="44444444-4444-4444-8444-444444444444",
            kind=WorkspaceKind.DIRECTORY,
            name="Alpha",
            root_path=root,
            revision=4,
            root_hash="b" * 64,
            availability=WorkspaceAvailability.UNAVAILABLE,
            unavailable_reason=WorkspaceUnavailableReason.MISSING,
        ),
    )
    grant = ToolApprovalGrant(
        "33333333-3333-4333-8333-333333333333",
        "a" * 64,
    )
    asyncio.run(writer.record_authorized(definition, context, grant))
    assert verify_tool_receipts(paths) is True

    receipt = next(paths.tool_receipts_dir.glob("*.jsonl"))
    raw = json.loads(receipt.read_text(encoding="utf-8"))
    assert raw["version"] == 3
    assert raw["workspaceAvailability"] == "unavailable"
    assert root not in receipt.read_text(encoding="utf-8")

    for version in (2, 1):
        legacy_body = {key: value for key, value in raw.items() if key != "signature"}
        legacy_body["version"] = version
        legacy_body.pop("workspaceAvailability")
        if version == 1:
            for key in ("workspaceId", "workspaceRevision", "workspaceRootHash"):
                legacy_body.pop(key)
        legacy_signature = hmac.new(
            paths.tool_receipt_key_file.read_bytes(),
            json.dumps(legacy_body, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8"),
            sha256,
        ).hexdigest()
        legacy = {**legacy_body, "signature": legacy_signature}
        receipt.write_text(
            json.dumps(legacy, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assert verify_tool_receipts(paths) is True

    receipt.write_text(
        receipt.read_text(encoding="utf-8").replace(
            '"status":"authorized"',
            '"status":"completed"',
        ),
        encoding="utf-8",
    )
    assert verify_tool_receipts(paths) is False


class FakeApprovalOperations:
    def __init__(self) -> None:
        now = datetime(2026, 9, 2, tzinfo=UTC)
        self.detail = ToolApprovalDetail(
            id="33333333-3333-4333-8333-333333333333",
            runId="11111111-1111-4111-8111-111111111111",
            conversationId="22222222-2222-4222-8222-222222222222",
            toolId="mcp_12345678_echo_abcdef12",
            toolName="Echo",
            serverId="12345678-1234-4234-8234-123456789012",
            arguments={"value": "hello"},
            argumentHash="a" * 64,
            createdAt=now,
            expiresAt=now + timedelta(minutes=10),
        )
        self.decision: ToolApprovalDecision | None = None

    async def get(self, approval_id: str) -> ToolApprovalDetail:
        assert approval_id == self.detail.id
        return self.detail

    async def decide(
        self,
        approval_id: str,
        decision: ToolApprovalDecision,
    ) -> ToolApprovalDecisionResponse:
        assert approval_id == self.detail.id
        self.decision = decision
        return ToolApprovalDecisionResponse(id=approval_id, decision=decision)


def test_approval_api_returns_exact_arguments_and_requires_same_origin() -> None:
    approvals = FakeApprovalOperations()
    app = create_app(tool_approvals=approvals, enforce_local_security=True)
    with TestClient(app, base_url="http://localhost:8765") as client:
        detail = client.get(f"/api/tool-approvals/{approvals.detail.id}")
        rejected = client.put(
            f"/api/tool-approvals/{approvals.detail.id}",
            headers={"Origin": "http://evil.example"},
            json={"decision": "allow_once"},
        )
        decided = client.put(
            f"/api/tool-approvals/{approvals.detail.id}",
            headers={"Origin": "http://localhost:8765"},
            json={"decision": "deny"},
        )

    assert detail.status_code == 200
    assert detail.json()["arguments"] == {"value": "hello"}
    assert rejected.status_code == 400
    assert decided.json() == {"id": approvals.detail.id, "decision": "deny"}
    assert approvals.decision is ToolApprovalDecision.DENY


async def _mark_started(started: list[bool]) -> None:
    started.append(True)
