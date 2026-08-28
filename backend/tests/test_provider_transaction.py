"""Crash recovery tests for provider credential and metadata mutations."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
from pathlib import Path

import pytest

from opensprite_backend.credentials import EncryptedJsonCredentialStore
from opensprite_backend.models import ProviderStatus
from opensprite_backend.provider_connections import ProviderConnectionService
from opensprite_backend.provider_state import JsonProviderStateRepository, ProviderState
from opensprite_backend.provider_transaction import (
    JsonProviderTransactionJournal,
    ProviderTransaction,
    ProviderTransactionError,
    ProviderTransactionSide,
)

NOW = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)
OLD_SECRET = "old-secret-1234"
NEW_SECRET = "new-secret-5678"


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def state(secret: str, checked_at: datetime) -> ProviderState:
    return ProviderState(
        provider_id="openai",
        status=ProviderStatus.CONNECTED,
        credential_preview=f"••••{secret[-4:]}",
        credential_fingerprint=fingerprint(secret),
        last_checked_at=checked_at,
    )


def transaction() -> ProviderTransaction:
    return ProviderTransaction(
        provider_id="openai",
        before=ProviderTransactionSide(
            fingerprint=fingerprint(OLD_SECRET),
            state=state(OLD_SECRET, NOW),
        ),
        after=ProviderTransactionSide(
            fingerprint=fingerprint(NEW_SECRET),
            state=state(NEW_SECRET, NOW),
        ),
    )


class UnusedValidator:
    async def validate(self, provider_id: str, api_key: str) -> None:
        del provider_id, api_key

    async def list_openrouter_models(self, api_key: str):
        del api_key
        raise AssertionError("not used")


class AcceptingValidator(UnusedValidator):
    async def validate(self, provider_id: str, api_key: str) -> None:
        assert provider_id == "openai"
        assert api_key == NEW_SECRET


def test_journal_round_trip_is_strict_and_contains_no_secret(tmp_path: Path) -> None:
    path = tmp_path / "state" / "provider-transaction.json"
    journal = JsonProviderTransactionJournal(path)

    journal.set(transaction())

    assert journal.get() == transaction()
    encoded = path.read_bytes()
    assert OLD_SECRET.encode() not in encoded
    assert NEW_SECRET.encode() not in encoded
    assert list(path.parent.glob("*.tmp")) == []
    journal.clear()
    assert journal.get() is None


@pytest.mark.parametrize(
    "payload",
    [
        b'{"version":1,"version":1,"providerId":"openai","before":{},"after":{}}',
        b" " * (1024 * 1024 + 1),
    ],
    ids=["duplicate-key", "oversized"],
)
def test_invalid_journal_fails_closed(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "provider-transaction.json"
    path.write_bytes(payload)

    with pytest.raises(ProviderTransactionError):
        JsonProviderTransactionJournal(path).get()


def test_recovery_rolls_forward_when_new_credential_was_written(tmp_path: Path) -> None:
    credential_path = tmp_path / "auth.json"
    key_path = tmp_path / "config" / "credential.key"
    state_path = tmp_path / "state" / "providers.json"
    journal_path = tmp_path / "state" / "provider-transaction.json"
    credentials = EncryptedJsonCredentialStore(credential_path, key_path)
    states = JsonProviderStateRepository(state_path)
    journal = JsonProviderTransactionJournal(journal_path)
    credentials.set("openai", OLD_SECRET)
    states.set(state(OLD_SECRET, NOW))
    journal.set(transaction())
    credentials.set("openai", NEW_SECRET)

    service = ProviderConnectionService(
        credentials,
        states,
        UnusedValidator(),  # type: ignore[arg-type]
        journal,
        clock=lambda: NOW,
    )
    asyncio.run(service.recover_pending())

    assert credentials.get("openai") == NEW_SECRET
    assert states.get("openai") == transaction().after.state
    assert journal.get() is None


def test_recovery_finishes_disconnect_after_credential_delete(tmp_path: Path) -> None:
    credentials = EncryptedJsonCredentialStore(
        tmp_path / "auth.json",
        tmp_path / "config" / "credential.key",
    )
    states = JsonProviderStateRepository(tmp_path / "state" / "providers.json")
    journal = JsonProviderTransactionJournal(
        tmp_path / "state" / "provider-transaction.json"
    )
    old_state = state(OLD_SECRET, NOW)
    credentials.set("openai", OLD_SECRET)
    states.set(old_state)
    journal.set(
        ProviderTransaction(
            provider_id="openai",
            before=ProviderTransactionSide(
                fingerprint=fingerprint(OLD_SECRET),
                state=old_state,
            ),
            after=ProviderTransactionSide(fingerprint=None, state=None),
        )
    )
    credentials.delete("openai")

    service = ProviderConnectionService(
        credentials,
        states,
        UnusedValidator(),  # type: ignore[arg-type]
        journal,
        clock=lambda: NOW,
    )
    asyncio.run(service.recover_pending())

    assert credentials.get("openai") is None
    assert states.get("openai") is None
    assert journal.get() is None


def test_normal_connect_and_idempotent_disconnect_leave_no_journal(
    tmp_path: Path,
) -> None:
    credentials = EncryptedJsonCredentialStore(
        tmp_path / "auth.json",
        tmp_path / "config" / "credential.key",
    )
    states = JsonProviderStateRepository(tmp_path / "state" / "providers.json")
    journal = JsonProviderTransactionJournal(
        tmp_path / "state" / "provider-transaction.json"
    )
    service = ProviderConnectionService(
        credentials,
        states,
        AcceptingValidator(),  # type: ignore[arg-type]
        journal,
        clock=lambda: NOW,
    )

    summary = asyncio.run(service.connect("openai", NEW_SECRET))
    repeated = asyncio.run(service.connect("openai", NEW_SECRET))
    asyncio.run(service.disconnect("openai"))
    asyncio.run(service.disconnect("openai"))

    assert summary.status is ProviderStatus.CONNECTED
    assert repeated == summary
    assert credentials.get("openai") is None
    assert states.get("openai") is None
    assert journal.get() is None
