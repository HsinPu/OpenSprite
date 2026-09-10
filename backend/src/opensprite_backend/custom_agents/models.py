"""Strict agent registration and immutable per-parent-run policy records."""

from __future__ import annotations

from dataclasses import dataclass
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from typing import Literal
from uuid import UUID
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .definition import AgentDefinition


class AgentError(Exception):
    """Public safe error code, never definition content or a filesystem path."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AgentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str
    scope: Literal["global", "workspace"]
    workspaceId: str | None
    fileName: str
    name: str
    revision: int = Field(ge=1)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_identity(self) -> AgentRecord:
        UUID(self.id)
        if self.scope == "workspace":
            if self.workspaceId is None:
                raise ValueError("invalid_workspace")
            UUID(self.workspaceId)
        elif self.workspaceId is not None:
            raise ValueError("invalid_workspace")
        if not 1 <= len(self.name) <= 80 or self.name != unicodedata.normalize("NFC", self.name):
            raise ValueError("invalid_name")
        if not self.name.strip() or any(unicodedata.category(c) in {"Cc", "Cs"} for c in self.name):
            raise ValueError("invalid_name")
        # Import is lazy to keep this domain separate from workspace lifecycle.
        from opensprite_backend.workspaces import WorkspaceRootPolicy

        if not self.fileName.endswith(".toml"):
            raise ValueError("invalid_filename")
        WorkspaceRootPolicy.persisted_directory_name(self.fileName)
        return self


class AgentCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    enabled: bool = True
    agents: tuple[AgentRecord, ...] = ()

    @model_validator(mode="after")
    def validate_unique(self) -> AgentCatalog:
        ids: set[str] = set()
        files: set[tuple[str, str | None, str]] = set()
        for agent in self.agents:
            key = (agent.scope, agent.workspaceId, agent.fileName.casefold())
            if agent.id in ids or key in files:
                raise ValueError("duplicate_registration")
            ids.add(agent.id)
            files.add(key)
        return self


@dataclass(frozen=True, slots=True)
class AgentCandidate:
    record: AgentRecord
    definition: AgentDefinition | None
    error: str | None = None

    @property
    def name_key(self) -> str:
        name = self.definition.name if self.definition is not None else self.record.name
        return unicodedata.normalize("NFC", name).casefold()


@dataclass(frozen=True, slots=True)
class AgentDecision:
    candidate: AgentCandidate
    reason: str
    shadowed_by: str | None = None


@dataclass(frozen=True, slots=True)
class AgentExecutionSnapshot:
    available: tuple[AgentCandidate, ...] = ()
    provider_endpoints: tuple[ProviderEndpointSnapshot, ...] = ()

    def get(self, identifier: str) -> AgentCandidate:
        for item in self.available:
            if item.record.id == identifier:
                return item
        raise AgentError("agent_unavailable")
