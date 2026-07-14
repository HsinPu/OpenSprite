"""LLM prompt preparation and call orchestration."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ...config import AgentConfig
from ...context.message_history import PreparedPromptHistory
from ...llms import ChatMessage
from ...runs.events import (
    HISTORY_LOADED_EVENT,
    MCP_TOOLS_SYNCED_EVENT,
    PROMPT_BUILT_EVENT,
    PROMPT_TOKENS_ESTIMATED_EVENT,
)
from ...runs.trace import mcp_tool_names as list_mcp_tool_names
from ...tools import ToolRegistry
from ...utils.log import logger
from ..execution import ExecutionResult


class LlmCallService:
    """Builds the prompt for one LLM call and delegates to the execution engine."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        load_prompt_history: Callable[[str, str], Awaitable[PreparedPromptHistory]],
        get_current_audios: Callable[[], list[str] | None],
        get_current_videos: Callable[[], list[str] | None],
        augment_message_for_media: Callable[..., str],
        estimate_tool_schema_tokens: Callable[..., int],
        trim_history_to_token_budget: Callable[..., tuple[list[dict[str, Any]], int, int, int]],
        effective_context_token_budget: Callable[[], int],
        llm_context_window_tokens: Callable[[], int | None],
        llm_output_reserve_tokens: Callable[[], int],
        sync_runtime_mcp_tools_context: Callable[[], None],
        build_messages: Callable[..., list[dict[str, Any]]],
        build_system_prompt: Callable[[str], str],
        log_prepared_messages: Callable[[str, list[dict[str, Any]]], None],
        emit_run_event: Callable[..., Awaitable[None]],
        get_tool_registry: Callable[[], ToolRegistry],
        get_current_run_id: Callable[[], str | None],
        should_cancel_run: Callable[[str, str | None], bool],
        make_tool_progress_hook: Callable[..., Callable[[str, dict[str, Any]], Awaitable[None]] | None],
        make_tool_result_hook: Callable[..., Callable[[str, dict[str, Any], str], Awaitable[None]] | None],
        make_llm_status_hook: Callable[..., Callable[[Any], Awaitable[None]] | None],
        make_llm_delta_hook: Callable[..., Callable[[str, str, str, int], Awaitable[None]] | None],
        make_tool_input_delta_hook: Callable[..., Callable[[str, str, str, int], Awaitable[None]] | None],
        make_reasoning_delta_hook: Callable[..., Callable[[str, int], Awaitable[None]] | None],
        execute_messages: Callable[..., Awaitable[ExecutionResult]],
    ):
        self.config = config
        self._load_prompt_history = load_prompt_history
        self._get_current_audios = get_current_audios
        self._get_current_videos = get_current_videos
        self._augment_message_for_media = augment_message_for_media
        self._estimate_tool_schema_tokens = estimate_tool_schema_tokens
        self._trim_history_to_token_budget = trim_history_to_token_budget
        self._effective_context_token_budget = effective_context_token_budget
        self._llm_context_window_tokens = llm_context_window_tokens
        self._llm_output_reserve_tokens = llm_output_reserve_tokens
        self._sync_runtime_mcp_tools_context = sync_runtime_mcp_tools_context
        self._build_messages = build_messages
        self._build_system_prompt = build_system_prompt
        self._log_prepared_messages = log_prepared_messages
        self._emit_run_event = emit_run_event
        self._get_tool_registry = get_tool_registry
        self._get_current_run_id = get_current_run_id
        self._should_cancel_run = should_cancel_run
        self._make_tool_progress_hook = make_tool_progress_hook
        self._make_tool_result_hook = make_tool_result_hook
        self._make_llm_status_hook = make_llm_status_hook
        self._make_llm_delta_hook = make_llm_delta_hook
        self._make_tool_input_delta_hook = make_tool_input_delta_hook
        self._make_reasoning_delta_hook = make_reasoning_delta_hook
        self._execute_messages = execute_messages

    async def call_llm(
        self,
        session_id: str,
        current_message: str,
        channel: str | None = None,
        allow_tools: bool = True,
        user_images: list[str] | None = None,
        user_image_files: list[str] | None = None,
        user_audio_files: list[str] | None = None,
        user_video_files: list[str] | None = None,
        *,
        external_chat_id: str | None = None,
        emit_tool_progress: bool = False,
        history_current_message: str | None = None,
    ) -> ExecutionResult:
        """Prepare prompt messages and run the LLM/tool execution loop."""
        run_id = self._get_current_run_id()
        logger.info(f"[{session_id}] history.load | requested=true")
        history_message = current_message if history_current_message is None else history_current_message
        prompt_history = await self._load_prompt_history(session_id, history_message)
        history_dicts = prompt_history.messages
        loaded_history_count = prompt_history.loaded_messages
        filtered_tool_messages = prompt_history.filtered_tool_messages

        logger.info(
            f"[{session_id}] prompt.build | history={len(history_dicts)} channel={channel or '-'} images={len(user_images or [])}"
        )
        if run_id is not None:
            await self._emit_run_event(
                session_id,
                run_id,
                HISTORY_LOADED_EVENT,
                {
                    "loaded_messages": loaded_history_count,
                    "history_messages": len(history_dicts),
                    "filtered_tool_messages": filtered_tool_messages,
                },
                channel=channel,
                external_chat_id=external_chat_id,
            )
        if run_id is not None:
            await self._emit_run_event(
                session_id,
                run_id,
                PROMPT_BUILT_EVENT,
                {
                    "history_messages": len(history_dicts),
                    "current_message_len": len(str(current_message or "")),
                    "images": len(user_images or []),
                    "audio_files": len(user_audio_files or []),
                    "video_files": len(user_video_files or []),
                },
                channel=channel,
                external_chat_id=external_chat_id,
            )
        current_audios = self._get_current_audios()
        current_videos = self._get_current_videos()
        prompt_message = self._augment_message_for_media(
            current_message,
            user_images,
            current_audios,
            current_videos,
            user_image_files=user_image_files,
            user_audio_files=user_audio_files,
            user_video_files=user_video_files,
        )
        selected_tool_registry = self._get_tool_registry()
        tool_schema_tokens = self._estimate_tool_schema_tokens(
            allow_tools=allow_tools,
            tool_registry=selected_tool_registry,
        )
        history_dicts, base_tokens, history_tokens, final_tokens = self._trim_history_to_token_budget(
            history=history_dicts,
            current_message=prompt_message,
            channel=channel,
            session_id=session_id,
            tool_schema_tokens=tool_schema_tokens,
        )
        effective_context_budget = self._effective_context_token_budget()
        logger.info(
            f"[{session_id}] prompt.tokens | budget={effective_context_budget} "
            f"history_budget={self.config.history_token_budget} model_window={self._llm_context_window_tokens() or '-'} "
            f"output_reserve={self._llm_output_reserve_tokens()} base={base_tokens} tools={tool_schema_tokens} "
            f"history={history_tokens} final_estimated={final_tokens}"
        )
        if run_id is not None:
            await self._emit_run_event(
                session_id,
                run_id,
                PROMPT_TOKENS_ESTIMATED_EVENT,
                {
                    "budget": effective_context_budget,
                    "history_budget": self.config.history_token_budget,
                    "model_window": self._llm_context_window_tokens(),
                    "output_reserve": self._llm_output_reserve_tokens(),
                    "base_tokens": base_tokens,
                    "tool_schema_tokens": tool_schema_tokens,
                    "history_tokens": history_tokens,
                    "final_estimated_tokens": final_tokens,
                },
                channel=channel,
                external_chat_id=external_chat_id,
            )
        self._sync_runtime_mcp_tools_context()
        if run_id is not None:
            tool_names = list(selected_tool_registry.tool_names) if selected_tool_registry is not None else []
            mcp_tool_names = list_mcp_tool_names(tool_names)
            await self._emit_run_event(
                session_id,
                run_id,
                MCP_TOOLS_SYNCED_EVENT,
                {"tool_names": mcp_tool_names, "tool_count": len(mcp_tool_names)},
                channel=channel,
                external_chat_id=external_chat_id,
            )
        full_messages = self._build_messages(
            history=history_dicts,
            current_message=prompt_message,
            current_images=None,
            channel=channel,
            session_id=session_id,
        )

        chat_messages = []
        for m in full_messages:
            msg = ChatMessage(role=m["role"], content=m.get("content", ""))
            if m.get("tool_call_id"):
                msg.tool_call_id = m["tool_call_id"]
            if m.get("tool_calls"):
                msg.tool_calls = m["tool_calls"]
            if m.get("reasoning_details"):
                msg.reasoning_details = m["reasoning_details"]
            chat_messages.append(msg)

        self._log_prepared_messages(session_id, full_messages)
        on_tool_before_execute = self._make_tool_progress_hook(
            channel=channel,
            external_chat_id=external_chat_id,
            session_id=session_id,
            run_id=run_id,
            enabled=emit_tool_progress,
        )
        on_tool_after_execute = self._make_tool_result_hook(
            channel=channel,
            external_chat_id=external_chat_id,
            session_id=session_id,
            run_id=run_id,
            enabled=emit_tool_progress,
        )
        on_llm_status = self._make_llm_status_hook(
            channel=channel,
            external_chat_id=external_chat_id,
            session_id=session_id,
            run_id=run_id,
            enabled=emit_tool_progress,
        )
        on_response_delta = self._make_llm_delta_hook(
            channel=channel,
            external_chat_id=external_chat_id,
            session_id=session_id,
            run_id=run_id,
            enabled=emit_tool_progress,
        )
        on_tool_input_delta = self._make_tool_input_delta_hook(
            channel=channel,
            external_chat_id=external_chat_id,
            session_id=session_id,
            run_id=run_id,
            enabled=emit_tool_progress,
        )
        reasoning_delta_count = 0

        reasoning_hook = self._make_reasoning_delta_hook(
            channel=channel,
            external_chat_id=external_chat_id,
            session_id=session_id,
            run_id=run_id,
            enabled=emit_tool_progress,
        )

        async def on_reasoning_delta(delta: str) -> None:
            nonlocal reasoning_delta_count
            reasoning_delta_count += 1
            if reasoning_hook is not None:
                await reasoning_hook(delta, reasoning_delta_count)

        execute_kwargs = {
            "allow_tools": allow_tools,
            "tool_result_session_id": session_id if allow_tools else None,
            "tool_registry": selected_tool_registry,
            "on_tool_before_execute": on_tool_before_execute,
            "on_llm_status": on_llm_status,
            "on_response_delta": on_response_delta,
            "on_tool_input_delta": on_tool_input_delta,
            "on_reasoning_delta": on_reasoning_delta if reasoning_hook is not None else None,
            "refresh_system_prompt": lambda: self._build_system_prompt(session_id),
            "should_cancel": lambda: self._should_cancel_run(session_id, run_id),
        }
        if on_tool_after_execute is not None:
            execute_kwargs["on_tool_after_execute"] = on_tool_after_execute
        return await self._execute_messages(session_id, chat_messages, **execute_kwargs)
