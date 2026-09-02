"""Strict persisted settings and catalog for production Agent tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Protocol

from .app_paths import AppPaths
from .atomic_file import atomic_write
from .models import ToolListResponse, ToolSettings, ToolSummary
from .tools.availability import ToolAvailabilitySnapshot
from .tools.registry import ToolRegistry


_SCHEMA_VERSION: Final = 1
_MAX_SETTINGS_BYTES: Final = 1024 * 1024


class ToolSettingsStoreError(Exception):
    """Sanitized failure for unavailable or malformed tool settings."""

    def __init__(self) -> None:
        super().__init__("Tool settings are unavailable.")


class ToolNotFoundError(Exception):
    """A syntactically valid tool id is not in the production registry."""


class ToolSettingsStore(Protocol):
    def get(self) -> ToolSettings: ...

    def set(self, settings: ToolSettings) -> None: ...


class ToolSettingsOperations(Protocol):
    async def list_tools(self) -> ToolListResponse: ...

    async def get(self) -> ToolSettings: ...

    async def put(self, payload: ToolSettings) -> ToolSettings: ...

    async def snapshot(self) -> ToolAvailabilitySnapshot: ...


def default_tool_settings() -> ToolSettings:
    return ToolSettings(enabled=True, enabledTools=["calculator"])


class JsonToolSettingsStore:
    """Persist one fixed-schema tool settings record atomically."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> ToolSettings:
        raw = self._read()
        return self._decode(raw) if raw is not None else default_tool_settings()

    def set(self, settings: ToolSettings) -> None:
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                **settings.model_dump(mode="json", by_alias=True),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_SETTINGS_BYTES:
            raise ToolSettingsStoreError
        try:
            atomic_write(self._path, payload)
        except Exception as error:
            raise ToolSettingsStoreError from error

    def _read(self) -> object | None:
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_SETTINGS_BYTES + 1)
        except FileNotFoundError:
            return None
        except Exception as error:
            raise ToolSettingsStoreError from error
        if len(data) > _MAX_SETTINGS_BYTES:
            raise ToolSettingsStoreError
        try:
            return json.loads(
                data.decode("utf-8"),
                object_pairs_hook=self._object_without_duplicate_keys,
            )
        except Exception as error:
            raise ToolSettingsStoreError from error

    @staticmethod
    def _object_without_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value

    @staticmethod
    def _decode(raw: object) -> ToolSettings:
        if (
            type(raw) is not dict
            or set(raw) != {"version", "enabled", "enabledTools"}
            or type(raw["version"]) is not int
            or raw["version"] != _SCHEMA_VERSION
        ):
            raise ToolSettingsStoreError
        try:
            return ToolSettings.model_validate(
                {
                    "enabled": raw["enabled"],
                    "enabledTools": raw["enabledTools"],
                }
            )
        except Exception as error:
            raise ToolSettingsStoreError from error


class UnavailableToolSettings:
    async def list_tools(self) -> ToolListResponse:
        raise ToolSettingsStoreError

    async def get(self) -> ToolSettings:
        raise ToolSettingsStoreError

    async def put(self, payload: ToolSettings) -> ToolSettings:
        del payload
        raise ToolSettingsStoreError

    async def snapshot(self) -> ToolAvailabilitySnapshot:
        raise ToolSettingsStoreError


class ToolSettingsService:
    def __init__(self, store: ToolSettingsStore, registry: ToolRegistry) -> None:
        self._store = store
        self._registry = registry

    async def list_tools(self) -> ToolListResponse:
        return ToolListResponse(
            items=[
                ToolSummary(
                    id=definition.name,
                    source=definition.source.value,
                    effect=definition.effect.value,
                    available=True,
                )
                for definition in self._registry.definitions()
            ]
        )

    async def get(self) -> ToolSettings:
        settings = self._store.get()
        if not self._known(set(settings.enabledTools)):
            raise ToolSettingsStoreError
        return self._normalized(settings)

    async def put(self, payload: ToolSettings) -> ToolSettings:
        if not self._known(set(payload.enabledTools)):
            raise ToolNotFoundError
        confirmed = self._normalized(payload)
        self._store.set(confirmed)
        return confirmed

    async def snapshot(self) -> ToolAvailabilitySnapshot:
        settings = await self.get()
        return ToolAvailabilitySnapshot(
            frozenset(settings.enabledTools if settings.enabled else ())
        )

    def _known(self, names: set[str]) -> bool:
        registered = {definition.name for definition in self._registry.definitions()}
        return names.issubset(registered)

    @staticmethod
    def _normalized(settings: ToolSettings) -> ToolSettings:
        return ToolSettings(
            enabled=settings.enabled,
            enabledTools=sorted(settings.enabledTools),
        )


def create_tool_settings_service(
    app_paths: AppPaths,
    registry: ToolRegistry,
) -> ToolSettingsService:
    return ToolSettingsService(
        JsonToolSettingsStore(app_paths.tool_settings_file),
        registry,
    )
