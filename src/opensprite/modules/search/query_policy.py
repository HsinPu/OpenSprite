"""Pure query parsing and Unicode matching policy for conversation search."""

from __future__ import annotations

import re
import unicodedata


MAX_HISTORY_SEARCH_RESULTS = 20
MAX_HISTORY_SEARCH_QUERY_LENGTH = 512
MAX_HISTORY_SEARCH_QUERY_TOKENS = 64

_LITERAL_IDENTIFIER_TERM_PATTERN = re.compile(
    r"(?<![\w+#])(?P<identifier>\w+(?:\+\+|#)\w*)(?![\w+#])",
    flags=re.UNICODE,
)


def unicode_casefold(value: str | None) -> str:
    """Normalize and casefold text consistently for history search."""
    normalized = unicodedata.normalize("NFC", value or "")
    return unicodedata.normalize("NFC", normalized.casefold())


def bound_history_search_limit(value: int | None, *, default: int) -> int:
    """Coerce a history-search result limit into the supported range."""
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, 1), MAX_HISTORY_SEARCH_RESULTS)


def _literal_identifiers(query: str) -> list[str]:
    normalized_query = unicodedata.normalize("NFC", query)
    identifiers: list[str] = []
    seen: set[str] = set()
    for match in _LITERAL_IDENTIFIER_TERM_PATTERN.finditer(normalized_query):
        identifier = match.group("identifier")
        normalized_identifier = unicode_casefold(identifier)
        if normalized_identifier in seen:
            continue
        seen.add(normalized_identifier)
        identifiers.append(identifier)
    return identifiers


def _query_without_literal_identifiers(query: str) -> str:
    normalized_query = unicodedata.normalize("NFC", query)
    return _LITERAL_IDENTIFIER_TERM_PATTERN.sub(" ", normalized_query)


def _deduplicated_query_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"\w+", query.lower()):
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def parse_history_search_terms(query: str) -> tuple[list[str], list[str]]:
    """Split a query into semantic literals and ordinary word tokens."""
    literals = _literal_identifiers(query)
    tokens = _deduplicated_query_tokens(_query_without_literal_identifiers(query))
    return literals, tokens


def _is_contiguous_script_character(character: str) -> bool:
    unicode_name = unicodedata.name(character, "")
    return unicode_name.startswith(
        (
            "CJK COMPATIBILITY IDEOGRAPH",
            "CJK UNIFIED IDEOGRAPH",
            "HANGUL",
            "HIRAGANA",
            "KATAKANA",
        )
    )


def _unicode_search_spans(value: str | None) -> list[tuple[str, str]]:
    normalized_value = unicode_casefold(value)
    spans: list[tuple[str, str]] = []
    current_kind: str | None = None
    for character in normalized_value:
        if _is_contiguous_script_character(character):
            kind = "contiguous"
        elif character.isalnum() or character == "_":
            kind = "word"
        elif unicodedata.category(character).startswith("M") and current_kind:
            kind = current_kind
        else:
            current_kind = None
            continue

        if spans and current_kind == kind:
            previous_kind, previous_text = spans[-1]
            spans[-1] = (previous_kind, f"{previous_text}{character}")
        else:
            spans.append((kind, character))
        current_kind = kind
    return spans


def _unicode_search_span_matches(
    query_kind: str,
    query_text: str,
    content_kind: str,
    content_text: str,
    *,
    has_previous_query_span: bool,
    has_next_query_span: bool,
) -> bool:
    if query_kind != content_kind:
        return False
    if query_kind != "contiguous":
        return query_text == content_text
    if has_previous_query_span and has_next_query_span:
        return query_text == content_text
    if has_previous_query_span:
        return content_text.startswith(query_text)
    if has_next_query_span:
        return content_text.endswith(query_text)
    return query_text in content_text


def _matching_unicode_span_index(
    content_spans: list[tuple[str, str]],
    query_spans: list[tuple[str, str]],
) -> int | None:
    if len(query_spans) > len(content_spans):
        return None

    for start in range(len(content_spans) - len(query_spans) + 1):
        candidates = content_spans[start : start + len(query_spans)]
        if all(
            _unicode_search_span_matches(
                query_kind,
                query_text,
                content_kind,
                content_text,
                has_previous_query_span=index > 0,
                has_next_query_span=index < len(query_spans) - 1,
            )
            for index, (
                (query_kind, query_text),
                (content_kind, content_text),
            ) in enumerate(zip(query_spans, candidates))
        ):
            return start
    return None


def find_history_search_token_offset(value: str, token: str) -> int | None:
    """Return a folded-text offset for one parsed ordinary query token."""
    query_spans = _unicode_search_spans(token)
    if not query_spans:
        return None
    content_spans = _unicode_search_spans(value)
    match_index = _matching_unicode_span_index(content_spans, query_spans)
    if match_index is None:
        return None

    folded_value = unicode_casefold(value)
    content_offsets: list[int] = []
    cursor = 0
    for _, content_text in content_spans:
        content_offset = folded_value.find(content_text, cursor)
        if content_offset < 0:
            return None
        content_offsets.append(content_offset)
        cursor = content_offset + len(content_text)

    content_kind, content_text = content_spans[match_index]
    query_kind, query_text = query_spans[0]
    relative_offset = 0
    if query_kind == content_kind == "contiguous":
        relative_offset = (
            len(content_text) - len(query_text)
            if len(query_spans) > 1
            else content_text.find(query_text)
        )
    return content_offsets[match_index] + relative_offset


def validate_history_search_query(query: str) -> str:
    """Return a stripped query or raise a stable validation error."""
    if not isinstance(query, str):
        raise ValueError("history search query must be a string")

    normalized = query.strip()
    if len(normalized) > MAX_HISTORY_SEARCH_QUERY_LENGTH:
        raise ValueError(
            "history search query must be at most "
            f"{MAX_HISTORY_SEARCH_QUERY_LENGTH} characters"
        )

    literals, tokens = parse_history_search_terms(normalized)
    query_components = {unicode_casefold(identifier) for identifier in literals}
    query_components.update(unicode_casefold(token) for token in tokens)
    token_count = len(query_components)
    if token_count > MAX_HISTORY_SEARCH_QUERY_TOKENS:
        raise ValueError(
            "history search query has too many unique tokens "
            f"(maximum {MAX_HISTORY_SEARCH_QUERY_TOKENS})"
        )
    return normalized
