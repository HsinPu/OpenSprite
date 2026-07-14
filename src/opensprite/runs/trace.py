"""Run trace persistence and event publishing helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import time
from collections.abc import Iterable
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable

from ..bus.events import OutboundMessage, RunEvent
from ..bus.message import CLIENT_TURN_ID_METADATA_KEY
from ..config import Config, ToolsConfig
from ..runs.events import (
    FILE_CHANGED_EVENT,
    FILE_REVERT_APPLIED_EVENT,
    FILE_REVERT_FAILED_EVENT,
    FILE_REVERT_PREVIEWED_EVENT,
    FILE_REVERT_SKIPPED_EVENT,
    LLM_STATUS_EVENT,
    MCP_CONNECTED_EVENT,
    MCP_CONNECTION_FAILED_EVENT,
    REASONING_DELTA_EVENT,
    RUN_PART_DELTA_EVENT,
    TOOL_INPUT_DELTA_EVENT,
    TOOL_RESULT_EVENT,
    TOOL_STARTED_EVENT,
    VERIFICATION_NAME_METADATA_FIELD,
    VERIFICATION_RESULT_EVENT,
    VERIFICATION_STATUS_METADATA_FIELD,
    VERIFICATION_STARTED_EVENT,
)
from ..runs.lifecycle import (
    RUN_CANCELLED_EVENT,
    RUN_CANCELLED_STATUS,
    RUN_COMPLETED_STATUS,
    RUN_FAILED_EVENT,
    RUN_FINISHED_EVENT,
    RUN_RUNNING_STATUS,
    RUN_STARTED_EVENT,
)
from ..storage import StorageProvider, StoredRunFileChange
from ..tool_names import (
    DELEGATE_MANY_TOOL_NAME,
    DELEGATE_TOOL_NAME,
    READ_SKILL_TOOL_NAME,
    RUN_WORKFLOW_TOOL_NAME,
)
from ..tools import ToolRegistry
from ..tool_names import is_verification_tool_name
from ..tools.result_status import classify_tool_result_status, tool_error_result
from ..tools.verify import classify_verification_result
from ..utils.json_safe import json_safe_payload
from ..utils.log import logger
from ..utils.text_changes import format_unified_diff, text_sha256


RUN_PART_CONTENT_MAX_CHARS = 20_000
TERMINAL_EVENT_DELIVERY_TIMEOUT_SECONDS = 5.0
RUN_FILE_REVERT_DIFF_MAX_CHARS = 12_000
TRACE_PROFILE_FIELD = "profile"
TRACE_POLICY_FIELD = "policy"
TRACE_STATUS_FIELD = "status"
TRACE_NAME_FIELD = "name"
TRACE_SUMMARY_FIELD = "summary"
TRACE_KIND_FIELD = "kind"
TRACE_OK_FIELD = "ok"
TRACE_PASSED_CASES_FIELD = "passed_cases"
TRACE_TOTAL_CASES_FIELD = "total_cases"
TRACE_PASSED_CHECKS_FIELD = "passed_checks"
TRACE_TOTAL_CHECKS_FIELD = "total_checks"
TRACE_OPERATION_TYPE_FIELD = "operation_type"
TRACE_TARGET_FIELD = "target"
TRACE_ROLLBACK_AVAILABLE_FIELD = "rollback_available"
WorkspaceForSession = Callable[[str], Path]
EventEmitter = Callable[..., Awaitable[None]]
PreviewFormatter = Callable[[str | list[dict[str, Any]] | None, int], str]
FileChangeRecorder = Callable[[str], None]
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
        add_event = getattr(self.storage, "add_run_event", None)
        stored_event = None
        if callable(add_event):
            try:
                stored_event = await add_event(
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


@dataclass(frozen=True)
class PreparedRunFileChangeRevert:
    """Prepared state for safely previewing or applying one file-change revert."""

    preview: dict[str, Any]
    change: StoredRunFileChange | None = None
    file_path: Path | None = None
    target_content: str | None = None


class RunFileChangeService:
    """Records file mutations and evaluates guarded single-file revert operations."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        workspace_for_session: WorkspaceForSession,
        emit_run_event: EventEmitter,
        format_log_preview: PreviewFormatter,
        note_file_change: FileChangeRecorder | None = None,
    ):
        self.storage = storage
        self._workspace_for_session = workspace_for_session
        self._emit_run_event = emit_run_event
        self._format_log_preview = format_log_preview
        self._note_file_change = note_file_change

    async def record_changes(
        self,
        tool_name: str,
        changes: list[dict[str, Any]],
        *,
        session_id: str | None,
        run_id: str | None,
        channel: str | None = None,
        external_chat_id: str | None = None,
    ) -> None:
        """Persist file mutations for the active run when available."""
        if not session_id or not run_id or not changes:
            return

        add_change = getattr(self.storage, "add_run_file_change", None)
        if not callable(add_change):
            return

        for raw_change in changes:
            path = str(raw_change.get("path") or "").strip()
            action = str(raw_change.get("action") or "").strip()
            if not path or not action:
                continue

            diff = str(raw_change.get("diff") or "")
            raw_metadata = raw_change.get("metadata")
            metadata = json_safe_payload(raw_metadata if isinstance(raw_metadata, dict) else {})
            metadata.setdefault("diff_len", len(diff))
            try:
                stored_change = await add_change(
                    session_id,
                    run_id,
                    tool_name,
                    path,
                    action,
                    before_sha256=raw_change.get("before_sha256"),
                    after_sha256=raw_change.get("after_sha256"),
                    before_content=raw_change.get("before_content"),
                    after_content=raw_change.get("after_content"),
                    diff=diff,
                    metadata=metadata,
                )
            except Exception as e:
                logger.warning(
                    "[{}] run.file-change.persist.failed | run_id={} tool={} path={} error={}",
                    session_id,
                    run_id,
                    tool_name,
                    path,
                    e,
                )
                continue

            event_payload = {
                "tool_name": tool_name,
                "path": path,
                "action": action,
                "before_sha256": raw_change.get("before_sha256"),
                "after_sha256": raw_change.get("after_sha256"),
                "diff_len": len(diff),
                "diff_preview": self._format_log_preview(diff, 240),
            }
            change_id = getattr(stored_change, "change_id", None)
            if change_id is not None:
                event_payload["change_id"] = change_id
            await self._emit_run_event(
                session_id,
                run_id,
                FILE_CHANGED_EVENT,
                event_payload,
                channel=channel,
                external_chat_id=external_chat_id,
            )
            if self._note_file_change is not None:
                try:
                    self._note_file_change(path)
                except Exception:
                    logger.exception("[{}] run.file-change.progress-hook.failed | run_id={} path={}", session_id, run_id, path)

    def _resolve_change_path(self, session_id: str, path: str) -> tuple[Path | None, str | None]:
        """Resolve a stored run file-change path and keep it inside the session workspace."""
        raw_path = str(path or "").strip()
        if not raw_path:
            return None, "stored file-change path is empty"

        workspace = self._workspace_for_session(session_id).resolve(strict=False)
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = workspace / candidate
        candidate = candidate.resolve(strict=False)
        try:
            candidate.relative_to(workspace)
        except ValueError:
            return None, f"stored file-change path escapes workspace: {raw_path}"
        return candidate, None

    @staticmethod
    def _read_current_content(file_path: Path) -> tuple[str | None, str | None, str | None]:
        """Read current text content for revert checks; return content, sha, error."""
        if not file_path.exists():
            return None, None, None
        if not file_path.is_file():
            return None, None, "path exists but is not a file"
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None, None, "current file is not valid UTF-8 text"
        except OSError as e:
            return None, None, f"failed to read current file: {e}"
        return content, text_sha256(content), None

    async def prepare_revert(
        self,
        session_id: str,
        run_id: str,
        change_id: int,
    ) -> PreparedRunFileChangeRevert:
        """Build a dry-run preview and required state for one guarded revert."""
        getter = getattr(self.storage, "get_run_file_change", None)
        if not callable(getter):
            return PreparedRunFileChangeRevert(
                preview={
                    "status": "unavailable",
                    "ok": False,
                    "session_id": session_id,
                    "run_id": run_id,
                    "change_id": change_id,
                    "reason": "storage does not support run file-change lookup",
                }
            )

        try:
            normalized_change_id = int(change_id)
        except (TypeError, ValueError):
            return PreparedRunFileChangeRevert(
                preview={
                    "status": "not_found",
                    "ok": False,
                    "session_id": session_id,
                    "run_id": run_id,
                    "change_id": change_id,
                    "reason": "change_id must be an integer",
                }
            )

        change = await getter(session_id, run_id, normalized_change_id)
        if change is None:
            return PreparedRunFileChangeRevert(
                preview={
                    "status": "not_found",
                    "ok": False,
                    "session_id": session_id,
                    "run_id": run_id,
                    "change_id": normalized_change_id,
                    "reason": "file change was not found for this run",
                }
            )

        file_path, path_error = self._resolve_change_path(session_id, change.path)
        base_preview = self._base_revert_preview(session_id, run_id, normalized_change_id, change)
        if path_error or file_path is None:
            return PreparedRunFileChangeRevert(
                preview={
                    **base_preview,
                    "status": "invalid_path",
                    "ok": False,
                    "reason": path_error or "invalid stored file-change path",
                },
                change=change,
                file_path=file_path,
            )

        current_content, current_sha, current_error = self._read_current_content(file_path)
        target_content = change.before_content
        preview = {
            **base_preview,
            "absolute_path": str(file_path),
            "current_exists": current_content is not None,
            "current_sha256": current_sha,
        }

        failure = self._validate_revert_preconditions(change, current_content, current_sha, current_error, target_content)
        if failure is not None:
            if failure.get("include_diff"):
                failure["diff"] = format_unified_diff(
                    change.path,
                    current_content,
                    target_content,
                    max_chars=RUN_FILE_REVERT_DIFF_MAX_CHARS,
                )
                failure.pop("include_diff", None)
            return PreparedRunFileChangeRevert(
                preview={**preview, **failure},
                change=change,
                file_path=file_path,
                target_content=target_content,
            )

        return PreparedRunFileChangeRevert(
            preview={
                **preview,
                "status": "ready",
                "ok": True,
                "reason": "ready to revert",
                "diff": format_unified_diff(
                    change.path,
                    current_content,
                    target_content,
                    max_chars=RUN_FILE_REVERT_DIFF_MAX_CHARS,
                ),
            },
            change=change,
            file_path=file_path,
            target_content=target_content,
        )

    @staticmethod
    def _base_revert_preview(
        session_id: str,
        run_id: str,
        change_id: int,
        change: StoredRunFileChange,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "run_id": run_id,
            "change_id": change_id,
            "path": change.path,
            "tool_name": change.tool_name,
            "original_action": change.action,
            "before_sha256": change.before_sha256,
            "after_sha256": change.after_sha256,
            "expected_current_sha256": change.after_sha256,
            "target_sha256": change.before_sha256,
            "current_exists": False,
            "target_exists": change.before_sha256 is not None,
            "current_sha256": None,
            "revert_action": "delete" if change.before_sha256 is None else "write",
            "diff": "",
        }

    @staticmethod
    def _validate_revert_preconditions(
        change: StoredRunFileChange,
        current_content: str | None,
        current_sha: str | None,
        current_error: str | None,
        target_content: str | None,
    ) -> dict[str, Any] | None:
        if current_error:
            return {"status": "conflict", "ok": False, "reason": current_error}

        if change.before_sha256 is not None:
            if target_content is None:
                return {
                    "status": "unavailable",
                    "ok": False,
                    "reason": "stored before_content snapshot is unavailable; cannot safely reconstruct the file",
                }
            target_sha = text_sha256(target_content)
            if target_sha != change.before_sha256:
                return {
                    "status": "unavailable",
                    "ok": False,
                    "reason": "stored before_content snapshot hash does not match before_sha256",
                }

        if change.after_sha256 is None:
            if current_content is not None:
                return {
                    "status": "conflict",
                    "ok": False,
                    "reason": "current file exists but the recorded post-change state expected it to be missing",
                    "include_diff": True,
                }
        elif current_content is None:
            return {
                "status": "conflict",
                "ok": False,
                "reason": "current file is missing but the recorded post-change state expected file content",
            }
        elif current_sha != change.after_sha256:
            return {
                "status": "conflict",
                "ok": False,
                "reason": "current file hash does not match the recorded post-change hash",
                "include_diff": True,
            }

        return None

    async def preview_revert(self, session_id: str, run_id: str, change_id: int) -> dict[str, Any]:
        """Inspect whether one captured file change can be safely reverted."""
        prepared = await self.prepare_revert(session_id, run_id, change_id)
        await self._emit_revert_event(session_id, run_id, FILE_REVERT_PREVIEWED_EVENT, prepared.preview)
        return prepared.preview

    async def _emit_revert_event(
        self,
        session_id: str,
        run_id: str,
        event_type: str,
        result: dict[str, Any],
    ) -> None:
        payload = {
            "change_id": result.get("change_id"),
            "path": result.get("path"),
            "status": result.get("status"),
            "ok": bool(result.get("ok")),
            "applied": bool(result.get("applied", False)),
            "dry_run": bool(result.get("dry_run", False)),
            "reason": result.get("reason"),
            "revert_action": result.get("revert_action"),
            "post_sha256": result.get("post_sha256"),
        }
        await self._emit_run_event(session_id, run_id, event_type, payload)

    async def revert(
        self,
        session_id: str,
        run_id: str,
        change_id: int,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Safely revert one captured file change; defaults to dry-run inspection."""
        prepared = await self.prepare_revert(session_id, run_id, change_id)
        result = {**prepared.preview, "dry_run": bool(dry_run), "applied": False}
        if dry_run or prepared.preview.get("status") != "ready" or prepared.file_path is None:
            await self._emit_revert_event(session_id, run_id, FILE_REVERT_SKIPPED_EVENT, result)
            return result

        current_content, current_sha, current_error = self._read_current_content(prepared.file_path)
        if current_error:
            result.update({"status": "conflict", "ok": False, "reason": current_error})
            await self._emit_revert_event(session_id, run_id, FILE_REVERT_SKIPPED_EVENT, result)
            return result

        expected_current_sha = prepared.preview.get("expected_current_sha256")
        if expected_current_sha is None:
            if current_content is not None:
                result.update({"status": "conflict", "ok": False, "reason": "current file changed before revert apply"})
                await self._emit_revert_event(session_id, run_id, FILE_REVERT_SKIPPED_EVENT, result)
                return result
        elif current_sha != expected_current_sha:
            result.update(
                {
                    "status": "conflict",
                    "ok": False,
                    "reason": "current file changed before revert apply",
                    "current_sha256": current_sha,
                }
            )
            await self._emit_revert_event(session_id, run_id, FILE_REVERT_SKIPPED_EVENT, result)
            return result

        try:
            if prepared.target_content is None:
                if prepared.file_path.exists():
                    prepared.file_path.unlink()
                post_sha = None
            else:
                prepared.file_path.parent.mkdir(parents=True, exist_ok=True)
                prepared.file_path.write_text(prepared.target_content, encoding="utf-8")
                post_sha = text_sha256(prepared.target_content)
        except OSError as e:
            result.update({"status": "failed", "ok": False, "reason": f"failed to apply revert: {e}"})
            await self._emit_revert_event(session_id, run_id, FILE_REVERT_FAILED_EVENT, result)
            return result

        result.update(
            {
                "status": "applied",
                "ok": True,
                "applied": True,
                "post_sha256": post_sha,
                "reason": "file change reverted",
            }
        )
        await self._emit_revert_event(session_id, run_id, FILE_REVERT_APPLIED_EVENT, result)
        return result


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
        create_supported = self._overrides_optional_storage_method("create_run")
        update_supported = self._overrides_optional_storage_method("update_run_status")
        self._run_persistence_supported = create_supported and update_supported
        self._run_persistence_contract_error = create_supported != update_supported

    def _overrides_optional_storage_method(self, method_name: str) -> bool:
        method = getattr(self.storage, method_name, None)
        implementation = getattr(method, "__func__", method)
        return callable(method) and implementation is not getattr(StorageProvider, method_name, None)

    def _require_consistent_run_persistence_contract(self) -> None:
        if self._run_persistence_contract_error:
            raise RuntimeError(
                "Run storage must implement create_run and update_run_status together, or inherit both optional defaults."
            )

    async def create_run(
        self,
        session_id: str,
        run_id: str,
        *,
        status: str = "running",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a durable run record when the configured storage supports it."""
        self._require_consistent_run_persistence_contract()
        if not self._run_persistence_supported:
            return
        creator = getattr(self.storage, "create_run", None)
        if not callable(creator):
            return
        created = await creator(session_id, run_id, status=status, metadata=metadata)
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
        """Update a durable run record when the configured storage supports it.

        Terminal status is the source of truth for CLI, Web, and smoke clients,
        so persistence failures must propagate instead of creating a false
        successful terminal event while the durable row remains ``running``.
        """
        self._require_consistent_run_persistence_contract()
        if not self._run_persistence_supported:
            return
        updater = getattr(self.storage, "update_run_status", None)
        if not callable(updater):
            return
        updated = await updater(session_id, run_id, status, metadata=metadata, finished_at=finished_at)
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
        """Persist one ordered run artifact when the storage supports it."""
        add_part = getattr(self.storage, "add_run_part", None)
        if not callable(add_part):
            return
        try:
            stored_content, content_metadata = truncate_run_part_content(str(content or ""))
            safe_metadata = json_safe_payload(metadata)
            safe_metadata.update(content_metadata)
            await add_part(
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


MCP_TOOL_NAME_PREFIX = "mcp_"
PROGRESS_NOTICE_TOOL_NAMES = frozenset(
    {
        READ_SKILL_TOOL_NAME,
        DELEGATE_TOOL_NAME,
        DELEGATE_MANY_TOOL_NAME,
        RUN_WORKFLOW_TOOL_NAME,
    }
)


def is_mcp_tool_name(tool_name: str | None) -> bool:
    return str(tool_name or "").startswith(MCP_TOOL_NAME_PREFIX)


def mcp_tool_display_name(tool_name: str | None) -> str:
    text = str(tool_name or "")
    return text[len(MCP_TOOL_NAME_PREFIX) :] if is_mcp_tool_name(text) else text


def mcp_tool_names(tool_names: Iterable[str]) -> list[str]:
    return sorted(name for name in tool_names if is_mcp_tool_name(name))


def tool_warrants_progress_notice(tool_name: str | None) -> bool:
    return str(tool_name or "").strip() in PROGRESS_NOTICE_TOOL_NAMES or is_mcp_tool_name(tool_name)


def _mcp_lifecycle_error_result(message: str, *, category: str) -> str:
    return tool_error_result(
        str(message or "").strip(),
        error_type="ConfigureMCPToolError",
        category=category,
        metadata={"tool_name": "configure_mcp"},
    )


class McpLifecycleService:
    """Owns MCP connection state, reconnect backoff, and runtime tool summaries."""

    INITIAL_RETRY_BACKOFF_SECONDS = 15.0
    MAX_RETRY_BACKOFF_SECONDS = 300.0

    def __init__(
        self,
        *,
        tools: ToolRegistry,
        tools_config: ToolsConfig,
        context_builder: Any,
        config_path_getter: Callable[[], Path | None],
        current_session_id_getter: Callable[[], str | None],
        current_run_id_getter: Callable[[], str | None],
        current_channel_getter: Callable[[], str | None],
        current_external_chat_id_getter: Callable[[], str | None],
        emit_run_event: Callable[..., Awaitable[None]],
    ):
        self.tools = tools
        self.tools_config = tools_config
        self.context_builder = context_builder
        self._config_path_getter = config_path_getter
        self._current_session_id_getter = current_session_id_getter
        self._current_run_id_getter = current_run_id_getter
        self._current_channel_getter = current_channel_getter
        self._current_external_chat_id_getter = current_external_chat_id_getter
        self._emit_run_event = emit_run_event
        self.servers = dict(tools_config.mcp_servers)
        self.tool_names: set[str] = set()
        self.connected_server_names: set[str] = set()
        self.failed_server_names: set[str] = set()
        self.stack: AsyncExitStack | None = None
        self.connected = False
        self.connecting = False
        self.connect_failures = 0
        self.retry_after = 0.0
        self._connect_lock = asyncio.Lock()

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        session_id = self._current_session_id_getter()
        run_id = self._current_run_id_getter()
        if session_id is None or run_id is None:
            return
        await self._emit_run_event(
            session_id,
            run_id,
            event_type,
            payload,
            channel=self._current_channel_getter(),
            external_chat_id=self._current_external_chat_id_getter(),
        )

    def sync_runtime_tools_context(self) -> None:
        """Expose connected MCP tools to context builders that support prompt summaries."""
        if not hasattr(self.context_builder, "set_runtime_mcp_tools"):
            return

        mcp_tools = sorted(
            [
                (tool.name, tool.description)
                for tool_name in self.tools.tool_names
                for tool in [self.tools.get(tool_name)]
                if tool is not None and is_mcp_tool_name(tool.name)
            ],
            key=lambda item: item[0],
        )
        self.context_builder.set_runtime_mcp_tools(mcp_tools)

    async def _record_connection_failure(
        self,
        *,
        attempted_server_names: set[str],
        failure_messages: dict[str, str],
    ) -> None:
        self.connect_failures += 1
        retry_delay = min(
            self.INITIAL_RETRY_BACKOFF_SECONDS * (2 ** (self.connect_failures - 1)),
            self.MAX_RETRY_BACKOFF_SECONDS,
        )
        self.retry_after = time.monotonic() + retry_delay
        error = "; ".join(
            f"{name}: {failure_messages.get(name, 'unknown connection failure')}"
            for name in sorted(attempted_server_names)
        )
        logger.error(
            "agent.mcp.connect.error | error={} retry_in_s={} failures={}",
            error,
            retry_delay,
            self.connect_failures,
        )
        await self._emit_event(
            MCP_CONNECTION_FAILED_EVENT,
            {
                "server_count": len(self.servers),
                "attempted_server_count": len(attempted_server_names),
                "connected_server_count": len(self.connected_server_names),
                "failed_server_names": sorted(attempted_server_names),
                "error": error,
                "connect_failures": self.connect_failures,
                "retry_in_seconds": retry_delay,
            },
        )

    async def connect(self) -> None:
        """Connect pending MCP servers, sharing one in-flight attempt between callers."""
        if not self.servers:
            return

        async with self._connect_lock:
            configured_server_names = set(self.servers)
            self.connected_server_names.intersection_update(configured_server_names)
            pending_server_names = configured_server_names - self.connected_server_names
            now = time.monotonic()
            if not pending_server_names:
                self.connected = bool(configured_server_names)
                self.failed_server_names.clear()
                return
            if now < self.retry_after:
                return

            self.connecting = True
            attempt_stack: AsyncExitStack | None = None
            preexisting_registry_tool_names = set(self.tools.tool_names)
            previous_tool_names = set(self.tool_names)
            previous_connected_server_names = set(self.connected_server_names)
            previous_failed_server_names = set(self.failed_server_names)
            previous_connect_failures = self.connect_failures
            previous_retry_after = self.retry_after
            try:
                from ..tools.mcp import connect_mcp_servers

                attempt_stack = AsyncExitStack()
                await attempt_stack.__aenter__()
                summary = await connect_mcp_servers(
                    {name: self.servers[name] for name in sorted(pending_server_names)},
                    self.tools,
                    attempt_stack,
                )
                connected_this_attempt = set(summary.connected_server_names) & pending_server_names
                reported_failures = set(summary.failed_server_names) & pending_server_names
                failed_this_attempt = pending_server_names - connected_this_attempt
                failure_messages = dict(summary.failure_messages)
                for name in failed_this_attempt - reported_failures:
                    failure_messages[name] = "no connection result returned"

                new_tool_names = {
                    name for name in self.tools.tool_names
                    if is_mcp_tool_name(name) and name not in preexisting_registry_tool_names
                }

                if not connected_this_attempt:
                    for name in new_tool_names:
                        self.tools.unregister(name)
                    await attempt_stack.aclose()
                    attempt_stack = None
                    self.failed_server_names = configured_server_names - self.connected_server_names
                    await self._record_connection_failure(
                        attempted_server_names=failed_this_attempt,
                        failure_messages=failure_messages,
                    )
                    return

                self.connected_server_names.update(connected_this_attempt)
                self.failed_server_names = configured_server_names - self.connected_server_names
                self.connected = True
                self.tool_names.update(new_tool_names)
                self.sync_runtime_tools_context()
                await self._emit_event(
                    MCP_CONNECTED_EVENT,
                    {
                        "server_count": len(self.servers),
                        "connected_server_count": len(self.connected_server_names),
                        "connected_server_names": sorted(self.connected_server_names),
                        "failed_server_names": sorted(self.failed_server_names),
                        "tool_names": sorted(self.tool_names),
                        "registered_tool_count": len(self.tool_names),
                    },
                )
                if failed_this_attempt:
                    await self._record_connection_failure(
                        attempted_server_names=failed_this_attempt,
                        failure_messages=failure_messages,
                    )
                else:
                    self.connect_failures = 0
                    self.retry_after = 0.0

                if self.stack is None:
                    self.stack = attempt_stack
                else:
                    self.stack.push_async_callback(attempt_stack.aclose)
                attempt_stack = None
                logger.info("agent.{} | tools={}", MCP_CONNECTED_EVENT, ", ".join(self.tools.tool_names))
            except asyncio.CancelledError:
                for name in list(self.tools.tool_names):
                    if is_mcp_tool_name(name) and name not in preexisting_registry_tool_names:
                        self.tools.unregister(name)
                self.tool_names = previous_tool_names
                self.connected_server_names = previous_connected_server_names
                self.failed_server_names = previous_failed_server_names
                self.connected = bool(previous_connected_server_names)
                self.connect_failures = previous_connect_failures
                self.retry_after = previous_retry_after
                self.sync_runtime_tools_context()
                if attempt_stack is not None:
                    try:
                        await attempt_stack.aclose()
                    except asyncio.CancelledError:
                        raise
                    except Exception as cleanup_exc:
                        logger.warning("agent.mcp.cancel.cleanup.error | error={}", cleanup_exc)
                raise
            except Exception as exc:
                for name in list(self.tools.tool_names):
                    if is_mcp_tool_name(name) and name not in preexisting_registry_tool_names:
                        self.tools.unregister(name)
                if attempt_stack is not None:
                    try:
                        await attempt_stack.aclose()
                    except asyncio.CancelledError:
                        raise
                    except Exception as cleanup_exc:
                        logger.warning("agent.mcp.connect.cleanup.error | error={}", cleanup_exc)
                self.tool_names = previous_tool_names
                self.connected_server_names = previous_connected_server_names
                self.failed_server_names = configured_server_names - previous_connected_server_names
                self.connected = bool(previous_connected_server_names)
                self.connect_failures = previous_connect_failures
                self.retry_after = previous_retry_after
                self.sync_runtime_tools_context()
                await self._record_connection_failure(
                    attempted_server_names=pending_server_names,
                    failure_messages={name: f"{type(exc).__name__}: {exc}" for name in pending_server_names},
                )
            finally:
                self.connecting = False

    async def close(self) -> None:
        """Close any active MCP sessions and reset lifecycle flags."""
        async with self._connect_lock:
            stack = self.stack
            self.stack = None
            self.connected = False
            self.connecting = False
            self.connected_server_names.clear()
            self.failed_server_names.clear()
            self.connect_failures = 0
            self.retry_after = 0.0
            for tool_name in list(self.tool_names):
                self.tools.unregister(tool_name)
            self.tool_names.clear()
            self.sync_runtime_tools_context()

        if stack is None:
            return

        try:
            await stack.aclose()
        except Exception as exc:
            logger.warning("agent.mcp.close.error | error={}", exc)

    async def reload_from_config(self) -> str:
        """Reload MCP settings from disk and reconnect MCP tools."""
        config_path = self._config_path_getter()
        if config_path is None:
            return _mcp_lifecycle_error_result(
                "MCP config path is unavailable.",
                category="missing_config_path",
            )

        loaded = Config.load(config_path)
        self.tools_config.mcp_servers_file = loaded.tools.mcp_servers_file
        self.tools_config.mcp_servers = dict(loaded.tools.mcp_servers)
        self.servers = dict(loaded.tools.mcp_servers)
        self.connect_failures = 0
        self.retry_after = 0.0

        await self.close()
        if not self.servers:
            return "MCP configuration reloaded. No MCP servers are configured now."

        await self.connect()
        if not self.connected:
            return "MCP configuration reloaded, but no MCP servers connected successfully."

        if self.failed_server_names:
            failed_servers = ", ".join(sorted(self.failed_server_names))
            return f"MCP configuration reloaded partially. Retry scheduled for: {failed_servers}"

        connected_tools = ", ".join(sorted(self.tool_names)) or "(none)"
        return f"MCP configuration reloaded. Connected tools: {connected_tools}"


@dataclass
class ActiveRunState:
    """In-memory state for one currently active user-facing run."""

    session_id: str
    run_id: str
    started_at: float
    cancel_requested: bool = False
    cancel_requested_at: float | None = None


class RunBusyError(RuntimeError):
    """Raised when the same session already has an active run."""


class RunCancelledError(asyncio.CancelledError):
    """Raised when cooperative cancellation is requested for an active run."""


class AgentRunStateService:
    """Tracks one active run per session and handles cooperative cancel requests."""

    def __init__(self):
        self._active_by_session: dict[str, ActiveRunState] = {}

    def ensure_available(self, session_id: str) -> None:
        """Reject a new turn before it performs any input side effects."""
        existing = self._active_by_session.get(session_id)
        if existing is not None:
            raise RunBusyError(
                f"Session '{session_id}' is already processing run '{existing.run_id}'."
            )

    def start(self, session_id: str, run_id: str) -> ActiveRunState:
        existing = self._active_by_session.get(session_id)
        if existing is not None and existing.run_id != run_id:
            raise RunBusyError(
                f"Session '{session_id}' is already processing run '{existing.run_id}'."
            )
        active = ActiveRunState(session_id=session_id, run_id=run_id, started_at=time.time())
        self._active_by_session[session_id] = active
        return active

    def finish(self, session_id: str, run_id: str) -> None:
        existing = self._active_by_session.get(session_id)
        if existing is not None and existing.run_id == run_id:
            self._active_by_session.pop(session_id, None)

    def get_active(self, session_id: str) -> ActiveRunState | None:
        return self._active_by_session.get(session_id)

    def is_active(self, session_id: str, run_id: str) -> bool:
        active = self._active_by_session.get(session_id)
        return active is not None and active.run_id == run_id

    def request_cancel(self, session_id: str, run_id: str) -> ActiveRunState | None:
        active = self._active_by_session.get(session_id)
        if active is None or active.run_id != run_id:
            return None
        if not active.cancel_requested:
            active.cancel_requested = True
            active.cancel_requested_at = time.time()
        return active

    def is_cancel_requested(self, session_id: str, run_id: str) -> bool:
        active = self._active_by_session.get(session_id)
        return bool(active is not None and active.run_id == run_id and active.cancel_requested)


_TRACE_TEXT_FIELDS = {
    "type",
    "query",
    "url",
    "final_url",
    "provider",
    "backend",
    "search_provider",
    "search_backend",
    "configured_provider",
    "extractor",
    "error",
}

_TRACE_COUNT_FIELDS = {
    "source_count",
    "fetched_count",
    "search_result_count",
    "returned_items",
}


def _trace_text(value: Any, *, max_chars: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) > max_chars:
        return f"{text[: max_chars - 3]}..."
    return text


def _trace_count(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_object(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(str(value or "").lstrip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _trace_attempt_payload(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    attempts = payload.get(key)
    if not isinstance(attempts, list):
        return None
    candidates = [attempt for attempt in attempts if isinstance(attempt, dict)]
    if not candidates:
        return None
    for attempt in candidates:
        if attempt.get("ok") is True:
            return attempt
    return candidates[0]


def _tool_result_trace_metadata(result_text: str) -> dict[str, Any]:
    """Extract compact traceable fields from structured tool results."""
    payload = _json_object(result_text)
    if payload is None:
        return {}

    metadata: dict[str, Any] = {}
    for field in _TRACE_TEXT_FIELDS:
        value = _trace_text(payload.get(field))
        if value:
            metadata[field] = value
    for field in _TRACE_COUNT_FIELDS:
        count = _trace_count(payload.get(field))
        if count is not None:
            metadata[field] = count

    items = payload.get("items")
    if isinstance(items, list):
        metadata.setdefault("returned_items", len(items))

    sources = payload.get("sources")
    if isinstance(sources, list):
        metadata.setdefault("source_count", len(sources))
        for source in sources:
            if not isinstance(source, dict):
                continue
            provider = _trace_text(source.get("search_provider") or source.get("provider"))
            backend = _trace_text(source.get("search_backend") or source.get("backend"))
            if provider:
                metadata.setdefault("search_provider", provider)
                metadata.setdefault("provider", provider)
            if backend:
                metadata.setdefault("search_backend", backend)
                metadata.setdefault("backend", backend)
            if provider or backend:
                break

    for attempt_key in ("search_attempts", "query_attempts"):
        attempt = _trace_attempt_payload(payload, attempt_key)
        if not attempt:
            continue
        provider = _trace_text(attempt.get("provider") or attempt.get("configured_provider"))
        backend = _trace_text(attempt.get("backend"))
        if provider:
            metadata.setdefault("provider", provider)
        if backend:
            metadata.setdefault("backend", backend)

    if metadata.get("provider") and not metadata.get("search_provider"):
        metadata["search_provider"] = metadata["provider"]
    if metadata.get("backend") and not metadata.get("search_backend"):
        metadata["search_backend"] = metadata["backend"]
    return metadata


def _tool_error_trace_metadata(result_text: str) -> dict[str, Any]:
    """Extract structured error fields from failed plain-text tool results."""
    return classify_tool_result_status(result_text).error_metadata()


class RunHookService:
    """Builds callbacks passed into the LLM/tool execution engine."""

    def __init__(
        self,
        *,
        message_bus_getter: Callable[[], Any],
        add_run_part: Callable[..., Awaitable[None]],
        emit_run_event: Callable[..., Awaitable[None]],
        format_log_preview: Callable[..., str],
    ):
        self._message_bus_getter = message_bus_getter
        self._add_run_part = add_run_part
        self._emit_run_event = emit_run_event
        self._format_log_preview = format_log_preview
        self._tool_started_at: dict[tuple[str, str, str], float] = {}

    @staticmethod
    def _tool_lifecycle_key(
        session_id: str,
        run_id: str,
        tool_call_id: str | None,
        tool_name: str,
        iteration: int | None,
    ) -> tuple[str, str, str]:
        identifier = tool_call_id or f"{tool_name}:{iteration or 0}"
        return (session_id, run_id, identifier)

    @staticmethod
    def tool_warrants_progress_notice(tool_name: str) -> bool:
        """Whether to send a short interim message before this tool runs."""
        return tool_warrants_progress_notice(tool_name)

    @staticmethod
    def format_tool_progress_message(tool_name: str, tool_args: dict[str, Any]) -> str:
        """User-facing one-line status for skill, subagent, and MCP tool execution."""
        args = tool_args or {}
        if tool_name == READ_SKILL_TOOL_NAME:
            name = args.get("skill_name") or "?"
            return f"正在讀取技能〈{name}〉…"
        if tool_name == DELEGATE_TOOL_NAME:
            task_id = args.get("task_id")
            ptype = args.get("prompt_type") or "writer"
            if task_id:
                return f"正在續跑子代理任務（{task_id}）…"
            return f"正在委派子代理（{ptype}）…"
        if tool_name == DELEGATE_MANY_TOOL_NAME:
            tasks = args.get("tasks") if isinstance(args.get("tasks"), list) else []
            return f"正在平行委派 {max(1, len(tasks))} 個子代理任務…"
        if tool_name == RUN_WORKFLOW_TOOL_NAME:
            workflow = args.get("workflow") or args.get("workflow_id") or "workflow"
            start_step = args.get("start_step") or args.get("startStep")
            if start_step:
                return f"正在續跑固定工作流（{workflow}:{start_step}）…"
            return f"正在執行固定工作流（{workflow}）…"
        if is_mcp_tool_name(tool_name):
            tail = mcp_tool_display_name(tool_name)
            return f"正在呼叫 MCP：{tail}…"
        return "處理中…"

    def make_tool_progress_hook(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str,
        run_id: str | None,
        enabled: bool,
    ) -> Callable[[str, dict[str, Any]], Awaitable[None]] | None:
        """Publish run telemetry and a brief outbound status before selected tools run."""
        if not enabled or run_id is None:
            return None
        bus = self._message_bus_getter()
        ch = channel
        tid = str(external_chat_id) if external_chat_id is not None else None
        sid = session_id
        rid = run_id

        async def _hook(tool_name: str, tool_args: dict[str, Any], tool_call_id: str | None = None, iteration: int | None = None) -> None:
            safe_args = json_safe_payload(tool_args or {})
            args_preview = self._format_log_preview(json.dumps(safe_args, ensure_ascii=False), max_chars=240)
            started_at = time.time()
            self._tool_started_at[self._tool_lifecycle_key(sid, rid, tool_call_id, tool_name, iteration)] = started_at
            metadata = {
                "args": safe_args,
                "args_preview": args_preview,
                "state": "running",
                "started_at": started_at,
            }
            if tool_call_id:
                metadata["tool_call_id"] = tool_call_id
            if iteration is not None:
                metadata["iteration"] = int(iteration)
            await self._add_run_part(
                sid,
                rid,
                "tool_call",
                content=json.dumps(safe_args, ensure_ascii=False, sort_keys=True),
                tool_name=tool_name,
                metadata=metadata,
            )
            await self._emit_run_event(
                sid,
                rid,
                TOOL_STARTED_EVENT,
                {
                    "tool_name": tool_name,
                    "args_preview": args_preview,
                    "tool_call_id": tool_call_id,
                    "iteration": iteration,
                    "state": "running",
                    "started_at": started_at,
                },
                channel=ch,
                external_chat_id=tid,
            )
            if is_verification_tool_name(tool_name):
                await self._emit_run_event(
                    sid,
                    rid,
                    VERIFICATION_STARTED_EVENT,
                    {
                        "action": (tool_args or {}).get("action", "auto"),
                        "path": (tool_args or {}).get("path", "."),
                    },
                    channel=ch,
                    external_chat_id=tid,
                )
            if bus is None or not ch or tid is None or not self.tool_warrants_progress_notice(tool_name):
                return
            text = self.format_tool_progress_message(tool_name, tool_args)
            await bus.publish_outbound(
                OutboundMessage(
                    channel=ch,
                    external_chat_id=tid,
                    session_id=sid,
                    content=text,
                    metadata={"interim": True, "kind": "tool_progress", "tool_name": tool_name},
                )
            )

        return _hook

    def make_tool_result_hook(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str,
        run_id: str | None,
        enabled: bool,
    ) -> Callable[[str, dict[str, Any], str], Awaitable[None]] | None:
        """Publish structured run telemetry after a tool finishes."""
        if not enabled or run_id is None:
            return None
        tid = str(external_chat_id) if external_chat_id is not None else None
        rid = run_id

        async def _hook(
            tool_name: str,
            tool_args: dict[str, Any],
            result: str,
            tool_call_id: str | None = None,
            iteration: int | None = None,
            delegate_task_id: str | None = None,
            delegate_prompt_type: str | None = None,
            state: str | None = None,
            interrupted: bool = False,
        ) -> None:
            safe_args = json_safe_payload(tool_args or {})
            result_text = str(result or "")
            result_preview = self._format_log_preview(result_text, max_chars=240)
            state_text = str(state or "").strip().lower()
            result_status = classify_tool_result_status(result_text, state=state_text)
            ok = result_status.ok
            finished_at = time.time()
            started_at = self._tool_started_at.pop(
                self._tool_lifecycle_key(session_id, rid, tool_call_id, tool_name, iteration),
                None,
            )
            duration_ms = int(max(0.0, finished_at - started_at) * 1000) if started_at is not None else None
            metadata = {
                "args": safe_args,
                "ok": ok,
                "result_len": len(result_text),
                "result_preview": result_preview,
                "state": state or ("completed" if ok else "error"),
                "finished_at": finished_at,
            }
            trace_metadata = _tool_result_trace_metadata(result_text)
            metadata.update(trace_metadata)
            if not ok:
                metadata.update(result_status.error_metadata())
            if started_at is not None:
                metadata["started_at"] = started_at
                metadata["duration_ms"] = duration_ms
            if interrupted:
                metadata["interrupted"] = True
            if tool_call_id:
                metadata["tool_call_id"] = tool_call_id
            if iteration is not None:
                metadata["iteration"] = int(iteration)
            if delegate_task_id:
                metadata["delegate_task_id"] = delegate_task_id
            if delegate_prompt_type:
                metadata["delegate_prompt_type"] = delegate_prompt_type
            await self._add_run_part(
                session_id,
                rid,
                "tool_result",
                content=result_text,
                tool_name=tool_name,
                metadata=metadata,
            )
            await self._emit_run_event(
                session_id,
                rid,
                TOOL_RESULT_EVENT,
                {
                    "tool_name": tool_name,
                    "ok": ok,
                    "result_len": len(result_text),
                    "result_preview": result_preview,
                    **trace_metadata,
                    **({} if ok else _tool_error_trace_metadata(result_text)),
                    "tool_call_id": tool_call_id,
                    "iteration": iteration,
                    "delegate_task_id": delegate_task_id,
                    "delegate_prompt_type": delegate_prompt_type,
                    "state": metadata["state"],
                    "interrupted": interrupted,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_ms": duration_ms,
                },
                channel=channel,
                external_chat_id=tid,
            )
            if is_verification_tool_name(tool_name):
                verification = classify_verification_result(result_text)
                await self._emit_run_event(
                    session_id,
                    rid,
                    VERIFICATION_RESULT_EVENT,
                    {
                        "action": (tool_args or {}).get("action", "auto"),
                        "path": (tool_args or {}).get("path", "."),
                        "ok": ok,
                        VERIFICATION_STATUS_METADATA_FIELD: verification["status"],
                        VERIFICATION_NAME_METADATA_FIELD: verification["name"],
                        "result_preview": result_preview,
                    },
                    channel=channel,
                    external_chat_id=tid,
                )

        return _hook

    def make_llm_status_hook(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str,
        run_id: str | None,
        enabled: bool,
    ) -> Callable[[Any], Awaitable[None]] | None:
        """Publish run telemetry and interim outbound status during long LLM waits."""
        if not enabled or run_id is None:
            return None
        bus = self._message_bus_getter()
        ch = channel
        tid = str(external_chat_id) if external_chat_id is not None else None
        sid = session_id
        rid = run_id

        async def _hook(update: Any) -> None:
            if isinstance(update, dict):
                text = str(update.get("message") or "").strip()
                payload = {
                    key: value
                    for key, value in update.items()
                    if key != "message" and value not in (None, "")
                }
                payload["message"] = text
            else:
                text = str(update or "")
                payload = {"message": text}
            await self._emit_run_event(
                sid,
                rid,
                LLM_STATUS_EVENT,
                payload,
                channel=ch,
                external_chat_id=tid,
            )
            if bus is None or not ch or tid is None:
                return
            await bus.publish_outbound(
                OutboundMessage(
                    channel=ch,
                    external_chat_id=tid,
                    session_id=sid,
                    content=text,
                    metadata={"interim": True, "kind": "llm_wait"},
                )
            )

        return _hook

    def make_llm_delta_hook(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str,
        run_id: str | None,
        enabled: bool,
    ) -> Callable[[str, str, str, int], Awaitable[None]] | None:
        """Publish visible assistant response chunks into the run event stream."""
        if not enabled or run_id is None:
            return None
        ch = channel
        tid = str(external_chat_id) if external_chat_id is not None else None
        sid = session_id
        rid = run_id

        async def _hook(part_id: str, delta: str, state: str = "running", sequence: int = 0) -> None:
            text = str(delta or "")
            normalized_state = str(state or "running")
            if not text and normalized_state == "running":
                return
            await self._emit_run_event(
                sid,
                rid,
                RUN_PART_DELTA_EVENT,
                {
                    "part_id": part_id,
                    "part_type": "assistant_message",
                    "content_delta": text,
                    "state": normalized_state,
                    "sequence": int(sequence),
                },
                channel=ch,
                external_chat_id=tid,
            )

        return _hook

    def make_tool_input_delta_hook(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str,
        run_id: str | None,
        enabled: bool,
    ) -> Callable[[str, str, str, int], Awaitable[None]] | None:
        """Publish streamed tool-call argument chunks into the run event stream."""
        if not enabled or run_id is None:
            return None
        ch = channel
        tid = str(external_chat_id) if external_chat_id is not None else None
        sid = session_id
        rid = run_id

        async def _hook(tool_call_id: str, tool_name: str, delta: str, sequence: int = 0) -> None:
            text = str(delta or "")
            if not text:
                return
            await self._emit_run_event(
                sid,
                rid,
                TOOL_INPUT_DELTA_EVENT,
                {
                    "tool_call_id": str(tool_call_id or ""),
                    "tool_name": str(tool_name or ""),
                    "input_delta": text,
                    "sequence": int(sequence),
                },
                channel=ch,
                external_chat_id=tid,
            )

        return _hook

    def make_reasoning_delta_hook(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str,
        run_id: str | None,
        enabled: bool,
    ) -> Callable[[str, int], Awaitable[None]] | None:
        """Publish provider reasoning chunks into inspector-only run events."""
        if not enabled or run_id is None:
            return None
        ch = channel
        tid = str(external_chat_id) if external_chat_id is not None else None
        sid = session_id
        rid = run_id

        async def _hook(delta: str, sequence: int = 0) -> None:
            text = str(delta or "")
            if not text:
                return
            await self._emit_run_event(
                sid,
                rid,
                REASONING_DELTA_EVENT,
                {
                    "content_delta": text,
                    "sequence": int(sequence),
                    "inspector_only": True,
                },
                channel=ch,
                external_chat_id=tid,
            )

        return _hook
