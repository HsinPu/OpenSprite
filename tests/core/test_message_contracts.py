from dataclasses import fields

import pytest

from opensprite.core.contracts.messages import (
    CLI_VIA_WEB_TURN_SOURCE,
    CLIENT_TURN_ID_METADATA_KEY,
    RESPONSE_KIND_METADATA_KEY,
    SESSION_COMMAND_RESPONSE_KIND,
    TURN_SOURCE_METADATA_KEY,
    AssistantMessage,
    UserMessage,
)
from opensprite.core.ports.channels import MessageAdapter


def test_message_contract_constants_are_stable():
    assert CLIENT_TURN_ID_METADATA_KEY == "client_turn_id"
    assert RESPONSE_KIND_METADATA_KEY == "response_kind"
    assert SESSION_COMMAND_RESPONSE_KIND == "session_command"
    assert TURN_SOURCE_METADATA_KEY == "source"
    assert CLI_VIA_WEB_TURN_SOURCE == "cli_via_web"


def test_user_message_fields_and_defaults_are_stable():
    assert [field.name for field in fields(UserMessage)] == [
        "text",
        "channel",
        "external_chat_id",
        "session_id",
        "sender_id",
        "sender_name",
        "images",
        "audios",
        "videos",
        "metadata",
        "raw",
    ]
    first = UserMessage(text="first")
    second = UserMessage(text="second")
    assert first.channel == "unknown"
    assert first.metadata == {}
    assert first.metadata is not second.metadata


def test_assistant_message_fields_and_defaults_are_stable():
    assert [field.name for field in fields(AssistantMessage)] == [
        "text",
        "channel",
        "external_chat_id",
        "session_id",
        "images",
        "voices",
        "audios",
        "videos",
        "metadata",
        "raw",
    ]
    first = AssistantMessage(text="first")
    second = AssistantMessage(text="second")
    assert first.channel == "unknown"
    assert first.metadata == {}
    assert first.metadata is not second.metadata


def test_message_adapter_remains_abstract():
    with pytest.raises(TypeError):
        MessageAdapter()
