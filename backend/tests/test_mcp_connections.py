"""Tests for inert MCP configuration, explicit lifecycle, and discovery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import wraps
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from threading import Thread

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.mcp.config import JsonMcpConfigStore, McpConfigStoreError, McpStdioConfig, McpStreamableHttpConfig
from opensprite_backend.mcp.manager import McpConnectionManager
from opensprite_backend.mcp.session import (
    DiscoveredMcpTool,
    McpClientSession,
    McpToolAnnotations,
    OfficialMcpSessionFactory,
)
from opensprite_backend.models import CreateMcpServerRequest
from opensprite_backend.tools.definition import (
    ToolDefinition,
    ToolEffect,
    ToolSource,
)


FIXTURE = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"
HTTP_FIXTURE = Path(__file__).parent / "fixtures" / "mcp_streamable_http_server.py"


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def payload(*, start_on_launch: bool = False) -> CreateMcpServerRequest:
    return CreateMcpServerRequest.model_validate(
        {
            "name": "Test MCP",
            "startOnLaunch": start_on_launch,
            "transport": {
                "type": "stdio",
                "executable": sys.executable,
                "arguments": [str(FIXTURE)],
                "workingDirectory": str(FIXTURE.parent),
            },
        }
    )


def http_payload(url: str = "https://mcp.example.test/mcp") -> CreateMcpServerRequest:
    return CreateMcpServerRequest.model_validate({
        "name": "Remote MCP",
        "startOnLaunch": False,
        "transport": {"type": "streamable-http", "url": url},
    })


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
            raise AssertionError("Streamable HTTP fixture stopped during startup")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return process, f"http://127.0.0.1:{port}/mcp"
        except OSError:
            time.sleep(0.02)
    process.kill()
    process.wait(timeout=5)
    raise AssertionError("Streamable HTTP fixture did not start")


def stop_http_fixture(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


class FixedStatusHandler(BaseHTTPRequestHandler):
    response_status = 401

    def do_POST(self) -> None:  # noqa: N802
        self.send_response(self.response_status)
        if self.response_status == 302:
            self.send_header("Location", "http://127.0.0.1/private")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def fixed_status_server(status: int) -> tuple[ThreadingHTTPServer, Thread, str]:
    handler = type(f"Status{status}Handler", (FixedStatusHandler,), {"response_status": status})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/mcp"
def discovered_tool() -> DiscoveredMcpTool:
    definition = ToolDefinition(
        name="mcp_12345678_echo_abcdef12",
        description="Echo a value.",
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
    return DiscoveredMcpTool(
        id=definition.name,
        server_id="12345678-1234-4234-8234-123456789012",
        original_name="echo",
        title="Echo",
        description="Echo a value.",
        annotations=McpToolAnnotations(False, True, False, True),
        definition=definition,
        unsupported_reason=None,
    )


@dataclass
class FakeSession(McpClientSession):
    protocol_version: str = "2026-07-28"
    server_name: str = "test-server"
    closed: bool = False

    async def discover_tools(self) -> tuple[DiscoveredMcpTool, ...]:
        return (discovered_tool(),)

    async def call_tool(self, original_name: str, arguments: dict[str, object]) -> str:
        del original_name, arguments
        return "ok"

    async def close(self) -> None:
        self.closed = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.opened = []

    async def open(self, config):
        self.opened.append(config)
        return FakeSession()


def test_config_store_round_trip_is_lazy_and_strict(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonMcpConfigStore(paths.mcp_settings_file)

    assert store.get() == ()
    assert not paths.home.exists()

    manager = McpConnectionManager(store, FakeSessionFactory())
    created = asyncio.run(manager.create_server(payload()))
    assert created.status == "disabled"
    stored = json.loads(paths.mcp_settings_file.read_text(encoding="utf-8"))
    assert stored["version"] == 2
    assert stored["servers"][0]["enabled"] is False

    corrupt = paths.mcp_settings_file
    corrupt.write_text('{"version":1,"version":1,"servers":[]}', encoding="utf-8")
    with pytest.raises(McpConfigStoreError):
        store.get()


def test_schema_v1_stdio_is_read_without_rewrite_and_next_write_uses_v2(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    identifier = "11111111-1111-4111-8111-111111111111"
    original = json.dumps({
        "version": 1,
        "servers": [{
            "id": identifier,
            "name": "Legacy",
            "enabled": False,
            "startOnLaunch": False,
            "transport": {"type": "stdio", "executable": sys.executable, "arguments": [str(FIXTURE)], "workingDirectory": None},
        }],
    }, separators=(",", ":"))
    path.write_text(original, encoding="utf-8")
    store = JsonMcpConfigStore(path)

    loaded = store.get()
    assert isinstance(loaded[0].transport, McpStdioConfig)
    assert path.read_text(encoding="utf-8") == original

    store.set(loaded)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


def test_schema_v2_streamable_http_round_trip_is_strict(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    manager = McpConnectionManager(JsonMcpConfigStore(path), FakeSessionFactory())
    created = asyncio.run(manager.create_server(http_payload()))

    assert created.transport.type == "streamable-http"
    loaded = JsonMcpConfigStore(path).get()
    assert isinstance(loaded[0].transport, McpStreamableHttpConfig)
    assert loaded[0].transport.url == "https://mcp.example.test/mcp"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["version"] == 2
    assert stored["servers"][0]["transport"] == {"type": "streamable-http", "url": "https://mcp.example.test/mcp"}

    stored["servers"][0]["transport"]["headers"] = {"Authorization": "secret"}
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(McpConfigStoreError):
        JsonMcpConfigStore(path).get()

    del stored["servers"][0]["transport"]["headers"]
    stored["servers"][0]["transport"]["url"] = "https://user:secret@mcp.example.test/mcp"
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(McpConfigStoreError):
        JsonMcpConfigStore(path).get()


@async_test
async def test_tampered_relative_executable_is_never_started(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    identifier = "11111111-1111-4111-8111-111111111111"
    path.write_text(json.dumps({
        "version": 1,
        "servers": [{
            "id": identifier,
            "name": "Tampered",
            "enabled": True,
            "startOnLaunch": True,
            "transport": {"type": "stdio", "executable": "python", "arguments": ["server.py"], "workingDirectory": None},
        }],
    }), encoding="utf-8")
    factory = FakeSessionFactory()
    manager = McpConnectionManager(JsonMcpConfigStore(path), factory)

    await manager.startup()

    assert factory.opened == []
    assert (await manager.list_servers()).servers[0].status == "stopped"


@async_test
async def test_create_is_inert_and_start_stop_are_explicit(tmp_path: Path) -> None:
    factory = FakeSessionFactory()
    manager = McpConnectionManager(JsonMcpConfigStore(tmp_path / "mcp.json"), factory)

    created = await manager.create_server(payload())
    assert created.enabled is False
    assert created.status == "disabled"
    assert factory.opened == []

    tested = await manager.test_server(created.id)
    assert tested.status == "connected"
    assert tested.enabled is False
    assert tested.toolCount == 1
    assert len(factory.opened) == 1

    started = await manager.start_server(created.id)
    assert started.enabled is True
    assert started.status == "connected"
    tools = await manager.list_tools(created.id)
    assert tools.tools[0].originalName == "echo"
    assert tools.tools[0].supported is True

    stopped = await manager.stop_server(created.id)
    assert stopped.enabled is False
    assert stopped.status == "disabled"
    await manager.delete_server(created.id)
    assert (await manager.list_servers()).servers == []


@async_test
async def test_autostart_requires_a_prior_explicit_start(tmp_path: Path) -> None:
    store = JsonMcpConfigStore(tmp_path / "mcp.json")
    first_factory = FakeSessionFactory()
    first = McpConnectionManager(store, first_factory)
    created = await first.create_server(payload(start_on_launch=True))

    await first.startup()
    assert first_factory.opened == []
    await first.start_server(created.id)
    assert len(first_factory.opened) == 1
    await first.close()

    second_factory = FakeSessionFactory()
    second = McpConnectionManager(store, second_factory)
    await second.startup()
    assert len(second_factory.opened) == 1
    assert (await second.list_servers()).servers[0].status == "connected"
    await second.close()


@async_test
async def test_official_manager_connects_to_repository_fixture(tmp_path: Path) -> None:
    manager = McpConnectionManager(
        JsonMcpConfigStore(tmp_path / "mcp.json"),
        OfficialMcpSessionFactory(),
    )
    created = await manager.create_server(payload())

    started = await manager.start_server(created.id)
    tools = await manager.list_tools(created.id)
    try:
        assert started.status == "connected"
        assert started.protocolVersion == "2026-07-28"
        assert {tool.originalName for tool in tools.tools} == {"echo", "process_id"}
        assert all(tool.supported for tool in tools.tools), tools.model_dump(mode="json")
    finally:
        await manager.close()


def test_api_crud_does_not_start_until_explicit_action(tmp_path: Path) -> None:
    factory = FakeSessionFactory()
    manager = McpConnectionManager(JsonMcpConfigStore(tmp_path / "mcp.json"), factory)
    app = create_app(mcp_connections=manager, enforce_local_security=True)
    body = payload().model_dump(mode="json", by_alias=True)

    with TestClient(app, base_url="http://localhost:8765") as client:
        rejected = client.post(
            "/api/mcp/servers",
            headers={"Origin": "http://evil.example"},
            json=body,
        )
        origin = {"Origin": "http://localhost:8765"}
        created = client.post("/api/mcp/servers", headers=origin, json=body)
        assert created.status_code == 201, created.text
        server_id = created.json()["id"]
        listed = client.get("/api/mcp/servers")
        started = client.post(f"/api/mcp/servers/{server_id}/start", headers=origin)
        tools = client.get(f"/api/mcp/servers/{server_id}/tools")
        stopped = client.post(f"/api/mcp/servers/{server_id}/stop", headers=origin)
        deleted = client.delete(f"/api/mcp/servers/{server_id}", headers=origin)

    assert rejected.status_code == 400
    assert listed.json()["servers"][0]["status"] == "disabled"
    assert len(factory.opened) == 1
    assert started.json()["status"] == "connected"
    assert tools.json()["tools"][0]["originalName"] == "echo"
    assert stopped.json()["status"] == "disabled"
    assert deleted.status_code == 204


def test_official_sdk_session_survives_separate_http_request_tasks(tmp_path: Path) -> None:
    manager = McpConnectionManager(
        JsonMcpConfigStore(tmp_path / "mcp.json"),
        OfficialMcpSessionFactory(),
    )
    app = create_app(mcp_connections=manager)
    body = payload().model_dump(mode="json", by_alias=True)

    with TestClient(app) as client:
        created = client.post("/api/mcp/servers", json=body)
        server_id = created.json()["id"]
        started = client.post(f"/api/mcp/servers/{server_id}/start")
        tools = client.get(f"/api/mcp/servers/{server_id}/tools")
        stopped = client.post(f"/api/mcp/servers/{server_id}/stop")

    assert created.status_code == 201
    assert started.status_code == 200, started.text
    assert {item["originalName"] for item in tools.json()["tools"]} == {
        "echo",
        "process_id",
    }
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "disabled"


def test_streamable_http_sdk_session_survives_separate_http_request_tasks(tmp_path: Path) -> None:
    process, url = start_http_fixture()
    try:
        manager = McpConnectionManager(
            JsonMcpConfigStore(tmp_path / "mcp.json"),
            OfficialMcpSessionFactory(),
        )
        app = create_app(mcp_connections=manager)
        body = http_payload(url).model_dump(mode="json", by_alias=True)

        with TestClient(app) as client:
            created = client.post("/api/mcp/servers", json=body)
            server_id = created.json()["id"]
            started = client.post(f"/api/mcp/servers/{server_id}/start")
            tools = client.get(f"/api/mcp/servers/{server_id}/tools")
            stopped = client.post(f"/api/mcp/servers/{server_id}/stop")

        assert created.status_code == 201
        assert started.status_code == 200, started.text
        assert started.json()["transport"] == {"type": "streamable-http", "url": url}
        assert [item["originalName"] for item in tools.json()["tools"]] == ["echo_http"]
        assert stopped.status_code == 200, stopped.text
    finally:
        stop_http_fixture(process)


@pytest.mark.parametrize(("status_code", "expected_status", "expected_code"), [
    (401, 401, "authentication_required"),
    (302, 502, "redirect_not_allowed"),
])
def test_streamable_http_maps_auth_and_redirect_without_following(
    tmp_path: Path,
    status_code: int,
    expected_status: int,
    expected_code: str,
) -> None:
    server, thread, url = fixed_status_server(status_code)
    try:
        manager = McpConnectionManager(JsonMcpConfigStore(tmp_path / "mcp.json"))
        app = create_app(mcp_connections=manager)
        with TestClient(app) as client:
            created = client.post("/api/mcp/servers", json=http_payload(url).model_dump(mode="json", by_alias=True))
            response = client.post(f"/api/mcp/servers/{created.json()['id']}/start")
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
