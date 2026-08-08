import pytest

from opensprite.modules.subagents.profiles import (
    IMPLEMENTATION_PROFILE,
    READ_ONLY_PROFILE,
    RESEARCH_PROFILE,
    TESTING_PROFILE,
    profile_for_subagent,
    supports_parallel_delegation,
)


@pytest.mark.parametrize(
    ("prompt_type", "expected_profile"),
    [
        ("researcher", RESEARCH_PROFILE),
        ("implementer", IMPLEMENTATION_PROFILE),
        ("test-writer", TESTING_PROFILE),
        ("code-reviewer", READ_ONLY_PROFILE),
    ],
)
def test_profile_for_subagent_uses_builtin_policy(prompt_type, expected_profile):
    assert profile_for_subagent(prompt_type) is expected_profile


def test_profile_for_custom_subagent_defaults_to_read_only():
    assert profile_for_subagent("custom-agent") is READ_ONLY_PROFILE


def test_profile_for_subagent_normalizes_quoted_metadata_override():
    assert profile_for_subagent("custom-agent", tool_profile='"research"') is RESEARCH_PROFILE


def test_profile_for_subagent_rejects_invalid_metadata_override():
    with pytest.raises(
        ValueError,
        match="subagent 'custom-agent' has invalid tool_profile 'root'",
    ):
        profile_for_subagent("custom-agent", tool_profile="root")


@pytest.mark.parametrize(
    ("tool_profile", "expected"),
    [
        ("read-only", True),
        ("research", True),
        ("implementation", False),
        ("testing", False),
    ],
)
def test_parallel_delegation_follows_profile_safety(tool_profile, expected):
    assert supports_parallel_delegation("custom-agent", tool_profile=tool_profile) is expected
