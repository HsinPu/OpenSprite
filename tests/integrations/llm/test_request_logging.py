from opensprite.core.contracts.llm_requests import LLMRequestMode
from opensprite.integrations.llm.request_logging import request_param_log_fields


def test_request_param_log_fields_are_sanitized_and_provider_neutral():
    fields = request_param_log_fields(
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "secret prompt"}],
            "tools": [{"type": "function", "function": {"name": "secret_tool"}}],
            "tool_choice": {"type": "auto"},
            "stream": True,
            "max_output_tokens": 321,
            "reasoning": {"effort": "high"},
        },
        request_mode=LLMRequestMode.MAIN_CHAT,
    )

    assert fields == {
        "mode": "main_chat",
        "model": "test-model",
        "messages": 1,
        "tools": 1,
        "tool_choice": '{"type":"auto"}',
        "stream": True,
        "max_tokens": 321,
        "reasoning": '{"effort":"high"}',
        "response_format": "-",
    }
    assert "secret prompt" not in str(fields)
    assert "secret_tool" not in str(fields)


def test_openrouter_request_log_fields_use_shared_sanitized_fields():
    fields = request_param_log_fields(
        {
            "model": "google/gemini-3-flash-preview",
            "messages": [{"role": "user", "content": "do not log this"}],
            "tools": [{"type": "function", "function": {"name": "secret_tool"}}],
            "tool_choice": "auto",
            "stream": True,
            "max_tokens": 123,
            "extra_body": {"reasoning": {"enabled": True, "effort": "high"}},
            "response_format": {"type": "json_object"},
        }
    )

    assert fields == {
        "mode": "main_chat",
        "model": "google/gemini-3-flash-preview",
        "messages": 1,
        "tools": 1,
        "tool_choice": "auto",
        "stream": True,
        "max_tokens": 123,
        "reasoning": '{"effort":"high","enabled":true}',
        "response_format": '{"type":"json_object"}',
    }
    assert "do not log this" not in str(fields)
    assert "secret_tool" not in str(fields)
