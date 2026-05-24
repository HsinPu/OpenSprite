"""Update command implementation helpers."""

from __future__ import annotations

from typing import Any, Callable

import typer


def update_command(
    *,
    branch: str,
    check: bool,
    dev: bool,
    restart: bool,
    update_cli_module: Any,
    use_linux_service: Callable[[], bool],
    service_linux_module: Any,
    service_background_module: Any,
    handle_service_error: Callable[[Exception], None],
) -> None:
    """Update a source-checkout OpenSprite install."""
    try:
        if check:
            count = update_cli_module.check_update_available(branch=branch)
            if count:
                typer.echo(f"Update available: {count} commit(s) behind origin/{branch}.")
            else:
                typer.echo("OpenSprite is up to date.")
            return

        typer.echo("Updating OpenSprite...")
        result = update_cli_module.update_checkout(branch=branch, install_dev=dev)
    except update_cli_module.UpdateError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if result.updated:
        typer.echo(f"Updated {result.before_rev[:7]} -> {result.after_rev[:7]} on {result.branch}.")
    else:
        typer.echo(f"Already up to date on {result.branch}.")
    typer.echo(f"Project: {result.project_root}")
    typer.echo(f"Python: {result.python_executable}")
    if result.frontend_build == "built":
        typer.echo("Web frontend: built")

    if restart:
        try:
            if use_linux_service():
                service_linux_module.restart_service()
                typer.echo("Restarted OpenSprite service.")
            else:
                try:
                    service_background_module.stop_service()
                except FileNotFoundError:
                    pass
                status = service_background_module.start_service()
                typer.echo(f"Restarted OpenSprite background gateway (PID {status.pid}).")
                typer.echo(f"Log: {status.log_file}")
        except (FileNotFoundError, RuntimeError) as exc:
            handle_service_error(exc)
