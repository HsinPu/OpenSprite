from opensprite.agent.media_inbound_policy import INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON


def test_inbound_media_reason_markers_are_stable():
    assert INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON == "unsupported-payload"
