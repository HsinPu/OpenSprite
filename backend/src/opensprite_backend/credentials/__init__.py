"""Secure operating-system credential storage for fixed providers."""

from .keyring_store import KeyringCredentialStore
from .store import (
    CredentialStore,
    CredentialStoreError,
    CredentialStoreUnavailableError,
    InvalidCredentialSecretError,
    UnsupportedCredentialProviderError,
)

__all__ = [
    "CredentialStore",
    "CredentialStoreError",
    "CredentialStoreUnavailableError",
    "InvalidCredentialSecretError",
    "KeyringCredentialStore",
    "UnsupportedCredentialProviderError",
]
