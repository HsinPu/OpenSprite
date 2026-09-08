"""Strict, atomic persistence and v1 migration for Workspace catalogs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Final, Protocol
import unicodedata
from uuid import NAMESPACE_URL, UUID, uuid5

from opensprite_backend.atomic_file import atomic_write

from .models import (
    DEFAULT_WORKSPACE_DIRECTORY,
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
    WorkspaceCatalogState,
    WorkspaceMountAccess,
    WorkspaceMountRecord,
    WorkspaceRecord,
    WorkspaceUnavailableReason,
)
from .policy import (
    InvalidWorkspaceDirectoryName,
    WorkspaceRootPolicy,
    has_unsafe_name_controls,
)


_SCHEMA_VERSION: Final = 3
_MAX_BYTES: Final = 80 * 1024 * 1024
_MAX_WORKSPACES: Final = 100
_MAX_MOUNTS: Final = 20


class WorkspaceStoreError(Exception):
    def __init__(self) -> None:
        super().__init__("Workspace settings are unavailable.")


class WorkspaceStore(Protocol):
    def get(self) -> WorkspaceCatalogState: ...

    def set(self, catalog: WorkspaceCatalogState) -> None: ...


def empty_catalog() -> WorkspaceCatalogState:
    return WorkspaceCatalogState(
        revision=0,
        active_workspace_id=DEFAULT_WORKSPACE_ID,
        workspaces=(),
    )


class JsonWorkspaceStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> WorkspaceCatalogState:
        raw = self._read()
        if raw is None:
            return empty_catalog()
        if type(raw) is not dict or type(raw.get("version")) is not int:
            raise WorkspaceStoreError
        if raw["version"] == 1:
            return self._decode_v1(raw)
        if raw["version"] in (2, _SCHEMA_VERSION):
            return self._decode_v2(raw)
        raise WorkspaceStoreError

    def set(self, catalog: WorkspaceCatalogState) -> None:
        document = {
            "version": _SCHEMA_VERSION,
            "revision": catalog.revision,
            "activeWorkspaceId": catalog.active_workspace_id,
            "defaultWorkspace": {
                "revision": catalog.default_revision,
                "mounts": [self._mount_payload(item) for item in catalog.default_mounts],
                "updatedAt": self._timestamp(catalog.default_updated_at),
            },
            "workspaces": [
                {
                    "id": item.id,
                    "name": item.name,
                    "directoryName": item.directory_name,
                    "mounts": [self._mount_payload(mount) for mount in item.mounts],
                    "revision": item.revision,
                    "createdAt": self._timestamp(item.created_at),
                    "updatedAt": self._timestamp(item.updated_at),
                }
                for item in catalog.workspaces
            ],
        }
        try:
            self._decode_v2(document)
            payload = json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except WorkspaceStoreError:
            raise
        except Exception:
            raise WorkspaceStoreError from None
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
    def _decode_v2(cls, raw: dict[str, object]) -> WorkspaceCatalogState:
        if set(raw) != {
            "version", "revision", "activeWorkspaceId", "defaultWorkspace", "workspaces"
        }:
            raise WorkspaceStoreError
        revision = raw["revision"]
        active = raw["activeWorkspaceId"]
        default = raw["defaultWorkspace"]
        items = raw["workspaces"]
        if (
            type(revision) is not int
            or revision < 0
            or not cls._identifier(active)
            or type(default) is not dict
            or set(default) != {"revision", "mounts", "updatedAt"}
            or type(default["revision"]) is not int
            or default["revision"] < 1
            or type(items) is not list
            or len(items) > _MAX_WORKSPACES
        ):
            raise WorkspaceStoreError
        default_mounts = cls._mounts(default["mounts"])
        decoded: list[WorkspaceRecord] = []
        identifiers: set[str] = set()
        names: set[str] = set()
        directories: set[str] = set()
        for item in items:
            record = cls._workspace_v2(item)
            name_key = record.name.casefold()
            directory_key = record.directory_name.casefold()
            if (
                record.id == DEFAULT_WORKSPACE_ID
                or record.id in identifiers
                or name_key == DEFAULT_WORKSPACE_NAME.casefold()
                or name_key in names
                or directory_key == DEFAULT_WORKSPACE_DIRECTORY.casefold()
                or directory_key in directories
            ):
                raise WorkspaceStoreError
            identifiers.add(record.id)
            names.add(name_key)
            directories.add(directory_key)
            decoded.append(record)
        if active != DEFAULT_WORKSPACE_ID and active not in identifiers:
            raise WorkspaceStoreError
        return WorkspaceCatalogState(
            revision=revision,
            active_workspace_id=active,
            workspaces=tuple(decoded),
            default_revision=default["revision"],
            default_mounts=default_mounts,
            default_updated_at=cls._datetime(default["updatedAt"]),
            source_version=raw["version"],
        )

    @classmethod
    def _decode_v1(cls, raw: dict[str, object]) -> WorkspaceCatalogState:
        if set(raw) != {"version", "revision", "activeWorkspaceId", "workspaces"}:
            raise WorkspaceStoreError
        revision = raw["revision"]
        active = raw["activeWorkspaceId"]
        items = raw["workspaces"]
        if (
            type(revision) is not int
            or revision < 0
            or not cls._identifier(active)
            or type(items) is not list
            or len(items) > _MAX_WORKSPACES
        ):
            raise WorkspaceStoreError
        legacy = [cls._workspace_v1(item) for item in items]
        identifiers = {item[0] for item in legacy}
        names = {item[1].casefold() for item in legacy}
        roots = {WorkspaceRootPolicy.comparison_key(item[2]) for item in legacy}
        if (
            len(identifiers) != len(legacy)
            or len(names) != len(legacy)
            or len(roots) != len(legacy)
            or DEFAULT_WORKSPACE_ID in identifiers
        ):
            raise WorkspaceStoreError
        if active != DEFAULT_WORKSPACE_ID and active not in identifiers:
            raise WorkspaceStoreError
        conflicting: set[str] = set()
        for index, left in enumerate(legacy):
            for right in legacy[index + 1 :]:
                if WorkspaceRootPolicy.paths_overlap(left[2], right[2]):
                    conflicting.update((left[0], right[0]))
        used_names = {DEFAULT_WORKSPACE_NAME.casefold()}
        used_directories = {DEFAULT_WORKSPACE_DIRECTORY.casefold()}
        records: list[WorkspaceRecord] = []
        for identifier, name, root, item_revision, created, updated in legacy:
            migrated_name = cls._legacy_name(name, identifier, used_names)
            directory = cls._legacy_directory(name, identifier, used_directories)
            mount = WorkspaceMountRecord(
                id=str(uuid5(NAMESPACE_URL, f"opensprite:legacy:{identifier}:{root}")),
                alias="legacy-root",
                root_path=root,
                access_mode=WorkspaceMountAccess.READ_WRITE,
                enabled=identifier not in conflicting,
                disabled_reason=(
                    WorkspaceUnavailableReason.OVERLAP
                    if identifier in conflicting
                    else None
                ),
            )
            records.append(
                WorkspaceRecord(
                    identifier,
                    migrated_name,
                    directory,
                    (mount,),
                    item_revision,
                    created,
                    updated,
                )
            )
        return WorkspaceCatalogState(
            revision=revision,
            active_workspace_id=active,
            workspaces=tuple(records),
            source_version=1,
        )

    @classmethod
    def _workspace_v2(cls, raw: object) -> WorkspaceRecord:
        if type(raw) is not dict or set(raw) != {
            "id", "name", "directoryName", "mounts", "revision", "createdAt", "updatedAt"
        }:
            raise WorkspaceStoreError
        identifier = raw["id"]
        name = raw["name"]
        directory = raw["directoryName"]
        revision = raw["revision"]
        if (
            not cls._identifier(identifier)
            or not cls._name(name, maximum=80)
            or type(directory) is not str
            or cls._safe_directory(directory) != directory
            or type(revision) is not int
            or revision < 1
        ):
            raise WorkspaceStoreError
        created = cls._datetime(raw["createdAt"])
        updated = cls._datetime(raw["updatedAt"])
        if updated < created:
            raise WorkspaceStoreError
        return WorkspaceRecord(
            identifier,
            name,
            directory,
            cls._mounts(raw["mounts"]),
            revision,
            created,
            updated,
        )

    @classmethod
    def _workspace_v1(
        cls, raw: object
    ) -> tuple[str, str, str, int, datetime, datetime]:
        if type(raw) is not dict or set(raw) != {
            "id", "name", "rootPath", "revision", "createdAt", "updatedAt"
        }:
            raise WorkspaceStoreError
        identifier = raw["id"]
        name = raw["name"]
        root = raw["rootPath"]
        revision = raw["revision"]
        if (
            not cls._identifier(identifier)
            or not cls._legacy_name_valid(name, maximum=80)
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
        return identifier, name, root, revision, created, updated

    @classmethod
    def _mounts(cls, raw: object) -> tuple[WorkspaceMountRecord, ...]:
        if type(raw) is not list or len(raw) > _MAX_MOUNTS:
            raise WorkspaceStoreError
        mounts = tuple(cls._mount(item) for item in raw)
        if len({item.id for item in mounts}) != len(mounts):
            raise WorkspaceStoreError
        if len({item.alias.casefold() for item in mounts}) != len(mounts):
            raise WorkspaceStoreError
        return mounts

    @classmethod
    def _mount(cls, raw: object) -> WorkspaceMountRecord:
        if type(raw) is not dict or set(raw) != {
            "id", "alias", "rootPath", "accessMode", "enabled", "disabledReason"
        }:
            raise WorkspaceStoreError
        identifier = raw["id"]
        alias = raw["alias"]
        root = raw["rootPath"]
        access = raw["accessMode"]
        enabled = raw["enabled"]
        disabled_reason = raw["disabledReason"]
        if (
            not cls._mount_identifier(identifier)
            or not cls._name(alias, maximum=40)
            or any(character in alias for character in "/\\")
            or type(root) is not str
            or not root
            or len(root) > 32_768
            or not Path(root).is_absolute()
            or any(character in root for character in ("\x00", "\r", "\n"))
            or access not in {item.value for item in WorkspaceMountAccess}
            or type(enabled) is not bool
            or disabled_reason not in {None, WorkspaceUnavailableReason.OVERLAP.value}
            or (disabled_reason is not None and enabled)
        ):
            raise WorkspaceStoreError
        return WorkspaceMountRecord(
            identifier,
            alias,
            root,
            WorkspaceMountAccess(access),
            enabled,
            None if disabled_reason is None else WorkspaceUnavailableReason(disabled_reason),
        )

    @staticmethod
    def _mount_payload(item: WorkspaceMountRecord) -> dict[str, object]:
        return {
            "id": item.id,
            "alias": item.alias,
            "rootPath": item.root_path,
            "accessMode": item.access_mode.value,
            "enabled": item.enabled,
            "disabledReason": (
                None if item.disabled_reason is None else item.disabled_reason.value
            ),
        }

    @staticmethod
    def _name(value: object, *, maximum: int) -> bool:
        return (
            type(value) is str
            and bool(value)
            and len(value) <= maximum
            and value == value.strip()
            and value == unicodedata.normalize("NFC", value)
            and not has_unsafe_name_controls(value)
        )

    @staticmethod
    def _legacy_name_valid(value: object, *, maximum: int) -> bool:
        return (
            type(value) is str
            and bool(value)
            and len(value) <= maximum
            and value == value.strip()
            and value == unicodedata.normalize("NFC", value)
            and not any(ord(character) < 32 for character in value)
        )

    @classmethod
    def _legacy_name(
        cls, name: str, identifier: str, used: set[str]
    ) -> str:
        if cls._name(name, maximum=80) and name.casefold() not in used:
            used.add(name.casefold())
            return name
        base = f"workspace-{identifier[:8]}"
        candidate = base
        suffix = 2
        while candidate.casefold() in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate.casefold())
        return candidate

    @classmethod
    def _legacy_directory(cls, name: str, identifier: str, used: set[str]) -> str:
        try:
            candidate = WorkspaceRootPolicy.directory_name(name)
        except InvalidWorkspaceDirectoryName:
            candidate = f"workspace-{identifier[:8]}"
        if candidate.casefold() in used:
            base = f"workspace-{identifier[:8]}"
            candidate = base
            suffix = 2
            while candidate.casefold() in used:
                candidate = f"{base}-{suffix}"
                suffix += 1
        used.add(candidate.casefold())
        return candidate

    @staticmethod
    def _safe_directory(value: str) -> str | None:
        try:
            return WorkspaceRootPolicy.persisted_directory_name(value)
        except InvalidWorkspaceDirectoryName:
            return None

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
    def _mount_identifier(value: object) -> bool:
        if type(value) is not str:
            return False
        try:
            parsed = UUID(value)
        except (TypeError, ValueError, AttributeError):
            return False
        return str(parsed) == value and parsed.version in {4, 5}

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
