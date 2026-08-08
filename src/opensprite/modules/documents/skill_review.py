"""Background skill-review use case."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from ...core.contracts.tool_names import CONFIGURE_SKILL_TOOL_NAME, SKILL_REVIEW_TOOL_NAMES
from ...core.ports.storage import StorageProvider
from ...core.contracts.llm import ChatMessage
from opensprite.core.logging import logger
from .skill_review_prompts import (
    SKILL_REVIEW_SYSTEM as _SKILL_REVIEW_SYSTEM,
    SKILL_REVIEW_TRANSCRIPT_TOO_SHORT_REASON as _SKILL_REVIEW_TRANSCRIPT_TOO_SHORT_REASON,
    build_skill_review_user_content as _build_skill_review_user_content,
    format_stored_messages_for_transcript as _format_stored_messages_for_transcript,
)


class _SkillToolRegistry(Protocol):
    """Minimal tool-registry surface required by skill review."""

    @property
    def tool_names(self) -> list[str]: ...

    def filtered(self, *, exclude_names: set[str]) -> "_SkillToolRegistry": ...


class SkillReviewService:
    """Run the background skill persistence review pass."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        tools: _SkillToolRegistry,
        tool_result_succeeded: Callable[[str], bool],
        transcript_message_limit_getter: Callable[[], int],
        max_tool_iterations_getter: Callable[[], int],
        build_system_prompt: Callable[[str], str],
        execute_messages: Callable[..., Awaitable[Any]],
    ):
        self.storage = storage
        self.tools = tools
        self._tool_result_succeeded = tool_result_succeeded
        self._transcript_message_limit_getter = transcript_message_limit_getter
        self._max_tool_iterations_getter = max_tool_iterations_getter
        self._build_system_prompt = build_system_prompt
        self._execute_messages = execute_messages

    def tool_registry(self) -> _SkillToolRegistry | None:
        """Return the restricted tool registry allowed during background skill review."""
        allowed = SKILL_REVIEW_TOOL_NAMES
        available = set(self.tools.tool_names)
        if not allowed.issubset(available):
            return None
        excluded = available - allowed
        return self.tools.filtered(exclude_names=excluded)

    async def run(self, session_id: str, *, tool_registry: _SkillToolRegistry) -> list[dict[str, str]]:
        """Execute one review pass for a session using the restricted skill tool registry."""
        stored = await self.storage.get_messages(session_id, limit=self._transcript_message_limit_getter())
        transcript = _format_stored_messages_for_transcript(stored)
        if len(transcript) < 80:
            logger.info(
                "[%s] skill.review.skip | reason=%s",
                session_id,
                _SKILL_REVIEW_TRANSCRIPT_TOO_SHORT_REASON,
            )
            return []

        user_content = _build_skill_review_user_content(transcript)
        chat_messages = [
            ChatMessage(role="system", content=_SKILL_REVIEW_SYSTEM),
            ChatMessage(role="user", content=user_content),
        ]
        touched_skills: list[dict[str, str]] = []

        async def on_tool_after_execute(tool_name: str, tool_args: dict[str, Any], result: str, *args: Any) -> None:
            if tool_name != CONFIGURE_SKILL_TOOL_NAME:
                return
            action = str((tool_args or {}).get("action") or "").strip()
            if action not in {"add", "upsert"}:
                return
            if not self._tool_result_succeeded(result):
                return
            skill_name = str((tool_args or {}).get("skill_name") or "").strip()
            if not skill_name:
                return
            touched_skills.append(
                {
                    "skill_name": skill_name,
                    "action": action,
                    "description": str((tool_args or {}).get("description") or "").strip(),
                }
            )

        await self._execute_messages(
            f"{session_id}:skill-review",
            chat_messages,
            allow_tools=True,
            tool_result_session_id=None,
            tool_registry=tool_registry,
            on_tool_before_execute=None,
            on_tool_after_execute=on_tool_after_execute,
            refresh_system_prompt=lambda: self._build_system_prompt(session_id),
            max_tool_iterations=self._max_tool_iterations_getter(),
        )
        logger.info("[%s] skill.review.done", session_id)
        return touched_skills
