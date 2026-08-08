import asyncio
import json

from opensprite.config.schema import BrowserToolConfig
from opensprite.app.tools.web.browser import (
    BrowserClickTool,
    BrowserConsoleTool,
    BrowserNavigateTool,
    BrowserSnapshotTool,
    BrowserTypeTool,
)


class _FakeRuntime:
    def __init__(self):
        self.calls = []

    async def run(self, *, session_key, command, args=None, timeout=None):
        self.calls.append({"session_key": session_key, "command": command, "args": list(args or []), "timeout": timeout})
        return {"success": True, "data": {"command": command}}


def test_browser_navigate_uses_current_session_and_open_command():
    runtime = _FakeRuntime()
    tool = BrowserNavigateTool(
        runtime=runtime,
        get_session_id=lambda: "web:browser-1",
        browser_config=BrowserToolConfig(enabled=True),
    )

    result = json.loads(asyncio.run(tool.execute(url="https://example.com")))

    assert result["success"] is True
    assert result["type"] == "browser_navigate"
    assert runtime.calls == [
        {
            "session_key": "web:browser-1",
            "command": "open",
            "args": ["https://example.com"],
            "timeout": 60,
        }
    ]


def test_browser_snapshot_uses_compact_mode_by_default():
    runtime = _FakeRuntime()
    tool = BrowserSnapshotTool(runtime=runtime, get_session_id=lambda: None)

    result = json.loads(asyncio.run(tool.execute()))

    assert result["type"] == "browser_snapshot"
    assert runtime.calls[0] == {"session_key": "default", "command": "snapshot", "args": ["-c"], "timeout": None}


def test_browser_click_and_type_normalize_refs():
    runtime = _FakeRuntime()

    click = BrowserClickTool(runtime=runtime, get_session_id=lambda: "s")
    fill = BrowserTypeTool(runtime=runtime, get_session_id=lambda: "s")

    asyncio.run(click.execute(ref="e2"))
    asyncio.run(fill.execute(ref="@e3", text="hello"))

    assert runtime.calls[0]["args"] == ["@e2"]
    assert runtime.calls[1]["args"] == ["@e3", "hello"]


def test_browser_navigate_blocks_private_urls_by_default():
    runtime = _FakeRuntime()
    tool = BrowserNavigateTool(runtime=runtime, browser_config=BrowserToolConfig(enabled=True))

    result = json.loads(asyncio.run(tool.execute(url="http://127.0.0.1:8765")))

    assert result == {
        "type": "browser_navigate",
        "success": False,
        "error": "Blocked: URL targets a private or internal host.",
    }
    assert runtime.calls == []


def test_browser_navigate_allows_private_urls_when_configured():
    runtime = _FakeRuntime()
    tool = BrowserNavigateTool(
        runtime=runtime,
        browser_config=BrowserToolConfig(enabled=True, allow_private_urls=True),
    )

    result = json.loads(asyncio.run(tool.execute(url="http://127.0.0.1:8765")))

    assert result["success"] is True
    assert runtime.calls[0]["args"] == ["http://127.0.0.1:8765"]


def test_browser_navigate_blocks_secret_bearing_urls():
    runtime = _FakeRuntime()
    tool = BrowserNavigateTool(runtime=runtime, browser_config=BrowserToolConfig(enabled=True))

    result = json.loads(asyncio.run(tool.execute(url="https://example.com/?api_key=secret-token-value")))

    assert result == {
        "type": "browser_navigate",
        "success": False,
        "error": "Blocked: URL appears to contain a secret or credential.",
    }
    assert runtime.calls == []


def test_browser_console_reads_or_evaluates_page_context():
    runtime = _FakeRuntime()
    tool = BrowserConsoleTool(runtime=runtime, browser_config=BrowserToolConfig(enabled=True))

    asyncio.run(tool.execute(clear=True))
    asyncio.run(tool.execute(expression="document.title"))

    assert runtime.calls[0]["command"] == "console"
    assert runtime.calls[0]["args"] == ["--clear"]
    assert runtime.calls[1]["command"] == "eval"
    assert runtime.calls[1]["args"] == ["document.title"]
