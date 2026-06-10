from opensprite.llms.base import ChatMessage
from opensprite.llms.request_builder import normalize_openai_compatible_messages


def test_normalize_openai_compatible_messages_omits_reasoning_details_by_default():
    messages = [
        ChatMessage(
            role="assistant",
            content="previous answer",
            tool_calls=[{"id": "call-1", "type": "function"}],
            reasoning_details=[{"type": "reasoning.text", "text": "thinking"}],
        )
    ]

    assert normalize_openai_compatible_messages(messages) == [
        {
            "role": "assistant",
            "content": "previous answer",
            "tool_calls": [{"id": "call-1", "type": "function"}],
        }
    ]


def test_normalize_openai_compatible_messages_includes_reasoning_details_when_enabled():
    messages = [
        {
            "role": "assistant",
            "content": "previous answer",
            "reasoning_details": [{"type": "reasoning.text", "text": "thinking"}],
        }
    ]

    assert normalize_openai_compatible_messages(messages, include_reasoning_details=True) == [
        {
            "role": "assistant",
            "content": "previous answer",
            "reasoning_details": [{"type": "reasoning.text", "text": "thinking"}],
        }
    ]


def test_normalize_openai_compatible_messages_uses_legacy_dict_defaults():
    assert normalize_openai_compatible_messages([{"content": "hello"}]) == [{"role": "?", "content": "hello"}]
