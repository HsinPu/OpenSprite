from opensprite.context.paths import (
    get_session_curator_state_file,
    get_session_learning_state_file,
    get_session_memory_dir,
    get_session_memory_file,
    get_session_recent_summary_state_file,
    get_session_skills_dir,
    get_session_state_dir,
    get_session_workspace,
    get_user_overlay_file,
    get_user_overlay_index_file,
    get_user_overlay_state_file,
    get_user_profile_file,
    sync_templates,
)


def test_session_workspace_is_stable_per_session_and_separates_sessions(tmp_path):
    workspace_root = tmp_path / "workspace"

    workspace_a_first = get_session_workspace("telegram:user-a", workspace_root=workspace_root)
    workspace_a_second = get_session_workspace("telegram:user-a", workspace_root=workspace_root)
    workspace_b = get_session_workspace("telegram:user-b", workspace_root=workspace_root)

    assert workspace_a_first == workspace_a_second
    assert workspace_a_first != workspace_b
    assert workspace_a_first.name != workspace_b.name


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


def test_session_skills_dir_is_nested_under_the_same_session_workspace(tmp_path):
    workspace_root = tmp_path / "workspace"

    workspace = get_session_workspace("telegram:user-a", workspace_root=workspace_root)
    skills_dir = get_session_skills_dir("telegram:user-a", workspace_root=workspace_root)

    assert skills_dir.parent == workspace
    assert skills_dir.name == "skills"


def test_user_profile_file_is_stable_per_session_and_separates_sessions(tmp_path):
    app_home = tmp_path / "home"
    workspace_root = app_home / "workspace"

    profile_a_first = get_user_profile_file(
        app_home=app_home, session_id="telegram:user-a", workspace_root=workspace_root
    )
    profile_a_second = get_user_profile_file(
        app_home=app_home, session_id="telegram:user-a", workspace_root=workspace_root
    )
    profile_b = get_user_profile_file(app_home=app_home, session_id="telegram:user-b", workspace_root=workspace_root)

    assert profile_a_first == profile_a_second
    assert profile_a_first != profile_b
    assert profile_a_first.parent != profile_b.parent
    assert profile_a_first.name == "USER.md"
    assert profile_a_first.parent == get_session_workspace("telegram:user-a", workspace_root=workspace_root)


def test_session_memory_paths_are_nested_under_the_same_session_workspace(tmp_path):
    workspace_root = tmp_path / "workspace"

    workspace = get_session_workspace("telegram:user-a", workspace_root=workspace_root)
    memory_dir = get_session_memory_dir("telegram:user-a", workspace_root=workspace_root)
    memory_file = get_session_memory_file("telegram:user-a", workspace_root=workspace_root)
    state_dir = get_session_state_dir("telegram:user-a", workspace_root=workspace_root)
    summary_state_file = get_session_recent_summary_state_file("telegram:user-a", workspace_root=workspace_root)

    assert memory_dir.parent == workspace
    assert memory_dir.name == "memory"
    assert memory_file.parent == memory_dir
    assert memory_file.name == "MEMORY.md"
    assert state_dir.parent == workspace
    assert state_dir.name == "state"
    assert summary_state_file.parent == state_dir


def test_session_curator_and_learning_state_files_live_under_session_state_dir(tmp_path):
    workspace_root = tmp_path / "workspace"

    state_dir = get_session_state_dir("telegram:user-a", workspace_root=workspace_root)
    curator_state = get_session_curator_state_file("telegram:user-a", workspace_root=workspace_root)
    learning_state = get_session_learning_state_file("telegram:user-a", workspace_root=workspace_root)

    assert curator_state.parent == state_dir
    assert curator_state.name == ".curator_state.json"
    assert learning_state.parent == state_dir
    assert learning_state.name == ".learning_state.json"


def test_user_overlay_paths_are_stable_and_separate_overlay_ids(tmp_path):
    app_home = tmp_path / "home"

    overlay_a_file = get_user_overlay_file("web:profile-a", app_home=app_home)
    overlay_a_index = get_user_overlay_index_file("web:profile-a", app_home=app_home)
    overlay_a_state = get_user_overlay_state_file("web:profile-a", app_home=app_home)
    overlay_b_file = get_user_overlay_file("web:profile-b", app_home=app_home)

    assert overlay_a_file != overlay_b_file
    assert overlay_a_file.parent != overlay_b_file.parent
    assert overlay_a_file.name == "USER_OVERLAY.md"
    assert overlay_a_index.name == "user_overlay_index.json"
    assert overlay_a_state.name == ".user_overlay_state.json"
    assert overlay_a_index.parent == overlay_a_state.parent
