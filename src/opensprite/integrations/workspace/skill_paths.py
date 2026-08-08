"""Workspace path rules shared by skill-aware tools."""

from __future__ import annotations

from pathlib import Path

import opensprite.integrations.workspace.paths as workspace_paths


def path_touches_read_only_app_skills_dir(file_path: Path) -> str | None:
    """Return the established error when a path targets read-only bundled skills."""
    try:
        resolved = file_path.resolve(strict=False)
        skills_home = workspace_paths.get_skills_dir().resolve(strict=False)
    except OSError:
        return None
    try:
        resolved.relative_to(skills_home)
    except ValueError:
        return None
    return (
        "Cannot modify files under ~/.opensprite/skills/ via write_file or edit_file. "
        "Bundled skills there are read-only; use the session workspace skills/ folder or configure_skill."
    )
