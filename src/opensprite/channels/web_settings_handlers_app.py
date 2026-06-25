"""Application-level settings HTTP handlers for the web adapter."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from aiohttp import web

from ..cli import service_background, service_linux, update as update_cli
from ..config import Config
from ..network_environment import apply_network_environment
from ..utils.log import logger
from . import web_settings_coercion, web_settings_payloads, web_settings_reload, web_settings_support


async def handle_settings_media(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = adapter._get_media_settings().list_media()
    except Exception as exc:
        web_settings_support.raise_provider_settings_error(exc)
    return web.json_response(payload)


async def handle_settings_media_update(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    category = adapter._coerce_optional_text(body.get("category"))
    if category is None:
        raise web.HTTPBadRequest(text="category is required")
    try:
        payload = adapter._get_media_settings().update_media(
            category,
            enabled=web_settings_coercion.coerce_bool(body.get("enabled"), field="enabled", default=False),
            provider_id=adapter._coerce_optional_text(body.get("provider_id")),
            model=adapter._coerce_optional_text(body.get("model")),
        )
    except Exception as exc:
        web_settings_support.raise_provider_settings_error(exc)
    payload = web_settings_reload.reload_media_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_model_select(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    provider_id = adapter._coerce_optional_text(body.get("provider_id"))
    model = adapter._coerce_optional_text(body.get("model"))
    reasoning_effort = (
        adapter._coerce_optional_text(body.get("reasoning_effort"), default="")
        if "reasoning_effort" in body
        else None
    )
    if provider_id is None or model is None:
        raise web.HTTPBadRequest(text="provider_id and model are required")
    try:
        payload = adapter._get_provider_settings().select_model(
            provider_id,
            model,
            reasoning_effort=reasoning_effort,
        )
    except Exception as exc:
        web_settings_support.raise_provider_settings_error(exc)
    payload = web_settings_reload.reload_agent_llm_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


def build_update_status_payload() -> dict[str, Any]:
    try:
        root = update_cli.find_project_root()
        current_rev = update_cli._git_output(["rev-parse", "HEAD"], cwd=root)
        branch = update_cli._git_output(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
        dirty = bool(update_cli._git_output(["status", "--porcelain"], cwd=root))
        commits_behind = update_cli.check_update_available(project_root=root, branch=branch)
        return {
            "ok": True,
            "supported": True,
            "project_root": str(root),
            "branch": branch,
            "current_rev": current_rev,
            "current_rev_short": current_rev[:7],
            "dirty": dirty,
            "commits_behind": commits_behind,
            "update_available": commits_behind > 0,
        }
    except Exception as exc:
        return {
            "ok": False,
            "supported": False,
            "error": str(exc),
            "dirty": False,
            "commits_behind": 0,
            "update_available": False,
        }


async def handle_settings_update_status(adapter: Any, request: web.Request) -> web.Response:
    payload = await asyncio.to_thread(build_update_status_payload)
    return web.json_response(payload)


async def restart_gateway_after_response(config_path: Path | None = None) -> None:
    await asyncio.sleep(1.0)
    try:
        try:
            linux_status = service_linux.get_service_status()
        except RuntimeError:
            linux_status = None
        if linux_status is not None and getattr(linux_status, "installed", False):
            service_linux.restart_service()
            return

        pid_file = service_background.get_pid_file()
        try:
            pid_file.unlink()
        except FileNotFoundError:
            pass
        service_background.start_service(config_path=config_path, python_executable=Path(sys.executable))
    except Exception:
        logger.exception("Failed to restart OpenSprite gateway after update")
        return
    os._exit(0)


async def handle_settings_update_apply(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    restart = web_settings_coercion.coerce_bool(body.get("restart"), field="restart", default=True)
    try:
        result = await asyncio.to_thread(update_cli.update_checkout, branch="main", install_dev=False)
    except update_cli.UpdateError as exc:
        raise web.HTTPConflict(text=str(exc)) from exc
    except Exception as exc:
        raise web.HTTPServiceUnavailable(text=str(exc)) from exc

    payload = {
        "ok": True,
        "updated": result.updated,
        "before_rev": result.before_rev,
        "before_rev_short": result.before_rev[:7],
        "after_rev": result.after_rev,
        "after_rev_short": result.after_rev[:7],
        "branch": result.branch,
        "project_root": str(result.project_root),
        "python": str(result.python_executable),
        "restart_scheduled": restart,
    }
    if restart:
        config_path = adapter._config.get("config_path") if hasattr(adapter, "_config") else adapter.config.get("config_path")
        resolved_config_path = None
        if config_path:
            resolved_config_path = Path(config_path).expanduser()
        asyncio.create_task(restart_gateway_after_response(config_path=resolved_config_path))
    return web.json_response(payload)


async def handle_settings_schedule(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = adapter._get_schedule_settings().get_schedule()
    except Exception as exc:
        web_settings_support.raise_schedule_settings_error(exc)
    return web.json_response(payload)


async def handle_settings_schedule_update(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    try:
        payload = adapter._get_schedule_settings().update_schedule(
            default_timezone=adapter._coerce_optional_text(body.get("default_timezone")),
        )
    except Exception as exc:
        web_settings_support.raise_schedule_settings_error(exc)
    payload = web_settings_reload.reload_schedule_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_network(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    return web.json_response({"network": web_settings_payloads.network_payload(config)})


async def handle_settings_network_update(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    config_path = adapter._get_config_path()
    config = Config.load(config_path)
    config.network.http_proxy = adapter._coerce_optional_text(body.get("http_proxy"), default="") or ""
    config.network.https_proxy = adapter._coerce_optional_text(body.get("https_proxy"), default="") or ""
    config.network.no_proxy = adapter._coerce_optional_text(body.get("no_proxy"), default="") or ""
    config.save(config_path)
    apply_network_environment(config, clear_blank=True)
    return web.json_response({"network": web_settings_payloads.network_payload(config), "restart_required": False})
