"""Lifecycle checks for the production local runtime composition."""

from asyncio import run
from collections.abc import Callable, Iterator

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.models import ProviderListResponse
from opensprite_backend.model_selection import UnavailableModelSelections
from opensprite_backend.provider_connections import (
    UnavailableProviderConnections,
)
from opensprite_backend.runtime import create_system_app

from test_local_security import RecordingConnections


class FakeClient:
    def __init__(
        self,
        *,
        close_error: Exception | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.provider_calls = 0
        self.close_calls = 0
        self.close_error = close_error
        self.on_close = on_close

    async def aclose(self) -> None:
        if self.on_close is not None:
            self.on_close()
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class RuntimeConnections(RecordingConnections):
    def __init__(self, client: FakeClient) -> None:
        super().__init__()
        self.client = client

    async def list_providers(self) -> ProviderListResponse:
        self.client.provider_calls += 1
        return await super().list_providers()


class FakeRuntime:
    def __init__(self, *, close_error: Exception | None = None) -> None:
        self.client = FakeClient(close_error=close_error)
        self.connections = RuntimeConnections(self.client)
        self.model_selection = UnavailableModelSelections()

    async def aclose(self) -> None:
        await self.client.aclose()


def test_system_app_is_offline_until_lifespan_entry() -> None:
    factory_calls = 0

    def factory() -> FakeRuntime:
        nonlocal factory_calls
        factory_calls += 1
        return FakeRuntime()

    app = create_system_app(runtime_factory=factory)

    assert factory_calls == 0
    assert isinstance(
        app.state.provider_connections,
        UnavailableProviderConnections,
    )


def test_sequential_lifespans_use_and_close_fresh_runtimes() -> None:
    runtimes: list[FakeRuntime] = []

    def factory() -> FakeRuntime:
        runtime = FakeRuntime()
        runtimes.append(runtime)
        return runtime

    app = create_system_app(runtime_factory=factory)

    for expected_count in (1, 2):
        with TestClient(app, base_url="http://127.0.0.1:8765") as client:
            response = client.get("/api/providers")
            assert response.status_code == 200
            ProviderListResponse.model_validate(response.json())
            assert len(runtimes) == expected_count
            assert app.state.provider_connections is runtimes[-1].connections
            assert runtimes[-1].client.close_calls == 0

        assert isinstance(
            app.state.provider_connections,
            UnavailableProviderConnections,
        )
        assert runtimes[-1].client.close_calls == 1

    assert runtimes[0].client is not runtimes[1].client
    assert runtimes[0].client.provider_calls == 1
    assert runtimes[1].client.provider_calls == 1
    assert runtimes[0].client.close_calls == 1
    assert runtimes[1].client.close_calls == 1


def test_close_failure_unbinds_and_later_entry_uses_fresh_runtime() -> None:
    runtimes = [
        FakeRuntime(close_error=RuntimeError("close failed")),
        FakeRuntime(),
    ]
    pending: Iterator[FakeRuntime] = iter(runtimes)
    app = create_system_app(runtime_factory=lambda: next(pending))
    unbound_during_close: list[bool] = []
    runtimes[0].client.on_close = lambda: unbound_during_close.append(
        isinstance(
            app.state.provider_connections,
            UnavailableProviderConnections,
        )
    )

    with pytest.raises(RuntimeError, match="close failed"):
        with TestClient(app, base_url="http://localhost:8765") as client:
            assert client.get("/api/providers").status_code == 200

    assert isinstance(
        app.state.provider_connections,
        UnavailableProviderConnections,
    )
    assert runtimes[0].client.close_calls == 1
    assert unbound_during_close == [True]

    with TestClient(app, base_url="http://localhost:8765") as client:
        assert client.get("/api/providers").status_code == 200
        assert app.state.provider_connections is runtimes[1].connections

    assert runtimes[0].client.provider_calls == 1
    assert runtimes[1].client.provider_calls == 1
    assert runtimes[1].client.close_calls == 1


def test_factory_failure_does_not_enter_or_bind_and_can_retry() -> None:
    runtime = FakeRuntime()
    attempts = 0
    context_body_entered = False

    def factory() -> FakeRuntime:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("startup failed")
        return runtime

    app = create_system_app(runtime_factory=factory)

    with pytest.raises(RuntimeError, match="startup failed"):
        with TestClient(app, base_url="http://localhost:8765"):
            context_body_entered = True

    assert context_body_entered is False
    assert isinstance(
        app.state.provider_connections,
        UnavailableProviderConnections,
    )
    assert runtime.client.close_calls == 0

    with TestClient(app, base_url="http://localhost:8765") as client:
        assert client.get("/api/providers").status_code == 200

    assert attempts == 2
    assert runtime.client.close_calls == 1


def test_exception_inside_lifespan_closes_and_unbinds_runtime() -> None:
    runtime = FakeRuntime()
    app = create_system_app(runtime_factory=lambda: runtime)

    async def exercise_lifespan() -> None:
        with pytest.raises(RuntimeError, match="lifespan body failed"):
            async with app.router.lifespan_context(app):
                assert app.state.provider_connections is runtime.connections
                raise RuntimeError("lifespan body failed")

    run(exercise_lifespan())

    assert isinstance(
        app.state.provider_connections,
        UnavailableProviderConnections,
    )
    assert runtime.client.close_calls == 1


def test_concurrent_lifespan_entry_is_rejected_before_serving() -> None:
    runtime = FakeRuntime()
    factory_calls = 0

    def factory() -> FakeRuntime:
        nonlocal factory_calls
        factory_calls += 1
        return runtime

    app = create_system_app(runtime_factory=factory)

    async def exercise_lifespans() -> None:
        async with app.router.lifespan_context(app):
            assert app.state.provider_connections is runtime.connections
            with pytest.raises(RuntimeError, match="already active"):
                async with app.router.lifespan_context(app):
                    pytest.fail("concurrent lifespan unexpectedly entered")
            assert app.state.provider_connections is runtime.connections

    run(exercise_lifespans())

    assert factory_calls == 1
    assert runtime.client.close_calls == 1
    assert isinstance(
        app.state.provider_connections,
        UnavailableProviderConnections,
    )
