"""Immutable per-Run tool availability boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ToolAvailabilitySnapshot:
    enabled_names: frozenset[str]

    def allows(self, name: str) -> bool:
        return name in self.enabled_names


class ToolAvailabilityProvider(Protocol):
    async def snapshot(self) -> ToolAvailabilitySnapshot: ...
