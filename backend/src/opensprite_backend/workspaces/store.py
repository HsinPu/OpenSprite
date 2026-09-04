"""Strict, atomic persistence for the Workspace catalog."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Final, Protocol
import unicodedata
from uuid import UUID

from opensprite_backend.atomic_file import atomic_write

from .models import UNASSIGNED_WORKSPACE_ID, WorkspaceCatalogState, WorkspaceRecord
from .policy import WorkspaceRootPolicy


_SCHEMA_VERSION: Final = 1
_MAX_BYTES: Final = 1024 * 1024
_MAX_WORKSPACES: Final = 100


class WorkspaceStoreError(Exception):
    def __init__(self) -> None:
        super().__init__("Workspace settings are unavailable.")


class WorkspaceStore(Protocol):
    def get(self) -> WorkspaceCatalogState: ...

    def set(self, catalog: WorkspaceCatalogState) -> None: ...


def empty_catalog() -> WorkspaceCatalogState:
    return WorkspaceCatalogState(
        revision=0,
        active_workspace_id=UNASSIGNED_WORKSPACE_ID,
        workspaces=(),
    )


class JsonWorkspaceStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> WorkspaceCatalogState:
        raw = self._read()
        return empty_catalog() if raw is None else self._decode(raw)

    def set(self, catalog: WorkspaceCatalogState) -> None:
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                "revision": catalog.revision,
                "activeWorkspaceId": catalog.active_workspace_id,
                "workspaces": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "rootPath": item.root_path,
                        "revision": item.revision,
                        "createdAt": self._timestamp(item.created_at),
                        "updatedAt": self._timestamp(item.updated_at),
                    }
                    for item in catalog.workspaces
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_BYTES:
            raise WorkspaceStoreError
        try:
            atomic_write(self._path, payload)
        except Exception:
            raise WorkspaceStoreError from None

    def _read(self) -> object | None:
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_BYTES + 1)
        except FileNotFoundError:
            return None
        except Exception:
            raise WorkspaceStoreError from None
        if len(data) > _MAX_BYTES:
            raise WorkspaceStoreError
        try:
            return json.loads(
                data.decode("utf-8"),
                object_pairs_hook=self._without_duplicate_keys,
            )
        except Exception:
            raise WorkspaceStoreError from None

    @classmethod
    def _decode(cls, raw: object) -> WorkspaceCatalogState:
        if type(raw) is not dict or set(raw) != {
            "version",
            "revision",
            "activeWorkspaceId",
            "workspaces",
        }:
            raise WorkspaceStoreError
        if raw["version"] != _SCHEMA_VERSION or type(raw["version"]) is not int:
            raise WorkspaceStoreError
        revision = raw["revision"]
        active = raw["activeWorkspaceId"]
        items = raw["workspaces"]
        if type(revision) is not int or revision < 0 or not cls._identifier(active):
            raise WorkspaceStoreError
        if type(items) is not list or len(items) > _MAX_WORKSPACES:
            raise WorkspaceStoreError
        decoded: list[WorkspaceRecord] = []
        identifiers: set[str] = set()
        names: set[str] = set()
        roots: set[str] = set()
        for item in items:
            record = cls._workspace(item)
            name_key = record.name.casefold()
            root_key = WorkspaceRootPolicy.comparison_key(record.root_path)
            if (
                record.id == UNASSIGNED_WORKSPACE_ID
                or record.id in identifiers
                or name_key in names
                or root_key in roots
            ):
                raise WorkspaceStoreError
            identifiers.add(record.id)
            names.add(name_key)
            roots.add(root_key)
            decoded.append(record)
        if active != UNASSIGNED_WORKSPACE_ID and active not in identifiers:
            raise WorkspaceStoreError
        return WorkspaceCatalogState(revision, active, tuple(decoded))

    @classmethod
    def _workspace(cls, raw: object) -> WorkspaceRecord:
        if type(raw) is not dict or set(raw) != {
            "id",
            "name",
            "rootPath",
            "revision",
            "createdAt",
            "updatedAt",
        }:
            raise WorkspaceStoreError
        identifier = raw["id"]
        name = raw["name"]
        root = raw["rootPath"]
        revision = raw["revision"]
        if (
            not cls._identifier(identifier)
            or type(name) is not str
            or not name
            or len(name) > 80
            or name != name.strip()
            or name != unicodedata.normalize("NFC", name)
            or any(ord(character) < 32 for character in name)
            or type(root) is not str
            or not root
            or len(root) > 32_768
            or not Path(root).is_absolute()
            or any(character in root for character in ("\x00", "\r", "\n"))
            or type(revision) is not int
            or revision < 1
        ):
            raise WorkspaceStoreError
        created = cls._datetime(raw["createdAt"])
        updated = cls._datetime(raw["updatedAt"])
        if updated < created:
            raise WorkspaceStoreError
        return WorkspaceRecord(identifier, name, root, revision, created, updated)

    @staticmethod
    def _without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    @staticmethod
    def _identifier(value: object) -> bool:
        if type(value) is not str:
            return False
        try:
            parsed = UUID(value)
        except (TypeError, ValueError, AttributeError):
            return False
        return str(parsed) == value and parsed.version == 4

    @staticmethod
    def _datetime(value: object) -> datetime:
        if type(value) is not str:
            raise WorkspaceStoreError
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise WorkspaceStoreError from None
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise WorkspaceStoreError
        return parsed

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if value.tzinfo is None or value.utcoffset() is None:
            raise WorkspaceStoreError
        return value.astimezone(timezone.utc).isoformat()
