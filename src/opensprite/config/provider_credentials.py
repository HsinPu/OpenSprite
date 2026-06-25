"""Provider credential resolution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import CredentialNotFoundError, resolve_credential


def has_provider_secret(provider: dict[str, Any]) -> bool:
    return bool(str(provider.get("api_key", "") or "").strip() or str(provider.get("credential_id", "") or "").strip())


def resolve_provider_api_key(
    provider_id: str,
    provider: dict[str, Any],
    *,
    app_home: str | Path | None = None,
    allow_default: bool = False,
) -> str:
    """Return an inline or credential-backed API key for a provider config."""
    api_key = str(provider.get("api_key", "") or "").strip()
    if api_key:
        return api_key

    credential_id = str(provider.get("credential_id", "") or "").strip()
    if not credential_id and not allow_default:
        return ""

    credential_provider = str(provider.get("provider") or provider_id).strip() or provider_id
    if not credential_provider:
        return ""

    try:
        return resolve_credential(
            provider=credential_provider,
            credential_id=credential_id or None,
            app_home=app_home,
        ).secret
    except CredentialNotFoundError:
        return ""
