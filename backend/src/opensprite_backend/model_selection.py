"""Strict persisted default-model selection for the local backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Final, Protocol

from .app_paths import AppPaths
from .models import ModelSelection, ModelSelectionResponse, PutModelSelectionRequest
from .provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
)
from .models import ErrorCode

_SCHEMA_VERSION: Final = 1
_MAX_SETTINGS_BYTES: Final = 1024 * 1024
_PROVIDERS: Final = frozenset({"openai", "anthropic", "openrouter"})


class SettingsStoreError(Exception):
    """Sanitized failure for unavailable or malformed local settings."""

    def __init__(self) -> None:
        super().__init__("Model selection settings are unavailable.")


class ModelSelectionStore(Protocol):
    def get(self) -> ModelSelection | None: ...

    def set(self, selection: ModelSelection | None) -> None: ...


class ModelSelections(Protocol):
    async def get(self) -> ModelSelectionResponse: ...

    async def put(
        self,
        payload: PutModelSelectionRequest,
    ) -> ModelSelectionResponse: ...


class JsonModelSelectionStore:
    """Persist the one fixed-schema model-selection record atomically."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> ModelSelection | None:
        raw = self._read()
        return self._decode(raw) if raw is not None else None

    def set(self, selection: ModelSelection | None) -> None:
        if selection is None:
            self._clear()
            return
        self._validate_selection(selection)
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                "defaultModel": selection.model_dump(by_alias=True),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_SETTINGS_BYTES:
            raise SettingsStoreError
        self._atomic_write(payload)

    def _read(self) -> object | None:
        failed = False
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_SETTINGS_BYTES + 1)
        except FileNotFoundError:
            return None
        except Exception:
            failed = True
            data = b""
        if failed:
            raise SettingsStoreError
        if len(data) > _MAX_SETTINGS_BYTES:
            raise SettingsStoreError
        failed = False
        raw: object = None
        try:
            raw = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=self._object_without_duplicate_keys,
            )
        except Exception:
            failed = True
        if failed:
            raise SettingsStoreError
        return raw

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

    def _decode(self, raw: object) -> ModelSelection:
        if (
            type(raw) is not dict
            or set(raw) != {"version", "defaultModel"}
            or type(raw["version"]) is not int
            or raw["version"] != _SCHEMA_VERSION
            or type(raw["defaultModel"]) is not dict
        ):
            raise SettingsStoreError
        default_model = raw["defaultModel"]
        if set(default_model) != {"providerId", "modelId"}:
            raise SettingsStoreError
        failed = False
        selection: ModelSelection | None = None
        try:
            selection = ModelSelection.model_validate(default_model)
        except Exception:
            failed = True
        if failed or selection is None:
            raise SettingsStoreError
        self._validate_selection(selection)
        return selection

    @staticmethod
    def _validate_selection(selection: ModelSelection) -> None:
        if (
            selection.provider_id not in _PROVIDERS
            or type(selection.model_id) is not str
            or not selection.model_id.strip()
        ):
            raise SettingsStoreError

    def _clear(self) -> None:
        failed = False
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            failed = True
        if failed:
            raise SettingsStoreError

    def _atomic_write(self, payload: bytes) -> None:
        temporary_path: Path | None = None
        file_descriptor: int | None = None
        failed = False
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            file_descriptor, temporary_name = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(file_descriptor, "wb") as stream:
                file_descriptor = None
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except Exception:
            failed = True
        finally:
            if file_descriptor is not None:
                try:
                    os.close(file_descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
        if failed:
            raise SettingsStoreError


class UnavailableModelSelections:
    """Fail closed when selection storage is not explicitly composed."""

    @staticmethod
    def _unavailable() -> SettingsStoreError:
        return SettingsStoreError()

    async def get(self) -> ModelSelectionResponse:
        raise self._unavailable()

    async def put(
        self,
        payload: PutModelSelectionRequest,
    ) -> ModelSelectionResponse:
        del payload
        raise self._unavailable()


class ModelSelectionService:
    """Validate default selection against connected provider summaries only."""

    def __init__(
        self,
        store: ModelSelectionStore,
        provider_connections: ProviderConnections,
    ) -> None:
        self._store = store
        self._provider_connections = provider_connections

    async def get(self) -> ModelSelectionResponse:
        return ModelSelectionResponse(selection=self._store.get())

    async def put(
        self,
        payload: PutModelSelectionRequest,
    ) -> ModelSelectionResponse:
        selection = payload.selection
        if selection is not None:
            providers = await self._provider_connections.list_providers()
            if not any(
                provider.id == selection.provider_id and provider.connected
                for provider in providers.providers
            ):
                raise ProviderConnectionError(ErrorCode.NOT_CONNECTED)
        self._store.set(selection)
        return ModelSelectionResponse(selection=selection)


def create_model_selection_service(
    app_paths: AppPaths,
    provider_connections: ProviderConnections,
) -> ModelSelectionService:
    """Compose settings persistence from the existing local data root."""

    return ModelSelectionService(
        JsonModelSelectionStore(app_paths.settings_file),
        provider_connections,
    )
