"""End-to-end Agent integration against the repository-owned MCP fixture."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from functools import wraps
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

from context_test_support import TestCapabilityResolver

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.inference.models import (
    ModelCompleted,
    ModelFinishReason,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCall,
)
from opensprite_backend.mcp.config import JsonMcpConfigStore
from opensprite_backend.mcp.manager import McpConnectionManager
from opensprite_backend.models import CreateMcpServerRequest, ToolApprovalDecision
from opensprite_backend.tools import create_production_tool_registry
from opensprite_backend.tools.approval import ToolApprovalManager
from opensprite_backend.tools.availability import ToolAvailabilitySnapshot
from opensprite_backend.tools.receipts import FileToolReceiptWriter, verify_tool_receipts


FIXTURE = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"
HTTP_FIXTURE = Path(__file__).parent / "fixtures" / "mcp_streamable_http_server.py"


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class ScriptedGateway:
    def __init__(self) -> None:
        self.scripts: deque[list[ModelStreamEvent]] = deque()
        self.requests: list[ModelRequest] = []

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        self.requests.append(request)
        for event in self.scripts.popleft():
            yield event


class FixedAvailability:
    def __init__(self, names: frozenset[str]) -> None:
        self.names = names

    async def snapshot(self) -> ToolAvailabilitySnapshot:
        return ToolAvailabilitySnapshot(self.names)


async def wait_for_approval(repository, run_id: str) -> str:
    for _ in range(500):
        events = repository.list_run_events(run_id, after_sequence=0, limit=100)
        for event in events:
            if event.type is RunEventType.TOOL_APPROVAL_REQUESTED:
                return str(event.data["approvalId"])
        await asyncio.sleep(0.01)
    raise AssertionError("approval request was not emitted")


def start_http_fixture() -> tuple[subprocess.Popen[bytes], str]:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, str(HTTP_FIXTURE), str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("HTTP fixture stopped during startup")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return process, f"http://127.0.0.1:{port}/mcp"
        except OSError:
            time.sleep(0.02)
    process.kill()
    process.wait(timeout=5)
    raise AssertionError("HTTP fixture did not start")


def stop_http_fixture(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@async_test
async def test_approved_mcp_tool_runs_inside_agent_loop(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    repository = SqliteConversationRepository(paths.database_file)
    approvals = ToolApprovalManager(repository)
    receipts = FileToolReceiptWriter(paths)
    manager = McpConnectionManager(JsonMcpConfigStore(paths.mcp_settings_file))
    created = await manager.create_server(
        CreateMcpServerRequest.model_validate(
            {
                "name": "Fixture",
                "transport": {
                    "type": "stdio",
                    "executable": sys.executable,
                    "arguments": [str(FIXTURE)],
                    "workingDirectory": str(FIXTURE.parent),
                },
                "startOnLaunch": False,
            }
        )
    )
    await manager.start_server(created.id)
    tools = await manager.list_tools(created.id)
    echo_id = next(tool.id for tool in tools.tools if tool.originalName == "echo")
    gateway = ScriptedGateway()
    gateway.scripts.extend(
        [
            [
                ModelToolCall("mcp-call-1", echo_id, {"value": "hello"}),
                ModelCompleted(ModelFinishReason.TOOL_CALLS),
            ],
            [
                ModelTextDelta("MCP returned hello."),
                ModelCompleted(ModelFinishReason.FINAL),
            ],
        ]
    )
    run = repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="Use the MCP echo tool.",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run
    loop = AgentLoop(
        repository=repository,
        gateway=gateway,
        tools=create_production_tool_registry(approvals, receipts),
        tool_availability=FixedAvailability(frozenset({echo_id})),
        dynamic_tools=manager,
        capability_resolver=TestCapabilityResolver(),
    )

    try:
        execution = asyncio.create_task(loop.execute(run.id, asyncio.Event()))
        approval_id = await wait_for_approval(repository, run.id)
        detail = await approvals.get(approval_id)
        assert detail.arguments == {"value": "hello"}
        await approvals.decide(approval_id, ToolApprovalDecision.ALLOW_ONCE)
        result = await execution

        assert result.status is RunStatus.COMPLETED
        assert result.partial_text == "MCP returned hello."
        assert gateway.requests[0].tools[0].name == echo_id
        assert gateway.requests[1].messages[-1].content == "hello"
        events = repository.list_run_events(run.id, after_sequence=0, limit=100)
        assert [event.type for event in events] == [
            RunEventType.RUN_STARTED,
            RunEventType.MODEL_STARTED,
            RunEventType.TOOL_APPROVAL_REQUESTED,
            RunEventType.TOOL_APPROVAL_DECIDED,
            RunEventType.TOOL_STARTED,
            RunEventType.TOOL_COMPLETED,
            RunEventType.MODEL_STARTED,
            RunEventType.ASSISTANT_DELTA,
            RunEventType.RUN_COMPLETED,
        ]
        assert verify_tool_receipts(paths) is True
    finally:
        await manager.close()


@async_test
async def test_approved_streamable_http_tool_reuses_agent_safety_boundary(tmp_path: Path) -> None:
    process, url = start_http_fixture()
    paths = build_app_paths(tmp_path / ".opensprite")
    repository = SqliteConversationRepository(paths.database_file)
    approvals = ToolApprovalManager(repository)
    receipts = FileToolReceiptWriter(paths)
    manager = McpConnectionManager(JsonMcpConfigStore(paths.mcp_settings_file))
    try:
        created = await manager.create_server(CreateMcpServerRequest.model_validate({
            "name": "HTTP Fixture",
            "transport": {"type": "streamable-http", "url": url},
            "startOnLaunch": False,
        }))
        await manager.start_server(created.id)
        tools = await manager.list_tools(created.id)
        echo_id = next(tool.id for tool in tools.tools if tool.originalName == "echo_http")
        gateway = ScriptedGateway()
        gateway.scripts.extend([
            [ModelToolCall("http-call-1", echo_id, {"value": "remote hello"}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
            [ModelTextDelta("HTTP MCP returned remote hello."), ModelCompleted(ModelFinishReason.FINAL)],
        ])
        run = repository.start_run(
            conversation_id=None,
            client_request_id=str(uuid4()),
            message="Use the HTTP MCP echo tool.",
            provider_id="openrouter",
            model_id="openrouter/auto",
            response_mode="default",
        ).run
        loop = AgentLoop(
            repository=repository,
            gateway=gateway,
            tools=create_production_tool_registry(approvals, receipts),
            tool_availability=FixedAvailability(frozenset({echo_id})),
            dynamic_tools=manager,
            capability_resolver=TestCapabilityResolver(),
        )

        execution = asyncio.create_task(loop.execute(run.id, asyncio.Event()))
        approval_id = await wait_for_approval(repository, run.id)
        assert (await approvals.get(approval_id)).arguments == {"value": "remote hello"}
        await approvals.decide(approval_id, ToolApprovalDecision.ALLOW_ONCE)
        result = await execution

        assert result.status is RunStatus.COMPLETED
        assert gateway.requests[1].messages[-1].content == "remote hello"
        assert verify_tool_receipts(paths) is True
        receipt = next(paths.tool_receipts_dir.glob("*.jsonl")).read_text(encoding="utf-8")
        assert "remote hello" not in receipt
    finally:
        await manager.close()
        stop_http_fixture(process)
