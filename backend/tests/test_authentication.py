"""Security, lifecycle, and HTTP tests for local owner authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.authentication import (
    AccessMode,
    AccessPolicy,
    JsonAccessPolicyStore,
    LocalAuthentication,
    LocalAuthenticationError,
)
from opensprite_backend.authentication.store import (
    AccessRecord,
    AccessStoreError,
    BootstrapRecord,
    JsonAccessStore,
    JsonBootstrapStore,
)
from opensprite_backend.models import AuthLoginRequest, AuthSetupRequest


NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
PASSWORD = "correct horse battery staple"
BOOTSTRAP = "bootstrap-token-with-more-than-32-characters"


def authentication(tmp_path: Path, clock=None) -> tuple[LocalAuthentication, object]:
    paths = build_app_paths(tmp_path / ".opensprite")
    bootstrap = JsonBootstrapStore(paths.access_bootstrap_file)
    bootstrap.set(BootstrapRecord(
        hashlib.sha256(BOOTSTRAP.encode()).hexdigest(),
        NOW,
        NOW + timedelta(minutes=30),
    ))
    return LocalAuthentication(
        JsonAccessStore(paths.access_file),
        bootstrap,
        clock=clock or (lambda: NOW),
    ), paths


def origin() -> dict[str, str]:
    return {"Origin": "https://localhost:8765"}


def test_access_store_absent_read_is_lazy_and_strict(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonAccessStore(paths.access_file)
    assert store.get() is None
    assert not paths.home.exists()

    paths.access_file.parent.mkdir(parents=True)
    paths.access_file.write_text('{"version":1,"version":1,"passwordHash":"$argon2id$bad"}', encoding="utf-8")
    with pytest.raises(AccessStoreError):
        store.get()


def test_access_policy_is_strict_atomic_and_defaults_to_password(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonAccessPolicyStore(paths.access_policy_file)
    assert store.get() == AccessPolicy(AccessMode.PASSWORD_REQUIRED)
    assert not paths.home.exists()
    store.set(AccessPolicy(AccessMode.TRUSTED_LOCAL))
    assert store.get() == AccessPolicy(AccessMode.TRUSTED_LOCAL)
    assert paths.access_policy_file.read_text(encoding="utf-8") == '{"version":1,"mode":"trusted_local"}\n'
    paths.access_policy_file.write_text('{"version":1,"mode":"unknown"}', encoding="utf-8")
    with pytest.raises(AccessStoreError):
        store.get()


def test_access_store_atomic_failure_preserves_previous_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonAccessStore(paths.access_file)
    previous = AccessRecord("$argon2id$previous")
    store.set(previous)

    def fail_write(path: Path, payload: bytes) -> None:
        del path, payload
        raise OSError("simulated write failure")

    monkeypatch.setattr("opensprite_backend.authentication.store.atomic_write", fail_write)
    with pytest.raises(AccessStoreError):
        store.set(AccessRecord("$argon2id$replacement"))
    assert store.get() == previous


def test_setup_hashes_password_and_bootstrap_is_single_use(tmp_path: Path) -> None:
    auth, paths = authentication(tmp_path)
    assert asyncio_run(auth.status(None)).state == "setup_required"

    result = asyncio_run(auth.setup(BOOTSTRAP, PASSWORD))

    assert result.status.state == "authenticated"
    stored = paths.access_file.read_text(encoding="utf-8")
    assert PASSWORD not in stored
    assert "$argon2id$" in stored
    assert "m=19456,t=2,p=1" in stored
    assert not paths.access_bootstrap_file.exists()
    with pytest.raises(LocalAuthenticationError) as raised:
        asyncio_run(auth.setup(BOOTSTRAP, PASSWORD))
    assert raised.value.code == "setup_unavailable"


def test_trusted_local_status_never_accepts_password_mutations(tmp_path: Path) -> None:
    auth, paths = authentication(tmp_path)
    trusted = LocalAuthentication(
        JsonAccessStore(paths.access_file),
        JsonBootstrapStore(paths.access_bootstrap_file),
        access_mode=AccessMode.TRUSTED_LOCAL,
        clock=lambda: NOW,
    )
    assert asyncio_run(trusted.status(None)).state == "trusted_local"
    for operation in (
        trusted.setup(BOOTSTRAP, PASSWORD),
        trusted.login(PASSWORD),
        trusted.change_password(None, PASSWORD, "replacement password value"),
    ):
        with pytest.raises(LocalAuthenticationError) as raised:
            asyncio_run(operation)
        assert raised.value.code == "authentication_not_enabled"


def test_password_normalization_length_and_controls(tmp_path: Path) -> None:
    auth, _ = authentication(tmp_path)
    for invalid in ("short", "a" * 129, "valid-length-but\nnewline"):
        with pytest.raises(LocalAuthenticationError) as raised:
            asyncio_run(auth.setup(BOOTSTRAP, invalid))
        assert raised.value.code == "invalid_request"


def test_session_expires_and_restart_requires_login(tmp_path: Path) -> None:
    now = [NOW]
    auth, paths = authentication(tmp_path, lambda: now[0])
    result = asyncio_run(auth.setup(BOOTSTRAP, PASSWORD))
    assert asyncio_run(auth.authenticate(result.token)) is not None
    now[0] += timedelta(hours=12)
    assert asyncio_run(auth.authenticate(result.token)) is None

    restarted = LocalAuthentication(
        JsonAccessStore(paths.access_file),
        JsonBootstrapStore(paths.access_bootstrap_file),
        clock=lambda: now[0],
    )
    assert asyncio_run(restarted.status(result.token)).state == "unauthenticated"
    assert asyncio_run(restarted.login(PASSWORD)).status.state == "authenticated"


def test_failed_logins_are_throttled_with_retry_after(tmp_path: Path) -> None:
    now = [NOW]
    auth, _ = authentication(tmp_path, lambda: now[0])
    asyncio_run(auth.setup(BOOTSTRAP, PASSWORD))
    for _ in range(5):
        with pytest.raises(LocalAuthenticationError) as raised:
            asyncio_run(auth.login("incorrect password value"))
        assert raised.value.code == "invalid_credentials"
    with pytest.raises(LocalAuthenticationError) as raised:
        asyncio_run(auth.login("incorrect password value"))
    assert raised.value.code == "rate_limited"
    assert raised.value.retry_after == 1


def test_change_password_revokes_old_sessions_and_issues_current(tmp_path: Path) -> None:
    auth, _ = authentication(tmp_path)
    first = asyncio_run(auth.setup(BOOTSTRAP, PASSWORD))
    second = asyncio_run(auth.login(PASSWORD))
    changed = asyncio_run(auth.change_password(first.token, PASSWORD, "replacement password value"))
    assert asyncio_run(auth.authenticate(first.token)) is None
    assert asyncio_run(auth.authenticate(second.token)) is None
    assert asyncio_run(auth.authenticate(changed.token)) is not None
    with pytest.raises(LocalAuthenticationError):
        asyncio_run(auth.login(PASSWORD))


def test_http_setup_cookie_and_protected_route_matrix(tmp_path: Path) -> None:
    auth, _ = authentication(tmp_path)
    app = create_app(
        local_authentication=auth,
        enforce_authentication=True,
        enforce_local_security=True,
    )
    with TestClient(app, base_url="https://localhost:8765") as client:
        unauthenticated = client.get("/api/providers")
        status = client.get("/api/auth/status")
        setup = client.post("/api/auth/setup", headers=origin(), json={
            "bootstrapToken": BOOTSTRAP,
            "password": PASSWORD,
        })
        authenticated = client.get("/api/auth/status")
        protected = client.get("/api/providers")
        logout = client.post("/api/auth/logout", headers=origin())
        after = client.get("/api/providers")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "authentication_required"
    assert status.json() == {"state": "setup_required"}
    cookie = setup.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert authenticated.json()["state"] == "authenticated"
    assert protected.status_code == 503
    assert logout.status_code == 204
    assert after.status_code == 401
    for response in (unauthenticated, status, setup, authenticated, protected, logout, after):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_auth_mutations_still_require_same_origin(tmp_path: Path) -> None:
    auth, _ = authentication(tmp_path)
    app = create_app(local_authentication=auth, enforce_authentication=True, enforce_local_security=True)
    with TestClient(app, base_url="https://localhost:8765") as client:
        response = client.post("/api/auth/setup", headers={"Origin": "https://evil.example"}, json={
            "bootstrapToken": BOOTSTRAP,
            "password": PASSWORD,
        })
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/api/settings/ai"),
    ("PUT", "/api/settings/general"),
    ("GET", "/api/providers"),
    ("DELETE", "/api/providers/openai/connection"),
    ("GET", "/api/mcp/servers"),
    ("POST", "/api/local-paths/pick"),
    ("GET", "/api/conversations"),
    ("GET", "/api/workspaces"),
    ("POST", "/api/workspaces"),
    ("POST", "/api/runs"),
    ("GET", "/api/runs/00000000-0000-4000-8000-000000000000/events"),
    ("PUT", "/api/tool-approvals/00000000-0000-4000-8000-000000000000"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/logout-all"),
    ("PUT", "/api/auth/password"),
])
def test_all_sensitive_api_families_default_to_authentication(method: str, path: str, tmp_path: Path) -> None:
    auth, _ = authentication(tmp_path)
    app = create_app(local_authentication=auth, enforce_authentication=True, enforce_local_security=False)
    with TestClient(app, base_url="https://localhost:8765") as client:
        response = client.request(method, path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_auth_requests_are_strict_and_secrets_do_not_leak_from_repr(tmp_path: Path) -> None:
    auth, _ = authentication(tmp_path)
    app = create_app(local_authentication=auth, enforce_authentication=True, enforce_local_security=False)
    with TestClient(app, base_url="https://localhost:8765") as client:
        response = client.post("/api/auth/login", json={"password": PASSWORD, "unexpected": True})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert PASSWORD not in repr(AuthLoginRequest(password=PASSWORD))
    assert BOOTSTRAP not in repr(AuthSetupRequest(bootstrapToken=BOOTSTRAP, password=PASSWORD))


def test_concurrent_bootstrap_setup_has_exactly_one_winner(tmp_path: Path) -> None:
    import asyncio

    auth, _ = authentication(tmp_path)

    async def setup_once() -> str:
        try:
            await auth.setup(BOOTSTRAP, PASSWORD)
            return "authenticated"
        except LocalAuthenticationError as error:
            return error.code

    async def run_both() -> list[str]:
        return list(await asyncio.gather(setup_once(), setup_once()))

    results = asyncio.run(run_both())
    assert sorted(results) == ["authenticated", "setup_unavailable"]


def asyncio_run(awaitable):
    import asyncio
    return asyncio.run(awaitable)
