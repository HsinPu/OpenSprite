"""Resolve configured LLM providers into runtime client settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..auth.credentials import CredentialNotFoundError
from ..auth.codex import CodexAuthError, load_or_refresh_codex_token
from ..auth.copilot import CopilotAuthError, get_copilot_api_token, load_copilot_token
from ..config import Config, ProviderConfig
from .reasoning import normalize_reasoning_effort
from .runtime_auth import resolve_runtime_provider_auth
from .runtime_credentials import resolve_runtime_credentials
from .runtime_profile import resolve_runtime_provider_profile


class ProviderRuntimeError(RuntimeError):
    """Raised when a configured provider cannot be resolved for runtime use."""


@dataclass(frozen=True)
class ResolvedProviderRuntime:
    provider_name: str
    api_key: str
    model: str
    base_url: str
    enabled: bool
    api_mode: str | None = None
    auth_type: str = "api_key"
    reasoning_effort: str = ""
    context_window_tokens: int | None = None


def default_app_home(config_path: str | Path | None = None) -> Path:
    if config_path is not None:
        return Path(config_path).expanduser().resolve().parent
    return Path.home() / ".opensprite"


def resolve_provider_runtime(
    provider: ProviderConfig,
    *,
    provider_name: str,
    app_home: str | Path | None = None,
) -> ResolvedProviderRuntime:
    """Resolve a ProviderConfig into the arguments needed by create_llm()."""
    profile = resolve_runtime_provider_profile(provider, provider_name=provider_name)
    configured_provider = profile.provider_name
    auth_type = profile.auth_type
    api_mode = profile.api_mode
    profile_base_url = profile.profile_base_url
    base_url = str(provider.base_url or "").strip()
    api_key = str(provider.api_key or "").strip()
    credential_id = str(provider.credential_id or "").strip()
    app_home_path = Path(app_home) if app_home is not None else default_app_home()

    try:
        provider_auth = resolve_runtime_provider_auth(
            provider_name=configured_provider,
            auth_type=auth_type,
            api_key=api_key,
            base_url=base_url,
            api_mode=api_mode,
            profile_base_url=profile_base_url,
            app_home=app_home_path,
            codex_token_loader=load_or_refresh_codex_token,
            copilot_token_loader=load_copilot_token,
            copilot_api_token_resolver=get_copilot_api_token,
        )
    except (CodexAuthError, CopilotAuthError) as exc:
        raise ProviderRuntimeError(str(exc)) from exc
    configured_provider = provider_auth.provider_name
    api_key = provider_auth.api_key
    base_url = provider_auth.base_url
    api_mode = provider_auth.api_mode

    try:
        runtime_credentials = resolve_runtime_credentials(
            provider_name=configured_provider,
            auth_type=auth_type,
            api_key=api_key,
            base_url=base_url,
            credential_id=credential_id,
            app_home=app_home_path,
        )
    except CredentialNotFoundError as exc:
        raise ProviderRuntimeError(str(exc)) from exc
    api_key = runtime_credentials.api_key
    base_url = runtime_credentials.base_url
    if not base_url:
        base_url = profile_base_url

    return ResolvedProviderRuntime(
        provider_name=configured_provider,
        api_key=api_key,
        model=provider.model,
        base_url=base_url,
        enabled=provider.enabled,
        api_mode=api_mode,
        auth_type=auth_type,
        reasoning_effort=normalize_reasoning_effort(provider.reasoning_effort),
        context_window_tokens=provider.context_window_tokens,
    )


def create_llm_from_runtime(runtime: ResolvedProviderRuntime):
    from .provider_factory import create_llm

    return create_llm(
        api_key=runtime.api_key,
        model=runtime.model,
        base_url=runtime.base_url,
        provider_name=runtime.provider_name,
        enabled=runtime.enabled,
        api_mode=runtime.api_mode,
        auth_type=runtime.auth_type,
        reasoning_effort=runtime.reasoning_effort,
    )


def create_configured_llm(
    config: Config,
    *,
    fallback_app_home: str | Path | None = None,
):
    """Create the active configured LLM and return it with its resolved runtime."""
    cfg = config.llm.get_active()
    return create_provider_llm(
        cfg,
        provider_name=cfg.provider or config.llm.default or "",
        app_home=config.source_path.parent if config.source_path is not None else fallback_app_home,
    )


def create_provider_llm(
    provider: ProviderConfig,
    *,
    provider_name: str,
    app_home: str | Path | None = None,
):
    """Create an LLM for one resolved provider config and return its runtime metadata."""
    llm_runtime = resolve_provider_runtime(
        provider,
        provider_name=provider_name,
        app_home=app_home,
    )
    return create_llm_from_runtime(llm_runtime), llm_runtime
