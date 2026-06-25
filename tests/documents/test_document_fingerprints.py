from opensprite.documents.curator import fingerprint_text_directory as legacy_fingerprint_text_directory
from opensprite.documents.document_fingerprints import fingerprint_text_directory


def test_fingerprint_text_directory_handles_missing_roots(tmp_path):
    assert fingerprint_text_directory(None) == ""
    assert fingerprint_text_directory(tmp_path / "missing") == ""


def test_fingerprint_text_directory_tracks_paths_and_content(tmp_path):
    root = tmp_path / "docs"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "a.txt").write_text("alpha", encoding="utf-8")
    (nested / "b.txt").write_text("bravo", encoding="utf-8")

    original = fingerprint_text_directory(root)

    (nested / "b.txt").write_text("changed", encoding="utf-8")
    changed_content = fingerprint_text_directory(root)

    (root / "renamed.txt").write_text((root / "a.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "a.txt").unlink()
    changed_path = fingerprint_text_directory(root)

    assert original
    assert changed_content != original
    assert changed_path != changed_content


def test_curator_reexports_fingerprint_helper_for_compatibility():
    assert legacy_fingerprint_text_directory is fingerprint_text_directory
