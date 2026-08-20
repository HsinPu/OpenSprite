"""Strict-schema and atomic-write tests for non-secret provider metadata."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest

from opensprite_backend.models import ProviderStatus
from opensprite_backend.provider_state import (
    JsonProviderStateRepository,
    ProviderState,
    ProviderStateError,
)

CHECKED_AT = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)
FINGERPRINT = hashlib.sha256(b"stored-secret-1234").hexdigest()


def state() -> ProviderState:
    return ProviderState(
        provider_id="openai",
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


def test_delete_is_idempotent(tmp_path: Path) -> None:
    repository = JsonProviderStateRepository(tmp_path / "providers.json")
    repository.delete("openai")
    repository.set(state())
    repository.delete("openai")
    repository.delete("openai")
    assert repository.get("openai") is None
