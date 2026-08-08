"""User-profile consolidation policy and incremental update service."""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol

from ...config.schema import DocumentLlmConfig
from ...core.contracts.persistence import StoredMessage
from ...core.ports.storage import StorageProvider
from opensprite.core.logging import logger
from .prompts import curator_shared_rules as _curator_shared_rules


class _UserProfileStore(Protocol):
    def read_response_language_block(self) -> str: ...

    def write_response_language_block(self, content: str) -> None: ...

    def read_managed_block(self) -> str: ...

    def write_managed_block(self, content: str) -> None: ...

    def get_processed_index(self, session_id: str) -> int: ...

    def set_processed_index(self, session_id: str, index: int) -> None: ...


_SAVE_USER_PROFILE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_user_profile",
            "description": (
                "Update auto-managed USER.md blocks: the profile block (required) and optionally "
                "the Response language block."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_update": {
                        "type": "string",
                        "description": (
                            "Replacement markdown for the auto-managed USER.md profile block "
                            "(under the Auto-managed Profile markers). "
                            "Keep it concise, stable, and free of secrets."
                        ),
                    },
                    "response_language_update": {
                        "type": "string",
                        "description": (
                            "Replacement markdown for the auto-managed Response language block only "
                            "(typically one bullet line, e.g. '- Traditional Chinese (Taiwan)' or '- not set'). "
                            "Omit this field entirely if that block should stay unchanged."
                        ),
                    },
                },
                "required": ["profile_update"],
            },
        },
    }
]


def _format_messages(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role", "?")).upper()
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


async def consolidate_user_profile(
    profile_store: _UserProfileStore,
    messages: list[dict[str, Any]],
    provider,
    model: str,
    *,
    profile_llm: DocumentLlmConfig,
) -> bool:
    """Update this session's USER.md managed blocks from conversation history."""
    if not messages:
        return True

    current_profile = profile_store.read_managed_block()
    current_response_language = profile_store.read_response_language_block()
    transcript = _format_messages(messages)
    if not transcript:
        return True

    prompt = f"""Review this conversation and update this session's USER.md user context.

Current auto-managed Response language block:
{current_response_language or '(empty)'}

Current auto-managed USER.md user-context block:
{current_profile or '(empty)'}

Conversation to analyze:
{transcript}

{_curator_shared_rules("USER.md")}

Rules:
- Return the full replacement content for the managed user-context block using exactly these sections and order: `### Communication Preferences`, `### Work Context`, `### Stable Constraints`.
- Capture only durable, user-focused context that helps future turns in this same session.
- Put communication style, formatting, and collaboration preferences under Communication Preferences.
- Put recurring user work background or long-lived user context under Work Context.
- Put durable constraints that should shape future assistance under Stable Constraints.
- Use one concise markdown bullet per item. If a section has no learned items, keep its default `- No learned ... yet.` bullet.
- Update the Response language block only when the user explicitly states a durable assistant language preference. Do not infer a permanent language preference from the language used in a single message. Use `- not set` when response language should follow the user's current message.
- Do not store secrets, API keys, access tokens, passwords, or private file contents.
- Do not store one-off tasks, task progress, project decisions, temporary requests, raw logs, or details that belong in MEMORY.md.
- Prefer explicit facts and durable preferences over guesses. When uncertain, leave the block unchanged.
- Write the user-context block in clear, concise English unless the user explicitly prefers another language for saved profile content.
- If nothing meaningful changed in a block, return that block unchanged.
"""

    llm = profile_llm
    try:
        response = await provider.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You maintain one session's USER.md for an assistant: the Response language block "
                        "and the Auto-managed User Context block. "
                        "Call save_user_profile with profile_update (required) and, when needed, "
                        "response_language_update for the Response language section only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            tools=_SAVE_USER_PROFILE_TOOL,
            model=model,
            **llm.request_kwargs(),
        )

        if not response.tool_calls:
            logger.warning("User profile consolidation: LLM did not call save_user_profile")
            return False

        args = response.tool_calls[0].arguments
        if isinstance(args, str):
            args = json.loads(args)

        update = str(args.get("profile_update", "")).strip()
        if not update:
            logger.warning("User profile consolidation: empty profile_update payload")
            return False

        if update != current_profile:
            profile_store.write_managed_block(update)
            logger.info("USER.md profile updated ({} chars)", len(update))

        lang_raw = args.get("response_language_update", None)
        if lang_raw is not None:
            lang_stripped = str(lang_raw).strip()
            if lang_stripped and lang_stripped != current_response_language:
                profile_store.write_response_language_block(lang_stripped)
                logger.info("USER.md response language updated ({} chars)", len(lang_stripped))

        return True
    except Exception as exc:
        logger.error("User profile consolidation failed: {}", exc)
        return False


class UserProfileConsolidator:
    """Manage incremental USER.md updates from stored session history."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        provider,
        model: str,
        profile_store_factory: Callable[[str], _UserProfileStore],
        threshold: int,
        lookback_messages: int,
        enabled: bool,
        llm: DocumentLlmConfig,
    ):
        self.storage = storage
        self.provider = provider
        self.model = model
        self.profile_store_factory = profile_store_factory
        self.threshold = max(1, threshold)
        self.lookback_messages = max(1, lookback_messages)
        self.enabled = enabled
        self.llm = llm

    @staticmethod
    def _to_message_dict(message: StoredMessage) -> dict[str, Any]:
        return {
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp,
            "metadata": dict(message.metadata or {}),
        }

    async def maybe_update(self, session_id: str) -> None:
        if not self.enabled:
            return

        profile_store = self.profile_store_factory(session_id)
        message_count = await self.storage.get_message_count(session_id)
        last_processed = profile_store.get_processed_index(session_id)
        if last_processed > message_count:
            profile_store.set_processed_index(session_id, message_count)
            return

        pending = message_count - last_processed
        if pending < self.threshold:
            return

        end_index = min(message_count, last_processed + self.lookback_messages)
        chunk = await self.storage.get_messages_slice(
            session_id,
            start_index=last_processed,
            end_index=end_index,
        )
        if not chunk:
            return

        logger.info("[{}] Updating USER.md profile from {} messages", session_id, len(chunk))
        success = await consolidate_user_profile(
            profile_store=profile_store,
            messages=[self._to_message_dict(message) for message in chunk],
            provider=self.provider,
            model=self.model,
            profile_llm=self.llm,
        )
        if success:
            profile_store.set_processed_index(session_id, end_index)


class _UserProfileConsolidator(Protocol):
    async def maybe_update(self, session_id: str) -> None: ...


class UserProfileUpdateService:
    """Wrap optional USER.md profile updates behind a stable interface."""

    def __init__(self, consolidator: _UserProfileConsolidator | None = None):
        self.consolidator = consolidator

    async def maybe_update(self, session_id: str) -> None:
        """Refresh this session's USER.md managed block when enough new history exists."""
        if self.consolidator is None:
            return

        try:
            await self.consolidator.maybe_update(session_id)
        except Exception as exc:
            logger.error(f"[{session_id}] profile.update.error | error={exc}")
