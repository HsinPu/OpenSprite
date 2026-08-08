"""Settings service and error helpers for the web adapter."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable

from aiohttp import web

from ....app.settings.media import MediaSettingsService
from ....app.settings.providers import ProviderSettingsService
from ....modules.channels import catalog as _channel_catalog
from ....modules.llm.provider_errors import (
    ProviderSettingsConflict,
    ProviderSettingsError,
    ProviderSettingsNotFound,
    ProviderSettingsValidationError,
)
from ....modules.channels import settings as _channel_settings
from ....modules.scheduling.settings import (
    ScheduleSettingsError,
    ScheduleSettingsNotFound,
    ScheduleSettingsService,
    ScheduleSettingsValidationError,
)
from ...auth.credentials import CredentialNotFoundError, CredentialStoreError
from ...mcp.settings import (
    MCPSettingsError,
    MCPSettingsNotFound,
    MCPSettingsService,
    MCPSettingsValidationError,
)


def get_provider_settings(adapter: Any) -> ProviderSettingsService:
    return ProviderSettingsService(adapter._get_config_path())


def _channel_type_registration_predicate(adapter: Any) -> Callable[[str], bool]:
    predicate = getattr(adapter, "_is_registered_channel_type", None)
    if callable(predicate):
        return predicate
    return _channel_catalog.CHANNEL_TYPES.__contains__


def get_channel_settings(adapter: Any) -> _channel_settings.ChannelSettingsService:
    return _channel_settings.ChannelSettingsService(
        adapter._get_config_path(),
        is_registered_channel_type=_channel_type_registration_predicate(adapter),
    )


def get_schedule_settings(adapter: Any) -> ScheduleSettingsService:
    return ScheduleSettingsService(adapter._get_config_path())


def get_mcp_settings(adapter: Any) -> MCPSettingsService:
    return MCPSettingsService(adapter._get_config_path())


def get_media_settings(adapter: Any) -> MediaSettingsService:
    return MediaSettingsService(adapter._get_config_path())


def mcp_runtime_payload(adapter: Any) -> dict[str, Any]:
    agent = adapter._get_agent()
    lifecycle = getattr(agent, "mcp_lifecycle", None) if agent is not None else None
    if lifecycle is None:
        return {
            "connected": False,
            "connecting": False,
            "connect_failures": 0,
            "retry_after": 0.0,
            "tool_names": [],
        }
    return {
        "connected": bool(getattr(lifecycle, "connected", False)),
        "connecting": bool(getattr(lifecycle, "connecting", False)),
        "connect_failures": int(getattr(lifecycle, "connect_failures", 0) or 0),
        "retry_after": float(getattr(lifecycle, "retry_after", 0.0) or 0.0),
        "tool_names": sorted(getattr(lifecycle, "tool_names", set()) or []),
    }


def with_mcp_runtime(adapter: Any, payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    updated["runtime"] = mcp_runtime_payload(adapter)
    return updated


async def read_json_body(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise web.HTTPBadRequest(text="Request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Request body must be a JSON object")
    return payload


def _raise_settings_error(
    exc: Exception,
    bad_request: type[Exception],
    not_found: type[Exception] | None = None,
    conflict: type[Exception] | None = None,
) -> None:
    if isinstance(exc, bad_request):
        raise web.HTTPBadRequest(text=str(exc)) from exc
    if not_found and isinstance(exc, not_found):
        raise web.HTTPNotFound(text=str(exc)) from exc
    if conflict and isinstance(exc, conflict):
        raise web.HTTPConflict(text=str(exc)) from exc
    raise web.HTTPServiceUnavailable(text=str(exc)) from exc


def raise_provider_settings_error(exc: Exception) -> None:
    _raise_settings_error(
        exc, ProviderSettingsValidationError, ProviderSettingsNotFound, ProviderSettingsConflict
    )


@contextmanager
def provider_settings_errors(*, include_unexpected: bool = False) -> Iterator[None]:
    try:
        yield
    except ProviderSettingsError as exc:
        raise_provider_settings_error(exc)
    except Exception as exc:
        if not include_unexpected:
            raise
        raise_provider_settings_error(exc)


def raise_channel_settings_error(exc: _channel_settings.ChannelSettingsError) -> None:
    _raise_settings_error(
        exc,
        _channel_settings.ChannelSettingsValidationError,
        _channel_settings.ChannelSettingsNotFound,
    )


def raise_credential_store_error(exc: CredentialStoreError) -> None:
    if isinstance(exc, CredentialNotFoundError):
        raise web.HTTPNotFound(text=str(exc)) from exc
    raise web.HTTPBadRequest(text=str(exc)) from exc


def raise_schedule_settings_error(exc: ScheduleSettingsError) -> None:
    _raise_settings_error(exc, ScheduleSettingsValidationError, ScheduleSettingsNotFound)


def raise_mcp_settings_error(exc: MCPSettingsError) -> None:
    _raise_settings_error(exc, MCPSettingsValidationError, MCPSettingsNotFound)
