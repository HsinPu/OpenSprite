import asyncio
import json

from typer.testing import CliRunner

from opensprite.cli.commands import app
from opensprite.search.sqlite_store import SQLiteSearchStore
from opensprite.storage.base import StoredMessage
from opensprite.storage.sqlite import SQLiteStorage


runner = CliRunner()


def _write_config(path, db_path, *, enabled=True, history_top_k=5):
    path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "key",
                    "model": "gpt",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "storage": {"type": "sqlite", "path": str(db_path)},
                "channels": {
                    "instances": {
                        "telegram": {"type": "telegram", "enabled": False},
                        "web": {"type": "web", "enabled": True},
                    }
                },
                "history_search": {
                    "enabled": enabled,
                    "backend": "sqlite",
                    "history_top_k": history_top_k,
                },
            }
        ),
        encoding="utf-8",
    )


def test_status_command_renders_history_search_values(tmp_path):
    db_path = tmp_path / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path, history_top_k=7)

    result = runner.invoke(app, ["status", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "History search: enabled=yes backend=sqlite (history_top_k=7)" in result.stdout


def test_search_status_cli_reports_plain_fts_counts(tmp_path):
    db_path = tmp_path / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path)

    async def scenario():
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await storage.add_message(
            "chat-a",
            StoredMessage(role="user", content="Please keep sqlite docs handy", timestamp=10.0),
        )
        await search.index_message(
            "chat-a",
            role="user",
            content="Please keep sqlite docs handy",
            created_at=10.0,
        )

    asyncio.run(scenario())
    result = runner.invoke(app, ["search", "status", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Chat history search status for all sessions." in result.stdout
    assert "Backend: SQLite FTS5" in result.stdout
    assert "Messages: 1" in result.stdout
    assert "Chunks: 1" in result.stdout
    assert "Embedding" not in result.stdout
    assert "Queue worker" not in result.stdout


def test_search_help_only_exposes_status_command():
    result = runner.invoke(app, ["search", "--help"])

    assert result.exit_code == 0
    assert "status" in result.stdout
    assert "rebuild" not in result.stdout
