"""Installed desktop runtime serves the built frontend without changing APIs."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.installed_runtime import (
    create_installed_app,
    default_frontend_dist,
)


def frontend_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html><body><div id="root">OpenSprite</div></body></html>',
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text(
        'document.title = "OpenSprite";',
        encoding="utf-8",
    )
    return dist


def test_installed_app_serves_frontend_and_preserves_api_priority(
    tmp_path: Path,
) -> None:
    app = create_installed_app(
        frontend_dist=frontend_dist(tmp_path),
        system_app_factory=create_app,
    )

    with TestClient(app) as client:
        index = client.get("/")
        asset = client.get("/assets/app.js")
        health = client.get("/healthz")

    assert index.status_code == 200
    assert index.headers["content-type"].startswith("text/html")
    assert "OpenSprite" in index.text
    assert asset.status_code == 200
    assert asset.text == 'document.title = "OpenSprite";'
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_installed_app_rejects_missing_or_incomplete_frontend(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()

    with pytest.raises(RuntimeError, match="frontend distribution"):
        create_installed_app(
            frontend_dist=missing,
            system_app_factory=create_app,
        )
    with pytest.raises(RuntimeError, match="frontend distribution"):
        create_installed_app(
            frontend_dist=incomplete,
            system_app_factory=create_app,
        )


def test_default_frontend_dist_is_below_repository_or_install_root() -> None:
    expected = Path(__file__).parents[2] / "frontend" / "dist"

    assert default_frontend_dist() == expected.resolve(strict=False)
