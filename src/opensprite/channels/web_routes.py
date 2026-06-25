"""Route registration for the web channel adapter."""

from __future__ import annotations

from typing import Any

from ..utils.log import logger
from . import (
    web_cron_api,
    web_settings_handlers_app,
    web_settings_handlers_core,
    web_settings_handlers_provider,
    web_settings_handlers_tools,
)


def _bind_adapter(adapter: Any, handler: Any) -> Any:
    async def bound(request: Any) -> Any:
        return await handler(adapter, request)

    return bound


def register_web_routes(adapter: Any, *, ws_path: str, health_path: str) -> None:
    """Register HTTP and WebSocket routes on a prepared WebAdapter app."""
    app = adapter.app
    if app is None:
        raise RuntimeError("WebAdapter app must be created before registering routes")

    api = adapter._api
    router = app.router
    router.add_get(ws_path, adapter._handle_websocket)
    router.add_get(health_path, adapter._handle_health)
    router.add_get("/api/commands", api.handle_command_catalog)
    router.add_get("/api/curator/status", api.handle_curator_status)
    router.add_get("/api/curator/history", api.handle_curator_history)
    router.add_post("/api/curator/{action}", api.handle_curator_action)
    router.add_get("/api/sessions/status", api.handle_session_status)
    router.add_get("/api/sessions", api.handle_sessions)
    router.add_delete("/api/sessions", api.handle_sessions_delete)
    router.add_delete("/api/sessions/{session_id}", api.handle_sessions_delete)
    router.add_get("/api/background-processes", api.handle_background_processes)
    router.add_get("/api/runs", api.handle_runs)
    router.add_get("/api/runs/{run_id}/summary", api.handle_run_summary)
    router.add_get("/api/runs/{run_id}", api.handle_run_trace)
    router.add_get("/api/runs/{run_id}/events", api.handle_run_events)
    router.add_post("/api/runs/{run_id}/cancel", api.handle_run_cancel)
    router.add_post("/api/runs/{run_id}/file-changes/{change_id}/revert", api.handle_run_file_change_revert)
    router.add_post("/api/worktrees/cleanup", api.handle_worktree_cleanup)
    router.add_get("/api/settings/channels", _bind_adapter(adapter, web_settings_handlers_core.handle_settings_channels))
    router.add_post("/api/settings/channels", _bind_adapter(adapter, web_settings_handlers_core.handle_settings_channel_create))
    router.add_put(
        "/api/settings/channels/{channel_id}",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_channel_update),
    )
    router.add_put(
        "/api/settings/channels/{channel_id}/connect",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_channel_connect),
    )
    router.add_post(
        "/api/settings/channels/{channel_id}/disconnect",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_channel_disconnect),
    )
    router.add_get("/api/settings/providers", _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_providers))
    router.add_get(
        "/api/settings/auth/openai-codex",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_codex_auth_status),
    )
    router.add_post(
        "/api/settings/auth/openai-codex/login",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_codex_auth_login),
    )
    router.add_post(
        "/api/settings/auth/openai-codex/poll",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_codex_auth_poll),
    )
    router.add_post(
        "/api/settings/auth/openai-codex/logout",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_codex_auth_logout),
    )
    router.add_get("/api/settings/auth/copilot", _bind_adapter(adapter, web_settings_handlers_core.handle_settings_copilot_auth_status))
    router.add_post(
        "/api/settings/auth/copilot/login",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_copilot_auth_login),
    )
    router.add_post(
        "/api/settings/auth/copilot/poll",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_copilot_auth_poll),
    )
    router.add_post(
        "/api/settings/auth/copilot/logout",
        _bind_adapter(adapter, web_settings_handlers_core.handle_settings_copilot_auth_logout),
    )
    router.add_get("/api/settings/credentials", _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_credentials))
    router.add_post("/api/settings/credentials", _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_credential_create))
    router.add_delete(
        "/api/settings/credentials/{provider}/{credential_id}",
        _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_credential_delete),
    )
    router.add_post(
        "/api/settings/credentials/default",
        _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_credential_default),
    )
    router.add_put(
        "/api/settings/providers/{provider_id}/connect",
        _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_provider_connect),
    )
    router.add_post(
        "/api/settings/providers/{provider_id}/credential",
        _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_provider_credential),
    )
    router.add_post(
        "/api/settings/providers/{provider_id}/disconnect",
        _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_provider_disconnect),
    )
    router.add_get("/api/settings/models", _bind_adapter(adapter, web_settings_handlers_provider.handle_settings_models))
    router.add_post("/api/settings/models/select", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_model_select))
    router.add_get("/api/settings/update", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_update_status))
    router.add_post("/api/settings/update", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_update_apply))
    router.add_get("/api/settings/media", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_media))
    router.add_put("/api/settings/media", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_media_update))
    router.add_get("/api/settings/schedule", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_schedule))
    router.add_put("/api/settings/schedule", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_schedule_update))
    router.add_get("/api/settings/network", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_network))
    router.add_put("/api/settings/network", _bind_adapter(adapter, web_settings_handlers_app.handle_settings_network_update))
    router.add_get("/api/settings/search", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_search))
    router.add_get(
        "/api/settings/search/searxng-options",
        _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_search_searxng_options),
    )
    router.add_put("/api/settings/search", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_search_update))
    router.add_get("/api/settings/browser", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_browser))
    router.add_put("/api/settings/browser", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_browser_update))
    router.add_post("/api/settings/browser/test", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_browser_test))
    router.add_post("/api/settings/browser/doctor", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_browser_doctor))
    router.add_post("/api/settings/browser/install", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_browser_install))
    router.add_get("/api/settings/log", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_log))
    router.add_put("/api/settings/log", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_log_update))
    router.add_get("/api/settings/mcp", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_mcp))
    router.add_post("/api/settings/mcp", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_mcp_create))
    router.add_post("/api/settings/mcp/reload", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_mcp_reload))
    router.add_put("/api/settings/mcp/{server_id}", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_mcp_update))
    router.add_delete("/api/settings/mcp/{server_id}", _bind_adapter(adapter, web_settings_handlers_tools.handle_settings_mcp_delete))
    router.add_get("/api/cron/jobs", _bind_adapter(adapter, web_cron_api.handle_cron_jobs))
    router.add_post("/api/cron/jobs", _bind_adapter(adapter, web_cron_api.handle_cron_job_create))
    router.add_put("/api/cron/jobs/{job_id}", _bind_adapter(adapter, web_cron_api.handle_cron_job_update))
    router.add_delete("/api/cron/jobs/{job_id}", _bind_adapter(adapter, web_cron_api.handle_cron_job_delete))
    router.add_post("/api/cron/jobs/{job_id}/{action}", _bind_adapter(adapter, web_cron_api.handle_cron_job_action))
    router.add_get("/", adapter._handle_frontend_index)
    router.add_get("/index.html", adapter._handle_frontend_index)
    if adapter._frontend_dir is not None:
        router.add_get(r"/{asset_path:.+\..+}", adapter._handle_frontend_asset)
    else:
        logger.info("Web adapter did not find a frontend directory; serving API endpoints only")
