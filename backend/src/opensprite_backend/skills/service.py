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
from .models import SkillCatalog, SkillRecord, LegacySkillCatalog, LegacySkillRecord, SkillError, SkillContent, SkillExecutionSnapshot


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
            segment = WorkspaceRootPolicy.persisted_directory_name(item.directoryName)
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
        catalog = (LegacySkillCatalog if isinstance(raw, dict) and raw.get("version") in (1, 2) else SkillCatalog).model_validate(raw)
        ids, names, directories = set(), set(), set()
        for item in catalog.skills:
            if not 1 <= len(item.name) <= 80 or item.name != unicodedata.normalize("NFC", item.name).strip():
                raise ValueError
            if any(unicodedata.category(c) in {"Cc", "Cs"} for c in item.name):
                raise ValueError
            UUID(item.id)
            if item.scope == "workspace":
                UUID(item.workspaceId)
            elif item.workspaceId is not None:
                raise ValueError
            WorkspaceRootPolicy.persisted_directory_name(item.directoryName)
            group = (item.scope, item.workspaceId)
            name = (*group, item.name.casefold())
            directory = (*group, item.directoryName.casefold())
            if item.id in ids or name in names or directory in directories:
                raise ValueError
            if item.confirmedHash is not None and (len(item.confirmedHash) != 64 or any(c not in "0123456789abcdef" for c in item.confirmedHash)):
                raise ValueError
            for identifier in getattr(item, "disabledWorkspaces", []):
                UUID(identifier)
            ids.add(item.id); names.add(name); directories.add(directory)
        return catalog

    def _recover(self) -> None:
        journal = self.paths.skills_transaction_file
        if not journal.exists():
            return
        tx = self._read_json(journal)
        if type(tx) is dict and tx.get("version") == 3:
            from .batch import recover_batch
            recover_batch(self, tx)
            return
        if type(tx) is dict and tx.get("version") == 2:
            from .folder_import import recover_package
            recover_package(self, tx)
            return
        if type(tx) is not dict or set(tx) != {"version", "catalog", "record", "content", "archive"} or tx["version"] != 1:
            raise SkillError("store_unavailable")
        catalog = self._validate(tx["catalog"])
        item = (LegacySkillRecord if catalog.version < 3 else SkillRecord).model_validate(tx["record"])
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
            catalog = self._validate(self._read_json(self.paths.skills_settings_file))
            if catalog.version < 3:
                catalog = SkillCatalog(revision=catalog.revision + 1, enabled=catalog.enabled,
                    skills=[SkillRecord.model_validate(item.model_dump(exclude={"disabledWorkspaces"})) for item in catalog.skills])
                self._write(catalog)
            return catalog
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

    def _read_view(self, item):
        raw, digest, state = None, None, "disabled"
        name, description = item.name, item.description
        try:
            raw = self._read_file(item)
            name, description, body, digest = parse(raw)
            state = "ready" if item.enabled else "disabled"
        except SkillError as error:
            state = error.code
        result = {**item.model_dump(), "name": name, "description": description, "contentHash": digest, "state": state, "effective": False, "reason": state, "shadowedBySkillId": None}
        instruction = SkillContent(item.id, item.scope, name, description, item.revision, digest, body) if digest is not None else None
        return result, raw, instruction

    def _resolve(self, catalog, workspace_id=None):
        """Resolve each file once for both presentation and immutable Run contents."""
        entries = {item.id: self._read_view(item) for item in catalog.skills
                   if item.scope == "global" or item.workspaceId == workspace_id}
        groups = {}
        for identifier, (view, _, _) in entries.items():
            key = (view["scope"], unicodedata.normalize("NFC", view["name"]).casefold())
            groups.setdefault(key, []).append(identifier)
        for identifier, (view, _, _) in entries.items():
            key = unicodedata.normalize("NFC", view["name"]).casefold()
            if len(groups[(view["scope"], key)]) > 1:
                view["state"] = view["reason"] = "duplicate_name"
            if view["scope"] == "global" and ("workspace", key) in groups:
                matches = groups[("workspace", key)]
                view["reason"] = "shadowed_by_workspace"
                view["shadowedBySkillId"] = matches[0] if len(matches) == 1 else None
            elif view["reason"] == "ready" and not catalog.enabled:
                view["reason"] = "master_disabled"
            view["effective"] = view["reason"] == "ready"
        return entries

    def _view(self, catalog, item, workspace_id=None, *, content=False, resolved=None):
        view, raw, _ = (resolved if resolved is not None else self._resolve(catalog, workspace_id or item.workspaceId))[item.id]
        result = dict(view)
        if content:
            result["content"] = raw
        return result

    def settings(self):
        with self.lock:
            cat = self._catalog()
            return {"enabled": cat.enabled, "revision": cat.revision}

    def batch(self, *, scope, workspace_id, action, expected):
        from .batch import apply_batch
        return apply_batch(self, scope=scope, workspace_id=workspace_id, action=action, expected=expected)

    def list(self, scope, workspace_id=None):
        with self.lock:
            if scope not in {"global", "workspace"} or (scope == "workspace" and workspace_id is None):
                raise SkillError("invalid_request")
            cat = self._catalog()
            items = [i for i in cat.skills if i.scope == scope and (scope == "global" or i.workspaceId == workspace_id)]
            resolved = self._resolve(cat, workspace_id)
            return {"revision": cat.revision, "enabled": cat.enabled, "skills": [self._view(cat, i, workspace_id, resolved=resolved) for i in items]}

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
            try:
                directory = current.directoryName if current else WorkspaceRootPolicy.directory_name(name)
            except ValueError:
                raise SkillError("unsafe_path") from None
            item = SkillRecord(id=identifier or str(uuid4()), scope=scope, workspaceId=workspace_id, directoryName=directory, name=name, description=description, revision=current.revision + 1 if current else 1, enabled=current.enabled if current else True)
            path = self._path(item); self._safe_file(path, missing=True)
            if not current and path.parent.exists():
                raise SkillError("directory_exists")
            cat.skills = [i for i in cat.skills if i.id != item.id] + [item]; cat.revision += 1
            self._transaction(cat, item, content=content)
            return self.get(item.id)

    def import_folder(self, *, scope, workspace_id, directory_name, files, expected):
        from .folder_import import validate_package, journal_bytes
        package = validate_package(directory_name, files)
        with self.lock:
            cat = self._catalog()
            self._expected(cat, expected)
            peers = [item for item in cat.skills if item.scope == scope and item.workspaceId == workspace_id]
            if any(item.name.casefold() == package.name.casefold() for item in peers):
                raise SkillError("duplicate_name")
            item = SkillRecord(id=str(uuid4()), scope=scope, workspaceId=workspace_id,
                               directoryName=package.directory_name, name=package.name,
                               description=package.description, revision=1, enabled=True)
            target = self._path(item).parent
            self._safe_file(target / "SKILL.md", missing=True)
            if target.parent.exists() and any(child.name.casefold() == target.name.casefold() for child in target.parent.iterdir()):
                raise SkillError("directory_exists")
            if any(peer.directoryName.casefold() == item.directoryName.casefold() for peer in peers):
                raise SkillError("directory_exists")
            cat.skills.append(item)
            cat.revision += 1
            try:
                self._validate(cat.model_dump())
                self._safe_file(self.paths.skills_transaction_file, missing=True)
                atomic_write(self.paths.skills_transaction_file, journal_bytes(cat, item, package))
                self._recover()
            except Exception:
                raise SkillError("store_unavailable") from None
            return self.get(item.id)

    def _transaction(self, catalog, item, *, content=None, archive=None):
        try:
            self._validate(catalog.model_dump())
            self._safe_file(self.paths.skills_transaction_file, missing=True)
            atomic_write(self.paths.skills_transaction_file, json.dumps({"version": 1, "catalog": catalog.model_dump(), "record": item.model_dump(), "content": content, "archive": archive}).encode())
            self._recover()
        except Exception:
            raise SkillError("store_unavailable") from None

    def configure(self, *, expected, enabled=None, identifier=None):
        with self.lock:
            cat = self._catalog(); self._expected(cat, expected)
            if identifier is None:
                cat.enabled = enabled
            else:
                item = self._find(cat, identifier)
                if enabled:
                    name, description, _, digest = parse(self._read_file(item))
                    if any(i.id != item.id and i.scope == item.scope and i.workspaceId == item.workspaceId and i.name.casefold() == name.casefold() for i in cat.skills):
                        raise SkillError("duplicate_name")
                    item.name, item.description = name, description
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
                    try:
                        directory = WorkspaceRootPolicy.directory_name(child.name)
                        item = SkillRecord(id=str(uuid4()), scope=scope, workspaceId=workspace_id, directoryName=directory, name=directory, description="", revision=1)
                        require_plain_directory(child)
                        try:
                            name, description, _, _ = parse(self._read_file(item))
                            item.enabled = True
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
                contents = [instruction for view, _, instruction in self._resolve(cat, workspace_id).values()
                            if view["effective"] and instruction is not None]
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
            cat.revision += 1; self._write(cat)
