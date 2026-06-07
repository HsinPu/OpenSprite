"""Subagent prompt, task, and structured-output contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..context.runtime import build_runtime_context
from ..llms import ChatMessage
from ..skills import SkillsLoader
from ..storage import StoredMessage
from ..subagent_prompts import load_metadata, load_prompt
from ..tools import ToolRegistry
from ..utils.json_safe import json_safe_value

SUBAGENT_TASK_ID_LABEL = "Task ID"
SUBAGENT_PROMPT_TYPE_LABEL = "Subagent"
STRUCTURED_SUBAGENT_SCHEMA_VERSION = 1
READONLY_SUBAGENT_RESULT_CONTRACT = "readonly_subagent_result"
STRUCTURED_SUBAGENT_SCHEMA_VERSION_FIELD = "schema_version"
STRUCTURED_SUBAGENT_CONTRACT_FIELD = "contract"
STRUCTURED_SUBAGENT_PROMPT_TYPE_FIELD = "prompt_type"
STRUCTURED_SUBAGENT_STATUS_FIELD = "status"
STRUCTURED_SUBAGENT_SUMMARY_FIELD = "summary"
STRUCTURED_SUBAGENT_SECTIONS_FIELD = "sections"
STRUCTURED_SUBAGENT_SECTION_TYPE_FIELD = "type"
STRUCTURED_SUBAGENT_ITEMS_FIELD = "items"
STRUCTURED_SUBAGENT_SECTION_COUNT_FIELD = "section_count"
STRUCTURED_SUBAGENT_ITEM_COUNT_FIELD = "item_count"
STRUCTURED_SUBAGENT_FINDING_COUNT_FIELD = "finding_count"
STRUCTURED_SUBAGENT_QUESTIONS_FIELD = "questions"
STRUCTURED_SUBAGENT_QUESTION_COUNT_FIELD = "question_count"
STRUCTURED_SUBAGENT_RESIDUAL_RISKS_FIELD = "residual_risks"
STRUCTURED_SUBAGENT_RESIDUAL_RISK_COUNT_FIELD = "residual_risk_count"
STRUCTURED_SUBAGENT_SOURCES_FIELD = "sources"
STRUCTURED_SUBAGENT_SOURCE_COUNT_FIELD = "source_count"
STRUCTURED_SUBAGENT_TRUNCATED_FIELD = "truncated"
STRUCTURED_SUBAGENT_OK_STATUS = "ok"
STRUCTURED_SUBAGENT_NEEDS_INPUT_STATUS = "needs_input"
STRUCTURED_SUBAGENT_INCONCLUSIVE_STATUS = "inconclusive"
ALLOWED_STRUCTURED_SUBAGENT_STATUSES = frozenset(
    {
        STRUCTURED_SUBAGENT_OK_STATUS,
        STRUCTURED_SUBAGENT_NEEDS_INPUT_STATUS,
        STRUCTURED_SUBAGENT_INCONCLUSIVE_STATUS,
    }
)
MAX_STRUCTURED_SUBAGENT_SUMMARY_CHARS = 280
MAX_STRUCTURED_SUBAGENT_TEXT_CHARS = 500
MAX_STRUCTURED_SUBAGENT_SECTIONS = 8
MAX_STRUCTURED_SUBAGENT_ITEMS_PER_SECTION = 12
MAX_STRUCTURED_SUBAGENT_QUESTIONS = 8
MAX_STRUCTURED_SUBAGENT_RESIDUAL_RISKS = 8
MAX_STRUCTURED_SUBAGENT_SOURCES = 12
_JSON_FENCE_RE = re.compile(r"```json\s*(?P<body>.*?)\s*```", re.IGNORECASE | re.DOTALL)


def subagent_result_line(label: str, value: object) -> str:
    return f"{label}: {value}"


def parse_subagent_result_line(line: str | None, label: str) -> str | None:
    prefix = f"{label}: "
    text = str(line or "")
    if not text.startswith(prefix):
        return None
    return text[len(prefix) :].strip() or None


def is_clean_structured_subagent_status(status: str | None) -> bool:
    """Return whether a structured subagent status represents a clean result."""
    return str(status or "").strip() == STRUCTURED_SUBAGENT_OK_STATUS


def _structured_subagent_result_fields(
    structured_output: dict[str, Any],
    *,
    include_section_counts: bool = False,
) -> dict[str, Any]:
    payload = {
        STRUCTURED_SUBAGENT_STATUS_FIELD: structured_output.get(STRUCTURED_SUBAGENT_STATUS_FIELD),
        STRUCTURED_SUBAGENT_SUMMARY_FIELD: structured_output.get(STRUCTURED_SUBAGENT_SUMMARY_FIELD),
    }
    if include_section_counts:
        payload.update(
            {
                STRUCTURED_SUBAGENT_SECTION_COUNT_FIELD: structured_output.get(STRUCTURED_SUBAGENT_SECTION_COUNT_FIELD, 0),
                STRUCTURED_SUBAGENT_ITEM_COUNT_FIELD: structured_output.get(STRUCTURED_SUBAGENT_ITEM_COUNT_FIELD, 0),
            }
        )
    payload.update(
        {
            STRUCTURED_SUBAGENT_FINDING_COUNT_FIELD: structured_output.get(STRUCTURED_SUBAGENT_FINDING_COUNT_FIELD, 0),
            STRUCTURED_SUBAGENT_QUESTION_COUNT_FIELD: structured_output.get(STRUCTURED_SUBAGENT_QUESTION_COUNT_FIELD, 0),
            STRUCTURED_SUBAGENT_RESIDUAL_RISK_COUNT_FIELD: structured_output.get(STRUCTURED_SUBAGENT_RESIDUAL_RISK_COUNT_FIELD, 0),
        }
    )
    return payload


def parse_structured_subagent_output(
    text: str,
    *,
    prompt_type: str,
) -> tuple[str, dict[str, Any] | None, str | None]:
    """Return visible text plus optional structured payload parsed from a trailing JSON block."""
    raw_text = str(text or "")
    visible_text, raw_json = _split_trailing_json_block(raw_text)
    if raw_json is None:
        return visible_text, None, None

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return _fallback_visible_text(visible_text, raw_text), None, f"invalid_json: {exc.msg}"

    normalized, error = _normalize_structured_payload(payload, prompt_type=prompt_type, fallback_text=visible_text)
    if normalized is None:
        return _fallback_visible_text(visible_text, raw_text), None, error
    return _fallback_visible_text(visible_text, raw_text) or normalized[STRUCTURED_SUBAGENT_SUMMARY_FIELD], normalized, None


def build_structured_subagent_contract_instructions(prompt_type: str) -> str:
    """Return shared prompt instructions for the structured readonly subagent contract."""
    normalized_prompt_type = str(prompt_type or "subagent").strip() or "subagent"
    return (
        "## Structured Output Contract\n\n"
        "After your normal human-readable answer, append one final fenced `json` block and do not output anything after it. "
        "Keep the human-readable answer useful on its own because the JSON block is optional machine-readable metadata.\n\n"
        "Rules:\n"
        f"- The JSON block must be one object with `schema_version: 1`, `contract: \"{READONLY_SUBAGENT_RESULT_CONTRACT}\"`, and `prompt_type: \"{normalized_prompt_type}\"`.\n"
        "- `status` must be one of `ok`, `needs_input`, or `inconclusive`.\n"
        "- `summary` must be one concise conclusion sentence.\n"
        "- Put main structured content in `sections`, using stable keys and one of these `type` values when applicable: `finding_list`, `bullet_list`, `outline`, `api_surface`, `pattern_matches`, `fact_check`.\n"
        "- Use `questions` only for concrete missing-input questions.\n"
        "- Use `residual_risks` only for unverified assumptions, blind spots, or remaining uncertainty.\n"
        "- Use `sources` only for concrete evidence you actually inspected.\n"
        "- Do not wrap the whole answer in JSON. Only the final fenced block should be JSON.\n\n"
        "Template:\n"
        "```json\n"
        "{\n"
        '  "schema_version": 1,\n'
        f'  "contract": "{READONLY_SUBAGENT_RESULT_CONTRACT}",\n'
        f'  "prompt_type": "{normalized_prompt_type}",\n'
        '  "status": "ok",\n'
        '  "summary": "...",\n'
        '  "sections": [\n'
        '    {\n'
        '      "key": "main",\n'
        '      "title": "Main Results",\n'
        '      "type": "bullet_list",\n'
        '      "items": ["..."]\n'
        '    }\n'
        '  ],\n'
        '  "questions": [],\n'
        '  "residual_risks": [],\n'
        '  "sources": []\n'
        "}\n"
        "```"
    )


def _split_trailing_json_block(text: str) -> tuple[str, str | None]:
    last_match = None
    for match in _JSON_FENCE_RE.finditer(str(text or "")):
        last_match = match
    if last_match is None:
        return str(text or "").strip(), None
    visible = (str(text or "")[: last_match.start()] + str(text or "")[last_match.end():]).strip()
    return visible, last_match.group("body").strip()


def _fallback_visible_text(visible_text: str, raw_text: str) -> str:
    text = str(visible_text or "").strip() or str(raw_text or "").strip()
    return _bounded_text(text, MAX_STRUCTURED_SUBAGENT_TEXT_CHARS)


def _normalize_structured_payload(
    payload: Any,
    *,
    prompt_type: str,
    fallback_text: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "payload_must_be_object"
    if int(payload.get(STRUCTURED_SUBAGENT_SCHEMA_VERSION_FIELD) or 0) != STRUCTURED_SUBAGENT_SCHEMA_VERSION:
        return None, "schema_version_mismatch"
    if str(payload.get(STRUCTURED_SUBAGENT_CONTRACT_FIELD) or "").strip() != READONLY_SUBAGENT_RESULT_CONTRACT:
        return None, "contract_mismatch"

    payload_prompt_type = str(payload.get(STRUCTURED_SUBAGENT_PROMPT_TYPE_FIELD) or "").strip()
    if payload_prompt_type and payload_prompt_type != str(prompt_type or "").strip():
        return None, "prompt_type_mismatch"

    truncated = False
    status = str(payload.get(STRUCTURED_SUBAGENT_STATUS_FIELD) or STRUCTURED_SUBAGENT_INCONCLUSIVE_STATUS).strip() or STRUCTURED_SUBAGENT_INCONCLUSIVE_STATUS
    if status not in ALLOWED_STRUCTURED_SUBAGENT_STATUSES:
        status = STRUCTURED_SUBAGENT_INCONCLUSIVE_STATUS
        truncated = True

    summary = _bounded_text(str(payload.get(STRUCTURED_SUBAGENT_SUMMARY_FIELD) or "").strip() or _first_nonempty_line(fallback_text), MAX_STRUCTURED_SUBAGENT_SUMMARY_CHARS)
    if summary != str(payload.get(STRUCTURED_SUBAGENT_SUMMARY_FIELD) or "").strip():
        truncated = truncated or bool(str(payload.get(STRUCTURED_SUBAGENT_SUMMARY_FIELD) or "").strip())

    sections, sections_truncated = _normalize_sections(payload.get(STRUCTURED_SUBAGENT_SECTIONS_FIELD))
    questions, questions_truncated = _normalize_string_list(payload.get(STRUCTURED_SUBAGENT_QUESTIONS_FIELD), limit=MAX_STRUCTURED_SUBAGENT_QUESTIONS)
    residual_risks, residual_risks_truncated = _normalize_string_list(
        payload.get(STRUCTURED_SUBAGENT_RESIDUAL_RISKS_FIELD) or payload.get("residualRisks"),
        limit=MAX_STRUCTURED_SUBAGENT_RESIDUAL_RISKS,
    )
    sources, sources_truncated = _normalize_sources(payload.get(STRUCTURED_SUBAGENT_SOURCES_FIELD))
    truncated = truncated or sections_truncated or questions_truncated or residual_risks_truncated or sources_truncated

    item_count = sum(len(section.get(STRUCTURED_SUBAGENT_ITEMS_FIELD, [])) for section in sections)
    finding_count = sum(len(section.get(STRUCTURED_SUBAGENT_ITEMS_FIELD, [])) for section in sections if section.get(STRUCTURED_SUBAGENT_SECTION_TYPE_FIELD) == "finding_list")
    return {
        STRUCTURED_SUBAGENT_SCHEMA_VERSION_FIELD: STRUCTURED_SUBAGENT_SCHEMA_VERSION,
        STRUCTURED_SUBAGENT_CONTRACT_FIELD: READONLY_SUBAGENT_RESULT_CONTRACT,
        STRUCTURED_SUBAGENT_PROMPT_TYPE_FIELD: str(prompt_type or "").strip() or None,
        STRUCTURED_SUBAGENT_STATUS_FIELD: status,
        STRUCTURED_SUBAGENT_SUMMARY_FIELD: summary,
        STRUCTURED_SUBAGENT_SECTIONS_FIELD: sections,
        STRUCTURED_SUBAGENT_SECTION_COUNT_FIELD: len(sections),
        STRUCTURED_SUBAGENT_ITEM_COUNT_FIELD: item_count,
        STRUCTURED_SUBAGENT_FINDING_COUNT_FIELD: finding_count,
        STRUCTURED_SUBAGENT_QUESTIONS_FIELD: questions,
        STRUCTURED_SUBAGENT_QUESTION_COUNT_FIELD: len(questions),
        STRUCTURED_SUBAGENT_RESIDUAL_RISKS_FIELD: residual_risks,
        STRUCTURED_SUBAGENT_RESIDUAL_RISK_COUNT_FIELD: len(residual_risks),
        STRUCTURED_SUBAGENT_SOURCES_FIELD: sources,
        STRUCTURED_SUBAGENT_SOURCE_COUNT_FIELD: len(sources),
        STRUCTURED_SUBAGENT_TRUNCATED_FIELD: truncated,
    }, None


def _normalize_sections(value: Any) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(value, list):
        return [], False
    truncated = len(value) > MAX_STRUCTURED_SUBAGENT_SECTIONS
    sections: list[dict[str, Any]] = []
    for index, section in enumerate(value[:MAX_STRUCTURED_SUBAGENT_SECTIONS], start=1):
        if not isinstance(section, dict):
            truncated = True
            continue
        key = _bounded_text(str(section.get("key") or f"section_{index}"), 64)
        title = _bounded_text(str(section.get("title") or key), 120)
        section_type = _bounded_text(str(section.get(STRUCTURED_SUBAGENT_SECTION_TYPE_FIELD) or "bullet_list"), 64)
        items_value = section.get(STRUCTURED_SUBAGENT_ITEMS_FIELD)
        items: list[Any] = []
        if isinstance(items_value, list):
            truncated = truncated or len(items_value) > MAX_STRUCTURED_SUBAGENT_ITEMS_PER_SECTION
            for item in items_value[:MAX_STRUCTURED_SUBAGENT_ITEMS_PER_SECTION]:
                normalized = _bounded_json_value(item)
                if normalized in (None, "", [], {}):
                    continue
                items.append(normalized)
        elif items_value not in (None, ""):
            truncated = True
        sections.append(
            {
                "key": key,
                "title": title,
                STRUCTURED_SUBAGENT_SECTION_TYPE_FIELD: section_type,
                STRUCTURED_SUBAGENT_ITEMS_FIELD: items,
            }
        )
    return sections, truncated


def _normalize_string_list(value: Any, *, limit: int) -> tuple[list[str], bool]:
    if not isinstance(value, list):
        return [], False
    truncated = len(value) > limit
    items = [
        _bounded_text(str(item or "").strip(), MAX_STRUCTURED_SUBAGENT_TEXT_CHARS)
        for item in value[:limit]
        if str(item or "").strip()
    ]
    return items, truncated


def _normalize_sources(value: Any) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(value, list):
        return [], False
    truncated = len(value) > MAX_STRUCTURED_SUBAGENT_SOURCES
    items: list[dict[str, Any]] = []
    for source in value[:MAX_STRUCTURED_SUBAGENT_SOURCES]:
        if not isinstance(source, dict):
            truncated = True
            continue
        normalized = {
            "kind": _bounded_text(str(source.get("kind") or "unknown"), 32),
            "path": _bounded_text(str(source.get("path") or ""), 240),
            "title": _bounded_text(str(source.get("title") or ""), 160),
            "url": _bounded_text(str(source.get("url") or ""), 240),
            "start_line": _non_negative_int(source.get("start_line") or source.get("startLine")),
            "end_line": _non_negative_int(source.get("end_line") or source.get("endLine")),
        }
        items.append({key: value for key, value in normalized.items() if value not in (None, "", 0)})
    return items, truncated


def _bounded_json_value(value: Any) -> Any:
    safe = json_safe_value(value)
    if isinstance(safe, str):
        return _bounded_text(safe, MAX_STRUCTURED_SUBAGENT_TEXT_CHARS)
    if isinstance(safe, list):
        return [_bounded_json_value(item) for item in safe[:MAX_STRUCTURED_SUBAGENT_ITEMS_PER_SECTION]]
    if isinstance(safe, dict):
        limited: dict[str, Any] = {}
        for index, (key, item) in enumerate(safe.items()):
            if index >= 12:
                break
            limited[_bounded_text(str(key), 64)] = _bounded_json_value(item)
        return limited
    return safe


def _bounded_text(text: str, max_chars: int) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


def _first_nonempty_line(text: str) -> str:
    for line in str(text or "").splitlines():
        candidate = str(line or "").strip()
        if candidate:
            return candidate
    return ""


def _non_negative_int(value: Any) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, number)

DEFAULT_MAX_PARALLEL_SUBAGENTS = 2
MAX_PARALLEL_SUBAGENTS = 4
DEFAULT_SUBAGENT_MAX_TOOL_ITERATIONS = 100
SUBAGENT_TASK_ID_PATTERN = r"^task_[A-Za-z0-9_-]{8,64}$"
_TASK_ID_RE = re.compile(SUBAGENT_TASK_ID_PATTERN)


def new_subagent_task_id() -> str:
    """Return a compact id that can be shown to the model/user and reused later."""
    return f"task_{uuid4().hex[:12]}"


def validate_subagent_task_id(task_id: str) -> str | None:
    """Return an error message when a task id is malformed."""
    value = str(task_id or "").strip()
    if _TASK_ID_RE.fullmatch(value):
        return None
    return "task_id must match pattern task_[A-Za-z0-9_-]{8,64}."


def build_child_subagent_session_id(parent_session_id: str, task_id: str) -> str:
    """Build the storage session id for one child subagent task session."""
    return f"{parent_session_id}:subagent:{task_id}"


def extract_subagent_prompt_type(messages: list[StoredMessage]) -> str | None:
    """Return the prompt type stored on the first child task message, if available."""
    for message in messages:
        metadata = getattr(message, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        if metadata.get("kind") != "subagent_task":
            continue
        prompt_type = metadata.get("prompt_type")
        if isinstance(prompt_type, str) and prompt_type.strip():
            return prompt_type.strip()
    return None


class SubagentMessageBuilder:
    """Build prompt/messages for delegated subagent work."""

    def __init__(self, prompt_loader=load_prompt, skills_loader: SkillsLoader | None = None):
        self.prompt_loader = prompt_loader
        self.skills_loader = skills_loader

    def build_system_prompt(
        self,
        prompt_type: str = "writer",
        workspace: str | Path | None = None,
        app_home: Path | None = None,
    ) -> str:
        prompt_body = self.prompt_loader(
            prompt_type,
            app_home=app_home,
            session_workspace=workspace,
        )
        prompt_metadata = load_metadata(
            prompt_type,
            app_home=app_home,
            session_workspace=workspace,
        )
        runtime_context = build_runtime_context(workspace=workspace)
        workspace_path = Path(workspace) if workspace is not None else None
        skills_summary = ""
        if self.skills_loader is not None:
            personal_skills_dir = workspace_path / "skills" if workspace_path is not None else None
            skills_summary = self.skills_loader.build_skills_summary(personal_skills_dir)

        sections = []
        if prompt_body:
            sections.append(prompt_body)
        else:
            sections.append(
                "## 角色（Role）\n"
                f"你是專注於單一任務的 `{prompt_type}` 助手。\n\n"
                "## 任務（Task）\n"
                "1. 先理解目前任務。\n"
                "2. 根據已提供資訊完成內容。\n"
                "3. 若資訊不足，只提出必要問題。\n\n"
                "## 規範（Constraints）\n"
                "- 聚焦當前任務\n"
                "- 不要虛構事實\n"
                "- 直接輸出可交付內容\n\n"
                "## 輸出（Output）\n"
                "- 若資訊足夠：直接輸出完成內容。\n"
                "- 若資訊不足：列出需要補充的問題。"
            )

        if str(prompt_metadata.get("structured_output_contract") or "").strip() == READONLY_SUBAGENT_RESULT_CONTRACT:
            sections.extend(["", build_structured_subagent_contract_instructions(prompt_type)])

        if skills_summary:
            sections.extend([
                "",
                "If a listed skill is relevant, read it before using other non-trivial tools so you can follow its workflow first.",
                "",
                skills_summary,
            ])
        sections.extend(["", runtime_context])
        return "\n".join(sections).strip()

    def build_messages(
        self,
        task: str,
        prompt_type: str = "writer",
        workspace: str | Path | None = None,
        app_home: Path | None = None,
    ) -> list[ChatMessage]:
        system_prompt = self.build_system_prompt(prompt_type, workspace=workspace, app_home=app_home)
        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=task),
        ]

@dataclass(frozen=True)
class PreparedSubagentTask:
    """Resolved child-task execution inputs after validation and profile selection."""

    task_text: str
    task_preview: str
    prompt_type: str
    task_id: str
    child_session_id: str
    child_run_id: str
    parent_session_id: str
    parent_run_id: str | None
    is_resume: bool
    app_home: Path | None
    workspace: Path
    subagent_tools: ToolRegistry
    subagent_profile_name: str
    provider_override: Any | None = None
    group_id: str | None = None
    group_index: int | None = None
    group_total: int | None = None


@dataclass(frozen=True)
class SubagentTaskOutcome:
    """Structured result for one delegated child task."""

    task_id: str
    prompt_type: str
    child_session_id: str
    child_run_id: str
    status: str
    content: str = ""
    error: str = ""
    summary: str = ""
    executed_tool_calls: int = 0
    had_tool_error: bool = False
    verification_attempted: bool = False
    verification_passed: bool = False
    is_resume: bool = False
    structured_output: dict[str, Any] | None = None
    group_id: str | None = None
    group_index: int | None = None
    group_total: int | None = None

def format_review_finding(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    path = str(item.get("path") or "").strip()
    fix = str(item.get("fix") or "").strip()
    why = str(item.get("why") or "").strip()
    subject = f"{path}: {title}" if path and title else title or path
    if fix:
        return f"{subject}: {fix}" if subject else fix
    if why:
        return f"{subject}: {why}" if subject else why
    return subject


def first_structured_review_finding(structured_output: dict[str, Any] | None) -> str:
    sections = structured_output.get(STRUCTURED_SUBAGENT_SECTIONS_FIELD) if isinstance(structured_output, dict) else None
    if not isinstance(sections, list):
        return ""
    for section in sections:
        if not isinstance(section, dict):
            continue
        items = section.get(STRUCTURED_SUBAGENT_ITEMS_FIELD)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                detail = format_review_finding(item)
                if detail:
                    return detail
            elif isinstance(item, str) and item.strip():
                return item.strip()
    return ""
