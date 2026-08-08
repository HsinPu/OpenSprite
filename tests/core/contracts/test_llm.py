"""Tests for provider-neutral LLM contracts."""

from dataclasses import fields

from opensprite.core.contracts.llm import (
    CHAT_CONTENT_TYPE_IMAGE_URL,
    CHAT_CONTENT_TYPE_TEXT,
    CHAT_ROLE_ASSISTANT,
    CHAT_ROLE_SYSTEM,
    CHAT_ROLE_TOOL,
    CHAT_ROLE_USER,
    ChatMessage,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)


def test_llm_contract_constants_keep_provider_wire_values():
    assert CHAT_ROLE_SYSTEM == "system"
    assert CHAT_ROLE_USER == "user"
    assert CHAT_ROLE_ASSISTANT == "assistant"
    assert CHAT_ROLE_TOOL == "tool"
    assert CHAT_CONTENT_TYPE_TEXT == "text"
    assert CHAT_CONTENT_TYPE_IMAGE_URL == "image_url"


def test_llm_contract_dataclass_fields_and_defaults_are_stable():
    assert [field.name for field in fields(ToolCall)] == ["id", "name", "arguments"]
    assert [field.name for field in fields(LLMResponse)] == [
        "content",
        "model",
        "tool_calls",
        "usage",
        "finish_reason",
        "reasoning_details",
    ]
    assert [field.name for field in fields(ChatMessage)] == [
        "role",
        "content",
        "tool_call_id",
        "tool_calls",
        "reasoning_details",
    ]
    assert [field.name for field in fields(ToolDefinition)] == [
        "name",
        "description",
        "parameters",
    ]

    message = ChatMessage(role="assistant")
    response = LLMResponse(content="done", model="test")
    assert message.content == ""
    assert message.tool_call_id is None
    assert message.tool_calls is None
    assert message.reasoning_details is None
    assert response.tool_calls == []
    assert response.usage == {}
    assert response.finish_reason is None
    assert response.reasoning_details is None


def test_llm_response_mutable_defaults_are_independent():
    first = LLMResponse(content="first", model="test")
    second = LLMResponse(content="second", model="test")

    first.tool_calls.append(ToolCall(id="call-1", name="read_file", arguments={}))
    first.usage["input_tokens"] = 3

    assert second.tool_calls == []
    assert second.usage == {}


def test_chat_message_create_user_message_preserves_text_and_image_shapes():
    assert ChatMessage.create_user_message("hello") == ChatMessage(
        role="user",
        content="hello",
    )
    assert ChatMessage.create_user_message(
        "look",
        ["data:image/png;base64,first", "data:image/jpeg;base64,second"],
    ) == ChatMessage(
        role="user",
        content=[
            {"type": "text", "text": "look"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,first"},
            },
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,second"},
            },
        ],
    )
