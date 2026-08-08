"""Filesystem-backed subagent prompt repository."""

import logging
import shutil
from pathlib import Path

from ..workspace.paths import (
    SUBAGENT_PROMPTS_DIRNAME,
    get_app_home,
    get_subagent_prompts_dir,
)


logger = logging.getLogger(__name__)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def sync_subagent_prompts_from_package(
    app_home: str | Path | None = None,
    *,
    silent: bool = False,
) -> list[str]:
    """Copy bundled subagent *.md into app_home/subagent_prompts when missing."""
    from importlib.resources import as_file, files as pkg_files

    home = get_app_home(app_home)
    dest_root = get_subagent_prompts_dir(home)
    bundled_root = pkg_files("opensprite") / "resources" / SUBAGENT_PROMPTS_DIRNAME
    if not bundled_root.is_dir():
        return []

    changed: list[str] = []
    bundled_files = sorted(
        (item for item in bundled_root.iterdir() if item.is_file() and item.name.endswith(".md")),
        key=lambda item: item.name,
    )
    for resource in bundled_files:
        dest = dest_root / resource.name
        if dest.exists():
            continue
        with as_file(resource) as source_path:
            shutil.copy2(source_path, dest)
        changed.append(_relative_path(dest, home))

    if changed and not silent:
        logger.info("Synced subagent prompt files: %s", changed)

    return changed


def _split_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter and return metadata plus markdown body."""
    metadata = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_content = parts[1].strip()
            body = parts[2].lstrip()
            for line in yaml_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()
    return metadata, body


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter metadata from a prompt file."""
    metadata, _ = _split_frontmatter(content)
    return metadata


def _session_subagent_dir(session_workspace: Path | str | None) -> Path | None:
    if session_workspace is None:
        return None
    return Path(session_workspace).expanduser() / SUBAGENT_PROMPTS_DIRNAME


def _get_prompt_path(
    prompt_type: str,
    app_home: Path | None,
    *,
    session_workspace: Path | str | None = None,
) -> Path:
    """Resolve markdown: session workspace overrides app home (~/.opensprite/subagent_prompts)."""
    home = get_app_home(app_home)
    sync_subagent_prompts_from_package(home)
    session_dir = _session_subagent_dir(session_workspace)
    if session_dir is not None:
        session_path = session_dir / f"{prompt_type}.md"
        if session_path.exists():
            return session_path
    user_path = get_subagent_prompts_dir(home) / f"{prompt_type}.md"
    return user_path


def load_metadata(
    prompt_type: str = "writer",
    *,
    app_home: Path | None = None,
    session_workspace: Path | str | None = None,
) -> dict:
    """Load frontmatter metadata for a prompt type."""
    md_path = _get_prompt_path(prompt_type, app_home, session_workspace=session_workspace)
    if not md_path.exists():
        return {}

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    return _parse_frontmatter(content)


def load_prompt(
    prompt_type: str = "writer",
    *,
    app_home: Path | None = None,
    session_workspace: Path | str | None = None,
) -> str:
    """Load prompt markdown content without frontmatter."""
    md_path = _get_prompt_path(prompt_type, app_home, session_workspace=session_workspace)
    if not md_path.exists():
        return ""

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    _, body = _split_frontmatter(content)
    return body.strip()


def load_all_metadata(
    *,
    app_home: Path | None = None,
    session_workspace: Path | str | None = None,
) -> dict[str, str]:
    """Load subagent ids and descriptions from app home plus optional session overrides."""
    home = get_app_home(app_home)
    sync_subagent_prompts_from_package(home)
    user_dir = get_subagent_prompts_dir(home)
    result: dict[str, str] = {}
    for md_file in sorted(user_dir.glob("*.md")):
        metadata = load_metadata(md_file.stem, app_home=home, session_workspace=session_workspace)
        description = metadata.get("description", md_file.stem)
        result[md_file.stem] = description
    session_dir = _session_subagent_dir(session_workspace)
    if session_dir is not None and session_dir.is_dir():
        for md_file in sorted(session_dir.glob("*.md")):
            if md_file.stem in result:
                continue
            metadata = load_metadata(md_file.stem, app_home=home, session_workspace=session_workspace)
            result[md_file.stem] = metadata.get("description", md_file.stem)
    return dict(sorted(result.items()))


def get_all_subagents(
    app_home: Path | None = None,
    *,
    session_workspace: Path | str | None = None,
) -> dict[str, str]:
    """Return available subagent types and short descriptions (same as load_all_metadata)."""
    return load_all_metadata(app_home=app_home, session_workspace=session_workspace)


def get_prompt_types(
    app_home: Path | None = None,
    *,
    session_workspace: Path | str | None = None,
) -> list[str]:
    """Return all available prompt types."""
    return list(load_all_metadata(app_home=app_home, session_workspace=session_workspace).keys())


def has_prompt(
    prompt_type: str,
    *,
    app_home: Path | None = None,
    session_workspace: Path | str | None = None,
) -> bool:
    """Check whether a prompt file exists for the given type."""
    return _get_prompt_path(prompt_type, app_home, session_workspace=session_workspace).exists()


def read_prompt_document(
    prompt_type: str,
    *,
    app_home: Path | None = None,
    session_workspace: Path | str | None = None,
) -> tuple[Path | None, str]:
    """Return (resolved_path, full_file_text); path None if no file under session or app home."""
    md_path = _get_prompt_path(prompt_type, app_home, session_workspace=session_workspace)
    if not md_path.exists():
        return None, ""
    return md_path, md_path.read_text(encoding="utf-8")


def __getattr__(name: str):
    if name == "ALL_SUBAGENTS":
        return load_all_metadata()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "sync_subagent_prompts_from_package",
    "load_metadata",
    "load_prompt",
    "load_all_metadata",
    "get_all_subagents",
    "get_prompt_types",
    "has_prompt",
    "read_prompt_document",
    "ALL_SUBAGENTS",
]
