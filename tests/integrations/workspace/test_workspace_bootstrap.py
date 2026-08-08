"""Behavior tests for bundled workspace resource provisioning."""

from opensprite.integrations.workspace.bootstrap import load_bootstrap_files, sync_templates


def test_load_bootstrap_files_returns_all_sections_in_stable_order(tmp_path):
    (tmp_path / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    (tmp_path / "USER.md").write_text("# User\n", encoding="utf-8")

    loaded = load_bootstrap_files(tmp_path)

    assert list(loaded) == ["IDENTITY", "SOUL", "AGENTS", "TOOLS", "USER"]
    assert loaded == {
        "IDENTITY": "",
        "SOUL": "# Soul\n",
        "AGENTS": "",
        "TOOLS": "",
        "USER": "# User\n",
    }


def test_sync_templates_does_not_seed_default_session_workspace(tmp_path):
    app_home = tmp_path / "home"

    changed = sync_templates(app_home, silent=True)

    assert (app_home / "bootstrap").is_dir()
    assert {
        "bootstrap/IDENTITY.md",
        "bootstrap/SOUL.md",
        "bootstrap/AGENTS.md",
        "bootstrap/TOOLS.md",
        "bootstrap/USER.md",
    }.issubset({item.replace("\\", "/") for item in changed})
    assert not (app_home / "workspace" / "sessions" / "default" / "default").exists()


def test_sync_templates_copies_bundled_skill_resources_to_the_public_app_path(tmp_path):
    app_home = tmp_path / "home"

    changed = sync_templates(app_home, silent=True)

    normalized_changed = {item.replace("\\", "/") for item in changed}
    expected_skills = {
        "agent-creator-design",
        "coding",
        "memory",
        "skill-creator-design",
    }
    assert {
        f"skills/{skill_name}/SKILL.md" for skill_name in expected_skills
    }.issubset(normalized_changed)
    for skill_name in expected_skills:
        skill_file = app_home / "skills" / skill_name / "SKILL.md"
        assert skill_file.is_file()
        assert f"name: {skill_name}" in skill_file.read_text(encoding="utf-8")


def test_sync_templates_copies_bundled_subagent_prompt_resources(tmp_path):
    app_home = tmp_path / "home"

    changed = sync_templates(app_home, silent=True)

    normalized_changed = {item.replace("\\", "/") for item in changed}
    expected_prompts = {
        "api-designer",
        "async-concurrency-reviewer",
        "bug-fixer",
        "code-reviewer",
        "debugger",
        "editor",
        "fact-checker",
        "implementer",
        "integration-engineer",
        "migration-writer",
        "observability-engineer",
        "outliner",
        "pattern-matcher",
        "performance-optimizer",
        "porting-planner",
        "refactorer",
        "reference-analyzer",
        "researcher",
        "security-reviewer",
        "test-implementer",
        "test-writer",
        "writer",
    }
    assert {
        f"subagent_prompts/{prompt_name}.md" for prompt_name in expected_prompts
    }.issubset(normalized_changed)
    for prompt_name in expected_prompts:
        prompt_file = app_home / "subagent_prompts" / f"{prompt_name}.md"
        assert prompt_file.is_file()
        assert prompt_file.read_text(encoding="utf-8").startswith("---\n")


def test_sync_templates_preserves_existing_custom_bootstrap_files(tmp_path):
    app_home = tmp_path / "custom"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    agents_file = bootstrap_dir / "AGENTS.md"
    tools_file = bootstrap_dir / "TOOLS.md"
    agents_content = "# My rules\n\nKeep this custom rule.\n"
    tools_content = "# My tools\n\nKeep this custom tool note.\n"
    agents_file.write_text(agents_content, encoding="utf-8")
    tools_file.write_text(tools_content, encoding="utf-8")

    changed = sync_templates(app_home, silent=True)

    normalized_changed = {item.replace("\\", "/") for item in changed}
    assert "bootstrap/AGENTS.md" not in normalized_changed
    assert "bootstrap/TOOLS.md" not in normalized_changed
    assert agents_file.read_text(encoding="utf-8") == agents_content
    assert tools_file.read_text(encoding="utf-8") == tools_content
