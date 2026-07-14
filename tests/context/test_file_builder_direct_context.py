from opensprite.context.file_builder import FileContextBuilder


def _builder(tmp_path):
    return FileContextBuilder(
        app_home=tmp_path / "home",
        bootstrap_dir=tmp_path / "bootstrap",
        memory_dir=tmp_path / "memory",
        tool_workspace=tmp_path / "workspace",
        skills_root=tmp_path / "skills",
    )


def test_build_messages_does_not_classify_code_keywords(tmp_path):
    builder = _builder(tmp_path)

    messages = builder.build_messages(
        history=[],
        current_message="Please fix the failing pytest in tests/test_app.py",
        channel="web",
        session_id="web:browser-1",
    )

    assert [message["role"] for message in messages] == ["system", "user", "user"]
    assert "# Workspace Task Guidance" not in messages[0]["content"]
    assert "# Workspace Operating Policy" in messages[0]["content"]


def test_build_messages_does_not_classify_history_keywords(tmp_path):
    builder = _builder(tmp_path)

    messages = builder.build_messages(
        history=[],
        current_message="Use the earlier fix again and compare it to what you found before.",
        channel="web",
        session_id="web:browser-1",
    )

    assert [message["role"] for message in messages] == ["system", "user", "user"]
    assert "# Retrieval Guidance" not in messages[0]["content"]


def test_system_prompt_does_not_read_existing_active_task_file(tmp_path):
    builder = _builder(tmp_path)
    session_workspace = builder.get_session_workspace("telegram:room-1")
    session_workspace.mkdir(parents=True, exist_ok=True)
    (session_workspace / "ACTIVE_TASK.md").write_text(
        "sentinel legacy active task content",
        encoding="utf-8",
    )

    prompt = builder.build_system_prompt("telegram:room-1")

    assert "sentinel legacy active task content" not in prompt
    assert "Active task:" not in prompt
