from opensprite.core.contracts.persistence import StoredMessage
from opensprite.modules.documents.skill_review_prompts import (
    SKILL_REVIEW_SYSTEM,
    SKILL_REVIEW_TRANSCRIPT_TOO_SHORT_REASON,
    build_skill_review_user_content,
    format_stored_messages_for_transcript,
)


def test_skill_review_system_prompt_includes_shared_curator_boundaries():
    assert "Shared curator rules for session skills" in SKILL_REVIEW_SYSTEM
    assert "Document responsibility boundaries:" in SKILL_REVIEW_SYSTEM
    assert "Session skills: reusable procedures only" in SKILL_REVIEW_SYSTEM


def test_skill_review_reason_markers_are_stable():
    assert SKILL_REVIEW_TRANSCRIPT_TOO_SHORT_REASON == "transcript-too-short"


def test_format_stored_messages_for_transcript_includes_tool_name():
    rows = [
        StoredMessage(role="user", content="hi", timestamp=1.0),
        StoredMessage(role="assistant", content="hello", timestamp=2.0),
        StoredMessage(role="tool", content="output", timestamp=3.0, tool_name="read_file"),
    ]

    text = format_stored_messages_for_transcript(rows)

    assert "USER" in text
    assert "ASSISTANT" in text
    assert "[tool:read_file]" in text
    assert "output" in text


def test_format_stored_messages_for_transcript_applies_both_size_limits():
    rows = [
        StoredMessage(role="user", content="abcdefgh", timestamp=1.0),
        StoredMessage(role="assistant", content="second", timestamp=2.0),
    ]

    text = format_stored_messages_for_transcript(
        rows,
        per_message_max_chars=4,
        transcript_max_chars=30,
    )

    assert "abcd\n… (truncated)" in text
    assert text.endswith("… (transcript truncated)")


def test_build_skill_review_user_content_wraps_transcript():
    body = build_skill_review_user_content("LINE1")

    assert "--- TRANSCRIPT ---" in body
    assert "LINE1" in body
    assert "Nothing to save" in body
