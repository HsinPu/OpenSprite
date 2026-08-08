"""Durable run persistence and live event delivery."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from ...core.contracts.bus_events import RunEvent
from ...core.contracts.messages import CLIENT_TURN_ID_METADATA_KEY
from ...core.contracts.run_lifecycle import (
    RUN_CANCELLED_EVENT,
    RUN_CANCELLED_STATUS,
    RUN_COMPLETED_STATUS,
    RUN_FAILED_EVENT,
    RUN_FINISHED_EVENT,
    RUN_RUNNING_STATUS,
    RUN_STARTED_EVENT,
)
from ...core.ports.storage import StorageProvider
from ...core.serialization import json_safe_payload
from opensprite.core.logging import logger


RUN_PART_CONTENT_MAX_CHARS = 20_000
TERMINAL_EVENT_DELIVERY_TIMEOUT_SECONDS = 5.0
TRACE_OPERATION_TYPE_FIELD = "operation_type"
TRACE_TARGET_FIELD = "target"
TRACE_ROLLBACK_AVAILABLE_FIELD = "rollback_available"


def truncate_run_part_content(
    content: str,
    max_chars: int = RUN_PART_CONTENT_MAX_CHARS,
) -> tuple[str, dict[str, Any]]:
    """Bound durable run-part content while preserving useful head/tail context."""
    text = str(content or "")
    original_len = len(text)
    if original_len <= max_chars:
        return text, {"content_truncated": False, "content_original_len": original_len}

    marker = f"\n... (run part content truncated, original {original_len} chars) ...\n"
    tail_chars = max(1000, max_chars // 4)
    head_chars = max(0, max_chars - tail_chars - len(marker))
    truncated = text[:head_chars].rstrip() + marker + text[-tail_chars:].lstrip()
    return truncated, {"content_truncated": True, "content_original_len": original_len}


class RunEventPersistenceError(RuntimeError):
    """Raised when a caller requires an event to be durably stored."""


class RunEventSink:
    """Persists run events and publishes their live bus representation."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        message_bus_getter: Callable[[], Any | None],
    ):
        self.storage = storage
        self._message_bus_getter = message_bus_getter

    async def emit(
        self,
        session_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        channel: str | None = None,
        external_chat_id: str | None = None,
        require_persistence: bool = False,
    ) -> None:
        """Persist and publish one structured run event."""
        created_at = time.time()
        safe_payload = json_safe_payload(payload)
        stored_event = None
        try:
            stored_event = await self.storage.add_run_event(
                session_id,
                run_id,
                event_type,
                payload=safe_payload,
                created_at=created_at,
            )
        except Exception as e:
            logger.warning("[{}] run.event.persist.failed | run_id={} type={} error={}", session_id, run_id, event_type, e)
            if require_persistence:
                raise RunEventPersistenceError(
                    f"Failed to persist run event {event_type!r} for run {run_id!r}"
                ) from e
        if require_persistence and stored_event is None:
            raise RunEventPersistenceError(
                f"Run event persistence is unavailable for event {event_type!r} on run {run_id!r}"
            )

        message_bus = self._message_bus_getter()
        if message_bus is None or not channel or external_chat_id is None:
            return
        try:
            await message_bus.publish_run_event(
                RunEvent(
                    channel=channel,
                    external_chat_id=str(external_chat_id),
                    session_id=session_id,
                    run_id=run_id,
                    event_type=event_type,
                    payload=safe_payload,
                    created_at=created_at,
                )
            )
        except Exception as e:
            logger.warning("[{}] run.event.publish.failed | run_id={} type={} error={}", session_id, run_id, event_type, e)


