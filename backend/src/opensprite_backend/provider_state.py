"""Strict non-secret provider metadata stored with atomic JSON replacement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Final, Protocol

from .models import ProviderId, ProviderStatus

_SCHEMA_VERSION: Final = 2
_CATALOG: Final[tuple[ProviderId, ...]] = ("openai", "anthropic")
_PERSISTED_STATUSES: Final = frozenset(
    {
        ProviderStatus.CONNECTED,
        ProviderStatus.INVALID_CREDENTIALS,
        ProviderStatus.PROVIDER_UNREACHABLE,
        ProviderStatus.PROVIDER_TIMEOUT,
        ProviderStatus.PROVIDER_RATE_LIMITED,
    }
)


class ProviderStateError(Exception):
    """Sanitized failure for unavailable or invalid local metadata."""

    def __init__(self) -> None:
        super().__init__("Provider metadata is unavailable.")


@dataclass(frozen=True, slots=True)
class ProviderState:
    provider_id: ProviderId
    status: ProviderStatus
    credential_preview: str | None
    credential_fingerprint: str
    last_checked_at: datetime


class ProviderStateRepository(Protocol):
    def get(self, provider_id: ProviderId) -> ProviderState | None: ...

    def set(self, state: ProviderState) -> None: ...

    def delete(self, provider_id: ProviderId) -> None: ...


class JsonProviderStateRepository:
    """Persist only validated, non-secret metadata in one atomic JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, provider_id: ProviderId) -> ProviderState | None:
        return self._read().get(provider_id)

    def set(self, state: ProviderState) -> None:
        self._validate_state(state)
        states = self._read()
        states[state.provider_id] = state
        self._write(states)

    def delete(self, provider_id: ProviderId) -> None:
        states = self._read()
        if provider_id not in states:
            return
        del states[provider_id]
        self._write(states)

    def _read(self) -> dict[ProviderId, ProviderState]:
        failed = False
        exists = False
        try:
            exists = self._path.exists()
        except Exception:
            failed = True
        if failed:
            raise ProviderStateError
        if not exists:
            return {}
        raw: object = None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            failed = True
        if failed:
            raise ProviderStateError
        return self._decode(raw)

    def _decode(self, raw: object) -> dict[ProviderId, ProviderState]:
        if (
            type(raw) is not dict
            or set(raw) != {"version", "providers"}
            or raw["version"] != _SCHEMA_VERSION
            or type(raw["providers"]) is not list
        ):
            raise ProviderStateError

        states: dict[ProviderId, ProviderState] = {}
        for record in raw["providers"]:
            if type(record) is not dict or set(record) != {
                "id",
                "status",
                "credentialPreview",
                "credentialFingerprint",
                "lastCheckedAt",
            }:
                raise ProviderStateError
            provider_id = record["id"]
            if provider_id not in _CATALOG or provider_id in states:
                raise ProviderStateError
            decode_failed = False
            status: ProviderStatus | None = None
            checked_at: datetime | None = None
            try:
                status = ProviderStatus(record["status"])
                checked_at = datetime.fromisoformat(
                    record["lastCheckedAt"].replace("Z", "+00:00")
                )
            except (AttributeError, TypeError, ValueError):
                decode_failed = True
            if decode_failed or status is None or checked_at is None:
                raise ProviderStateError
            state = ProviderState(
                provider_id=provider_id,
                status=status,
                credential_preview=record["credentialPreview"],
                credential_fingerprint=record["credentialFingerprint"],
                last_checked_at=checked_at,
            )
            self._validate_state(state)
            states[provider_id] = state
        return states

    @staticmethod
    def _validate_state(state: ProviderState) -> None:
        preview = state.credential_preview
        fingerprint = state.credential_fingerprint
        if (
            state.provider_id not in _CATALOG
            or state.status not in _PERSISTED_STATUSES
            or type(fingerprint) is not str
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
            or state.last_checked_at.tzinfo is None
            or state.last_checked_at.utcoffset() != UTC.utcoffset(None)
            or (
                preview is not None
                and not (
                    type(preview) is str
                    and (
                        preview == "••••"
                        or (
                            preview.startswith("••••")
                            and len(preview) == 8
                            and all(
                                character.isascii()
                                and (character.isalnum() or character in "_-")
                                for character in preview[4:]
                            )
                        )
                    )
                )
            )
        ):
            raise ProviderStateError

    def _write(self, states: dict[ProviderId, ProviderState]) -> None:
        records = []
        for provider_id in _CATALOG:
            state = states.get(provider_id)
            if state is None:
                continue
            self._validate_state(state)
            records.append(
                {
                    "id": state.provider_id,
                    "status": state.status.value,
                    "credentialPreview": state.credential_preview,
                    "credentialFingerprint": state.credential_fingerprint,
                    "lastCheckedAt": state.last_checked_at.isoformat(),
                }
            )
        payload = json.dumps(
            {"version": _SCHEMA_VERSION, "providers": records},
            ensure_ascii=False,
            separators=(",", ":"),
        )

        failed = False
        temporary_path: Path | None = None
        file_descriptor: int | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            file_descriptor, temporary_name = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                text=True,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                file_descriptor = None
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except Exception:
            failed = True
        finally:
            if file_descriptor is not None:
                try:
                    os.close(file_descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
        if failed:
            raise ProviderStateError
