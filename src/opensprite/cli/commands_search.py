"""Search and benchmark command helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import statistics
import time
from typing import Any, Callable

import typer

from ..search.base import SearchHit
from ..storage.base import StoredMessage


def format_search_timestamp(value: float | None) -> str:
    """Render an optional unix timestamp for search status output."""
    if not value:
        return "never"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def render_benchmark_hits(hits, *, limit: int) -> list[str]:
    """Render a compact benchmark preview for the top hits."""
    lines: list[str] = []
    for index, hit in enumerate(hits[:limit], start=1):
        title = hit.title or hit.source_type
        score = f" score={hit.score:.4f}" if hit.score is not None else ""
        lines.append(f"{index}. [{hit.source_type}] {title}{score}")
        if hit.url:
            lines.append(f"   {hit.url}")
    return lines


def serialize_benchmark_hits(hits, *, limit: int) -> list[dict[str, object]]:
    """Convert benchmark hits into a compact JSON-friendly structure."""
    payload: list[dict[str, object]] = []
    for hit in hits[:limit]:
        payload.append(
            {
                "id": hit.id,
                "source_type": hit.source_type,
                "title": hit.title,
                "url": hit.url,
                "score": hit.score,
                "content": hit.content,
            }
        )
    return payload


def summarize_benchmark_runs(elapsed_runs: list[float]) -> dict[str, float]:
    """Summarize repeated benchmark timings."""
    if not elapsed_runs:
        return {"runs": 0.0, "avg_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "median_ms": 0.0}
    return {
        "runs": float(len(elapsed_runs)),
        "avg_ms": float(statistics.mean(elapsed_runs)),
        "min_ms": float(min(elapsed_runs)),
        "max_ms": float(max(elapsed_runs)),
        "median_ms": float(statistics.median(elapsed_runs)),
    }


def benchmark_hit_identity(hit: SearchHit) -> str:
    """Build a stable identity for comparing benchmark result overlap."""
    if hit.url:
        return f"url:{hit.url}"
    title = hit.title or hit.source_type or hit.id
    return f"title:{title}|source:{hit.source_type}"


def compare_benchmark_results(results: list[dict[str, object]]) -> dict[str, object]:
    """Compare benchmark outputs pairwise by overlap and top-hit agreement."""
    if len(results) < 2:
        return {}

    comparisons = []
    for index in range(len(results) - 1):
        first = results[index]
        second = results[index + 1]
        first_hits = first.get("_raw_hits", [])
        second_hits = second.get("_raw_hits", [])
        first_keys = {benchmark_hit_identity(hit) for hit in first_hits}
        second_keys = {benchmark_hit_identity(hit) for hit in second_hits}
        overlap = first_keys & second_keys
        union = first_keys | second_keys
        first_top = benchmark_hit_identity(first_hits[0]) if first_hits else None
        second_top = benchmark_hit_identity(second_hits[0]) if second_hits else None

        comparisons.append(
            {
                "strategies": [first.get("strategy"), second.get("strategy")],
                "overlap_count": len(overlap),
                "overlap_ratio": (len(overlap) / len(union)) if union else 1.0,
                "top_hit_same": bool(first_top and second_top and first_top == second_top),
                "first_only_count": len(first_keys - second_keys),
                "second_only_count": len(second_keys - first_keys),
                "first_top": first_top,
                "second_top": second_top,
            }
        )

    return {"pairs": comparisons}


def load_sqlite_search_store(config: str | None, *, resolve_config_path: Callable[[str | None], Path]):
    """Load the configured SQLite search store or fail with a clear message."""
    from ..config import Config
    from ..runtime import create_search_store
    from ..search.sqlite_store import SQLiteSearchStore

    loaded = Config.load(resolve_config_path(config))
    search_store = create_search_store(loaded)
    if search_store is None:
        raise ValueError("search.enabled=false; enable search first")
    if not isinstance(search_store, SQLiteSearchStore):
        raise ValueError("configured search backend does not support rebuild")
    return loaded, search_store


def build_sqlite_search_store(
    loaded,
    *,
    candidate_strategy: str | None = None,
    vector_backend: str | None = None,
    embedding_provider_override=None,
):
    """Build a SQLite search store from an already loaded config."""
    from ..runtime import create_search_embedding_provider
    from ..search.sqlite_store import SQLiteSearchStore

    embedding_provider = embedding_provider_override or create_search_embedding_provider(loaded)
    strategy = candidate_strategy or loaded.search.embedding.candidate_strategy
    backend = vector_backend or loaded.search.embedding.vector_backend
    return SQLiteSearchStore(
        path=loaded.storage.path,
        history_top_k=loaded.search.history_top_k,
        knowledge_top_k=loaded.search.knowledge_top_k,
        embedding_provider=embedding_provider,
        hybrid_candidate_count=loaded.search.embedding.candidate_count,
        embedding_candidate_strategy=strategy,
        vector_backend=backend,
        vector_candidate_count=loaded.search.embedding.vector_candidate_count,
        retry_failed_on_startup=loaded.search.embedding.retry_failed_on_startup,
    )


def benchmark_one_strategy(
    search_store,
    *,
    kind: str,
    session_id: str,
    query: str,
    limit: int,
    source_type: str | None = None,
    provider: str | None = None,
    extractor: str | None = None,
    status: int | None = None,
    content_type: str | None = None,
    truncated: bool | None = None,
):
    """Run one benchmark query and return elapsed time with hits."""
    started = time.perf_counter()
    if kind == "history":
        hits = asyncio.run(search_store.search_history(session_id, query, limit=limit))
    else:
        hits = asyncio.run(
            search_store.search_knowledge(
                session_id,
                query,
                limit=limit,
                source_type=source_type,
                provider=provider,
                extractor=extractor,
                status=status,
                content_type=content_type,
                truncated=truncated,
            )
        )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return elapsed_ms, hits


def demo_search_payload(query: str, title: str, url: str, content: str, *, provider: str = "duckduckgo") -> str:
    """Build a demo web_search payload."""
    return json.dumps(
        {
            "type": "web_search",
            "query": query,
            "url": "",
            "final_url": "",
            "title": "",
            "content": "",
            "summary": f"Search results for: {query}",
            "provider": provider,
            "extractor": "search",
            "status": None,
            "truncated": False,
            "content_type": "application/json",
            "items": [{"title": title, "url": url, "content": content}],
        },
        ensure_ascii=False,
    )


def demo_fetch_payload(url: str, title: str, content: str, *, extractor: str = "trafilatura") -> str:
    """Build a demo web_fetch payload."""
    return json.dumps(
        {
            "type": "web_fetch",
            "query": url,
            "url": url,
            "final_url": url,
            "title": title,
            "content": content,
            "summary": title,
            "provider": "web_fetch",
            "extractor": extractor,
            "status": 200,
            "content_type": "text/html",
            "truncated": False,
            "items": [],
        },
        ensure_ascii=False,
    )


async def seed_demo_search_data(loaded, search_store, *, session_id: str, reset: bool) -> dict[str, int]:
    """Seed one synthetic session with history and stored web knowledge."""
    from ..storage.sqlite import SQLiteStorage

    storage = SQLiteStorage(loaded.storage.path)
    if reset:
        await storage.clear_messages(session_id)
        await search_store.clear_session(session_id)

    seeded_messages = [
        StoredMessage(role="user", content="Compare SQLite FTS and vector search strategies.", timestamp=10.0),
        StoredMessage(role="assistant", content="I can compare retrieval speed and relevance once benchmark data is ready.", timestamp=11.0),
        StoredMessage(role="user", content="Focus on orchard planning, irrigation, and soil notes.", timestamp=12.0),
    ]

    for message in seeded_messages:
        await storage.add_message(session_id, message)
        await search_store.index_message(
            session_id,
            role=message.role,
            content=message.content,
            tool_name=message.tool_name,
            created_at=message.timestamp,
        )

    demo_knowledge = [
        (
            "web_search",
            {"query": "orchard irrigation guide", "provider": "duckduckgo"},
            demo_search_payload(
                "orchard irrigation guide",
                "Orchard Irrigation Guide",
                "https://example.com/orchard-irrigation",
                "Irrigation scheduling, soil moisture, and orchard planning checklist.",
            ),
            20.0,
        ),
        (
            "web_fetch",
            {"url": "https://example.com/orchard-irrigation"},
            demo_fetch_payload(
                "https://example.com/orchard-irrigation",
                "Orchard Irrigation Guide",
                "This guide covers orchard layout, irrigation timing, soil moisture targets, and benchmark-friendly notes about planning healthy trees.",
            ),
            21.0,
        ),
        (
            "web_search",
            {"query": "soil amendment notes", "provider": "duckduckgo"},
            demo_search_payload(
                "soil amendment notes",
                "Soil Amendment Notes",
                "https://example.com/soil-notes",
                "Soil notes on compost, drainage, and amendment timing for orchards.",
            ),
            22.0,
        ),
        (
            "web_fetch",
            {"url": "https://example.com/soil-notes"},
            demo_fetch_payload(
                "https://example.com/soil-notes",
                "Soil Amendment Notes",
                "Detailed soil notes covering compost rates, drainage fixes, and orchard soil preparation steps.",
            ),
            23.0,
        ),
    ]

    for tool_name, tool_args, payload, created_at in demo_knowledge:
        tool_message = StoredMessage(role="tool", content=payload, timestamp=created_at, tool_name=tool_name)
        await storage.add_message(session_id, tool_message)
        await search_store.index_message(
            session_id,
            role=tool_message.role,
            content=tool_message.content,
            tool_name=tool_message.tool_name,
            created_at=tool_message.timestamp,
        )
        await search_store.index_tool_result(
            session_id,
            tool_name=tool_name,
            tool_args=tool_args,
            result=payload,
            created_at=created_at,
        )

    status = await search_store.wait_for_embedding_idle()
    return {
        "messages": len(seeded_messages) + len(demo_knowledge),
        "knowledge_sources": 4,
        "chunks": status["chunk_count"],
        "completed": status["completed"],
    }


def search_rebuild_command(*, config: str | None, session_id: str | None, load_sqlite_search_store: Callable[[str | None], Any], handle_search_error: Callable[[Exception | str], None]) -> None:
    try:
        loaded, search_store = load_sqlite_search_store(config)
        result = asyncio.run(search_store.rebuild_index(session_id=session_id))
        status = asyncio.run(search_store.wait_for_embedding_idle())
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    scope = session_id or "all sessions"
    typer.echo(f"Rebuilt search index for {scope}.")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(f"Sessions: {result['session_count']}")
    typer.echo(f"Messages: {result['message_count']}")
    typer.echo(f"Knowledge sources: {result['knowledge_count']}")
    typer.echo(f"Chunks: {result['chunk_count']}")
    typer.echo(
        "Embeddings: "
        f"queued={status['queued']} pending={status['pending']} processing={status['processing']} completed={status['completed']} failed={status['failed']} missing={status['missing']} stale={status['stale']}"
    )


def search_status_command(*, config: str | None, session_id: str | None, load_sqlite_search_store: Callable[[str | None], Any], handle_search_error: Callable[[Exception | str], None], format_presence: Callable[[bool], str]) -> None:
    try:
        loaded, search_store = load_sqlite_search_store(config)
        status = asyncio.run(search_store.get_status(session_id=session_id))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    scope = session_id or "all sessions"
    embedding = loaded.search.embedding
    typer.echo(f"Search status for {scope}.")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(f"Sessions: {status['session_count']}")
    typer.echo(f"Messages: {status['message_count']}")
    typer.echo(f"Knowledge sources: {status['knowledge_count']}")
    typer.echo(f"Chunks: {status['chunk_count']}")
    typer.echo(
        "Embedding: "
        f"enabled={format_presence(bool(embedding.enabled))} "
        f"provider={embedding.provider} model={embedding.model or '<unset>'} "
        f"candidate_strategy={embedding.candidate_strategy} "
        f"vector_backend={embedding.vector_backend} "
        f"retry_failed_on_startup={format_presence(bool(embedding.retry_failed_on_startup))}"
    )
    typer.echo(
        "Embedding jobs: "
        f"total={status['embedding_total']} queued={status['queued']} pending={status['pending']} processing={status['processing']} completed={status['completed']} failed={status['failed']} missing={status['missing']} stale={status['stale']}"
    )
    typer.echo(f"Vector backend: requested={status['vector_backend_requested']} effective={status['vector_backend_effective']}")
    typer.echo(
        "Queue worker: "
        f"running={format_presence(bool(status['worker_running']))} "
        f"owner={status['worker_owner'] or '<none>'} "
        f"expires={format_search_timestamp(status['worker_expires_at'])}"
    )
    typer.echo(
        "Last queue run: "
        f"mode={status['last_run_mode'] or '<none>'} "
        f"started={format_search_timestamp(status['last_run_started_at'])} "
        f"finished={format_search_timestamp(status['last_run_finished_at'])} "
        f"refreshed={status['last_run_refreshed']} processed={status['last_run_processed']} failed={status['last_run_failed']}"
    )


def search_refresh_embeddings_command(*, config: str | None, session_id: str | None, force: bool, load_sqlite_search_store: Callable[[str | None], Any], handle_search_error: Callable[[Exception | str], None], format_presence: Callable[[bool], str]) -> None:
    try:
        loaded, search_store = load_sqlite_search_store(config)
        if not loaded.search.embedding.enabled:
            raise ValueError("search.embedding.enabled=false; enable embeddings first")
        status = asyncio.run(search_store.refresh_embeddings(session_id=session_id, force=force, wait=True))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    scope = session_id or "all sessions"
    embedding = loaded.search.embedding
    typer.echo(f"Refreshed embeddings for {scope}.")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(
        "Embedding: "
        f"enabled={format_presence(bool(embedding.enabled))} "
        f"provider={embedding.provider} model={embedding.model or '<unset>'} force={format_presence(bool(force))}"
    )
    typer.echo(f"Refreshed: {status['refreshed']}")
    typer.echo(
        "Embedding jobs: "
        f"total={status['embedding_total']} queued={status['queued']} pending={status['pending']} processing={status['processing']} completed={status['completed']} failed={status['failed']} missing={status['missing']} stale={status['stale']}"
    )


def search_run_queue_command(*, config: str | None, watch: bool, poll_interval: float, idle_exit_seconds: float | None, force_refresh: bool, load_sqlite_search_store: Callable[[str | None], Any], handle_search_error: Callable[[Exception | str], None]) -> None:
    try:
        loaded, search_store = load_sqlite_search_store(config)
        if not loaded.search.embedding.enabled:
            raise ValueError("search.embedding.enabled=false; enable embeddings first")
        status = asyncio.run(
            search_store.run_queue(
                once=not watch,
                poll_interval=poll_interval,
                idle_exit_seconds=idle_exit_seconds,
                force_refresh=force_refresh,
            )
        )
    except KeyboardInterrupt:
        typer.secho("Search queue stopped.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=130)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    scope = "watch" if watch else "once"
    typer.echo(f"Ran search queue in {scope} mode.")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(
        "Embedding jobs: "
        f"total={status['embedding_total']} queued={status['queued']} pending={status['pending']} processing={status['processing']} completed={status['completed']} failed={status['failed']} missing={status['missing']} stale={status['stale']}"
    )
    typer.echo(f"Queue run: refreshed={status['refreshed']} processed={status['processed_chunks']} failed={status['failed_chunks_run']}")


def search_benchmark_command(*, query: str, session_id: str, kind: str, strategy: str, vector_backend: str | None, limit: int, repeat: int, json_output: bool, demo_embeddings: bool, source_type: str | None, provider: str | None, extractor: str | None, status: int | None, content_type: str | None, truncated: bool | None, config: str | None, build_sqlite_search_store: Callable[..., Any], handle_search_error: Callable[[Exception | str], None], resolve_config_path: Callable[[str | None], Path], benchmark_one_strategy_fn: Callable[..., Any]) -> None:
    if kind not in {"history", "knowledge"}:
        handle_search_error("--kind must be 'history' or 'knowledge'")
    if strategy not in {"fts", "vector", "both"}:
        handle_search_error("--strategy must be 'fts', 'vector', or 'both'")
    if vector_backend is not None and vector_backend not in {"exact", "sqlite_vec", "auto", "both"}:
        handle_search_error("--vector-backend must be 'exact', 'sqlite_vec', 'auto', or 'both'")
    if repeat < 1:
        handle_search_error("--repeat must be greater than 0")

    try:
        from ..config import Config
        from ..search.embeddings import LocalHashEmbeddingProvider

        loaded = Config.load(resolve_config_path(config))
        if not loaded.search.enabled:
            raise ValueError("search.enabled=false; enable search first")
        strategies = ["fts", "vector"] if strategy == "both" else [strategy]
        benchmark_embedding_provider = LocalHashEmbeddingProvider() if demo_embeddings else None
        vector_available = loaded.search.embedding.enabled or benchmark_embedding_provider is not None
        if strategy == "vector" and not vector_available:
            raise ValueError("search.embedding.enabled=false; vector benchmarks require embeddings")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    backend_overrides = [vector_backend] if vector_backend not in {None, "both"} else (["exact", "sqlite_vec"] if vector_backend == "both" else [None])

    filters = []
    if kind == "knowledge":
        if source_type:
            filters.append(f"source_type={source_type}")
        if provider:
            filters.append(f"provider={provider}")
        if extractor:
            filters.append(f"extractor={extractor}")
        if status is not None:
            filters.append(f"status={status}")
        if content_type:
            filters.append(f"content_type={content_type}")
        if truncated is not None:
            filters.append(f"truncated={'yes' if truncated else 'no'}")

    if "vector" in strategies and not vector_available:
        if not json_output:
            typer.echo("Vector benchmark skipped because embeddings are disabled.")
        strategies = [item for item in strategies if item != "vector"]

    benchmark_payload: dict[str, object] = {
        "session_id": session_id,
        "kind": kind,
        "query": query,
        "repeat": repeat,
        "demo_embeddings": demo_embeddings,
        "vector_backend": vector_backend or getattr(loaded.search.embedding, "vector_backend", "exact"),
        "filters": filters,
        "strategies": [],
        "comparison": {},
    }

    if not json_output:
        typer.echo(f"Search benchmark for {session_id} ({kind}).")
        typer.echo(f"Query: {query}")
        if vector_backend:
            typer.echo(f"Vector backend override: {vector_backend}")
        if kind == "knowledge":
            typer.echo(f"Filters: {', '.join(filters) if filters else '<none>'}")

    for candidate_strategy in strategies:
        strategy_backends = backend_overrides if candidate_strategy == "vector" else [None]
        for backend_override in strategy_backends:
            try:
                embedding_override = benchmark_embedding_provider if candidate_strategy == "vector" and benchmark_embedding_provider is not None else None
                search_store = build_sqlite_search_store(
                    loaded,
                    candidate_strategy=candidate_strategy,
                    vector_backend=backend_override,
                    embedding_provider_override=embedding_override,
                )
                if embedding_override is not None:
                    asyncio.run(search_store.refresh_embeddings(force=False, wait=True))
                elapsed_runs: list[float] = []
                hits = []
                for _ in range(repeat):
                    elapsed_ms, hits = benchmark_one_strategy_fn(
                        search_store,
                        kind=kind,
                        session_id=session_id,
                        query=query,
                        limit=limit,
                        source_type=source_type,
                        provider=provider,
                        extractor=extractor,
                        status=status,
                        content_type=content_type,
                        truncated=truncated,
                    )
                    elapsed_runs.append(elapsed_ms)
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                handle_search_error(exc)

            timing = summarize_benchmark_runs(elapsed_runs)
            strategy_name = candidate_strategy
            if candidate_strategy == "vector" and backend_override:
                strategy_name = f"vector:{backend_override}"

            result = {
                "strategy": strategy_name,
                "candidate_strategy": candidate_strategy,
                "vector_backend_requested": getattr(search_store, "vector_backend_requested", None),
                "vector_backend_effective": getattr(search_store, "vector_backend_effective", None),
                "summary": timing,
                "hit_count": len(hits),
                "hits": serialize_benchmark_hits(hits, limit=limit),
                "_raw_hits": hits,
            }
            benchmark_payload["strategies"].append(result)

            if not json_output:
                typer.echo("")
                typer.echo(f"Strategy: {strategy_name}")
                if candidate_strategy == "vector":
                    typer.echo(
                        "Vector backend: "
                        f"requested={getattr(search_store, 'vector_backend_requested', '<unknown>')} "
                        f"effective={getattr(search_store, 'vector_backend_effective', '<unknown>')}"
                    )
                typer.echo(
                    "Elapsed: "
                    f"avg={timing['avg_ms']:.2f} ms min={timing['min_ms']:.2f} ms "
                    f"max={timing['max_ms']:.2f} ms median={timing['median_ms']:.2f} ms "
                    f"runs={int(timing['runs'])}"
                )
                typer.echo(f"Hits: {len(hits)}")
                for line in render_benchmark_hits(hits, limit=limit):
                    typer.echo(line)
                if not hits:
                    typer.echo("<no hits>")

    benchmark_payload["comparison"] = compare_benchmark_results(benchmark_payload["strategies"])
    for result in benchmark_payload["strategies"]:
        result.pop("_raw_hits", None)

    if json_output:
        typer.echo(json.dumps(benchmark_payload, ensure_ascii=False, indent=2))
        return
    if benchmark_payload["comparison"]:
        for pair in benchmark_payload["comparison"]["pairs"]:
            typer.echo("")
            typer.echo(
                "Comparison: "
                f"{pair['strategies'][0]} vs {pair['strategies'][1]} | "
                f"overlap={pair['overlap_count']} ({pair['overlap_ratio']:.2%}) "
                f"top_hit_same={'yes' if pair['top_hit_same'] else 'no'} "
                f"{pair['strategies'][0]}_only={pair['first_only_count']} "
                f"{pair['strategies'][1]}_only={pair['second_only_count']}"
            )
            if pair["first_top"] or pair["second_top"]:
                typer.echo(
                    "Top hits: "
                    f"{pair['strategies'][0]}={pair['first_top'] or '<none>'} | "
                    f"{pair['strategies'][1]}={pair['second_top'] or '<none>'}"
                )


def search_seed_demo_command(*, session_id: str, reset: bool, config: str | None, load_sqlite_search_store: Callable[[str | None], Any], handle_search_error: Callable[[Exception | str], None]) -> None:
    try:
        loaded, search_store = load_sqlite_search_store(config)
        result = asyncio.run(seed_demo_search_data(loaded, search_store, session_id=session_id, reset=reset))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    typer.echo(f"Seeded demo search data for {session_id}.")
    typer.echo(f"Messages: {result['messages']}")
    typer.echo(f"Knowledge sources: {result['knowledge_sources']}")
    typer.echo(f"Chunks: {result['chunks']}")
    typer.echo(f"Completed embeddings: {result['completed']}")


def search_retry_embeddings_command(*, config: str | None, session_id: str | None, load_sqlite_search_store: Callable[[str | None], Any], handle_search_error: Callable[[Exception | str], None], format_presence: Callable[[bool], str]) -> None:
    try:
        loaded, search_store = load_sqlite_search_store(config)
        if not loaded.search.embedding.enabled:
            raise ValueError("search.embedding.enabled=false; enable embeddings first")
        status = asyncio.run(search_store.retry_failed_embeddings(session_id=session_id, wait=True))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        handle_search_error(exc)

    scope = session_id or "all sessions"
    embedding = loaded.search.embedding
    typer.echo(f"Retried failed embeddings for {scope}.")
    typer.echo(f"Storage DB: {Path(loaded.storage.path).expanduser()}")
    typer.echo(
        "Embedding: "
        f"enabled={format_presence(bool(embedding.enabled))} "
        f"provider={embedding.provider} model={embedding.model or '<unset>'}"
    )
    typer.echo(f"Retried: {status['retried']}")
    typer.echo(
        "Embedding jobs: "
        f"total={status['embedding_total']} queued={status['queued']} pending={status['pending']} processing={status['processing']} completed={status['completed']} failed={status['failed']} missing={status['missing']} stale={status['stale']}"
    )
