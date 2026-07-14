"""Marker-guarded cleanup for worktrees created by older OpenSprite versions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from ..utils.processes import windows_hidden_process_kwargs


SANDBOX_MARKER = ".opensprite-worktree.json"
MISSING_WORKTREE_MARKER_REASON = "missing OpenSprite worktree marker"
WORKTREE_MARKER_NOT_MANAGED_REASON = "worktree marker is not managed by OpenSprite"
WORKTREE_CLEANUP_IDENTITY_REQUIRED_REASON = "session_id and run_id are required"
WORKTREE_MARKER_IDENTITY_MISMATCH_REASON = "worktree marker identity does not match request"
REPOSITORY_ROOT_MISSING_REASON = "repository root no longer exists"
GIT_WORKTREE_REMOVE_FAILED_REASON = "git worktree remove failed"
GIT_COMMAND_FAILED_REASON = "git command failed"
WORKTREE_PATH_IDENTITY_MISMATCH_REASON = "worktree path does not match marker identity"
WORKTREE_PATH_REDIRECTED_REASON = "worktree path resolves through a symlink or reparse point"
WORKTREE_NOT_REGISTERED_REASON = "worktree is not registered with repository"
REPOSITORY_IDENTITY_MISMATCH_REASON = "repository root does not match git metadata"

LEGACY_WORKTREE_ROOT_SUFFIX = ".opensprite-worktrees"


def cleanup_worktree_sandbox(
    sandbox_path: str | Path,
    *,
    session_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Remove a legacy OpenSprite worktree only when its marker is valid."""
    path = _lexical_absolute_path(sandbox_path)
    requested_session_id = str(session_id or "").strip()
    requested_run_id = str(run_id or "").strip()
    if not requested_session_id or not requested_run_id:
        return _refused(path, WORKTREE_CLEANUP_IDENTITY_REQUIRED_REASON)
    if _path_is_redirected(path):
        return _refused(path, WORKTREE_PATH_REDIRECTED_REASON)

    marker_path = _marker_path(path)
    if not marker_path.exists():
        return _missing_marker_result(
            path,
            session_id=requested_session_id,
            run_id=requested_run_id,
        )
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _refused(path, f"invalid worktree marker: {exc}")
    if not isinstance(marker, dict):
        return _refused(path, "invalid worktree marker: expected an object")
    if marker.get("managed_by") != "opensprite":
        return _refused(path, WORKTREE_MARKER_NOT_MANAGED_REASON)
    marker_session_id = str(marker.get("session_id") or "").strip()
    marker_run_id = str(marker.get("run_id") or "").strip()
    if (
        not marker_session_id
        or not marker_run_id
        or marker_session_id != requested_session_id
        or marker_run_id != requested_run_id
    ):
        return _refused(path, WORKTREE_MARKER_IDENTITY_MISMATCH_REASON)

    repository_root_value = str(marker.get("repository_root") or "").strip()
    if not repository_root_value:
        return _refused(path, REPOSITORY_ROOT_MISSING_REASON)
    repository_root = _lexical_absolute_path(repository_root_value)
    if not repository_root.exists():
        return _refused(path, REPOSITORY_ROOT_MISSING_REASON)

    expected_path = _legacy_sandbox_path(
        repository_root,
        session_id=requested_session_id,
        run_id=requested_run_id,
    )
    if not _same_lexical_path(path, expected_path):
        return _refused(path, WORKTREE_PATH_IDENTITY_MISMATCH_REASON)

    repository_reason = _repository_identity_error(repository_root)
    if repository_reason is not None:
        return _refused(path, repository_reason)

    registered_paths, registry_error = _registered_worktree_paths(repository_root)
    if registry_error is not None:
        return _refused(path, registry_error)
    if not any(_same_registered_path(path, registered_path) for registered_path in registered_paths):
        if not path.exists():
            _unlink_marker(marker_path)
            return _already_removed(path, repository_root)
        return _refused(path, WORKTREE_NOT_REGISTERED_REASON)

    result = _run_git("worktree", "remove", str(path), cwd=repository_root, timeout=20)
    if result.returncode != 0:
        return {
            "ok": False,
            "status": "remove_failed",
            "reason": (result.stderr or result.stdout).strip() or GIT_WORKTREE_REMOVE_FAILED_REASON,
            "sandbox_path": str(path),
            "repository_root": str(repository_root),
        }
    _unlink_marker(marker_path)
    return {
        "ok": True,
        "status": "removed",
        "sandbox_path": str(path),
        "repository_root": str(repository_root),
    }


def _marker_path(sandbox_path: Path) -> Path:
    return sandbox_path.with_name(f"{sandbox_path.name}{SANDBOX_MARKER}")


