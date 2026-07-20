import asyncio
import sqlite3

import pytest

from opensprite.search.sqlite_store import (
    MAX_HISTORY_SEARCH_QUERY_LENGTH,
    MAX_HISTORY_SEARCH_QUERY_TOKENS,
    MAX_HISTORY_SEARCH_RESULTS,
    SQLiteSearchStore,
)
from opensprite.storage.base import StoredMessage
from opensprite.storage.sqlite import SQLiteStorage


async def _persist_and_index(
    storage: SQLiteStorage,
    search: SQLiteSearchStore,
    session_id: str,
    content: str,
    *,
    timestamp: float,
    role: str = "user",
    tool_name: str | None = None,
) -> None:
    await storage.add_message(
        session_id,
        StoredMessage(
            role=role,
            content=content,
            timestamp=timestamp,
            tool_name=tool_name,
        ),
    )
    await search.index_message(
        session_id,
        role=role,
        content=content,
        tool_name=tool_name,
        created_at=timestamp,
    )


def test_sqlite_search_store_indexes_only_the_current_session(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Please keep sqlite fts docs handy",
            timestamp=10.0,
        )
        await _persist_and_index(
            storage,
            search,
            "chat-b",
            "Need postgres docs",
            timestamp=11.0,
        )

        hits = await search.search_history("chat-a", "sqlite docs")
        other_hits = await search.search_history("chat-b", "sqlite docs")
        await search.clear_session("chat-a")
        cleared_hits = await search.search_history("chat-a", "sqlite docs")
        persisted = await storage.get_messages("chat-a")
        return hits, other_hits, cleared_hits, persisted

    hits, other_hits, cleared_hits, persisted = asyncio.run(scenario())

    assert len(hits) == 1
    assert hits[0].session_id == "chat-a"
    assert "sqlite fts docs" in hits[0].content.lower()
    assert other_hits == []
    assert cleared_hits == []
    assert [message.content for message in persisted] == ["Please keep sqlite fts docs handy"]


def test_sync_backfills_messages_and_skips_search_history_output(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        await storage.add_message(
            "chat-a",
            StoredMessage(role="user", content="Remember the blue deployment", timestamp=10.0),
        )
        await storage.add_message(
            "chat-a",
            StoredMessage(
                role="tool",
                content="History matches for: blue deployment",
                timestamp=11.0,
                tool_name="search_history",
            ),
        )

        search = SQLiteSearchStore(db_path)
        await search.sync_from_storage()
        hits = await search.search_history("chat-a", "blue deployment")
        status = await search.get_status("chat-a")
        return hits, status

    hits, status = asyncio.run(scenario())

    assert [hit.role for hit in hits] == ["user"]
    assert status == {"session_count": 1, "message_count": 1, "chunk_count": 1}


def test_fts_zero_results_fall_back_to_chinese_substring_matching(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "我們最後決定把後端搜尋整理成簡單流程",
            timestamp=10.0,
        )
        return await search.search_history("chat-a", "搜尋整理")

    hits = asyncio.run(scenario())

    assert len(hits) == 1
    assert "搜尋整理" in hits[0].content


@pytest.mark.parametrize(
    ("query", "content", "expected_match"),
    [
        ("版本1", "版本10已部署", False),
        ("模型A", "模型AB已部署", False),
        ("版本1", "版本說明1", False),
        ("1版本", "1說明版本", False),
        ("A模型B", "A超級模型B", False),
        ("版本1", "新版本1", True),
        ("1版本", "1版本更新", True),
    ],
)
def test_mixed_cjk_tokens_preserve_latin_and_number_boundaries(
    tmp_path,
    query,
    content,
    expected_match,
):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            content,
            timestamp=10.0,
        )
        return await search.search_history("chat-a", query)

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == ([content] if expected_match else [])


def test_casefolded_latin_token_matches_between_cjk_spans(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        content = "版本Straße已更新"
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            content,
            timestamp=10.0,
        )
        return content, await search.search_history("chat-a", "STRASSE")

    content, hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [content]


