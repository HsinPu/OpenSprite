"""Conversation startup and send-behavior settings tests."""

from __future__ import annotations

from asyncio import run
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversation_settings import (
    ConversationSettingsService,
    ConversationSettingsStoreError,
    JsonConversationSettingsStore,
)
from opensprite_backend.models import ConversationSettings


def settings(
    startup_view: str = "new",
    send_behavior: str = "enter",
    auto_scroll: bool = True,
) -> ConversationSettings:
    return ConversationSettings(  # type: ignore[arg-type]
        startupView=startup_view,
        sendBehavior=send_behavior,
        autoScroll=auto_scroll,
    )


def test_store_round_trip_and_lazy_default_read(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonConversationSettingsStore(paths.conversation_settings_file)

    assert store.get() == settings()
    assert not paths.home.exists()
    saved = settings("recent", "modifier-enter", False)
    store.set(saved)

    assert store.get() == saved
    assert json.loads(
        paths.conversation_settings_file.read_text(encoding="utf-8")
    ) == {
        "version": 2,
        "startupView": "recent",
        "sendBehavior": "modifier-enter",
        "autoScroll": False,
    }
    assert sorted(
        path.relative_to(paths.home).as_posix()
        for path in paths.home.rglob("*")
    ) == ["config", "config/conversation.json"]


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":2,"startupView":"new","sendBehavior":"enter","autoScroll":true,"extra":true}',
        '{"version":2,"version":2,"startupView":"new","sendBehavior":"enter","autoScroll":true}',
        '{"version":1,"startupView":"new","sendBehavior":"enter","autoScroll":true}',
        '{"version":2,"startupView":"new","sendBehavior":"enter"}',
        '{"version":2,"startupView":"last","sendBehavior":"enter","autoScroll":true}',
        '{"version":2,"startupView":"new","sendBehavior":"shift-enter","autoScroll":true}',
        '{"version":2,"startupView":"new","sendBehavior":"enter","autoScroll":1}',
    ],
)
def test_store_rejects_malformed_or_noncanonical_json(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "conversation.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ConversationSettingsStoreError):
        JsonConversationSettingsStore(path).get()


def test_store_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "conversation.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(ConversationSettingsStoreError):
        JsonConversationSettingsStore(path).get()


def test_atomic_failure_cleans_temp_and_preserves_old_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config" / "conversation.json"
    store = JsonConversationSettingsStore(path)
    store.set(settings())
    before = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(ConversationSettingsStoreError):
        store.set(settings("recent", "modifier-enter", False))

    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_service_api_validation_and_same_origin(tmp_path: Path) -> None:
    service = ConversationSettingsService(
        JsonConversationSettingsStore(tmp_path / "conversation.json")
    )
    assert run(service.get()) == settings()

    with TestClient(create_app(conversation_settings=service)) as client:
        initial = client.get("/api/settings/conversation")
        saved = client.put(
            "/api/settings/conversation",
            json={"startupView": "recent", "sendBehavior": "modifier-enter", "autoScroll": False},
        )
        invalid = client.put(
            "/api/settings/conversation",
            json={"startupView": "last", "sendBehavior": "enter", "autoScroll": True},
        )

    assert initial.json() == {"startupView": "new", "sendBehavior": "enter", "autoScroll": True}
    assert saved.json() == {
        "startupView": "recent",
        "sendBehavior": "modifier-enter",
        "autoScroll": False,
    }
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"

    secured = create_app(
        conversation_settings=service,
        enforce_local_security=True,
    )
    with TestClient(secured, base_url="http://localhost:8765") as client:
        rejected = client.put(
            "/api/settings/conversation",
            headers={"Origin": "http://evil.example"},
            json={"startupView": "new", "sendBehavior": "enter", "autoScroll": True},
        )
    assert rejected.status_code == 400


def test_corrupt_store_maps_to_sanitized_503(tmp_path: Path) -> None:
    path = tmp_path / "conversation.json"
    path.write_text("not-json", encoding="utf-8")
    service = ConversationSettingsService(JsonConversationSettingsStore(path))

    response = TestClient(
        create_app(conversation_settings=service)
    ).get("/api/settings/conversation")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "settings_store_unavailable",
            "message": "Conversation settings are unavailable.",
            "retryable": True,
        }
    }


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_store_uses_owner_only_directory_and_file_modes(tmp_path: Path) -> None:
    path = tmp_path / "config" / "conversation.json"
    JsonConversationSettingsStore(path).set(settings())

    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
