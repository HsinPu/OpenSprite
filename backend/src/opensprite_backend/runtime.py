"""Production composition for the secured loopback ASGI runtime."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Lock
from typing import Protocol

from fastapi import FastAPI

from .app import create_app
from .provider_connections import (
    ProviderConnections,
    UnavailableProviderConnections,
    create_provider_runtime,
)


class LocalProviderRuntime(Protocol):
    connections: ProviderConnections

    async def aclose(self) -> None: ...


RuntimeFactory = Callable[[], LocalProviderRuntime]


def create_system_app(
    *,
    runtime_factory: RuntimeFactory = create_provider_runtime,
) -> FastAPI:
    """Create an offline secured app with one fresh runtime per lifespan."""

    entry_lock = Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not entry_lock.acquire(blocking=False):
            raise RuntimeError(
                "OpenSprite runtime lifespan is already active."
            )
        runtime: LocalProviderRuntime | None = None
        try:
            app.state.provider_connections = UnavailableProviderConnections()
            runtime = runtime_factory()
            app.state.provider_connections = runtime.connections
            yield
        finally:
            app.state.provider_connections = UnavailableProviderConnections()
            try:
                if runtime is not None:
                    await runtime.aclose()
            finally:
                entry_lock.release()

    return create_app(
        lifespan=lifespan,
        enforce_local_security=True,
    )
