"""Skills policy, safe disk discovery, and recoverable file/catalog mutations."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from pydantic import ValidationError
from opensprite_backend.app_paths import AppPaths
from opensprite_backend.atomic_file import atomic_write
from opensprite_backend.workspaces import WorkspaceAvailability, WorkspaceRootPolicy
from opensprite_backend.workspaces.relocation import require_plain_directory, ensure_plain_directory, WorkspaceRelocationError
from .format import parse
from .models import SkillCatalog, SkillRecord, SkillError, SkillContent, SkillExecutionSnapshot


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SkillError("store_unavailable")
        result[key] = value
    return result


class SkillsService:
    def __init__(self, paths: AppPaths, workspaces):
        self.paths = paths
        self.workspaces = workspaces
        self.lock = RLock()

    def _base(self, scope: str, workspace_id: str | None) -> Path:
        if scope == "global" and workspace_id is None:
            return self.paths.skills_dir
        if scope != "workspace" or workspace_id is None:
            raise SkillError("invalid_request")
        try:
            workspace = self.workspaces.execution_context(workspace_id)
        except Exception:
            raise SkillError("workspace_unavailable") from None
        if workspace.availability is not WorkspaceAvailability.AVAILABLE or workspace.root_path is None:
            raise SkillError("workspace_unavailable")
        return Path(workspace.root_path) / "skills"

    def _path(self, item: SkillRecord) -> Path:
        try:
            segment = WorkspaceRootPolicy.directory_name(item.directoryName)
        except ValueError:
            raise SkillError("unsafe_path") from None
        return self._base(item.scope, item.workspaceId) / segment / "SKILL.md"

    @staticmethod
    def _safe_file(path: Path, *, missing: bool = False) -> None:
        try:
            for node in (path.parent, *path.parent.parents):
                if node.exists() or node.is_symlink():
                    require_plain_directory(node)
            if path.is_symlink() or (path.exists() and WorkspaceRootPolicy._is_reparse_point(path)):
                raise SkillError("unsafe_path")
            if not missing and not path.is_file():
                raise SkillError("missing")
        except (OSError, ValueError, RuntimeError, WorkspaceRelocationError):
            raise SkillError("unsafe_path") from None

    def _read_file(self, item: SkillRecord) -> str:
        path = self._path(item)
        self._safe_file(path)
        try:
            with path.open("rb") as stream:
                data = stream.read(65537)
            if len(data) > 65536:
                raise SkillError("content_too_large")
            return data.decode("utf-8")
        except UnicodeError:
            raise SkillError("invalid_format") from None
        except OSError:
            raise SkillError("missing") from None

    def _read_json(self, path: Path):
        self._safe_file(path)
        with path.open("rb") as stream:
            data = stream.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise SkillError("store_unavailable")
        return json.loads(data, object_pairs_hook=unique)

    def _validate(self, raw) -> SkillCatalog:
        catalog = SkillCatalog.model_validate(raw)
        ids, names, directories, counts = set(), set(), set(), {}
        for item in catalog.skills:
            if not 1 <= len(item.name) <= 80 or item.name != unicodedata.normalize("NFC", item.name).strip() or len(item.description) > 500:
                raise ValueError
            if any(unicodedata.category(c) in {"Cc", "Cs"} for c in item.name):
                raise ValueError
            UUID(item.id)
            if item.scope == "workspace":
                UUID(item.workspaceId)
            elif item.workspaceId is not None:
                raise ValueError
            WorkspaceRootPolicy.directory_name(item.directoryName)
            group = (item.scope, item.workspaceId)
            name = (*group, item.name.casefold())
            directory = (*group, item.directoryName.casefold())
            counts[group] = counts.get(group, 0) + 1
            if item.id in ids or name in names or directory in directories or counts[group] > 100:
                raise ValueError
            if item.confirmedHash is not None and (len(item.confirmedHash) != 64 or any(c not in "0123456789abcdef" for c in item.confirmedHash)):
                raise ValueError
            for identifier in item.disabledWorkspaces:
                UUID(identifier)
            ids.add(item.id); names.add(name); directories.add(directory)
        return catalog

    def _recover(self) -> None:
        journal = self.paths.skills_transaction_file
        if not journal.exists():
            return
        tx = self._read_json(journal)
        if type(tx) is not dict or set(tx) != {"version", "catalog", "record", "content", "archive"} or tx["version"] != 1:
            raise SkillError("store_unavailable")
        catalog = self._validate(tx["catalog"])
        item = SkillRecord.model_validate(tx["record"])
        path = self._path(item)
        self._safe_file(path, missing=True)
        if tx["archive"] is not None:
            UUID(tx["archive"])
            archive = self.paths.skills_archive_dir / tx["archive"]
            ensure_plain_directory(archive.parent)
            if path.parent.exists():
                if archive.exists():
                    raise SkillError("store_unavailable")
                require_plain_directory(path.parent)
                path.parent.rename(archive)
            elif archive.exists():
                require_plain_directory(archive)
        else:
            parse(tx["content"])
            ensure_plain_directory(path.parent)
            atomic_write(path, tx["content"].encode("utf-8"))
        atomic_write(self.paths.skills_settings_file, catalog.model_dump_json().encode())
        journal.unlink()

    def _catalog(self) -> SkillCatalog:
        try:
            self._recover()
            if not self.paths.skills_settings_file.exists():
                return SkillCatalog()
            return self._validate(self._read_json(self.paths.skills_settings_file))
        except Exception:
            raise SkillError("store_unavailable") from None

    def _write(self, catalog: SkillCatalog) -> None:
        try:
            self._validate(catalog.model_dump())
            self._safe_file(self.paths.skills_settings_file, missing=True)
            atomic_write(self.paths.skills_settings_file, catalog.model_dump_json().encode())
        except Exception:
            raise SkillError("store_unavailable") from None

    @staticmethod
    def _expected(catalog, expected):
        if type(expected) is not int or expected != catalog.revision:
            raise SkillError("revision_conflict")

    @staticmethod
    def _find(catalog, identifier):
        item = next((item for item in catalog.skills if item.id == identifier), None)
        if item is None:
            raise SkillError("not_found")
        return item

    def _view(self, catalog, item, workspace_id=None, *, content=False):
        raw, digest, state = None, None, "disabled"
        name, description = item.name, item.description
        try:
            raw = self._read_file(item)
            name, description, _, digest = parse(raw)
            state = "ready" if item.enabled and digest == item.confirmedHash else "pending" if digest != item.confirmedHash else "disabled"
        except SkillError as error:
            state = error.code
        reason = state
        if state == "ready":
            reason = "master_disabled" if not catalog.enabled else "workspace_disabled" if workspace_id in item.disabledWorkspaces else "ready"
        result = {**item.model_dump(), "name": name, "description": description, "contentHash": digest, "state": state, "effective": reason == "ready", "reason": reason}
        if content:
            result["content"] = raw
        return result

    def settings(self):
        with self.lock:
            cat = self._catalog()
            return {"enabled": cat.enabled, "revision": cat.revision}

    def list(self, scope, workspace_id=None):
        with self.lock:
            if scope not in {"global", "workspace"} or (scope == "workspace" and workspace_id is None):
                raise SkillError("invalid_request")
            cat = self._catalog()
            items = [i for i in cat.skills if i.scope == scope and (scope == "global" or i.workspaceId == workspace_id)]
            return {"revision": cat.revision, "enabled": cat.enabled, "skills": [self._view(cat, i, workspace_id) for i in items]}

    def get(self, identifier):
        with self.lock:
            cat = self._catalog()
            return {"revision": cat.revision, "skill": self._view(cat, self._find(cat, identifier), content=True)}

    def save(self, *, scope, workspace_id, content, expected, identifier=None):
        with self.lock:
            cat = self._catalog(); self._expected(cat, expected)
            name, description, _, _ = parse(content)
            current = self._find(cat, identifier) if identifier else None
            if current:
                scope, workspace_id = current.scope, current.workspaceId
            peers = [i for i in cat.skills if i.scope == scope and i.workspaceId == workspace_id and i.id != identifier]
            if any(i.name.casefold() == name.casefold() for i in peers):
                raise SkillError("duplicate_name")
            if len(peers) >= 100:
                raise SkillError("limit_reached")
            try:
                directory = current.directoryName if current else WorkspaceRootPolicy.directory_name(name)
            except ValueError:
                raise SkillError("unsafe_path") from None
            item = SkillRecord(id=identifier or str(uuid4()), scope=scope, workspaceId=workspace_id, directoryName=directory, name=name, description=description, revision=current.revision + 1 if current else 1, disabledWorkspaces=current.disabledWorkspaces if current else [])
            path = self._path(item); self._safe_file(path, missing=True)
            if not current and path.parent.exists():
                raise SkillError("directory_exists")
            cat.skills = [i for i in cat.skills if i.id != item.id] + [item]; cat.revision += 1
            self._transaction(cat, item, content=content)
            return self.get(item.id)

    def _transaction(self, catalog, item, *, content=None, archive=None):
        try:
            self._validate(catalog.model_dump())
            self._safe_file(self.paths.skills_transaction_file, missing=True)
            atomic_write(self.paths.skills_transaction_file, json.dumps({"version": 1, "catalog": catalog.model_dump(), "record": item.model_dump(), "content": content, "archive": archive}).encode())
            self._recover()
        except Exception:
            raise SkillError("store_unavailable") from None

    def configure(self, *, expected, enabled=None, identifier=None, confirmed_hash=None, workspace_id=None, disabled=None):
        with self.lock:
            cat = self._catalog(); self._expected(cat, expected)
            if identifier is None:
                cat.enabled = enabled
            else:
                item = self._find(cat, identifier)
                if disabled is not None:
                    if item.scope != "global":
                        raise SkillError("invalid_request")
                    try:
                        self.workspaces.execution_context(workspace_id)
                    except Exception:
                        raise SkillError("workspace_unavailable") from None
                    item.disabledWorkspaces = sorted(set(item.disabledWorkspaces) | {workspace_id}) if disabled else [i for i in item.disabledWorkspaces if i != workspace_id]
                else:
                    if enabled:
                        name, description, _, digest = parse(self._read_file(item))
                        if digest != confirmed_hash:
                            raise SkillError("content_changed")
                        if any(i.id != item.id and i.scope == item.scope and i.workspaceId == item.workspaceId and i.name.casefold() == name.casefold() for i in cat.skills):
                            raise SkillError("duplicate_name")
                        item.name, item.description, item.confirmedHash = name, description, digest
                    item.enabled = enabled
                item.revision += 1
            cat.revision += 1; self._write(cat)
            return {"enabled": cat.enabled, "revision": cat.revision}

    def delete(self, identifier, expected):
        with self.lock:
            cat = self._catalog(); self._expected(cat, expected)
            item = self._find(cat, identifier)
            cat.skills = [i for i in cat.skills if i.id != identifier]; cat.revision += 1
            self._transaction(cat, item, archive=str(uuid4()))

    def scan(self, scope, workspace_id, expected):
        with self.lock:
            cat = self._catalog(); self._expected(cat, expected)
            base = self._base(scope, workspace_id)
            if not base.exists():
                return self.list(scope, workspace_id)
            try:
                require_plain_directory(base)
                peers = [i for i in cat.skills if i.scope == scope and i.workspaceId == workspace_id]
                for child in sorted(base.iterdir()):
                    if not child.is_dir() or not child.joinpath("SKILL.md").exists():
                        continue
                    if any(i.directoryName.casefold() == child.name.casefold() for i in peers):
                        continue
                    if len(peers) >= 100:
                        raise SkillError("limit_reached")
                    try:
                        directory = WorkspaceRootPolicy.directory_name(child.name)
                        item = SkillRecord(id=str(uuid4()), scope=scope, workspaceId=workspace_id, directoryName=directory, name=directory, description="", revision=1)
                        require_plain_directory(child)
                        try:
                            name, description, _, _ = parse(self._read_file(item))
                        except SkillError as error:
                            if error.code not in {"invalid_format", "content_too_large"} or len(directory) > 80:
                                raise
                            name, description = directory, ""
                        if any(i.name.casefold() == name.casefold() for i in peers):
                            continue
                        item.name, item.description = name, description
                    except (SkillError, ValueError, WorkspaceRelocationError):
                        continue
                    peers.append(item); cat.skills.append(item)
                cat.revision += 1; self._write(cat)
                return self.list(scope, workspace_id)
            except OSError:
                raise SkillError("unsafe_path") from None

    def snapshot(self, workspace_id, selected=()) -> SkillExecutionSnapshot:
        with self.lock:
            try:
                cat = self._catalog()
            except SkillError:
                if selected:
                    raise SkillError("skill_unavailable") from None
                return SkillExecutionSnapshot()
            contents = []
            if cat.enabled:
                for item in cat.skills:
                    if not item.enabled or workspace_id in item.disabledWorkspaces or (item.scope == "workspace" and item.workspaceId != workspace_id):
                        continue
                    try:
                        name, description, body, digest = parse(self._read_file(item))
                        if digest == item.confirmedHash:
                            contents.append(SkillContent(item.id, item.scope, name, description, item.revision, digest, body))
                    except SkillError:
                        continue
            result = SkillExecutionSnapshot(tuple(contents), tuple(selected))
            if len(selected) > 5 or len(set(selected)) != len(selected):
                raise SkillError("invalid_request")
            for identifier in selected:
                result.get(identifier)
            return result

    def forget_workspace(self, workspace_id):
        with self.lock:
            cat = self._catalog()
            cat.skills = [i for i in cat.skills if i.workspaceId != workspace_id]
            for item in cat.skills:
                item.disabledWorkspaces = [i for i in item.disabledWorkspaces if i != workspace_id]
            cat.revision += 1; self._write(cat)
