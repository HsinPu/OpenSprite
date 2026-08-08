"""Content-only workspace diagnostics behavior."""

from pathlib import Path

from opensprite.modules.tools.workspace_diagnostics import format_post_edit_diagnostics


def test_formats_successful_supported_content_diagnostics():
    result, failed = format_post_edit_diagnostics(
        [
            (Path("app.py"), "app.py", "VALUE = 1\n"),
            (Path("settings.json"), "settings.json", '{"enabled": true}\n'),
            (Path("pyproject.toml"), "pyproject.toml", "[project]\nname = 'opensprite'\n"),
        ]
    )

    assert failed is False
    assert result == (
        "Diagnostics:\n"
        "- app.py [python_syntax] OK\n"
        "- settings.json [json_parse] OK\n"
        "- pyproject.toml [toml_parse] OK"
    )


def test_formats_parse_failure_without_changing_its_contract():
    result, failed = format_post_edit_diagnostics(
        [
            (Path("broken.py"), "broken.py", "def broken(:\n"),
            (Path("broken.json"), "broken.json", "{not json}"),
        ]
    )

    assert failed is True
    assert result.startswith("Post-edit diagnostics failed for 2 file(s).\n\n")
    assert "- broken.py [python_syntax]: invalid syntax" in result
    assert "- broken.json [json_parse]:" in result


def test_ignores_content_types_without_a_configured_diagnostic():
    result, failed = format_post_edit_diagnostics(
        [(Path("notes.txt"), "notes.txt", "plain text\n")]
    )

    assert result == ""
    assert failed is False
