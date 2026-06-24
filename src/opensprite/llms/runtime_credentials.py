"""Credential resolution helpers for LLM runtime providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..auth.credentials import (
    DEFAULT_LLM_CAPABILITY,
    CredentialNotFoundError,
    mark_credential_used,
    resolve_credential,
)


@dataclass(frozen=True)
class RuntimeCredentials:
    api_key: str
    base_url: str


def resolve_runtime_credentials(
    *,
    provider_name: str,
    auth_type: str,
    api_key: str,
    base_url: str,
    credential_id: str,
    app_home: Path,
) -> RuntimeCredentials:
    """Resolve API-key style runtime credentials without provider-specific OAuth."""
    if not api_key and auth_type == "api_key":
        try:
            credential = resolve_credential(
                provider=provider_name,
                credential_id=credential_id or None,
                capability=DEFAULT_LLM_CAPABILITY,
                app_home=app_home,
            )
        except CredentialNotFoundError:
            if credential_id:
                raise
        else:
            api_key = credential.secret
            if not base_url and credential.base_url:
                base_url = credential.base_url
            mark_credential_used(credential.provider, credential.id, app_home=app_home)
    elif not api_key and auth_type == "optional_api_key":
        api_key = "no-key-required"

    return RuntimeCredentials(api_key=api_key, base_url=base_url)
