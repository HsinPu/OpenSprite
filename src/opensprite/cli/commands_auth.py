"""Authentication and credential command helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import typer


def _require_supported_provider(provider: str) -> None:
    if provider not in {"openai-codex", "copilot"}:
        typer.secho(
            "Error: only openai-codex and copilot auth are supported right now.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


def auth_status_command(
    *,
    provider: str,
    config: str | None,
    json_output: bool,
    resolve_app_home: Callable[[str | None], Path],
    format_presence: Callable[[bool], str],
) -> None:
    """Show provider authentication status."""
    _require_supported_provider(provider)
    app_home = resolve_app_home(config)
    if provider == "copilot":
        from ..auth.copilot import CopilotAuthError, get_copilot_status

        try:
            status = get_copilot_status(app_home)
            payload = {"provider": provider, "configured": status.configured, "path": str(status.path)}
        except CopilotAuthError as exc:
            payload = {"provider": provider, "configured": False, "error": str(exc)}
            if json_output:
                typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
                return
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        if json_output:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        typer.echo(f"Provider: {provider}")
        typer.echo(f"Configured: {format_presence(status.configured)}")
        typer.echo(f"Token file: {status.path}")
        return

    from ..auth.codex import CodexAuthError, get_codex_status

    try:
        status = get_codex_status(app_home)
        payload = {
            "provider": provider,
            "configured": status.configured,
            "path": str(status.path),
            "expires_at": status.expires_at,
            "expired": status.expired,
            "account_id": status.account_id,
        }
    except CodexAuthError as exc:
        payload = {"provider": provider, "configured": False, "error": str(exc)}
        if json_output:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    typer.echo(f"Provider: {provider}")
    typer.echo(f"Configured: {format_presence(status.configured)}")
    typer.echo(f"Token file: {status.path}")
    if status.configured:
        typer.echo(f"Expired: {format_presence(bool(status.expired))}")
        if status.expires_at is not None:
            typer.echo(f"Expires at: {status.expires_at}")
        if status.account_id:
            typer.echo(f"Account: {status.account_id}")


def auth_logout_command(*, provider: str, config: str | None, resolve_app_home: Callable[[str | None], Path]) -> None:
    """Remove stored provider credentials."""
    _require_supported_provider(provider)
    app_home = resolve_app_home(config)
    if provider == "copilot":
        from ..auth.copilot import copilot_auth_path, delete_copilot_token

        path = copilot_auth_path(app_home)
        removed = delete_copilot_token(app_home)
        typer.echo(f"Removed GitHub Copilot credentials: {path}" if removed else f"No GitHub Copilot credentials found: {path}")
        return

    from ..auth.codex import codex_auth_path, delete_codex_token

    path = codex_auth_path(app_home)
    removed = delete_codex_token(app_home)
    if removed:
        typer.echo(f"Removed OpenAI Codex credentials: {path}")
    else:
        typer.echo(f"No OpenAI Codex credentials found: {path}")


def auth_login_command(*, provider: str, config: str | None, timeout_seconds: float, resolve_app_home: Callable[[str | None], Path]) -> None:
    """Start provider login."""
    _require_supported_provider(provider)
    app_home = resolve_app_home(config)
    if provider == "copilot":
        import time
        from ..auth.copilot import (
            CopilotAuthError,
            copilot_auth_path,
            copilot_poll_device_auth,
            copilot_start_device_auth,
        )

        typer.echo("Signing in to GitHub Copilot...")
        try:
            device = copilot_start_device_auth()
            typer.echo("To continue, open this URL in your browser:")
            typer.echo(f"  {device.verification_uri}")
            typer.echo("Enter this code:")
            typer.echo(f"  {device.user_code}")
            deadline = time.monotonic() + max(1.0, float(timeout_seconds))
            while time.monotonic() < deadline:
                time.sleep(device.poll_interval)
                result = copilot_poll_device_auth(device.device_code, app_home=app_home)
                if result.status == "authorized":
                    typer.echo("Login successful.")
                    typer.echo(f"Token file: {copilot_auth_path(app_home)}")
                    return
                if result.status in {"expired_token", "access_denied"}:
                    raise CopilotAuthError(f"GitHub Copilot login failed: {result.status}")
        except CopilotAuthError as exc:
            typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        typer.secho(
            "Error: GitHub Copilot login timed out waiting for browser authorization.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    from ..auth.codex import CodexAuthError, codex_auth_path, codex_device_login

    typer.echo("Signing in to OpenAI Codex...")
    try:
        codex_device_login(app_home, timeout_seconds=timeout_seconds, announce=typer.echo)
    except CodexAuthError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Login successful.")
    typer.echo(f"Token file: {codex_auth_path(app_home)}")


def auth_credentials_list_command(
    *,
    provider: str | None,
    config: str | None,
    json_output: bool,
    resolve_app_home: Callable[[str | None], Path],
    emit_credential_listing: Callable[[dict[str, object], bool], None],
) -> None:
    """List stored API-key credentials without revealing secrets."""
    from ..auth.credentials import CredentialStoreError, list_credentials

    try:
        payload = {"credentials": list_credentials(provider, app_home=resolve_app_home(config))}
    except CredentialStoreError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    emit_credential_listing(payload, json_output)
