"""Shared text-grounding checks for tool result previews."""

from __future__ import annotations

import re


def response_reports_tool_result_preview(response_text: str | None, preview: str | None) -> bool:
    normalized_response = _normalize_text(response_text)
    normalized_preview = _normalize_text(preview)
    if not normalized_response or not normalized_preview:
        return False
    if normalized_preview in normalized_response:
        return True
    if _version_token_overlap(normalized_preview, normalized_response):
        return True
    return len(normalized_preview) > 16 and _meaningful_overlap(normalized_preview, normalized_response)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _version_token_overlap(expected: str, actual: str) -> bool:
    if not expected or not actual:
        return False
    version_tokens = [
        token
        for token in re.split(r"[^0-9a-zA-Z._-]+", expected)
        if len(token) >= 5 and any(char.isdigit() for char in token) and "." in token
    ]
    actual_tokens = [
        token
        for token in re.split(r"[^0-9a-zA-Z._-]+", actual)
        if len(token) >= 5 and any(char.isdigit() for char in token) and "." in token
    ]
    return any(
        token in actual
        or any(token.startswith(actual_token) or actual_token.startswith(token) for actual_token in actual_tokens)
        for token in version_tokens
    )


def _meaningful_overlap(expected: str, actual: str) -> bool:
    tokens = [token for token in re.split(r"[^0-9a-zA-Z._-]+", expected) if len(token) >= 3]
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in actual)
    return matched >= min(3, len(tokens))
