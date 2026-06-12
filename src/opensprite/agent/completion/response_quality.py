"""Response-shape and grounding helpers for completion quality checks."""

from __future__ import annotations

import re

from ...tool_names import EXECUTION_TOOL_NAMES
from ..execution import ExecutionResult
from ..task.capabilities import OPERATIONS_TASK_TYPE
from .value_utils import coerce_text as _coerce_text

ITEMIZED_RESPONSE_LINE_RE = re.compile(r"^(?:[-*]|\d+[.)]|\|)")
ITEMIZED_OUTPUT_MISSING_REASON = "assistant did not provide the requested itemized result"
TERSE_FINAL_ANSWER_REASON = "assistant final answer was too terse for the task"
MEANINGFUL_OVERLAP_MIN_PREVIEW_CHARS = 17
GROUNDING_TOKEN_MIN_CHARS = 3
VERSION_TOKEN_MIN_CHARS = 5
MEANINGFUL_OVERLAP_MAX_REQUIRED_MATCHES = 3
WORKSPACE_LOCATION_CODE_TOKEN_RE = re.compile(
    r"\b[A-Za-z_][\w:-]*(?:\.[A-Za-z_][\w:-]*|_[A-Za-z0-9_]+|\(\))\b"
)
WORKSPACE_LOCATION_QUOTED_TOKEN_RE = re.compile(r"[`'\"][\w.:-]+[`'\"]")
WORKSPACE_PATH_RE = re.compile(
    r"(?:[\w.-]+[\\/])+[\w.-]+|[\w.-]+\.(?:py|js|ts|tsx|jsx|vue|json|toml|yaml|yml|md|css|html|java|go|rs|sql)",
    flags=re.IGNORECASE,
)
WORKSPACE_CONTEXT_REFERENCE_MISSING_REASON = (
    "assistant final answer did not reference inspected workspace context"
)
WORKSPACE_LOCATION_MISSING_REASON = "assistant final answer did not identify the workspace location"
OPERATION_VALIDATION_OR_RISK_MISSING_REASON = "operation validation or risk was not reported"
REPOSITORY_STATE_GIT_SUBCOMMANDS = frozenset({"rev-parse", "status", "log", "show", "branch"})
COMMAND_VERSION_MISSING_REASON = "command version answer did not report a version"


def normalized_response_text(response_text: str | None) -> str:
    return re.sub(r"\s+", " ", str(response_text or "").strip())


def response_item_count(response_text: str | None) -> int:
    lines = [line.strip() for line in str(response_text or "").splitlines() if line.strip()]
    return sum(1 for line in lines if ITEMIZED_RESPONSE_LINE_RE.match(line))


def response_has_minimum_text_length(response_text: str | None, min_chars: int) -> bool:
    return len(normalized_response_text(response_text)) >= max(1, int(min_chars or 1))


def itemized_output_follow_up_instruction() -> str:
    return (
        "\n- Quality follow-up: provide the requested itemized result, not an acknowledgement or plan. "
        "Include enough list/table entries to satisfy the user's requested count or clearly explain any remaining blocker."
    )


def response_reports_tool_result_preview(response_text: str | None, preview: str | None) -> bool:
    normalized_response = _normalize_grounding_text(response_text)
    normalized_preview = _normalize_grounding_text(preview)
    if not normalized_response or not normalized_preview:
        return False
    if normalized_preview in normalized_response:
        return True
    if _version_token_overlap(normalized_preview, normalized_response):
        return True
    return (
        len(normalized_preview) >= MEANINGFUL_OVERLAP_MIN_PREVIEW_CHARS
        and _meaningful_overlap(normalized_preview, normalized_response)
    )


