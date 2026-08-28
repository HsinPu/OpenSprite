"""Strict-schema and atomic-write tests for non-secret provider metadata."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest

from opensprite_backend.models import ProviderId, ProviderStatus
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.provider_state import (
    JsonProviderStateRepository,
    ProviderState,
    ProviderStateError,
)

CHECKED_AT = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)
FINGERPRINT = hashlib.sha256(b"stored-secret-1234").hexdigest()


def state(provider_id: ProviderId = "openai") -> ProviderState:
    return ProviderState(
        provider_id=provider_id,
        status=ProviderStatus.CONNECTED,
        credential_preview="••••1234",
        credential_fingerprint=FINGERPRINT,
        last_checked_at=CHECKED_AT,
    )


def test_round_trip_uses_only_strict_non_secret_schema(tmp_path: Path) -> None:
    path = tmp_path / "state" / "providers.json"
    repository = JsonProviderStateRepository(path)

    repository.set(state())

    assert repository.get("openai") == state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "version": 2,
        "providers": [
            {
                "id": "openai",
                "status": "connected",
                "credentialPreview": "••••1234",
                "credentialFingerprint": FINGERPRINT,
                "lastCheckedAt": "2026-08-20T09:30:00+00:00",
            }
        ],
    }
    assert list(path.parent.glob("*.tmp")) == []


def test_empty_read_is_side_effect_free_and_first_write_only_creates_state(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    repository = JsonProviderStateRepository(paths.provider_state_file)

    assert repository.get("openai") is None
    assert not paths.home.exists()

    repository.set(state())

    assert paths.provider_state_file.is_file()
    assert sorted(
        path.relative_to(paths.home).as_posix()
        for path in paths.home.rglob("*")
    ) == ["state", "state/providers.json"]


def test_openrouter_round_trip_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    repository = JsonProviderStateRepository(path)

    repository.set(state("openrouter"))

    assert repository.get("openrouter") == state("openrouter")
    assert json.loads(path.read_text(encoding="utf-8"))["providers"][0]["id"] == (
        "openrouter"
    )


def test_metadata_write_uses_fixed_catalog_order(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    repository = JsonProviderStateRepository(path)

    repository.set(state("openrouter"))
    repository.set(state("openai"))
    repository.set(state("anthropic"))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert [record["id"] for record in payload["providers"]] == [
        "openai",
        "anthropic",
        "openrouter",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":1,"providers":[]}',
        '{"version":2,"providers":{},"secret":"x"}',
        '{"version":2,"providers":[{"id":"other","status":"connected","credentialPreview":"••••1234","credentialFingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","lastCheckedAt":"2026-08-20T09:30:00Z"}]}',
        '{"version":2,"providers":[{"id":"openai","status":"disconnected","credentialPreview":"••••1234","credentialFingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","lastCheckedAt":"2026-08-20T09:30:00Z"}]}',
        '{"version":2,"providers":[{"id":"openai","status":"connected","credentialPreview":"secret","credentialFingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","lastCheckedAt":"2026-08-20T09:30:00Z"}]}',
        '{"version":2,"providers":[{"id":"openai","status":"connected","credentialPreview":1234,"credentialFingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","lastCheckedAt":"2026-08-20T09:30:00Z"}]}',
        '{"version":2,"providers":[{"id":"openai","status":"connected","credentialPreview":"••••1234","credentialFingerprint":"not-a-fingerprint","lastCheckedAt":"2026-08-20T09:30:00Z"}]}',
    ],
)
def test_corrupt_or_noncanonical_metadata_fails_closed(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "providers.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ProviderStateError) as raised:
        JsonProviderStateRepository(path).get("openai")

    assert str(raised.value) == "Provider metadata is unavailable."
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    "payload",
    [
        '{"version":2,"version":2,"providers":[]}',
        '{"version":2,"providers":[{"id":"openai","id":"openai","status":"connected","credentialPreview":"••••1234","credentialFingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","lastCheckedAt":"2026-08-20T09:30:00Z"}]}',
    ],
)
def test_duplicate_json_keys_fail_closed(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "providers.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ProviderStateError):
        JsonProviderStateRepository(path).get("openai")


def test_oversized_metadata_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(ProviderStateError):
        JsonProviderStateRepository(path).get("openai")


def test_delete_is_idempotent(tmp_path: Path) -> None:
    repository = JsonProviderStateRepository(tmp_path / "providers.json")
    repository.delete("openai")
    repository.set(state())
    repository.delete("openai")
    repository.delete("openai")
    assert repository.get("openai") is None
