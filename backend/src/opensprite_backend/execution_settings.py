"""Revisioned selection of one Agent Loop, with inert legacy data migration."""
from __future__ import annotations

import asyncio
from enum import StrEnum
import json
from threading import RLock
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .agent.execution_input import ExecutionPluginError
from .execution_plugins.catalog import PluginDescriptor
from .app_paths import AppPaths
from .atomic_file import atomic_write

_MAX_SETTINGS_BYTES = 1024 * 1024
_PLUGIN_ID_PATTERN = r"^[a-z][a-z0-9_.-]{0,63}$"
_MAX_REVISION = 2**53 - 1


class ExecutionSettingsErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    PLUGIN_UNAVAILABLE = "plugin_unavailable"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    REVISION_CONFLICT = "revision_conflict"
    MIGRATION_REQUIRED = "migration_required"
    INTERNAL_ERROR = "internal_error"


class ExecutionSettingsError(Exception):
    def __init__(self, code: ExecutionSettingsErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ExecutionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)
    plugin_id: str = Field(alias="pluginId", min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)


class PutExecutionSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pluginId: str = Field(min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)
    expectedRevision: int = Field(ge=0, le=_MAX_REVISION)


class ExecutionPluginSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)
    id: str = Field(min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=2048)
    version: str = Field(min_length=1, max_length=64)
    api_version: int = Field(alias="apiVersion", ge=1)
    status: Literal["available", "incompatible", "unavailable"]


class LegacySelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    loopId: str = Field(min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)
    policyId: str = Field(min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selection: ExecutionSelection | None
    revision: int = Field(ge=0, le=_MAX_REVISION)
    migration: LegacySelection | None
    plugins: list[ExecutionPluginSummary]


class ExecutionSettingsErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ExecutionSettingsErrorCode
    message: str
    retryable: bool


class ExecutionSettingsErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ExecutionSettingsErrorDetail


class ExecutionPluginCatalog(Protocol):
    def descriptors(self) -> tuple[PluginDescriptor, ...]: ...
    def validate_selection(self, plugin_id: str) -> None: ...


class ExecutionSettingsOperations(Protocol):
    async def get(self) -> ExecutionSettings: ...
    async def update(self, plugin_id: str, expected_revision: int) -> ExecutionSettings: ...
    def selection(self) -> str: ...


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate settings field.")
        value[key] = item
    return value


class ExecutionSettingsService:
    def __init__(self, paths: AppPaths, catalog: ExecutionPluginCatalog) -> None:
        self._path = paths.execution_settings_file
        self._catalog = catalog
        self._lock = RLock()

    def _write(self, selection: ExecutionSelection, revision: int) -> None:
        payload = json.dumps({"version": 2, "revision": revision, **selection.model_dump(by_alias=True)},
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        failed = False
        try:
            atomic_write(self._path, payload)
        except Exception:
            failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE)

    def _read(self) -> tuple[ExecutionSelection | None, int, LegacySelection | None]:
        failed = False
        result = None
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_SETTINGS_BYTES + 1)
        except FileNotFoundError:
            return ExecutionSelection(pluginId="standard"), 0, None
        except Exception:
            failed = True
            data = b""
        if not failed:
            try:
                if len(data) > _MAX_SETTINGS_BYTES:
                    raise ValueError("Oversized settings.")
                raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
                if type(raw) is not dict or type(raw.get("version")) is not int:
                    raise ValueError("Invalid settings schema.")
                if raw["version"] == 1 and set(raw) == {"version", "loopId", "policyId"}:
                    legacy = LegacySelection.model_validate({key: raw[key] for key in ("loopId", "policyId")})
                    mapped = legacy.policyId if legacy.loopId == "standard" and legacy.policyId in {"standard", "no_recovery"} else None
                    if mapped is None:
                        return None, 0, legacy
                    selection = ExecutionSelection(pluginId=mapped)
                    self._write(selection, 1)
                    return selection, 1, None
                if (raw["version"] != 2 or set(raw) != {"version", "revision", "pluginId"}
                    or type(raw["revision"]) is not int or not 1 <= raw["revision"] <= _MAX_REVISION):
                    raise ValueError("Invalid settings schema.")
                result = ExecutionSelection(pluginId=raw["pluginId"]), raw["revision"], None
            except Exception:
                failed = True
        if failed or result is None:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE)
        return result

    def _validate(self, selection: ExecutionSelection) -> None:
        code = None
        try:
            self._catalog.validate_selection(selection.plugin_id)
        except ExecutionPluginError as error:
            code = ExecutionSettingsErrorCode.INVALID_REQUEST if error.code == "invalid_request" else ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE
        except Exception:
            code = ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE
        if code is not None:
            raise ExecutionSettingsError(code)

    def selection(self) -> str:
        with self._lock:
            selection, _, migration = self._read()
            if selection is None or migration is not None:
                raise ExecutionSettingsError(ExecutionSettingsErrorCode.MIGRATION_REQUIRED)
            self._validate(selection)
            return selection.plugin_id

    def _response(self, selection, revision, migration) -> ExecutionSettings:
        failed = False
        try:
            plugins = [ExecutionPluginSummary(id=item.id, name=item.name, description=item.description,
                                              version=item.version, apiVersion=item.api_version, status=item.status)
                       for item in self._catalog.descriptors()]
            if len({item.id for item in plugins}) != len(plugins):
                raise ValueError("Duplicate plugin identity.")
            result = ExecutionSettings(selection=selection, revision=revision, migration=migration, plugins=plugins)
        except Exception:
            failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)
        return result

    def _get(self) -> ExecutionSettings:
        with self._lock:
            return self._response(*self._read())

    async def get(self) -> ExecutionSettings:
        return await asyncio.to_thread(self._get)

    def _update(self, plugin_id: str, expected_revision: int) -> ExecutionSettings:
        failed = False
        try:
            request = PutExecutionSettingsRequest(pluginId=plugin_id, expectedRevision=expected_revision)
        except Exception:
            failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.INVALID_REQUEST)
        with self._lock:
            _, current_revision, _ = self._read()
            if request.expectedRevision != current_revision or current_revision == _MAX_REVISION:
                raise ExecutionSettingsError(ExecutionSettingsErrorCode.REVISION_CONFLICT)
            selection = ExecutionSelection(pluginId=request.pluginId)
            self._validate(selection)
            result = self._response(selection, current_revision + 1, None)
            self._write(selection, result.revision)
            return result

    async def update(self, plugin_id: str, expected_revision: int) -> ExecutionSettings:
        return await asyncio.to_thread(self._update, plugin_id, expected_revision)


class UnavailableExecutionSettings:
    async def get(self) -> ExecutionSettings:
        raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)

    async def update(self, plugin_id: str, expected_revision: int) -> ExecutionSettings:
        raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)

    def selection(self) -> str:
        raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)