def _normalize_grounding_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _version_token_overlap(expected: str, actual: str) -> bool:
    if not expected or not actual:
        return False
    version_tokens = [
        token
        for token in re.split(r"[^0-9a-zA-Z._-]+", expected)
        if len(token) >= VERSION_TOKEN_MIN_CHARS and any(char.isdigit() for char in token) and "." in token
    ]
    actual_tokens = [
        token
        for token in re.split(r"[^0-9a-zA-Z._-]+", actual)
        if len(token) >= VERSION_TOKEN_MIN_CHARS and any(char.isdigit() for char in token) and "." in token
    ]
    return any(
        token in actual
        or any(token.startswith(actual_token) or actual_token.startswith(token) for actual_token in actual_tokens)
        for token in version_tokens
    )


def _meaningful_overlap(expected: str, actual: str) -> bool:
    tokens = [token for token in re.split(r"[^0-9a-zA-Z._-]+", expected) if len(token) >= GROUNDING_TOKEN_MIN_CHARS]
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in actual)
    return matched >= min(MEANINGFUL_OVERLAP_MAX_REQUIRED_MATCHES, len(tokens))


def contains_workspace_location_clue(response_text: str | None, *, has_workspace_path: bool = False) -> bool:
    """Return whether a final answer identifies a concrete workspace location."""
    if has_workspace_path:
        return True
    normalized = str(response_text or "").strip().lower()
    if not normalized:
        return False
    if WORKSPACE_LOCATION_CODE_TOKEN_RE.search(normalized):
        return True
    return bool(WORKSPACE_LOCATION_QUOTED_TOKEN_RE.search(normalized))


def workspace_paths(text: str | None) -> tuple[str, ...]:
    matches = WORKSPACE_PATH_RE.findall(str(text or ""))
    seen: set[str] = set()
    paths: list[str] = []
    for match in matches:
        normalized = match.strip().lower().replace("\\", "/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            paths.append(normalized)
    return tuple(paths)


def response_references_workspace_path(path: str, normalized_response: str) -> bool:
    normalized_path = str(path or "").lower().replace("\\", "/")
    if normalized_path in str(normalized_response or "").replace("\\", "/"):
        return True
    filename = normalized_path.rsplit("/", 1)[-1]
    return bool(filename and filename in normalized_response)


def is_operations_task_type(task_type: str | None) -> bool:
    return _operation_policy_value(task_type) == OPERATIONS_TASK_TYPE


def is_command_execution_tool_name(tool_name: str | None) -> bool:
    return _operation_policy_value(tool_name) in EXECUTION_TOOL_NAMES


def execution_has_failed_command_evidence(execution_result: ExecutionResult) -> bool:
    return any(
        is_command_execution_tool_name(evidence.name) and not evidence.ok
        for evidence in execution_result.tool_evidence
    )


def execution_confuses_command_version_with_repo_state(execution_result: ExecutionResult) -> bool:
    for evidence in execution_result.tool_evidence:
        command = ""
        if isinstance(evidence.metadata, dict):
            args = evidence.metadata.get("tool_args")
            if isinstance(args, dict):
                command = str(args.get("command") or "").lower()
        if command_inspects_git_repository_state(command):
            return True
    return False


def command_inspects_git_repository_state(command: str | None) -> bool:
    normalized = re.sub(r"\s+", " ", str(command or "").strip().lower())
    if not normalized.startswith("git "):
        return False
    return any(f"git {subcommand}" in normalized for subcommand in REPOSITORY_STATE_GIT_SUBCOMMANDS)


def command_version_follow_up_instruction() -> str:
    return (
        "\n- Quality follow-up: the user asked for the installed command/program version. "
        "Run the direct version command, such as `<command> --version`, and answer with the version value. "
        "Do not inspect `.git`, `HEAD`, repository commits, or package metadata unless the user asks for repository state."
    )


def command_version_missing_detail(*, inspected_repository_state: bool) -> str:
    if inspected_repository_state:
        return (
            "- The user asked for the installed command/program version. "
            "Run the direct version command, such as `<command> --version`, instead of inspecting `.git`, `HEAD`, or repository commits."
        )
    return "- Include the installed command/program version from the execution result, or clearly state that the command is unavailable."


def _operation_policy_value(value: str | None) -> str:
    return _coerce_text(value)

