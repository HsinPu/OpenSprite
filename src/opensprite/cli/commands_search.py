"""Local conversation-history search command helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import typer

if TYPE_CHECKING:
    from ..config import Config
    from ..search.sqlite_store import SQLiteSearchStore


def load_sqlite_history_search_store(
    config: str | None,
    *,
    resolve_config_path: Callable[[str | None], Path],
) -> tuple[Config, SQLiteSearchStore]:
    """Open the configured history-search store without changing local state."""
    from ..config import Config
    from ..search.sqlite_store import SQLiteSearchStore

    config_path = resolve_config_path(config)
    if config_path.suffix != ".json":
        raise ValueError(f"config path must be a JSON file: {config_path}")

    loaded = Config.from_json(config_path)
    if not loaded.history_search.enabled:
        raise ValueError("history_search.enabled=false; enable history search first")
    if loaded.storage.type != "sqlite":
        raise ValueError('history_search requires storage.type="sqlite"')

    store = SQLiteSearchStore(
        path=loaded.storage.path,
        history_top_k=loaded.history_search.history_top_k,
        read_only=True,
    )
    return loaded, store


def search_status_command(
    *,
    config: str | None,
    session_id: str | None,
    load_history_search_store: Callable[[str | None], Any],
    handle_search_error: Callable[[Exception | str], None],
) -> None:
    """Print compact SQLite FTS index counts."""
    try:
        loaded, store = load_history_search_store(config)
        status = asyncio.run(store.get_status(session_id=session_id))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)
        return

    scope = session_id or "all sessions"
    typer.echo(f"Chat history search status for {scope}.")
    typer.echo("Backend: SQLite FTS5")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(f"Sessions: {status['session_count']}")
    typer.echo(f"Messages: {status['message_count']}")
    typer.echo(f"Chunks: {status['chunk_count']}")
