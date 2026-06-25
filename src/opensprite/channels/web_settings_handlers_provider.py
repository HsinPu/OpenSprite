"""Provider settings HTTP handlers for the web adapter."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from ..auth.credentials import (
    CredentialStoreError,
    add_credential,
    list_credentials,
    remove_credential,
    set_capability_default,
    set_provider_default,
)
from ..config.provider_errors import ProviderSettingsError
from . import web_settings_support


async def handle_settings_providers(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = adapter._get_provider_settings().list_providers()
    except ProviderSettingsError as exc:
        web_settings_support.raise_provider_settings_error(exc)
    return web.json_response(payload)


async def handle_settings_provider_connect(adapter: Any, request: web.Request) -> web.Response:
    provider_id = adapter._coerce_optional_text(request.match_info.get("provider_id"))
    if provider_id is None:
        raise web.HTTPBadRequest(text="provider_id is required")
    body = await adapter._read_json_body(request)
    try:
        payload = adapter._get_provider_settings().connect_provider(
            provider_id,
            api_key=adapter._coerce_optional_text(body.get("api_key")),
            base_url=adapter._coerce_optional_text(body.get("base_url")),
            name=adapter._coerce_optional_text(body.get("name")),
        )
    except ProviderSettingsError as exc:
        web_settings_support.raise_provider_settings_error(exc)
    return web.json_response(payload)


async def handle_settings_provider_disconnect(adapter: Any, request: web.Request) -> web.Response:
    provider_id = adapter._coerce_optional_text(request.match_info.get("provider_id"))
    if provider_id is None:
        raise web.HTTPBadRequest(text="provider_id is required")
    try:
        payload = adapter._get_provider_settings().disconnect_provider(provider_id)
    except ProviderSettingsError as exc:
        web_settings_support.raise_provider_settings_error(exc)
    payload = adapter._reload_agent_llm_from_config(payload, force=True)
    return web.json_response(payload)


async def handle_settings_credentials(adapter: Any, request: web.Request) -> web.Response:
    provider = adapter._coerce_optional_text(request.query.get("provider"))
    try:
        credentials = list_credentials(provider, app_home=adapter._get_config_path().parent)
    except CredentialStoreError as exc:
        web_settings_support.raise_credential_store_error(exc)
    return web.json_response({"credentials": credentials})


async def handle_settings_credential_create(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    provider = adapter._coerce_optional_text(body.get("provider"))
    secret = adapter._coerce_optional_text(body.get("secret")) or adapter._coerce_optional_text(body.get("api_key"))
    if provider is None or secret is None:
        raise web.HTTPBadRequest(text="provider and secret are required")
    scopes = body.get("scopes")
    if not isinstance(scopes, list):
        scopes = None
    try:
        credential = add_credential(
            provider,
            secret,
            label=adapter._coerce_optional_text(body.get("label")),
            auth_type=adapter._coerce_optional_text(body.get("auth_type"), default="api_key") or "api_key",
            base_url=adapter._coerce_optional_text(body.get("base_url")),
            scopes=scopes,
            app_home=adapter._get_config_path().parent,
        )
    except CredentialStoreError as exc:
        web_settings_support.raise_credential_store_error(exc)
    return web.json_response({"ok": True, "credential": credential})


async def handle_settings_credential_delete(adapter: Any, request: web.Request) -> web.Response:
    provider = adapter._coerce_optional_text(request.match_info.get("provider"))
    credential_id = adapter._coerce_optional_text(request.match_info.get("credential_id"))
    if provider is None or credential_id is None:
        raise web.HTTPBadRequest(text="provider and credential_id are required")
    try:
        payload = remove_credential(provider, credential_id, app_home=adapter._get_config_path().parent)
        cleanup = adapter._get_provider_settings().remove_credential_references(provider, credential_id)
        payload.update(cleanup)
    except CredentialStoreError as exc:
        web_settings_support.raise_credential_store_error(exc)
    except ProviderSettingsError as exc:
        web_settings_support.raise_provider_settings_error(exc)
    payload = adapter._reload_agent_llm_from_config(payload, force=bool(payload.get("restart_required")))
    return web.json_response(payload)


async def handle_settings_credential_default(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    provider = adapter._coerce_optional_text(body.get("provider"))
    capability = adapter._coerce_optional_text(body.get("capability"))
    credential_id = adapter._coerce_optional_text(body.get("credential_id"))
    if credential_id is None or (provider is None and capability is None):
        raise web.HTTPBadRequest(text="credential_id plus provider or capability is required")
    try:
        if provider is not None:
            credential = set_provider_default(provider, credential_id, app_home=adapter._get_config_path().parent)
        else:
            credential = set_capability_default(capability or "", credential_id, app_home=adapter._get_config_path().parent)
    except CredentialStoreError as exc:
        web_settings_support.raise_credential_store_error(exc)
    return web.json_response({"ok": True, "credential": credential})


async def handle_settings_provider_credential(adapter: Any, request: web.Request) -> web.Response:
    provider_id = adapter._coerce_optional_text(request.match_info.get("provider_id"))
    if provider_id is None:
        raise web.HTTPBadRequest(text="provider_id is required")
    body = await adapter._read_json_body(request)
    credential_id = adapter._coerce_optional_text(body.get("credential_id"))
    if credential_id is None:
        raise web.HTTPBadRequest(text="credential_id is required")
    try:
        payload = adapter._get_provider_settings().set_provider_credential(provider_id, credential_id)
    except ProviderSettingsError as exc:
        web_settings_support.raise_provider_settings_error(exc)
    payload = adapter._reload_agent_llm_from_config(payload, force=True)
    return web.json_response(payload)


async def handle_settings_models(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = adapter._get_provider_settings().list_models()
    except ProviderSettingsError as exc:
        web_settings_support.raise_provider_settings_error(exc)
    return web.json_response(payload)
