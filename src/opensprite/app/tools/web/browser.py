"""Browser automation tools backed by agent-browser-compatible runtimes."""

from __future__ import annotations

import json
from typing import Any, Callable

from opensprite.config.schema import BrowserToolConfig
from opensprite.integrations.browser.provider_base import (
    BrowserRuntimeError as _BrowserRuntimeError,
)
from opensprite.integrations.browser.runtime import AgentBrowserRuntime as _AgentBrowserRuntime
from opensprite.modules.tools.browser_navigation import (
    validate_navigation_url as _validate_navigation_url,
)
from opensprite.modules.tools.base import Tool
from opensprite.modules.tools.validation import NON_EMPTY_STRING_PATTERN


SessionIdGetter = Callable[[], str | None]


class BrowserToolBase(Tool):
    """Shared helpers for browser tools."""

    def __init__(
        self,
        *,
        runtime: _AgentBrowserRuntime | None = None,
        get_session_id: SessionIdGetter | None = None,
        browser_config: BrowserToolConfig | None = None,
    ):
        self.runtime = runtime or _AgentBrowserRuntime()
        self.get_session_id = get_session_id or (lambda: None)
        self.browser_config = browser_config or BrowserToolConfig(enabled=True)

    def _session_key(self) -> str:
        return self.get_session_id() or "default"

    async def _run_browser(self, action: str, args: list[str] | None = None, *, timeout: int | None = None) -> str:
        try:
            payload = await self.runtime.run(
                session_key=self._session_key(),
                command=action,
                args=args or [],
                timeout=timeout,
            )
        except _BrowserRuntimeError as exc:
            payload = {"success": False, "error": str(exc)}
        payload.setdefault("type", self.name)
        return json.dumps(payload, ensure_ascii=False)


class BrowserNavigateTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_navigate"

    @property
    def description(self) -> str:
        return "Navigate the browser to a URL using the configured browser automation backend."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                    "description": "HTTP or HTTPS URL to open in the current browser session.",
                }
            },
            "required": ["url"],
        }

    async def _execute(self, **kwargs: Any) -> str:
        url = str(kwargs["url"])
        blocked = _validate_navigation_url(url, allow_private_urls=self.browser_config.allow_private_urls)
        if blocked:
            return json.dumps({"type": self.name, "success": False, "error": blocked}, ensure_ascii=False)
        return await self._run_browser("open", [url], timeout=60)


class BrowserSnapshotTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_snapshot"

    @property
    def description(self) -> str:
        return "Return a text accessibility snapshot of the current browser page."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "full": {
                    "type": "boolean",
                    "description": "Return the full snapshot instead of a compact snapshot.",
                    "default": False,
                }
            },
        }

    async def _execute(self, **kwargs: Any) -> str:
        args = [] if bool(kwargs.get("full", False)) else ["-c"]
        return await self._run_browser("snapshot", args)


class BrowserClickTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return "Click an element reference from browser_snapshot, such as @e3."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                    "description": "Element reference from browser_snapshot, for example @e3.",
                }
            },
            "required": ["ref"],
        }

    async def _execute(self, **kwargs: Any) -> str:
        ref = _normalize_ref(str(kwargs["ref"]))
        return await self._run_browser("click", [ref])


class BrowserTypeTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_type"

    @property
    def description(self) -> str:
        return "Fill text into an element reference from browser_snapshot."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                    "description": "Input element reference from browser_snapshot, for example @e5.",
                },
                "text": {"type": "string", "description": "Text to enter into the target element."},
            },
            "required": ["ref", "text"],
        }

    async def _execute(self, **kwargs: Any) -> str:
        return await self._run_browser("fill", [_normalize_ref(str(kwargs["ref"])), str(kwargs["text"])])


class BrowserPressTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_press"

    @property
    def description(self) -> str:
        return "Press a keyboard key in the current browser page, such as Enter or Tab."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                    "description": "Keyboard key to press, for example Enter, Tab, Escape, or ArrowDown.",
                }
            },
            "required": ["key"],
        }

    async def _execute(self, **kwargs: Any) -> str:
        return await self._run_browser("press", [str(kwargs["key"])])


class BrowserScrollTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_scroll"

    @property
    def description(self) -> str:
        return "Scroll the current browser page up or down."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Scroll direction.",
                }
            },
            "required": ["direction"],
        }

    async def _execute(self, **kwargs: Any) -> str:
        return await self._run_browser("scroll", [str(kwargs["direction"]), "500"])


class BrowserBackTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_back"

    @property
    def description(self) -> str:
        return "Navigate back in the current browser page history."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs: Any) -> str:
        return await self._run_browser("back", [])


class BrowserConsoleTool(BrowserToolBase):
    @property
    def name(self) -> str:
        return "browser_console"

    @property
    def description(self) -> str:
        return "Read browser console messages or evaluate a JavaScript expression in the current page."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "clear": {
                    "type": "boolean",
                    "description": "Clear console messages after reading when expression is not provided.",
                    "default": False,
                },
                "expression": {
                    "type": "string",
                    "description": "Optional JavaScript expression to evaluate in the current page.",
                },
            },
        }

    async def _execute(self, **kwargs: Any) -> str:
        expression = str(kwargs.get("expression") or "").strip()
        if expression:
            return await self._run_browser("eval", [expression])
        args = ["--clear"] if bool(kwargs.get("clear", False)) else []
        return await self._run_browser("console", args)


def _normalize_ref(ref: str) -> str:
    normalized = str(ref or "").strip()
    return normalized if normalized.startswith("@") else f"@{normalized}"
