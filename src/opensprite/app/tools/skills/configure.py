"""Tool for safely creating and managing skills (SKILL.md) in dedicated skill directories."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from opensprite.core.contracts.tool_results import tool_error_result
from opensprite.integrations.workspace.skill_paths import path_touches_read_only_app_skills_dir
from opensprite.modules.skills.loader import SkillsLoader
from opensprite.modules.skills.writing import (
    MAX_SKILL_ID_LEN,
    MIN_SKILL_BODY_LEN,
    MIN_SKILL_DESCRIPTION_CONTENT_WORDS,
    MIN_SKILL_DESCRIPTION_LEN,
    MIN_SKILL_DESCRIPTION_WORDS,
    build_skill_markdown,
    validate_body_for_write,
    validate_description_for_write,
    validate_skill_id,
)
from opensprite.modules.tools.base import Tool

WorkspaceResolver = Callable[[], Path]

# Bundled guide skill (see src/opensprite/resources/skills/skill-creator-design/SKILL.md) — full rules for new skills.
SKILL_CREATION_GUIDE_NAME = "skill-creator-design"
_TOOL_NAME = "configure_skill"


_CONFIGURE_SKILL_RULES_SUMMARY = (
    "Skill layout: one directory per skill named like the skill id, containing SKILL.md. "
    "Mutable skills live only under the current session workspace skills/; "
    "Bundled skills stay under ~/.opensprite/skills/<id>/ (read-only). "
    "YAML frontmatter must include name (same as skill_name / folder) and description. "
    "Before writing a new skill, read the bundled guide with read_skill using skill_name "
    f"'{SKILL_CREATION_GUIDE_NAME}': it defines concise metadata, English frontmatter, "
    "detailed description (what the skill does + when to trigger), imperative body text, "
    "progressive disclosure, and optional scripts/, references/, assets/ next to SKILL.md."
)


def _strip_error_prefix(message: str) -> str:
    return str(message or "").strip()


def _configure_skill_error_result(
    message: str,
    *,
    category: str,
    error_type: str = "ConfigureSkillToolError",
    invalid_arguments: bool = False,
) -> str:
    error = _strip_error_prefix(message)
    return tool_error_result(
        error,
        error_type=error_type,
        category=category,
        repeated_error_key=error if invalid_arguments else None,
        invalid_arguments=invalid_arguments,
        metadata={"tool_name": _TOOL_NAME},
    )


def _configure_skill_validation_error(message: str) -> str:
    return _configure_skill_error_result(
        message,
        category="invalid_arguments",
        error_type="ToolValidationError",
        invalid_arguments=True,
    )


class ConfigureSkillTool(Tool):
    """Read and update skill definitions under the session workspace ``skills/`` (not under ~/.opensprite/skills/)."""

    name = _TOOL_NAME
    description = (
        "Inspect, add, update, or remove skills (each skill is a directory containing SKILL.md). "
        "Use this when the user wants a new skill or to change skill metadata and instructions instead of editing files manually. "
        + _CONFIGURE_SKILL_RULES_SUMMARY
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get", "add", "upsert", "remove"],
                "description": (
                    "list: enumerate skills; get: read one SKILL.md; "
                    "add: create a new skill only (fails if it already exists); "
                    "upsert: create or replace SKILL.md; remove: delete skill directory. "
                    "All paths are under the session workspace skills/ (never ~/.opensprite/skills/)."
                ),
            },
            "skill_name": {
                "type": "string",
                "description": (
                    "Skill id: must match directory and frontmatter name. "
                    "Required format: lowercase ASCII, start with a letter, hyphens only between segments "
                    f"(2–{MAX_SKILL_ID_LEN} chars). Required for get, add, upsert, and remove."
                ),
            },
            "description": {
                "type": "string",
                "description": (
                    f"YAML frontmatter for add and upsert: min {MIN_SKILL_DESCRIPTION_LEN} chars, "
                    f"min {MIN_SKILL_DESCRIPTION_WORDS} English words, min {MIN_SKILL_DESCRIPTION_CONTENT_WORDS} substantive words; "
                    "must not be repetitive padding. Cover what the skill does and when to load it. See "
                    f"'{SKILL_CREATION_GUIDE_NAME}'."
                ),
            },
            "body": {
                "type": "string",
                "description": (
                    f"Markdown body for add and upsert (min {MIN_SKILL_BODY_LEN} chars after trim). Imperative instructions; "
                    f"lean body per '{SKILL_CREATION_GUIDE_NAME}', long text in references via write_file."
                ),
            },
        },
        "required": ["action"],
    }

    def __init__(
        self,
        skills_loader: SkillsLoader,
        *,
        workspace_resolver: WorkspaceResolver,
    ):
        self._skills_loader = skills_loader
        self._workspace_resolver = workspace_resolver

    def _session_skills_root(self) -> Path:
        return (Path(self._workspace_resolver()) / "skills").resolve()

    @staticmethod
    def _is_under(root: Path, path: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _list_payload(self, root: Path) -> dict[str, Any]:
        payload: dict[str, Any] = {"skills_dir": str(root), "skills": {}}
        if not root.exists():
            return payload
        for skill in self._skills_loader._load_skills_from_dir(root):
            payload["skills"][skill.name] = {
                "description": skill.description,
                "path": str(skill.path),
            }
        return payload

    async def _execute(self, action: str, **kwargs: Any) -> str:
        root = self._session_skills_root()

        if action == "list":
            return json.dumps(self._list_payload(root), ensure_ascii=False, indent=2)

        skill_name = str(kwargs.get("skill_name", "") or "").strip()
        err = validate_skill_id(skill_name)
        if err:
            return _configure_skill_validation_error(err)

        skill_dir = (root / skill_name).resolve()
        if not self._is_under(root, skill_dir):
            return _configure_skill_validation_error("skill path escapes skills root")

        skill_file = skill_dir / "SKILL.md"

        if action == "get":
            if not skill_file.is_file():
                return _configure_skill_error_result(
                    f"skill '{skill_name}' not found under {root}",
                    category="skill_not_found",
                )
            text = skill_file.read_text(encoding="utf-8")
            payload = {
                "skills_dir": str(root),
                "skill_name": skill_name,
                "path": str(skill_file),
                "content": text,
            }
            return json.dumps(payload, ensure_ascii=False, indent=2)

        if action == "remove":
            if not skill_dir.is_dir():
                return _configure_skill_error_result(
                    f"skill directory '{skill_name}' not found under {root}",
                    category="skill_not_found",
                )
            shutil.rmtree(skill_dir)
            return f"Removed skill '{skill_name}' from {root}."

        if action in {"add", "upsert"}:
            description = kwargs.get("description")
            body = kwargs.get("body")

            desc_err = validate_description_for_write(description, action=action)
            if desc_err:
                return _configure_skill_validation_error(desc_err)
            body_err = validate_body_for_write(body, action=action)
            if body_err:
                return _configure_skill_validation_error(body_err)

            existed = skill_file.is_file()
            if action == "add" and existed:
                return _configure_skill_error_result(
                    f"skill '{skill_name}' already exists at {skill_file}. "
                    "Use action=upsert to replace it, or remove it first.",
                    category="skill_conflict",
                )

            root.mkdir(parents=True, exist_ok=True)
            skill_dir.mkdir(parents=True, exist_ok=True)
            content = build_skill_markdown(skill_name, str(description), str(body))
            skill_file.write_text(content, encoding="utf-8")
            guide_hint = (
                f" Next: use read_skill with skill_name '{SKILL_CREATION_GUIDE_NAME}' if you have not applied the full checklist; "
                "add optional scripts/, references/, assets/ beside SKILL.md with write_file as needed."
            )
            if action == "add":
                return f"Added skill '{skill_name}' at {skill_file}.{guide_hint}"
            mode = "Updated" if existed else "Added"
            return f"{mode} skill '{skill_name}' at {skill_file}.{guide_hint}"

        return _configure_skill_validation_error(f"unsupported action '{action}'")
