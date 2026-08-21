"""Production composition for the secured loopback ASGI runtime."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Lock
from typing import Protocol

from fastapi import FastAPI

from .app import create_app
from .app_paths import AppPaths, build_app_paths
from .model_selection import (
    ModelSelections,
    UnavailableModelSelections,
    create_model_selection_service,
)
from .provider_connections import (
    ProviderConnections,
    UnavailableProviderConnections,
    create_provider_runtime,
)


class LocalProviderRuntime(Protocol):
    connections: ProviderConnections

    async def aclose(self) -> None: ...


class LocalSystemRuntime(LocalProviderRuntime, Protocol):
    model_selection: ModelSelections


RuntimeFactory = Callable[[], LocalSystemRuntime]


class _SystemRuntime:
    def __init__(
        self,
        provider_runtime: LocalProviderRuntime,
        model_selection: ModelSelections,
    ) -> None:
        self._provider_runtime = provider_runtime
        self.connections = provider_runtime.connections
        self.model_selection = model_selection

    async def aclose(self) -> None:
        await self._provider_runtime.aclose()


def create_system_runtime(
    *,
    app_paths: AppPaths | None = None,
) -> LocalSystemRuntime:
    """Compose providers and settings from one local OpenSprite root."""

    paths = app_paths if app_paths is not None else build_app_paths()
    provider_runtime = create_provider_runtime(app_paths=paths)
    return _SystemRuntime(
        provider_runtime,
        create_model_selection_service(paths, provider_runtime.connections),
    )


def create_system_app(
    *,
    app_paths: AppPaths | None = None,
    runtime_factory: RuntimeFactory | None = None,
) -> FastAPI:
    """Create an offline secured app with one fresh runtime per lifespan."""

    entry_lock = Lock()
    factory = runtime_factory
    if factory is None:
        factory = lambda: create_system_runtime(app_paths=app_paths)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not entry_lock.acquire(blocking=False):
            raise RuntimeError(
                "OpenSprite runtime lifespan is already active."
            )
        runtime: LocalSystemRuntime | None = None
        try:
            app.state.provider_connections = UnavailableProviderConnections()
            app.state.model_selection = UnavailableModelSelections()
            runtime = factory()
            app.state.provider_connections = runtime.connections
            app.state.model_selection = runtime.model_selection
            yield
        finally:
            app.state.provider_connections = UnavailableProviderConnections()
            app.state.model_selection = UnavailableModelSelections()
            try:
                if runtime is not None:
                    await runtime.aclose()
            finally:
                entry_lock.release()

    return create_app(
        lifespan=lifespan,
        enforce_local_security=True,
    )
