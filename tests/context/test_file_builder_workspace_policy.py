from opensprite.context.file_builder import FileContextBuilder


def test_file_builder_includes_workspace_operating_policy(tmp_path):
    builder = FileContextBuilder(
        app_home=tmp_path / "home",
        bootstrap_dir=tmp_path / "bootstrap",
        memory_dir=tmp_path / "memory",
        tool_workspace=tmp_path / "workspace",
        skills_root=tmp_path / "skills",
    )

    prompt = builder.build_system_prompt("telegram:room-1")

    assert "## Workspace Operating Policy" in prompt
    assert "Treat the active workspace as trusted working context." in prompt
    assert "read files, search files, edit files, apply patches" in prompt
    assert "inspect -> edit -> verify -> summarize" in prompt
    assert "external side effects" in prompt
