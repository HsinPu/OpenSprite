import asyncio
import unicodedata

import pytest

from opensprite.search.base import SearchHit
from opensprite.search.sqlite_store import (
    MAX_HISTORY_SEARCH_QUERY_LENGTH,
    MAX_HISTORY_SEARCH_QUERY_TOKENS,
)
from opensprite.tools.result_status import classify_tool_result_status
from opensprite.tools.search import SearchHistoryTool


class EmptySearchStore:
    async def search_history(self, session_id: str, query: str, limit: int = 5):
        return []


def test_search_history_limit_schema_is_bounded():
    tool = SearchHistoryTool(
        EmptySearchStore(),
        get_session_id=lambda: "chat-1",
        default_limit=5,
    )

    limit_schema = tool.parameters["properties"]["limit"]

    assert limit_schema["minimum"] == 1
    assert limit_schema["maximum"] == 20


def test_search_history_query_schema_has_a_length_limit():
    tool = SearchHistoryTool(
        EmptySearchStore(),
        get_session_id=lambda: "chat-1",
        default_limit=5,
    )

    query_schema = tool.parameters["properties"]["query"]

    assert query_schema["maxLength"] == MAX_HISTORY_SEARCH_QUERY_LENGTH


def test_search_history_rejects_too_many_unique_query_tokens():
    tool = SearchHistoryTool(
        EmptySearchStore(),
        get_session_id=lambda: "chat-1",
        default_limit=5,
    )
    query = " ".join(
        f"token{index}" for index in range(MAX_HISTORY_SEARCH_QUERY_TOKENS + 1)
    )

    result = asyncio.run(tool.execute(query=query))
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolValidationError"
    assert status.category == "invalid_query"
    assert status.invalid_arguments is True
    assert "too many unique tokens" in status.error


def test_search_history_rejects_an_overlong_query_from_the_schema():
    tool = SearchHistoryTool(
        EmptySearchStore(),
        get_session_id=lambda: "chat-1",
        default_limit=5,
    )

    result = asyncio.run(
        tool.execute(query="x" * (MAX_HISTORY_SEARCH_QUERY_LENGTH + 1))
    )
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolValidationError"
    assert status.invalid_arguments is True


def test_search_history_missing_session_returns_structured_error():
    tool = SearchHistoryTool(EmptySearchStore(), get_session_id=lambda: None, default_limit=5)

    result = asyncio.run(tool.execute(query="prior decision"))
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolValidationError"
    assert status.category == "session_unavailable"
    assert status.invalid_arguments is True
    assert "session_id is unavailable" in status.error


def test_search_history_uses_current_session_id():
    calls = []

    class Store:
        async def search_history(self, session_id: str, query: str, limit: int = 5):
            calls.append((session_id, query, limit))
            return []

    tool = SearchHistoryTool(Store(), get_session_id=lambda: "chat-1", default_limit=5)

    result = asyncio.run(tool.execute(query="prior decision", limit=2))

    assert calls == [("chat-1", "prior decision", 2)]
    assert result == "No history matches found for 'prior decision' in this session."


def test_search_history_result_keeps_a_late_match_visible():
    class Store:
        async def search_history(self, session_id: str, query: str, limit: int = 5):
            return [
                SearchHit(
                    id="chunk-1",
                    session_id=session_id,
                    content=f"{'a' * 300} needle {'b' * 100}",
                    created_at=10.0,
                    role="user",
                )
            ]

    tool = SearchHistoryTool(Store(), get_session_id=lambda: "chat-1", default_limit=5)

    result = asyncio.run(tool.execute(query="needle"))

    assert "needle" in result
    assert "..." in result


@pytest.mark.parametrize(
    ("matched_text", "query"),
    [
        ("Stra\u00dfe", "STRASSE"),
        (unicodedata.normalize("NFD", "Caf\u00e9"), "Caf\u00e9"),
        ("Caf\u00e9", unicodedata.normalize("NFD", "Caf\u00e9")),
    ],
)
def test_search_history_result_keeps_a_late_unicode_match_visible(
    matched_text: str,
    query: str,
):
    class Store:
        async def search_history(self, session_id: str, query: str, limit: int = 5):
            return [
                SearchHit(
                    id="chunk-1",
                    session_id=session_id,
                    content=f"{'a' * 300} {matched_text} {'b' * 100}",
                    created_at=10.0,
                    role="user",
                )
            ]

    tool = SearchHistoryTool(Store(), get_session_id=lambda: "chat-1", default_limit=5)

    result = asyncio.run(tool.execute(query=query))

    assert matched_text in result
    assert "..." in result


def test_search_history_result_prefers_semantic_literal_in_multiword_query():
    class Store:
        async def search_history(self, session_id: str, query: str, limit: int = 5):
            return [
                SearchHit(
                    id="chunk-1",
                    session_id=session_id,
                    content=(
                        f"C is unrelated {'a' * 300} "
                        "C++ advanced templates are documented here"
                    ),
                    created_at=10.0,
                    role="user",
                )
            ]

    tool = SearchHistoryTool(Store(), get_session_id=lambda: "chat-1", default_limit=5)

    result = asyncio.run(tool.execute(query="C++ templates"))

    assert "C++" in result
    assert "templates" in result


def test_search_history_result_skips_earlier_token_substring():
    class Store:
        async def search_history(self, session_id: str, query: str, limit: int = 5):
            return [
                SearchHit(
                    id="chunk-1",
                    session_id=session_id,
                    content=(
                        f"metatemplates are unrelated {'a' * 300} "
                        "standalone templates are documented here"
                    ),
                    created_at=10.0,
                    role="user",
                )
            ]

    tool = SearchHistoryTool(Store(), get_session_id=lambda: "chat-1", default_limit=5)

    result = asyncio.run(tool.execute(query="templates"))

    assert "standalone templates" in result
