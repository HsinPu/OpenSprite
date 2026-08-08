from opensprite.core.contracts.channel_identity import (
    ChannelIdentity,
    build_session_id,
    channel_from_session,
    external_chat_id_from_session,
    normalize_identifier,
)


def test_normalize_identifier_produces_stable_config_key():
    assert normalize_identifier(" My Channel! ") == "my_channel"
    assert normalize_identifier("", fallback="web") == "web"


def test_build_session_id_normalizes_instance_and_defaults_external_chat():
    assert build_session_id("My Channel", " chat-1 ") == "my_channel:chat-1"
    assert build_session_id("", None) == "unknown:default"


def test_session_id_parts_preserve_transport_identifier():
    assert channel_from_session("telegram-main:chat:42") == "telegram-main"
    assert external_chat_id_from_session("telegram-main:chat:42") == "chat:42"
    assert channel_from_session("chat-42") == "unknown"
    assert external_chat_id_from_session("chat-42") == "chat-42"


def test_channel_identity_builds_session_id_from_instance_and_chat():
    identity = ChannelIdentity(
        channel_instance_id="Web Main",
        channel_type="web",
        external_chat_id="browser-1",
        external_user_id="user-1",
        sender_name="User",
    )

    assert identity.session_id == "web_main:browser-1"
