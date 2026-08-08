import tomllib
from pathlib import Path


def test_runtime_dependencies_include_pytest_for_verify_tool():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.startswith("pytest") for dependency in dependencies)


def test_console_script_uses_application_cli_entrypoint():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["opensprite"] == "opensprite.app.cli.commands:app"


def test_bundled_templates_are_included_as_resources():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["opensprite"]

    assert "resources/templates/*.md" in package_data
    assert "resources/templates/memory/*.md" in package_data
    assert not any(entry.startswith("templates/") for entry in package_data)


def test_bundled_skill_resources_are_included_as_package_data():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["opensprite"]

    assert "resources/skills/*/*.md" in package_data
    assert not any(entry.startswith("skills/") for entry in package_data)


def test_bundled_subagent_prompts_are_included_as_resources():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["opensprite"]

    assert "resources/subagent_prompts/*.md" in package_data
    assert not any(entry.startswith("subagent_prompts/") for entry in package_data)
