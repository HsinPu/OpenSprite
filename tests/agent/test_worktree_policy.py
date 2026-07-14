import json
import os
import subprocess
from pathlib import Path

import pytest

from opensprite.runs import worktree as worktree_module
from opensprite.runs.worktree import (
    GIT_COMMAND_FAILED_REASON,
    GIT_WORKTREE_REMOVE_FAILED_REASON,
    MISSING_WORKTREE_MARKER_REASON,
    REPOSITORY_ROOT_MISSING_REASON,
    REPOSITORY_IDENTITY_MISMATCH_REASON,
    SANDBOX_MARKER,
    WORKTREE_CLEANUP_IDENTITY_REQUIRED_REASON,
    WORKTREE_MARKER_IDENTITY_MISMATCH_REASON,
    WORKTREE_MARKER_NOT_MANAGED_REASON,
    WORKTREE_NOT_REGISTERED_REASON,
    WORKTREE_PATH_IDENTITY_MISMATCH_REASON,
    WORKTREE_PATH_REDIRECTED_REASON,
    cleanup_worktree_sandbox,
)


def _init_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def _legacy_sandbox_path(repo: Path, *, session_id: str, run_id: str) -> Path:
    def slug(value: str) -> str:
        normalized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
        return normalized[:80] or "sandbox"

    return repo.parent / f"{repo.name}.opensprite-worktrees" / slug(session_id) / slug(run_id)


