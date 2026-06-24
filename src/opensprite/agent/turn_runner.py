"""User turn orchestration for AgentLoop.process."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..bus.message import AssistantMessage, UserMessage
from ..runs.events import (
    AUTO_CONTINUE_COMPLETED_EVENT,
    AUTO_CONTINUE_SCHEDULED_EVENT,
    AUTO_CONTINUE_SKIPPED_EVENT,
    AUDIO_INPUT_TRANSCRIBED_EVENT,
    COMPLETION_GATE_EVALUATED_EVENT,
    DIRECT_VERIFICATION_STARTED_EVENT,
    DIRECT_WORKFLOW_RESUME_STARTED_EVENT,
    EXECUTION_STOPPED_EVENT,
    LLM_STATUS_EVENT,
    TASK_ARTIFACTS_RECORDED_EVENT,
    TASK_CHECKLIST_UPDATED_EVENT,
    TASK_CLARIFICATION_REQUESTED_EVENT,
    TASK_CHECKPOINT_RECORDED_EVENT,
    TASK_SCORECARD_RECORDED_EVENT,
    TASK_INTENT_DETECTED_EVENT,
    WORK_PLAN_CREATED_EVENT,
    WORK_PROGRESS_UPDATED_EVENT,
)
from ..utils.log import logger
from .completion.auto_continue import AutoContinueService
from .completion.source_finalization import source_finalization_sources
from .completion.source_material import format_web_source_context
from .completion_gate import (
    CompletionBlockerMessages,
    CompletionGateResult,
    CompletionGateService,
)
from .completion_gate import (
    INCOMPLETE_COMPLETION_STATUS,
    is_complete_completion_status,
)
from .execution import ExecutionResult
from ..media import (
    AgentMediaService,
    AudioInputPreprocessor,
)
from ..runs.trace import AgentRunStateService
from ..runs.trace import RunTraceRecorder, WorktreeSandboxInspector
from ..storage import StorageProvider, StoredDelegatedTask, StoredWorkState
from .task.resolution import TaskContextDecision
from .task.intent import TaskIntent
from .task.progress import (
    WorkPlan,
    WorkProgressService,
    WorkProgressUpdate,
)
from .task.scorecard import task_scorecard_metadata
from .task.decision import TurnTaskPlanningService
from .turn_context import TurnContextService
from .turn_directives import (
    extract_direct_verify_request,
    extract_follow_up_resume_request,
)
from .turn_events import TurnEventEmitter
from .turn_input import (
    PreparedTurnInput,
    message_with_runtime_context,
)
from .turn_result_aggregation import aggregate_execution_results
from .turn_result_updates import (
    apply_runtime_progress,
    merge_delegated_task_updates,
    merge_workflow_outcomes,
    with_delegated_tasks,
    with_workflow_outcomes,
)
from .turn_response_metadata import build_turn_response_metadata
from .turn_outcome import (
    LLM_NOT_CONFIGURED_LOG_REASON,
    LLM_NOT_CONFIGURED_TURN_REASON,
    MEDIA_ONLY_TURN_REASON,
    TASK_CLARIFICATION_TURN_REASON,
    TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD,
    TURN_METADATA_COMPLETION_REASON_FIELD,
    TURN_METADATA_COMPLETION_STATUS_FIELD,
    can_replace_initial_work_state,
    final_response_after_exhausted_continuation,
    is_tool_backed_task_contract,
    task_checkpoint_metadata,
)
from .run_lifecycle import RunLifecycleService
from .response_finalizer import AgentResponseFinalizer


@dataclass(frozen=True)
class TurnPassEvaluation:
    """Evaluation output for one normal-turn execution pass."""

    aggregate_result: ExecutionResult
    completion_result: CompletionGateResult
    work_progress: WorkProgressUpdate
    collected_delegated_tasks: tuple[StoredDelegatedTask, ...]
    collected_workflow_outcomes: tuple[dict[str, Any], ...]


class AgentTurnRunner:
    """Runs user-turn branches after inbound turn input is prepared."""

    def __init__(
        self,
        *,
        run_trace: RunTraceRecorder,
        response_finalizer: AgentResponseFinalizer,
        turn_context: TurnContextService,
        run_state: AgentRunStateService,
        task_initial_llm_config: Any | None,
        completion_gate: CompletionGateService,
        completion_verifier_context: Callable[[], tuple[Any, str | None]],
        auto_continue: AutoContinueService,
        work_progress: WorkProgressService,
        connect_mcp: Callable[[], Awaitable[None]],
        save_user_message: Callable[..., Awaitable[None]],
        emit_run_event: Callable[..., Awaitable[None]],
        call_llm: Callable[..., Awaitable[ExecutionResult]],
        transcribe_audio: Callable[[list[str]], Awaitable[str]],
        run_workflow: Callable[[str, str, str | None], Awaitable[str]],
        run_verify: Callable[[str, str, tuple[str, ...]], Awaitable[ExecutionResult]],
        verification_available: Callable[[], bool],
        get_queued_outbound_media: Callable[[], dict[str, list[str]]],
        media_saved_ack: Callable[[], str],
        llm_not_configured_message: Callable[[], str],
        completion_blocker_messages: Callable[[], CompletionBlockerMessages],
        format_log_preview: Callable[..., str],
        set_session_overlay_id: Callable[[str, dict[str, Any] | None, str | None, str | None], None],
        read_active_task_snapshot: Callable[[str], str],
        get_work_state: Callable[[str], Awaitable[StoredWorkState | None]],
        save_work_state: Callable[[StoredWorkState | None], Awaitable[None]],
        apply_completion_gate_result: Callable[[str, CompletionGateResult], Awaitable[None]],
        apply_work_progress: Callable[[str, WorkProgressUpdate, StoredWorkState | None], Awaitable[None]],
        schedule_curator: Callable[[str, str, str | None, str | None, ExecutionResult], None],
        finalize_learning_reuse: Callable[[str, str, bool], None],
        consume_delegated_task_updates: Callable[[str], tuple[StoredDelegatedTask, ...]],
        clear_delegated_task_updates: Callable[[str], None],
        consume_workflow_outcomes: Callable[[str], tuple[dict[str, Any], ...]],
        clear_workflow_outcomes: Callable[[str], None],
        worktree_sandbox_enabled: Callable[[], bool],
        workspace_root: Callable[[], Path],
    ):
        self.run_trace = run_trace
        self.response_finalizer = response_finalizer
        self.turn_context = turn_context
        self.completion_gate = completion_gate
        self._completion_verifier_context = completion_verifier_context
        self.auto_continue = auto_continue
        self.work_progress = work_progress
        self.task_planning = TurnTaskPlanningService(
            work_progress=work_progress,
            read_active_task_snapshot=read_active_task_snapshot,
            build_runtime_message=message_with_runtime_context,
            llm_config=task_initial_llm_config,
        )
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
        self._run_workflow = run_workflow
        self._run_verify = run_verify
        self._verification_available = verification_available
        self._get_queued_outbound_media = get_queued_outbound_media
        self._media_saved_ack = media_saved_ack
        self._llm_not_configured_message = llm_not_configured_message
        self._completion_blocker_messages = completion_blocker_messages
        self._format_log_preview = format_log_preview
        self._set_session_overlay_id = set_session_overlay_id
        self._get_work_state = get_work_state
        self._save_work_state = save_work_state
        self._apply_completion_gate_result = apply_completion_gate_result
        self._apply_work_progress = apply_work_progress
        self._schedule_curator = schedule_curator
        self._finalize_learning_reuse = finalize_learning_reuse
        self._consume_delegated_task_updates = consume_delegated_task_updates
        self._consume_workflow_outcomes = consume_workflow_outcomes
        self._worktree_sandbox_enabled = worktree_sandbox_enabled
        self._workspace_root = workspace_root

    @staticmethod
    def is_media_only_message(user_message: UserMessage) -> bool:
        """Return whether a turn only carries media without user instructions."""
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

    async def _maybe_record_worktree_sandbox(
        self,
        session_id: str,
        run_id: str,
        *,
        task_kind: str,
        expects_code_change: bool,
    ) -> bool:
        enabled = self._worktree_sandbox_enabled()
        if not enabled and not expects_code_change:
            return False
        metadata = WorktreeSandboxInspector(
            enabled=enabled,
            workspace_root=self._workspace_root(),
        ).create(session_id=session_id, run_id=run_id).to_payload()
        metadata["task_kind"] = task_kind
        metadata["expects_code_change"] = expects_code_change
        await self.run_trace.record_worktree_sandbox_part(session_id, run_id, metadata)
        return True

    async def run_user_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        llm_configured: bool,
    ) -> AssistantMessage:
        """Start run telemetry and dispatch one prepared user turn."""
        run = await self.run_lifecycle.start_turn(user_message=user_message, turn=turn)
        run_id = run.run_id
        try:
            await self.run_lifecycle.record_inbound_media(run=run, turn=turn)
            await self._preprocess_audio_only_message(user_message, turn, run_id)
            self._set_session_overlay_id(turn.session_id, user_message.metadata, turn.channel, user_message.sender_id)
            existing_work_state = await self._get_work_state(turn.session_id)
            provider, model = self._completion_verifier_context()
            task_plan = await self.task_planning.plan(
                user_message=user_message,
                session_id=turn.session_id,
                user_metadata=turn.user_metadata,
                existing_work_state=existing_work_state,
                provider=provider,
                model=model,
            )
            task_intent = task_plan.task_intent
            worktree_sandbox_recorded = False
            if not task_plan.clarification_question:
                worktree_sandbox_recorded = await self._maybe_record_worktree_sandbox(
                    turn.session_id,
                    run_id,
                    task_kind=task_intent.kind,
                    expects_code_change=False,
                )
            await self._turn_events.emit(
                turn,
                run_id,
                TASK_INTENT_DETECTED_EVENT,
                {
                    **task_intent.to_metadata(),
                    "classification": {
                        "method": task_plan.task_intent_method,
                        "confidence": task_plan.task_intent_confidence,
                        "reason": task_plan.task_intent_reason,
                    },
                    "task_context": task_plan.task_context_decision.to_metadata(),
                },
            )
            work_plan = task_plan.work_plan
            current_work_state = task_plan.current_work_state
        except asyncio.CancelledError:
            try:
                await self.run_lifecycle.record_cancelled(run)
            finally:
                self.run_lifecycle.finish_turn(run)
            raise
        except Exception as exc:
            logger.exception(
                f"[{turn.session_id}] Agent.process failed: channel={turn.channel}, "
                f"text_len={len(user_message.text or '')}, images={len(user_message.images or [])}, audios={len(user_message.audios or [])}, videos={len(user_message.videos or [])}"
            )
            self._finalize_learning_reuse(turn.session_id, run_id, False)
            try:
                await self.run_lifecycle.record_failed(run, exc)
            finally:
                self.run_lifecycle.finish_turn(run)
            raise

        try:
            if task_plan.clarification_question:
                return await self.run_task_clarification_turn(
                    user_message=user_message,
                    turn=turn,
                    run_id=run_id,
                    task_intent=task_intent,
                    task_context_decision=task_plan.task_context_decision,
                    clarification_question=task_plan.clarification_question,
                    confidence=task_plan.task_intent_confidence,
                    reason=task_plan.task_intent_reason,
                )
            if self.is_media_only_message(user_message):
                return await self.run_media_only_turn(
                    user_message=user_message,
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
                try:
                    if not llm_configured:
                        return await self.run_llm_not_configured_turn(
                            user_message=user_message,
                            turn=turn,
                            run_id=run_id,
                        )

                    return await self.run_normal_turn(
                        user_message=user_message,
                        turn=turn,
                        run_id=run_id,
                        task_intent=task_intent,
                        task_context_decision=task_plan.task_context_decision,
                        work_plan=work_plan,
                        current_work_state=current_work_state,
                        worktree_sandbox_recorded=worktree_sandbox_recorded,
                    )
                except asyncio.CancelledError:
                    await self.run_lifecycle.record_cancelled(run)
                    raise
                except Exception as exc:
                    logger.exception(
                        f"[{turn.session_id}] Agent.process failed: channel={turn.channel}, "
                        f"text_len={len(user_message.text or '')}, images={len(user_message.images or [])}, audios={len(user_message.audios or [])}, videos={len(user_message.videos or [])}"
                    )
                    self._finalize_learning_reuse(turn.session_id, run_id, False)
                    await self.run_lifecycle.record_failed(run, exc)
                    raise
        finally:
            self.run_lifecycle.finish_turn(run)

    async def run_media_only_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> AssistantMessage:
        """Persist a media-only turn and return the configured acknowledgement."""
        media_history_content = AgentMediaService.format_saved_media_history_content(
            image_files=turn.image_files,
            audio_files=turn.audio_files,
            video_files=turn.video_files,
        )
        await self._save_user_message(turn.session_id, media_history_content, metadata=turn.user_metadata)
        response = self._media_saved_ack()
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata={"reason": MEDIA_ONLY_TURN_REASON, "response_len": len(response or "")},
            run_event_payload={
                "status": "completed",
                "reason": MEDIA_ONLY_TURN_REASON,
                "response_len": len(response or ""),
            },
            log_prefix="media_only=true ",
            log_before_record=True,
        )

    async def run_llm_not_configured_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
    ) -> AssistantMessage:
        """Persist a turn and return the configured setup hint when no LLM is available."""
        logger.warning("[{}] agent.skip | reason={}", turn.session_id, LLM_NOT_CONFIGURED_LOG_REASON)
        await self._save_user_message(turn.session_id, user_message.text, metadata=turn.user_metadata)
        response = self._llm_not_configured_message()
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata={"reason": LLM_NOT_CONFIGURED_TURN_REASON, "response_len": len(response or "")},
            run_event_payload={
                "status": "completed",
                "reason": LLM_NOT_CONFIGURED_TURN_REASON,
                "response_len": len(response or ""),
            },
            log_before_record=True,
        )

    async def run_task_clarification_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
        task_intent: TaskIntent,
        task_context_decision: TaskContextDecision,
        clarification_question: str,
        confidence: float,
        reason: str,
    ) -> AssistantMessage:
        """Persist an unclear turn and ask the user for the missing routing detail."""
        response = clarification_question.strip()
        metadata = {
            "schema_version": 1,
            "status": "completed",
            "reason": TASK_CLARIFICATION_TURN_REASON,
            "response_len": len(response),
            "confidence": confidence,
            "classification_reason": reason,
            "task_intent": task_intent.to_metadata(),
            "task_context": task_context_decision.to_metadata(),
        }
        await self._save_user_message(turn.session_id, user_message.text, metadata=turn.user_metadata)
        await self._turn_events.emit(
            turn,
            run_id,
            TASK_CLARIFICATION_REQUESTED_EVENT,
            metadata,
        )
        return await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            run_part_metadata=metadata,
            run_event_payload=metadata,
            log_prefix="clarification=true ",
            log_before_record=True,
        )

    async def _evaluate_turn_pass(
        self,
        *,
        turn: PreparedTurnInput,
        run_id: str,
        task_intent: TaskIntent,
        user_message_text: str,
        execution_results: list[ExecutionResult],
        response: str,
        collected_delegated_tasks: tuple[StoredDelegatedTask, ...],
        collected_workflow_outcomes: tuple[dict[str, Any], ...],
        auto_continue_attempts: int,
    ) -> TurnPassEvaluation:
        """Record trace artifacts, aggregate execution, and evaluate completion for one pass."""
        exec_result = execution_results[-1]
        await self.run_trace.record_context_compaction_parts(
            turn.session_id,
            run_id,
            exec_result.context_compaction_events,
        )
        await self.run_trace.record_llm_step_parts(
            turn.session_id,
            run_id,
            exec_result.llm_step_events,
        )
        if exec_result.stop_reason:
            await self._turn_events.emit(
                turn,
                run_id,
                EXECUTION_STOPPED_EVENT,
                {
                    "schema_version": 1,
                    "status": "stopped",
                    "stop_reason": exec_result.stop_reason,
                    **dict(exec_result.stop_metadata or {}),
                },
            )
        aggregate_result = aggregate_execution_results(execution_results, content=response)
        delegated_task_updates = self._consume_delegated_task_updates(run_id)
        if delegated_task_updates:
            collected_delegated_tasks = merge_delegated_task_updates(
                collected_delegated_tasks,
                delegated_task_updates,
            )
        workflow_outcomes = self._consume_workflow_outcomes(run_id)
        if workflow_outcomes:
            collected_workflow_outcomes = merge_workflow_outcomes(
                collected_workflow_outcomes,
                workflow_outcomes,
            )
        if collected_delegated_tasks:
            aggregate_result = with_delegated_tasks(aggregate_result, collected_delegated_tasks)
        if collected_workflow_outcomes:
            aggregate_result = with_workflow_outcomes(aggregate_result, collected_workflow_outcomes)

        completion_result = await self._evaluate_completion(
            task_intent=task_intent,
            response_text=response,
            execution_result=aggregate_result,
            user_message_text=user_message_text,
        )
        completion_metadata = self._completion_metadata(
            completion_result,
            auto_continue_attempts=auto_continue_attempts,
        )
        await self._turn_events.emit(
            turn,
            run_id,
            COMPLETION_GATE_EVALUATED_EVENT,
            completion_metadata,
        )
        work_progress = self.work_progress.evaluate(
            task_intent=task_intent,
            completion_result=completion_result,
            execution_result=aggregate_result,
            auto_continue_attempts=auto_continue_attempts,
            pass_index=len(execution_results),
        )
        await self._turn_events.emit(
            turn,
            run_id,
            WORK_PROGRESS_UPDATED_EVENT,
            work_progress.to_metadata(),
        )
        task_checkpoint = task_checkpoint_metadata(
            aggregate_result=aggregate_result,
            completion_result=completion_result,
            work_progress=work_progress,
            pass_index=len(execution_results),
            auto_continue_attempts=auto_continue_attempts,
        )
        await self._turn_events.emit(
            turn,
            run_id,
            TASK_CHECKPOINT_RECORDED_EVENT,
            task_checkpoint,
        )
        await self.run_trace.record_task_checkpoint_part(turn.session_id, run_id, task_checkpoint)
        task_scorecard = task_scorecard_metadata(
            aggregate_result=aggregate_result,
            completion_result=completion_result,
        )
        await self._turn_events.emit(
            turn,
            run_id,
            TASK_SCORECARD_RECORDED_EVENT,
            task_scorecard,
        )
        await self.run_trace.record_task_scorecard_part(turn.session_id, run_id, task_scorecard)
        if auto_continue_attempts > 0:
            await self._turn_events.emit(
                turn,
                run_id,
                AUTO_CONTINUE_COMPLETED_EVENT,
                {
                    "attempt": auto_continue_attempts,
                    TURN_METADATA_COMPLETION_STATUS_FIELD: completion_result.status,
                    TURN_METADATA_COMPLETION_REASON_FIELD: completion_result.reason,
                },
            )
        return TurnPassEvaluation(
            aggregate_result=aggregate_result,
            completion_result=completion_result,
            work_progress=work_progress,
            collected_delegated_tasks=collected_delegated_tasks,
            collected_workflow_outcomes=collected_workflow_outcomes,
        )

    async def _evaluate_completion(
        self,
        *,
        task_intent: TaskIntent,
        response_text: str,
        execution_result: ExecutionResult,
        user_message_text: str = "",
    ) -> CompletionGateResult:
        provider, model = self._completion_verifier_context()
        return await self.completion_gate.evaluate_with_verifier(
            task_intent=task_intent,
            response_text=response_text,
            execution_result=execution_result,
            user_message_text=user_message_text,
            provider=provider,
            model=model,
        )

    def _completion_metadata(
        self,
        completion_result: CompletionGateResult,
        *,
        auto_continue_attempts: int,
    ) -> dict[str, Any]:
        metadata = completion_result.to_metadata()
        metadata[TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD] = auto_continue_attempts
        provider, model = self._completion_verifier_context()
        verifier = metadata.setdefault("verifier", {})
        if isinstance(verifier, dict):
            verifier.setdefault("method", "llm")
            verifier.setdefault("role", "verifier")
            verifier.setdefault("provider", type(provider).__name__ if provider is not None else "")
            verifier.setdefault("model", model or "")
        return metadata

    async def _refresh_completion_after_response_change(
        self,
        *,
        turn: PreparedTurnInput,
        run_id: str,
        task_intent: TaskIntent,
        user_message_text: str,
        aggregate_result: ExecutionResult,
        response: str,
        execution_results: list[ExecutionResult],
        auto_continue_attempts: int,
    ) -> tuple[CompletionGateResult, WorkProgressUpdate]:
        aggregate_result.content = response
        completion_result = await self._evaluate_completion(
            task_intent=task_intent,
            response_text=response,
            execution_result=aggregate_result,
            user_message_text=user_message_text,
        )
        completion_metadata = self._completion_metadata(
            completion_result,
            auto_continue_attempts=auto_continue_attempts,
        )
        await self._turn_events.emit(
            turn,
            run_id,
            COMPLETION_GATE_EVALUATED_EVENT,
            completion_metadata,
        )
        work_progress = self.work_progress.evaluate(
            task_intent=task_intent,
            completion_result=completion_result,
            execution_result=aggregate_result,
            auto_continue_attempts=auto_continue_attempts,
            pass_index=len(execution_results),
        )
        await self._turn_events.emit(
            turn,
            run_id,
            WORK_PROGRESS_UPDATED_EVENT,
            work_progress.to_metadata(),
        )
        final_task_scorecard = task_scorecard_metadata(
            aggregate_result=aggregate_result,
            completion_result=completion_result,
        )
        await self._turn_events.emit(
            turn,
            run_id,
            TASK_SCORECARD_RECORDED_EVENT,
            final_task_scorecard,
        )
        await self.run_trace.record_task_scorecard_part(
            turn.session_id,
            run_id,
            final_task_scorecard,
        )
        return completion_result, work_progress

    async def run_normal_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnInput,
        run_id: str,
        task_intent: TaskIntent,
        task_context_decision: TaskContextDecision,
        work_plan: WorkPlan | None,
        current_work_state: StoredWorkState | None,
        worktree_sandbox_recorded: bool,
    ) -> AssistantMessage:
        """Execute the normal turn path after special-case early exits are ruled out."""
        await self._connect_mcp()

        # The current user message is persisted before building the prompt so history/search stay current.
        await self._save_user_message(turn.session_id, user_message.text, metadata=turn.user_metadata)

        logger.info(f"[{turn.session_id}] agent.run | status=processing")
        await self._turn_events.emit(
            turn,
            run_id,
            LLM_STATUS_EVENT,
            {"message": "processing"},
        )
        execution_results: list[ExecutionResult] = []
        collected_delegated_tasks: tuple[StoredDelegatedTask, ...] = ()
        collected_workflow_outcomes: tuple[dict[str, Any], ...] = ()
        auto_continue_attempts = 0
        direct_actions_used = 0
        last_direct_workflow: str | None = None
        last_direct_start_step: str | None = None
        last_direct_verify_action: str | None = None
        last_direct_verify_path: str | None = None
        last_direct_verify_pytest_args: tuple[str, ...] = ()
        same_target_verify_attempts = 0
        work_plan_recorded = False
        pending_direct_verify: dict[str, Any] | None = extract_direct_verify_request(user_message.metadata)
        current_message = message_with_runtime_context(user_message.text, turn.user_metadata)
        current_allow_tools = True
        current_task_contract_override = None

        pending_direct_resume = extract_follow_up_resume_request(user_message.metadata)

        while True:
            self.turn_context.reset_work_progress()
            direct_resume_context: dict[str, str] | None = None
            if pending_direct_resume is not None:
                direct_resume_context = dict(pending_direct_resume)
                await self._turn_events.emit(
                    turn,
                    run_id,
                    DIRECT_WORKFLOW_RESUME_STARTED_EVENT,
                    {"schema_version": 1, **direct_resume_context},
                )
                response, exec_result, collected_delegated_tasks, collected_workflow_outcomes = await self._run_direct_workflow_resume(
                    run_id=run_id,
                    task_intent=task_intent,
                    current_work_state=current_work_state,
                    direct_resume=pending_direct_resume,
                    collected_delegated_tasks=collected_delegated_tasks,
                    collected_workflow_outcomes=collected_workflow_outcomes,
                )
                pending_direct_resume = None
            elif pending_direct_verify is not None:
                await self._turn_events.emit(
                    turn,
                    run_id,
                    DIRECT_VERIFICATION_STARTED_EVENT,
                    {"schema_version": 1, **dict(pending_direct_verify)},
                )
                response, exec_result = await self._run_direct_verification(
                    direct_verify=pending_direct_verify,
                )
                pending_direct_verify = None
            else:
                exec_result = await self._call_llm(
                    turn.session_id,
                    current_message=current_message,
                    channel=turn.channel,
                    user_images=user_message.images,
                    user_image_files=turn.image_files,
                    user_audio_files=self.audio_input.audio_files_for_llm(user_message, turn),
                    user_video_files=turn.video_files,
                    external_chat_id=turn.external_chat_id,
                    emit_tool_progress=True,
                    task_intent=task_intent,
                    task_context_decision=task_context_decision,
                    allow_tools=current_allow_tools,
                    task_contract_override=(
                        current_task_contract_override if auto_continue_attempts > 0 else None
                    ),
                )
                exec_result = apply_runtime_progress(exec_result, self.turn_context.snapshot_work_progress())
                if exec_result.task_contract is not None:
                    contract_work_plan = self.work_progress.create_plan(
                        task_intent,
                        task_contract=exec_result.task_contract,
                    )
                    if contract_work_plan is None:
                        if can_replace_initial_work_state(current_work_state):
                            work_plan = None
                            current_work_state = None
                    else:
                        work_plan = contract_work_plan
                        if not work_plan_recorded:
                            await self._turn_events.emit(
                                turn,
                                run_id,
                                WORK_PLAN_CREATED_EVENT,
                                work_plan.to_metadata(),
                            )
                            work_plan_recorded = True
                        if not worktree_sandbox_recorded and work_plan.expects_code_change:
                            worktree_sandbox_recorded = await self._maybe_record_worktree_sandbox(
                                turn.session_id,
                                run_id,
                                task_kind=work_plan.kind,
                                expects_code_change=True,
                            )
                        if can_replace_initial_work_state(current_work_state):
                            current_work_state = self.work_progress.build_initial_state(
                                session_id=turn.session_id,
                                task_intent=task_intent,
                                work_plan=work_plan,
                                existing_state=None,
                            )
                response = exec_result.content
            execution_results.append(exec_result)

            evaluation = await self._evaluate_turn_pass(
                turn=turn,
                run_id=run_id,
                task_intent=task_intent,
                user_message_text=user_message.text,
                execution_results=execution_results,
                response=response,
                collected_delegated_tasks=collected_delegated_tasks,
                collected_workflow_outcomes=collected_workflow_outcomes,
                auto_continue_attempts=auto_continue_attempts,
            )
            aggregate_result = evaluation.aggregate_result
            completion_result = evaluation.completion_result
            work_progress = evaluation.work_progress
            if is_tool_backed_task_contract(aggregate_result.task_contract):
                current_task_contract_override = aggregate_result.task_contract
            collected_delegated_tasks = evaluation.collected_delegated_tasks
            collected_workflow_outcomes = evaluation.collected_workflow_outcomes

            decision = self.auto_continue.decide(
                task_intent=task_intent,
                completion_result=completion_result,
                execution_result=aggregate_result,
                attempts_used=auto_continue_attempts,
                previous_response=response,
                work_progress=work_progress,
                last_direct_workflow=last_direct_workflow,
                last_direct_start_step=last_direct_start_step,
                direct_actions_used=direct_actions_used,
                last_direct_verify_action=last_direct_verify_action,
                last_direct_verify_path=last_direct_verify_path,
                last_direct_verify_pytest_args=last_direct_verify_pytest_args,
                same_target_verify_attempts=same_target_verify_attempts,
                verification_available=self._verification_available(),
                compaction_handoff=aggregate_result.compaction_handoff,
            )
            if decision.should_continue and decision.direct_workflow and decision.direct_start_step:
                await self._turn_events.emit_auto_continue(
                    turn=turn,
                    run_id=run_id,
                    event_type=AUTO_CONTINUE_SCHEDULED_EVENT,
                    decision=decision,
                    completion_result=completion_result,
                )
                auto_continue_attempts += 1
                direct_actions_used += 1
                last_direct_workflow = decision.direct_workflow
                last_direct_start_step = decision.direct_start_step
                pending_direct_resume = {
                    "workflow": decision.direct_workflow,
                    "start_step": decision.direct_start_step,
                    "step_label": completion_result.follow_up_step_label or decision.direct_start_step,
                    "prompt_type": completion_result.follow_up_prompt_type or "",
                    "detail": completion_result.active_task_detail or "",
                    "previous_response": response,
                }
                continue
            if decision.should_continue and decision.direct_verify_action:
                await self._turn_events.emit_auto_continue(
                    turn=turn,
                    run_id=run_id,
                    event_type=AUTO_CONTINUE_SCHEDULED_EVENT,
                    decision=decision,
                    completion_result=completion_result,
                )
                auto_continue_attempts += 1
                direct_actions_used += 1
                if (
                    decision.direct_verify_action == last_direct_verify_action
                    and (decision.direct_verify_path or ".") == (last_direct_verify_path or ".")
                    and tuple(decision.direct_verify_pytest_args) == tuple(last_direct_verify_pytest_args)
                ):
                    same_target_verify_attempts += 1
                else:
                    same_target_verify_attempts = 1
                last_direct_verify_action = decision.direct_verify_action
                last_direct_verify_path = decision.direct_verify_path or "."
                last_direct_verify_pytest_args = tuple(decision.direct_verify_pytest_args)
                pending_direct_verify = {
                    "action": decision.direct_verify_action,
                    "path": decision.direct_verify_path or ".",
                    "pytest_args": tuple(decision.direct_verify_pytest_args),
                }
                continue
            if decision.should_continue and decision.prompt:
                await self._turn_events.emit_auto_continue(
                    turn=turn,
                    run_id=run_id,
                    event_type=AUTO_CONTINUE_SCHEDULED_EVENT,
                    decision=decision,
                    completion_result=completion_result,
                )
                auto_continue_attempts += 1
                if direct_resume_context is not None:
                    current_message = self.auto_continue.build_post_workflow_resume_prompt(
                        task_intent=task_intent,
                        completion_result=completion_result,
                        previous_response=direct_resume_context.get("previous_response") or "continue",
                        workflow_result=response,
                    )
                else:
                    current_message = decision.prompt
                    current_allow_tools = decision.allow_tools
                continue

            if decision.emit_skipped_event:
                await self._turn_events.emit_auto_continue(
                    turn=turn,
                    run_id=run_id,
                    event_type=AUTO_CONTINUE_SKIPPED_EVENT,
                    decision=decision,
                    completion_result=completion_result,
                )
            break

        ran_source_finalization = False
        source_finalization_source_list = source_finalization_sources(completion_result, aggregate_result)
        if source_finalization_source_list:
            finalization_prompt = self.auto_continue.build_prompt(
                task_intent=task_intent,
                completion_result=completion_result,
                previous_response=response,
                compaction_handoff=aggregate_result.compaction_handoff,
                execution_result=aggregate_result,
                allow_tools=False,
                source_context_override=format_web_source_context(source_finalization_source_list),
            )
            finalization_result = await self._call_llm(
                turn.session_id,
                current_message=finalization_prompt,
                channel=turn.channel,
                user_images=[],
                user_image_files=[],
                user_audio_files=[],
                user_video_files=[],
                external_chat_id=turn.external_chat_id,
                emit_tool_progress=True,
                task_intent=task_intent,
                allow_tools=False,
                task_contract_override=aggregate_result.task_contract,
            )
            finalization_result = apply_runtime_progress(
                finalization_result,
                self.turn_context.snapshot_work_progress(),
            )
            execution_results.append(finalization_result)
            response = finalization_result.content
            aggregate_result = aggregate_execution_results(execution_results, content=response)
            ran_source_finalization = True
        if ran_source_finalization or response != aggregate_result.content:
            completion_result, work_progress = await self._refresh_completion_after_response_change(
                turn=turn,
                run_id=run_id,
                task_intent=task_intent,
                user_message_text=user_message.text,
                aggregate_result=aggregate_result,
                response=response,
                execution_results=execution_results,
                auto_continue_attempts=auto_continue_attempts,
            )

        response = final_response_after_exhausted_continuation(
            response=response,
            completion_result=completion_result,
            auto_continue_attempts=auto_continue_attempts,
            completion_blocker_messages=self._completion_blocker_messages(),
        )
        if response != aggregate_result.content:
            completion_result, work_progress = await self._refresh_completion_after_response_change(
                turn=turn,
                run_id=run_id,
                task_intent=task_intent,
                user_message_text=user_message.text,
                aggregate_result=aggregate_result,
                response=response,
                execution_results=execution_results,
                auto_continue_attempts=auto_continue_attempts,
            )

        outbound_media = self._get_queued_outbound_media()

        response_metadata, status_metadata, persisted_assistant_metadata = build_turn_response_metadata(
            response=response,
            aggregate_result=aggregate_result,
            completion_result=completion_result,
            work_progress=work_progress,
            auto_continue_attempts=auto_continue_attempts,
            assistant_metadata=turn.assistant_metadata,
        )

        updated_work_state = self.work_progress.update_state(
            session_id=turn.session_id,
            state=current_work_state,
            task_intent=task_intent,
            work_plan=work_plan,
            progress=work_progress,
            completion_result=completion_result,
            delegated_task_updates=aggregate_result.delegated_tasks,
            delegate_task_id=aggregate_result.active_delegate_task_id,
            delegate_prompt_type=aggregate_result.active_delegate_prompt_type,
        )
        run_finish_status = (
            "completed" if is_complete_completion_status(completion_result.status)
            else (completion_result.status or INCOMPLETE_COMPLETION_STATUS)
        )

        async def after_response_saved() -> None:
            await self._save_work_state(updated_work_state)
            if updated_work_state is not None:
                todos = await self.run_trace.record_task_checklist_part(turn.session_id, run_id, updated_work_state)
                await self._turn_events.emit(
                    turn,
                    run_id,
                    TASK_CHECKLIST_UPDATED_EVENT,
                    {
                        "status": updated_work_state.status,
                        "objective": updated_work_state.objective,
                        "todos": todos,
                    },
                )
            await self._apply_work_progress(turn.session_id, work_progress, updated_work_state)
            await self._apply_completion_gate_result(turn.session_id, completion_result)
            if aggregate_result.task_artifacts:
                await self._turn_events.emit(
                    turn,
                    run_id,
                    TASK_ARTIFACTS_RECORDED_EVENT,
                    {
                        "status": "completed",
                        "count": len(aggregate_result.task_artifacts),
                        "artifacts": [item.to_metadata() for item in aggregate_result.task_artifacts],
                    },
                )
            self._finalize_learning_reuse(turn.session_id, run_id, True)

        assistant_message = await self.response_finalizer.finalize(
            session_id=turn.session_id,
            run_id=run_id,
            response=response,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            assistant_metadata=turn.assistant_metadata,
            persisted_assistant_metadata=persisted_assistant_metadata,
            run_part_metadata=response_metadata,
            run_event_payload={"status": run_finish_status, **response_metadata},
            status_metadata=status_metadata,
            images=outbound_media["images"] or None,
            voices=outbound_media["voices"] or None,
            audios=outbound_media["audios"] or None,
            videos=outbound_media["videos"] or None,
            after_save=after_response_saved,
        )
        self._schedule_curator(
            turn.session_id,
            run_id,
            turn.channel,
            turn.external_chat_id,
            aggregate_result,
        )
        return assistant_message

    async def _run_direct_workflow_resume(
        self,
        *,
        run_id: str,
        task_intent: TaskIntent,
        current_work_state: StoredWorkState | None,
        direct_resume: dict[str, str],
        collected_delegated_tasks: tuple[StoredDelegatedTask, ...],
        collected_workflow_outcomes: tuple[dict[str, Any], ...],
    ) -> tuple[str, ExecutionResult, tuple[StoredDelegatedTask, ...], tuple[dict[str, Any], ...]]:
        task_objective = (
            current_work_state.objective
            if current_work_state is not None and current_work_state.objective.strip()
            else task_intent.objective
        )
        workflow_result = await self._run_workflow(
            direct_resume["workflow"],
            task_objective,
            direct_resume["start_step"],
        )
        direct_result = ExecutionResult(content=workflow_result, executed_tool_calls=1)
        delegated_task_updates = self._consume_delegated_task_updates(run_id)
        if delegated_task_updates:
            collected_delegated_tasks = merge_delegated_task_updates(
                collected_delegated_tasks,
                delegated_task_updates,
            )
        workflow_outcomes = self._consume_workflow_outcomes(run_id)
        if workflow_outcomes:
            collected_workflow_outcomes = merge_workflow_outcomes(
                collected_workflow_outcomes,
                workflow_outcomes,
            )
        if collected_delegated_tasks:
            direct_result = with_delegated_tasks(direct_result, collected_delegated_tasks)
        if collected_workflow_outcomes:
            direct_result = with_workflow_outcomes(direct_result, collected_workflow_outcomes)
        return workflow_result, direct_result, collected_delegated_tasks, collected_workflow_outcomes

    async def _run_direct_verification(
        self,
        *,
        direct_verify: dict[str, Any],
    ) -> tuple[str, ExecutionResult]:
        result = await self._run_verify(
            str(direct_verify.get("action") or "auto"),
            str(direct_verify.get("path") or "."),
            tuple(str(item or "").strip() for item in (direct_verify.get("pytest_args") or ()) if str(item or "").strip()),
        )
        return result.content, result
