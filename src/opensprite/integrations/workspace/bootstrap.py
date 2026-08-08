"""Provision and load bundled OpenSprite workspace resources."""

import logging
from pathlib import Path

from .paths import (
    get_app_home,
    get_bootstrap_dir,
    get_skills_dir,
    get_tool_workspace,
)
from ..subagents.prompts import sync_subagent_prompts_from_package


logger = logging.getLogger(__name__)

BOOTSTRAP_FILES = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "TOOLS.md", "USER.md"]


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def sync_templates(app_home: str | Path | None = None, silent: bool = False) -> list[str]:
    """Sync bundled templates into ~/.opensprite app directories."""
    home = get_app_home(app_home)
    bootstrap_dir = get_bootstrap_dir(home)
    skills_dir = get_skills_dir(home)
    get_tool_workspace(home)

    changed: list[str] = []

    try:
        from importlib.resources import files as pkg_files

        templates_root = pkg_files("opensprite") / "resources" / "templates"
        skills_root = pkg_files("opensprite") / "resources" / "skills"
    except Exception:
        return changed

    def _write(src, dest: Path, *, overwrite: bool = False) -> None:
        content = src.read_text(encoding="utf-8") if src else ""
        if dest.exists():
            if not overwrite:
                return
            if dest.read_text(encoding="utf-8") == content:
                return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        changed.append(_relative_path(dest, home))

    if templates_root.is_dir():
        for item in templates_root.iterdir():
            if item.name.endswith(".md"):
                _write(item, bootstrap_dir / item.name)

    if skills_root.is_dir():
        skills_dir.mkdir(parents=True, exist_ok=True)
        for skill_folder in skills_root.iterdir():
            if not skill_folder.is_dir():
                continue
            skill_dest = skills_dir / skill_folder.name
            skill_dest.mkdir(parents=True, exist_ok=True)
            for item in skill_folder.iterdir():
                if item.name.endswith((".md", ".py")):
                    _write(item, skill_dest / item.name, overwrite=True)

    changed.extend(sync_subagent_prompts_from_package(home, silent=True))

    if changed and not silent:
        logger.info("Synced template files: %s", changed)

    return changed


def load_bootstrap_files(bootstrap_dir: str | Path) -> dict[str, str]:
    """Load bootstrap markdown files from the bootstrap directory."""
    result = {}
    base_dir = Path(bootstrap_dir).expanduser()
    for filename in BOOTSTRAP_FILES:
        file_path = base_dir / filename
        result[filename.removesuffix(".md")] = (
            file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        )
    return result
