"""CLI command helpers for one-shot chat turns."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from typing import Any

import typer

from ..channels.cli import CliAdapter, CliChatResult
from ..config import Config
from ..runtime import (
    apply_network_environment,
    create_agent,
    start_search_queue_worker,
    stop_background_task,
)
from ..utils.log import setup_log


def _event_payload(event: Any) -> dict[str, Any]:
    return {
        "run_id": event.run_id,
        "event_type": event.event_type,
        "status": event.payload.get("status") if isinstance(event.payload, dict) else None,
        "created_at": event.created_at,
    }


async def run_cli_chat(
    message: str,
    *,
    config_path: str | Path | None = None,
    external_chat_id: str = "default",
    session_id: str | None = None,
    sender_name: str = "OpenSprite CLI",
    timeout_seconds: float = 120.0,
) -> tuple[CliChatResult, dict[str, Any]]:
    """Run a one-shot local CLI channel turn through the normal agent queue."""
    if not message.strip():
        raise ValueError("message is required")

    early_app_home = Path(config_path).expanduser().resolve().parent if config_path is not None else None
    setup_log(app_home=early_app_home)
    config = Config.load(config_path)
    app_home = config.source_path.parent if config.source_path is not None else early_app_home
    setup_log(config.log, app_home=app_home)
    apply_network_environment(config)

    started = time.monotonic()
    agent, mq, cron_manager = await create_agent(config)
    search_queue_worker = start_search_queue_worker(getattr(agent, "search_store", None))
    processor = asyncio.create_task(mq.process_queue())
    trace_summary: dict[str, Any] = {}

    try:
        await agent.connect_mcp()
        await cron_manager.start()
        adapter = CliAdapter(
            mq,
            external_chat_id=external_chat_id,
            session_id=session_id,
            sender_name=sender_name,
        )
        result = await adapter.run_once(message, timeout=timeout_seconds)
        if result.run_id:
            trace = await agent.storage.get_run_trace(result.response.session_id or adapter.session_id, result.run_id)
            if trace is not None:
                trace_summary = {
                    "event_count": len(trace.events),
                    "part_count": len(trace.parts),
                    "file_change_count": len(trace.file_changes),
                }
        trace_summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return result, trace_summary
    finally:
        await mq.stop()
        await stop_background_task(processor, name="message queue processor")
        await stop_background_task(search_queue_worker, name="search embedding queue worker")
        await cron_manager.stop()
        await agent.close_background_maintenance()
        await agent.close_background_skill_reviews()
        close_background_processes = getattr(agent, "close_background_processes", None)
        if close_background_processes is not None:
            await close_background_processes()
        await agent.close_mcp()


def result_payload(result: CliChatResult, trace_summary: dict[str, Any]) -> dict[str, Any]:
    """Convert a chat result into stable JSON for scripts."""
    return {
        "ok": not bool(result.error),
        "session_id": result.response.session_id,
        "external_chat_id": result.response.external_chat_id,
        "run_id": result.run_id,
        "run_status": result.run_status,
        "reply": result.response.text,
        "run_event_count": len(result.run_events),
        "tool_call_count": result.tool_call_count,
        "trace": trace_summary,
        "recent_events": [_event_payload(event) for event in result.run_events[-8:]],
    }


def _render_text(result: CliChatResult, trace_summary: dict[str, Any]) -> None:
    typer.echo("OpenSprite CLI Chat")
    typer.echo(f"Session: {result.response.session_id}")
    if result.run_id:
        status = f" [{result.run_status}]" if result.run_status else ""
        typer.echo(f"Run: {result.run_id}{status}")
    typer.echo(f"Events: run={len(result.run_events)} tools={result.tool_call_count}")
    if trace_summary:
        typer.echo(
            "Trace: "
            f"events={trace_summary.get('event_count', 0)} "
            f"parts={trace_summary.get('part_count', 0)} "
            f"files={trace_summary.get('file_change_count', 0)}"
        )
    elapsed = trace_summary.get("elapsed_seconds")
    if elapsed is not None:
        typer.echo(f"Elapsed: {elapsed}s")
    typer.echo("")
    typer.echo(result.response.text)


def chat_command(
    *,
    message: str,
    config: str | None,
    external_chat_id: str,
    session_id: str | None,
    sender_name: str,
    timeout_seconds: float,
    json_output: bool,
) -> None:
    """Run the Typer-facing one-shot chat command."""
    try:
        result, trace_summary = asyncio.run(
            run_cli_chat(
                message,
                config_path=config,
                external_chat_id=external_chat_id,
                session_id=session_id,
                sender_name=sender_name,
                timeout_seconds=timeout_seconds,
            )
        )
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(result_payload(result, trace_summary), ensure_ascii=False, indent=2))
        return
    _render_text(result, trace_summary)
