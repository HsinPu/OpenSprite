import asyncio

import pytest

from opensprite.integrations.browser.provider_base import (
    BrowserRuntimeError,
    CloudBrowserSession,
)
from opensprite.integrations.browser.runtime import AgentBrowserRuntime


class _FakeCloudProvider:
    def __init__(self):
        self.create_calls = []

    async def create_session(self, *, session_key, session_timeout, timeout):
        self.create_calls.append({"session_key": session_key, "session_timeout": session_timeout, "timeout": timeout})
        return CloudBrowserSession(
            provider_session_id="provider-session-1",
            cdp_url="ws://cloud.example/devtools/browser/abc",
            expires_at=999999999.0,
        )

    async def close_session(self, provider_session_id, *, timeout):
        return True


def test_agent_browser_runtime_builds_json_command(monkeypatch):
    runtime = AgentBrowserRuntime(command="agent-browser", command_timeout=9)
    captured = {}

    async def fake_run(argv, timeout):
        captured["argv"] = argv
        captured["timeout"] = timeout
        return {"success": True}

    monkeypatch.setattr(runtime, "_run_subprocess", fake_run)

    result = asyncio.run(runtime.run(session_key="web:browser-1", command="open", args=["https://example.com"]))

    assert result == {"success": True}
    assert captured == {
        "argv": [
            "agent-browser",
            "--session",
            "opensprite_web_browser-1",
            "--json",
            "open",
            "https://example.com",
        ],
        "timeout": 9,
    }


def test_agent_browser_runtime_uses_cdp_backend_without_session(monkeypatch):
    runtime = AgentBrowserRuntime(command="agent-browser", command_timeout=9, cdp_url="http://127.0.0.1:9222")
    captured = {}

    async def fake_resolve():
        return "ws://127.0.0.1:9222/devtools/browser/abc"

    async def fake_run(argv, timeout):
        captured["argv"] = argv
        captured["timeout"] = timeout
        return {"success": True}

    monkeypatch.setattr(runtime, "_resolve_cdp_url", fake_resolve)
    monkeypatch.setattr(runtime, "_run_subprocess", fake_run)

    result = asyncio.run(runtime.run(session_key="web:browser-1", command="open", args=["https://example.com"]))

    assert result == {"success": True}
    assert captured == {
        "argv": [
            "agent-browser",
            "--cdp",
            "ws://127.0.0.1:9222/devtools/browser/abc",
            "--json",
            "open",
            "https://example.com",
        ],
        "timeout": 9,
    }


def test_agent_browser_runtime_passes_launch_args_for_managed_session(monkeypatch):
    runtime = AgentBrowserRuntime(command="agent-browser", command_timeout=9, launch_args="--no-sandbox")
    captured = {}

    async def fake_run(argv, timeout):
        captured["argv"] = argv
        captured["timeout"] = timeout
        return {"success": True}

    monkeypatch.setattr(runtime, "_run_subprocess", fake_run)

    result = asyncio.run(runtime.run(session_key="web:browser-1", command="open", args=["https://example.com"]))

    assert result == {"success": True}
    assert captured == {
        "argv": [
            "agent-browser",
            "--args",
            "--no-sandbox",
            "--session",
            "opensprite_web_browser-1",
            "--json",
            "open",
            "https://example.com",
        ],
        "timeout": 9,
    }


def test_agent_browser_runtime_uses_cloud_provider_cdp_session(monkeypatch):
    cloud_provider = _FakeCloudProvider()
    runtime = AgentBrowserRuntime(
        command="agent-browser",
        command_timeout=9,
        session_timeout=600,
        cloud_provider=cloud_provider,
    )
    captured = []

    async def fake_run(argv, timeout):
        captured.append({"argv": argv, "timeout": timeout})
        return {"success": True}

    monkeypatch.setattr(runtime, "_run_subprocess", fake_run)

    asyncio.run(runtime.run(session_key="web:browser-1", command="open", args=["https://example.com"]))
    asyncio.run(runtime.run(session_key="web:browser-1", command="snapshot", args=["-c"]))

    assert cloud_provider.create_calls == [
        {"session_key": "opensprite_web_browser-1", "session_timeout": 600, "timeout": 9}
    ]
    assert captured[0] == {
        "argv": [
            "agent-browser",
            "--cdp",
            "ws://cloud.example/devtools/browser/abc",
            "--json",
            "open",
            "https://example.com",
        ],
        "timeout": 9,
    }
    assert captured[1]["argv"][:4] == [
        "agent-browser",
        "--cdp",
        "ws://cloud.example/devtools/browser/abc",
        "--json",
    ]


def test_agent_browser_runtime_reports_missing_runtime(monkeypatch):
    monkeypatch.setattr("opensprite.integrations.browser.runtime.shutil.which", lambda name: None)
    monkeypatch.setattr("opensprite.integrations.browser.runtime._local_agent_browser_path", lambda: "")

    with pytest.raises(BrowserRuntimeError):
        AgentBrowserRuntime()._command_prefix()
