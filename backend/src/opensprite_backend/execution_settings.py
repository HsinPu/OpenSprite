"""Persisted selection of trusted execution-loop and policy plugins."""

from __future__ import annotations

from enum import StrEnum
import json
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .agent.plugin_catalog import ExecutionPluginError, PluginDescriptor
from .app_paths import AppPaths
from .atomic_file import atomic_write

_MAX_SETTINGS_BYTES = 1024 * 1024
_PLUGIN_ID_PATTERN = r"^[a-z][a-z0-9_.-]{0,63}$"


class ExecutionSettingsErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    PLUGIN_UNAVAILABLE = "plugin_unavailable"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class ExecutionSettingsError(Exception):
    """A public failure code without paths or plugin implementation details."""

    def __init__(self, code: ExecutionSettingsErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ExecutionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)

    loop_id: str = Field(alias="loopId", strict=True, min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)
    policy_id: str = Field(alias="policyId", strict=True, min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)


class PutExecutionSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    loopId: str = Field(strict=True, min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)
    policyId: str = Field(strict=True, min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)


class ExecutionPluginSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)

    id: str = Field(strict=True, min_length=1, max_length=64, pattern=_PLUGIN_ID_PATTERN)
    kind: Literal["loop", "policy"]
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=2048)
    version: str = Field(min_length=1, max_length=128)
    api_version: int = Field(alias="apiVersion", strict=True, ge=1)
    status: Literal["available", "incompatible", "unavailable"]


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    selection: ExecutionSelection
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

    def validate_selection(self, loop_id: str, policy_id: str) -> None: ...


class ExecutionSettingsOperations(Protocol):
    async def get(self) -> ExecutionSettings: ...

    async def update(self, loop_id: str, policy_id: str) -> ExecutionSettings: ...

    def selection(self) -> tuple[str, str]: ...


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate settings field.")
        value[key] = item
    return value


class ExecutionSettingsService:
    """Read lazily and atomically write a fixed-schema pair of plugin IDs."""

    def __init__(self, paths: AppPaths, catalog: ExecutionPluginCatalog) -> None:
        self._path = paths.execution_settings_file
        self._catalog = catalog

    def _read(self) -> ExecutionSelection:
        failed = False
        raw: object = None
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_SETTINGS_BYTES + 1)
        except FileNotFoundError:
            return ExecutionSelection(loopId="standard", policyId="standard")
        except Exception:
            failed = True
            data = b""
        if not failed:
            try:
                if len(data) > _MAX_SETTINGS_BYTES:
                    raise ValueError("Oversized settings.")
                raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
                if type(raw) is not dict or set(raw) != {"version", "loopId", "policyId"} or type(raw["version"]) is not int or raw["version"] != 1:
                    raise ValueError("Invalid settings schema.")
                selection = ExecutionSelection.model_validate({"loopId": raw["loopId"], "policyId": raw["policyId"]})
            except Exception:
                failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE)
        return selection

    def _validate(self, selection: ExecutionSelection) -> None:
        code: ExecutionSettingsErrorCode | None = None
        try:
            self._catalog.validate_selection(selection.loop_id, selection.policy_id)
        except ExecutionPluginError as error:
            code = ExecutionSettingsErrorCode.INVALID_REQUEST if error.code == "invalid_request" else ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE
        except Exception:
            code = ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE
        if code is not None:
            raise ExecutionSettingsError(code)

    def selection(self) -> tuple[str, str]:
        selection = self._read()
        self._validate(selection)
        return selection.loop_id, selection.policy_id

    def _response(self, selection: ExecutionSelection) -> ExecutionSettings:
        failed = False
        try:
            plugins = [ExecutionPluginSummary(
                id=item.id, kind=item.kind, name=item.name, description=item.description,
                version=item.version, apiVersion=item.api_version, status=item.status,
            ) for item in self._catalog.descriptors()]
            identities = {(item.kind, item.id) for item in plugins}
            if len(identities) != len(plugins):
                raise ValueError("Duplicate plugin identity.")
            result = ExecutionSettings(selection=selection, plugins=plugins)
        except Exception:
            failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)
        return result

    async def get(self) -> ExecutionSettings:
        return self._response(self._read())

    async def update(self, loop_id: str, policy_id: str) -> ExecutionSettings:
        failed = False
        try:
            selection = ExecutionSelection(loopId=loop_id, policyId=policy_id)
        except Exception:
            failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.INVALID_REQUEST)
        self._validate(selection)
        # Resolve the catalog before writing so a broken catalog cannot save settings.
        result = self._response(selection)
        payload = json.dumps({"version": 1, **selection.model_dump(by_alias=True)}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        failed = False
        try:
            atomic_write(self._path, payload)
        except Exception:
            failed = True
        if failed:
            raise ExecutionSettingsError(ExecutionSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE)
        return result


class UnavailableExecutionSettings:
    async def get(self) -> ExecutionSettings:
        raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)

    async def update(self, loop_id: str, policy_id: str) -> ExecutionSettings:
        del loop_id, policy_id
        raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)

    def selection(self) -> tuple[str, str]:
        raise ExecutionSettingsError(ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE)
