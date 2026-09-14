"""Strict persisted AI settings for the local backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Protocol

from .app_paths import AppPaths
from .atomic_file import atomic_write
from .models import AiSettings, ErrorCode, ProviderToolPolicy
from .provider_connections import ProviderConnectionError, ProviderConnections
from .providers.catalog_models import BUILTIN_PROVIDER_IDS
from .providers.catalog_store import CatalogError
from .providers.custom_service import CustomProviderService
from .workspaces import WorkspaceMutationGate

_SCHEMA_VERSION: Final = 9
_PREVIOUS_CANONICAL_SCHEMA_VERSION: Final = 7
_BOOLEAN_CONTINUATION_SCHEMA_VERSION: Final = 6
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

    async def put_tool_policy(self, provider_id: str, policy: ProviderToolPolicy) -> AiSettings: ...


def default_ai_settings() -> AiSettings:
    return AiSettings(
        model=None,
        responseMode="default",
        outputContinuation="5",
        responseDelivery="stream",
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
        output_continuation: object
        response_delivery: object = "stream"
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
            output_continuation = "2"
            log_full_prompts = False
        elif raw["version"] == _LEGACY_SCHEMA_VERSION:
            if set(raw) != {"version", "model", "responseMode"}:
                raise SettingsStoreError
            output_continuation = "2"
            log_full_prompts = False
        elif raw["version"] == _PREVIOUS_SCHEMA_VERSION:
            if set(raw) != {"version", "model", "responseMode"}:
                raise SettingsStoreError
            output_continuation = "2"
            log_full_prompts = False
        elif raw["version"] == _BOOLEAN_CONTINUATION_SCHEMA_VERSION:
            if set(raw) != {
                "version",
                "model",
                "responseMode",
                "autoContinueOutput",
                "logFullPrompts",
            }:
                raise SettingsStoreError
            if type(raw["autoContinueOutput"]) is not bool:
                raise SettingsStoreError
            output_continuation = "2" if raw["autoContinueOutput"] else "off"
            log_full_prompts = raw["logFullPrompts"]
        elif raw["version"] == _PREVIOUS_CANONICAL_SCHEMA_VERSION:
            if set(raw) != {
                "version",
                "model",
                "responseMode",
                "outputContinuation",
                "logFullPrompts",
            }:
                raise SettingsStoreError
            output_continuation = raw["outputContinuation"]
            response_delivery = "stream"
            log_full_prompts = raw["logFullPrompts"]
        elif raw["version"] in {8, _SCHEMA_VERSION}:
            expected = {
                "version",
                "model",
                "responseMode",
                "outputContinuation",
                "responseDelivery",
                "logFullPrompts",
            }
            if raw["version"] == _SCHEMA_VERSION:
                expected.add("providerToolPolicies")
            if set(raw) != expected:
                raise SettingsStoreError
            output_continuation = raw["outputContinuation"]
            response_delivery = raw["responseDelivery"]
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
                    "outputContinuation": output_continuation,
                    "responseDelivery": response_delivery,
                    "logFullPrompts": log_full_prompts,
                    "providerToolPolicies": raw.get("providerToolPolicies", {}),
                }
            )
        except Exception:
            failed = True
        if failed or settings is None:
            raise SettingsStoreError
        return settings

    def _atomic_write(self, payload: bytes) -> None:
        failed = False
        try:
            atomic_write(self._path, payload)
        except Exception:
            failed = True
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
        custom_providers: CustomProviderService | None = None,
        mutation_gate: WorkspaceMutationGate | None = None,
    ) -> None:
        self._store = store
        self._provider_connections = provider_connections
        self._custom_providers = custom_providers
        self._mutation_gate = mutation_gate or WorkspaceMutationGate()

    async def get(self) -> AiSettings:
        return self._store.get()

    async def put(self, payload: AiSettings) -> AiSettings:
        async with self._mutation_gate.hold():
            if "providerToolPolicies" not in payload.model_fields_set:
                payload = payload.model_copy(update={"providerToolPolicies": self._store.get().providerToolPolicies})
            return await self._put(payload)

    async def put_tool_policy(self, provider_id: str, policy: ProviderToolPolicy) -> AiSettings:
        if provider_id not in BUILTIN_PROVIDER_IDS:
            raise ProviderConnectionError(ErrorCode.INVALID_REQUEST)
        async with self._mutation_gate.hold():
            current = self._store.get()
            updated = current.model_copy(update={"providerToolPolicies": {**current.providerToolPolicies, provider_id: policy}})
            self._store.set(updated)
            return updated

    async def _put(self, payload: AiSettings) -> AiSettings:
        if payload.model is not None and payload.model.provider_id not in BUILTIN_PROVIDER_IDS:
            if self._custom_providers is None:
                raise ProviderConnectionError(ErrorCode.NOT_CONNECTED)
            try:
                provider = self._custom_providers.get(payload.model.provider_id)
            except CatalogError:
                raise ProviderConnectionError(ErrorCode.NOT_CONNECTED) from None
            if not any(model.model_id == payload.model.model_id for model in provider.models):
                raise ProviderConnectionError(ErrorCode.INVALID_REQUEST)
        elif payload.model is not None:
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
    custom_providers: CustomProviderService | None = None,
    mutation_gate: WorkspaceMutationGate | None = None,
) -> AiSettingsService:
    """Compose AI settings persistence from the local data root."""

    return AiSettingsService(
        JsonAiSettingsStore(app_paths.settings_file),
        provider_connections,
        custom_providers,
        mutation_gate,
    )
