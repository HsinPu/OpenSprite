"""Workspace write-protection policy independent from app runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


BlockedPathResolver = Callable[[], frozenset[Path] | None]

_CONFIG_WRITE_GUARD_MSG = (
    "Cannot modify OpenSprite configuration files with write_file, edit_file, or apply_patch. "
    "Use the OpenSprite Web UI Settings or edit them outside the agent."
)
_SENSITIVE_USER_WRITE_GUARD_MSG = (
    "Cannot modify sensitive user configuration files with write_file, edit_file, or apply_patch. "
    "Edit SSH keys, cloud credentials, shell profiles, and credential files outside the agent."
)
_SENSITIVE_USER_FILE_PARTS = frozenset(
    {
        (".ssh", "authorized_keys"),
        (".ssh", "id_rsa"),
        (".ssh", "id_ed25519"),
        (".ssh", "config"),
        (".netrc",),
        (".pgpass",),
        (".npmrc",),
        (".pypirc",),
        (".bashrc",),
        (".zshrc",),
        (".profile",),
        (".bash_profile",),
        (".zprofile",),
    }
)
_SENSITIVE_USER_DIR_PARTS = frozenset(
    {
        (".aws",),
        (".gnupg",),
        (".kube",),
        (".docker",),
        (".azure",),
        (".config", "gh"),
    }
)


@dataclass(frozen=True)
class WorkspaceWriteProtection:
    """One deterministic reason a workspace write must be refused."""

    category: str
    message: str


def evaluate_workspace_write_protection(
    file_path: Path,
    *,
    blocked_paths_resolver: BlockedPathResolver | None = None,
    home_path: Path | None = None,
) -> WorkspaceWriteProtection | None:
    """Return the first app-independent write restriction for a path, if any."""
    try:
        resolved = file_path.resolve(strict=False)
    except OSError:
        return None

    if blocked_paths_resolver is not None:
        blocked_paths = blocked_paths_resolver()
        if blocked_paths is not None and resolved in blocked_paths:
            return WorkspaceWriteProtection("protected_config", _CONFIG_WRITE_GUARD_MSG)

    if resolved.name.lower() == "opensprite.json":
        return WorkspaceWriteProtection("protected_config", _CONFIG_WRITE_GUARD_MSG)

    try:
        home = (home_path if home_path is not None else Path.home()).expanduser().resolve(strict=False)
        relative_parts = resolved.relative_to(home).parts
    except (OSError, ValueError):
        return None

    normalized = tuple(part.lower() for part in relative_parts)
    if normalized in _SENSITIVE_USER_FILE_PARTS:
        return WorkspaceWriteProtection("sensitive_user_config", _SENSITIVE_USER_WRITE_GUARD_MSG)
    for directory_parts in _SENSITIVE_USER_DIR_PARTS:
        if normalized[: len(directory_parts)] == directory_parts:
            return WorkspaceWriteProtection("sensitive_user_config", _SENSITIVE_USER_WRITE_GUARD_MSG)
    return None
