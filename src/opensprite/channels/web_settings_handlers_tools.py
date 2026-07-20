"""Tool-facing settings HTTP handlers for the web adapter."""

from __future__ import annotations

import asyncio
import httpx
from typing import Any
from uuid import uuid4

from aiohttp import web

from ..config import Config
from ..config.defaults import DEFAULT_SEARXNG_URL
from ..tools.browser import _validate_navigation_url
from ..tools.browser_provider_factory import browser_cloud_status, cloud_provider_from_config
from ..tools.browser_runtime import AgentBrowserRuntime
from ..utils.log import logger, setup_log
from ..utils.searxng_url import normalize_searxng_proxy_url, read_limited_searxng_json
from . import (
    web_frontend_runtime,
    web_settings_coercion,
    web_settings_payloads,
    web_settings_reload,
    web_settings_support,
)


SEARXNG_OPTIONS_USER_AGENT = "Mozilla/5.0 AppleWebKit/537.36 OpenSprite/0.1"


def _browser_command_prefix() -> list[str]:
    return web_frontend_runtime.browser_command_prefix()


def _browser_runtime_status() -> dict[str, Any]:
    return web_frontend_runtime.browser_runtime_status(_browser_command_prefix())


async def _run_browser_doctor_command(
    args: list[str],
    *,
    timeout: int = 20,
    launch_args: str = "",
) -> dict[str, Any]:
    return await web_frontend_runtime.run_browser_doctor_command(
        args,
        timeout=timeout,
        launch_args=launch_args,
        command_prefix=_browser_command_prefix(),
    )


async def _run_browser_install_command(*, timeout: int = 300) -> dict[str, Any]:
    return await web_frontend_runtime.run_browser_install_command(
        timeout=timeout,
        command_prefix=_browser_command_prefix(),
    )


def _with_browser_diagnostic(result: dict[str, Any] | None) -> dict[str, Any]:
    return web_frontend_runtime.with_browser_diagnostic(result)


def _browser_payload(adapter: Any, config: Config) -> dict[str, Any]:
    return web_settings_payloads.browser_payload(
        config,
        browser_cloud_status_fn=browser_cloud_status,
        browser_runtime_status_fn=_browser_runtime_status,
    )