def _slug(value: str) -> str:
    """Reproduce the path slug used by the retired worktree creator."""
    normalized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return normalized[:80] or "sandbox"


def _legacy_sandbox_path(repository_root: Path, *, session_id: str, run_id: str) -> Path:
    root = repository_root.parent / f"{repository_root.name}{LEGACY_WORKTREE_ROOT_SUFFIX}"
    return _lexical_absolute_path(root / _slug(session_id) / _slug(run_id))


def _lexical_absolute_path(path: str | Path) -> Path:
    expanded = Path(path).expanduser()
    return Path(os.path.abspath(os.fspath(expanded)))


def _normalized_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _same_lexical_path(left: Path, right: Path) -> bool:
    return _normalized_path(_lexical_absolute_path(left)) == _normalized_path(
        _lexical_absolute_path(right)
    )


def _resolved_path(path: Path) -> Path | None:
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _path_is_redirected(path: Path) -> bool:
    resolved = _resolved_path(path)
    return resolved is None or not _same_lexical_path(path, resolved)


def _same_registered_path(path: Path, registered_path: Path) -> bool:
    resolved_path = _resolved_path(path)
    resolved_registered_path = _resolved_path(registered_path)
    if resolved_path is None or resolved_registered_path is None:
        return False
    return _same_lexical_path(resolved_path, resolved_registered_path)


def _repository_identity_error(repository_root: Path) -> str | None:
    result = _run_git("rev-parse", "--show-toplevel", cwd=repository_root, timeout=5)
    if result.returncode != 0:
        return (result.stderr or result.stdout).strip() or GIT_COMMAND_FAILED_REASON
    reported_root = str(result.stdout or "").strip()
    if not reported_root or not _same_lexical_path(repository_root, Path(reported_root).expanduser()):
        return REPOSITORY_IDENTITY_MISMATCH_REASON
    return None


def _registered_worktree_paths(repository_root: Path) -> tuple[list[Path], str | None]:
    result = _run_git("worktree", "list", "--porcelain", "-z", cwd=repository_root, timeout=5)
    if result.returncode != 0:
        return [], (result.stderr or result.stdout).strip() or GIT_COMMAND_FAILED_REASON
    paths: list[Path] = []
    for field in str(result.stdout or "").split("\0"):
        if not field.startswith("worktree "):
            continue
        value = field[len("worktree ") :].strip()
        if value:
            paths.append(_lexical_absolute_path(value))
    return paths, None


def _repository_root_from_legacy_path(path: Path, *, session_id: str, run_id: str) -> Path | None:
    worktree_root = path.parent.parent
    if not worktree_root.name.endswith(LEGACY_WORKTREE_ROOT_SUFFIX):
        return None
    repository_name = worktree_root.name[: -len(LEGACY_WORKTREE_ROOT_SUFFIX)]
    if not repository_name:
        return None
    repository_root = _lexical_absolute_path(worktree_root.with_name(repository_name))
    expected_path = _legacy_sandbox_path(
        repository_root,
        session_id=session_id,
        run_id=run_id,
    )
    return repository_root if _same_lexical_path(path, expected_path) else None


def _missing_marker_result(path: Path, *, session_id: str, run_id: str) -> dict[str, Any]:
    """Recognize a completed legacy cleanup without authorizing a new deletion."""
    if path.exists():
        return _refused(path, MISSING_WORKTREE_MARKER_REASON)
    repository_root = _repository_root_from_legacy_path(path, session_id=session_id, run_id=run_id)
    if repository_root is None or not repository_root.exists():
        return _refused(path, MISSING_WORKTREE_MARKER_REASON)
    if _repository_identity_error(repository_root) is not None:
        return _refused(path, MISSING_WORKTREE_MARKER_REASON)
    registered_paths, registry_error = _registered_worktree_paths(repository_root)
    if registry_error is not None:
        return _refused(path, registry_error)
    if any(_same_registered_path(path, registered_path) for registered_path in registered_paths):
        return _refused(path, MISSING_WORKTREE_MARKER_REASON)
    return _already_removed(path, repository_root)


def _unlink_marker(marker_path: Path) -> None:
    try:
        marker_path.unlink(missing_ok=True)
    except OSError:
        pass


def _already_removed(path: Path, repository_root: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "already_removed",
        "sandbox_path": str(path),
        "repository_root": str(repository_root),
    }


def _refused(path: Path, reason: str) -> dict[str, Any]:
    return {"ok": False, "status": "refused", "reason": reason, "sandbox_path": str(path)}


def _run_git(*args: str, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            **windows_hidden_process_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr=GIT_COMMAND_FAILED_REASON)
