"""Subagent tool profile metadata and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..tool_names import (
    BATCH_TOOL_NAME,
    EXECUTION_TOOL_NAMES,
    GLOB_FILES_TOOL_NAME,
    GREP_FILES_TOOL_NAME,
    LIST_DIR_TOOL_NAME,
    READ_FILE_TOOL_NAME,
    READ_SKILL_TOOL_NAME,
    WORKSPACE_WRITE_TOOL_NAMES,
)
from ..tool_names import WEB_SOURCE_TOOL_NAMES
from . import load_metadata

TOOL_PROFILE_METADATA_FIELD = "tool_profile"
TOOL_PROFILE_NAMES = frozenset({"read-only", "research", "implementation", "testing"})


def normalize_metadata_value(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def allowed_tool_profile_names() -> list[str]:
    """Return supported frontmatter tool profile names."""
    return sorted(TOOL_PROFILE_NAMES)


def validate_tool_profile_name(tool_profile: Any) -> str | None:
    """Return an error when a tool_profile value is not supported."""
    normalized = normalize_metadata_value(tool_profile)
    if normalized in TOOL_PROFILE_NAMES:
        return None
    allowed = ", ".join(allowed_tool_profile_names())
    return f"tool_profile must be one of: {allowed}."


READ_ONLY_TOOLS = frozenset(
    {
        READ_FILE_TOOL_NAME,
        LIST_DIR_TOOL_NAME,
        GLOB_FILES_TOOL_NAME,
        GREP_FILES_TOOL_NAME,
        BATCH_TOOL_NAME,
        READ_SKILL_TOOL_NAME,
    }
)
WEB_TOOLS = WEB_SOURCE_TOOL_NAMES
WRITE_TOOLS = WORKSPACE_WRITE_TOOL_NAMES
EXEC_TOOLS = EXECUTION_TOOL_NAMES

TEST_WRITE_PATTERNS = frozenset(
    {
        "test/**",
        "tests/**",
        "**/test/**",
        "**/tests/**",
        "__tests__/**",
        "**/__tests__/**",
        "**/test_*.py",
        "**/*_test.py",
        "test_*.py",
        "*_test.py",
        "**/*.test.*",
        "**/*.spec.*",
        "*.test.*",
        "*.spec.*",
    }
)


@dataclass(frozen=True)
class SubagentToolProfile:
    """Allowed runtime tools for one class of subagent."""

    name: str
    allowed_tools: frozenset[str]
    write_path_patterns: frozenset[str] = frozenset()


READ_ONLY_PROFILE = SubagentToolProfile("read-only", READ_ONLY_TOOLS)
RESEARCH_PROFILE = SubagentToolProfile("research", READ_ONLY_TOOLS | WEB_TOOLS)
IMPLEMENTATION_PROFILE = SubagentToolProfile(
    "implementation",
    READ_ONLY_TOOLS | WRITE_TOOLS | EXEC_TOOLS,
)
TESTING_PROFILE = SubagentToolProfile(
    "testing",
    READ_ONLY_TOOLS | WRITE_TOOLS | EXEC_TOOLS,
    write_path_patterns=TEST_WRITE_PATTERNS,
)

TOOL_PROFILES_BY_NAME: dict[str, SubagentToolProfile] = {
    READ_ONLY_PROFILE.name: READ_ONLY_PROFILE,
    RESEARCH_PROFILE.name: RESEARCH_PROFILE,
    IMPLEMENTATION_PROFILE.name: IMPLEMENTATION_PROFILE,
    TESTING_PROFILE.name: TESTING_PROFILE,
}

PARALLEL_SAFE_PROFILE_NAMES = frozenset({READ_ONLY_PROFILE.name, RESEARCH_PROFILE.name})

CODE_REVIEWER_PROMPT_TYPE = "code-reviewer"
SECURITY_REVIEWER_PROMPT_TYPE = "security-reviewer"
ASYNC_CONCURRENCY_REVIEWER_PROMPT_TYPE = "async-concurrency-reviewer"
REVIEW_PROMPT_TYPES = frozenset(
    {
        CODE_REVIEWER_PROMPT_TYPE,
        SECURITY_REVIEWER_PROMPT_TYPE,
        ASYNC_CONCURRENCY_REVIEWER_PROMPT_TYPE,
    }
)

SUBAGENT_TOOL_PROFILES: dict[str, SubagentToolProfile] = {
    "implementer": IMPLEMENTATION_PROFILE,
    "debugger": IMPLEMENTATION_PROFILE,
    "bug-fixer": IMPLEMENTATION_PROFILE,
    "refactorer": IMPLEMENTATION_PROFILE,
    "integration-engineer": IMPLEMENTATION_PROFILE,
    "migration-writer": IMPLEMENTATION_PROFILE,
    "performance-optimizer": IMPLEMENTATION_PROFILE,
    "observability-engineer": IMPLEMENTATION_PROFILE,
    "test-writer": TESTING_PROFILE,
    "test-implementer": TESTING_PROFILE,
    CODE_REVIEWER_PROMPT_TYPE: READ_ONLY_PROFILE,
    SECURITY_REVIEWER_PROMPT_TYPE: READ_ONLY_PROFILE,
    ASYNC_CONCURRENCY_REVIEWER_PROMPT_TYPE: READ_ONLY_PROFILE,
    "pattern-matcher": READ_ONLY_PROFILE,
    "porting-planner": READ_ONLY_PROFILE,
    "api-designer": READ_ONLY_PROFILE,
    "outliner": READ_ONLY_PROFILE,
    "editor": READ_ONLY_PROFILE,
    "writer": RESEARCH_PROFILE,
    "researcher": RESEARCH_PROFILE,
    "fact-checker": RESEARCH_PROFILE,
    "reference-analyzer": RESEARCH_PROFILE,
}


def profile_for_subagent(
    prompt_type: str,
    *,
    app_home: Any = None,
    session_workspace: Any = None,
) -> SubagentToolProfile:
    """Return the runtime tool profile for a subagent id."""
    metadata = load_metadata(
        prompt_type,
        app_home=app_home,
        session_workspace=session_workspace,
    )
    metadata_profile = normalize_metadata_value(metadata.get(TOOL_PROFILE_METADATA_FIELD))
    if metadata_profile:
        profile = TOOL_PROFILES_BY_NAME.get(metadata_profile)
        if profile is None:
            allowed = ", ".join(allowed_tool_profile_names())
            raise ValueError(
                f"subagent '{prompt_type}' has invalid tool_profile '{metadata_profile}'. Allowed: {allowed}"
            )
        return profile
    return SUBAGENT_TOOL_PROFILES.get(prompt_type, READ_ONLY_PROFILE)


def supports_parallel_delegation(
    prompt_type: str,
    *,
    app_home: Any = None,
    session_workspace: Any = None,
) -> bool:
    """Return whether a subagent is safe for bounded parallel delegation."""
    return profile_for_subagent(
        prompt_type,
        app_home=app_home,
        session_workspace=session_workspace,
    ).name in PARALLEL_SAFE_PROFILE_NAMES
