"""Session workspace subagent_prompts/ merges with ~/.opensprite/subagent_prompts (session wins on overlap)."""

from pathlib import Path

from opensprite.integrations.workspace.paths import (
    get_session_workspace,
    get_subagent_prompts_dir,
)
from opensprite.integrations.subagents.prompts import (
    get_all_subagents,
    load_prompt,
    sync_subagent_prompts_from_package,
)
from opensprite.integrations.workspace.bootstrap import sync_templates


def test_bundled_subagent_prompt_sync_is_sorted_idempotent_and_preserves_existing(tmp_path):
    app_home = tmp_path / "home"

    first_changed = sync_subagent_prompts_from_package(app_home, silent=True)
    writer_prompt = app_home / "subagent_prompts" / "writer.md"
    writer_prompt.write_text("# Custom writer\n", encoding="utf-8")
    second_changed = sync_subagent_prompts_from_package(app_home, silent=True)

    assert first_changed == sorted(first_changed)
    assert first_changed
    assert second_changed == []
    assert writer_prompt.read_text(encoding="utf-8") == "# Custom writer\n"


def test_session_only_subagent_is_listed_and_loaded(tmp_path: Path) -> None:
    app_home = tmp_path / "home"
    sync_templates(app_home, silent=True)
    ws_root = app_home / "workspace"
    session_ws = get_session_workspace("telegram:t1", workspace_root=ws_root)
    session_dir = session_ws / "subagent_prompts"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-only.md").write_text(
        "---\nname: session-only\ndescription: from session\n---\nOnly in session.\n",
        encoding="utf-8",
    )

    merged = get_all_subagents(app_home, session_workspace=session_ws)
    assert "session-only" in merged
    assert merged["session-only"] == "from session"
    assert "Only in session." in load_prompt("session-only", app_home=app_home, session_workspace=session_ws)


def test_session_file_overrides_global_for_same_id(tmp_path: Path) -> None:
    app_home = tmp_path / "home"
    sync_templates(app_home, silent=True)
    user_dir = get_subagent_prompts_dir(app_home)
    (user_dir / "writer.md").write_text(
        "---\nname: writer\ndescription: from global\n---\nGLOBAL BODY\n",
        encoding="utf-8",
    )

    ws_root = app_home / "workspace"
    session_ws = get_session_workspace("telegram:t2", workspace_root=ws_root)
    session_dir = session_ws / "subagent_prompts"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "writer.md").write_text(
        "---\nname: writer\ndescription: from session\n---\nSESSION BODY\n",
        encoding="utf-8",
    )

    merged = get_all_subagents(app_home, session_workspace=session_ws)
    assert merged["writer"] == "from session"
    body = load_prompt("writer", app_home=app_home, session_workspace=session_ws)
    assert "SESSION BODY" in body
    assert "GLOBAL BODY" not in body
