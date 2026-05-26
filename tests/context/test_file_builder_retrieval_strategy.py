from opensprite.context.file_builder import FileContextBuilder
from opensprite.context.paths import sync_templates
from opensprite.subagent_prompts import get_all_subagents


def test_file_builder_includes_retrieval_strategy_in_system_prompt(tmp_path):
    app_home = tmp_path / "home"
    sync_templates(app_home, silent=True)
    builder = FileContextBuilder(
        app_home=app_home,
        bootstrap_dir=app_home / "bootstrap",
        memory_dir=app_home / "memory",
        tool_workspace=app_home / "workspace",
    )

    prompt = builder.build_system_prompt("telegram:room-1")

    assert "## External Knowledge Tools" in prompt
    assert "Use `web_research` for broad, current, comparative, ambiguous, or public-information questions" in prompt
    assert "search_knowledge" not in prompt
    assert "Use the optional `queries` argument" in prompt


def test_file_builder_includes_available_subagents_in_system_prompt(tmp_path):
    app_home = tmp_path / "home"
    sync_templates(app_home, silent=True)
    builder = FileContextBuilder(
        app_home=app_home,
        bootstrap_dir=app_home / "bootstrap",
        memory_dir=app_home / "memory",
        tool_workspace=app_home / "workspace",
    )

    prompt = builder.build_system_prompt("telegram:room-1")

    assert "# Available Subagents" in prompt
    assert "Use `delegate` when a focused subproblem would benefit from a dedicated prompt." in prompt
    first_name, first_description = next(iter(get_all_subagents(app_home).items()))
    assert f"- `{first_name}`: {first_description}" in prompt


def test_sync_templates_repairs_stale_tools_bootstrap(tmp_path):
    app_home = tmp_path / "home"
    sync_templates(app_home, silent=True)
    tools_path = app_home / "bootstrap" / "TOOLS.md"
    user_path = app_home / "bootstrap" / "USER.md"
    tools_path.write_text("# Old tools\n\n- `search_knowledge`\n", encoding="utf-8")
    user_path.write_text("# Custom user bootstrap\n", encoding="utf-8")

    changed = sync_templates(app_home, silent=True)

    assert any(item.replace("\\", "/") == "bootstrap/TOOLS.md" for item in changed)
    assert "search_knowledge" not in tools_path.read_text(encoding="utf-8")
    assert user_path.read_text(encoding="utf-8") == "# Custom user bootstrap\n"
