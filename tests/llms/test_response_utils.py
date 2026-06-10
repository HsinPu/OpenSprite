from types import SimpleNamespace

from opensprite.llms.response_utils import (
    coerce_content,
    coerce_reasoning_details,
    extract_openai_compatible_message,
    extract_openai_compatible_tool_calls,
    json_safe,
    safe_len,
    usage_payload,
)


def test_coerce_content_handles_none_strings_and_other_values():
    assert coerce_content(None) == ""
    assert coerce_content("hello") == "hello"
    assert coerce_content(123) == "123"


def test_safe_len_returns_length_or_na():
    assert safe_len([1, 2, 3]) == "3"
    assert safe_len(object()) == "n/a"


def test_usage_payload_prefers_model_dump():
    class Usage:
        def model_dump(self, *, exclude_none):
            assert exclude_none is True
            return {"prompt_tokens": 1, "completion_tokens": None}

    assert usage_payload(Usage()) == {"prompt_tokens": 1, "completion_tokens": None}


def test_usage_payload_copies_dict():
    source = {"total_tokens": 3}

    payload = usage_payload(source)

    assert payload == {"total_tokens": 3}
    assert payload is not source


def test_usage_payload_extracts_common_token_attrs():
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3, ignored=4)

    assert usage_payload(usage) == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
    }


def test_json_safe_converts_nested_values_and_model_dump_objects():
    class Nested:
        def model_dump(self):
            return {"value": "x"}

    class Payload:
        def model_dump(self):
            return {"items": (Nested(),), 1: "number-key"}

    assert json_safe(Payload()) == {"items": [{"value": "x"}], "1": "number-key"}


def test_coerce_reasoning_details_returns_dict_items_only():
    value = [{"type": "reasoning.text", "text": "thinking"}, "skip", SimpleNamespace(type="reasoning.text")]

    assert coerce_reasoning_details(value) == [{"type": "reasoning.text", "text": "thinking"}]


def test_coerce_reasoning_details_returns_none_for_empty_or_non_list_values():
    assert coerce_reasoning_details({"type": "reasoning.text"}) is None
    assert coerce_reasoning_details(["skip"]) is None


def test_extract_openai_compatible_tool_calls_parses_arguments_and_fallback_id():
    message = SimpleNamespace(
        tool_calls=[
            SimpleNamespace(
                id="",
                function=SimpleNamespace(name="lookup", arguments='{"query": "hello"}'),
            )
        ]
    )

    tool_calls = extract_openai_compatible_tool_calls(message, provider_name="TestProvider")

    assert len(tool_calls) == 1
    assert tool_calls[0].id == "tool_call_1"
    assert tool_calls[0].name == "lookup"
    assert tool_calls[0].arguments == {"query": "hello"}


def test_extract_openai_compatible_tool_calls_supports_dict_payloads():
    message = {
        "tool_calls": [
            {
                "id": "call-1",
                "function": {"name": "lookup", "arguments": '{"query": "hello"}'},
            }
        ]
    }

    tool_calls = extract_openai_compatible_tool_calls(message, provider_name="TestProvider")

    assert len(tool_calls) == 1
    assert tool_calls[0].id == "call-1"
    assert tool_calls[0].name == "lookup"
    assert tool_calls[0].arguments == {"query": "hello"}


def test_extract_openai_compatible_tool_calls_skips_missing_function_payload():
    message = SimpleNamespace(tool_calls=[SimpleNamespace(id="call-1", function=None)])

    assert extract_openai_compatible_tool_calls(message, provider_name="TestProvider") == []


def test_extract_openai_compatible_message_returns_first_message_and_choice():
    choice = SimpleNamespace(message=SimpleNamespace(content="hello"), finish_reason="stop")
    response = SimpleNamespace(model="model-a", choices=[choice], usage={"total_tokens": 1})

    result = extract_openai_compatible_message(response, provider_name="TestProvider", default_model="default-model")

    assert result.message.content == "hello"
    assert result.choice is choice
    assert result.fallback_response is None


def test_extract_openai_compatible_message_returns_usage_fallback_for_empty_choices():
    response = SimpleNamespace(id="response-id", model="model-a", object="chat.completion", choices=[], usage={"total_tokens": 1})

    result = extract_openai_compatible_message(response, provider_name="TestProvider", default_model="default-model")

    assert result.message is None
    assert result.fallback_response is not None
    assert result.fallback_response.content == ""
    assert result.fallback_response.model == "model-a"
    assert result.fallback_response.usage == {"total_tokens": 1}


def test_extract_openai_compatible_message_can_omit_usage_from_fallback():
    response = SimpleNamespace(id="response-id", model="model-a", object="chat.completion", choices=[], usage={"total_tokens": 1})

    result = extract_openai_compatible_message(
        response,
        provider_name="TestProvider",
        default_model="default-model",
        include_usage_in_fallback=False,
    )

    assert result.fallback_response is not None
    assert result.fallback_response.usage == {}


def test_extract_openai_compatible_message_returns_default_model_when_response_model_missing():
    response = SimpleNamespace(choices=[])

    result = extract_openai_compatible_message(response, provider_name="TestProvider", default_model="default-model")

    assert result.fallback_response is not None
    assert result.fallback_response.model == "default-model"


def test_extract_openai_compatible_message_returns_fallback_for_parse_failure():
    response = SimpleNamespace(model="model-a", choices=[object()], usage=None)

    result = extract_openai_compatible_message(response, provider_name="TestProvider", default_model="default-model")

    assert result.message is None
    assert result.fallback_response is not None
    assert result.fallback_response.model == "model-a"


def test_extract_openai_compatible_message_returns_fallback_for_missing_message():
    choice = SimpleNamespace(message=None, finish_reason="stop")
    response = SimpleNamespace(model="model-a", choices=[choice], usage=None)

    result = extract_openai_compatible_message(response, provider_name="TestProvider", default_model="default-model")

    assert result.message is None
    assert result.choice is choice
    assert result.fallback_response is not None
