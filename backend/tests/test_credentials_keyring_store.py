"""Security regression tests for the operating-system credential boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from keyring.errors import PasswordDeleteError

from opensprite_backend.credentials import (
    CredentialStore,
    CredentialStoreError,
    CredentialStoreUnavailableError,
    InvalidCredentialSecretError,
    KeyringCredentialStore,
    UnsupportedCredentialProviderError,
)

SENTINEL_SECRET = "sentinel-secret-must-never-leak"


class RecordingKeyringBackend:
    priority = 5

    def __init__(self) -> None:
        self.passwords: dict[tuple[str, str], str] = {}
        self.calls: list[tuple[str, ...]] = []
        self.failure: Exception | None = None
        self.fail_on: str | None = None

    def maybe_fail(self, operation: str) -> None:
        if self.failure is not None and self.fail_on == operation:
            raise self.failure

    def get_password(self, service_name: str, username: str) -> str | None:
        self.calls.append(("get", service_name, username))
        self.maybe_fail("get")
        return self.passwords.get((service_name, username))

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None:
        self.calls.append(("set", service_name, username))
        self.maybe_fail("set")
        self.passwords[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.calls.append(("delete", service_name, username))
        self.maybe_fail("delete")
        try:
            del self.passwords[(service_name, username)]
        except KeyError as error:
            raise PasswordDeleteError("credential missing") from error


class WinVaultKeyring(RecordingKeyringBackend):
    pass


WinVaultKeyring.__module__ = "keyring.backends.Windows"


class SecretServiceKeyring(RecordingKeyringBackend):
    pass


SecretServiceKeyring.__module__ = "keyring.backends.SecretService"
SecretServiceKeyring.__qualname__ = "Keyring"


class FakeKeyringFacade:
    def __init__(
        self,
        backend: object | None = None,
        global_backend: RecordingKeyringBackend | None = None,
    ) -> None:
        self.backend = backend if backend is not None else WinVaultKeyring()
        self.global_backend = (
            global_backend
            if global_backend is not None
            else RecordingKeyringBackend()
        )
        self.calls: list[tuple[str, ...]] = []
        self.passwords: dict[tuple[str, str], str] = {}
        if isinstance(self.backend, RecordingKeyringBackend):
            self.backend.calls = self.calls
            self.backend.passwords = self.passwords

    @property
    def failure(self) -> Exception | None:
        if isinstance(self.backend, RecordingKeyringBackend):
            return self.backend.failure
        return None

    @failure.setter
    def failure(self, value: Exception | None) -> None:
        if isinstance(self.backend, RecordingKeyringBackend):
            self.backend.failure = value

    @property
    def fail_on(self) -> str | None:
        if isinstance(self.backend, RecordingKeyringBackend):
            return self.backend.fail_on
        return None

    @fail_on.setter
    def fail_on(self, value: str | None) -> None:
        if isinstance(self.backend, RecordingKeyringBackend):
            self.backend.fail_on = value

    def get_keyring(self) -> object:
        self.calls.append(("preflight",))
        if self.failure is not None and self.fail_on == "preflight":
            raise self.failure
        return self.backend

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.global_backend.get_password(service_name, username)

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None:
        self.global_backend.set_password(service_name, username, password)

    def delete_password(self, service_name: str, username: str) -> None:
        self.global_backend.delete_password(service_name, username)


def store_for(
    facade: FakeKeyringFacade,
    platform: str = "win32",
) -> KeyringCredentialStore:
    return KeyringCredentialStore(cast(Any, facade), platform)


@pytest.mark.parametrize(
    ("platform", "backend"),
    [
        ("win32", WinVaultKeyring()),
        ("linux", SecretServiceKeyring()),
    ],
)
def test_preflight_accepts_only_documented_native_backend_identity(
    platform: str,
    backend: object,
) -> None:
    store_for(FakeKeyringFacade(backend), platform).preflight()


@pytest.mark.parametrize("provider_id", ["openai", "anthropic", "openrouter"])
def test_set_get_and_delete_use_fixed_names(provider_id: str) -> None:
    facade = FakeKeyringFacade()
    store: CredentialStore = store_for(facade)

    store.set(provider_id, "previous-secret")
    store.set(provider_id, SENTINEL_SECRET)
    assert store.get(provider_id) == SENTINEL_SECRET
    store.delete(provider_id)
    assert store.get(provider_id) is None

    expected_name = f"provider.{provider_id}.api-key"
    assert ("set", "OpenSprite", expected_name) in facade.calls
    assert ("delete", "OpenSprite", expected_name) in facade.calls


def test_delete_is_idempotent_when_credential_is_missing() -> None:
    facade = FakeKeyringFacade()
    store = store_for(facade)

    store.delete("openai")
    store.delete("openai")

    assert not any(call[0] == "delete" for call in facade.calls)


@pytest.mark.parametrize(
    ("platform", "backend"),
    [
        ("darwin", WinVaultKeyring()),
        ("win32", SecretServiceKeyring()),
        ("win32", type("FailBackend", (), {"priority": 0})()),
    ],
)
def test_preflight_fails_closed_for_unavailable_or_unapproved_backend(
    platform: str,
    backend: object,
) -> None:
    with pytest.raises(CredentialStoreUnavailableError) as raised:
        store_for(FakeKeyringFacade(backend), platform).preflight()

    assert_detached(
        raised.value,
        "Secure credential storage is unavailable.",
    )


def test_preflight_sanitizes_backend_failure() -> None:
    facade = FakeKeyringFacade()
    facade.failure = RuntimeError(SENTINEL_SECRET)
    facade.fail_on = "preflight"

    with pytest.raises(CredentialStoreUnavailableError) as raised:
        store_for(facade).preflight()

    assert_sanitized(raised.value)


def test_preflight_sanitizes_priority_failure() -> None:
    class ExplodingPriorityBackend(RecordingKeyringBackend):
        @property
        def priority(self) -> float:
            raise RuntimeError(SENTINEL_SECRET)

    ExplodingPriorityBackend.__module__ = "keyring.backends.Windows"
    ExplodingPriorityBackend.__qualname__ = "WinVaultKeyring"

    with pytest.raises(CredentialStoreUnavailableError) as raised:
        store_for(FakeKeyringFacade(ExplodingPriorityBackend())).preflight()

    assert_sanitized(raised.value)


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_operations_use_exact_preflight_backend_instance(operation: str) -> None:
    approved_backend = WinVaultKeyring()
    unapproved_global_backend = RecordingKeyringBackend()
    facade = FakeKeyringFacade(
        approved_backend,
        global_backend=unapproved_global_backend,
    )
    store = store_for(facade)
    credential = ("OpenSprite", "provider.openai.api-key")

    if operation in {"get", "delete"}:
        facade.passwords[credential] = SENTINEL_SECRET

    if operation == "get":
        assert store.get("openai") == SENTINEL_SECRET
    elif operation == "set":
        store.set("openai", SENTINEL_SECRET)
        assert facade.passwords[credential] == SENTINEL_SECRET
    else:
        store.delete("openai")
        assert credential not in facade.passwords

    assert unapproved_global_backend.calls == []


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
@pytest.mark.parametrize(
    "provider_id",
    [
        "",
        "OpenAI",
        "openai ",
        "../openai",
        "openai%00",
        "anthropic\x00",
        None,
        b"openai",
    ],
)
def test_unsupported_provider_is_rejected_before_keyring_call(
    operation: str,
    provider_id: object,
) -> None:
    facade = FakeKeyringFacade()
    store = store_for(facade)

    with pytest.raises(UnsupportedCredentialProviderError) as raised:
        if operation == "get":
            store.get(cast(Any, provider_id))
        elif operation == "set":
            store.set(cast(Any, provider_id), SENTINEL_SECRET)
        else:
            store.delete(cast(Any, provider_id))

    assert facade.calls == []
    assert_detached(raised.value, "Unsupported credential provider.")


@pytest.mark.parametrize("secret", ["", " ", "\t\r\n", "\u2003"])
def test_blank_secret_is_rejected_before_keyring_call(secret: str) -> None:
    facade = FakeKeyringFacade()

    with pytest.raises(InvalidCredentialSecretError) as raised:
        store_for(facade).set("openai", secret)

    assert facade.calls == []
    assert_detached(raised.value, "Credential secret must not be blank.")


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_backend_operation_errors_do_not_expose_secret(operation: str) -> None:
    facade = FakeKeyringFacade()
    store = store_for(facade)
    if operation == "delete":
        facade.passwords[("OpenSprite", "provider.openai.api-key")] = "present"
    facade.failure = RuntimeError(SENTINEL_SECRET)
    facade.fail_on = operation

    with pytest.raises(CredentialStoreUnavailableError) as raised:
        if operation == "get":
            store.get("openai")
        elif operation == "set":
            store.set("openai", SENTINEL_SECRET)
        else:
            store.delete("openai")

    assert_sanitized(raised.value)


def test_password_delete_error_for_existing_credential_is_sanitized() -> None:
    class FailingDeleteBackend(WinVaultKeyring):
        def delete_password(self, service_name: str, username: str) -> None:
            self.calls.append(("delete", service_name, username))
            raise PasswordDeleteError(SENTINEL_SECRET)

    FailingDeleteBackend.__module__ = "keyring.backends.Windows"
    FailingDeleteBackend.__qualname__ = "WinVaultKeyring"
    facade = FakeKeyringFacade(FailingDeleteBackend())
    facade.passwords[("OpenSprite", "provider.openai.api-key")] = "present"

    with pytest.raises(CredentialStoreUnavailableError) as raised:
        store_for(facade).delete("openai")

    assert_sanitized(raised.value)


def test_unexpected_backend_value_fails_closed_without_exposure() -> None:
    facade = FakeKeyringFacade()
    facade.passwords[("OpenSprite", "provider.openai.api-key")] = cast(
        Any,
        SENTINEL_SECRET.encode(),
    )

    with pytest.raises(CredentialStoreUnavailableError) as raised:
        store_for(facade).get("openai")

    assert_sanitized(raised.value)


def test_delete_error_is_idempotent_if_backend_reports_already_missing() -> None:
    class ConcurrentDeleteBackend(WinVaultKeyring):
        def delete_password(self, service_name: str, username: str) -> None:
            self.calls.append(("delete", service_name, username))
            self.passwords.pop((service_name, username), None)
            raise PasswordDeleteError(SENTINEL_SECRET)

    ConcurrentDeleteBackend.__module__ = "keyring.backends.Windows"
    ConcurrentDeleteBackend.__qualname__ = "WinVaultKeyring"
    facade = FakeKeyringFacade(ConcurrentDeleteBackend())
    facade.passwords[("OpenSprite", "provider.openai.api-key")] = "present"

    store_for(facade).delete("openai")


def test_no_secret_file_or_serialized_error_is_created(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    facade = FakeKeyringFacade()
    facade.failure = RuntimeError(SENTINEL_SECRET)
    facade.fail_on = "set"

    with pytest.raises(CredentialStoreError) as raised:
        store_for(facade).set("anthropic", SENTINEL_SECRET)

    serialized_error = json.dumps({"error": str(raised.value)})
    output = capsys.readouterr()
    assert list(tmp_path.rglob("*")) == []
    assert SENTINEL_SECRET not in serialized_error
    assert SENTINEL_SECRET not in repr(raised.value)
    assert SENTINEL_SECRET not in output.out
    assert SENTINEL_SECRET not in output.err


def assert_sanitized(error: Exception) -> None:
    assert_detached(error, "Secure credential storage is unavailable.")
    assert SENTINEL_SECRET not in str(error)
    assert SENTINEL_SECRET not in repr(error)


def assert_detached(error: Exception, expected_message: str) -> None:
    assert str(error) == expected_message
    assert error.__context__ is None
    assert error.__cause__ is None
