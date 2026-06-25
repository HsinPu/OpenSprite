"""Core settings HTTP handlers for the web adapter."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from ..config.channel_settings import ChannelSettingsError
from ..utils.log import logger
from . import web_settings_reload, web_settings_support


async def handle_settings_codex_auth_status(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.codex import CodexAuthError, get_codex_status

    try:
        status = get_codex_status(adapter._get_app_home())
    except CodexAuthError as exc:
        return web.json_response({"provider": "openai-codex", "configured": False, "error": str(exc)}, status=400)
    return web.json_response(status.to_public_payload())


async def handle_settings_codex_auth_login(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.codex import CodexAuthError, codex_start_device_auth

    try:
        device_auth = codex_start_device_auth()
    except CodexAuthError as exc:
        return web.json_response({"ok": False, "provider": "openai-codex", "error": str(exc)}, status=502)
    return web.json_response(
        {
            "ok": True,
            "provider": "openai-codex",
            "mode": "web_device_code",
            "verification_uri": device_auth.verification_uri,
            "user_code": device_auth.user_code,
            "device_auth_id": device_auth.device_auth_id,
            "interval": device_auth.poll_interval,
            "expires_in": device_auth.expires_in,
            "message": "Open the verification URL and enter the code to complete OpenAI Codex login.",
        }
    )


async def handle_settings_codex_auth_poll(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.codex import CodexAuthError, codex_poll_device_auth, get_codex_status

    body = await adapter._read_json_body(request)
    try:
        result = codex_poll_device_auth(
            adapter._coerce_optional_text(body.get("device_auth_id")),
            adapter._coerce_optional_text(body.get("user_code")),
            app_home=adapter._get_app_home(),
        )
        status = get_codex_status(adapter._get_app_home()) if result.status == "authorized" else None
    except CodexAuthError as exc:
        return web.json_response({"ok": False, "provider": "openai-codex", "error": str(exc)}, status=400)
    payload: dict[str, Any] = {"ok": True, "provider": "openai-codex", "status": result.status}
    if status is not None:
        payload["auth"] = status.to_public_payload(include_provider=False)
        payload = web_settings_reload.reload_agent_llm_from_config(adapter, payload, force=True, logger=logger)
    return web.json_response(payload)


async def handle_settings_codex_auth_logout(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.codex import codex_auth_path, delete_codex_token

    app_home = adapter._get_app_home()
    path = codex_auth_path(app_home)
    removed = delete_codex_token(app_home)
    return web.json_response({"ok": True, "provider": "openai-codex", "removed": removed, "path": str(path)})


async def handle_settings_copilot_auth_status(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.copilot import CopilotAuthError, get_copilot_status

    try:
        status = get_copilot_status(adapter._get_app_home())
    except CopilotAuthError as exc:
        return web.json_response({"provider": "copilot", "configured": False, "error": str(exc)}, status=400)
    return web.json_response(status.to_public_payload())


async def handle_settings_copilot_auth_login(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.copilot import CopilotAuthError, copilot_start_device_auth

    try:
        device_auth = copilot_start_device_auth()
    except CopilotAuthError as exc:
        return web.json_response({"ok": False, "provider": "copilot", "error": str(exc)}, status=502)
    return web.json_response(
        {
            "ok": True,
            "provider": "copilot",
            "mode": "web_device_code",
            "verification_uri": device_auth.verification_uri,
            "user_code": device_auth.user_code,
            "device_code": device_auth.device_code,
            "interval": device_auth.poll_interval,
            "expires_in": device_auth.expires_in,
        }
    )


async def handle_settings_copilot_auth_poll(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.copilot import CopilotAuthError, copilot_poll_device_auth, get_copilot_status

    body = await adapter._read_json_body(request)
    try:
        result = copilot_poll_device_auth(adapter._coerce_optional_text(body.get("device_code")), app_home=adapter._get_app_home())
        status = get_copilot_status(adapter._get_app_home()) if result.status == "authorized" else None
    except CopilotAuthError as exc:
        return web.json_response({"ok": False, "provider": "copilot", "error": str(exc)}, status=400)
    payload: dict[str, Any] = {"ok": True, "provider": "copilot", "status": result.status}
    if status is not None:
        payload["auth"] = status.to_public_payload(include_provider=False)
        payload = web_settings_reload.reload_agent_llm_from_config(adapter, payload, force=True, logger=logger)
    return web.json_response(payload)


async def handle_settings_copilot_auth_logout(adapter: Any, request: web.Request) -> web.Response:
    from ..auth.copilot import copilot_auth_path, delete_copilot_token

    app_home = adapter._get_app_home()
    path = copilot_auth_path(app_home)
    removed = delete_copilot_token(app_home)
    return web.json_response({"ok": True, "provider": "copilot", "removed": removed, "path": str(path)})


async def handle_settings_channels(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = web_settings_support.get_channel_settings(adapter).list_channels()
    except ChannelSettingsError as exc:
        web_settings_support.raise_channel_settings_error(exc)
    payload = await web_settings_reload.reload_channels_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)
async def handle_settings_channel_create(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    channel_type = adapter._coerce_optional_text(body.get("type"))
    if channel_type is None:
        raise web.HTTPBadRequest(text="type is required")
    try:
        payload = web_settings_support.get_channel_settings(adapter).create_channel(
            channel_type,
            name=adapter._coerce_optional_text(body.get("name")),
            token=adapter._coerce_optional_text(body.get("token")),
        )
    except ChannelSettingsError as exc:
        web_settings_support.raise_channel_settings_error(exc)
    payload = await web_settings_reload.reload_channels_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)

async def handle_settings_channel_update(adapter: Any, request: web.Request) -> web.Response:
    channel_id = adapter._coerce_optional_text(request.match_info.get("channel_id"))
    if channel_id is None:
        raise web.HTTPBadRequest(text="channel_id is required")
    body = await adapter._read_json_body(request)
    try:
        payload = web_settings_support.get_channel_settings(adapter).update_channel(
            channel_id,
            enabled=body.get("enabled") if "enabled" in body else None,
            settings=body.get("settings", {}),
        )
    except ChannelSettingsError as exc:
        web_settings_support.raise_channel_settings_error(exc)
    payload = await web_settings_reload.reload_channels_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_channel_connect(adapter: Any, request: web.Request) -> web.Response:
    channel_id = adapter._coerce_optional_text(request.match_info.get("channel_id"))
    if channel_id is None:
        raise web.HTTPBadRequest(text="channel_id is required")
    body = await adapter._read_json_body(request)
    try:
        payload = web_settings_support.get_channel_settings(adapter).connect_channel(
            channel_id,
            token=adapter._coerce_optional_text(body.get("token")),
            name=adapter._coerce_optional_text(body.get("name")),
        )
    except ChannelSettingsError as exc:
        web_settings_support.raise_channel_settings_error(exc)
    payload = await web_settings_reload.reload_channels_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_channel_disconnect(adapter: Any, request: web.Request) -> web.Response:
    channel_id = adapter._coerce_optional_text(request.match_info.get("channel_id"))
    if channel_id is None:
        raise web.HTTPBadRequest(text="channel_id is required")
    try:
        payload = web_settings_support.get_channel_settings(adapter).disconnect_channel(channel_id)
    except ChannelSettingsError as exc:
        web_settings_support.raise_channel_settings_error(exc)
    payload = await web_settings_reload.reload_channels_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)