def test_result_limit_is_bounded_between_one_and_twenty(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        for index in range(25):
            await _persist_and_index(
                storage,
                search,
                "chat-a",
                f"shared-keyword message {index}",
                timestamp=float(index + 1),
            )
        upper = await search.search_history("chat-a", "shared keyword", limit=999)
        lower = await search.search_history("chat-a", "shared keyword", limit=0)
        return upper, lower

    upper, lower = asyncio.run(scenario())

    assert len(upper) == MAX_HISTORY_SEARCH_RESULTS
    assert len(lower) == 1


def test_reindexing_a_message_does_not_duplicate_chunks(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "single indexed message",
            timestamp=10.0,
        )
        await search.index_message(
            "chat-a",
            role="user",
            content="single indexed message",
            created_at=10.0,
        )
        return await search.get_status("chat-a")

    assert asyncio.run(scenario())["chunk_count"] == 1


def test_search_returns_only_the_best_chunk_per_message(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path, chunk_size=40, chunk_overlap=15)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            f"{'a' * 26} needle {'b' * 50}",
            timestamp=10.0,
        )
        return await search.search_history("chat-a", "needle", limit=20)

    hits = asyncio.run(scenario())

    assert len(hits) == 1
    assert "needle" in hits[0].content


@pytest.mark.parametrize(
    ("query", "matching_content"),
    [
        ("C++", "Use C++ templates for this implementation"),
        ("C#", "Use C# records for this implementation"),
        ("C++?", "Use C++ templates for this implementation"),
        ('"C#"', "Use C# records for this implementation"),
    ],
)
def test_punctuation_heavy_queries_require_a_literal_match(
    tmp_path,
    query,
    matching_content,
):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Only the letter C appears in this message",
            timestamp=10.0,
        )
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            matching_content,
            timestamp=11.0,
        )
        return await search.search_history("chat-a", query)

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [matching_content]


def test_multiword_literal_query_does_not_degrade_to_plain_token(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Use C templates for this implementation",
            timestamp=20.0,
        )
        matching_content = "Use C++ templates for this implementation"
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            matching_content,
            timestamp=10.0,
        )
        return matching_content, await search.search_history(
            "chat-a",
            "C++ templates",
        )

    matching_content, hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [matching_content]


@pytest.mark.parametrize(
    ("query", "plain_content", "matching_content"),
    [
        (
            "C++17 migration",
            "Plan the C 17 migration",
            "Plan the C++17 migration",
        ),
        (
            "C#12 migration",
            "Plan the C 12 migration",
            "Plan the C#12 migration",
        ),
    ],
)
def test_versioned_literal_identifier_does_not_degrade_to_plain_tokens(
    tmp_path,
    query,
    plain_content,
    matching_content,
):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            plain_content,
            timestamp=20.0,
        )
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            matching_content,
            timestamp=10.0,
        )
        return await search.search_history("chat-a", query)

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [matching_content]


def test_multiword_query_requires_each_literal_identifier(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        for timestamp, content in enumerate(
            (
                "Only C++ templates are discussed here",
                "Only C# records are discussed here",
                "C++ and C# interop is discussed here",
            ),
            start=10,
        ):
            await _persist_and_index(
                storage,
                search,
                "chat-a",
                content,
                timestamp=float(timestamp),
            )
        return await search.search_history("chat-a", "C++ C#")

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == ["C++ and C# interop is discussed here"]


def test_literal_only_query_returns_phrase_and_non_phrase_matches(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        contents = (
            "C++ C# direct comparison",
            "C++ and C# interop notes",
        )
        for timestamp, content in enumerate(contents, start=10):
            await _persist_and_index(
                storage,
                search,
                "chat-a",
                content,
                timestamp=float(timestamp),
            )
        return contents, await search.search_history("chat-a", "C++ C#")

    contents, hits = asyncio.run(scenario())

    assert {hit.content for hit in hits} == set(contents)


def test_multiword_literal_query_preserves_word_boundaries(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "C++ metatemplates are mentioned",
            timestamp=10.0,
        )
        return await search.search_history("chat-a", "C++ templates")

    hits = asyncio.run(scenario())

    assert hits == []


def test_multiword_query_punctuation_remains_a_search_separator(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Alpha and beta are both present",
            timestamp=10.0,
        )
        return await search.search_history("chat-a", "alpha, beta")

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == ["Alpha and beta are both present"]


@pytest.mark.parametrize(
    ("query", "matching_content"),
    [
        ("sqlite?", "SQLite powers local history search"),
        ('"hello"', "Hello from OpenSprite"),
    ],
)
def test_common_punctuation_falls_back_to_fts_tokens(
    tmp_path,
    query,
    matching_content,
):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            matching_content,
            timestamp=10.0,
        )
        return await search.search_history("chat-a", query)

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [matching_content]


def test_unicode61_query_tokens_preserve_sharp_s(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Die Straße bleibt geöffnet",
            timestamp=10.0,
        )
        return await search.search_history("chat-a", "Straße")

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == ["Die Straße bleibt geöffnet"]


def test_fts_and_unicode_substring_results_are_merged_stably(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        unicode_content = "Die Straße bleibt geöffnet"
        ascii_content = "The ASCII STRASSE spelling is also recorded"
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            unicode_content,
            timestamp=20.0,
        )
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            ascii_content,
            timestamp=10.0,
        )
        full = await search.search_history("chat-a", "STRASSE", limit=2)
        limited = await search.search_history("chat-a", "STRASSE", limit=1)
        return unicode_content, ascii_content, full, limited

    unicode_content, ascii_content, full, limited = asyncio.run(scenario())

    assert [hit.content for hit in full] == [ascii_content, unicode_content]
    assert [hit.content for hit in limited] == [ascii_content]
    assert len({hit.id for hit in full}) == 2


