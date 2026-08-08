from opensprite.integrations.context.file_builder import FileContextBuilder


def test_file_builder_includes_memory_before_recent_summary_in_system_prompt(tmp_path):
    builder = FileContextBuilder(
        app_home=tmp_path / "home",
        bootstrap_dir=tmp_path / "bootstrap",
        memory_dir=tmp_path / "memory",
        tool_workspace=tmp_path / "workspace",
    )

    session_id = "telegram:room-1"
    builder.memory_store.write(session_id, "# User Preferences\n- concise replies")
    builder.recent_summary_store.write(session_id, "# Active Threads\n- current refactor")

    prompt = builder.build_system_prompt(session_id)

    assert prompt.count("# Memory") == 1
    assert prompt.count("# Recent Summary") == 1
    assert prompt.index("# Memory") < prompt.index("# Recent Summary")
    assert "# Recent Summary" in prompt
    assert "Approx size:" in prompt
    assert "Keep this document concise; use search tools for detailed past transcripts." in prompt
    assert "concise replies" in prompt
    assert "current refactor" in prompt
