"""
opensprite/integrations/workspace/paths.py - Workspace path and snapshot helpers.

Path layout:
- app home: ~/.opensprite
- subagent prompts: ~/.opensprite/subagent_prompts/*.md (seeded from bundled templates on first sync)
- bootstrap files: ~/.opensprite/bootstrap/*.md
- per-session workspace: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}
- per-session user profile: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/USER.md
- per-session memory: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/memory/MEMORY.md
- per-session recent summary: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/memory/RECENT_SUMMARY.md
- per-session recent-summary state: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/state/.recent_summary_state.json
- per-session curator state: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/state/.curator_state.json
- per-session learning ledger: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/state/.learning_state.json
- bundled skills (read-only, synced from package): ~/.opensprite/skills/<skill_id>/SKILL.md
- session workspace skills (mutable): ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/skills/*/SKILL.md
- session subagent overrides: ~/.opensprite/workspace/sessions/{channel}/{external_chat_id}/subagent_prompts/*.md
- workspace root: ~/.opensprite/workspace
"""

import shutil
from collections.abc import Callable
from pathlib import Path

from ...core.session_identity import (
    sanitize_path_segment as _sanitize_path_segment,
    split_session_id as _split_session_id,
)

OPENSPRITE_HOME = Path.home() / ".opensprite"
BOOTSTRAP_DIRNAME = "bootstrap"
MEMORY_DIRNAME = "memory"
SKILLS_DIRNAME = "skills"
WORKSPACE_DIRNAME = "workspace"
WORKSPACE_SESSIONS_DIRNAME = "sessions"
USER_OVERLAYS_DIRNAME = "user_overlays"
SESSION_MEMORY_DIRNAME = "memory"
SESSION_STATE_DIRNAME = "state"
SUBAGENT_PROMPTS_DIRNAME = "subagent_prompts"
USER_PROFILE_STATE_FILENAME = ".user_profile_state.json"
RECENT_SUMMARY_STATE_FILENAME = ".recent_summary_state.json"
CURATOR_STATE_FILENAME = ".curator_state.json"
LEARNING_STATE_FILENAME = ".learning_state.json"
USER_OVERLAY_FILENAME = "USER_OVERLAY.md"
USER_OVERLAY_INDEX_FILENAME = "user_overlay_index.json"


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_workspace_root(workspace: Path) -> Path:
    """Resolve and ensure a tool workspace root directory exists."""
    root = Path(workspace).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_workspace_resolver(
    workspace: Path | None = None,
    workspace_resolver: Callable[[], Path] | None = None,
) -> Callable[[], Path]:
    """Build a resolver that always returns a normalized workspace root."""
    if workspace_resolver is not None:
        return lambda: resolve_workspace_root(workspace_resolver())
    if workspace is None:
        raise ValueError("workspace or workspace_resolver is required")
    root = resolve_workspace_root(workspace)
    return lambda: root


def resolve_workspace_path(workspace: Path, path: str) -> Path | None:
    """Resolve a user path only when it remains inside its workspace."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(workspace)
    except ValueError:
        return None
    return candidate


def get_app_home(app_home: str | Path | None = None) -> Path:
    """Resolve the OpenSprite app home directory."""
    path = Path(app_home).expanduser() if app_home else OPENSPRITE_HOME
    return ensure_dir(path)


def get_bootstrap_dir(app_home: str | Path | None = None) -> Path:
    """Get the bootstrap directory that stores startup markdown files."""
    return ensure_dir(get_app_home(app_home) / BOOTSTRAP_DIRNAME)


def get_user_profile_file(
    app_home: str | Path | None = None,
    *,
    session_id: str | None = None,
    workspace_root: str | Path | None = None,
) -> Path:
    """Get the per-session USER.md profile file path."""
    return get_session_workspace(session_id, workspace_root=workspace_root, app_home=app_home) / "USER.md"


def get_user_profile_state_file(
    app_home: str | Path | None = None,
    *,
    session_id: str | None = None,
    workspace_root: str | Path | None = None,
) -> Path:
    """Get the persisted state file for per-session USER.md auto-update."""
    return get_session_workspace(session_id, workspace_root=workspace_root, app_home=app_home) / USER_PROFILE_STATE_FILENAME


def get_memory_dir(app_home: str | Path | None = None) -> Path:
    """Get the long-term memory directory."""
    return ensure_dir(get_app_home(app_home) / MEMORY_DIRNAME)


def get_skills_dir(app_home: str | Path | None = None) -> Path:
    """Get the app-home bundled skills directory (~/.opensprite/skills/<skill_id>/)."""
    return ensure_dir(get_app_home(app_home) / SKILLS_DIRNAME)


def get_user_overlays_dir(app_home: str | Path | None = None) -> Path:
    """Get the app-home directory for stable cross-session user overlays."""
    return ensure_dir(get_app_home(app_home) / USER_OVERLAYS_DIRNAME)


def get_tool_workspace(app_home: str | Path | None = None) -> Path:
    """Get the shared root directory that contains per-session workspaces."""
    return ensure_dir(get_app_home(app_home) / WORKSPACE_DIRNAME)


def get_subagent_prompts_dir(app_home: str | Path | None = None) -> Path:
    """Directory for editable subagent prompt markdown files (mirrors bundled defaults)."""
    return ensure_dir(get_app_home(app_home) / SUBAGENT_PROMPTS_DIRNAME)


def resolve_session_workspace_path(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Resolve the isolated workspace path for a session without creating it."""
    root = (
        Path(workspace_root).expanduser()
        if workspace_root is not None
        else (Path(app_home).expanduser() if app_home is not None else OPENSPRITE_HOME) / WORKSPACE_DIRNAME
    )
    channel, external_chat_id = _split_session_id(session_id)
    safe_channel = _sanitize_path_segment(channel, default="default", max_length=32)
    safe_external_chat_id = _sanitize_path_segment(external_chat_id, default="default")
    return root / WORKSPACE_SESSIONS_DIRNAME / safe_channel / safe_external_chat_id


