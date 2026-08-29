"""Installed desktop composition that serves the built browser application."""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .runtime import create_system_app


SystemAppFactory = Callable[[], FastAPI]


def default_frontend_dist() -> Path:
    """Resolve the frontend build beside backend in a deployed repository tree."""

    return (
        Path(__file__).resolve().parents[3] / "frontend" / "dist"
    ).resolve(strict=False)


def create_installed_app(
    *,
    frontend_dist: str | Path | None = None,
    system_app_factory: SystemAppFactory = create_system_app,
) -> FastAPI:
    """Create the secured local runtime with the built frontend mounted last."""

    dist = (
        Path(frontend_dist).expanduser().resolve(strict=False)
        if frontend_dist is not None
        else default_frontend_dist()
    )
    if not dist.is_dir() or not (dist / "index.html").is_file():
        raise RuntimeError("OpenSprite frontend distribution is unavailable.")

    app = system_app_factory()
    app.mount(
        "/",
        StaticFiles(directory=dist, html=True, check_dir=True),
        name="frontend",
    )
    return app
