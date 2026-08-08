from opensprite.core.text_changes import format_unified_diff, text_sha256


def test_text_sha256_is_stable_for_utf8_text():
    assert text_sha256("OpenSprite") == "acbdebc87b0c21eb4f1af44e197c5435a2ceeb24ec36ffd6b9a3227c8d7f6000"


def test_format_unified_diff_describes_creation_and_bounds_output():
    diff = format_unified_diff("notes.txt", None, "first\nsecond", max_chars=30)

    assert diff.startswith("--- /dev/null\n+++ b/notes.tx")
    assert "... (diff truncated, total " in diff


def test_format_unified_diff_reports_unchanged_text():
    assert format_unified_diff("notes.txt", "same", "same") == "(no changes)"
