"""Local conversation-history search command helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

import typer


def load_sqlite_history_search_store(
    config: str | None,
    *,
    resolve_config_path: Callable[[str | None], Path],
):
    """Load the configured SQLite history-search store."""
    from ..config import Config
    from ..search.sqlite_store import SQLiteSearchStore
    from ..search.store_factory import create_history_search_store

    loaded = Config.load(resolve_config_path(config))
    store = create_history_search_store(loaded)
    if store is None:
        raise ValueError("history_search.enabled=false; enable history search first")
    if not isinstance(store, SQLiteSearchStore):
        raise ValueError("configured history search backend does not support status inspection")
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

    scope = session_id or "all sessions"
    typer.echo(f"Chat history search status for {scope}.")
    typer.echo("Backend: SQLite FTS5")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(f"Sessions: {status['session_count']}")
    typer.echo(f"Messages: {status['message_count']}")
    typer.echo(f"Chunks: {status['chunk_count']}")
