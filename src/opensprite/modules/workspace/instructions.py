"""Safety and size policy for workspace instruction documents."""

from __future__ import annotations

import re


WORKSPACE_INSTRUCTION_MAX_CHARS = 20_000
WORKSPACE_INSTRUCTION_TRUNCATE_HEAD_RATIO = 0.7
WORKSPACE_INSTRUCTION_TRUNCATE_TAIL_RATIO = 0.2
_DEFAULT_FULL_READ_GUIDANCE = "Use file tools to read the full file."

_INVISIBLE_CHARS = frozenset(
    {
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
    }
)
_THREAT_PATTERNS = (
    (
        re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.IGNORECASE),
        "prompt_injection",
    ),
    (
        re.compile(
            r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)",
            re.IGNORECASE,
        ),
        "disregard_rules",
    ),
    (re.compile(r"do\s+not\s+tell\s+the\s+user", re.IGNORECASE), "deception_hide"),
    (re.compile(r"system\s+prompt\s+override", re.IGNORECASE), "system_prompt_override"),
    (
        re.compile(
            r"<!--[^>]*(ignore|override|system|secret|hidden)[^>]*-->",
            re.IGNORECASE,
        ),
        "html_comment_injection",
    ),
    (
        re.compile(r"<\s*div\s+style\s*=\s*[\"'][\s\S]*?display\s*:\s*none", re.IGNORECASE),
        "hidden_div",
    ),
    (
        re.compile(
            r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
            re.IGNORECASE,
        ),
        "secret_exfiltration",
    ),
    (
        re.compile(r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)", re.IGNORECASE),
        "secret_file_access",
    ),
)


def find_workspace_instruction_threats(content: str) -> list[str]:
    """Return ordered findings for suspicious workspace instruction content."""
    findings: list[str] = []
    for char in _INVISIBLE_CHARS:
        if char in content:
            findings.append(f"invisible unicode U+{ord(char):04X}")
    for pattern, finding in _THREAT_PATTERNS:
        if pattern.search(content):
            findings.append(finding)
    return findings


def truncate_workspace_instruction(
    content: str,
    filename: str,
    *,
    max_chars: int = WORKSPACE_INSTRUCTION_MAX_CHARS,
    full_read_guidance: str = _DEFAULT_FULL_READ_GUIDANCE,
) -> str:
    """Truncate a trusted instruction document while retaining its head and tail."""
    if len(content) <= max_chars:
        return content
    head_chars = int(max_chars * WORKSPACE_INSTRUCTION_TRUNCATE_HEAD_RATIO)
    tail_chars = int(max_chars * WORKSPACE_INSTRUCTION_TRUNCATE_TAIL_RATIO)
    head = content[:head_chars].rstrip()
    tail = content[-tail_chars:].lstrip()
    marker = (
        f"\n\n[...truncated {filename}: kept {head_chars}+{tail_chars} of "
        f"{len(content)} chars. {full_read_guidance}]\n\n"
    )
    return f"{head}{marker}{tail}"


def sanitize_workspace_instruction(
    content: str,
    filename: str,
    *,
    max_chars: int = WORKSPACE_INSTRUCTION_MAX_CHARS,
    full_read_guidance: str = _DEFAULT_FULL_READ_GUIDANCE,
) -> str:
    """Block suspicious instructions and truncate large trusted documents."""
    findings = find_workspace_instruction_threats(content)
    if findings:
        return (
            f"[BLOCKED: {filename} contained potential prompt injection "
            f"({', '.join(findings)}). Content not loaded.]"
        )
    return truncate_workspace_instruction(
        content,
        filename,
        max_chars=max_chars,
        full_read_guidance=full_read_guidance,
    )
