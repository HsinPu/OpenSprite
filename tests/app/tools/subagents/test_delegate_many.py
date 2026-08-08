from pathlib import Path

from opensprite.app.tools.subagents.delegate_many import _eligible_subagents


def _write_custom_subagent(
    session_workspace: Path,
    subagent_id: str,
    *,
    tool_profile: str,
) -> None:
    prompt_dir = session_workspace / "subagent_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / f"{subagent_id}.md").write_text(
        "---\n"
        f"name: {subagent_id}\n"
        f"description: Custom {tool_profile} helper.\n"
        f"tool_profile: {tool_profile}\n"
        "---\n"
        "Handle the delegated task.\n",
        encoding="utf-8",
    )


def test_eligible_subagents_respects_custom_session_tool_profiles(tmp_path):
    app_home = tmp_path / "opensprite-home"
    session_workspace = tmp_path / "session-workspace"
    _write_custom_subagent(
        session_workspace,
        "custom-researcher",
        tool_profile="research",
    )
    _write_custom_subagent(
        session_workspace,
        "custom-implementer",
        tool_profile="implementation",
    )

    eligible = _eligible_subagents(app_home, session_workspace)

    assert "custom-researcher" in eligible
    assert "custom-implementer" not in eligible
