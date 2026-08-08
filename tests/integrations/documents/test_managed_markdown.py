import pytest

from opensprite.integrations.documents.managed_markdown import ManagedMarkdownDocument


START = "<!-- START -->"
END = "<!-- END -->"
DEFAULT = "- default"


def _document(file_path, *, anchor_heading=None, bootstrap_text=""):
    return ManagedMarkdownDocument(
        file_path,
        start_marker=START,
        end_marker=END,
        default_content=DEFAULT,
        heading="## Managed",
        intro="Managed by OpenSprite.",
        anchor_heading=anchor_heading,
        bootstrap_text=bootstrap_text,
    )


def test_constructor_creates_parent_and_appends_managed_section(tmp_path):
    file_path = tmp_path / "nested" / "USER.md"

    document = _document(file_path, bootstrap_text="# User\n")

    assert file_path.parent.is_dir()
    assert document.read_managed_block() == DEFAULT
    assert file_path.read_text(encoding="utf-8") == (
        "# User\n\n"
        "## Managed\n\n"
        "Managed by OpenSprite.\n\n"
        f"{START}\n{DEFAULT}\n{END}\n"
    )


def test_constructor_inserts_section_before_first_anchor(tmp_path):
    file_path = tmp_path / "USER.md"
    file_path.write_text("# User\n\n## Notes\nkeep\n\n## Notes\nkeep too\n", encoding="utf-8")

    _document(file_path, anchor_heading="## Notes")

    text = file_path.read_text(encoding="utf-8")
    assert text.index("## Managed") < text.index("## Notes")
    assert text.count("## Managed") == 1
    assert text.count("## Notes") == 2
    assert "keep too" in text


def test_read_repairs_existing_empty_file_after_bootstrap_only_constructor_write(tmp_path):
    file_path = tmp_path / "USER.md"
    file_path.write_text("", encoding="utf-8")
    document = _document(file_path, bootstrap_text="# Bootstrap\n")

    assert file_path.read_text(encoding="utf-8") == "# Bootstrap\n"

    repaired = document.read_text()

    assert repaired.startswith("# Bootstrap\n\n## Managed")
    assert START in repaired
    assert END in repaired


def test_write_preserves_outside_text_and_blank_uses_default(tmp_path):
    file_path = tmp_path / "USER.md"
    file_path.write_text(f"before\n{START}\nold\n{END}\nafter\n", encoding="utf-8")
    document = _document(file_path)

    document.write_managed_block("  new value  ")

    assert file_path.read_text(encoding="utf-8") == f"before\n{START}\nnew value\n{END}\nafter\n"

    document.write_managed_block("  ")

    assert document.read_managed_block() == DEFAULT
    assert file_path.read_text(encoding="utf-8") == f"before\n{START}\n{DEFAULT}\n{END}\nafter\n"


def test_reversed_markers_read_default_and_write_raises(tmp_path):
    file_path = tmp_path / "USER.md"
    file_path.write_text(f"{END}\ncontent\n{START}\n", encoding="utf-8")
    document = _document(file_path)

    assert document.read_managed_block() == DEFAULT
    with pytest.raises(ValueError, match="Managed markers missing"):
        document.write_managed_block("new")


def test_two_managed_documents_share_one_file_without_removing_each_other(tmp_path):
    file_path = tmp_path / "USER.md"
    first = _document(file_path, bootstrap_text="# User\n")
    second = ManagedMarkdownDocument(
        file_path,
        start_marker="<!-- SECOND:START -->",
        end_marker="<!-- SECOND:END -->",
        default_content="second default",
        heading="## Second",
        intro="Second block.",
    )

    first.write_managed_block("first value")
    second.write_managed_block("second value")

    assert first.read_managed_block() == "first value"
    assert second.read_managed_block() == "second value"
    text = file_path.read_text(encoding="utf-8")
    assert START in text
    assert "<!-- SECOND:START -->" in text
