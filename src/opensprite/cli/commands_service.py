"""Background service command helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import typer


def service_install_command(
    *,
    config: str | None,
    start: bool,
    resolve_config_path: Callable[[str | None], Path],
    service_linux_module: Any,
    handle_service_error: Callable[[Exception], None],
) -> None:
    """Install OpenSprite as a Linux systemd user service."""
    try:
        config_path = resolve_config_path(config)
        service_file = service_linux_module.install_service(config_path, start=start)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        handle_service_error(exc)

    typer.echo(f"Installed service: {service_file}")
    typer.echo(f"Config: {config_path}")
    typer.echo(f"Started: {'yes' if start else 'no'}")
    typer.echo("Tip: run `loginctl enable-linger $USER` if you want the user service to stay up after logout.")


def service_uninstall_command(*, service_linux_module: Any, handle_service_error: Callable[[Exception], None]) -> None:
    """Uninstall the OpenSprite Linux systemd user service."""
    try:
        removed = service_linux_module.uninstall_service()
    except RuntimeError as exc:
        handle_service_error(exc)

    if removed:
        typer.echo("Removed OpenSprite service.")
    else:
        typer.echo("OpenSprite service is not installed.")


def service_start_command(
    *,
    config: str | None,
    use_linux_service: bool,
    service_linux_module: Any,
    service_background_module: Any,
    handle_service_error: Callable[[Exception], None],
) -> None:
    """Start the OpenSprite gateway in the background."""
    try:
        if use_linux_service:
            service_linux_module.start_service()
            typer.echo("Started OpenSprite service.")
            return
        status = service_background_module.start_service(config_path=Path(config) if config else None)
    except (FileNotFoundError, RuntimeError) as exc:
        handle_service_error(exc)
    typer.echo(f"Started OpenSprite background gateway (PID {status.pid}).")
    typer.echo(f"Log: {status.log_file}")


def service_stop_command(
    *,
    use_linux_service: bool,
    service_linux_module: Any,
    service_background_module: Any,
    handle_service_error: Callable[[Exception], None],
) -> None:
    """Stop the OpenSprite background gateway."""
    try:
        if use_linux_service:
            service_linux_module.stop_service()
        else:
            service_background_module.stop_service()
    except (FileNotFoundError, RuntimeError) as exc:
        handle_service_error(exc)
    typer.echo("Stopped OpenSprite service.")


def service_restart_command(
    *,
    config: str | None,
    use_linux_service: bool,
    service_linux_module: Any,
    service_background_module: Any,
    handle_service_error: Callable[[Exception], None],
) -> None:
    """Restart the OpenSprite background gateway."""
    try:
        if use_linux_service:
            service_linux_module.restart_service()
            typer.echo("Restarted OpenSprite service.")
            return
        try:
            service_background_module.stop_service()
        except FileNotFoundError:
            pass
        status = service_background_module.start_service(config_path=Path(config) if config else None)
    except (FileNotFoundError, RuntimeError) as exc:
        handle_service_error(exc)
    typer.echo(f"Restarted OpenSprite background gateway (PID {status.pid}).")
    typer.echo(f"Log: {status.log_file}")


def service_status_command(
    *,
    use_linux_service: bool,
    service_linux_module: Any,
    service_background_module: Any,
    format_presence: Callable[[bool], str],
    handle_service_error: Callable[[Exception], None],
) -> None:
    """Show OpenSprite background gateway status."""
    try:
        if use_linux_service:
            status = service_linux_module.get_service_status()
            typer.echo("OpenSprite Service")
            typer.echo(f"Service File: {status.service_file}")
            typer.echo(f"Installed: {format_presence(status.installed)}")
            typer.echo(f"Enabled: {format_presence(status.enabled)}")
            typer.echo(f"Active: {format_presence(status.active)}")
            return
        status = service_background_module.get_service_status()
    except RuntimeError as exc:
        handle_service_error(exc)

    typer.echo("OpenSprite Service")
    typer.echo("Mode: detached process")
    typer.echo(f"Active: {format_presence(status.running)}")
    typer.echo(f"PID: {status.pid or '<none>'}")
    typer.echo(f"PID File: {status.pid_file}")
    typer.echo(f"Log: {status.log_file}")
