"""Typed boundary and sanitized errors for credential persistence."""

from typing import Protocol


class CredentialStoreError(Exception):
    """Base failure with a fixed representation that cannot carry secrets."""

    message = "Credential storage failed."

    def __init__(self) -> None:
        super().__init__(self.message)


class CredentialStoreUnavailableError(CredentialStoreError):
    """The approved operating-system credential backend is unavailable."""

    message = "Secure credential storage is unavailable."


class UnsupportedCredentialProviderError(CredentialStoreError):
    """A caller supplied a provider outside the fixed catalog."""

    message = "Unsupported credential provider."


class InvalidCredentialSecretError(CredentialStoreError):
    """A caller supplied a secret that must not be persisted."""

    message = "Credential secret must not be blank."


class CredentialStore(Protocol):
    """Store one API credential for each supported provider."""

    def get(self, provider_id: str) -> str | None: ...

    def set(self, provider_id: str, secret: str) -> None: ...

    def delete(self, provider_id: str) -> None: ...
