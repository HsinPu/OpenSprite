"""Shared LLM provider auth type identifiers."""

from typing import Literal

API_KEY_AUTH_TYPE = "api_key"
OPTIONAL_API_KEY_AUTH_TYPE = "optional_api_key"
OPENAI_CODEX_OAUTH_AUTH_TYPE = "openai_codex_oauth"
GITHUB_COPILOT_OAUTH_AUTH_TYPE = "github_copilot_oauth"

ProviderAuthType = Literal[
    API_KEY_AUTH_TYPE,
    OPTIONAL_API_KEY_AUTH_TYPE,
    OPENAI_CODEX_OAUTH_AUTH_TYPE,
    GITHUB_COPILOT_OAUTH_AUTH_TYPE,
]
