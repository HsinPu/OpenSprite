"""Strict persisted language and time-zone settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Protocol

from .app_paths import AppPaths
from .atomic_file import atomic_write
from .models import GeneralSettings

_SCHEMA_VERSION: Final = 1
_MAX_SETTINGS_BYTES: Final = 1024 * 1024


class GeneralSettingsStoreError(Exception):
    """Sanitized failure for unavailable or malformed general settings."""

    def __init__(self) -> None:
        super().__init__("General settings are unavailable.")


class GeneralSettingsStore(Protocol):
    def get(self) -> GeneralSettings: ...

    def set(self, settings: GeneralSettings) -> None: ...


class GeneralSettingsOperations(Protocol):
    async def get(self) -> GeneralSettings: ...

    async def put(self, payload: GeneralSettings) -> GeneralSettings: ...


def default_general_settings() -> GeneralSettings:
    return GeneralSettings(locale="zh-TW", timeZone="system")


class JsonGeneralSettingsStore:
    """Persist one fixed-schema general settings record atomically."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> GeneralSettings:
        raw = self._read()
        return self._decode(raw) if raw is not None else default_general_settings()

    def set(self, settings: GeneralSettings) -> None:
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                **settings.model_dump(mode="json", by_alias=True),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_SETTINGS_BYTES:
            raise GeneralSettingsStoreError
        self._atomic_write(payload)

    def _read(self) -> object | None:
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_SETTINGS_BYTES + 1)
        except FileNotFoundError:
            return None
        except Exception:
            failed = True
            data = b""
        else:
            failed = False
        if failed:
            raise GeneralSettingsStoreError
        if len(data) > _MAX_SETTINGS_BYTES:
            raise GeneralSettingsStoreError
        raw: object = None
        failed = False
        try:
            raw = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=self._object_without_duplicate_keys,
            )
        except Exception:
            failed = True
        if failed:
            raise GeneralSettingsStoreError
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
    def _decode(raw: object) -> GeneralSettings:
        if (
            type(raw) is not dict
            or set(raw) != {"version", "locale", "timeZone"}
            or type(raw["version"]) is not int
            or raw["version"] != _SCHEMA_VERSION
        ):
            raise GeneralSettingsStoreError
        settings: GeneralSettings | None = None
        failed = False
        try:
            settings = GeneralSettings.model_validate(
                {"locale": raw["locale"], "timeZone": raw["timeZone"]}
            )
        except Exception:
            failed = True
        if failed or settings is None:
            raise GeneralSettingsStoreError
        return settings

    def _atomic_write(self, payload: bytes) -> None:
        failed = False
        try:
            atomic_write(self._path, payload)
        except Exception:
            failed = True
        if failed:
            raise GeneralSettingsStoreError


class UnavailableGeneralSettings:
    async def get(self) -> GeneralSettings:
        raise GeneralSettingsStoreError

    async def put(self, payload: GeneralSettings) -> GeneralSettings:
        del payload
        raise GeneralSettingsStoreError


class GeneralSettingsService:
    def __init__(self, store: GeneralSettingsStore) -> None:
        self._store = store

    async def get(self) -> GeneralSettings:
        return self._store.get()

    async def put(self, payload: GeneralSettings) -> GeneralSettings:
        self._store.set(payload)
        return payload


def create_general_settings_service(app_paths: AppPaths) -> GeneralSettingsService:
    return GeneralSettingsService(
        JsonGeneralSettingsStore(app_paths.general_settings_file)
    )
