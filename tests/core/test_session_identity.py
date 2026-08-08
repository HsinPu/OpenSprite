import hashlib

import pytest

from opensprite.core.session_identity import sanitize_path_segment, split_session_id


@pytest.mark.parametrize(
    ("session_id", "expected"),
    [
        (None, ("default", "default")),
        ("", ("default", "default")),
        ("   ", ("default", "default")),
        ("room-1", ("default", "room-1")),
        ("telegram:room-1", ("telegram", "room-1")),
        (" telegram : room:thread ", ("telegram", "room:thread")),
        (":room-1", ("default", "room-1")),
        ("telegram:", ("telegram", "default")),
    ],
)
def test_split_session_id_preserves_the_existing_normalization(session_id, expected):
    assert split_session_id(session_id) == expected


def test_sanitize_path_segment_preserves_safe_values_and_defaults():
    assert sanitize_path_segment("channel_1.test") == "channel_1.test"
    assert sanitize_path_segment("   ") == "default"


@pytest.mark.parametrize(
    ("raw", "slug"),
    [
        ("user / name", "user-name"),
        ("--foo---bar--", "foo-bar"),
        ("...", "default"),
    ],
)
def test_sanitize_path_segment_keeps_the_existing_slug_and_hash(raw, slug):
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]

    assert sanitize_path_segment(raw) == f"{slug}-{digest}"


def test_sanitize_path_segment_keeps_the_existing_truncation_and_hash_length():
    raw = "a" * 60
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]

    sanitized = sanitize_path_segment(raw, max_length=48)

    assert sanitized == f"{'a' * 48}-{digest}"
    assert len(sanitized) == 48 + 9
