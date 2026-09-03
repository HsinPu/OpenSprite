"""Strict atomic stores for local access and one-time bootstrap state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Final
from enum import StrEnum

from ..atomic_file import atomic_write


_MAX_BYTES: Final = 64 * 1024
_HEX = frozenset("0123456789abcdef")


class AccessStoreError(Exception):
    def __init__(self) -> None:
        super().__init__("Local access storage is unavailable.")


@dataclass(frozen=True, slots=True)
class AccessRecord:
    password_hash: str


class AccessMode(StrEnum):
    TRUSTED_LOCAL = "trusted_local"
    PASSWORD_REQUIRED = "password_required"


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    mode: AccessMode


@dataclass(frozen=True, slots=True)
class BootstrapRecord:
    token_hash: str
    created_at: datetime
    expires_at: datetime


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read(path: Path) -> object | None:
    try:
        with path.open("rb") as stream:
            data = stream.read(_MAX_BYTES + 1)
    except FileNotFoundError:
        return None
    except OSError:
        raise AccessStoreError from None
    if len(data) > _MAX_BYTES:
        raise AccessStoreError
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise AccessStoreError from None


def _write(path: Path, payload: dict[str, object]) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        raise AccessStoreError
    try:
        atomic_write(path, encoded)
    except Exception:
        raise AccessStoreError from None


class JsonAccessStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> AccessRecord | None:
        raw = _read(self._path)
        if raw is None:
            return None
        if type(raw) is not dict or set(raw) != {"version", "passwordHash"} or raw["version"] != 1:
            raise AccessStoreError
        value = raw["passwordHash"]
        if type(value) is not str or not value.startswith("$argon2id$") or len(value) > 1024:
            raise AccessStoreError
        return AccessRecord(value)

    def set(self, record: AccessRecord) -> None:
        if not isinstance(record, AccessRecord) or not record.password_hash.startswith("$argon2id$"):
            raise AccessStoreError
        _write(self._path, {"version": 1, "passwordHash": record.password_hash})

    def delete(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            raise AccessStoreError from None


class JsonAccessPolicyStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> AccessPolicy:
        raw = _read(self._path)
        if raw is None:
            return AccessPolicy(AccessMode.PASSWORD_REQUIRED)
        if type(raw) is not dict or set(raw) != {"version", "mode"} or raw["version"] != 1:
            raise AccessStoreError
        try:
            return AccessPolicy(AccessMode(raw["mode"]))
        except (TypeError, ValueError):
            raise AccessStoreError from None

    def set(self, policy: AccessPolicy) -> None:
        if not isinstance(policy, AccessPolicy):
            raise AccessStoreError
        _write(self._path, {"version": 1, "mode": policy.mode.value})


class JsonBootstrapStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> BootstrapRecord | None:
        raw = _read(self._path)
        if raw is None:
            return None
        if type(raw) is not dict or set(raw) != {"version", "tokenHash", "createdAt", "expiresAt"} or raw["version"] != 1:
            raise AccessStoreError
        token_hash = raw["tokenHash"]
        if type(token_hash) is not str or len(token_hash) != 64 or any(char not in _HEX for char in token_hash):
            raise AccessStoreError
        try:
            created_at = datetime.fromisoformat(str(raw["createdAt"]).replace("Z", "+00:00"))
            expires_at = datetime.fromisoformat(str(raw["expiresAt"]).replace("Z", "+00:00"))
        except ValueError:
            raise AccessStoreError from None
        if created_at.tzinfo is None or expires_at.tzinfo is None or created_at >= expires_at:
            raise AccessStoreError
        return BootstrapRecord(token_hash, created_at.astimezone(UTC), expires_at.astimezone(UTC))

    def set(self, record: BootstrapRecord) -> None:
        if not isinstance(record, BootstrapRecord):
            raise AccessStoreError
        _write(self._path, {
            "version": 1,
            "tokenHash": record.token_hash,
            "createdAt": record.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "expiresAt": record.expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        })

    def delete(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            raise AccessStoreError from None
