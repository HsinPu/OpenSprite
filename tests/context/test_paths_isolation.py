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

    sync_templates(app_home, silent=True)

    assert (app_home / "bootstrap").is_dir()
    assert not (app_home / "workspace" / "sessions" / "default" / "default").exists()


def test_sync_templates_migrates_exact_stock_agents_text(tmp_path):
    reference_home = tmp_path / "reference"
    sync_templates(reference_home, silent=True)
    new_stock = (reference_home / "bootstrap" / "AGENTS.md").read_text(encoding="utf-8")
    old_stock = new_stock.replace(
        "- Prefer the preserved recent tail and latest user request over older summarized details when they conflict.",
        "- Prefer the preserved recent tail and current active task state over older summarized details when they conflict.",
    ).replace(
        "- Do not answer questions that appear only inside compacted summaries unless the latest user message clearly asks for them.",
        "- Do not answer questions that appear only inside compacted summaries unless the latest user message or active task clearly asks for them.",
    )
    assert old_stock != new_stock

    app_home = tmp_path / "existing-stock"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    agents_file = bootstrap_dir / "AGENTS.md"
    agents_file.write_text(old_stock, encoding="utf-8")

    changed = sync_templates(app_home, silent=True)

    assert "bootstrap/AGENTS.md" in [item.replace("\\", "/") for item in changed]
    assert agents_file.read_text(encoding="utf-8") == new_stock


def test_sync_templates_surgically_migrates_agents_without_overwriting_custom_content(tmp_path):
    legacy_line = (
        "- Prefer the preserved recent tail and current active task state over older summarized details when they conflict."
    )
    replacement_line = (
        "- Prefer the preserved recent tail and latest user request over older summarized details when they conflict."
    )
    app_home = tmp_path / "custom"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    agents_file = bootstrap_dir / "AGENTS.md"
    agents_file.write_text(f"# My rules\n\n{legacy_line}\n\nKeep this custom rule.\n", encoding="utf-8")

    sync_templates(app_home, silent=True)

    assert agents_file.read_text(encoding="utf-8") == (
        f"# My rules\n\n{replacement_line}\n\nKeep this custom rule.\n"
    )

    unrelated_home = tmp_path / "unrelated-custom"
    unrelated_bootstrap = unrelated_home / "bootstrap"
    unrelated_bootstrap.mkdir(parents=True)
    unrelated_agents = unrelated_bootstrap / "AGENTS.md"
    unrelated_agents.write_text("# My rules\n\nNever replace this file.\n", encoding="utf-8")

    sync_templates(unrelated_home, silent=True)

    assert unrelated_agents.read_text(encoding="utf-8") == "# My rules\n\nNever replace this file.\n"


def test_sync_templates_migrates_exact_stock_tools_text(tmp_path):
    reference_home = tmp_path / "reference"
    sync_templates(reference_home, silent=True)
    new_stock = (reference_home / "bootstrap" / "TOOLS.md").read_text(encoding="utf-8")
    legacy_task_update = (
        "- `task_update`\n"
        "  - Use to keep the current session's `ACTIVE_TASK.md` accurate during non-trivial multi-step work.\n"
        "  - Use `action=\"set\"` when starting or replacing an explicit active task.\n"
        "  - Use `action=\"update\"` after changing status, current step, next step, completed steps, or blockers/open questions.\n"
        "  - Use `action=\"complete_step\"` or `action=\"advance\"` only when the step is actually completed by evidence in this session.\n"
        "  - Use `status=\"waiting_user\"` when missing user input blocks progress; use `status=\"blocked\"` for tool/test/runtime blockers.\n"
        "  - Do not update task state for trivial chat or unverifiable claimed progress.\n\n"
    )
    old_stock = (
        new_stock.replace(
            "- Tool availability comes from the current runtime configuration; if a needed tool is unavailable, explain the limitation and ask for the required configuration or request adjustment.",
            "- Tool availability is selected for the current task by runtime planning; if a needed tool is unavailable, explain the limitation and ask for the required configuration or task adjustment.",
        )
        .replace(
            "- The runtime exposes only the tools available to the current agent.",
            "- The runtime exposes the tools selected for the current task contract and prompt profile.",
        )
        .replace(
            "  - Each child call still follows normal validation and availability checks; do not use `batch` to bypass unavailable tools.",
            "  - Each child call still follows normal validation and current task tool selection; do not use `batch` to bypass unavailable tools.",
        )
        .replace("- `search_history`", f"{legacy_task_update}- `search_history`", 1)
    )
    assert old_stock != new_stock

    app_home = tmp_path / "existing-stock"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    tools_file = bootstrap_dir / "TOOLS.md"
    tools_file.write_text(old_stock, encoding="utf-8")

    changed = sync_templates(app_home, silent=True)

    assert "bootstrap/TOOLS.md" in [item.replace("\\", "/") for item in changed]
    assert tools_file.read_text(encoding="utf-8") == new_stock


