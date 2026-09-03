"""Single-owner local authentication boundary."""

from .service import (
    AuthResult,
    LocalAuthentication,
    LocalAuthenticationError,
    LocalAuthenticationOperations,
    UnavailableLocalAuthentication,
    create_local_authentication,
)

__all__ = [
    "AuthResult",
    "LocalAuthentication",
    "LocalAuthenticationError",
    "LocalAuthenticationOperations",
    "UnavailableLocalAuthentication",
    "create_local_authentication",
]
