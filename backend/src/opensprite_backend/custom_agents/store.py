"""Bounded strict catalog IO; callers serialize mutations through their gate."""

from __future__ import annotations

import json
from pathlib import Path

from opensprite_backend.app_paths import AppPaths
from opensprite_backend.atomic_file import atomic_write
from opensprite_backend.workspaces import WorkspaceRootPolicy
from opensprite_backend.workspaces.relocation import require_plain_directory

from .models import AgentCatalog, AgentError


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_field")
        result[key] = value
    return result


def require_safe_file(path: Path, *, allow_missing: bool = False) -> None:
    """Reject linked ancestors and nonregular leaf nodes before local IO."""
    try:
        for parent in (path.parent, *path.parent.parents):
            if parent.exists() or parent.is_symlink():
                require_plain_directory(parent)
        if path.is_symlink() or (path.exists() and WorkspaceRootPolicy._is_reparse_point(path)):
            raise ValueError("linked_file")
        if path.exists():
            if not path.is_file():
                raise ValueError("not_file")
        elif not allow_missing:
            raise AgentError("missing")
    except AgentError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise AgentError("unsafe_path") from None


class AgentCatalogStore:
    """Missing catalog is virtual until a real policy mutation occurs."""

    def __init__(self, paths: AppPaths) -> None:
        self.path = paths.agents_settings_file

    def read(self) -> AgentCatalog:
        try:
            require_safe_file(self.path, allow_missing=True)
            if not self.path.exists():
                return AgentCatalog()
            with self.path.open("rb") as stream:
                payload = stream.read(16 * 1024 * 1024 + 1)
            if len(payload) > 16 * 1024 * 1024:
                raise ValueError("oversized_catalog")
            # Validate duplicate keys separately: Pydantic's JSON parser accepts them.
            raw = json.loads(payload, object_pairs_hook=_unique_object)
            if type(raw) is not dict or set(raw) != {"version", "revision", "enabled", "agents"}:
                raise ValueError("invalid_catalog_fields")
            return AgentCatalog.model_validate_json(payload)
        except Exception:
            raise AgentError("store_unavailable") from None

    def write(self, catalog: AgentCatalog) -> None:
        try:
            require_safe_file(self.path, allow_missing=True)
            payload = catalog.model_dump_json().encode("utf-8")
            if len(payload) > 16 * 1024 * 1024:
                raise ValueError("oversized_catalog")
            atomic_write(self.path, payload)
        except Exception:
            raise AgentError("store_unavailable") from None
