"""Crash-recovery journal for provider credential and metadata mutations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Final, Protocol

from .models import ProviderId, ProviderStatus
from .provider_state import ProviderState

_SCHEMA_VERSION: Final = 1
_MAX_JOURNAL_BYTES: Final = 1024 * 1024
_PROVIDER_IDS: Final = frozenset({"openai", "anthropic", "openrouter"})
_STATUSES: Final = frozenset(
    {
        ProviderStatus.CONNECTED,
        ProviderStatus.INVALID_CREDENTIALS,
        ProviderStatus.PROVIDER_UNREACHABLE,
        ProviderStatus.PROVIDER_TIMEOUT,
        ProviderStatus.PROVIDER_RATE_LIMITED,
    }
)


class ProviderTransactionError(Exception):
    """Sanitized failure for an unavailable provider transaction journal."""


@dataclass(frozen=True, slots=True)
class ProviderTransactionSide:
    fingerprint: str | None
    state: ProviderState | None


@dataclass(frozen=True, slots=True)
class ProviderTransaction:
    provider_id: ProviderId
    before: ProviderTransactionSide
    after: ProviderTransactionSide


class ProviderTransactionJournal(Protocol):
    def get(self) -> ProviderTransaction | None: ...

    def set(self, transaction: ProviderTransaction) -> None: ...

    def clear(self) -> None: ...


class JsonProviderTransactionJournal:
    """Persist one non-secret recovery record with strict atomic JSON."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = RLock()

    def get(self) -> ProviderTransaction | None:
        with self._lock:
            if not self._path.exists():
                return None
            try:
                with self._path.open("rb") as stream:
                    encoded = stream.read(_MAX_JOURNAL_BYTES + 1)
                if len(encoded) > _MAX_JOURNAL_BYTES:
                    raise ValueError("provider transaction journal is too large")
                payload = json.loads(
                    encoded.decode("utf-8"),
                    object_pairs_hook=self._reject_duplicate_keys,
                )
                return self._decode(payload)
            except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
                raise ProviderTransactionError from None

    def set(self, transaction: ProviderTransaction) -> None:
        with self._lock:
            try:
                payload = json.dumps(
                    self._encode(transaction),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                if len(payload) > _MAX_JOURNAL_BYTES:
                    raise ValueError("provider transaction journal is too large")
                self._atomic_write(payload)
            except (OSError, TypeError, ValueError):
                raise ProviderTransactionError from None

    def clear(self) -> None:
        with self._lock:
            try:
                self._path.unlink(missing_ok=True)
                self._sync_parent()
            except OSError:
                raise ProviderTransactionError from None

    @classmethod
    def _encode(cls, transaction: ProviderTransaction) -> dict[str, object]:
        cls._validate_transaction(transaction)
        return {
            "version": _SCHEMA_VERSION,
            "providerId": transaction.provider_id,
            "before": cls._encode_side(transaction.before),
            "after": cls._encode_side(transaction.after),
        }

    @classmethod
    def _decode(cls, payload: object) -> ProviderTransaction:
        if type(payload) is not dict or set(payload) != {
            "version",
            "providerId",
            "before",
            "after",
        }:
            raise ValueError("invalid provider transaction journal")
        if payload["version"] != _SCHEMA_VERSION:
            raise ValueError("unsupported provider transaction journal")
        provider_id = payload["providerId"]
        if provider_id not in _PROVIDER_IDS:
            raise ValueError("unsupported provider transaction")
        transaction = ProviderTransaction(
            provider_id=provider_id,
            before=cls._decode_side(payload["before"], provider_id),
            after=cls._decode_side(payload["after"], provider_id),
        )
        cls._validate_transaction(transaction)
        return transaction

    @classmethod
    def _encode_side(cls, side: ProviderTransactionSide) -> dict[str, object]:
        return {
            "fingerprint": side.fingerprint,
            "state": None if side.state is None else cls._encode_state(side.state),
        }

    @classmethod
    def _decode_side(
        cls,
        payload: object,
        provider_id: ProviderId,
    ) -> ProviderTransactionSide:
        if type(payload) is not dict or set(payload) != {"fingerprint", "state"}:
            raise ValueError("invalid provider transaction side")
        fingerprint = payload["fingerprint"]
        state_payload = payload["state"]
        state = (
            None
            if state_payload is None
            else cls._decode_state(state_payload, provider_id)
        )
        return ProviderTransactionSide(fingerprint=fingerprint, state=state)

    @staticmethod
    def _encode_state(state: ProviderState) -> dict[str, object]:
        return {
            "id": state.provider_id,
            "status": state.status.value,
            "credentialPreview": state.credential_preview,
            "credentialFingerprint": state.credential_fingerprint,
            "lastCheckedAt": state.last_checked_at.isoformat(),
        }

    @staticmethod
    def _decode_state(payload: object, provider_id: ProviderId) -> ProviderState:
        if type(payload) is not dict or set(payload) != {
            "id",
            "status",
            "credentialPreview",
            "credentialFingerprint",
            "lastCheckedAt",
        }:
            raise ValueError("invalid provider transaction state")
        if payload["id"] != provider_id:
            raise ValueError("provider transaction state does not match")
        try:
            status = ProviderStatus(payload["status"])
            checked_at = datetime.fromisoformat(
                payload["lastCheckedAt"].replace("Z", "+00:00")
            )
        except (AttributeError, TypeError, ValueError):
            raise ValueError("invalid provider transaction state") from None
        return ProviderState(
            provider_id=provider_id,
            status=status,
            credential_preview=payload["credentialPreview"],
            credential_fingerprint=payload["credentialFingerprint"],
            last_checked_at=checked_at,
        )

    @classmethod
    def _validate_transaction(cls, transaction: ProviderTransaction) -> None:
        if (
            not isinstance(transaction, ProviderTransaction)
            or transaction.provider_id not in _PROVIDER_IDS
        ):
            raise ValueError("invalid provider transaction")
        cls._validate_side(transaction.provider_id, transaction.before)
        cls._validate_side(transaction.provider_id, transaction.after)
        if transaction.before == transaction.after:
            raise ValueError("provider transaction has no mutation")

    @classmethod
    def _validate_side(
        cls,
        provider_id: ProviderId,
        side: ProviderTransactionSide,
    ) -> None:
        if not isinstance(side, ProviderTransactionSide):
            raise ValueError("invalid provider transaction side")
        fingerprint = side.fingerprint
        state = side.state
        if fingerprint is None:
            if state is not None:
                raise ValueError("provider transaction side is inconsistent")
            return
        if (
            type(fingerprint) is not str
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
            or not isinstance(state, ProviderState)
            or state.provider_id != provider_id
            or state.status not in _STATUSES
            or state.credential_fingerprint != fingerprint
            or state.last_checked_at.tzinfo is None
            or state.last_checked_at.utcoffset() != UTC.utcoffset(None)
        ):
            raise ValueError("provider transaction side is inconsistent")

    def _atomic_write(self, payload: bytes) -> None:
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            parent.chmod(0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{self._path.name}.",
            suffix=".tmp",
        )
        temporary: Path | None = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
            temporary = None
            if os.name != "nt":
                self._path.chmod(0o600)
            self._sync_parent()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _sync_parent(self) -> None:
        if os.name == "nt" or not self._path.parent.exists():
            return
        descriptor = os.open(self._path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate provider transaction key")
            result[key] = value
        return result
