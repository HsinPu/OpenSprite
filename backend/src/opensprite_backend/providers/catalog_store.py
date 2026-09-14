"""Strict non-secret custom-provider catalog with optimistic concurrency."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from opensprite_backend.atomic_file import atomic_write
from .catalog_models import BUILTIN_PROVIDER_IDS, canonical_base_url, provider_name, valid_provider_id


class CatalogError(Exception):
    def __init__(self, code: str = "provider_store_unavailable") -> None:
        self.code = code
        super().__init__(code)


class CustomModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    key: str
    model_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    context_limit: int = Field(ge=1024)
    output_limit: int = Field(ge=1)
    tools: bool = False
    source: Literal["manual", "discovered"] = "manual"

    @model_validator(mode="after")
    def validate_model(self) -> CustomModel:
        if not valid_provider_id(self.key) or self.key in BUILTIN_PROVIDER_IDS:
            raise ValueError("invalid_model_key")
        if self.model_id != self.model_id.strip() or self.output_limit > self.context_limit:
            raise ValueError("invalid_model")
        return self


class CustomProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: str
    name: str
    revision: int = Field(ge=1)
    protocol: Literal["openai_chat_completions"] = "openai_chat_completions"
    base_url: str
    auth_mode: Literal["none", "bearer"]
    allow_insecure_local: bool = False
    non_streaming_tools: bool = False
    tools_enabled: bool = True
    created_at: str
    updated_at: str
    models: tuple[CustomModel, ...] = ()

    def allows_model_tools(self, model: CustomModel) -> bool:
        """Model tools=True inherits; False is a preserved individual opt-out."""
        return self.tools_enabled and model.tools

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return provider_name(value)

    @model_validator(mode="after")
    def validate_provider(self) -> CustomProvider:
        from datetime import datetime

        if not valid_provider_id(self.id) or self.id in BUILTIN_PROVIDER_IDS:
            raise ValueError("invalid_provider_id")
        if canonical_base_url(self.base_url, allow_insecure_local=self.allow_insecure_local) != self.base_url:
            raise ValueError("noncanonical_base_url")
        for value in (self.created_at, self.updated_at):
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError("invalid_timestamp")
        if len({item.key for item in self.models}) != len(self.models) or len({item.model_id for item in self.models}) != len(self.models):
            raise ValueError("duplicate_model")
        return self


class ProviderCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: Literal[1] = 1
    revision: int = Field(ge=0, default=0)
    providers: tuple[CustomProvider, ...] = ()

    @model_validator(mode="after")
    def unique_providers(self) -> ProviderCatalog:
        if len({p.id for p in self.providers}) != len(self.providers):
            raise ValueError("duplicate_provider")
        names = [p.name.casefold() for p in self.providers]
        if len(set(names)) != len(names) or set(names) & BUILTIN_PROVIDER_IDS:
            raise ValueError("duplicate_name")
        return self


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


class JsonProviderCatalog:
    """One runtime-owned instance serializes catalog compare-and-swap writes."""
    def __init__(self, path: Path) -> None:
        self.path = path
        self.gate = RLock()

    def get(self) -> ProviderCatalog:
        with self.gate:
            try:
                with self.path.open("rb") as stream:
                    data = stream.read(16 * 1024 * 1024 + 1)
                if len(data) > 16 * 1024 * 1024:
                    raise ValueError("oversized_catalog")
                json.loads(data.decode("utf-8"), object_pairs_hook=_strict_pairs)
                return ProviderCatalog.model_validate_json(data)
            except FileNotFoundError:
                return ProviderCatalog()
            except Exception:
                raise CatalogError from None

    def replace(self, catalog: ProviderCatalog, *, expected_revision: int) -> None:
        with self.gate:
            if type(expected_revision) is not int or self.get().revision != expected_revision:
                raise CatalogError("revision_conflict")
            if catalog.revision != expected_revision + 1:
                raise CatalogError("invalid_request")
            try:
                payload = catalog.model_dump_json().encode("utf-8")
                ProviderCatalog.model_validate_json(payload)
                if len(payload) > 16 * 1024 * 1024:
                    raise ValueError("oversized_catalog")
                atomic_write(self.path, payload)
            except Exception:
                raise CatalogError from None
