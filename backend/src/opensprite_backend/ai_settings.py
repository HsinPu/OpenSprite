"""Strict persisted AI settings for the local backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Final, Protocol

from .app_paths import AppPaths
from .models import AiSettings, ErrorCode
from .provider_connections import ProviderConnectionError, ProviderConnections

_SCHEMA_VERSION: Final = 6
_PREVIOUS_SCHEMA_VERSION: Final = 5
_LEGACY_SCHEMA_VERSION: Final = 4
_OLDEST_SCHEMA_VERSION: Final = 3
_MAX_SETTINGS_BYTES: Final = 1024 * 1024


class SettingsStoreError(Exception):
    """Sanitized failure for unavailable or malformed local settings."""

    def __init__(self) -> None:
        super().__init__("AI settings are unavailable.")


class AiSettingsStore(Protocol):
    def get(self) -> AiSettings: ...

    def set(self, settings: AiSettings) -> None: ...


class AiSettingsOperations(Protocol):
    async def get(self) -> AiSettings: ...

    async def put(self, payload: AiSettings) -> AiSettings: ...


def default_ai_settings() -> AiSettings:
    return AiSettings(
        model=None,
        responseMode="default",
        autoContinueOutput=True,
        logFullPrompts=False,
    )


class JsonAiSettingsStore:
    """Persist one fixed-schema AI settings record atomically."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> AiSettings:
        raw = self._read()
        return self._decode(raw) if raw is not None else default_ai_settings()

    def set(self, settings: AiSettings) -> None:
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                **settings.model_dump(mode="json", by_alias=True),
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
        if failed or len(data) > _MAX_SETTINGS_BYTES:
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

    @staticmethod
    def _decode(raw: object) -> AiSettings:
        if (
            type(raw) is not dict
            or type(raw.get("version")) is not int
            or not {"model", "responseMode"}.issubset(raw)
        ):
            raise SettingsStoreError
        model = raw["model"]
        auto_continue_output: object
        if raw["version"] == _OLDEST_SCHEMA_VERSION:
            if set(raw) != {"version", "model", "responseMode"}:
                raise SettingsStoreError
            if model is not None:
                if type(model) is not dict or set(model) != {
                    "providerId",
                    "modelId",
                    "contextBudget",
                }:
                    raise SettingsStoreError
                model = {**model, "outputBudget": "auto"}
            auto_continue_output = True
            log_full_prompts = False
        elif raw["version"] == _LEGACY_SCHEMA_VERSION:
            if set(raw) != {"version", "model", "responseMode"}:
                raise SettingsStoreError
            auto_continue_output = True
            log_full_prompts = False
        elif raw["version"] == _PREVIOUS_SCHEMA_VERSION:
            if set(raw) != {"version", "model", "responseMode"}:
                raise SettingsStoreError
            auto_continue_output = True
            log_full_prompts = False
        elif raw["version"] == _SCHEMA_VERSION:
            if set(raw) != {
                "version",
                "model",
                "responseMode",
                "autoContinueOutput",
                "logFullPrompts",
            }:
                raise SettingsStoreError
            auto_continue_output = raw["autoContinueOutput"]
            log_full_prompts = raw["logFullPrompts"]
        else:
            raise SettingsStoreError
        failed = False
        settings: AiSettings | None = None
        try:
            settings = AiSettings.model_validate(
                {
                    "model": model,
                    "responseMode": raw["responseMode"],
                    "autoContinueOutput": auto_continue_output,
                    "logFullPrompts": log_full_prompts,
                }
            )
        except Exception:
            failed = True
        if failed or settings is None:
            raise SettingsStoreError
        return settings

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


class UnavailableAiSettings:
    """Fail closed when AI settings storage is not explicitly composed."""

    async def get(self) -> AiSettings:
        raise SettingsStoreError

    async def put(self, payload: AiSettings) -> AiSettings:
        del payload
        raise SettingsStoreError


class AiSettingsService:
    """Persist AI settings after validating any selected provider."""

    def __init__(
        self,
        store: AiSettingsStore,
        provider_connections: ProviderConnections,
    ) -> None:
        self._store = store
        self._provider_connections = provider_connections

    async def get(self) -> AiSettings:
        return self._store.get()

    async def put(self, payload: AiSettings) -> AiSettings:
        if payload.model is not None:
            providers = await self._provider_connections.list_providers()
            if not any(
                provider.id == payload.model.provider_id and provider.connected
                for provider in providers.providers
            ):
                raise ProviderConnectionError(ErrorCode.NOT_CONNECTED)
        self._store.set(payload)
        return payload


def create_ai_settings_service(
    app_paths: AppPaths,
    provider_connections: ProviderConnections,
) -> AiSettingsService:
    """Compose AI settings persistence from the local data root."""

    return AiSettingsService(
        JsonAiSettingsStore(app_paths.settings_file),
        provider_connections,
    )
