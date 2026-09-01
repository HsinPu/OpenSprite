"""Strict persisted conversation startup and send settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Protocol

from .app_paths import AppPaths
from .atomic_file import atomic_write
from .models import ConversationSettings


_SCHEMA_VERSION: Final = 3
_PREVIOUS_SCHEMA_VERSION: Final = 2
_MAX_SETTINGS_BYTES: Final = 1024 * 1024


class ConversationSettingsStoreError(Exception):
    """Sanitized failure for unavailable conversation settings."""

    def __init__(self) -> None:
        super().__init__("Conversation settings are unavailable.")


class ConversationSettingsStore(Protocol):
    def get(self) -> ConversationSettings: ...

    def set(self, settings: ConversationSettings) -> None: ...


class ConversationSettingsOperations(Protocol):
    async def get(self) -> ConversationSettings: ...

    async def put(self, payload: ConversationSettings) -> ConversationSettings: ...


def default_conversation_settings() -> ConversationSettings:
    return ConversationSettings(
        startupView="new",
        sendBehavior="enter",
        autoScroll=True,
        executionPanelDefaultExpanded=False,
    )


class JsonConversationSettingsStore:
    """Persist one fixed-schema conversation settings record atomically."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> ConversationSettings:
        raw = self._read()
        return self._decode(raw) if raw is not None else default_conversation_settings()

    def set(self, settings: ConversationSettings) -> None:
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                **settings.model_dump(mode="json", by_alias=True),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_SETTINGS_BYTES:
            raise ConversationSettingsStoreError
        self._atomic_write(payload)

    def _read(self) -> object | None:
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_SETTINGS_BYTES + 1)
        except FileNotFoundError:
            return None
        except Exception:
            raise ConversationSettingsStoreError from None
        if len(data) > _MAX_SETTINGS_BYTES:
            raise ConversationSettingsStoreError
        try:
            return json.loads(
                data.decode("utf-8"),
                object_pairs_hook=self._object_without_duplicate_keys,
            )
        except Exception:
            raise ConversationSettingsStoreError from None

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
    def _decode(raw: object) -> ConversationSettings:
        if type(raw) is not dict or type(raw.get("version")) is not int:
            raise ConversationSettingsStoreError
        if raw["version"] == _PREVIOUS_SCHEMA_VERSION:
            if set(raw) != {"version", "startupView", "sendBehavior", "autoScroll"}:
                raise ConversationSettingsStoreError
            execution_panel_default_expanded: object = False
        elif raw["version"] == _SCHEMA_VERSION:
            if set(raw) != {
                "version",
                "startupView",
                "sendBehavior",
                "autoScroll",
                "executionPanelDefaultExpanded",
            }:
                raise ConversationSettingsStoreError
            execution_panel_default_expanded = raw[
                "executionPanelDefaultExpanded"
            ]
        else:
            raise ConversationSettingsStoreError
        try:
            return ConversationSettings.model_validate(
                {
                    "startupView": raw["startupView"],
                    "sendBehavior": raw["sendBehavior"],
                    "autoScroll": raw["autoScroll"],
                    "executionPanelDefaultExpanded": execution_panel_default_expanded,
                }
            )
        except Exception:
            raise ConversationSettingsStoreError from None

    def _atomic_write(self, payload: bytes) -> None:
        try:
            atomic_write(self._path, payload)
        except Exception:
            raise ConversationSettingsStoreError from None


class UnavailableConversationSettings:
    async def get(self) -> ConversationSettings:
        raise ConversationSettingsStoreError

    async def put(self, payload: ConversationSettings) -> ConversationSettings:
        del payload
        raise ConversationSettingsStoreError


class ConversationSettingsService:
    def __init__(self, store: ConversationSettingsStore) -> None:
        self._store = store

    async def get(self) -> ConversationSettings:
        return self._store.get()

    async def put(self, payload: ConversationSettings) -> ConversationSettings:
        self._store.set(payload)
        return payload


def create_conversation_settings_service(
    app_paths: AppPaths,
) -> ConversationSettingsService:
    return ConversationSettingsService(
        JsonConversationSettingsStore(app_paths.conversation_settings_file)
    )
