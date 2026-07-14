"""Worktree-control HTTP API helpers for the web adapter."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import web

from .identity import external_chat_id_from_session
from ..runs.events import (
    WORKTREE_CLEANUP_COMPLETED_EVENT,
    WORKTREE_CLEANUP_FAILED_EVENT,
    WORKTREE_CLEANUP_STARTED_EVENT,
)


_WORKTREE_CLEANUP_FINALIZATION_TIMEOUT_SECONDS = 5.0
_WORKTREE_CLEANUP_FINALIZATION_TASKS: set[asyncio.Task[dict[str, Any]]] = set()


def _track_worktree_cleanup_finalization(task: asyncio.Task[dict[str, Any]]) -> None:
    """Keep irreversible cleanup finalization alive after request cancellation."""
    _WORKTREE_CLEANUP_FINALIZATION_TASKS.add(task)

    def _consume_result(completed: asyncio.Task[dict[str, Any]]) -> None:
        _WORKTREE_CLEANUP_FINALIZATION_TASKS.discard(completed)
        try:
            completed.result()
        except BaseException:
            pass

    task.add_done_callback(_consume_result)


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
    if session_id is None:
        raise web.HTTPBadRequest(text="session_id is required")
    if run_id is None:
        raise web.HTTPBadRequest(text="run_id is required")
    emit_run_event = getattr(agent, "_emit_run_event", None) if agent is not None else None
    can_trace = callable(emit_run_event)
    if can_trace:
        await emit_run_event(
            session_id,
            run_id,
            WORKTREE_CLEANUP_STARTED_EVENT,
            {"sandbox_path": sandbox_path, "status": "running"},
            channel=adapter.channel_instance_id,
            external_chat_id=external_chat_id_from_session(session_id),
            require_persistence=True,
        )

    async def _cleanup_and_finalize() -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(
                cleanup,
                sandbox_path,
                session_id=session_id,
                run_id=run_id,
            )
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
                    external_chat_id=external_chat_id_from_session(session_id),
                    require_persistence=True,
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
                external_chat_id=external_chat_id_from_session(session_id),
                require_persistence=True,
            )
        return result

    finalization_task = asyncio.create_task(_cleanup_and_finalize())
    _track_worktree_cleanup_finalization(finalization_task)
    try:
        result = await asyncio.shield(finalization_task)
    except asyncio.CancelledError as cancel_error:
        try:
            await asyncio.wait_for(
                asyncio.shield(finalization_task),
                timeout=_WORKTREE_CLEANUP_FINALIZATION_TIMEOUT_SECONDS,
            )
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            # Preserve the original request cancellation. The tracked task
            # must stay alive because cancelling a to_thread future cannot
            # stop an irreversible cleanup that may already be in progress.
            pass
        raise cancel_error

    return web.json_response({"ok": bool(result.get("ok")), "cleanup": adapter._json_safe(result)})
