from opensprite.core.contracts.llm import ChatMessage
from opensprite.integrations.llm.request_adapters import (
    OPENAI_CHAT_REQUEST_PROFILE,
    OPENAI_RESPONSES_REQUEST_PROFILE,
    build_llm_request,
    normalize_openai_compatible_messages,
)


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


def test_normalize_openai_compatible_messages_uses_dict_role_defaults():
    assert normalize_openai_compatible_messages([{"content": "hello"}]) == [{"role": "?", "content": "hello"}]


def test_openai_responses_request_profile_uses_responses_param_shape():
    params = build_llm_request(
        OPENAI_RESPONSES_REQUEST_PROFILE.options(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
            tools=[{"type": "function", "name": "lookup", "parameters": {}}],
            max_tokens=123,
            stream=True,
        )
    )

    assert params == {
        "model": "gpt-test",
        "input": [{"role": "user", "content": "hello"}],
        "max_output_tokens": 123,
        "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        "stream": True,
    }


def test_build_llm_request_includes_chat_response_format_when_set():
    params = build_llm_request(
        OPENAI_CHAT_REQUEST_PROFILE.options(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
            response_format={"type": "json_object"},
        )
    )

    assert params["response_format"] == {"type": "json_object"}


def test_build_llm_request_includes_provider_extra_body_when_set():
    params = build_llm_request(
        OPENAI_RESPONSES_REQUEST_PROFILE.options(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
            extra_body={"reasoning": {"enabled": True, "effort": "high"}},
        )
    )

    assert params["extra_body"] == {"reasoning": {"enabled": True, "effort": "high"}}


def test_build_llm_request_includes_top_level_extra_params_when_set():
    params = build_llm_request(
        OPENAI_RESPONSES_REQUEST_PROFILE.options(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
            extra_params={"reasoning": {"effort": "medium"}},
        )
    )

    assert params["reasoning"] == {"effort": "medium"}
