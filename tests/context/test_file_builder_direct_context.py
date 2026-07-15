from opensprite.context.file_builder import FileContextBuilder


def _builder(tmp_path):
    return FileContextBuilder(
        app_home=tmp_path / "home",
        bootstrap_dir=tmp_path / "bootstrap",
        memory_dir=tmp_path / "memory",
        tool_workspace=tmp_path / "workspace",
        skills_root=tmp_path / "skills",
    )


def test_build_messages_uses_standard_context_for_code_request(tmp_path):
    builder = _builder(tmp_path)

    messages = builder.build_messages(
        history=[],
        current_message="Please fix the failing pytest in tests/test_app.py",
        channel="web",
        session_id="web:browser-1",
    )

    assert [message["role"] for message in messages] == ["system", "user", "user"]
    assert "# Workspace Operating Policy" in messages[0]["content"]


def test_build_messages_uses_standard_context_for_follow_up_request(tmp_path):
    builder = _builder(tmp_path)

    messages = builder.build_messages(
        history=[],
        current_message="Use the earlier fix again and compare it to what you found before.",
        channel="web",
        session_id="web:browser-1",
    )

    assert [message["role"] for message in messages] == ["system", "user", "user"]
    assert "# Workspace Operating Policy" in messages[0]["content"]
