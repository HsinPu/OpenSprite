"""Dependency boundary for future secure provider-connection behavior."""

from typing import Protocol

from .models import (
    ErrorCode,
    ProviderId,
    ProviderListResponse,
    ProviderSummary,
)


class ProviderConnectionError(Exception):
    """A typed failure whose public representation is fixed by error code."""

    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ProviderConnections(Protocol):
    """Narrow seam implemented later by provider and credential-store code."""

    async def list_providers(self) -> ProviderListResponse: ...

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary: ...

    async def test(self, provider_id: ProviderId) -> ProviderSummary: ...

    async def disconnect(self, provider_id: ProviderId) -> None: ...


class UnavailableProviderConnections:
    """Fail-closed default until secure storage and provider adapters exist."""

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
