"""Secure orchestration for provider credential lifecycle operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
from typing import Protocol

from .credentials import CredentialStore
from .models import (
    ErrorCode,
    OpenRouterModelListResponse,
    ProviderId,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
)
from .provider_state import (
    ProviderState,
    ProviderStateRepository,
)
from .provider_transaction import (
    ProviderTransaction,
    ProviderTransactionJournal,
    ProviderTransactionSide,
)
from .providers import (
    ProviderOperationLocks,
    ProviderValidationError,
)

_CATALOG: tuple[tuple[ProviderId, str], ...] = (
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("openrouter", "OpenRouter"),
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
    async def recover_pending(self) -> None: ...

    async def list_providers(self) -> ProviderListResponse: ...

    async def list_openrouter_models(self) -> OpenRouterModelListResponse: ...

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary: ...

    async def test(self, provider_id: ProviderId) -> ProviderSummary: ...

    async def disconnect(self, provider_id: ProviderId) -> None: ...


class ProviderValidatorOperations(Protocol):
    async def validate(self, provider_id: ProviderId, api_key: str) -> None: ...

    async def list_openrouter_models(
        self,
        api_key: str,
    ) -> OpenRouterModelListResponse: ...


class UnavailableProviderConnections:
    """Fail-closed default when the runtime is not explicitly composed."""

    @staticmethod
    def _unavailable() -> ProviderConnectionError:
        return ProviderConnectionError(ErrorCode.CREDENTIAL_STORE_UNAVAILABLE)

    async def list_providers(self) -> ProviderListResponse:
        raise self._unavailable()

    async def recover_pending(self) -> None:
        raise self._unavailable()

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
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
        validator: ProviderValidatorOperations,
        transaction_journal: ProviderTransactionJournal,
        clock: Callable[[], datetime] | None = None,
        operation_locks: ProviderOperationLocks | None = None,
    ) -> None:
        self._credentials = credential_store
        self._states = state_repository
        self._validator = validator
        self._transactions = transaction_journal
        self._clock = clock or (lambda: datetime.now(UTC))
        self._operation_locks = operation_locks or ProviderOperationLocks()

    async def list_providers(self) -> ProviderListResponse:
        await self.recover_pending()
        summaries: list[ProviderSummary] = []
        for provider_id, name in _CATALOG:
            async with self._operation_locks.hold(provider_id):
                try:
                    fingerprint = self._credentials.fingerprint(provider_id)
                    state = self._states.get(provider_id)
                except Exception:
                    raise self._store_unavailable()
                if fingerprint is None:
                    summaries.append(self._disconnected(provider_id, name))
                    continue
                if (
                    state is None
                    or not self._state_matches_fingerprint(state, fingerprint)
                ):
                    raise self._store_unavailable()
                summaries.append(self._summary(provider_id, name, state))
        return ProviderListResponse(providers=summaries)

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
        await self.recover_pending()
        async with self._operation_locks.hold("openrouter"):
            snapshot = self._snapshot("openrouter")
            if snapshot is None:
                raise self._store_unavailable()
            if snapshot.credential is None:
                raise ProviderConnectionError(ErrorCode.NOT_CONNECTED)
            if (
                snapshot.state is None
                or not self._state_matches_credential(
                    snapshot.state,
                    snapshot.credential,
                )
            ):
                raise self._store_unavailable()

            failure: ErrorCode | None = None
            models: OpenRouterModelListResponse | None = None
            try:
                models = await self._validator.list_openrouter_models(
                    snapshot.credential
                )
            except ProviderValidationError as error:
                failure = error.code
            except Exception:
                failure = ErrorCode.PROVIDER_UNREACHABLE
            if failure is not None:
                raise ProviderConnectionError(failure)
            if models is None:
                raise ProviderConnectionError(ErrorCode.PROVIDER_UNREACHABLE)
            return models

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        await self.recover_pending()
        async with self._operation_locks.hold(provider_id):
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
            if before == _Snapshot(api_key, desired):
                return self._summary(provider_id, self._name(provider_id), desired)
            self._prepare_transaction(self._transaction(provider_id, before, desired))
            written = self._write_and_verify(provider_id, api_key, desired)
            if not written:
                if self._restore_and_verify(provider_id, before):
                    self._clear_transaction()
                raise self._store_unavailable()
            self._clear_transaction()
            self._operation_locks.invalidate(provider_id)
            return self._summary(provider_id, self._name(provider_id), desired)

    async def test(self, provider_id: ProviderId) -> ProviderSummary:
        await self.recover_pending()
        async with self._operation_locks.hold(provider_id):
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
        await self.recover_pending()
        async with self._operation_locks.hold(provider_id):
            before = self._snapshot(provider_id)
            if before is None:
                raise self._store_unavailable()
            if before.credential is None and before.state is None:
                return
            self._prepare_transaction(self._transaction(provider_id, before, None))
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
                if self._restore_and_verify(provider_id, before):
                    self._clear_transaction()
                raise self._store_unavailable()
            self._clear_transaction()
            self._operation_locks.invalidate(provider_id)

    async def recover_pending(self) -> None:
        try:
            transaction = self._transactions.get()
        except Exception:
            raise self._store_unavailable()
        if transaction is None:
            return
        async with self._operation_locks.hold(transaction.provider_id):
            try:
                credential_fingerprint = self._credentials.fingerprint(
                    transaction.provider_id
                )
                target = (
                    transaction.after
                    if credential_fingerprint == transaction.after.fingerprint
                    else transaction.before
                    if credential_fingerprint == transaction.before.fingerprint
                    else None
                )
                if target is None:
                    raise self._store_unavailable()
                if target.state is None:
                    self._states.delete(transaction.provider_id)
                else:
                    self._states.set(target.state)
                if (
                    self._credentials.fingerprint(transaction.provider_id)
                    != target.fingerprint
                    or self._states.get(transaction.provider_id) != target.state
                ):
                    raise self._store_unavailable()
                self._transactions.clear()
                self._operation_locks.invalidate(transaction.provider_id)
            except ProviderConnectionError:
                raise
            except Exception:
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

    def _transaction(
        self,
        provider_id: ProviderId,
        before: _Snapshot,
        after_state: ProviderState | None,
    ) -> ProviderTransaction:
        return ProviderTransaction(
            provider_id=provider_id,
            before=self._transaction_side(before.credential, before.state),
            after=ProviderTransactionSide(
                fingerprint=(
                    None
                    if after_state is None
                    else after_state.credential_fingerprint
                ),
                state=after_state,
            ),
        )

    @classmethod
    def _transaction_side(
        cls,
        credential: str | None,
        state: ProviderState | None,
    ) -> ProviderTransactionSide:
        return ProviderTransactionSide(
            fingerprint=None if credential is None else cls._fingerprint(credential),
            state=state,
        )

    def _prepare_transaction(self, transaction: ProviderTransaction) -> None:
        try:
            self._transactions.set(transaction)
        except Exception:
            raise self._store_unavailable()

    def _clear_transaction(self) -> None:
        try:
            self._transactions.clear()
        except Exception:
            raise self._store_unavailable()

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
        return cls._state_matches_fingerprint(
            state,
            cls._fingerprint(credential),
        )

    @staticmethod
    def _state_matches_fingerprint(
        state: ProviderState,
        credential_fingerprint: str,
    ) -> bool:
        fingerprint = state.credential_fingerprint
        return type(fingerprint) is str and hmac.compare_digest(
            fingerprint,
            credential_fingerprint,
        )

    @staticmethod
    def _name(provider_id: ProviderId) -> str:
        return dict(_CATALOG)[provider_id]

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
