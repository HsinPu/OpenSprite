"""Real multipart, HTTP errors and downloaded deployment archive."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from execution_package_test_support import FILE_NAME, paths, wheel, absent_distribution
from opensprite_backend.api.execution_package_routes import router, execution_package_error_handler
from opensprite_backend.execution_plugins.models import ExecutionPackageError, MAX_WHEEL_BYTES
from opensprite_backend.execution_plugins.service import ExecutionPackageService
from opensprite_backend.app import create_app


def client(tmp_path, *, image="opensprite:reviewed"):
    app = FastAPI()
    app.state.execution_packages = ExecutionPackageService(paths(tmp_path), base_image_ref=image, runtime_kind="docker",
                                                           distribution_lookup=absent_distribution)
    app.include_router(router)
    app.add_exception_handler(ExecutionPackageError, execution_package_error_handler)
    return TestClient(app)


def test_real_http_import_list_idempotency_download_and_cache_delete(tmp_path):
    data = wheel()
    with client(tmp_path) as http:
        before = http.get("/api/execution-plugin-packages")
        assert before.status_code == 200 and before.json()["packages"] == []
        assert not paths(tmp_path).home.exists()
        imported = http.post("/api/execution-plugin-packages", files={"file": (FILE_NAME, data, "application/octet-stream")})
        assert imported.status_code == 200
        package = imported.json()["packages"][0]
        assert package["runtimeStatus"] == "not_installed"
        assert package["distributionName"] == "opensprite-stage2-fixture"
        repeated = http.post("/api/execution-plugin-packages", files={"file": (FILE_NAME, data)})
        assert repeated.json()["packages"][0]["id"] == package["id"]
        bundle = http.get(f'/api/execution-plugin-packages/{package["id"]}/deployment-bundle')
        assert bundle.status_code == 200 and bundle.headers["content-type"] == "application/zip"
        deleted = http.delete(f'/api/execution-plugin-packages/{package["id"]}')
        assert deleted.status_code == 204 and deleted.content == b""
        assert http.get("/api/execution-plugin-packages").json()["packages"] == []


@pytest.mark.parametrize("files,data", [
    ([("file", (FILE_NAME, wheel())), ("file", (FILE_NAME, wheel()))], None),
    ({"wrong": (FILE_NAME, wheel())}, None),
    ({"file": (FILE_NAME, wheel())}, {"extra": "forbidden"}),
])
def test_multipart_accepts_exactly_one_wheel_and_no_other_fields(tmp_path, files, data):
    with client(tmp_path) as http:
        response = http.post("/api/execution-plugin-packages", files=files, data=data)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"
        assert not paths(tmp_path).home.exists()


def test_oversized_multipart_is_bounded_before_import(tmp_path):
    with client(tmp_path) as http:
        response = http.post("/api/execution-plugin-packages", files={"file": (FILE_NAME, b"x" * (MAX_WHEEL_BYTES + 1))})
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "package_too_large"
        assert not paths(tmp_path).home.exists()


def test_missing_base_image_disables_bundle_without_hiding_inventory(tmp_path):
    with client(tmp_path, image=None) as http:
        package = http.post("/api/execution-plugin-packages", files={"file": (FILE_NAME, wheel())}).json()["packages"][0]
        response = http.get(f'/api/execution-plugin-packages/{package["id"]}/deployment-bundle')
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "deployment_unavailable"
        assert http.get("/api/execution-plugin-packages").status_code == 200


def test_invalid_uuid_and_private_store_failures_are_sanitized(tmp_path):
    with client(tmp_path) as http:
        assert http.delete("/api/execution-plugin-packages/not-uuid").status_code == 400
        folder = paths(tmp_path).execution_plugin_packages_dir
        folder.mkdir(parents=True)
        (folder / "PRIVATE-INVALID-CACHE").mkdir()
        response = http.get("/api/execution-plugin-packages")
        assert response.status_code == 503
        assert "PRIVATE" not in response.text and str(tmp_path) not in response.text


def test_all_package_routes_require_owner_authentication_before_touching_cache(tmp_path):
    from test_authentication import authentication
    auth, _ = authentication(tmp_path / "auth")
    package_paths = paths(tmp_path / "packages")
    service = ExecutionPackageService(package_paths, base_image_ref="opensprite:reviewed", runtime_kind="docker",
                                      distribution_lookup=absent_distribution)
    app = create_app(execution_packages=service, local_authentication=auth, enforce_authentication=True)
    package_id = "00000000-0000-4000-8000-000000000001"
    with TestClient(app) as http:
        for method, suffix in (("GET", ""), ("POST", ""), ("DELETE", "/" + package_id),
                               ("GET", "/" + package_id + "/deployment-bundle")):
            response = http.request(method, "/api/execution-plugin-packages" + suffix)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "authentication_required"
    assert not package_paths.home.exists()


def test_authenticated_same_origin_package_flow_uses_real_app_wiring(tmp_path):
    from test_authentication import authentication, BOOTSTRAP, PASSWORD, origin
    auth, _ = authentication(tmp_path / "auth")
    service = ExecutionPackageService(paths(tmp_path / "packages"), base_image_ref="opensprite:reviewed", runtime_kind="docker",
                                      distribution_lookup=absent_distribution)
    app = create_app(execution_packages=service, local_authentication=auth,
                     enforce_authentication=True, enforce_local_security=True)
    with TestClient(app, base_url="https://localhost:8765") as http:
        setup = http.post("/api/auth/setup", headers=origin(), json={"bootstrapToken": BOOTSTRAP, "password": PASSWORD})
        assert setup.status_code == 200
        assert http.get("/api/execution-plugin-packages").json()["packages"] == []
        imported = http.post("/api/execution-plugin-packages", headers=origin(), files={"file": (FILE_NAME, wheel())})
        assert imported.status_code == 200
        package_id = imported.json()["packages"][0]["id"]
        downloaded = http.get(f"/api/execution-plugin-packages/{package_id}/deployment-bundle", headers=origin())
        assert downloaded.status_code == 200 and downloaded.headers["content-type"] == "application/zip"
        deleted = http.delete(f"/api/execution-plugin-packages/{package_id}", headers=origin())
        assert deleted.status_code == 204
        assert http.get("/api/execution-plugin-packages").json()["packages"] == []


@pytest.mark.parametrize("method,suffix", [("POST", ""),
    ("DELETE", "/00000000-0000-4000-8000-000000000001")])
def test_foreign_origin_is_rejected_before_package_operations(tmp_path, method, suffix):
    package_paths = paths(tmp_path)
    service = ExecutionPackageService(package_paths, base_image_ref="opensprite:reviewed", runtime_kind="docker",
                                      distribution_lookup=absent_distribution)
    app = create_app(execution_packages=service, enforce_local_security=True)
    with TestClient(app, base_url="http://localhost:8765") as http:
        response = http.request(method, "/api/execution-plugin-packages" + suffix,
                                headers={"Origin": "https://evil.example"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"
    assert not package_paths.home.exists()


@pytest.mark.parametrize("download", [False, True])
def test_authenticated_package_reads_do_not_open_cors_to_foreign_origin(tmp_path, download):
    from test_authentication import authentication, BOOTSTRAP, PASSWORD, origin
    auth, _ = authentication(tmp_path / "auth")
    service = ExecutionPackageService(paths(tmp_path / "packages"), base_image_ref="opensprite:reviewed", runtime_kind="docker",
                                      distribution_lookup=absent_distribution)
    app = create_app(execution_packages=service, local_authentication=auth,
                     enforce_authentication=True, enforce_local_security=True)
    with TestClient(app, base_url="https://localhost:8765") as http:
        setup = http.post("/api/auth/setup", headers=origin(), json={"bootstrapToken": BOOTSTRAP, "password": PASSWORD})
        assert setup.status_code == 200
        imported = http.post("/api/execution-plugin-packages", headers=origin(), files={"file": (FILE_NAME, wheel())})
        assert imported.status_code == 200
        package_id = imported.json()["packages"][0]["id"]
        suffix = f"/{package_id}/deployment-bundle" if download else ""
        url = "/api/execution-plugin-packages" + suffix
        # TestClient retains the synthetic session cookie; a browser must still
        # enforce the response's absent CORS permission for a foreign page.
        response = http.get(url, headers={"Origin": "https://evil.example"})
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers
        preflight = http.options(url, headers={"Origin": "https://evil.example",
                                             "Access-Control-Request-Method": "GET"})
        assert "access-control-allow-origin" not in preflight.headers
        assert "access-control-allow-credentials" not in preflight.headers


def test_unexpected_package_exception_does_not_log_private_context(tmp_path, caplog):
    service = ExecutionPackageService(paths(tmp_path))
    def failing_inventory():
        raise RuntimeError("PRIVATE WHEEL SOURCE AND FILESYSTEM PATH")
    service.list = failing_inventory
    with TestClient(create_app(execution_packages=service), raise_server_exceptions=False) as http:
        response = http.get("/api/execution-plugin-packages")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "PRIVATE" not in response.text
    assert "PRIVATE" not in caplog.text
