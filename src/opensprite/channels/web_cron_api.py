"""Cron HTTP API helpers for the web adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiohttp import web

from ..config import Config
from ..config.defaults import DEFAULT_CRON_TIMEZONE
from ..cron import CronJob, CronSchedule
from ..cron.presentation import format_cron_timestamp, format_cron_timing


def cron_default_timezone(adapter: Any) -> str:
    try:
        return Config.load(adapter._get_config_path()).tools.cron.default_timezone or DEFAULT_CRON_TIMEZONE
    except Exception:
        return DEFAULT_CRON_TIMEZONE


def require_cron_manager(adapter: Any) -> Any:
    agent = adapter._get_agent()
    cron_manager = getattr(agent, "cron_manager", None) if agent is not None else None
    if cron_manager is None:
        raise web.HTTPServiceUnavailable(text="Cron manager is not available")
    return cron_manager


async def get_cron_service(adapter: Any, session_id: str):
    return await require_cron_manager(adapter).get_or_create_service(session_id)


def require_session_id(value: Any) -> str:
    session_id = str(value or "").strip()
    if not session_id:
        raise web.HTTPBadRequest(text="session_id is required")
    return session_id


def split_session_for_cron(session_id: str) -> tuple[str, str]:
    if ":" in session_id:
        channel, external_chat_id = session_id.split(":", 1)
        return channel or "default", external_chat_id or "default"
    return "default", session_id or "default"


def build_cron_schedule_from_payload(adapter: Any, body: dict[str, Any]) -> tuple[CronSchedule, bool]:
    mode = str(body.get("kind") or body.get("mode") or "").strip().lower()
    default_timezone = cron_default_timezone(adapter)

    if mode == "every":
        try:
            every_seconds = int(body.get("every_seconds") or 0)
        except (TypeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="every_seconds must be an integer") from exc
        if every_seconds <= 0:
            raise web.HTTPBadRequest(text="every_seconds must be greater than zero")
        return CronSchedule(kind="every", every_ms=every_seconds * 1000), False

    if mode == "cron":
        expr = str(body.get("cron_expr") or body.get("expr") or "").strip()
        if not expr:
            raise web.HTTPBadRequest(text="cron_expr is required")
        tz = str(body.get("tz") or body.get("timezone") or default_timezone).strip() or default_timezone
        return CronSchedule(kind="cron", expr=expr, tz=tz), False

    if mode == "at":
        raw_at = str(body.get("at") or "").strip()
        if not raw_at:
            raise web.HTTPBadRequest(text="at is required")
        try:
            dt = datetime.fromisoformat(raw_at)
        except ValueError as exc:
            raise web.HTTPBadRequest(text="at must use ISO format like 2026-04-10T09:00:00") from exc
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo

            dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
        return CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000)), True

    raise web.HTTPBadRequest(text="kind must be one of every, cron, or at")


def serialize_cron_job(job: CronJob, *, default_timezone: str, session_id: str | None = None) -> dict[str, Any]:
    next_run_display = None
    if job.state.next_run_at_ms:
        next_run_display = format_cron_timestamp(job.state.next_run_at_ms, job.schedule.tz or default_timezone)
    return {
        "id": job.id,
        "session_id": session_id,
        "name": job.name,
        "enabled": job.enabled,
        "schedule": {
            "kind": job.schedule.kind,
            "at_ms": job.schedule.at_ms,
            "every_ms": job.schedule.every_ms,
            "expr": job.schedule.expr,
            "tz": job.schedule.tz,
            "display": format_cron_timing(job.schedule, default_timezone),
        },
        "payload": {
            "message": job.payload.message,
            "deliver": job.payload.deliver,
            "channel": job.payload.channel,
            "external_chat_id": job.payload.external_chat_id,
        },
        "state": {
            "next_run_at_ms": job.state.next_run_at_ms,
            "next_run_display": next_run_display,
            "last_run_at_ms": job.state.last_run_at_ms,
            "last_status": job.state.last_status,
            "last_error": job.state.last_error,
        },
        "created_at_ms": job.created_at_ms,
        "updated_at_ms": job.updated_at_ms,
        "delete_after_run": job.delete_after_run,
    }


async def handle_cron_jobs(adapter: Any, request: web.Request) -> web.Response:
    default_timezone = cron_default_timezone(adapter)
    session_id = adapter._coerce_optional_text(request.query.get("session_id"))
    if session_id:
        service = await get_cron_service(adapter, session_id)
        jobs = [serialize_cron_job(job, default_timezone=default_timezone, session_id=session_id) for job in service.list_jobs(include_disabled=True)]
    else:
        services = await require_cron_manager(adapter).get_all_services()
        jobs = [
            serialize_cron_job(job, default_timezone=default_timezone, session_id=job_session_id)
            for job_session_id, service in sorted(services.items())
            for job in service.list_jobs(include_disabled=True)
        ]
    return web.json_response({"session_id": session_id, "default_timezone": default_timezone, "jobs": jobs})


async def handle_cron_job_create(adapter: Any, request: web.Request) -> web.Response:
    body = await adapter._read_json_body(request)
    session_id = require_session_id(body.get("session_id"))
    message = adapter._coerce_optional_text(body.get("message"), default="") or ""
    if not message:
        raise web.HTTPBadRequest(text="message is required")

    schedule, delete_after_run = build_cron_schedule_from_payload(adapter, body)
    channel, external_chat_id = split_session_for_cron(session_id)
    service = await get_cron_service(adapter, session_id)
    try:
        job = service.add_job(
            name=adapter._coerce_optional_text(body.get("name"), default=message[:30]) or message[:30],
            schedule=schedule,
            message=message,
            deliver=bool(body.get("deliver", True)),
            channel=channel,
            external_chat_id=external_chat_id,
            delete_after_run=delete_after_run,
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc

    return web.json_response({"ok": True, "session_id": session_id, "job": serialize_cron_job(job, default_timezone=cron_default_timezone(adapter), session_id=session_id)})


async def handle_cron_job_update(adapter: Any, request: web.Request) -> web.Response:
    job_id = adapter._coerce_optional_text(request.match_info.get("job_id"), default="") or ""
    body = await adapter._read_json_body(request)
    session_id = require_session_id(body.get("session_id"))
    message = adapter._coerce_optional_text(body.get("message"), default="") or ""
    if not message:
        raise web.HTTPBadRequest(text="message is required")

    schedule, delete_after_run = build_cron_schedule_from_payload(adapter, body)
    channel, external_chat_id = split_session_for_cron(session_id)
    service = await get_cron_service(adapter, session_id)
    try:
        job = service.update_job(
            job_id,
            name=adapter._coerce_optional_text(body.get("name"), default=message[:30]) or message[:30],
            schedule=schedule,
            message=message,
            deliver=bool(body.get("deliver", True)),
            channel=channel,
            external_chat_id=external_chat_id,
            delete_after_run=delete_after_run,
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    if job is None:
        raise web.HTTPNotFound(text="Cron job not found")

    return web.json_response({"ok": True, "session_id": session_id, "job": serialize_cron_job(job, default_timezone=cron_default_timezone(adapter), session_id=session_id)})


async def handle_cron_job_delete(adapter: Any, request: web.Request) -> web.Response:
    job_id = adapter._coerce_optional_text(request.match_info.get("job_id"), default="") or ""
    session_id = require_session_id(request.query.get("session_id"))
    service = await get_cron_service(adapter, session_id)
    if not service.remove_job(job_id):
        raise web.HTTPNotFound(text="Cron job not found")
    return web.json_response({"ok": True, "session_id": session_id, "job_id": job_id})


async def handle_cron_job_action(adapter: Any, request: web.Request) -> web.Response:
    job_id = adapter._coerce_optional_text(request.match_info.get("job_id"), default="") or ""
    action = adapter._coerce_optional_text(request.match_info.get("action"), default="") or ""
    body = await adapter._read_json_body(request)
    session_id = require_session_id(body.get("session_id"))
    service = await get_cron_service(adapter, session_id)

    if action == "pause":
        ok = service.pause_job(job_id)
    elif action == "enable":
        ok = service.enable_job(job_id)
    elif action == "run":
        ok = await service.run_job(job_id)
    else:
        raise web.HTTPBadRequest(text="Unsupported cron job action")

    if not ok:
        raise web.HTTPNotFound(text="Cron job not found")
    job = service.get_job(job_id)
    return web.json_response(
        {
            "ok": True,
            "session_id": session_id,
            "job_id": job_id,
            "job": serialize_cron_job(job, default_timezone=cron_default_timezone(adapter), session_id=session_id) if job else None,
        }
    )
