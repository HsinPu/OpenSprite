"""Tests for user-initiated native local path selection."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.local_paths.linux import _path_from_file_uri
from opensprite_backend.local_paths.linux import LinuxPortalPathPicker
from opensprite_backend.local_paths.service import (
    LocalPathPickerError,
    LocalPathPickerService,
)


class FakePicker:
    def __init__(self, result: str | None) -> None:
        self.result = result
        self.kinds: list[str] = []

    async def pick(self, kind):
        self.kinds.append(kind)
        return self.result


class BlockingPicker:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def pick(self, kind):
        del kind
        self.entered.set()
        await self.release.wait()
        return None


@pytest.mark.parametrize("kind", ["executable", "directory"])
def test_api_returns_selected_absolute_path(tmp_path: Path, kind: str) -> None:
    selected = tmp_path / ("program.exe" if kind == "executable" else "workspace")
    if kind == "executable":
        selected.write_text("fixture", encoding="utf-8")
    else:
        selected.mkdir()
    native = FakePicker(str(selected))
    app = create_app(local_path_picker=LocalPathPickerService(native))

    with TestClient(app) as client:
        response = client.post("/api/local-paths/pick", json={"kind": kind})

    assert response.status_code == 200
    assert response.json() == {"path": str(selected.resolve())}
    assert native.kinds == [kind]


def test_cancel_returns_204_without_path() -> None:
    app = create_app(local_path_picker=LocalPathPickerService(FakePicker(None)))
    with TestClient(app) as client:
        response = client.post(
            "/api/local-paths/pick",
            json={"kind": "directory"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_code"),
    [
        ({"kind": "file"}, 400, "invalid_request"),
        ({"kind": "directory", "extra": True}, 400, "invalid_request"),
        ({}, 400, "invalid_request"),
    ],
)
def test_api_rejects_noncanonical_requests(
    payload: dict[str, object],
    expected_status: int,
    expected_code: str,
) -> None:
    app = create_app(local_path_picker=LocalPathPickerService(FakePicker(None)))
    with TestClient(app) as client:
        response = client.post("/api/local-paths/pick", json=payload)
    assert response.status_code == expected_status
    assert response.json() == {
        "error": {
            "code": expected_code,
            "message": "Request validation failed.",
            "retryable": False,
        }
    }


@pytest.mark.parametrize("selected", ["relative/path", "bad\npath"])
def test_service_rejects_invalid_picker_output(selected: str) -> None:
    service = LocalPathPickerService(FakePicker(selected))
    with pytest.raises(LocalPathPickerError) as raised:
        asyncio.run(service.pick("directory"))
    assert raised.value.code == "invalid_selection"
    assert selected not in repr(raised.value)


def test_wrong_selected_kind_is_rejected(tmp_path: Path) -> None:
    file_path = tmp_path / "file"
    file_path.write_text("fixture", encoding="utf-8")
    service = LocalPathPickerService(FakePicker(str(file_path)))
    with pytest.raises(LocalPathPickerError) as raised:
        asyncio.run(service.pick("directory"))
    assert raised.value.code == "invalid_selection"


def test_picker_busy_fails_without_waiting() -> None:
    async def scenario() -> None:
        native = BlockingPicker()
        service = LocalPathPickerService(native)
        first = asyncio.create_task(service.pick("directory"))
        await native.entered.wait()
        with pytest.raises(LocalPathPickerError) as raised:
            await service.pick("executable")
        assert raised.value.code == "picker_busy"
        native.release.set()
        assert await first is None

    asyncio.run(scenario())


def test_default_app_fails_closed_when_picker_is_not_composed() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/local-paths/pick",
            json={"kind": "directory"},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "picker_unavailable"


def test_mutating_picker_route_uses_existing_origin_protection() -> None:
    app = create_app(
        local_path_picker=LocalPathPickerService(FakePicker(None)),
        enforce_local_security=True,
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.post(
            "/api/local-paths/pick",
            headers={"Origin": "http://evil.example"},
            json={"kind": "directory"},
        )
    assert response.status_code == 400


def test_linux_portal_uri_parser_accepts_only_local_absolute_file_uri() -> None:
    assert _path_from_file_uri("file:///home/user/My%20Tools") == "/home/user/My Tools"
    for value in (
        "https://example.com/tool",
        "file://remote-host/path",
        "relative/path",
        1,
    ):
        with pytest.raises(LocalPathPickerError):
            _path_from_file_uri(value)


class FakeVariant:
    def __init__(self, signature: str, value: object) -> None:
        self.signature = signature
        self.value = value


class FakePortalRequest:
    def __init__(self, code: int, results: dict[str, object]) -> None:
        self.code = code
        self.results = results

    def on_response(self, callback) -> None:
        callback(self.code, self.results)


class FakePortalChooser:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, FakeVariant]]] = []

    async def call_open_file(self, parent: str, title: str, options: dict[str, FakeVariant]) -> str:
        self.calls.append((parent, title, options))
        return "/org/freedesktop/portal/desktop/request/fixture"


class FakePortalProxy:
    def __init__(self, interface: object) -> None:
        self.interface = interface

    def get_interface(self, name: str) -> object:
        del name
        return self.interface


class FakePortalBus:
    def __init__(self, chooser: FakePortalChooser, request: FakePortalRequest, **kwargs) -> None:
        del kwargs
        self.chooser = chooser
        self.request = request
        self.disconnected = False

    async def connect(self):
        return self

    async def introspect(self, destination: str, path: str):
        del destination
        return path

    def get_proxy_object(self, destination: str, path: str, introspection: str) -> FakePortalProxy:
        del destination, introspection
        return FakePortalProxy(self.chooser if path.endswith("/desktop") else self.request)

    def disconnect(self) -> None:
        self.disconnected = True


def test_linux_portal_requests_one_directory_and_decodes_result() -> None:
    chooser = FakePortalChooser()
    request = FakePortalRequest(
        0,
        {"uris": FakeVariant("as", ["file:///home/user/tools"])},
    )
    bus = FakePortalBus(chooser, request)
    picker = LinuxPortalPathPicker(
        message_bus_factory=lambda **kwargs: bus,
        variant_type=FakeVariant,
        session_bus="session",
    )

    selected = asyncio.run(picker.pick("directory"))

    assert selected == "/home/user/tools"
    assert chooser.calls[0][2]["directory"].value is True
    assert chooser.calls[0][2]["multiple"].value is False
    assert bus.disconnected is True


def test_linux_portal_cancel_returns_none() -> None:
    chooser = FakePortalChooser()
    bus = FakePortalBus(chooser, FakePortalRequest(1, {}))
    picker = LinuxPortalPathPicker(
        message_bus_factory=lambda **kwargs: bus,
        variant_type=FakeVariant,
        session_bus="session",
    )
    assert asyncio.run(picker.pick("executable")) is None