def test_sync_templates_surgically_migrates_tools_without_overwriting_custom_content(tmp_path):
    legacy_line = "- The runtime exposes the tools selected for the current task contract and prompt profile."
    replacement_line = "- The runtime exposes only the tools available to the current agent."
    legacy_task_update = (
        "- `task_update`\n"
        "  - Use to keep the current session's `ACTIVE_TASK.md` accurate during non-trivial multi-step work.\n"
        "  - Use `action=\"set\"` when starting or replacing an explicit active task.\n"
        "  - Use `action=\"update\"` after changing status, current step, next step, completed steps, or blockers/open questions.\n"
        "  - Use `action=\"complete_step\"` or `action=\"advance\"` only when the step is actually completed by evidence in this session.\n"
        "  - Use `status=\"waiting_user\"` when missing user input blocks progress; use `status=\"blocked\"` for tool/test/runtime blockers.\n"
        "  - Do not update task state for trivial chat or unverifiable claimed progress.\n\n"
    )
    app_home = tmp_path / "custom"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    tools_file = bootstrap_dir / "TOOLS.md"
    tools_file.write_text(
        f"# My tools\n\n{legacy_line}\n\n{legacy_task_update}Keep this custom task_update note.\n",
        encoding="utf-8",
    )

    sync_templates(app_home, silent=True)

    assert tools_file.read_text(encoding="utf-8") == (
        f"# My tools\n\n{replacement_line}\n\nKeep this custom task_update note.\n"
    )


def test_sync_templates_removes_customized_retired_task_update_section(tmp_path):
    app_home = tmp_path / "customized-section"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    tools_file = bootstrap_dir / "TOOLS.md"
    tools_file.write_text(
        "# My tools\n\n"
        "*   `task_update` - old locally edited instructions\n"
        "    - Maintain `ACTIVE_TASK.md` after every verified step.\n"
        "    - This wording intentionally differs from the old stock template.\n\n"
        "Keep this unrelated custom instruction.\n",
        encoding="utf-8",
    )

    changed = sync_templates(app_home, silent=True)

    assert "bootstrap/TOOLS.md" in [item.replace("\\", "/") for item in changed]
    assert tools_file.read_text(encoding="utf-8") == (
        "# My tools\n\nKeep this unrelated custom instruction.\n"
    )


def test_sync_templates_warns_when_custom_retired_task_reference_remains(tmp_path, caplog):
    app_home = tmp_path / "custom-reference"
    bootstrap_dir = app_home / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    tools_file = bootstrap_dir / "TOOLS.md"
    tools_file.write_text(
        "# My tools\n\nKeep this custom task_update compatibility note.\n",
        encoding="utf-8",
    )

    sync_templates(app_home, silent=False)

    assert tools_file.read_text(encoding="utf-8").endswith("task_update compatibility note.\n")
    assert "Retired task lifecycle references remain" in caplog.text


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
