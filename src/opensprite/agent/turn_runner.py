"""Direct user-turn orchestration for :class:`AgentLoop`."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from ..bus.message import AssistantMessage, UserMessage
from ..media import AgentMediaService, AudioInputPreprocessor
from ..runs.events import AUDIO_INPUT_TRANSCRIBED_EVENT, EXECUTION_STOPPED_EVENT, LLM_STATUS_EVENT
from ..runs.lifecycle import RUN_COMPLETED_STATUS, RUN_STOPPED_STATUS
from ..runs.trace import AgentRunStateService, RunBusyError, RunTraceRecorder
from ..storage import StoredDelegatedTask
from ..utils.log import logger
from .execution import ExecutionResult
from .response_finalizer import AgentResponseFinalizer
from .run_lifecycle import RunLifecycleService
from .turn_context import TurnContextService
from .turn_events import TurnEventEmitter
from .turn_input import PreparedTurnInput, message_with_runtime_context
from .turn_result_updates import (
    apply_runtime_file_changes,
    merge_delegated_task_updates,
    merge_workflow_outcomes,
    with_delegated_tasks,
    with_workflow_outcomes,
)


class AgentTurnRunner:
    """Run one prepared user turn through the normal LLM/tool loop."""

    def __init__(
        self,
        *,
        run_trace: RunTraceRecorder,
        response_finalizer: AgentResponseFinalizer,
        turn_context: TurnContextService,
        run_state: AgentRunStateService,
        connect_mcp: Callable[[], Awaitable[None]],
        save_user_message: Callable[..., Awaitable[None]],
        emit_run_event: Callable[..., Awaitable[None]],
        call_llm: Callable[..., Awaitable[ExecutionResult]],
        transcribe_audio: Callable[[list[str]], Awaitable[str]],
        get_queued_outbound_media: Callable[[], dict[str, list[str]]],
        media_saved_ack: Callable[[], str],
        media_persistence_failed_message: Callable[[], str],
        media_persistence_partial_failure_message: Callable[[], str],
        llm_not_configured_message: Callable[[], str],
        format_log_preview: Callable[..., str],
        set_session_overlay_id: Callable[[str, dict[str, Any] | None, str | None, str | None], None],
        schedule_curator: Callable[[str, str, str | None, str | None, ExecutionResult], None],
        finalize_learning_reuse: Callable[[str, str, bool], None],
        consume_delegated_task_updates: Callable[[str], tuple[StoredDelegatedTask, ...]],
        clear_delegated_task_updates: Callable[[str], None],
        consume_workflow_outcomes: Callable[[str], tuple[dict[str, Any], ...]],
        clear_workflow_outcomes: Callable[[str], None],
    ) -> None:
        self.run_trace = run_trace
        self.response_finalizer = response_finalizer
        self.turn_context = turn_context
        self.run_lifecycle = RunLifecycleService(
            run_trace=run_trace,
            run_state=run_state,
            emit_run_event=emit_run_event,
            clear_delegated_task_updates=clear_delegated_task_updates,
            clear_workflow_outcomes=clear_workflow_outcomes,
            format_log_preview=format_log_preview,
        )
        self._connect_mcp = connect_mcp
        self._save_user_message = save_user_message
        self._turn_events = TurnEventEmitter(emit_run_event)
        self._call_llm = call_llm
        self.audio_input = AudioInputPreprocessor(transcribe_audio)
        self._get_queued_outbound_media = get_queued_outbound_media
        self._media_saved_ack = media_saved_ack
        self._media_persistence_failed_message = media_persistence_failed_message
        self._media_persistence_partial_failure_message = (
            media_persistence_partial_failure_message
        )
        self._llm_not_configured_message = llm_not_configured_message
        self._set_session_overlay_id = set_session_overlay_id
        self._schedule_curator = schedule_curator
        self._finalize_learning_reuse = finalize_learning_reuse
        self._consume_delegated_task_updates = consume_delegated_task_updates
        self._consume_workflow_outcomes = consume_workflow_outcomes

    @staticmethod
    def is_media_only_message(user_message: UserMessage) -> bool:
        """Return whether a turn only carries media without instructions."""
        if AudioInputPreprocessor.should_pretranscribe(user_message):
            return False
        return AgentMediaService.is_media_only_message(
            text=user_message.text,
            images=user_message.images,
            audios=user_message.audios,
            videos=user_message.videos,
        )

    async def _preprocess_audio_only_message(
        self,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> None:
        """Turn pure voice input into text before it reaches the LLM."""
        result = await self.audio_input.preprocess(user_message, turn)
        if not result.transcribed:
            return
        await self._turn_events.emit(
            turn,
            run_id,
            AUDIO_INPUT_TRANSCRIBED_EVENT,
            {
                "status": result.status,
                "audio_files": list(result.audio_files),
                "transcript_len": result.transcript_len,
            },
        )

    @staticmethod
    def _user_history_content(user_message: UserMessage, turn: PreparedTurnInput) -> str:
        """Return one stable history entry for the original user turn."""
        if (user_message.text or "").strip():
            return user_message.text or ""

        failed_events = [event for event in turn.media_events if event.get("status") != "persisted"]
        if turn.image_files or turn.audio_files or turn.video_files:
            if failed_events:
                return AgentMediaService.format_partially_saved_media_history_content(
                    image_files=turn.image_files,
                    audio_files=turn.audio_files,
                    video_files=turn.video_files,
                    failed_count=len(failed_events),
                )
            return AgentMediaService.format_saved_media_history_content(
                image_files=turn.image_files,
                audio_files=turn.audio_files,
                video_files=turn.video_files,
            )
        return AgentMediaService.format_failed_media_history_content()

    async def _save_interrupted_user_history(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
    ) -> None:
        """Best-effort preserve input when preprocessing is interrupted."""
        try:
            await self._save_user_message(
                turn.session_id,
                self._user_history_content(user_message, turn),
                metadata=turn.user_metadata,
            )
        except BaseException as exc:
            logger.warning(
                "[{}] user.history.persist_after_interrupt_failed | error={}",
                turn.session_id,
                exc,
            )

    async def run_user_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        llm_configured: bool,
    ) -> AssistantMessage:
        """Start telemetry and run one user turn."""
        try:
            run = await self.run_lifecycle.start_turn(user_message=user_message, turn=turn)
        except RunBusyError:
            raise
        except BaseException:
            await self._save_interrupted_user_history(user_message=user_message, turn=turn)
            raise
        run_id = run.run_id
        history_saved = False
        try:
            await self.run_lifecycle.record_inbound_media(run=run, turn=turn)
            await self._preprocess_audio_only_message(user_message, turn, run_id)
            self._set_session_overlay_id(
                turn.session_id,
                user_message.metadata,
                turn.channel,
                user_message.sender_id,
            )

            await self._save_user_message(
                turn.session_id,
                self._user_history_content(user_message, turn),
                metadata=turn.user_metadata,
            )
            history_saved = True

            if self.is_media_only_message(user_message):
                return await self.run_media_only_turn(
                    turn=turn,
                    run_id=run_id,
                )

            with self.turn_context.activate(
                session_id=turn.session_id,
                channel=turn.channel,
                external_chat_id=turn.external_chat_id,
                images=user_message.images,
                audios=user_message.audios,
                videos=user_message.videos,
                run_id=run_id,
            ):
                if not llm_configured:
                    return await self.run_llm_not_configured_turn(
                        user_message=user_message,
                        turn=turn,
                        run_id=run_id,
                    )
                return await self.run_direct_turn(
                    user_message=user_message,
                    turn=turn,
                    run_id=run_id,
                )
        except asyncio.CancelledError:
            if not history_saved:
                await self._save_interrupted_user_history(user_message=user_message, turn=turn)
            self._finalize_learning_reuse(turn.session_id, run_id, False)
            await self.run_lifecycle.record_cancelled(run)
            raise
        except Exception as exc:
            if not history_saved:
                await self._save_interrupted_user_history(user_message=user_message, turn=turn)
            logger.exception(
                f"[{turn.session_id}] Agent.process failed: channel={turn.channel}, "
                f"text_len={len(user_message.text or '')}, images={len(user_message.images or [])}, "
                f"audios={len(user_message.audios or [])}, videos={len(user_message.videos or [])}"
            )
            self._finalize_learning_reuse(turn.session_id, run_id, False)
            await self.run_lifecycle.record_failed(run, exc)
            raise
        finally:
            self.run_lifecycle.finish_turn(run)

    async def run_media_only_turn(
        self,
        *,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> AssistantMessage:
        """Persist a media-only turn and return the configured acknowledgement."""
        if not (turn.image_files or turn.audio_files or turn.video_files):
            return await self.run_failed_media_only_turn(turn=turn, run_id=run_id)
        failed_events = [event for event in turn.media_events if event.get("status") != "persisted"]
        if failed_events:
            return await self.run_partially_failed_media_only_turn(
                turn=turn,
                run_id=run_id,
                failed_events=failed_events,
            )

        response = self._media_saved_ack()
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata={"reason": "media_only", "response_len": len(response or "")},
            run_event_payload={
                "status": "completed",
                "reason": "media_only",
                "response_len": len(response or ""),
            },
            log_prefix="media_only=true ",
            log_before_record=True,
        )

    async def run_failed_media_only_turn(
        self,
        *,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> AssistantMessage:
        """Persist an explicit failure when no attached media could be saved."""
        response = self._media_persistence_failed_message()
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata={
                "reason": "media_persistence_failed",
                "response_len": len(response),
            },
            run_event_payload={
                "status": "failed",
                "reason": "media_persistence_failed",
                "response_len": len(response),
            },
            log_prefix="media_only=true persisted_files=0 ",
            log_before_record=True,
            terminal_status="failed",
        )

    async def run_partially_failed_media_only_turn(
        self,
        *,
        turn: PreparedTurnInput,
        run_id: str,
        failed_events: list[dict[str, Any]],
    ) -> AssistantMessage:
        """Persist an honest failure when only some media attachments were saved."""
        saved_file_count = len(turn.image_files) + len(turn.audio_files) + len(turn.video_files)
        response = self._media_persistence_partial_failure_message()
        failure_metadata = {
            "reason": "media_persistence_partial_failure",
            "saved_file_count": saved_file_count,
            "failed_attachment_count": len(failed_events),
            "response_len": len(response),
        }
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata=failure_metadata,
            run_event_payload={"status": "failed", **failure_metadata},
            log_prefix=f"media_only=true persisted_files={saved_file_count} ",
            log_before_record=True,
            terminal_status="failed",
        )

    async def run_llm_not_configured_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> AssistantMessage:
        """Persist a turn and return the configured setup hint."""
        logger.warning("[{}] agent.skip | reason=llm-not-configured", turn.session_id)
        response = self._llm_not_configured_message()
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata={"reason": "llm_not_configured", "response_len": len(response or "")},
            run_event_payload={
                "status": "failed",
                "reason": "llm_not_configured",
                "response_len": len(response or ""),
            },
            log_before_record=True,
            terminal_status="failed",
        )

    async def run_direct_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> AssistantMessage:
        """Execute one normal LLM/tool turn and persist its visible response."""
        persisted_user_message = user_message.text
        await self._connect_mcp()

        logger.info(f"[{turn.session_id}] agent.run | status=processing")
        await self._turn_events.emit(turn, run_id, LLM_STATUS_EVENT, {"message": "processing"})

        self.turn_context.reset_file_changes()
        result = await self._call_llm(
            turn.session_id,
            current_message=message_with_runtime_context(persisted_user_message, turn.user_metadata),
            history_current_message=persisted_user_message,
            channel=turn.channel,
            user_images=user_message.images,
            user_image_files=turn.image_files,
            user_audio_files=self.audio_input.audio_files_for_llm(user_message, turn),
            user_video_files=turn.video_files,
            external_chat_id=turn.external_chat_id,
            emit_tool_progress=True,
        )
        result = apply_runtime_file_changes(result, self.turn_context.snapshot_file_changes())
        result = self._merge_runtime_updates(run_id, result)
        await self._record_execution_trace(turn, run_id, result)

        response = result.content
        response_metadata, status_metadata = self._response_metadata(response, result)
        persisted_assistant_metadata = dict(turn.assistant_metadata)
        if result.reasoning_details:
            persisted_assistant_metadata["llm_reasoning_details"] = result.reasoning_details

        outbound_media = self._get_queued_outbound_media()
        terminal_status = RUN_STOPPED_STATUS if result.stop_reason else RUN_COMPLETED_STATUS
        completed = terminal_status == RUN_COMPLETED_STATUS

        async def after_response_saved() -> None:
            self._finalize_learning_reuse(turn.session_id, run_id, completed)

        assistant_message = await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            persisted_assistant_metadata=persisted_assistant_metadata,
            run_part_metadata=response_metadata,
            run_event_payload={
                "status": terminal_status,
                **response_metadata,
            },
            status_metadata=status_metadata,
            images=outbound_media["images"] or None,
            voices=outbound_media["voices"] or None,
            audios=outbound_media["audios"] or None,
            videos=outbound_media["videos"] or None,
            after_save=after_response_saved,
            terminal_status=terminal_status,
        )
        if completed:
            self._schedule_curator(
                turn.session_id,
                run_id,
                turn.channel,
                turn.external_chat_id,
                result,
            )
        return assistant_message

    def _merge_runtime_updates(self, run_id: str, result: ExecutionResult) -> ExecutionResult:
        delegated_updates = self._consume_delegated_task_updates(run_id)
        if delegated_updates:
            result = with_delegated_tasks(
                result,
                merge_delegated_task_updates(result.delegated_tasks, delegated_updates),
            )
        workflow_updates = self._consume_workflow_outcomes(run_id)
        if workflow_updates:
            result = with_workflow_outcomes(
                result,
                merge_workflow_outcomes(result.workflow_outcomes, workflow_updates),
            )
        return result

    async def _record_execution_trace(
        self,
        turn: PreparedTurnInput,
        run_id: str,
        result: ExecutionResult,
    ) -> None:
        await self.run_trace.record_context_compaction_parts(
            turn.session_id,
            run_id,
            result.context_compaction_events,
        )
        await self.run_trace.record_llm_step_parts(
            turn.session_id,
            run_id,
            result.llm_step_events,
        )
        if result.stop_reason:
            await self._turn_events.emit(
                turn,
                run_id,
                EXECUTION_STOPPED_EVENT,
                {
                    "schema_version": 1,
                    "status": "stopped",
                    "stop_reason": result.stop_reason,
                    **dict(result.stop_metadata or {}),
                },
            )

    @staticmethod
    def _response_metadata(
        response: str,
        result: ExecutionResult,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        response_metadata: dict[str, Any] = {
            "response_len": len(response or ""),
            "executed_tool_calls": result.executed_tool_calls,
            "had_tool_error": result.had_tool_error,
            "context_compactions": result.context_compactions,
            "delegated_tasks": [task.to_payload() for task in result.delegated_tasks],
            "workflow_outcomes": [dict(item) for item in result.workflow_outcomes],
        }
        status_metadata: dict[str, Any] = {
            "executed_tool_calls": result.executed_tool_calls,
            "had_tool_error": result.had_tool_error,
            "context_compactions": result.context_compactions,
        }
        if result.stop_reason:
            response_metadata["stop_reason"] = result.stop_reason
            status_metadata["stop_reason"] = result.stop_reason
            if result.stop_metadata:
                response_metadata["stop_metadata"] = dict(result.stop_metadata)
                status_metadata["stop_metadata"] = dict(result.stop_metadata)
        return response_metadata, status_metadata
