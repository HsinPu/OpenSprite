"""Deny-by-default adapter for Windows Credential Manager and Secret Service."""

from __future__ import annotations

import sys
from typing import Final, Protocol, Self, cast

import keyring
from keyring.errors import PasswordDeleteError

from .store import (
    CredentialStoreUnavailableError,
    InvalidCredentialSecretError,
    UnsupportedCredentialProviderError,
)

_SERVICE_NAME: Final = "OpenSprite"
_APPROVED_BACKENDS: Final = {
    "win32": ("keyring.backends.Windows", "WinVaultKeyring"),
    "linux": ("keyring.backends.SecretService", "Keyring"),
}


class _KeyringBackend(Protocol):
    @property
    def priority(self) -> float: ...

    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class _KeyringProvider(Protocol):
    def get_keyring(self) -> _KeyringBackend: ...


def _credential_name(provider_id: str) -> str:
    if type(provider_id) is not str:
        raise UnsupportedCredentialProviderError
    if provider_id == "openai":
        return "provider.openai.api-key"
    if provider_id == "anthropic":
        return "provider.anthropic.api-key"
    raise UnsupportedCredentialProviderError


class KeyringCredentialStore:
    """Persist credentials only through an approved native keyring backend."""

    __slots__ = ("_platform", "_provider")

    def __init__(self, provider: _KeyringProvider, platform: str) -> None:
        self._provider = provider
        self._platform = platform

    @classmethod
    def from_system(cls) -> Self:
        """Build a store around the process keyring without accessing secrets."""

        return cls(keyring, sys.platform)

    def preflight(self) -> _KeyringBackend:
        """Return the exact approved native backend selected by keyring."""

        approved = _APPROVED_BACKENDS.get(self._platform)
        if approved is None:
            raise CredentialStoreUnavailableError

        backend: _KeyringBackend | None = None
        backend_is_approved = False
        try:
            candidate = self._provider.get_keyring()
            backend_identity = (
                type(candidate).__module__,
                type(candidate).__qualname__,
            )
            backend_is_approved = (
                backend_identity == approved and candidate.priority > 0
            )
            if backend_is_approved:
                backend = candidate
        except Exception:
            backend_is_approved = False

        if not backend_is_approved or backend is None:
            raise CredentialStoreUnavailableError
        return backend

    def get(self, provider_id: str) -> str | None:
        credential_name = _credential_name(provider_id)
        backend = self.preflight()
        return self._read(backend, credential_name)

    def set(self, provider_id: str, secret: str) -> None:
        credential_name = _credential_name(provider_id)
        if type(secret) is not str or not secret.strip():
            raise InvalidCredentialSecretError
        backend = self.preflight()
        write_failed = False
        try:
            backend.set_password(_SERVICE_NAME, credential_name, secret)
        except Exception:
            write_failed = True
        if write_failed:
            raise CredentialStoreUnavailableError

    def delete(self, provider_id: str) -> None:
        credential_name = _credential_name(provider_id)
        backend = self.preflight()
        if self._read(backend, credential_name) is None:
            return

        delete_failed = False
        may_be_missing = False
        try:
            backend.delete_password(_SERVICE_NAME, credential_name)
        except PasswordDeleteError:
            may_be_missing = True
        except Exception:
            delete_failed = True

        if delete_failed:
            raise CredentialStoreUnavailableError
        if may_be_missing and self._read(backend, credential_name) is not None:
            raise CredentialStoreUnavailableError

    @staticmethod
    def _read(
        backend: _KeyringBackend,
        credential_name: str,
    ) -> str | None:
        read_failed = False
        secret: object = None
        try:
            secret = backend.get_password(_SERVICE_NAME, credential_name)
        except Exception:
            read_failed = True

        if (
            read_failed
            or (secret is not None and type(secret) is not str)
            or (type(secret) is str and not secret.strip())
        ):
            raise CredentialStoreUnavailableError
        return cast(str | None, secret)
