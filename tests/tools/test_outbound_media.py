import asyncio

from opensprite.tools.outbound_media import SendMediaTool
from opensprite.tools.result_status import classify_tool_result_status


def test_send_media_tool_queues_explicit_payload():
    queued = []
    tool = SendMediaTool(
        queue_media=lambda kind, payload: queued.append((kind, payload)) or None,
        get_current_images=lambda: None,
        get_current_audios=lambda: None,
        get_current_videos=lambda: None,
    )

    result = asyncio.run(tool.execute(kind="image", payload="data:image/png;base64,aW1n"))

    assert result == "Queued image media for the next assistant reply."
    assert queued == [("image", "data:image/png;base64,aW1n")]


def test_send_media_tool_can_resend_current_audio_as_voice():
    queued = []
    tool = SendMediaTool(
        queue_media=lambda kind, payload: queued.append((kind, payload)) or None,
        get_current_images=lambda: None,
        get_current_audios=lambda: ["aud-0", "aud-1"],
        get_current_videos=lambda: None,
    )

    result = asyncio.run(tool.execute(kind="voice", media_index=1))

    assert result == "Queued voice media for the next assistant reply."
    assert queued == [("voice", "aud-1")]


def test_send_media_tool_reports_missing_current_media():
    tool = SendMediaTool(
        queue_media=lambda kind, payload: None,
        get_current_images=lambda: None,
        get_current_audios=lambda: None,
        get_current_videos=lambda: None,
    )

    result = asyncio.run(tool.execute(kind="video"))

    status = classify_tool_result_status(result)
    assert status.ok is False
    assert status.error_type == "SendMediaToolError"
    assert status.category == "media_unavailable"
    assert "No current video media is available" in status.error


def test_send_media_tool_reports_media_index_out_of_range():
    tool = SendMediaTool(
        queue_media=lambda kind, payload: None,
        get_current_images=lambda: ["image-0"],
        get_current_audios=lambda: None,
        get_current_videos=lambda: None,
    )

    result = asyncio.run(tool.execute(kind="image", media_index=2))
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "SendMediaToolError"
    assert status.category == "invalid_arguments"
    assert status.invalid_arguments is True
    assert "media_index 2 is out of range" in status.error
