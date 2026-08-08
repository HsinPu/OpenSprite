from opensprite.integrations.workspace.paths import (
    build_workspace_resolver,
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
    get_user_profile_file,
    resolve_workspace_path,
    resolve_workspace_root,
)


def test_session_workspace_is_stable_per_session_and_separates_sessions(tmp_path):
    workspace_root = tmp_path / "workspace"

    workspace_a_first = get_session_workspace("telegram:user-a", workspace_root=workspace_root)
    workspace_a_second = get_session_workspace("telegram:user-a", workspace_root=workspace_root)
    workspace_b = get_session_workspace("telegram:user-b", workspace_root=workspace_root)

    assert workspace_a_first == workspace_a_second
    assert workspace_a_first != workspace_b
    assert workspace_a_first.name != workspace_b.name


def test_tool_workspace_path_helpers_normalize_root_and_block_escapes(tmp_path):
    workspace = resolve_workspace_root(tmp_path / "workspace")
    inside = resolve_workspace_path(workspace, "src/main.py")

    assert workspace == (tmp_path / "workspace").resolve()
    assert workspace.is_dir()
    assert inside == (workspace / "src" / "main.py").resolve(strict=False)
    assert resolve_workspace_path(workspace, "../outside.txt") is None
    assert resolve_workspace_path(workspace, str(tmp_path / "outside.txt")) is None


def test_build_workspace_resolver_preserves_static_and_dynamic_workspace_behavior(tmp_path):
    static_workspace = tmp_path / "static"
    dynamic_workspace = tmp_path / "dynamic"

    static_resolver = build_workspace_resolver(static_workspace)
    dynamic_resolver = build_workspace_resolver(workspace_resolver=lambda: dynamic_workspace)

    assert static_resolver() == static_workspace.resolve()
    assert dynamic_resolver() == dynamic_workspace.resolve()
    assert static_workspace.is_dir()
    assert dynamic_workspace.is_dir()

    try:
        build_workspace_resolver()
    except ValueError as exc:
        assert str(exc) == "workspace or workspace_resolver is required"
    else:
        raise AssertionError("Expected a missing workspace configuration to fail")


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
    overlay_b_file = get_user_overlay_file("web:profile-b", app_home=app_home)

    assert overlay_a_file != overlay_b_file
    assert overlay_a_file.parent != overlay_b_file.parent
    assert overlay_a_file.name == "USER_OVERLAY.md"
    assert overlay_a_index.name == "user_overlay_index.json"
