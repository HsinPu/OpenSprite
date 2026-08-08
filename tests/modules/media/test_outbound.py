from opensprite.core.contracts.tool_results import classify_tool_result_status
from opensprite.modules.media.outbound import queue_outbound_media, queued_outbound_media


def test_queue_outbound_media_preserves_stable_reply_shape():
    media: dict[str, list[str]] = {}

    assert queue_outbound_media(media, "image", "images/out.png") is None
    assert queue_outbound_media(media, "voice", "voices/out.wav") is None

    assert queued_outbound_media(media) == {
        "images": ["images/out.png"],
        "voices": ["voices/out.wav"],
        "audios": [],
        "videos": [],
    }


def test_queue_outbound_media_reports_missing_turn_context():
    status = classify_tool_result_status(
        queue_outbound_media(None, "image", "images/out.png") or ""
    )

    assert status.ok is False
    assert status.error_type == "SendMediaToolError"
    assert status.category == "missing_turn_context"


def test_queue_outbound_media_reports_invalid_arguments():
    unsupported = classify_tool_result_status(
        queue_outbound_media({}, "sticker", "payload") or ""
    )
    empty = classify_tool_result_status(queue_outbound_media({}, "image", " ") or "")

    assert unsupported.ok is False
    assert unsupported.category == "invalid_arguments"
    assert unsupported.invalid_arguments is True
    assert empty.ok is False
    assert empty.category == "invalid_arguments"
    assert empty.invalid_arguments is True
