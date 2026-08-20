"""Secure orchestration for provider credential lifecycle operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
from pathlib import Path
from typing import Protocol

import httpx

from .credentials import CredentialStore, KeyringCredentialStore
from .models import (
    ErrorCode,
    ProviderId,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
)
from .provider_state import (
    JsonProviderStateRepository,
    ProviderState,
    ProviderStateRepository,
)
from .providers import ProviderValidationError, ProviderValidator

_CATALOG: tuple[tuple[ProviderId, str], ...] = (
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
)
_FAILURE_STATUS = {
    ErrorCode.INVALID_CREDENTIALS: ProviderStatus.INVALID_CREDENTIALS,
    ErrorCode.PROVIDER_UNREACHABLE: ProviderStatus.PROVIDER_UNREACHABLE,
    ErrorCode.PROVIDER_TIMEOUT: ProviderStatus.PROVIDER_TIMEOUT,
    ErrorCode.PROVIDER_RATE_LIMITED: ProviderStatus.PROVIDER_RATE_LIMITED,
}


class ProviderConnectionError(Exception):
    """A typed failure whose public representation is fixed by error code."""

    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ProviderConnections(Protocol):
    async def list_providers(self) -> ProviderListResponse: ...

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary: ...

    async def test(self, provider_id: ProviderId) -> ProviderSummary: ...

    async def disconnect(self, provider_id: ProviderId) -> None: ...


class UnavailableProviderConnections:
    """Fail-closed default when the runtime is not explicitly composed."""

    @staticmethod
    def _unavailable() -> ProviderConnectionError:
        return ProviderConnectionError(ErrorCode.CREDENTIAL_STORE_UNAVAILABLE)

    async def list_providers(self) -> ProviderListResponse:
        raise self._unavailable()

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        del provider_id, api_key
        raise self._unavailable()

    async def test(self, provider_id: ProviderId) -> ProviderSummary:
        del provider_id
        raise self._unavailable()

    async def disconnect(self, provider_id: ProviderId) -> None:
        del provider_id
        raise self._unavailable()


@dataclass(frozen=True, slots=True)
class _Snapshot:
    credential: str | None
    state: ProviderState | None


class ProviderConnectionService:
    """Own provider validation and secret/metadata transaction policy.

    Per-provider locks assume one owning desktop backend process. Cross-process
    serialization is intentionally outside this new-install-only runtime.
    """

    def __init__(
        self,
        credential_store: CredentialStore,
        state_repository: ProviderStateRepository,
        validator: ProviderValidator,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._credentials = credential_store
        self._states = state_repository
        self._validator = validator
        self._clock = clock or (lambda: datetime.now(UTC))
        self._locks = {provider_id: asyncio.Lock() for provider_id, _ in _CATALOG}

    async def list_providers(self) -> ProviderListResponse:
        summaries: list[ProviderSummary] = []
        for provider_id, name in _CATALOG:
            async with self._locks[provider_id]:
                snapshot = self._snapshot(provider_id)
                if snapshot is None:
                    raise self._store_unavailable()
                if snapshot.credential is None:
                    summaries.append(self._disconnected(provider_id, name))
                    continue
                if (
                    snapshot.state is None
                    or not self._state_matches_credential(
                        snapshot.state,
                        snapshot.credential,
                    )
                ):
                    raise self._store_unavailable()
                summaries.append(self._summary(provider_id, name, snapshot.state))
        return ProviderListResponse(providers=summaries)

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        async with self._locks[provider_id]:
            validation_error = await self._validate(provider_id, api_key)
            if validation_error is not None:
                raise ProviderConnectionError(validation_error)

            before = self._snapshot(provider_id)
            if before is None:
                raise self._store_unavailable()
            desired = ProviderState(
                provider_id=provider_id,
                status=ProviderStatus.CONNECTED,
                credential_preview=self._preview(api_key),
                credential_fingerprint=self._fingerprint(api_key),
                last_checked_at=self._now(),
            )
            written = self._write_and_verify(provider_id, api_key, desired)
            if not written:
                self._restore_and_verify(provider_id, before)
                raise self._store_unavailable()
            return self._summary(provider_id, self._name(provider_id), desired)

    async def test(self, provider_id: ProviderId) -> ProviderSummary:
        async with self._locks[provider_id]:
            before = self._snapshot(provider_id)
            if before is None:
                raise self._store_unavailable()
            if before.credential is None:
                raise ProviderConnectionError(ErrorCode.NOT_CONNECTED)

            validation_error = await self._validate(
                provider_id,
                before.credential,
            )
            status = (
                ProviderStatus.CONNECTED
                if validation_error is None
                else _FAILURE_STATUS[validation_error]
            )
            desired = ProviderState(
                provider_id=provider_id,
                status=status,
                credential_preview=self._preview(before.credential),
                credential_fingerprint=self._fingerprint(before.credential),
                last_checked_at=self._now(),
            )
            if not self._write_state_and_verify(
                provider_id,
                before.credential,
                desired,
            ):
                self._restore_state_and_verify(provider_id, before)
                raise self._store_unavailable()
            if validation_error is not None:
                raise ProviderConnectionError(validation_error)
            return self._summary(provider_id, self._name(provider_id), desired)

    async def disconnect(self, provider_id: ProviderId) -> None:
        async with self._locks[provider_id]:
            before = self._snapshot(provider_id)
            if before is None:
                raise self._store_unavailable()
            failed = False
            try:
                self._credentials.delete(provider_id)
                self._states.delete(provider_id)
                after = self._snapshot(provider_id)
                failed = (
                    after is None
                    or after.credential is not None
                    or after.state is not None
                )
            except Exception:
                failed = True
            if failed:
                self._restore_and_verify(provider_id, before)
                raise self._store_unavailable()

    async def _validate(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ErrorCode | None:
        failure: ErrorCode | None = None
        try:
            await self._validator.validate(provider_id, api_key)
        except ProviderValidationError as error:
            failure = error.code
        except Exception:
            failure = ErrorCode.PROVIDER_UNREACHABLE
        return failure

    def _snapshot(self, provider_id: ProviderId) -> _Snapshot | None:
        failed = False
        credential: str | None = None
        state: ProviderState | None = None
        try:
            credential = self._credentials.get(provider_id)
            state = self._states.get(provider_id)
        except Exception:
            failed = True
        if failed:
            return None
        return _Snapshot(credential, state)

    def _write_and_verify(
        self,
        provider_id: ProviderId,
        credential: str,
        state: ProviderState,
    ) -> bool:
        failed = False
        try:
            self._credentials.set(provider_id, credential)
            self._states.set(state)
            after = self._snapshot(provider_id)
            failed = after != _Snapshot(credential, state)
        except Exception:
            failed = True
        return not failed

    def _restore_and_verify(
        self,
        provider_id: ProviderId,
        snapshot: _Snapshot,
    ) -> bool:
        failed = False
        try:
            if snapshot.credential is None:
                self._credentials.delete(provider_id)
            else:
                self._credentials.set(provider_id, snapshot.credential)
            if snapshot.state is None:
                self._states.delete(provider_id)
            else:
                self._states.set(snapshot.state)
            failed = self._snapshot(provider_id) != snapshot
        except Exception:
            failed = True
        return not failed

    def _write_state_and_verify(
        self,
        provider_id: ProviderId,
        credential: str,
        state: ProviderState,
    ) -> bool:
        failed = False
        try:
            self._states.set(state)
            failed = self._snapshot(provider_id) != _Snapshot(credential, state)
        except Exception:
            failed = True
        return not failed

    def _restore_state_and_verify(
        self,
        provider_id: ProviderId,
        snapshot: _Snapshot,
    ) -> bool:
        failed = False
        try:
            if snapshot.state is None:
                self._states.delete(provider_id)
            else:
                self._states.set(snapshot.state)
            failed = self._snapshot(provider_id) != snapshot
        except Exception:
            failed = True
        return not failed

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
            raise self._store_unavailable()
        return value

    @staticmethod
    def _preview(api_key: str) -> str:
        suffix = api_key[-4:]
        if len(api_key) < 8 or not all(
            character.isascii()
            and (character.isalnum() or character in "_-")
            for character in suffix
        ):
            return "••••"
        return f"••••{suffix}"

    @staticmethod
    def _fingerprint(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @classmethod
    def _state_matches_credential(
        cls,
        state: ProviderState,
        credential: str,
    ) -> bool:
        fingerprint = state.credential_fingerprint
        return type(fingerprint) is str and hmac.compare_digest(
            fingerprint,
            cls._fingerprint(credential),
        )

    @staticmethod
    def _name(provider_id: ProviderId) -> str:
        return "OpenAI" if provider_id == "openai" else "Anthropic"

    @staticmethod
    def _summary(
        provider_id: ProviderId,
        name: str,
        state: ProviderState,
    ) -> ProviderSummary:
        return ProviderSummary(
            id=provider_id,
            name=name,
            connected=True,
            status=state.status,
            credentialPreview=state.credential_preview,
            lastCheckedAt=state.last_checked_at,
        )

    @staticmethod
    def _disconnected(provider_id: ProviderId, name: str) -> ProviderSummary:
        return ProviderSummary(
            id=provider_id,
            name=name,
            connected=False,
            status=ProviderStatus.DISCONNECTED,
            credentialPreview=None,
            lastCheckedAt=None,
        )

    @staticmethod
    def _store_unavailable() -> ProviderConnectionError:
        return ProviderConnectionError(ErrorCode.CREDENTIAL_STORE_UNAVAILABLE)


@dataclass(slots=True)
class ProviderRuntime:
    """Explicit system composition with owned HTTP-client lifecycle."""

    connections: ProviderConnectionService
    http_client: httpx.AsyncClient
    owns_http_client: bool

    async def aclose(self) -> None:
        if self.owns_http_client:
            await self.http_client.aclose()


def create_provider_runtime(
    *,
    credential_store: CredentialStore | None = None,
    state_repository: ProviderStateRepository | None = None,
    state_path: Path | None = None,
    http_client: httpx.AsyncClient | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ProviderRuntime:
    """Compose the provider runtime without accessing a secret or network."""

    if http_client is not None and transport is not None:
        raise ValueError("http_client and transport are mutually exclusive")
    owns_client = http_client is None
    client = (
        http_client
        if http_client is not None
        else httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
            transport=transport,
        )
    )
    store = (
        credential_store
        if credential_store is not None
        else KeyringCredentialStore.from_system()
    )
    states = (
        state_repository
        if state_repository is not None
        else JsonProviderStateRepository(state_path)
    )
    connections = ProviderConnectionService(
        store,
        states,
        ProviderValidator(client),
        clock,
    )
    return ProviderRuntime(connections, client, owns_client)
