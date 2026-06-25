"""Provider-specific auth normalization for LLM runtime providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..auth.codex import load_or_refresh_codex_token
from ..auth.copilot import COPILOT_BASE_URL, get_copilot_api_token, load_copilot_token
from ..config.provider_auth_types import GITHUB_COPILOT_OAUTH_AUTH_TYPE, OPENAI_CODEX_OAUTH_AUTH_TYPE


OPENAI_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
GITHUB_COPILOT_BASE_URL = COPILOT_BASE_URL


@dataclass(frozen=True)
class RuntimeProviderAuth:
    provider_name: str
    api_key: str
    base_url: str
    api_mode: str | None


TokenLoader = Callable[[Path], Any]
CopilotApiTokenResolver = Callable[[str], str]


def resolve_runtime_provider_auth(
    *,
    provider_name: str,
    auth_type: str,
    api_key: str,
    base_url: str,
    api_mode: str | None,
    profile_base_url: str,
    app_home: Path,
    codex_token_loader: TokenLoader | None = None,
    copilot_token_loader: TokenLoader | None = None,
    copilot_api_token_resolver: CopilotApiTokenResolver | None = None,
) -> RuntimeProviderAuth:
    """Apply provider-specific OAuth and API-mode runtime defaults."""
    codex_token_loader = codex_token_loader or load_or_refresh_codex_token
    copilot_token_loader = copilot_token_loader or load_copilot_token
    copilot_api_token_resolver = copilot_api_token_resolver or get_copilot_api_token

    if auth_type == OPENAI_CODEX_OAUTH_AUTH_TYPE:
        provider_name = provider_name or "openai-codex"
        api_mode = api_mode or "responses"
        base_url = base_url or profile_base_url or OPENAI_CODEX_BASE_URL
        if not api_key:
            api_key = codex_token_loader(app_home).access_token
    elif provider_name == "copilot" or auth_type == GITHUB_COPILOT_OAUTH_AUTH_TYPE:
        provider_name = "copilot"
        base_url = base_url or profile_base_url or GITHUB_COPILOT_BASE_URL
        api_mode = api_mode or "chat_completions"
        if not api_key and auth_type == GITHUB_COPILOT_OAUTH_AUTH_TYPE:
            api_key = copilot_token_loader(app_home).access_token
        api_key = copilot_api_token_resolver(api_key)
    elif api_mode is None:
        api_mode = "chat_completions"

    return RuntimeProviderAuth(
        provider_name=provider_name,
        api_key=api_key,
        base_url=base_url,
        api_mode=api_mode,
    )