def get_session_workspace(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the isolated workspace directory for a session."""
    return ensure_dir(resolve_session_workspace_path(session_id, workspace_root=workspace_root, app_home=app_home))


def get_user_overlay_dir(
    overlay_id: str | None,
    *,
    app_home: str | Path | None = None,
) -> Path:
    """Get the stable overlay directory for one resolved user identity."""
    safe_overlay_id = _sanitize_path_segment(str(overlay_id or "").strip(), default="default", max_length=48)
    return ensure_dir(get_user_overlays_dir(app_home) / safe_overlay_id)


def get_user_overlay_file(
    overlay_id: str | None,
    *,
    app_home: str | Path | None = None,
) -> Path:
    """Get the stable user overlay markdown file path."""
    return get_user_overlay_dir(overlay_id, app_home=app_home) / USER_OVERLAY_FILENAME


def get_user_overlay_index_file(
    overlay_id: str | None,
    *,
    app_home: str | Path | None = None,
) -> Path:
    """Get the structured overlay sidecar index path."""
    return ensure_dir(get_user_overlay_dir(overlay_id, app_home=app_home) / SESSION_STATE_DIRNAME) / USER_OVERLAY_INDEX_FILENAME


def get_session_memory_dir(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session memory directory nested under the session workspace."""
    return ensure_dir(get_session_workspace(session_id, workspace_root=workspace_root, app_home=app_home) / SESSION_MEMORY_DIRNAME)


def get_session_memory_file(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session MEMORY.md path under the session workspace tree."""
    return get_session_memory_dir(session_id, workspace_root=workspace_root, app_home=app_home) / "MEMORY.md"


def resolve_session_memory_file(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Resolve the per-session MEMORY.md path without creating session directories."""
    return (
        resolve_session_workspace_path(session_id, workspace_root=workspace_root, app_home=app_home)
        / SESSION_MEMORY_DIRNAME
        / "MEMORY.md"
    )


def get_session_recent_summary_file(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session RECENT_SUMMARY.md path under the session workspace tree."""
    return get_session_memory_dir(session_id, workspace_root=workspace_root, app_home=app_home) / "RECENT_SUMMARY.md"


def get_session_state_dir(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session state directory nested under the session workspace."""
    return ensure_dir(get_session_workspace(session_id, workspace_root=workspace_root, app_home=app_home) / SESSION_STATE_DIRNAME)


def get_session_recent_summary_state_file(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session recent-summary state file under the session workspace tree."""
    return get_session_state_dir(session_id, workspace_root=workspace_root, app_home=app_home) / RECENT_SUMMARY_STATE_FILENAME


def get_session_curator_state_file(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session curator state file under the session workspace tree."""
    return get_session_state_dir(session_id, workspace_root=workspace_root, app_home=app_home) / CURATOR_STATE_FILENAME


def get_session_learning_state_file(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the per-session learning ledger file under the session workspace tree."""
    return get_session_state_dir(session_id, workspace_root=workspace_root, app_home=app_home) / LEARNING_STATE_FILENAME


def get_session_skills_dir(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Get the personal/per-session skills directory for a session."""
    return get_session_workspace(session_id, workspace_root=workspace_root, app_home=app_home) / SKILLS_DIRNAME


def get_session_subagent_prompts_dir(
    session_id: str | None,
    *,
    workspace_root: str | Path | None = None,
    app_home: str | Path | None = None,
) -> Path:
    """Per-session subagent prompt overrides under the session workspace (mirrors app-home layout)."""
    return get_session_workspace(session_id, workspace_root=workspace_root, app_home=app_home) / SUBAGENT_PROMPTS_DIRNAME


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _copy_missing_file(source: Path, dest: Path, root: Path) -> str | None:
    """Copy a file if it exists and the destination is missing."""
    if not source.exists() or dest.exists():
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return _relative_path(dest, root)


def _copy_missing_tree(source: Path, dest: Path, root: Path) -> list[str]:
    """Copy a directory tree without overwriting existing files."""
    copied: list[str] = []

    if not source.exists():
        return copied

    if source.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            copied.extend(_copy_missing_tree(child, dest / child.name, root))
        return copied

    copied_file = _copy_missing_file(source, dest, root)
    if copied_file:
        copied.append(copied_file)
    return copied