class RunTraceRecorder:
    """Small service for durable run lifecycle, events, and ordered parts."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        message_bus_getter: Callable[[], Any | None],
    ):
        self.storage = storage
        self._message_bus_getter = message_bus_getter
        self.events = RunEventSink(storage=storage, message_bus_getter=message_bus_getter)

    async def create_run(
        self,
        session_id: str,
        run_id: str,
        *,
        status: str = "running",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a durable run record."""
        created = await self.storage.create_run(session_id, run_id, status=status, metadata=metadata)
        if created is None:
            raise RuntimeError(f"Run storage did not create {run_id!r} for session {session_id!r}.")

    async def update_run_status(
        self,
        session_id: str,
        run_id: str,
        status: str,
        *,
        metadata: dict[str, Any] | None = None,
        finished_at: float | None = None,
    ) -> None:
        """Update a durable run record.

        Terminal status is the source of truth for CLI, Web, and smoke clients,
        so persistence failures must propagate instead of creating a false
        successful terminal event while the durable row remains ``running``.
        """
        updated = await self.storage.update_run_status(
            session_id,
            run_id,
            status,
            metadata=metadata,
            finished_at=finished_at,
        )
        if updated is None:
            raise RuntimeError(f"Run storage did not update {run_id!r} for session {session_id!r}.")

    async def add_part(
        self,
        session_id: str,
        run_id: str,
        part_type: str,
        *,
        content: str = "",
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist one ordered run artifact."""
        try:
            stored_content, content_metadata = truncate_run_part_content(str(content or ""))
            safe_metadata = json_safe_payload(metadata)
            safe_metadata.update(content_metadata)
            await self.storage.add_run_part(
                session_id,
                run_id,
                part_type,
                content=stored_content,
                tool_name=tool_name,
                metadata=safe_metadata,
            )
        except Exception as e:
            logger.warning("[{}] run.part.persist.failed | run_id={} type={} error={}", session_id, run_id, part_type, e)

    async def emit_event(
        self,
        session_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        channel: str | None = None,
        external_chat_id: str | None = None,
        require_persistence: bool = False,
    ) -> None:
        """Persist and publish one structured run event."""
        await self.events.emit(
            session_id,
            run_id,
            event_type,
            payload,
            channel=channel,
            external_chat_id=external_chat_id,
            require_persistence=require_persistence,
        )

    async def start_turn_run(
        self,
        session_id: str,
        run_id: str,
        *,
        channel: str | None,
        external_chat_id: str | None,
        sender_id: str | None,
        sender_name: str | None,
        text: str | None,
        images: list[str] | None,
        audios: list[str] | None,
        videos: list[str] | None,
        client_turn_id: str | None = None,
    ) -> None:
        """Create a run and emit the initial user-turn run_started event."""
        run_metadata = {
            "channel": channel,
            "external_chat_id": external_chat_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            CLIENT_TURN_ID_METADATA_KEY: client_turn_id,
        }
        run_metadata = {key: value for key, value in run_metadata.items() if value is not None}
        await self.create_run(session_id, run_id, status=RUN_RUNNING_STATUS, metadata=run_metadata)
        start_payload = {
            "status": RUN_RUNNING_STATUS,
            "text_len": len(text or ""),
            "images_count": len(images or []),
            "audios_count": len(audios or []),
            "videos_count": len(videos or []),
        }
        if client_turn_id:
            start_payload[CLIENT_TURN_ID_METADATA_KEY] = client_turn_id
        await self.emit_event(
            session_id,
            run_id,
            RUN_STARTED_EVENT,
            start_payload,
            channel=channel,
            external_chat_id=external_chat_id,
        )

    async def record_assistant_message_part(
        self,
        session_id: str,
        run_id: str,
        response: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist the assistant-visible response as an ordered run part."""
        await self.add_part(
            session_id,
            run_id,
            "assistant_message",
            content=response,
            metadata=metadata,
        )

    async def record_context_compaction_parts(
        self,
        session_id: str,
        run_id: str,
        compaction_events: list[Any],
    ) -> None:
        """Persist context compaction telemetry events as ordered run parts."""
        for compaction_event in compaction_events:
            compaction_metadata = vars(compaction_event)
            await self.add_part(
                session_id,
                run_id,
                "context_compaction",
                content=(
                    f"{compaction_event.trigger}:"
                    f"{compaction_event.strategy}:"
                    f"{compaction_event.outcome}"
                ),
                metadata=compaction_metadata,
            )

    async def record_llm_step_parts(
        self,
        session_id: str,
        run_id: str,
        step_events: list[Any],
    ) -> None:
        """Persist LLM request attempts as ordered run artifacts."""
        for step_event in step_events:
            metadata = vars(step_event)
            content = (
                f"iteration={step_event.iteration} attempt={step_event.attempt} "
                f"status={step_event.status} provider={step_event.provider or 'unknown'} "
                f"model={step_event.model or 'unknown'}"
            )
            await self.add_part(
                session_id,
                run_id,
                "llm_step",
                content=content,
                metadata=metadata,
            )

    async def record_operation_audit_part(
        self,
        session_id: str,
        run_id: str,
        audit: dict[str, Any],
    ) -> None:
        """Persist an operation audit snapshot for rollback and review."""
        content = " · ".join(
            item
            for item in (
                f"operation={audit.get(TRACE_OPERATION_TYPE_FIELD)}",
                f"target={audit.get(TRACE_TARGET_FIELD)}",
                f"rollback={bool(audit.get(TRACE_ROLLBACK_AVAILABLE_FIELD))}",
            )
            if item
        )
        await self.add_part(
            session_id,
            run_id,
            "operation_audit",
            content=content,
            metadata=audit,
        )

    async def _emit_terminal_event_after_commit(
        self,
        session_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        channel: str | None,
        external_chat_id: str | None,
    ) -> None:
        """Finish terminal event delivery even if the caller is cancelled late."""
        emit_task = asyncio.create_task(
            asyncio.wait_for(
                self.emit_event(
                    session_id,
                    run_id,
                    event_type,
                    payload,
                    channel=channel,
                    external_chat_id=external_chat_id,
                ),
                timeout=TERMINAL_EVENT_DELIVERY_TIMEOUT_SECONDS,
            )
        )
        cancellation_seen = False
        while not emit_task.done():
            try:
                await asyncio.shield(emit_task)
            except asyncio.CancelledError:
                cancellation_seen = True
            except Exception:
                break
        try:
            emit_task.result()
        except asyncio.CancelledError:
            logger.warning(
                "[{}] run.terminal_event.cancelled | run_id={} type={}",
                session_id,
                run_id,
                event_type,
            )
        except Exception as exc:
            logger.warning(
                "[{}] run.terminal_event.delivery_failed | run_id={} type={} error={}",
                session_id,
                run_id,
                event_type,
                exc,
            )
        if cancellation_seen:
            logger.info(
                "[{}] run.cancellation_ignored_after_terminal_commit | run_id={}",
                session_id,
                run_id,
            )

    async def _commit_terminal_status_after_cancellation(
        self,
        session_id: str,
        run_id: str,
        status: str,
        *,
        finished_at: float,
    ) -> None:
        """Finish a failure/cancellation commit even if cleanup is cancelled again."""
        commit_task = asyncio.create_task(
            self.update_run_status(
                session_id,
                run_id,
                status,
                finished_at=finished_at,
            )
        )
        cancellation_seen = False
        while not commit_task.done():
            try:
                await asyncio.shield(commit_task)
            except asyncio.CancelledError:
                cancellation_seen = True
        commit_task.result()
        if cancellation_seen:
            logger.info(
                "[{}] run.cancellation_ignored_during_terminal_commit | run_id={} status={}",
                session_id,
                run_id,
                status,
            )

    async def finish_run(
        self,
        session_id: str,
        run_id: str,
        *,
        status: str,
        event_payload: dict[str, Any],
        status_metadata: dict[str, Any] | None = None,
        channel: str | None = None,
        external_chat_id: str | None = None,
    ) -> None:
        """Persist a non-error terminal status and then publish run_finished."""
        finished_at = time.time()
        await self.update_run_status(
            session_id,
            run_id,
            status,
            metadata=status_metadata,
            finished_at=finished_at,
        )
        await self._emit_terminal_event_after_commit(
            session_id,
            run_id,
            RUN_FINISHED_EVENT,
            {**event_payload, "status": status},
            channel=channel,
            external_chat_id=external_chat_id,
        )

    async def complete_run(
        self,
        session_id: str,
        run_id: str,
        *,
        event_payload: dict[str, Any],
        status_metadata: dict[str, Any] | None = None,
        channel: str | None = None,
        external_chat_id: str | None = None,
    ) -> None:
        """Persist and publish a successfully completed run."""
        await self.finish_run(
            session_id,
            run_id,
            status=RUN_COMPLETED_STATUS,
            event_payload=event_payload,
            status_metadata=status_metadata,
            channel=channel,
            external_chat_id=external_chat_id,
        )

    async def fail_run(
        self,
        session_id: str,
        run_id: str,
        *,
        status: str,
        event_payload: dict[str, Any],
        channel: str | None = None,
        external_chat_id: str | None = None,
    ) -> None:
        """Persist an error/cancel terminal status and then publish its event."""
        finished_at = time.time()
        event_type = RUN_CANCELLED_EVENT if status == RUN_CANCELLED_STATUS else RUN_FAILED_EVENT
        await self._commit_terminal_status_after_cancellation(
            session_id,
            run_id,
            status,
            finished_at=finished_at,
        )
        await self._emit_terminal_event_after_commit(
            session_id,
            run_id,
            event_type,
            {**event_payload, "status": status},
            channel=channel,
            external_chat_id=external_chat_id,
        )
