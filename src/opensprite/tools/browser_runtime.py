"""Runtime helpers for local browser automation tools."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class BrowserRuntimeError(RuntimeError):
    """Raised when browser automation cannot run."""


class AgentBrowserRuntime:
    """Small wrapper around the `agent-browser` CLI JSON interface."""

    def __init__(
        self,
        *,
        command_timeout: int = 30,
        session_timeout: int = 300,
        command: str | None = None,
        cdp_url: str | None = None,
    ):
        self.command_timeout = max(1, int(command_timeout or 30))
        self.session_timeout = max(1, int(session_timeout or 300))
        self.command = str(command or "").strip()
        self.cdp_url = str(cdp_url or "").strip()

    async def run(self, *, session_key: str, command: str, args: list[str] | None = None, timeout: int | None = None) -> dict[str, Any]:
        backend_args = ["--session", _browser_session_name(session_key)]
        if self.cdp_url:
            backend_args = ["--cdp", await self._resolve_cdp_url()]
        argv = [
            *self._command_prefix(),
            *backend_args,
            "--json",
            command,
            *(args or []),
        ]
        return await self._run_subprocess(argv, timeout or self.command_timeout)

    async def _resolve_cdp_url(self) -> str:
        return await resolve_cdp_url(self.cdp_url, timeout=self.command_timeout)

    def _command_prefix(self) -> list[str]:
        if self.command:
            return [self.command]

        agent_browser = shutil.which("agent-browser") or _local_agent_browser_path()
        if agent_browser:
            return [agent_browser]

        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if npx:
            return [npx, "agent-browser"]

        raise BrowserRuntimeError(
            "agent-browser CLI was not found. Install it with `npm install` in the repo root "
            "or `npm install -g agent-browser && agent-browser install`."
        )

    async def _run_subprocess(self, argv: list[str], timeout: int) -> dict[str, Any]:
        try:
            env = os.environ.copy()
            env.setdefault("AGENT_BROWSER_IDLE_TIMEOUT_MS", str(self.session_timeout * 1000))
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as exc:
            raise BrowserRuntimeError(str(exc)) from exc

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=max(1, timeout))
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"success": False, "error": f"browser command timed out after {timeout}s"}

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        payload = _parse_json_payload(stdout_text)
        if payload is not None:
            if proc.returncode and "success" not in payload:
                payload["success"] = False
            if stderr_text and "stderr" not in payload:
                payload["stderr"] = stderr_text[-1200:]
            return payload

        if proc.returncode:
            return {
                "success": False,
                "error": stderr_text or stdout_text or f"browser command exited with code {proc.returncode}",
            }
        return {"success": True, "output": stdout_text}


def _local_agent_browser_path() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    bin_dir = repo_root / "node_modules" / ".bin"
    for name in ("agent-browser.cmd", "agent-browser.exe", "agent-browser"):
        candidate = bin_dir / name
        if candidate.exists():
            return str(candidate)
    return ""


def _browser_session_name(session_key: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(session_key or "default")).strip("_")
    return f"opensprite_{normalized or 'default'}"[:80]


def _parse_json_payload(text: str) -> dict[str, Any] | None:
    for line in reversed([line.strip() for line in str(text or "").splitlines() if line.strip()]):
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        return payload if isinstance(payload, dict) else None
    return None


async def resolve_cdp_url(raw_url: str, *, timeout: int = 30) -> str:
    """Resolve an HTTP CDP discovery URL into a browser WebSocket URL when possible."""
    raw = str(raw_url or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith(("ws://", "wss://")) and "/devtools/browser/" in lowered:
        return raw
    discovery_url = _cdp_discovery_url(raw)
    if not discovery_url:
        return raw
    try:
        async with httpx.AsyncClient(timeout=max(1, int(timeout or 30)), follow_redirects=True) as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return raw
    if isinstance(payload, dict):
        ws_url = str(payload.get("webSocketDebuggerUrl") or "").strip()
        if ws_url:
            return ws_url
    return raw


def _cdp_discovery_url(raw_url: str) -> str:
    raw = str(raw_url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw if parsed.path.endswith("/json/version") else raw.rstrip("/") + "/json/version"
    if parsed.scheme in {"ws", "wss"} and parsed.netloc and not parsed.path.strip("/"):
        scheme = "http" if parsed.scheme == "ws" else "https"
        return f"{scheme}://{parsed.netloc}/json/version"
    return ""
