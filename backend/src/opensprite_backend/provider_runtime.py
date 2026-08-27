"""Concrete composition for the Provider connection and inference runtime."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from .app_paths import AppPaths, build_app_paths
from .credentials import CredentialStore, EncryptedJsonCredentialStore
from .inference.native_gateway import NativeModelGateway
from .provider_connections import ProviderConnectionService
from .provider_state import (
    JsonProviderStateRepository,
    ProviderStateRepository,
)
from .providers import ProviderOperationLocks, ProviderValidator


@dataclass(slots=True)
class ProviderRuntime:
    """Explicit system composition with owned HTTP-client lifecycle."""

    connections: ProviderConnectionService
    model_gateway: NativeModelGateway
    operation_locks: ProviderOperationLocks
    http_client: httpx.AsyncClient
    owns_http_client: bool

    async def aclose(self) -> None:
        if self.owns_http_client:
            await self.http_client.aclose()


def create_provider_runtime(
    *,
    app_paths: AppPaths | None = None,
    credential_store: CredentialStore | None = None,
    state_repository: ProviderStateRepository | None = None,
    http_client: httpx.AsyncClient | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], datetime] | None = None,
    operation_locks: ProviderOperationLocks | None = None,
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
    paths = app_paths if app_paths is not None else build_app_paths()
    store = (
        credential_store
        if credential_store is not None
        else EncryptedJsonCredentialStore(
            paths.credential_file,
            paths.credential_key_file,
        )
    )
    states = state_repository
    if states is None:
        states = JsonProviderStateRepository(paths.provider_state_file)
    locks = operation_locks or ProviderOperationLocks()
    connections = ProviderConnectionService(
        store,
        states,
        ProviderValidator(client),
        clock,
        locks,
    )
    return ProviderRuntime(
        connections=connections,
        model_gateway=NativeModelGateway(store, client, locks),
        operation_locks=locks,
        http_client=client,
        owns_http_client=owns_client,
    )