def test_unicode_literal_identifier_matching_is_case_insensitive(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Plain CAFÉ appears without a suffix",
            timestamp=10.0,
        )
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Use CAFÉ++ for this implementation",
            timestamp=11.0,
        )
        return await search.search_history("chat-a", "café++")

    hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == ["Use CAFÉ++ for this implementation"]


def test_unicode_literal_normalizes_nfd_content_before_matching(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        nfd_content = "Use CAFE\u0301++ for this implementation"
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            nfd_content,
            timestamp=10.0,
        )
        return nfd_content, await search.search_history("chat-a", "café++")

    nfd_content, hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [nfd_content]


def test_unicode_literal_normalizes_nfd_query_before_matching(tmp_path):
    async def scenario():
        db_path = tmp_path / "history.db"
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            "Plain CAFE appears without a suffix",
            timestamp=10.0,
        )
        matching_content = "Use CAFÉ++ for this implementation"
        await _persist_and_index(
            storage,
            search,
            "chat-a",
            matching_content,
            timestamp=11.0,
        )
        nfd_query = "cafe\u0301++"
        return matching_content, await search.search_history("chat-a", nfd_query)

    matching_content, hits = asyncio.run(scenario())

    assert [hit.content for hit in hits] == [matching_content]


def test_query_tokens_are_unicode_lowered_and_deduplicated():
    assert SQLiteSearchStore._query_tokens("Alpha alpha BETA alpha") == [
        "alpha",
        "beta",
    ]
    assert SQLiteSearchStore._query_tokens("Straße") == ["straße"]


def test_search_rejects_an_overlong_query_before_sqlite(tmp_path):
    search = SQLiteSearchStore(tmp_path / "history.db")
    query = "x" * (MAX_HISTORY_SEARCH_QUERY_LENGTH + 1)

    with pytest.raises(ValueError, match="must be at most"):
        asyncio.run(search.search_history("chat-a", query))


def test_search_rejects_too_many_unique_tokens_before_sqlite(tmp_path):
    search = SQLiteSearchStore(tmp_path / "history.db")
    query = " ".join(
        f"token{index}" for index in range(MAX_HISTORY_SEARCH_QUERY_TOKENS + 1)
    )
    assert len(query) <= MAX_HISTORY_SEARCH_QUERY_LENGTH

    with pytest.raises(ValueError, match="too many unique tokens"):
        asyncio.run(search.search_history("chat-a", query))


def test_schema_contains_expected_local_history_columns(tmp_path):
    db_path = tmp_path / "history.db"
    SQLiteStorage(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(search_chunks)")]
    finally:
        conn.close()

    assert columns == [
        "id",
        "session_id",
        "message_id",
        "role",
        "tool_name",
        "chunk_index",
        "content",
        "created_at",
    ]