def _add_legacy_worktree(repo: Path, *, session_id: str, run_id: str) -> tuple[Path, Path]:
    sandbox_path = _legacy_sandbox_path(repo, session_id=session_id, run_id=run_id)

    subprocess.run(
        ["git", "worktree", "add", "--detach", str(sandbox_path), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    marker_path = sandbox_path.with_name(f"{sandbox_path.name}{SANDBOX_MARKER}")
    marker_path.write_text(
        json.dumps(
            {
                "managed_by": "opensprite",
                "repository_root": str(repo),
                "session_id": session_id,
                "run_id": run_id,
            }
        ),
        encoding="utf-8",
    )
    return sandbox_path, marker_path


def _create_legacy_worktree(tmp_path: Path) -> tuple[Path, Path]:
    return _add_legacy_worktree(
        _init_repository(tmp_path),
        session_id="web:browser-1",
        run_id="run-1",
    )


def _create_directory_redirect(link: Path, target: Path) -> None:
    """Create a directory symlink, falling back to a Windows junction."""
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except (NotImplementedError, OSError) as symlink_error:
        if os.name != "nt":
            pytest.skip(f"directory symlinks are unavailable: {symlink_error}")

    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            "directory symlinks and junctions are unavailable: "
            f"{(result.stderr or result.stdout).strip()}"
        )


def test_legacy_worktree_cleanup_reasons_are_stable(tmp_path):
    assert GIT_COMMAND_FAILED_REASON == "git command failed"
    assert MISSING_WORKTREE_MARKER_REASON == "missing OpenSprite worktree marker"
    assert WORKTREE_MARKER_NOT_MANAGED_REASON == "worktree marker is not managed by OpenSprite"
    assert WORKTREE_CLEANUP_IDENTITY_REQUIRED_REASON == "session_id and run_id are required"
    assert WORKTREE_MARKER_IDENTITY_MISMATCH_REASON == "worktree marker identity does not match request"
    assert REPOSITORY_ROOT_MISSING_REASON == "repository root no longer exists"
    assert GIT_WORKTREE_REMOVE_FAILED_REASON == "git worktree remove failed"
    assert WORKTREE_PATH_IDENTITY_MISMATCH_REASON == "worktree path does not match marker identity"
    assert WORKTREE_PATH_REDIRECTED_REASON == "worktree path resolves through a symlink or reparse point"
    assert WORKTREE_NOT_REGISTERED_REASON == "worktree is not registered with repository"
    assert REPOSITORY_IDENTITY_MISMATCH_REASON == "repository root does not match git metadata"

    cleanup = cleanup_worktree_sandbox(
        tmp_path / "missing",
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup["ok"] is False
    assert cleanup["status"] == "refused"
    assert cleanup["reason"] == MISSING_WORKTREE_MARKER_REASON


def test_legacy_worktree_cleanup_removes_only_marked_worktree(tmp_path):
    sandbox_path, marker_path = _create_legacy_worktree(tmp_path)

    cleanup = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup["ok"] is True
    assert cleanup["status"] == "removed"
    assert not sandbox_path.exists()
    assert not marker_path.exists()

    retry = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert retry == {
        "ok": True,
        "status": "already_removed",
        "sandbox_path": str(sandbox_path.resolve(strict=False)),
        "repository_root": str((tmp_path / "repo").resolve(strict=False)),
    }


def test_legacy_worktree_cleanup_refuses_copied_marker_for_another_registered_worktree(tmp_path):
    repo = _init_repository(tmp_path)
    owned_path, owned_marker = _add_legacy_worktree(
        repo,
        session_id="web:browser-1",
        run_id="run-1",
    )
    other_path, other_marker = _add_legacy_worktree(
        repo,
        session_id="web:browser-1",
        run_id="run-2",
    )
    other_marker.write_text(owned_marker.read_text(encoding="utf-8"), encoding="utf-8")

    cleanup = cleanup_worktree_sandbox(
        other_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup["ok"] is False
    assert cleanup["status"] == "refused"
    assert cleanup["reason"] == WORKTREE_PATH_IDENTITY_MISMATCH_REASON
    assert owned_path.exists()
    assert other_path.exists()
    assert owned_marker.exists()
    assert other_marker.exists()


@pytest.mark.parametrize("redirect_location", ["worktree", "parent"])
def test_legacy_worktree_cleanup_refuses_redirect_to_registered_worktree(tmp_path, redirect_location):
    repo = _init_repository(tmp_path)
    sandbox_path = _legacy_sandbox_path(repo, session_id="web:browser-1", run_id="run-1")
    target_parent = tmp_path / f"redirect-target-{redirect_location}"
    target_path = target_parent / sandbox_path.name if redirect_location == "parent" else target_parent
    target_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(target_path), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    target_marker = target_path.with_name(f"{target_path.name}{SANDBOX_MARKER}")
    target_marker.write_text(
        json.dumps(
            {
                "managed_by": "opensprite",
                "repository_root": str(repo),
                "session_id": "web:browser-1",
                "run_id": "run-1",
            }
        ),
        encoding="utf-8",
    )

    redirect_path = sandbox_path if redirect_location == "worktree" else sandbox_path.parent
    redirect_target = target_path if redirect_location == "worktree" else target_path.parent
    redirect_path.parent.mkdir(parents=True, exist_ok=True)
    _create_directory_redirect(redirect_path, redirect_target)

    cleanup = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup == {
        "ok": False,
        "status": "refused",
        "reason": WORKTREE_PATH_REDIRECTED_REASON,
        "sandbox_path": str(sandbox_path),
    }
    assert target_path.exists()
    assert target_marker.exists()


def test_legacy_worktree_cleanup_refuses_expected_path_when_git_does_not_register_it(tmp_path):
    repo = _init_repository(tmp_path)
    sandbox_path = _legacy_sandbox_path(repo, session_id="web:browser-1", run_id="run-1")
    sandbox_path.mkdir(parents=True)
    marker_path = sandbox_path.with_name(f"{sandbox_path.name}{SANDBOX_MARKER}")
    marker_path.write_text(
        json.dumps(
            {
                "managed_by": "opensprite",
                "repository_root": str(repo),
                "session_id": "web:browser-1",
                "run_id": "run-1",
            }
        ),
        encoding="utf-8",
    )

    cleanup = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup["ok"] is False
    assert cleanup["status"] == "refused"
    assert cleanup["reason"] == WORKTREE_NOT_REGISTERED_REASON
    assert sandbox_path.exists()
    assert marker_path.exists()


def test_legacy_worktree_cleanup_refuses_missing_or_mismatched_identity(tmp_path):
    sandbox_path, marker_path = _create_legacy_worktree(tmp_path)

    missing_identity = cleanup_worktree_sandbox(sandbox_path, session_id="", run_id="run-1")
    mismatched_identity = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:other-browser",
        run_id="run-1",
    )

    assert missing_identity == {
        "ok": False,
        "status": "refused",
        "reason": WORKTREE_CLEANUP_IDENTITY_REQUIRED_REASON,
        "sandbox_path": str(sandbox_path.resolve(strict=False)),
    }
    assert mismatched_identity["ok"] is False
    assert mismatched_identity["status"] == "refused"
    assert mismatched_identity["reason"] == WORKTREE_MARKER_IDENTITY_MISMATCH_REASON
    assert sandbox_path.exists()
    assert marker_path.exists()


def test_legacy_worktree_cleanup_refuses_marker_with_missing_identity(tmp_path):
    sandbox_path, marker_path = _create_legacy_worktree(tmp_path)
    marker = json.loads(marker_path.read_text(encoding="utf-8"))

    marker_without_session = {key: value for key, value in marker.items() if key != "session_id"}
    marker_path.write_text(json.dumps(marker_without_session), encoding="utf-8")
    missing_session = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    marker_without_run = {key: value for key, value in marker.items() if key != "run_id"}
    marker_path.write_text(json.dumps(marker_without_run), encoding="utf-8")
    missing_run = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert missing_session["ok"] is False
    assert missing_session["status"] == "refused"
    assert missing_session["reason"] == WORKTREE_MARKER_IDENTITY_MISMATCH_REASON
    assert missing_run["ok"] is False
    assert missing_run["status"] == "refused"
    assert missing_run["reason"] == WORKTREE_MARKER_IDENTITY_MISMATCH_REASON
    assert sandbox_path.exists()
    assert marker_path.exists()


@pytest.mark.parametrize("repository_root", [None, "", "   "])
def test_legacy_worktree_cleanup_refuses_missing_repository_root(
    tmp_path,
    monkeypatch,
    repository_root,
):
    sandbox_path = tmp_path / "legacy-worktree"
    sandbox_path.mkdir()
    marker_path = sandbox_path.with_name(f"{sandbox_path.name}{SANDBOX_MARKER}")
    marker = {
        "managed_by": "opensprite",
        "session_id": "web:browser-1",
        "run_id": "run-1",
    }
    if repository_root is not None:
        marker["repository_root"] = repository_root
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    def unexpected_git_call(*args, **kwargs):
        pytest.fail("missing repository_root must be rejected before invoking git")

    monkeypatch.setattr(worktree_module, "_run_git", unexpected_git_call)

    cleanup = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup["ok"] is False
    assert cleanup["status"] == "refused"
    assert cleanup["reason"] == REPOSITORY_ROOT_MISSING_REASON
    assert sandbox_path.exists()
    assert marker_path.exists()


def test_legacy_worktree_cleanup_stays_successful_when_marker_unlink_is_locked(tmp_path, monkeypatch):
    sandbox_path, marker_path = _create_legacy_worktree(tmp_path)
    original_unlink = Path.unlink

    def locked_marker_unlink(path: Path, *args, **kwargs):
        if path == marker_path:
            raise PermissionError("marker is locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_marker_unlink)

    cleanup = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert cleanup["ok"] is True
    assert cleanup["status"] == "removed"
    assert not sandbox_path.exists()
    assert marker_path.exists()

    retry = cleanup_worktree_sandbox(
        sandbox_path,
        session_id="web:browser-1",
        run_id="run-1",
    )

    assert retry["ok"] is True
    assert retry["status"] == "already_removed"
    assert marker_path.exists()
