"""Worktree-control HTTP API helpers for the web adapter."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from ..runs.events import (
    WORKTREE_CLEANUP_COMPLETED_EVENT,
    WORKTREE_CLEANUP_FAILED_EVENT,
    WORKTREE_CLEANUP_STARTED_EVENT,
)


async def handle_worktree_cleanup(adapter: Any, request: web.Request) -> web.Response:
    agent = adapter._get_agent()
    cleanup = getattr(agent, "cleanup_worktree_sandbox", None) if agent is not None else None
    if not callable(cleanup):
        raise web.HTTPServiceUnavailable(text="Worktree sandbox cleanup is not available")

    body = await adapter._read_json_body(request)
    sandbox_path = adapter._coerce_optional_text(body.get("sandbox_path"))
    if sandbox_path is None:
        raise web.HTTPBadRequest(text="sandbox_path is required")

    session_id = adapter._coerce_optional_text(body.get("session_id") or request.query.get("session_id"))
    run_id = adapter._coerce_optional_text(body.get("run_id") or request.query.get("run_id"))
    emit_run_event = getattr(agent, "_emit_run_event", None) if agent is not None else None
    can_trace = callable(emit_run_event) and session_id is not None and run_id is not None
    if can_trace:
        await emit_run_event(
            session_id,
            run_id,
            WORKTREE_CLEANUP_STARTED_EVENT,
            {"sandbox_path": sandbox_path, "status": "running"},
            channel=adapter.channel_instance_id,
            external_chat_id=adapter._external_chat_id_from_session(session_id),
        )
    try:
        result = cleanup(sandbox_path)
    except Exception as exc:
        if can_trace:
            await emit_run_event(
                session_id,
                run_id,
                WORKTREE_CLEANUP_FAILED_EVENT,
                {
                    "sandbox_path": sandbox_path,
                    "status": "failed",
                    "ok": False,
                    "reason": str(exc) or exc.__class__.__name__,
                },
                channel=adapter.channel_instance_id,
                external_chat_id=adapter._external_chat_id_from_session(session_id),
            )
        raise
    if can_trace:
        ok = bool(result.get("ok"))
        await emit_run_event(
            session_id,
            run_id,
            WORKTREE_CLEANUP_COMPLETED_EVENT if ok else WORKTREE_CLEANUP_FAILED_EVENT,
            {
                "sandbox_path": result.get("sandbox_path") or sandbox_path,
                "status": result.get("status"),
                "ok": ok,
                "reason": result.get("reason"),
            },
            channel=adapter.channel_instance_id,
            external_chat_id=adapter._external_chat_id_from_session(session_id),
        )
    return web.json_response({"ok": bool(result.get("ok")), "cleanup": adapter._json_safe(result)})
