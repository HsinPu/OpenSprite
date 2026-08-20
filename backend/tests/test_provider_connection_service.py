"""Offline transaction tests for provider connection orchestration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi.testclient import TestClient
import pytest

from opensprite_backend import create_app
from opensprite_backend.credentials import CredentialStore, KeyringCredentialStore
from opensprite_backend.models import ErrorCode, ProviderId, ProviderStatus
from opensprite_backend.provider_connections import (
    ProviderConnectionError,
    ProviderConnectionService,
    create_provider_runtime,
)
from opensprite_backend.provider_state import (
    JsonProviderStateRepository,
    ProviderState,
    ProviderStateRepository,
)
from opensprite_backend.providers import ProviderValidationError, ProviderValidator

NOW = datetime(2026, 8, 20, 10, 15, tzinfo=UTC)
OLD = datetime(2026, 8, 19, 10, 15, tzinfo=UTC)
OLD_SECRET = "old-secret-1234"
NEW_SECRET = "new-secret-5678"


class FakeCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.fail_once: str | None = None
        self.calls: list[tuple[str, str]] = []

    def _fail(self, operation: str) -> None:
        if self.fail_once == operation:
            self.fail_once = None
            raise RuntimeError(f"private-{operation}-{NEW_SECRET}")

    def get(self, provider_id: str) -> str | None:
        self.calls.append(("get", provider_id))
        self._fail("get")
        return self.values.get(provider_id)

    def set(self, provider_id: str, secret: str) -> None:
        self.calls.append(("set", provider_id))
        self.values[provider_id] = secret
        self._fail("set")

    def delete(self, provider_id: str) -> None:
        self.calls.append(("delete", provider_id))
        self.values.pop(provider_id, None)
        self._fail("delete")


class FakeStateRepository:
    def __init__(self, credentials: FakeCredentialStore | None = None) -> None:
        self.values: dict[str, ProviderState] = {}
        self.fail_once: str | None = None
        self.fail_always: str | None = None
        self.mutate_credential_on_set: tuple[str, str] | None = None
        self.credentials = credentials

    def _fail(self, operation: str) -> None:
        if self.fail_always == operation:
            raise RuntimeError(f"private-{operation}-{NEW_SECRET}")
        if self.fail_once == operation:
            self.fail_once = None
            raise RuntimeError(f"private-{operation}-{NEW_SECRET}")

    def get(self, provider_id: ProviderId) -> ProviderState | None:
        self._fail("get")
        return self.values.get(provider_id)

    def set(self, state: ProviderState) -> None:
        self.values[state.provider_id] = state
        if self.mutate_credential_on_set is not None:
            provider_id, secret = self.mutate_credential_on_set
            assert self.credentials is not None
            self.credentials.values[provider_id] = secret
            self.mutate_credential_on_set = None
        self._fail("set")

    def delete(self, provider_id: ProviderId) -> None:
        self.values.pop(provider_id, None)
        self._fail("delete")


class FakeValidator:
    def __init__(self, failure: ErrorCode | None = None) -> None:
        self.failure = failure
        self.seen: list[tuple[ProviderId, str]] = []

    async def validate(self, provider_id: ProviderId, api_key: str) -> None:
        self.seen.append((provider_id, api_key))
        if self.failure is not None:
            raise ProviderValidationError(self.failure)


def old_state(
    status: ProviderStatus = ProviderStatus.CONNECTED,
) -> ProviderState:
    return ProviderState(
        provider_id="openai",
        status=status,
        credential_preview="••••1234",
        credential_fingerprint=hashlib.sha256(OLD_SECRET.encode()).hexdigest(),
        last_checked_at=OLD,
    )


def service(
    credentials: CredentialStore,
    states: ProviderStateRepository,
    validator: FakeValidator,
) -> ProviderConnectionService:
    return ProviderConnectionService(
        credentials,
        states,
        cast(ProviderValidator, validator),
        clock=lambda: NOW,
    )


def run(coroutine: object) -> object:
    return asyncio.run(coroutine)  # type: ignore[arg-type]


def connected_fixture() -> tuple[FakeCredentialStore, FakeStateRepository]:
    credentials = FakeCredentialStore()
    credentials.values["openai"] = OLD_SECRET
    states = FakeStateRepository(credentials)
    states.values["openai"] = old_state()
    return credentials, states


def assert_no_credential_mutations(credentials: FakeCredentialStore) -> None:
    assert [
        call for call in credentials.calls if call[0] in {"set", "delete"}
    ] == []


@pytest.mark.parametrize(
    "failure",
    [
        ErrorCode.INVALID_CREDENTIALS,
        ErrorCode.PROVIDER_RATE_LIMITED,
        ErrorCode.PROVIDER_TIMEOUT,
        ErrorCode.PROVIDER_UNREACHABLE,
    ],
)
def test_candidate_failure_preserves_existing_secret_and_state(
    failure: ErrorCode,
) -> None:
    credentials, states = connected_fixture()
    before = states.values["openai"]
    runtime = service(credentials, states, FakeValidator(failure))

    with pytest.raises(ProviderConnectionError) as raised:
        run(runtime.connect("openai", NEW_SECRET))

    assert raised.value.code is failure
    assert credentials.values["openai"] == OLD_SECRET
    assert states.values["openai"] == before
    assert not any(call[0] == "set" for call in credentials.calls)


@pytest.mark.parametrize("failure_target", ["credential", "state"])
def test_partial_connect_failure_rolls_back_prior_secret_and_state(
    failure_target: str,
) -> None:
    credentials, states = connected_fixture()
    before = states.values["openai"]
    if failure_target == "credential":
        credentials.fail_once = "set"
    else:
        states.fail_once = "set"
    runtime = service(credentials, states, FakeValidator())

    with pytest.raises(ProviderConnectionError) as raised:
        run(runtime.connect("openai", NEW_SECRET))

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert credentials.values["openai"] == OLD_SECRET
    assert states.values["openai"] == before
    assert NEW_SECRET not in repr(raised.value)


def test_successful_connect_replaces_after_validation() -> None:
    credentials, states = connected_fixture()
    validator = FakeValidator()
    runtime = service(credentials, states, validator)

    summary = run(runtime.connect("openai", NEW_SECRET))

    assert validator.seen == [("openai", NEW_SECRET)]
    assert credentials.values["openai"] == NEW_SECRET
    assert states.values["openai"].status is ProviderStatus.CONNECTED
    assert summary.credential_preview == "••••5678"
    assert NEW_SECRET not in summary.model_dump_json()


def test_repeated_put_revalidates_even_same_candidate() -> None:
    credentials = FakeCredentialStore()
    states = FakeStateRepository()
    validator = FakeValidator()
    runtime = service(credentials, states, validator)

    run(runtime.connect("anthropic", NEW_SECRET))
    run(runtime.connect("anthropic", NEW_SECRET))

    assert validator.seen == [
        ("anthropic", NEW_SECRET),
        ("anthropic", NEW_SECRET),
    ]


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (ErrorCode.INVALID_CREDENTIALS, ProviderStatus.INVALID_CREDENTIALS),
        (ErrorCode.PROVIDER_RATE_LIMITED, ProviderStatus.PROVIDER_RATE_LIMITED),
        (ErrorCode.PROVIDER_TIMEOUT, ProviderStatus.PROVIDER_TIMEOUT),
        (ErrorCode.PROVIDER_UNREACHABLE, ProviderStatus.PROVIDER_UNREACHABLE),
    ],
)
def test_stored_credential_test_persists_failure_status_before_raising(
    failure: ErrorCode,
    status: ProviderStatus,
) -> None:
    credentials, states = connected_fixture()
    runtime = service(credentials, states, FakeValidator(failure))

    with pytest.raises(ProviderConnectionError) as raised:
        run(runtime.test("openai"))

    assert raised.value.code is failure
    assert credentials.values["openai"] == OLD_SECRET
    assert states.values["openai"].status is status
    assert states.values["openai"].last_checked_at == NOW
    assert_no_credential_mutations(credentials)


def test_stored_credential_test_success_only_updates_state() -> None:
    credentials, states = connected_fixture()

    summary = run(service(credentials, states, FakeValidator()).test("openai"))

    assert summary.status is ProviderStatus.CONNECTED
    assert states.values["openai"].last_checked_at == NOW
    assert_no_credential_mutations(credentials)


def test_missing_stored_key_is_not_connected_and_makes_no_provider_call() -> None:
    credentials = FakeCredentialStore()
    states = FakeStateRepository()
    validator = FakeValidator()

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, validator).test("anthropic"))

    assert raised.value.code is ErrorCode.NOT_CONNECTED
    assert validator.seen == []
    assert_no_credential_mutations(credentials)


def test_test_metadata_failure_restores_prior_state() -> None:
    credentials, states = connected_fixture()
    before = states.values["openai"]
    states.fail_once = "set"

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, FakeValidator()).test("openai"))

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert credentials.values["openai"] == OLD_SECRET
    assert states.values["openai"] == before
    assert_no_credential_mutations(credentials)


@pytest.mark.parametrize(
    "failure",
    [None, ErrorCode.INVALID_CREDENTIALS],
    ids=["success", "provider-failure"],
)
def test_stored_credential_test_accepts_read_only_credential_store(
    failure: ErrorCode | None,
) -> None:
    class ReadOnlyCredentialStore:
        def __init__(self) -> None:
            self.mutations = 0

        def get(self, provider_id: str) -> str | None:
            return OLD_SECRET if provider_id == "openai" else None

        def set(self, provider_id: str, secret: str) -> None:
            del provider_id, secret
            self.mutations += 1
            raise AssertionError("POST test attempted credential write")

        def delete(self, provider_id: str) -> None:
            del provider_id
            self.mutations += 1
            raise AssertionError("POST test attempted credential delete")

    credentials = ReadOnlyCredentialStore()
    states = FakeStateRepository()
    states.values["openai"] = old_state()
    runtime = service(credentials, states, FakeValidator(failure))

    if failure is None:
        summary = run(runtime.test("openai"))
        assert summary.status is ProviderStatus.CONNECTED
    else:
        with pytest.raises(ProviderConnectionError) as raised:
            run(runtime.test("openai"))
        assert raised.value.code is failure
    assert credentials.mutations == 0


@pytest.mark.parametrize(
    "failure",
    [None, ErrorCode.PROVIDER_UNREACHABLE],
    ids=["success", "provider-failure"],
)
def test_stored_credential_test_uses_keyring_in_read_only_mode(
    failure: ErrorCode | None,
) -> None:
    class WinVaultKeyring:
        priority = 5

        def __init__(self) -> None:
            self.mutations = 0

        def get_password(self, service_name: str, username: str) -> str | None:
            assert service_name == "OpenSprite"
            assert username == "provider.openai.api-key"
            return OLD_SECRET

        def set_password(
            self,
            service_name: str,
            username: str,
            password: str,
        ) -> None:
            del service_name, username, password
            self.mutations += 1
            raise AssertionError("POST test attempted keyring write")

        def delete_password(self, service_name: str, username: str) -> None:
            del service_name, username
            self.mutations += 1
            raise AssertionError("POST test attempted keyring delete")

    WinVaultKeyring.__module__ = "keyring.backends.Windows"
    WinVaultKeyring.__qualname__ = "WinVaultKeyring"
    backend = WinVaultKeyring()

    class Facade:
        @staticmethod
        def get_keyring() -> object:
            return backend

    keyring_store = KeyringCredentialStore(cast(Any, Facade()), "win32")
    states = FakeStateRepository()
    states.values["openai"] = old_state()
    runtime = service(keyring_store, states, FakeValidator(failure))

    if failure is None:
        summary = run(runtime.test("openai"))
        assert summary.status is ProviderStatus.CONNECTED
    else:
        with pytest.raises(ProviderConnectionError) as raised:
            run(runtime.test("openai"))
        assert raised.value.code is failure
    assert backend.mutations == 0


def test_test_credential_mutation_during_state_write_fails_closed() -> None:
    credentials, states = connected_fixture()
    changed_secret = "changed-outside-store-9999"
    states.mutate_credential_on_set = ("openai", changed_secret)
    states.fail_once = "set"
    runtime = service(credentials, states, FakeValidator())

    with pytest.raises(ProviderConnectionError) as raised:
        run(runtime.test("openai"))

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert credentials.values["openai"] == changed_secret
    assert states.values["openai"] == old_state()
    assert_no_credential_mutations(credentials)
    with pytest.raises(ProviderConnectionError) as listed:
        run(runtime.list_providers())
    assert listed.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE


def test_test_unprovable_state_rollback_never_calls_credential_mutation() -> None:
    credentials, states = connected_fixture()
    changed_secret = "changed-during-failed-rollback-9999"
    states.mutate_credential_on_set = ("openai", changed_secret)
    states.fail_always = "set"
    runtime = service(credentials, states, FakeValidator())

    with pytest.raises(ProviderConnectionError) as raised:
        run(runtime.test("openai"))

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert credentials.values["openai"] == changed_secret
    assert_no_credential_mutations(credentials)
    with pytest.raises(ProviderConnectionError) as listed:
        run(runtime.list_providers())
    assert listed.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE


def test_delete_is_idempotent_and_removes_secret_and_state() -> None:
    credentials, states = connected_fixture()
    runtime = service(credentials, states, FakeValidator())

    run(runtime.disconnect("openai"))
    run(runtime.disconnect("openai"))

    assert credentials.values == {}
    assert states.values == {}


def test_partial_delete_failure_rolls_back_secret_and_state() -> None:
    credentials, states = connected_fixture()
    before = states.values["openai"]
    states.fail_once = "delete"

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, FakeValidator()).disconnect("openai"))

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert credentials.values["openai"] == OLD_SECRET
    assert states.values["openai"] == before


def test_unprovable_rollback_never_returns_success_or_private_error() -> None:
    class UnverifiableCredentialStore(FakeCredentialStore):
        def set(self, provider_id: str, secret: str) -> None:
            self.values[provider_id] = secret
            raise RuntimeError(f"private-write-{secret}")

    credentials = UnverifiableCredentialStore()
    credentials.values["openai"] = OLD_SECRET
    states = FakeStateRepository()
    states.values["openai"] = old_state()

    with pytest.raises(ProviderConnectionError) as raised:
        run(
            service(credentials, states, FakeValidator()).connect(
                "openai",
                NEW_SECRET,
            )
        )

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert raised.value.__context__ is None
    assert NEW_SECRET not in repr(raised.value)


def test_list_is_fixed_order_and_reconciles_absent_credentials() -> None:
    credentials, states = connected_fixture()
    states.values["anthropic"] = ProviderState(
        provider_id="anthropic",
        status=ProviderStatus.INVALID_CREDENTIALS,
        credential_preview="••••stale",
        credential_fingerprint=hashlib.sha256(b"stale-secret").hexdigest(),
        last_checked_at=OLD,
    )

    result = run(service(credentials, states, FakeValidator()).list_providers())

    assert [(item.id, item.name) for item in result.providers] == [
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
    ]
    assert result.providers[0].connected is True
    assert result.providers[1].connected is False
    assert result.providers[1].credential_preview is None


def test_list_fails_closed_for_secret_without_matching_metadata() -> None:
    credentials = FakeCredentialStore()
    credentials.values["openai"] = OLD_SECRET
    states = FakeStateRepository()

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, FakeValidator()).list_providers())

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE


def test_list_fails_closed_for_different_secret_with_same_last_four() -> None:
    credentials, states = connected_fixture()
    credentials.values["openai"] = "different-secret-1234"

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, FakeValidator()).list_providers())

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE


def test_list_fails_closed_when_generic_preview_matches_but_secret_does_not() -> None:
    credentials = FakeCredentialStore()
    credentials.values["openai"] = "xyz"
    states = FakeStateRepository(credentials)
    states.values["openai"] = ProviderState(
        provider_id="openai",
        status=ProviderStatus.CONNECTED,
        credential_preview="••••",
        credential_fingerprint=hashlib.sha256(b"abc").hexdigest(),
        last_checked_at=OLD,
    )

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, FakeValidator()).list_providers())

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE


def test_reloaded_repository_fingerprint_binds_full_credential(
    tmp_path: Path,
) -> None:
    credentials = FakeCredentialStore()
    path = tmp_path / "providers.json"
    runtime = service(
        credentials,
        JsonProviderStateRepository(path),
        FakeValidator(),
    )
    run(runtime.connect("openai", OLD_SECRET))

    reloaded = service(
        credentials,
        JsonProviderStateRepository(path),
        FakeValidator(),
    )
    listed = run(reloaded.list_providers())
    assert listed.providers[0].connected is True

    credentials.values["openai"] = "different-secret-1234"
    with pytest.raises(ProviderConnectionError) as raised:
        run(reloaded.list_providers())
    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE


def test_list_fails_closed_when_metadata_repository_is_unavailable() -> None:
    credentials, states = connected_fixture()
    states.fail_once = "get"

    with pytest.raises(ProviderConnectionError) as raised:
        run(service(credentials, states, FakeValidator()).list_providers())

    assert raised.value.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
    assert NEW_SECRET not in repr(raised.value)


def test_short_key_preview_does_not_persist_or_return_entire_key() -> None:
    credentials = FakeCredentialStore()
    states = FakeStateRepository()
    short_secret = "abc"

    summary = run(
        service(credentials, states, FakeValidator()).connect(
            "anthropic",
            short_secret,
        )
    )

    assert summary.credential_preview == "••••"
    assert short_secret not in repr(states.values["anthropic"])


def test_control_character_suffix_is_not_persisted_in_preview() -> None:
    credentials = FakeCredentialStore()
    states = FakeStateRepository()
    secret = "prefix-abc\n"

    summary = run(
        service(credentials, states, FakeValidator()).connect("openai", secret)
    )

    assert summary.credential_preview == "••••"
    assert "\n" not in repr(states.values["openai"].credential_preview)


def test_runtime_factory_is_offline_until_an_operation_and_owns_client() -> None:
    credentials = FakeCredentialStore()
    states = FakeStateRepository()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": []}, request=request)

    runtime = create_provider_runtime(
        credential_store=credentials,
        state_repository=states,
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    assert calls == 0
    assert runtime.owns_http_client is True

    summary = run(runtime.connections.connect("openai", NEW_SECRET))
    assert summary.status is ProviderStatus.CONNECTED
    assert calls == 1
    run(runtime.aclose())


def test_http_routes_use_composed_runtime_without_secret_echo() -> None:
    credentials = FakeCredentialStore()
    states = FakeStateRepository()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": []}, request=request)

    runtime = create_provider_runtime(
        credential_store=credentials,
        state_repository=states,
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    with TestClient(create_app(runtime.connections)) as client:
        connected = client.put(
            "/api/providers/openai/connection",
            json={"apiKey": NEW_SECRET},
        )
        listed = client.get("/api/providers")
        tested = client.post("/api/providers/openai/connection/test")
        deleted = client.delete("/api/providers/openai/connection")

    assert connected.status_code == 200
    assert listed.status_code == 200
    assert tested.status_code == 200
    assert deleted.status_code == 204
    assert calls == 2
    assert NEW_SECRET not in connected.text
    assert NEW_SECRET not in listed.text
    assert NEW_SECRET not in tested.text
    fingerprint = hashlib.sha256(NEW_SECRET.encode()).hexdigest()
    assert fingerprint not in connected.text
    assert fingerprint not in listed.text
    assert fingerprint not in tested.text
    assert "credentialFingerprint" not in connected.text
    assert "credentialFingerprint" not in listed.text
    assert "credentialFingerprint" not in tested.text
    assert credentials.values == {}
    assert states.values == {}
    run(runtime.aclose())