async def handle_settings_web_search(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    return web.json_response({"web_search": web_settings_payloads.web_search_payload(config)})


async def handle_settings_web_search_searxng_options(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    search = config.tools.web_search
    body = await adapter._read_json_body(request)
    requested_searxng_url = body.get("url") if "url" in body else search.searxng_url
    searxng_url = adapter._coerce_optional_text(
        requested_searxng_url,
        default=DEFAULT_SEARXNG_URL,
    ) or DEFAULT_SEARXNG_URL
    requested_searxng_proxy = (
        adapter._coerce_optional_text(body.get("proxy"), default=None)
        if "proxy" in body
        else search.searxng_proxy
    )
    try:
        config_url = web_settings_coercion.searxng_config_url(searxng_url)
        searxng_proxy = normalize_searxng_proxy_url(requested_searxng_proxy)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    try:
        async with httpx.AsyncClient(proxy=searxng_proxy) as client:
            async with client.stream(
                "GET",
                config_url,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": SEARXNG_OPTIONS_USER_AGENT,
                },
                timeout=10.0,
            ) as response:
                response.raise_for_status()
                payload = await read_limited_searxng_json(response)
    except Exception as exc:
        logger.warning("SearXNG options metadata unavailable | url={} error={}", searxng_url, exc)
        return web.json_response(
            {"ok": False, "error": f"Unable to load SearXNG /config metadata: {exc}"},
            status=502,
        )
    if not isinstance(payload, dict):
        return web.json_response(
            {"ok": False, "error": "SearXNG /config response was not a JSON object."},
            status=502,
        )
    return web.json_response({"searxng": web_settings_coercion.searxng_options_payload(payload, url=searxng_url)})


async def handle_settings_web_search_update(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    config_path = adapter._get_config_path()
    config = Config.load(config_path)
    search = config.tools.web_search
    search.provider = web_settings_coercion.coerce_web_search_provider(body.get("provider", search.provider))
    search.freshness = web_settings_coercion.coerce_web_search_freshness(body.get("freshness", search.freshness))
    search.max_results = web_settings_coercion.coerce_positive_int(body.get("max_results"), field="max_results", default=search.max_results, minimum=1, maximum=100)
    search.searxng_max_pages = web_settings_coercion.coerce_positive_int(body.get("searxng_max_pages"), field="searxng_max_pages", default=search.searxng_max_pages, minimum=1, maximum=50)
    if "searxng_url" in body:
        requested_searxng_url = adapter._coerce_optional_text(
            body.get("searxng_url"),
            default=DEFAULT_SEARXNG_URL,
        ) or DEFAULT_SEARXNG_URL
        try:
            web_settings_coercion.searxng_config_url(requested_searxng_url)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        search.searxng_url = requested_searxng_url
    if "searxng_engines" in body:
        search.searxng_engines = web_settings_coercion.coerce_text_list(body.get("searxng_engines"), field="searxng_engines", default=search.searxng_engines)
    if "searxng_categories" in body:
        search.searxng_categories = web_settings_coercion.coerce_text_list(body.get("searxng_categories"), field="searxng_categories", default=search.searxng_categories)
    if "searxng_proxy" in body:
        requested_searxng_proxy = adapter._coerce_optional_text(body.get("searxng_proxy"), default="") or None
        try:
            search.searxng_proxy = normalize_searxng_proxy_url(requested_searxng_proxy)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
    config.save(config_path)
    payload = {"web_search": web_settings_payloads.web_search_payload(config), "restart_required": True}
    payload = web_settings_reload.reload_web_search_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_browser(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    return web.json_response({"browser": _browser_payload(adapter, config)})


async def handle_settings_browser_update(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    config_path = adapter._get_config_path()
    config = Config.load(config_path)
    browser = config.tools.browser
    browser.enabled = web_settings_coercion.coerce_bool(body.get("enabled"), field="enabled", default=browser.enabled)
    browser.backend = web_settings_coercion.coerce_browser_backend(body.get("backend", browser.backend))
    browser.command_timeout = web_settings_coercion.coerce_positive_int(body.get("command_timeout"), field="command_timeout", default=browser.command_timeout, minimum=1, maximum=600)
    browser.session_timeout = web_settings_coercion.coerce_positive_int(body.get("session_timeout"), field="session_timeout", default=browser.session_timeout, minimum=1, maximum=86400)
    if "cdp_url" in body:
        browser.cdp_url = adapter._coerce_optional_text(body.get("cdp_url"), default="") or ""
    if "launch_args" in body:
        browser.launch_args = adapter._coerce_optional_text(body.get("launch_args"), default="") or ""
    browser.allow_private_urls = web_settings_coercion.coerce_bool(body.get("allow_private_urls"), field="allow_private_urls", default=browser.allow_private_urls)
    for field in (
        "browserbase_api_key",
        "browserbase_project_id",
        "browserbase_base_url",
        "browser_use_api_key",
        "browser_use_base_url",
        "firecrawl_api_key",
        "firecrawl_base_url",
    ):
        if field in body:
            setattr(browser, field, adapter._coerce_optional_text(body.get(field), default="") or "")
    for field in ("browserbase_proxies", "browserbase_advanced_stealth", "browserbase_keep_alive"):
        if field in body:
            setattr(browser, field, web_settings_coercion.coerce_bool(body.get(field), field=field, default=getattr(browser, field)))
    config.save(config_path)
    payload = {"browser": _browser_payload(adapter, config), "restart_required": True}
    payload = web_settings_reload.reload_browser_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_browser_test(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    config = Config.load(adapter._get_config_path())
    browser = config.tools.browser
    url = str(body.get("url") or "https://quotes.toscrape.com/js/").strip()
    blocked = _validate_navigation_url(url, allow_private_urls=bool(browser.allow_private_urls))
    if blocked:
        raise web.HTTPBadRequest(text=blocked)
    if not browser.enabled:
        diagnostic = _with_browser_diagnostic({"ok": False, "error": "Browser tools are disabled. Enable and save browser settings before running the manual test."})
        return web.json_response({"ok": False, "url": url, "backend": browser.backend, "error": diagnostic["error"], "diagnostic_code": diagnostic["diagnostic_code"], "suggestion": diagnostic["suggestion"], "browser": _browser_payload(adapter, config)})

    runtime = AgentBrowserRuntime(
        command_timeout=browser.command_timeout,
        session_timeout=browser.session_timeout,
        cdp_url=browser.cdp_url,
        launch_args=browser.launch_args,
        cloud_provider=cloud_provider_from_config(browser),
    )
    session_key = f"settings-test-{uuid4().hex[:8]}"
    open_result = _with_browser_diagnostic(await runtime.run(session_key=session_key, command="open", args=[url], timeout=max(30, browser.command_timeout)))
    snapshot_result: dict[str, Any] | None = None
    if bool(open_result.get("success")):
        snapshot_result = _with_browser_diagnostic(await runtime.run(session_key=session_key, command="snapshot", args=["-c"], timeout=browser.command_timeout))
    ok = bool(open_result.get("success")) and bool((snapshot_result or {}).get("success"))
    diagnostic_source = snapshot_result if snapshot_result is not None and not snapshot_result.get("success") else open_result
    return web.json_response(
        {
            "ok": ok,
            "url": url,
            "backend": browser.backend,
            "diagnostic_code": "ok" if ok else diagnostic_source.get("diagnostic_code", "unknown"),
            "suggestion": "" if ok else diagnostic_source.get("suggestion", ""),
            "open": adapter._json_safe(open_result),
            "snapshot": adapter._json_safe(snapshot_result) if snapshot_result is not None else None,
            "browser": _browser_payload(adapter, config),
        }
    )


async def handle_settings_browser_doctor(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    browser = config.tools.browser
    version_result = await _run_browser_doctor_command(["--version"], timeout=10)
    doctor_result = await _run_browser_doctor_command(["doctor"], timeout=30, launch_args=browser.launch_args)
    checks = [
        {"name": "version", "command": "agent-browser --version", **version_result},
        {"name": "doctor", "command": "agent-browser doctor", **doctor_result},
    ]
    return web.json_response({"ok": all(bool(check.get("ok")) for check in checks), "browser": _browser_payload(adapter, config), "runtime": _browser_runtime_status(), "checks": checks})


async def handle_settings_browser_install(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    browser = config.tools.browser
    before = await _run_browser_doctor_command(["doctor"], timeout=30, launch_args=browser.launch_args)
    if bool(before.get("ok")):
        return web.json_response({"ok": True, "installed": False, "already_installed": True, "browser": _browser_payload(adapter, config), "runtime": _browser_runtime_status(), "before": before, "install": None, "after": before})

    install_result = await _run_browser_install_command(timeout=300)
    after = await _run_browser_doctor_command(["doctor"], timeout=30, launch_args=browser.launch_args)
    install_ok = bool(install_result.get("ok"))
    after_ok = bool(after.get("ok"))
    sandbox_only_after_install = (
        install_ok
        and not after_ok
        and after.get("diagnostic_code") == "sandbox_unavailable"
        and adapter.DEFAULT_CONFIG.get("launch_args", "") in str(browser.launch_args or "")
    )
    return web.json_response(
        {
            "ok": after_ok or sandbox_only_after_install,
            "installed": install_ok,
            "doctor_warning": sandbox_only_after_install,
            "already_installed": False,
            "browser": _browser_payload(adapter, config),
            "runtime": _browser_runtime_status(),
            "before": before,
            "install": install_result,
            "after": after,
        }
    )


async def handle_settings_log(adapter: Any, request: web.Request) -> web.Response:
    config = Config.load(adapter._get_config_path())
    return web.json_response({"log": web_settings_payloads.log_payload(config)})


async def handle_settings_log_update(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    config_path = adapter._get_config_path()
    config = Config.load(config_path)
    if "enabled" in body:
        config.log.enabled = web_settings_coercion.coerce_bool(body.get("enabled"), field="enabled", default=config.log.enabled)
    if "level" in body:
        config.log.level = web_settings_coercion.coerce_log_level(body.get("level"))
    if "retention_days" in body:
        config.log.retention_days = web_settings_coercion.coerce_positive_int(body.get("retention_days"), field="retention_days", default=config.log.retention_days, minimum=1)
    if "log_system_prompt" in body:
        config.log.log_system_prompt = web_settings_coercion.coerce_bool(body.get("log_system_prompt"), field="log_system_prompt", default=config.log.log_system_prompt)
    if "log_system_prompt_lines" in body:
        config.log.log_system_prompt_lines = web_settings_coercion.coerce_positive_int(body.get("log_system_prompt_lines"), field="log_system_prompt_lines", default=config.log.log_system_prompt_lines, minimum=0)
    if "log_reasoning_details" in body:
        config.log.log_reasoning_details = web_settings_coercion.coerce_bool(body.get("log_reasoning_details"), field="log_reasoning_details", default=config.log.log_reasoning_details)
    config.save(config_path)
    setup_log(config.log)
    return web.json_response({"log": web_settings_payloads.log_payload(config), "restart_required": False, "runtime_reloaded": True})


async def handle_settings_mcp(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = web_settings_support.get_mcp_settings(adapter).list_servers()
    except Exception as exc:
        web_settings_support.raise_mcp_settings_error(exc)
    return web.json_response(web_settings_support.with_mcp_runtime(adapter, payload))


async def handle_settings_mcp_create(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    server_id = adapter._coerce_optional_text(body.get("server_id"), default="") or ""
    try:
        payload = web_settings_support.get_mcp_settings(adapter).upsert_server(server_id, body)
    except Exception as exc:
        web_settings_support.raise_mcp_settings_error(exc)
    payload = await web_settings_reload.reload_mcp_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_mcp_update(adapter: Any, request: web.Request) -> web.Response:
    server_id = adapter._coerce_optional_text(request.match_info.get("server_id"), default="") or ""
    body = await adapter._read_json_body(request)
    try:
        payload = web_settings_support.get_mcp_settings(adapter).upsert_server(server_id, body)
    except Exception as exc:
        web_settings_support.raise_mcp_settings_error(exc)
    payload = await web_settings_reload.reload_mcp_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_mcp_delete(adapter: Any, request: web.Request) -> web.Response:
    server_id = adapter._coerce_optional_text(request.match_info.get("server_id"), default="") or ""
    try:
        payload = web_settings_support.get_mcp_settings(adapter).remove_server(server_id)
    except Exception as exc:
        web_settings_support.raise_mcp_settings_error(exc)
    payload = await web_settings_reload.reload_mcp_from_config(adapter, payload, logger=logger)
    return web.json_response(payload)


async def handle_settings_mcp_reload(adapter: Any, request: web.Request) -> web.Response:
    try:
        payload = web_settings_support.get_mcp_settings(adapter).list_servers()
    except Exception as exc:
        web_settings_support.raise_mcp_settings_error(exc)
    payload = await web_settings_reload.reload_mcp_from_config(
        adapter,
        {**payload, "restart_required": True},
        force=True,
        logger=logger,
    )
    return web.json_response(payload)
