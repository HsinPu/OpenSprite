from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from opensprite_backend.app import create_app
from opensprite_backend.schedules.service import ScheduleService
from opensprite_backend.schedules.sqlite_repository import SqliteScheduleRepository


NOW = datetime(2026, 3, 5, 3, tzinfo=UTC)
IDS = tuple(
    f"20000000-0000-4000-8000-{index:012d}" for index in range(1, 30)
)


def _client(tmp_path: Path) -> TestClient:
    identifiers = iter(IDS)
    repository = SqliteScheduleRepository(
        tmp_path / "opensprite.db",
        clock=lambda: NOW,
        identifier_factory=lambda: next(identifiers),
    )
    service = ScheduleService(repository, clock=lambda: NOW)
    return TestClient(create_app(schedules=service), base_url="http://localhost:8765")


def _payload() -> dict[str, object]:
    return {
        "name": "Morning brief",
        "prompt": "Summarize today's priorities.",
        "timeZone": "Asia/Taipei",
        "cadence": {"type": "daily", "localTime": "09:30"},
        "executionProfile": {
            "providerId": "openrouter",
            "modelId": "openrouter/auto",
            "responseMode": "balanced",
            "contextBudget": "64k",
            "outputBudget": "16k",
            "outputContinuation": "5",
        },
    }


def test_schedule_crud_actions_and_occurrence_history(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        created = client.post("/api/schedules", json=_payload())
        assert created.status_code == 201
        schedule = created.json()
        schedule_id = schedule["id"]
        assert schedule["cadence"] == {"type": "daily", "localTime": "09:30"}

        listed = client.get("/api/schedules", params={"limit": 10})
        assert listed.status_code == 200
        assert listed.json()["schedules"][0]["id"] == schedule_id

        paused = client.post(
            f"/api/schedules/{schedule_id}/pause",
            json={"revision": schedule["revision"]},
        )
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

        resumed = client.post(
            f"/api/schedules/{schedule_id}/resume",
            json={"revision": paused.json()["revision"]},
        )
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "active"

        manual = client.post(f"/api/schedules/{schedule_id}/run-now")
        assert manual.status_code == 202
        assert manual.json()["trigger"] == "manual"
        assert manual.json()["status"] == "pending"

        history = client.get(f"/api/schedules/{schedule_id}/occurrences")
        assert history.status_code == 200
        assert history.json()["occurrences"][0]["id"] == manual.json()["id"]

        deleted = client.delete(f"/api/schedules/{schedule_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/schedules/{schedule_id}").status_code == 404


def test_schedule_routes_reject_unknown_duplicate_and_stale_revision(
    tmp_path: Path,
) -> None:
    with _client(tmp_path) as client:
        unknown = client.post(
            "/api/schedules",
            json={**_payload(), "unexpected": True},
        )
        assert unknown.status_code == 400

        duplicate = client.post(
            "/api/schedules",
            content='{"name":"a","name":"b"}',
            headers={"Content-Type": "application/json"},
        )
        assert duplicate.status_code == 400
        assert duplicate.json()["error"]["code"] == "invalid_request"

        created = client.post("/api/schedules", json=_payload()).json()
        updated_payload = {**_payload(), "revision": created["revision"]}
        first = client.put(
            f"/api/schedules/{created['id']}",
            json={**updated_payload, "name": "Changed"},
        )
        assert first.status_code == 200
        conflict = client.put(
            f"/api/schedules/{created['id']}",
            json=updated_payload,
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "revision_conflict"


def test_runtime_status_is_a_strict_supported_value(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/schedules/runtime-status")
    assert response.status_code == 200
    assert response.json()["continuity"] in {
        "linger_enabled",
        "login_only",
        "unknown",
    }


def test_schedule_routes_are_authentication_protected(tmp_path: Path) -> None:
    class Unauthenticated:
        async def authenticate(self, token):
            del token
            return None

    app = create_app(
        local_authentication=Unauthenticated(),
        enforce_authentication=True,
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/schedules")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
