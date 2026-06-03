"""Shared verification tool and artifact policy helpers."""

from __future__ import annotations


VERIFICATION_TOOL_NAME = "verify"
VERIFICATION_RESULT_ARTIFACT_KIND = "verification_result"


def is_verification_tool_name(tool_name: str | None) -> bool:
    """Return whether a tool name represents the verification tool."""
    return str(tool_name or "").strip() == VERIFICATION_TOOL_NAME


def is_verification_result_artifact_kind(kind: str | None) -> bool:
    """Return whether an artifact kind represents verification output."""
    return str(kind or "").strip() == VERIFICATION_RESULT_ARTIFACT_KIND
