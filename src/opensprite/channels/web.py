"""
opensprite/channels/web.py - WebSocket chat adapter

Expose a lightweight WebSocket endpoint that feeds browser messages into
MessageQueue and routes assistant replies back to the same web session.
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from aiohttp import WSMsgType, web
from pydantic import ValidationError

from .identity import build_session_id, normalize_identifier
from ..bus.events import RunEvent, SessionStatusEvent
from ..bus.message import AssistantMessage, MessageAdapter, UserMessage
from ..config import Config, MessagesConfig
from ..config.defaults import (
    DEFAULT_LOG_ENABLED,
    DEFAULT_LOG_REASONING_DETAILS,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_LOG_SYSTEM_PROMPT,
    DEFAULT_LOG_SYSTEM_PROMPT_LINES,
)
from ..ops import OperationAuditRecord
from ..runs.schema import serialize_diff_summary, serialize_run_event, serialize_work_state_todos
from ..runs.session_entries import serialize_session_entries
from ..tools.browser import _validate_navigation_url
from ..tools.browser_runtime import AgentBrowserRuntime, cloud_provider_from_config
from ..utils.log import logger
from ..utils.url import join_url_path
from .web_api import WebApiHandlers
from . import web_frontend_runtime
from . import web_settings_support
from .web_routes import register_web_routes


class WebAdapter(MessageAdapter):
    """WebSocket adapter for browser-based chat clients."""

    DEFAULT_CONFIG = {
        "host": "127.0.0.1",
        "port": 8765,
        "path": "/ws",
        "health_path": "/healthz",
        "max_message_size": 1024 * 1024,
        "frontend_auto_build": True,
        "frontend_auto_install": True,
        "frontend_build_timeout": 120,
        "frontend_install_timeout": 300,
        "auth_token": "",
    }

    def __init__(self, mq=None, config: dict[str, Any] | None = None):
        self.mq = mq
        self.messages = getattr(mq, "messages", None) or MessagesConfig()
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.channel_type = "web"
        self.channel_instance_id = normalize_identifier(str(self.config.get("id") or "web"), fallback="web")
        self.app: web.Application | None = None
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self._shutdown_event = asyncio.Event()
        self._started_event = asyncio.Event()
        self._session_connections: dict[str, set[web.WebSocketResponse]] = {}
        self._socket_sessions: dict[web.WebSocketResponse, set[str]] = {}
        self._api = WebApiHandlers(self)
        self._maybe_build_frontend()
        self._frontend_dir = self._resolve_frontend_dir()

    def _get_host(self) -> str:
        return str(self.config.get("host", self.DEFAULT_CONFIG["host"]))

    def _get_port(self) -> int:
        return int(self.config.get("port", self.DEFAULT_CONFIG["port"]))

    def _get_max_message_size(self) -> int:
        return int(self.config.get("max_message_size", self.DEFAULT_CONFIG["max_message_size"]))

    def _get_auth_token(self) -> str:
        return str(self.config.get("auth_token", "") or "").strip()

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        normalized = str(host or "").strip().strip("[]").lower()
        if normalized in {"localhost"}:
            return True
        if normalized in {"", "*", "0.0.0.0", "::", "::0"}:
            return False
        try:
            return ipaddress.ip_address(normalized).is_loopback
        except ValueError:
            return False

    def _validate_bind_auth_config(self, host: str) -> None:
        if self._is_loopback_host(host):
            return
        if self._get_auth_token():
            return
        raise RuntimeError(
            "WebAdapter refuses to bind to a non-loopback host without auth_token configured. "
            "Use host=127.0.0.1 for local-only access or set a strong web auth_token."
        )

    def _auth_required(self, request: web.Request) -> bool:
        token = self._get_auth_token()
        if not token:
            return False
        path = request.path or ""
        return path == self._get_path("path") or path.startswith("/api/")

    def _request_has_valid_auth(self, request: web.Request) -> bool:
        token = self._get_auth_token()
        if not token:
            return True
        auth_header = request.headers.get("Authorization", "").strip()
        supplied = ""
        if auth_header.lower().startswith("bearer "):
            supplied = auth_header[7:].strip()
        if not supplied:
            supplied = str(request.query.get("access_token") or "").strip()
        return bool(supplied) and hmac.compare_digest(supplied, token)

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        if self._auth_required(request) and not self._request_has_valid_auth(request):
            raise web.HTTPUnauthorized(text="Unauthorized")
        return await handler(request)

    def _get_frontend_build_timeout(self) -> int:
        return int(self.config.get("frontend_build_timeout", self.DEFAULT_CONFIG["frontend_build_timeout"]))

    def _get_frontend_install_timeout(self) -> int:
        return int(self.config.get("frontend_install_timeout", self.DEFAULT_CONFIG["frontend_install_timeout"]))

    def _get_path(self, key: str) -> str:
        raw = str(self.config.get(key, self.DEFAULT_CONFIG[key]) or self.DEFAULT_CONFIG[key]).strip() or "/"
        return raw if raw.startswith("/") else f"/{raw}"

    def _run_frontend_command(self, source_dir: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return web_frontend_runtime.run_frontend_command(source_dir, args, timeout)

    def _maybe_build_frontend(self) -> None:
        web_frontend_runtime.maybe_build_frontend(
            self.config,
            default_config=self.DEFAULT_CONFIG,
            module_path=Path(__file__).resolve(),
            build_timeout=self._get_frontend_build_timeout(),
            install_timeout=self._get_frontend_install_timeout(),
            logger=logger,
        )

    def _resolve_frontend_dir(self) -> Path | None:
        return web_frontend_runtime.resolve_frontend_dir(self.config, module_path=Path(__file__).resolve())

    def _resolve_frontend_asset(self, asset_path: str) -> Path:
        if self._frontend_dir is None:
            raise web.HTTPNotFound()

        target = (self._frontend_dir / asset_path).resolve(strict=False)
        if not target.is_relative_to(self._frontend_dir) or not target.is_file():
            raise web.HTTPNotFound()
        return target

    def _build_session_id(self, external_chat_id: str | None) -> str:
        normalized_external_chat_id = self._coerce_optional_text(external_chat_id, default="default") or "default"
        return build_session_id(self.channel_instance_id, normalized_external_chat_id)

    @property
    def bound_port(self) -> int | None:
        if self.site is None:
            return None
        server = getattr(self.site, "_server", None)
        sockets = getattr(server, "sockets", None) or []
        if not sockets:
            return None
        return int(sockets[0].getsockname()[1])

    async def wait_until_started(self, timeout: float = 5.0) -> None:
        """Wait until the HTTP server starts listening."""
        await asyncio.wait_for(self._started_event.wait(), timeout=timeout)

    def _bind_session(self, session_id: str, ws: web.WebSocketResponse) -> None:
        self._session_connections.setdefault(session_id, set()).add(ws)
        self._socket_sessions.setdefault(ws, set()).add(session_id)

    def _unbind_socket(self, ws: web.WebSocketResponse) -> None:
        for session_id in self._socket_sessions.pop(ws, set()):
            session_connections = self._session_connections.get(session_id)
            if session_connections is None:
                continue
            session_connections.discard(ws)
            if not session_connections:
                self._session_connections.pop(session_id, None)

    @staticmethod
    def _coerce_metadata(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _json_safe(value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            return json.loads(json.dumps(value, default=str))

    def _get_storage(self) -> Any | None:
        return getattr(getattr(self.mq, "agent", None), "storage", None)

    def _get_agent(self) -> Any | None:
        return getattr(self.mq, "agent", None)

    def _get_session_status_service(self) -> Any | None:
        return getattr(self.mq, "session_status", None)

    def _get_config_path(self) -> Path:
        agent = self._get_agent()
        raw_path = getattr(agent, "config_path", None) if agent is not None else None
        if raw_path is not None:
            return Path(raw_path).expanduser().resolve()
        config = Config.load(None)
        return Path(config.source_path or Path.home() / ".opensprite" / "opensprite.json").resolve()

    def _get_app_home(self) -> Path:
        return self._get_config_path().parent

    @staticmethod
    def _browser_runtime_status() -> dict[str, Any]:
        return web_frontend_runtime.browser_runtime_status(WebAdapter._browser_command_prefix())

    @staticmethod
    def _browser_command_prefix() -> list[str]:
        return web_frontend_runtime.browser_command_prefix()

    @classmethod
    async def _run_browser_doctor_command(
        cls,
        args: list[str],
        *,
        timeout: int = 20,
        launch_args: str = "",
    ) -> dict[str, Any]:
        return await web_frontend_runtime.run_browser_doctor_command(
            args,
            timeout=timeout,
            launch_args=launch_args,
            command_prefix=cls._browser_command_prefix(),
        )

    @classmethod
    async def _run_browser_install_command(cls, *, timeout: int = 300) -> dict[str, Any]:
        return await web_frontend_runtime.run_browser_install_command(
            timeout=timeout,
            command_prefix=cls._browser_command_prefix(),
        )

    @staticmethod
    def _with_browser_diagnostic(result: dict[str, Any] | None) -> dict[str, Any]:
        return web_frontend_runtime.with_browser_diagnostic(result)

    @staticmethod
    async def _read_json_body(request: web.Request) -> dict[str, Any]:
        return await web_settings_support.read_json_body(request)

    def _mcp_runtime_payload(self) -> dict[str, Any]:
        agent = self._get_agent()
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

    def _with_mcp_runtime(self, payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["runtime"] = self._mcp_runtime_payload()
        return updated

    def _serialize_run(self, run: Any) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "session_id": run.session_id,
            "status": run.status,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "finished_at": run.finished_at,
            "metadata": self._json_safe(dict(run.metadata or {})),
        }

    def _serialize_message(self, message: Any) -> dict[str, Any]:
        metadata = getattr(message, "metadata", {})
        return {
            "role": str(getattr(message, "role", "assistant") or "assistant"),
            "content": str(getattr(message, "content", "") or ""),
            "tool_name": getattr(message, "tool_name", None),
            "metadata": self._json_safe(dict(metadata or {})),
            "created_at": float(getattr(message, "timestamp", 0) or 0),
        }

    def _serialize_work_state(self, state: Any) -> dict[str, Any] | None:
        if state is None:
            return None
        return {
            "session_id": state.session_id,
            "objective": state.objective,
            "kind": state.kind,
            "status": state.status,
            "steps": list(state.steps or ()),
            "constraints": list(state.constraints or ()),
            "done_criteria": list(state.done_criteria or ()),
            "long_running": bool(state.long_running),
            "coding_task": bool(state.coding_task),
            "expects_code_change": bool(state.expects_code_change),
            "expects_verification": bool(state.expects_verification),
            "current_step": state.current_step,
            "next_step": state.next_step,
            "completed_steps": list(state.completed_steps or ()),
            "pending_steps": list(state.pending_steps or ()),
            "blockers": list(state.blockers or ()),
            "verification_targets": list(state.verification_targets or ()),
            "resume_hint": state.resume_hint,
            "last_progress_signals": list(state.last_progress_signals or ()),
            "file_change_count": int(state.file_change_count or 0),
            "touched_paths": list(state.touched_paths or ()),
            "verification_attempted": bool(state.verification_attempted),
            "verification_passed": bool(state.verification_passed),
            "last_next_action": state.last_next_action,
            "delegated_tasks": [
                {
                    "task_id": task.task_id,
                    "prompt_type": task.prompt_type,
                    "status": task.status,
                    "selected": bool(task.selected),
                    "summary": task.summary,
                    "error": task.error,
                    "child_session_id": task.child_session_id,
                    "last_child_run_id": task.last_child_run_id,
                    "metadata": self._json_safe(dict(task.metadata or {})),
                    "created_at": float(task.created_at or 0),
                    "updated_at": float(task.updated_at or 0),
                }
                for task in list(state.delegated_tasks or ())
            ],
            "active_delegate_task_id": state.active_delegate_task_id,
            "active_delegate_prompt_type": state.active_delegate_prompt_type,
            **(
                {"follow_up_workflow": str(state.metadata.get("follow_up_workflow") or "").strip()}
                if str(state.metadata.get("follow_up_workflow") or "").strip()
                else {}
            ),
            **(
                {"follow_up_step_id": str(state.metadata.get("follow_up_step_id") or "").strip()}
                if str(state.metadata.get("follow_up_step_id") or "").strip()
                else {}
            ),
            **(
                {"follow_up_step_label": str(state.metadata.get("follow_up_step_label") or "").strip()}
                if str(state.metadata.get("follow_up_step_label") or "").strip()
                else {}
            ),
            **(
                {"follow_up_prompt_type": str(state.metadata.get("follow_up_prompt_type") or "").strip()}
                if str(state.metadata.get("follow_up_prompt_type") or "").strip()
                else {}
            ),
            **(
                {"verification_action": str(state.metadata.get("verification_action") or "").strip()}
                if str(state.metadata.get("verification_action") or "").strip()
                else {}
            ),
            **(
                {"verification_path": str(state.metadata.get("verification_path") or "").strip()}
                if str(state.metadata.get("verification_path") or "").strip()
                else {}
            ),
            **(
                {"verification_pytest_args": self._json_safe(list(state.metadata.get("verification_pytest_args") or []))}
                if isinstance(state.metadata.get("verification_pytest_args"), list) and state.metadata.get("verification_pytest_args")
                else {}
            ),
            **(
                {"active_task_detail": str(state.metadata.get("active_task_detail") or "").strip()}
                if str(state.metadata.get("active_task_detail") or "").strip()
                else {}
            ),
            "metadata": self._json_safe(dict(state.metadata or {})),
            "todos": serialize_work_state_todos(state),
            "created_at": float(state.created_at or 0),
            "updated_at": float(state.updated_at or 0),
        }

    @staticmethod
    def _session_title(messages: list[Any], fallback: str) -> str:
        for message in messages:
            role = str(getattr(message, "role", "") or "")
            content = " ".join(str(getattr(message, "content", "") or "").split())
            if role == "user" and content:
                return f"{content[:30]}..." if len(content) > 30 else content
        return fallback

    @staticmethod
    def _session_updated_at(messages: list[Any], runs: list[Any]) -> float:
        timestamps = [float(getattr(message, "timestamp", 0) or 0) for message in messages]
        timestamps.extend(float(getattr(run, "updated_at", 0) or 0) for run in runs)
        return max(timestamps, default=0.0)

    async def _serialize_session_summary(self, storage: Any, session_id: str, *, message_limit: int) -> dict[str, Any]:
        messages = await storage.get_messages(session_id, limit=message_limit)
        display_messages = [message for message in messages if str(getattr(message, "role", "") or "") in {"user", "assistant"}]
        latest_runs = await storage.get_runs(session_id, limit=1)
        latest_traces = []
        for run in latest_runs:
            get_run_trace = getattr(storage, "get_run_trace", None)
            trace = await get_run_trace(session_id, run.run_id) if callable(get_run_trace) else None
            if trace is not None:
                latest_traces.append(trace)
        get_work_state = getattr(storage, "get_work_state", None)
        work_state = await get_work_state(session_id) if callable(get_work_state) else None
        external_chat_id = self._external_chat_id_from_session(session_id)
        fallback_title = external_chat_id or session_id
        return {
            "session_id": session_id,
            "channel": self._channel_from_session(session_id),
            "external_chat_id": external_chat_id,
            "title": self._session_title(display_messages, fallback_title),
            "updated_at": self._session_updated_at(messages, latest_runs),
            "status": self._serialize_session_status(session_id),
            "message_count": await storage.get_message_count(session_id),
            "messages": [self._serialize_message(message) for message in display_messages],
            "runs": [self._serialize_run(run) for run in latest_runs],
            "entries": serialize_session_entries(display_messages, latest_traces),
            "diff_summary": serialize_diff_summary(latest_traces[0]) if latest_traces else None,
            "work_state": self._serialize_work_state(work_state),
        }

    def _serialize_session_status(self, session_id: str) -> dict[str, Any]:
        service = self._get_session_status_service()
        if service is None:
            return {"session_id": session_id, "status": "idle", "metadata": {}}
        item = service.get(session_id)
        return {
            "session_id": item.session_id,
            "status": item.status,
            "updated_at": item.updated_at,
            "metadata": self._json_safe(dict(item.metadata or {})),
        }

    def _require_storage(self) -> Any:
        storage = self._get_storage()
        if storage is None:
            raise web.HTTPServiceUnavailable(text="Run trace storage is not available")
        return storage

    @staticmethod
    def _coerce_limit(value: str | None, *, default: int = 20, maximum: int = 100) -> int:
        if value is None or not value.strip():
            return default
        try:
            limit = int(value)
        except ValueError as exc:
            raise web.HTTPBadRequest(text="limit must be an integer") from exc
        if limit < 1:
            raise web.HTTPBadRequest(text="limit must be greater than zero")
        return min(limit, maximum)

    @staticmethod
    def _external_chat_id_from_session(session_id: str) -> str | None:
        parts = str(session_id or "").split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            return parts[1].strip()
        compact = str(session_id or "").strip()
        return compact or None

    @staticmethod
    def _channel_from_session(session_id: str) -> str:
        parts = str(session_id or "").split(":", 1)
        return parts[0].strip() if len(parts) == 2 and parts[0].strip() else "unknown"

    @staticmethod
    def _coerce_media_list(value: Any) -> list[str] | None:
        if not isinstance(value, list):
            return None
        items = [str(item) for item in value if isinstance(item, str) and item.strip()]
        return items or None

    @staticmethod
    def _coerce_optional_text(value: Any, *, default: str | None = None) -> str | None:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    def _parse_incoming_payload(self, raw_text: str) -> dict[str, Any]:
        stripped = raw_text.strip()
        if not stripped:
            raise ValueError("Message text cannot be empty")

        if stripped.startswith("{"):
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON payload: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValueError("JSON payload must be an object")
            return payload

        return {"text": raw_text}

    async def to_user_message(self, raw_message: Any) -> UserMessage:
        payload = dict(raw_message) if isinstance(raw_message, dict) else {}
        external_chat_id = self._coerce_optional_text(payload.get("external_chat_id"))
        session_id = self._coerce_optional_text(payload.get("session_id"))
        if session_id is None:
            session_id = self._build_session_id(external_chat_id)

        return UserMessage(
            text=self._coerce_optional_text(payload.get("text"), default="") or "",
            channel=self.channel_instance_id,
            external_chat_id=external_chat_id,
            session_id=session_id,
            sender_id=self._coerce_optional_text(payload.get("sender_id"), default="web-user"),
            sender_name=self._coerce_optional_text(payload.get("sender_name")),
            images=self._coerce_media_list(payload.get("images")),
            audios=self._coerce_media_list(payload.get("audios")),
            videos=self._coerce_media_list(payload.get("videos")),
            metadata={
                "channel_type": self.channel_type,
                "channel_instance_id": self.channel_instance_id,
                **self._coerce_metadata(payload.get("metadata")),
            },
            raw=payload,
        )

    async def send(self, message: AssistantMessage) -> None:
        session_id = message.session_id or self._build_session_id(message.external_chat_id)
        session_connections = self._session_connections.get(session_id) or set()
        live_connections = [ws for ws in session_connections if not ws.closed]
        if not live_connections:
            logger.warning("Web reply dropped because no active socket is bound to session {}", session_id)
            return

        payload = {
            "type": "message",
            "channel": self.channel_instance_id,
            "channel_type": self.channel_type,
            "external_chat_id": message.external_chat_id,
            "session_id": session_id,
            "text": message.text,
            "metadata": dict(message.metadata or {}),
        }
        for ws in live_connections:
            await ws.send_json(payload)

    async def send_run_event(self, event: RunEvent) -> None:
        """Send one structured run event to the browser session socket."""
        payload = serialize_run_event(
            event,
            include_event_id=False,
            extra={
                "type": "run_event",
                "channel": event.channel or self._channel_from_session(event.session_id),
                "channel_type": self.channel_type,
                "external_chat_id": event.external_chat_id,
            },
        )
        sent: set[web.WebSocketResponse] = set()
        session_connections = self._session_connections.get(event.session_id) or set()
        for session_ws in list(session_connections):
            if session_ws.closed:
                continue
            await session_ws.send_json(payload)
            sent.add(session_ws)

        if self._channel_from_session(event.session_id) == self.channel_instance_id:
            return

        # Browser clients can inspect external-channel sessions, so broadcast
        # non-web run events to connected Web inspectors as live trace updates.
        for ws in list(self._socket_sessions.keys()):
            if ws in sent or ws.closed:
                continue
            await ws.send_json(payload)

    async def send_session_status(self, event: SessionStatusEvent) -> None:
        """Send one session status update to interested browser sockets."""
        payload = {
            "type": "session_status",
            "channel": self._channel_from_session(event.session_id),
            "session_id": event.session_id,
            "status": event.status,
            "updated_at": event.updated_at,
            "metadata": self._json_safe(dict(event.metadata or {})),
        }
        sent: set[web.WebSocketResponse] = set()
        session_connections = self._session_connections.get(event.session_id) or set()
        for session_ws in list(session_connections):
            if session_ws.closed:
                continue
            await session_ws.send_json(payload)
            sent.add(session_ws)

        # The Web UI can inspect external-channel sessions through history, so
        # broadcast non-web status changes to connected browser inspectors too.
        for ws in list(self._socket_sessions.keys()):
            if ws in sent or ws.closed:
                continue
            await ws.send_json(payload)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "channel": self.channel_instance_id, "channel_type": self.channel_type})

    async def _handle_frontend_index(self, request: web.Request) -> web.FileResponse:
        if self._frontend_dir is None:
            npm_build = "npm.cmd run build" if os.name == "nt" else "npm run build"
            raise web.HTTPServiceUnavailable(
                text=(
                    "OpenSprite web frontend is not built yet. "
                    "Install Node.js 20.19+ or 22.12+ and npm if needed, "
                    f"then restart the gateway or run `{npm_build}` in frontend."
                )
            )
        return web.FileResponse(self._resolve_frontend_asset("index.html"))

    async def _handle_frontend_asset(self, request: web.Request) -> web.FileResponse:
        asset_path = request.match_info.get("asset_path", "")
        return web.FileResponse(self._resolve_frontend_asset(asset_path))

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        if self.mq is None:
            raise RuntimeError("WebAdapter requires a MessageQueue instance")

        ws = web.WebSocketResponse(max_msg_size=self._get_max_message_size())
        await ws.prepare(request)

        default_external_chat_id = (request.query.get("external_chat_id") or uuid4().hex).strip() or uuid4().hex
        default_session_id = self._build_session_id(default_external_chat_id)
        self._bind_session(default_session_id, ws)

        await ws.send_json(
            {
                "type": "session",
                "channel": self.channel_instance_id,
                "channel_type": self.channel_type,
                "external_chat_id": default_external_chat_id,
                "session_id": default_session_id,
            }
        )

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        payload = self._parse_incoming_payload(msg.data)
                        payload_external_chat_id = self._coerce_optional_text(
                            payload.get("external_chat_id"), default=default_external_chat_id
                        )
                        payload["external_chat_id"] = payload_external_chat_id
                        payload.setdefault("session_id", self._build_session_id(payload_external_chat_id))
                        user_message = await self.to_user_message(payload)
                    except ValueError as exc:
                        await ws.send_json({"type": "error", "error": str(exc)})
                        continue

                    self._bind_session(user_message.session_id or default_session_id, ws)
                    await self.mq.enqueue(user_message)
                    continue

                if msg.type == WSMsgType.ERROR:
                    logger.warning("WebSocket connection closed with error: {}", ws.exception())
        finally:
            self._unbind_socket(ws)

        return ws

    async def _on_response(self, response: AssistantMessage, channel: str, external_chat_id: str | None) -> None:
        await self.send(response)

    async def _on_run_event(self, event: RunEvent) -> None:
        await self.send_run_event(event)

    async def _on_session_status(self, event: SessionStatusEvent) -> None:
        await self.send_session_status(event)

    async def _shutdown(self) -> None:
        for ws in list(self._socket_sessions):
            self._unbind_socket(ws)
            if not ws.closed:
                await ws.close()

        if self.mq is not None:
            self.mq.unregister_response_handler(self.channel_instance_id)
            self.mq.unregister_run_event_handler(self.channel_instance_id)
            self.mq.unregister_session_status_handler(self.channel_instance_id)

        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None

        self.site = None
        self.app = None

    async def run(self) -> None:
        if self.mq is None:
            raise RuntimeError("WebAdapter requires a MessageQueue instance")

        host = self._get_host()
        port = self._get_port()
        ws_path = self._get_path("path")
        health_path = self._get_path("health_path")
        self._validate_bind_auth_config(host)

        middlewares = [self._auth_middleware] if self._get_auth_token() else []
        self.app = web.Application(middlewares=middlewares)
        register_web_routes(self, ws_path=ws_path, health_path=health_path)

        self.mq.register_response_handler(self.channel_instance_id, self._on_response)
        self.mq.register_run_event_handler(self.channel_instance_id, self._on_run_event)
        self.mq.register_session_status_handler(self.channel_instance_id, self._on_session_status)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, host=host, port=port)
        await self.site.start()
        self._started_event.set()

        logger.info(
            "Web adapter listening on ws://{}:{}{} (health=http://{}:{}{}, frontend={})",
            host,
            self.bound_port,
            ws_path,
            host,
            self.bound_port,
            health_path,
            self._frontend_dir if self._frontend_dir is not None else "disabled",
        )

        try:
            await self._shutdown_event.wait()
        finally:
            await self._shutdown()
