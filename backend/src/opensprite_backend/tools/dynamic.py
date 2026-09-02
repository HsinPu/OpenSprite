"""Dynamic Tool providers used to build one immutable Run registry."""

from __future__ import annotations

from typing import Protocol

from .definition import Tool


class DynamicToolProvider(Protocol):
    async def snapshot_tools(self) -> tuple[Tool, ...]: ...
