import base64

from opensprite.integrations.persistence.media import (
    InboundMediaPersistResult,
    InboundMediaPersistence,
)
from opensprite.modules.media.inbound import INBOUND_IMAGE_EXTENSIONS


def _data_url(mime_type: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def test_empty_media_does_not_resolve_or_create_a_workspace():
    def unexpected_workspace(_session_id: str):
        raise AssertionError("empty media must not resolve a workspace")

    persistence = InboundMediaPersistence(workspace_for_session=unexpected_workspace)

    result = persistence.persist_inbound_media_with_events(
        "web:empty",
        [],
        media_prefix="image",
        directory_name="images",
        extensions=INBOUND_IMAGE_EXTENSIONS,
    )

    assert result == InboundMediaPersistResult()


def test_media_persistence_keeps_event_order_and_unknown_mime_fallback(tmp_path):
    workspace = tmp_path / "sessions" / "web" / "room"
    persistence = InboundMediaPersistence(workspace_for_session=lambda _session_id: workspace)

    result = persistence.persist_inbound_media_with_events(
        "web:room",
        [
            _data_url("image/png", b"png"),
            "https://example.com/not-a-data-url.png",
            _data_url("image/tiff", b"tiff"),
        ],
        media_prefix="image",
        directory_name="images",
        extensions=INBOUND_IMAGE_EXTENSIONS,
    )

    assert [event["status"] for event in result.events] == ["persisted", "skipped", "persisted"]
    assert [event["index"] for event in result.events] == [1, 2, 3]
    assert result.events[1] == {
        "media_type": "image",
        "status": "skipped",
        "index": 2,
        "reason": "unsupported-payload",
    }
    assert result.files[0].startswith("images/inbound-")
    assert result.files[0].endswith("-1.png")
    assert result.files[1].startswith("images/inbound-")
    assert result.files[1].endswith("-3.bin")
    assert (workspace / result.files[0]).read_bytes() == b"png"
    assert (workspace / result.files[1]).read_bytes() == b"tiff"


def test_media_persistence_reports_filesystem_failure_and_continues(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "images").write_text("blocks directory creation", encoding="utf-8")
    persistence = InboundMediaPersistence(workspace_for_session=lambda _session_id: workspace)

    result = persistence.persist_inbound_media_with_events(
        "web:room",
        [
            _data_url("image/png", b"png"),
            _data_url("image/jpeg", b"jpeg"),
        ],
        media_prefix="image",
        directory_name="images",
        extensions=INBOUND_IMAGE_EXTENSIONS,
    )

    assert result.files == []
    assert [event["status"] for event in result.events] == ["failed", "failed"]
    assert [event["index"] for event in result.events] == [1, 2]
    assert [event["mime_type"] for event in result.events] == ["image/png", "image/jpeg"]
    assert all(event["media_type"] == "image" for event in result.events)
    assert all(event["error"] for event in result.events)
