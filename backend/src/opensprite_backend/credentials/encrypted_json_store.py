"""Cross-platform encrypted local storage for fixed provider credentials."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import threading
import uuid
from typing import Final, TypedDict, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .store import (
    CredentialStoreUnavailableError,
    InvalidCredentialSecretError,
    UnsupportedCredentialProviderError,
)

_STORE_VERSION: Final = 2
_ALGORITHM: Final = "AES-256-GCM"
_MAX_STORE_BYTES: Final = 1024 * 1024
_KEY_BYTES: Final = 32
_KEY_TEXT_BYTES: Final = 44
_NONCE_BYTES: Final = 12
_PROVIDER_IDS: Final = frozenset({"openai", "anthropic", "openrouter"})
_MCP_CREDENTIAL_ID: Final = re.compile(
    r"^mcp:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:bearer$"
)
_AAD_PREFIX: Final = b"OpenSprite credential store v1\0"


class _EncryptedEntry(TypedDict):
    nonce: str
    ciphertext: str
    fingerprint: str


def _validated_credential_id(credential_id: str) -> str:
    if (
        type(credential_id) is not str
        or (
            credential_id not in _PROVIDER_IDS
            and _MCP_CREDENTIAL_ID.fullmatch(credential_id) is None
        )
    ):
        raise UnsupportedCredentialProviderError
    return credential_id


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _encoded(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decoded(value: object) -> bytes:
    if type(value) is not str:
        raise ValueError("encoded value must be text")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("encoded value is invalid") from None


def _atomic_write(path: Path, payload: bytes) -> None:
    parent = path.parent
    temporary = path.with_name(
        f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    )
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            parent.chmod(0o700)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        if os.name != "nt":
            directory_descriptor = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except OSError:
        raise CredentialStoreUnavailableError from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class EncryptedJsonCredentialStore:
    """Encrypt each approved credential with a per-install AES-256-GCM key."""

    __slots__ = ("_key_path", "_lock", "_path")

    def __init__(self, path: str | Path, key_path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve(strict=False)
        self._key_path = Path(key_path).expanduser().resolve(strict=False)
        self._lock = threading.RLock()

    def fingerprint(self, provider_id: str) -> str | None:
        provider = _validated_credential_id(provider_id)
        with self._lock:
            entry = self._load_entries().get(provider)
            if entry is not None:
                self._load_key()
            return entry["fingerprint"] if entry is not None else None

    def get(self, provider_id: str) -> str | None:
        provider = _validated_credential_id(provider_id)
        with self._lock:
            entry = self._load_entries().get(provider)
            if entry is None:
                return None
            try:
                key = self._load_key()
                nonce = _decoded(entry["nonce"])
                ciphertext = _decoded(entry["ciphertext"])
                if len(nonce) != _NONCE_BYTES or len(ciphertext) < 17:
                    raise ValueError("invalid encrypted credential")
                fingerprint = entry["fingerprint"]
                plaintext = AESGCM(key).decrypt(
                    nonce,
                    ciphertext,
                    self._associated_data(provider, fingerprint),
                )
                secret = plaintext.decode("utf-8")
                actual_fingerprint = hashlib.sha256(plaintext).hexdigest()
                if not secret.strip() or not hmac.compare_digest(
                    fingerprint,
                    actual_fingerprint,
                ):
                    raise ValueError("invalid decrypted credential")
                return secret
            except (InvalidTag, UnicodeDecodeError, ValueError):
                raise CredentialStoreUnavailableError from None

    def set(self, provider_id: str, secret: str) -> None:
        provider = _validated_credential_id(provider_id)
        if type(secret) is not str or not secret.strip():
            raise InvalidCredentialSecretError
        plaintext = secret.encode("utf-8")
        with self._lock:
            entries = self._load_entries()
            key = self._load_or_create_key(has_entries=bool(entries))
            nonce = os.urandom(_NONCE_BYTES)
            fingerprint = hashlib.sha256(plaintext).hexdigest()
            ciphertext = AESGCM(key).encrypt(
                nonce,
                plaintext,
                self._associated_data(provider, fingerprint),
            )
            entries[provider] = {
                "nonce": _encoded(nonce),
                "ciphertext": _encoded(ciphertext),
                "fingerprint": fingerprint,
            }
            self._save_entries(entries)

    def delete(self, provider_id: str) -> None:
        provider = _validated_credential_id(provider_id)
        with self._lock:
            entries = self._load_entries()
            if provider not in entries:
                return
            entries.pop(provider)
            self._save_entries(entries)

    @staticmethod
    def _associated_data(provider_id: str, fingerprint: str) -> bytes:
        return (
            _AAD_PREFIX
            + provider_id.encode("ascii")
            + b"\0"
            + fingerprint.encode("ascii")
        )

    def _load_key(self) -> bytes:
        try:
            with self._key_path.open("rb") as handle:
                raw = handle.read(_KEY_TEXT_BYTES + 2)
            if (
                len(raw) != _KEY_TEXT_BYTES + 1
                or not raw.endswith(b"\n")
                or raw[:-1].count(b"\n") != 0
            ):
                raise ValueError("invalid credential key file")
            key = base64.b64decode(raw[:-1], validate=True)
            if len(key) != _KEY_BYTES:
                raise ValueError("invalid credential key")
            return key
        except (OSError, binascii.Error, ValueError):
            raise CredentialStoreUnavailableError from None

    def _load_or_create_key(self, *, has_entries: bool) -> bytes:
        if self._key_path.exists():
            return self._load_key()
        if has_entries:
            raise CredentialStoreUnavailableError
        key = AESGCM.generate_key(bit_length=256)
        _atomic_write(self._key_path, (_encoded(key) + "\n").encode("ascii"))
        return key

    def _load_entries(self) -> dict[str, _EncryptedEntry]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("rb") as handle:
                raw = handle.read(_MAX_STORE_BYTES + 1)
            if len(raw) > _MAX_STORE_BYTES:
                raise ValueError("credential file is too large")
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
            return self._validate_payload(payload)
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            raise CredentialStoreUnavailableError from None

    @staticmethod
    def _validate_payload(payload: object) -> dict[str, _EncryptedEntry]:
        expected_root = {"version", "algorithm", "credentials"}
        if type(payload) is not dict or set(payload) != expected_root:
            raise ValueError("invalid credential file")
        version = payload.get("version")
        if version not in {1, _STORE_VERSION}:
            raise ValueError("unsupported credential file version")
        if payload.get("algorithm") != _ALGORITHM:
            raise ValueError("unsupported credential algorithm")
        raw_credentials = payload.get("credentials")
        if type(raw_credentials) is not dict:
            raise ValueError("invalid credential map")

        entries: dict[str, _EncryptedEntry] = {}
        expected_entry = {"nonce", "ciphertext", "fingerprint"}
        for provider_id, entry in raw_credentials.items():
            if (
                type(provider_id) is not str
                or (
                    provider_id not in _PROVIDER_IDS
                    and not (
                        version == _STORE_VERSION
                        and _MCP_CREDENTIAL_ID.fullmatch(provider_id) is not None
                    )
                )
            ):
                raise ValueError("unsupported provider in credential file")
            if type(entry) is not dict or set(entry) != expected_entry:
                raise ValueError("invalid credential entry")
            nonce = _decoded(entry.get("nonce"))
            ciphertext = _decoded(entry.get("ciphertext"))
            fingerprint = entry.get("fingerprint")
            if (
                len(nonce) != _NONCE_BYTES
                or len(ciphertext) < 17
                or type(fingerprint) is not str
                or len(fingerprint) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in fingerprint
                )
            ):
                raise ValueError("invalid credential entry")
            entries[cast(str, provider_id)] = cast(_EncryptedEntry, entry)
        return entries

    def _save_entries(self, entries: dict[str, _EncryptedEntry]) -> None:
        payload = {
            "version": _STORE_VERSION,
            "algorithm": _ALGORITHM,
            "credentials": {
                provider_id: entries[provider_id]
                for provider_id in sorted(entries)
            },
        }
        encoded = (
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        if len(encoded) > _MAX_STORE_BYTES:
            raise CredentialStoreUnavailableError
        _atomic_write(self._path, encoded)
