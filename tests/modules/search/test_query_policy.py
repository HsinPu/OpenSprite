import unicodedata

import pytest

from opensprite.modules.search.query_policy import (
    MAX_HISTORY_SEARCH_QUERY_LENGTH,
    MAX_HISTORY_SEARCH_QUERY_TOKENS,
    MAX_HISTORY_SEARCH_RESULTS,
    bound_history_search_limit,
    find_history_search_token_offset,
    parse_history_search_terms,
    unicode_casefold,
    validate_history_search_query,
)


def test_history_search_terms_preserve_literals_and_deduplicate_components():
    literals, tokens = parse_history_search_terms(
        "C++ c++ C#12 c#12 C++17 alpha ALPHA beta",
    )

    assert literals == ["C++", "C#12", "C++17"]
    assert tokens == ["alpha", "beta"]


def test_history_search_terms_split_punctuation_and_lowercase_tokens():
    literals, tokens = parse_history_search_terms("SQLite? alpha, ALPHA; beta")

    assert literals == []
    assert tokens == ["sqlite", "alpha", "beta"]


def test_history_search_query_validation_preserves_existing_boundaries():
    assert validate_history_search_query("  prior decision  ") == "prior decision"
    assert validate_history_search_query("   ") == ""
    assert validate_history_search_query("x" * MAX_HISTORY_SEARCH_QUERY_LENGTH) == (
        "x" * MAX_HISTORY_SEARCH_QUERY_LENGTH
    )

    with pytest.raises(ValueError, match="must be a string"):
        validate_history_search_query(None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="must be at most"):
        validate_history_search_query("x" * (MAX_HISTORY_SEARCH_QUERY_LENGTH + 1))


def test_history_search_query_validation_counts_unique_components():
    accepted_query = " ".join(
        f"token{index}" for index in range(MAX_HISTORY_SEARCH_QUERY_TOKENS)
    )
    rejected_query = f"{accepted_query} overflow"

    assert validate_history_search_query(accepted_query) == accepted_query
    with pytest.raises(ValueError, match="too many unique tokens"):
        validate_history_search_query(rejected_query)


def test_unicode_casefold_normalizes_sharp_s_and_decomposed_text():
    decomposed = unicodedata.normalize("NFD", "Café")

    assert unicode_casefold(None) == ""
    assert unicode_casefold("Straße") == "strasse"
    assert unicode_casefold(decomposed) == "café"


def test_history_search_token_offset_skips_substrings_inside_latin_words():
    content = "metatemplates are unrelated; standalone templates are relevant"

    offset = find_history_search_token_offset(content, "templates")

    assert offset == unicode_casefold(content).rfind("templates")


def test_history_search_token_offset_preserves_unicode_matching_policy():
    assert find_history_search_token_offset("Die Straße bleibt offen", "STRASSE") == 4
    assert find_history_search_token_offset("這是搜尋功能", "搜尋") == 2
    assert find_history_search_token_offset("版本10", "版本1") is None


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (None, 5, 5),
        ("invalid", 7, 7),
        (0, 5, 1),
        (999, 5, MAX_HISTORY_SEARCH_RESULTS),
        ("3", 5, 3),
    ],
)
def test_history_search_limit_coercion_is_stable(value, default, expected):
    assert bound_history_search_limit(value, default=default) == expected
