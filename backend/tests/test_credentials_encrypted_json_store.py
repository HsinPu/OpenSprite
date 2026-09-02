"""Security and lifecycle tests for encrypted provider credentials."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path

import pytest

from opensprite_backend.credentials import (
    CredentialStoreUnavailableError,
    EncryptedJsonCredentialStore,
    InvalidCredentialSecretError,
    UnsupportedCredentialProviderError,
)
from opensprite_backend.credentials import encrypted_json_store as store_module


def build_store(tmp_path: Path) -> tuple[EncryptedJsonCredentialStore, Path, Path]:
    credential_path = tmp_path / ".opensprite" / "auth.json"
    key_path = tmp_path / ".opensprite" / "config" / "credential.key"
    return (
        EncryptedJsonCredentialStore(credential_path, key_path),
        credential_path,
        key_path,
    )


def load_payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def save_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_absent_store_reads_empty_without_creating_the_data_root(
    tmp_path: Path,
) -> None:
    store, credential_path, key_path = build_store(tmp_path)

    assert store.fingerprint("openai") is None
    assert store.get("openai") is None
    assert not credential_path.parent.exists()
    assert not key_path.parent.exists()


def test_three_providers_round_trip_without_plaintext_on_disk(
    tmp_path: Path,
) -> None:
    store, credential_path, key_path = build_store(tmp_path)
    secrets = {
        "openai": "openai-secret-1234",
        "anthropic": "anthropic-secret-5678",
        "openrouter": "openrouter-secret-9012",
    }

    for provider_id, secret in secrets.items():
        store.set(provider_id, secret)

    for provider_id, secret in secrets.items():
        assert store.get(provider_id) == secret
        assert store.fingerprint(provider_id) == hashlib.sha256(
            secret.encode("utf-8")
        ).hexdigest()

    credential_bytes = credential_path.read_bytes()
    key_bytes = key_path.read_bytes()
    for secret in secrets.values():
        assert secret.encode("utf-8") not in credential_bytes
        assert secret.encode("utf-8") not in key_bytes
    payload = load_payload(credential_path)
    assert payload["version"] == 2
    assert payload["algorithm"] == "AES-256-GCM"
    assert list(credential_path.parent.glob("auth.json.tmp.*")) == []
    assert list(key_path.parent.glob("credential.key.tmp.*")) == []
    if os.name != "nt":
        assert credential_path.stat().st_mode & 0o777 == 0o600
        assert key_path.stat().st_mode & 0o777 == 0o600
        assert credential_path.parent.stat().st_mode & 0o777 == 0o700
        assert key_path.parent.stat().st_mode & 0o777 == 0o700


def test_replacing_same_secret_uses_a_new_nonce_and_ciphertext(
    tmp_path: Path,
) -> None:
    store, credential_path, _ = build_store(tmp_path)
    store.set("openai", "same-secret")
    first = load_payload(credential_path)["credentials"]["openai"]  # type: ignore[index]

    store.set("openai", "same-secret")
    second = load_payload(credential_path)["credentials"]["openai"]  # type: ignore[index]

    assert first["nonce"] != second["nonce"]
    assert first["ciphertext"] != second["ciphertext"]
    assert first["fingerprint"] == second["fingerprint"]


def test_mcp_bearer_token_round_trips_without_plaintext_on_disk(
    tmp_path: Path,
) -> None:
    store, credential_path, key_path = build_store(tmp_path)
    credential_id = "mcp:11111111-1111-4111-8111-111111111111:bearer"
    secret = "mcp-bearer-secret"

    store.set(credential_id, secret)

    assert store.get(credential_id) == secret
    assert store.fingerprint(credential_id) == hashlib.sha256(
        secret.encode("utf-8")
    ).hexdigest()
    assert secret.encode("utf-8") not in credential_path.read_bytes()
    assert secret.encode("utf-8") not in key_path.read_bytes()


def test_schema_v1_provider_credentials_remain_readable(tmp_path: Path) -> None:
    store, credential_path, _ = build_store(tmp_path)
    store.set("openai", "legacy-secret")
    payload = load_payload(credential_path)
    payload["version"] = 1
    save_payload(credential_path, payload)

    assert store.get("openai") == "legacy-secret"

    store.set("anthropic", "new-secret")
    assert load_payload(credential_path)["version"] == 2


def test_cross_provider_writes_do_not_lose_updates(tmp_path: Path) -> None:
    store, _, _ = build_store(tmp_path)
    values = {
        "openai": "openai-secret",
        "anthropic": "anthropic-secret",
        "openrouter": "openrouter-secret",
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(store.set, provider_id, secret)
            for provider_id, secret in values.items()
        ]
        for future in futures:
            future.result()

    assert {provider_id: store.get(provider_id) for provider_id in values} == values


def test_fingerprint_reads_metadata_without_decrypting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, _, _ = build_store(tmp_path)
    store.set("openai", "openai-secret")

    def fail_decrypt(*args: object, **kwargs: object) -> bytes:
        del args, kwargs
        raise AssertionError("fingerprint attempted to decrypt")

    monkeypatch.setattr(store_module.AESGCM, "decrypt", fail_decrypt)
    assert store.fingerprint("openai") == hashlib.sha256(
        b"openai-secret"
    ).hexdigest()


@pytest.mark.parametrize("target", ["nonce", "ciphertext", "fingerprint"])
def test_tampered_entry_fails_closed(
    tmp_path: Path,
    target: str,
) -> None:
    case = tmp_path / target
    store, credential_path, _ = build_store(case)
    store.set("openai", "openai-secret")
    payload = load_payload(credential_path)
    entry = payload["credentials"]["openai"]  # type: ignore[index]
    if target == "fingerprint":
        entry[target] = "0" * 64
    else:
        raw = bytearray(base64.b64decode(entry[target]))
        raw[0] ^= 1
        entry[target] = base64.b64encode(raw).decode("ascii")
    save_payload(credential_path, payload)

    with pytest.raises(CredentialStoreUnavailableError):
        store.get("openai")


def test_provider_swap_is_rejected_by_associated_data(tmp_path: Path) -> None:
    store, credential_path, _ = build_store(tmp_path)
    store.set("openai", "openai-secret")
    payload = load_payload(credential_path)
    credentials = payload["credentials"]
    credentials["anthropic"] = credentials.pop("openai")  # type: ignore[union-attr]
    save_payload(credential_path, payload)

    with pytest.raises(CredentialStoreUnavailableError):
        store.get("anthropic")


def test_wrong_or_missing_key_fails_closed_without_overwriting_ciphertext(
    tmp_path: Path,
) -> None:
    store, credential_path, key_path = build_store(tmp_path)
    store.set("openai", "openai-secret")
    before = credential_path.read_bytes()

    key_path.write_bytes(base64.b64encode(os.urandom(32)) + b"\n")
    with pytest.raises(CredentialStoreUnavailableError):
        store.get("openai")

    key_path.unlink()
    with pytest.raises(CredentialStoreUnavailableError):
        store.fingerprint("openai")
    with pytest.raises(CredentialStoreUnavailableError):
        store.set("anthropic", "anthropic-secret")
    assert credential_path.read_bytes() == before
    assert not key_path.exists()


def test_delete_does_not_require_decryption_or_key(tmp_path: Path) -> None:
    store, credential_path, key_path = build_store(tmp_path)
    store.set("openai", "openai-secret")
    key_path.unlink()

    store.delete("openai")
    store.delete("openai")

    assert load_payload(credential_path)["credentials"] == {}


@pytest.mark.parametrize("secret", ["", " ", "\t\r\n"])
def test_blank_secret_is_rejected_without_creating_files(
    tmp_path: Path,
    secret: str,
) -> None:
    store, credential_path, key_path = build_store(tmp_path)

    with pytest.raises(InvalidCredentialSecretError):
        store.set("openai", secret)

    assert not credential_path.exists()
    assert not key_path.exists()


@pytest.mark.parametrize(
    "provider_id",
    ["", "unknown", "mcp:bad:bearer", "mcp:11111111-1111-4111-8111-111111111111:token", 1, None],
)
def test_unknown_provider_is_rejected_before_file_access(
    tmp_path: Path,
    provider_id: object,
) -> None:
    store, credential_path, _ = build_store(tmp_path)

    with pytest.raises(UnsupportedCredentialProviderError):
        store.get(provider_id)  # type: ignore[arg-type]

    assert not credential_path.parent.exists()


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b'{"version":3,"algorithm":"AES-256-GCM","credentials":{}}',
        b'{"version":1,"algorithm":"wrong","credentials":{}}',
        b'{"version":1,"algorithm":"AES-256-GCM","credentials":{},"extra":1}',
        b'{"version":1,"algorithm":"AES-256-GCM","credentials":{"unknown":{}}}',
        b'{"version":1,"version":1,"algorithm":"AES-256-GCM","credentials":{}}',
    ],
)
def test_corrupt_or_noncanonical_file_fails_closed(
    tmp_path: Path,
    raw: bytes,
) -> None:
    store, credential_path, _ = build_store(tmp_path)
    credential_path.parent.mkdir(parents=True)
    credential_path.write_bytes(raw)

    with pytest.raises(CredentialStoreUnavailableError) as raised:
        store.get("openai")

    assert str(raised.value) == "Secure credential storage is unavailable."
    assert raw.decode("utf-8", errors="ignore") not in repr(raised.value)


def test_oversized_file_fails_closed(tmp_path: Path) -> None:
    store, credential_path, _ = build_store(tmp_path)
    credential_path.parent.mkdir(parents=True)
    credential_path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(CredentialStoreUnavailableError):
        store.get("openai")


def test_failed_auth_replace_preserves_prior_credential_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, credential_path, _ = build_store(tmp_path)
    store.set("openai", "old-secret")
    before = credential_path.read_bytes()
    real_replace = store_module.os.replace

    def fail_auth_replace(source: object, destination: object) -> None:
        if Path(destination) == credential_path:
            raise OSError("replace failed")
        real_replace(source, destination)

    monkeypatch.setattr(store_module.os, "replace", fail_auth_replace)
    with pytest.raises(CredentialStoreUnavailableError):
        store.set("openai", "new-secret")

    assert credential_path.read_bytes() == before
    assert store.get("openai") == "old-secret"
    assert list(credential_path.parent.glob("auth.json.tmp.*")) == []


def test_failed_initial_key_replace_creates_no_auth_or_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, credential_path, key_path = build_store(tmp_path)

    def fail_replace(source: object, destination: object) -> None:
        del source, destination
        raise OSError("replace failed")

    monkeypatch.setattr(store_module.os, "replace", fail_replace)
    with pytest.raises(CredentialStoreUnavailableError):
        store.set("openai", "openai-secret")

    assert not credential_path.exists()
    assert not key_path.exists()
    assert list(key_path.parent.glob("credential.key.tmp.*")) == []
