"""Search tools for session history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from opensprite.core.contracts.search import SearchHit
from opensprite.core.contracts.tool_results import tool_error_result
from opensprite.core.ports.search import SearchStore
from opensprite.modules.search import query_policy
from opensprite.modules.tools.base import Tool
from opensprite.modules.tools.validation import NON_EMPTY_STRING_PATTERN


def _truncate(text: str, limit: int = 240) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit - 3]}..."


def _source_index_for_folded_offset(text: str, folded_offset: int) -> int:
    """Map an NFC/casefolded offset back to its source character index."""
    for source_end in range(1, len(text) + 1):
        if len(query_policy.unicode_casefold(text[:source_end])) > folded_offset:
            return source_end - 1
    return len(text)


def _truncate_around_query(text: str, query: str, limit: int = 240) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized

    folded_text = query_policy.unicode_casefold(normalized)
    literals, tokens = query_policy.parse_history_search_terms(query)
    match_start = -1
    for literal in literals:
        folded_literal = query_policy.unicode_casefold(literal)
        match_start = folded_text.find(folded_literal)
        if match_start >= 0:
            break
    if match_start < 0:
        for token in tokens:
            token_offset = query_policy.find_history_search_token_offset(
                normalized,
                token,
            )
            if token_offset is not None:
                match_start = token_offset
                break
    if match_start < 0:
        return _truncate(normalized, limit)

    content_budget = max(1, limit - 6)
    source_match_start = _source_index_for_folded_offset(normalized, match_start)
    start = max(0, source_match_start - content_budget // 2)
    end = min(len(normalized), start + content_budget)
    if end - start < content_budget:
        start = max(0, end - content_budget)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end]}{suffix}"


def _format_time(created_at: float) -> str:
    if not created_at:
        return "unknown"
    return datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")


class SearchHistoryTool(Tool):
    def __init__(self, store: SearchStore, get_session_id: Callable[[], str | None], default_limit: int):
        self.store = store
        self.get_session_id = get_session_id
        self.default_limit = default_limit

    def _current_session_id(self) -> str | None:
        return self.get_session_id()

    def _missing_chat_response(self) -> str:
        error = "current session_id is unavailable. Search tools require a session-scoped conversation."
        return tool_error_result(
            error,
            error_type="ToolValidationError",
            category="session_unavailable",
            repeated_error_key=error,
            invalid_arguments=True,
            metadata={"tool_name": self.name},
        )

    @property
    def name(self) -> str:
        return "search_history"

    @property
    def description(self) -> str:
        return (
            "Search saved conversation history for the current session only. Prefer this before asking the user "
            "to restate earlier chat details, and use it for prior decisions, commands, errors, task outcomes, "
            "or transcript-specific facts that should not be copied into MEMORY.md."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to search for in this session history; limited to "
                        f"{query_policy.MAX_HISTORY_SEARCH_QUERY_TOKENS} unique word tokens"
                    ),
                    "pattern": NON_EMPTY_STRING_PATTERN,
                    "maxLength": query_policy.MAX_HISTORY_SEARCH_QUERY_LENGTH,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum matches to return",
                    "default": self.default_limit,
                    "minimum": 1,
                    "maximum": query_policy.MAX_HISTORY_SEARCH_RESULTS,
                },
            },
            "required": ["query"],
        }

    async def _execute(self, query: str, limit: int | None = None, **kwargs: Any) -> str:
        try:
            query = query_policy.validate_history_search_query(query)
        except ValueError as exc:
            error = str(exc)
            return tool_error_result(
                error,
                error_type="ToolValidationError",
                category="invalid_query",
                repeated_error_key=error,
                invalid_arguments=True,
                metadata={"tool_name": self.name},
            )

        session_id = self._current_session_id()
        if not session_id:
            return self._missing_chat_response()

        requested_limit = self.default_limit if limit is None else limit
        hits = await self.store.search_history(
            session_id=session_id,
            query=query,
            limit=requested_limit,
        )
        if not hits:
            return f"No history matches found for '{query}' in this session."

        return self._format_hits(query, hits)

    def _format_hits(self, query: str, hits: list[SearchHit]) -> str:
        lines = [f"History matches for: {query}"]
        for index, hit in enumerate(hits, 1):
            label = hit.role or "message"
            if hit.tool_name:
                label = f"{label}:{hit.tool_name}"
            lines.append(f"{index}. [{label}] {_format_time(hit.created_at)}")
            lines.append(f"   {_truncate_around_query(hit.content, query)}")
        return "\n".join(lines)
