import asyncio
import sqlite3

from opensprite.search.sqlite_store import MAX_HISTORY_SEARCH_RESULTS, SQLiteSearchStore
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
