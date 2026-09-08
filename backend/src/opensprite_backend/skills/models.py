"""Strict persisted policy and immutable per-run instruction snapshots."""
from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class SkillError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SkillRecord(StrictModel):
    id: str
    scope: Literal["global", "workspace"]
    workspaceId: str | None
    directoryName: str
    name: str
    description: str
    revision: int = Field(ge=1)
    enabled: bool = False
    confirmedHash: str | None = None


class SkillCatalog(StrictModel):
    version: Literal[3] = 3
    revision: int = Field(default=0, ge=0)
    enabled: bool = True
    skills: list[SkillRecord] = Field(default_factory=list)


class LegacySkillRecord(SkillRecord):
    disabledWorkspaces: list[str] = Field(default_factory=list)


class LegacySkillCatalog(StrictModel):
    version: Literal[1, 2]
    revision: int = Field(default=0, ge=0)
    enabled: bool = True
    skills: list[LegacySkillRecord] = Field(default_factory=list)


@dataclass(frozen=True)
class SkillContent:
    id: str
    scope: str
    name: str
    description: str
    revision: int
    content_hash: str
    body: str = field(repr=False)


@dataclass(frozen=True)
class SkillExecutionSnapshot:
    available: tuple[SkillContent, ...] = ()
    selected_ids: tuple[str, ...] = ()

    def get(self, identifier: str) -> SkillContent:
        item = next((item for item in self.available if item.id == identifier), None)
        if item is None:
            raise SkillError("skill_unavailable")
        return item
