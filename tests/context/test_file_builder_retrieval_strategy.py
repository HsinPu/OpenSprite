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

