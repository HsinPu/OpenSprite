"""Redaction helpers for diagnostic log previews."""

from __future__ import annotations

import re


_SENSITIVE_QUERY_PARAMS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "api_key",
        "apikey",
        "client_secret",
        "password",
        "auth",
        "jwt",
        "session",
        "secret",
        "key",
        "code",
        "signature",
        "x-amz-signature",
    }
)
_SECRET_ENV_NAMES = r"(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)"
_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_-]{30,}|pplx-[A-Za-z0-9]{10,}|"
    r"hf_[A-Za-z0-9]{10,}|gsk_[A-Za-z0-9]{10,}|pypi-[A-Za-z0-9_-]{10,})"
    r"(?![A-Za-z0-9_-])"
)
_ENV_ASSIGN_RE = re.compile(
    rf"([A-Z0-9_]{{0,50}}{_SECRET_ENV_NAMES}[A-Z0-9_]{{0,50}})\s*=\s*(['\"]?)(\S+)\2"
)
_JSON_FIELD_RE = re.compile(
    r'("(?:api_?key|token|secret|password|access_token|refresh_token|authorization|key)")\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)
_AUTH_HEADER_RE = re.compile(r"(Authorization:\s*Bearer\s+)(\S+)", re.IGNORECASE)
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----")
_DB_CONNSTR_RE = re.compile(r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:]+:)([^@]+)(@)", re.IGNORECASE)
_URL_WITH_QUERY_RE = re.compile(r"(https?|wss?|ftp)://([^\s/?#]+)([^\s?#]*)\?([^\s#]+)(#\S*)?")


def _mask_secret(value: str) -> str:
    if not value:
        return "***"
    if len(value) < 18:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def _redact_query_string(query: str) -> str:
    parts = []
    for pair in query.split("&"):
        if "=" not in pair:
            parts.append(pair)
            continue
        key, _, value = pair.partition("=")
        parts.append(f"{key}=***" if key.lower() in _SENSITIVE_QUERY_PARAMS else pair)
    return "&".join(parts)


def redact_log_preview(text: str) -> str:
    """Redact common secret shapes before text reaches diagnostic logs."""
    if not text:
        return text

    text = _ENV_ASSIGN_RE.sub(lambda match: f"{match.group(1)}={match.group(2)}{_mask_secret(match.group(3))}{match.group(2)}", text)
    text = _JSON_FIELD_RE.sub(lambda match: f'{match.group(1)}: "{_mask_secret(match.group(2))}"', text)
    text = _AUTH_HEADER_RE.sub(lambda match: match.group(1) + _mask_secret(match.group(2)), text)
    text = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", text)
    text = _DB_CONNSTR_RE.sub(lambda match: f"{match.group(1)}***{match.group(3)}", text)
    text = _URL_WITH_QUERY_RE.sub(
        lambda match: f"{match.group(1)}://{match.group(2)}{match.group(3)}?{_redact_query_string(match.group(4))}{match.group(5) or ''}",
        text,
    )
    return _PREFIX_RE.sub(lambda match: _mask_secret(match.group(1)), text)


__all__ = ["redact_log_preview"]
