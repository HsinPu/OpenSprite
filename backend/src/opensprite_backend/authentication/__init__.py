"""Single-owner local authentication boundary."""

from .service import (
    AuthResult,
    LocalAuthentication,
    LocalAuthenticationError,
    LocalAuthenticationOperations,
    UnavailableLocalAuthentication,
    create_local_authentication,
)
from .store import AccessMode, AccessPolicy, JsonAccessPolicyStore

__all__ = [
    "AuthResult",
    "LocalAuthentication",
    "LocalAuthenticationError",
    "LocalAuthenticationOperations",
    "UnavailableLocalAuthentication",
    "create_local_authentication",
    "AccessMode",
    "AccessPolicy",
    "JsonAccessPolicyStore",
]
