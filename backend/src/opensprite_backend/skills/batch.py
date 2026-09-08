"""Scope-bounded batch changes and recoverable archive operations."""
from __future__ import annotations

import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from opensprite_backend.atomic_file import atomic_write
from opensprite_backend.workspaces.relocation import ensure_plain_directory, require_plain_directory
from .models import SkillCatalog, SkillError, StrictModel


class ArchiveEntry(StrictModel):
    skillId: str
    archiveId: str


class ArchiveJournal(StrictModel):
    version: Literal[3]
    catalog: SkillCatalog
    archives: list[ArchiveEntry] = Field(min_length=1)


def recover_batch(service, raw):
    tx = ArchiveJournal.model_validate(raw)
    catalog = service._validate(tx.catalog.model_dump())
    ids, archives, scopes = set(), set(), set()
    targets = []
    for entry in tx.archives:
        if str(UUID(entry.archiveId)) != entry.archiveId or entry.skillId in ids or entry.archiveId in archives:
            raise SkillError("store_unavailable")
        item = service._find(catalog, entry.skillId)
        ids.add(item.id); archives.add(entry.archiveId); scopes.add((item.scope, item.workspaceId))
        targets.append((service._path(item), service.paths.skills_archive_dir / entry.archiveId))
    if len(scopes) != 1:
        raise SkillError("store_unavailable")
    # All names and scope boundaries are validated before any filesystem mutation.
    for path, archive in targets:
        service._safe_file(path, missing=True)
        service._safe_file(archive / "SKILL.md", missing=True)
        ensure_plain_directory(archive.parent)
        if path.parent.exists():
            if archive.exists():
                raise SkillError("store_unavailable")
            require_plain_directory(path.parent)
            path.parent.rename(archive)
        elif archive.exists():
            require_plain_directory(archive)
    catalog.skills = [item for item in catalog.skills if item.id not in ids]
    catalog.revision += 1
    service._write(catalog)
    service.paths.skills_transaction_file.unlink()
    return catalog.revision


def apply_batch(service, *, scope, workspace_id, action, expected):
    if scope not in {"global", "workspace"} or action not in {"enable", "disable", "archive"}:
        raise SkillError("invalid_request")
    if (scope == "global" and workspace_id is not None) or (scope == "workspace" and workspace_id is None):
        raise SkillError("invalid_request")
    with service.lock:
        cat = service._catalog(); service._expected(cat, expected)
        items = [item for item in cat.skills if item.scope == scope and item.workspaceId == workspace_id]
        result = {"revision": cat.revision, "completed": 0, "skipped": [], "failed": []}
        if action == "archive":
            entries = []
            for item in items:
                try:
                    service._safe_file(service._path(item), missing=True)
                    archive_id = str(uuid4())
                    service._safe_file(service.paths.skills_archive_dir / archive_id / "SKILL.md", missing=True)
                    entries.append({"skillId": item.id, "archiveId": archive_id})
                except SkillError as error:
                    result["failed"].append({"id": item.id, "reason": error.code})
            if entries:
                tx = {"version": 3, "catalog": cat.model_dump(), "archives": entries}
                try:
                    service._safe_file(service.paths.skills_transaction_file, missing=True)
                    atomic_write(service.paths.skills_transaction_file, json.dumps(tx).encode())
                    result["revision"] = recover_batch(service, tx)
                except Exception:
                    # Keep the durable journal; reads recover before exposing any partial state.
                    raise SkillError("store_unavailable") from None
                result["completed"] = len(entries)
            return result
        resolved = service._resolve(cat, workspace_id) if action == "enable" else {}
        for item in items:
            if action == "enable":
                view = resolved[item.id][0]
                if view["state"] not in {"ready", "disabled"}:
                    result["skipped"].append({"id": item.id, "reason": view["state"]})
                    continue
            enabled = action == "enable"
            if item.enabled == enabled:
                result["skipped"].append({"id": item.id, "reason": "unchanged"})
                continue
            item.enabled = enabled
            item.revision += 1
            result["completed"] += 1
        if result["completed"]:
            cat.revision += 1
            service._write(cat)
            result["revision"] = cat.revision
        return result
