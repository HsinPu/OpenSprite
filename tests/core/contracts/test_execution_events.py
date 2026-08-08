from opensprite.core.contracts.execution_events import (
    COMPACTED_CONVERSATION_STATE_HEADING,
    COMPACTED_EXECUTION_STATE_HEADING,
    contains_compaction_handoff,
    format_repeated_invalid_tool_call_content,
)


def test_contains_compaction_handoff_detects_shared_headings():
    assert contains_compaction_handoff(f"{COMPACTED_CONVERSATION_STATE_HEADING}\nsummary")
    assert contains_compaction_handoff(f"{COMPACTED_EXECUTION_STATE_HEADING}\nsummary")
    assert not contains_compaction_handoff("# Other State\nsummary")


def test_repeated_invalid_tool_call_fallback_formats_configured_template():
    assert format_repeated_invalid_tool_call_content("REPEATED\n{result}", "bad args") == "REPEATED\nbad args"


def test_repeated_invalid_tool_call_fallback_uses_result_without_template():
    assert format_repeated_invalid_tool_call_content("", " bad args ") == "bad args"


def test_repeated_invalid_tool_call_fallback_preserves_bad_template():
    assert format_repeated_invalid_tool_call_content("REPEATED {missing}", "bad args") == "REPEATED {missing}\n\nbad args"
