from opensprite.integrations.context.file_builder import FileContextBuilder
from opensprite.integrations.documents.user_profile import create_user_profile_store
from opensprite.integrations.documents.user_overlay import UserOverlayIndexStore, UserOverlayStore
from opensprite.integrations.workspace.bootstrap import sync_templates
from opensprite.modules.documents.user_overlay import (
    RelevantUserOverlayContextService,
    UserOverlayPromotionService,
    UserOverlayRetrievalPlanner,
)


def test_user_overlay_promotion_service_merges_profile_and_memory(tmp_path):
    overlay_store = UserOverlayStore(app_home=tmp_path / "home")
    index_store = UserOverlayIndexStore(app_home=tmp_path / "home")
    service = UserOverlayPromotionService(overlay_store=overlay_store, index_store=index_store)

    result = service.update_from_session_documents(
        "web:profile-a",
        profile_block="- Prefers concise replies.\n- Works mostly in Python.",
        response_language_block="- Traditional Chinese (Taiwan)",
        memory_text="# User Preferences\n- Prefers concise replies.\n\n# Important Facts\n- Uses FastAPI for backend work.\n",
        source_session_id="web:browser-1",
        source_run_id="run_1",
    )

    overlay_text = overlay_store.read("web:profile-a")
    index_payload = index_store.read("web:profile-a")

    assert result["changed"] is True
    assert "- Prefers concise replies." in overlay_text
    assert "- Uses FastAPI for backend work." in overlay_text
    assert "- Traditional Chinese (Taiwan)" in overlay_text
    assert index_payload["response_language"]["text"] == "Traditional Chinese (Taiwan)"
    assert index_payload["preferences"][0]["text"] == "Prefers concise replies."
    assert index_payload["stable_facts"][0]["text"] == "Uses FastAPI for backend work."


def test_user_overlay_promotion_preserves_existing_preferences(tmp_path):
    overlay_store = UserOverlayStore(app_home=tmp_path / "home")
    index_store = UserOverlayIndexStore(app_home=tmp_path / "home")
    service = UserOverlayPromotionService(overlay_store=overlay_store, index_store=index_store)
    overlay_store.write(
        "web:profile-a",
        "# Stable Preferences\n- Prefers concise replies.\n\n# Stable Facts\n- Maintains OpenSprite.\n\n# Response Language\n- Traditional Chinese (Taiwan)\n",
    )

    result = service.update_from_session_documents(
        "web:profile-a",
        profile_block=(
            "### Communication Preferences\n"
            "- Prefers minimal diffs.\n\n"
            "### Work Context\n"
            "- No learned work context yet.\n\n"
            "### Stable Constraints\n"
            "- No learned stable constraints yet."
        ),
        response_language_block="- not set",
        memory_text="# Important Facts\n- Uses FastAPI for backend work.\n",
        source_session_id="web:browser-1",
    )

    overlay_text = overlay_store.read("web:profile-a")

    assert result["changed"] is True
    assert "- Prefers concise replies." in overlay_text
    assert "- Prefers minimal diffs." in overlay_text
    assert "- Maintains OpenSprite." in overlay_text
    assert "- Uses FastAPI for backend work." in overlay_text
    assert "No learned work context yet." not in overlay_text
    assert "- Traditional Chinese (Taiwan)" in overlay_text


def test_second_session_can_read_promoted_overlay(tmp_path):
    app_home = tmp_path / "home"
    sync_templates(app_home, silent=True)
    overlay_store = UserOverlayStore(app_home=app_home)
    index_store = UserOverlayIndexStore(app_home=app_home)
    service = UserOverlayPromotionService(overlay_store=overlay_store, index_store=index_store)
    service.update_from_session_documents(
        "web:profile-a",
        profile_block="- Prefers concise replies.",
        response_language_block="- Traditional Chinese (Taiwan)",
        memory_text="# Important Facts\n- Maintains OpenSprite.\n",
        source_session_id="web:browser-1",
    )

    builder = FileContextBuilder(
        app_home=app_home,
        bootstrap_dir=app_home / "bootstrap",
        memory_dir=app_home / "memory",
        tool_workspace=app_home / "workspace",
        skills_root=tmp_path / "skills",
    )
    profile = create_user_profile_store(app_home, "web:browser-2")
    profile.write_managed_block("- Session-local note only.")
    builder.set_session_overlay_id("web:browser-2", "web:profile-a")

    prompt = builder.build_system_prompt("web:browser-2")

    assert "- Prefers concise replies." in prompt
    assert "- Maintains OpenSprite." in prompt
    assert "- Session-local note only." in prompt


def test_user_overlay_retrieval_planner_selects_relevant_items(tmp_path):
    index_store = UserOverlayIndexStore(app_home=tmp_path / "home")
    index_store.write(
        "web:profile-a",
        {
            "updated_at": "2026-05-04T12:00:00Z",
            "response_language": {"text": "Traditional Chinese (Taiwan)", "confidence": 0.95},
            "preferences": [
                {"id": "pref:concise", "text": "Prefer concise replies.", "confidence": 0.9, "updated_at": "2026-05-04T12:00:00Z"},
            ],
            "stable_facts": [
                {"id": "fact:python", "text": "Works mostly on Python backend tasks.", "confidence": 0.85, "updated_at": "2026-05-04T12:00:00Z"},
                {"id": "fact:frontend", "text": "Maintains frontend design systems.", "confidence": 0.7, "updated_at": "2026-05-04T12:00:00Z"},
            ],
        },
    )
    planner = UserOverlayRetrievalPlanner(index_store=index_store)

    context = planner.build_context("web:profile-a", "Help me with this Python backend refactor.")

    assert "# Relevant Stable User Overlay" in context
    assert "Traditional Chinese (Taiwan)" in context
    assert "Works mostly on Python backend tasks." in context
    assert "Maintains frontend design systems." not in context


def test_relevant_user_overlay_context_tracks_session_overlay_and_builds_context(tmp_path):
    index_store = UserOverlayIndexStore(app_home=tmp_path / "home")
    index_store.write(
        "web:profile-a",
        {
            "updated_at": "2026-05-04T12:00:00Z",
            "response_language": {"text": "Traditional Chinese (Taiwan)", "confidence": 0.95},
            "preferences": [
                {
                    "id": "pref:concise",
                    "text": "Prefer concise replies.",
                    "confidence": 0.9,
                    "updated_at": "2026-05-04T12:00:00Z",
                },
            ],
            "stable_facts": [
                {
                    "id": "fact:python",
                    "text": "Works mostly on Python backend tasks.",
                    "confidence": 0.85,
                    "updated_at": "2026-05-04T12:00:00Z",
                },
            ],
        },
    )
    service = RelevantUserOverlayContextService(index_store=index_store)

    assert service.build_context("web:browser-1", "Python backend refactor") == ""

    service.set_session_overlay_id("web:browser-1", "web:profile-a")
    context = service.build_context("web:browser-1", "Python backend refactor")

    assert "# Relevant Stable User Overlay" in context
    assert "Traditional Chinese (Taiwan)" in context
    assert "Works mostly on Python backend tasks." in context


def test_relevant_user_overlay_context_normalizes_ids_and_clears_one_session(tmp_path):
    service = RelevantUserOverlayContextService(
        index_store=UserOverlayIndexStore(app_home=tmp_path / "home")
    )

    service.set_session_overlay_id("  web:browser-1  ", "  web:profile-a  ")
    service.set_session_overlay_id("web:browser-2", "web:profile-b")
    service.set_session_overlay_id("  ", "  web:profile-default  ")

    assert service.get_session_overlay_id("web:browser-1") == "web:profile-a"
    assert service.get_session_overlay_id("  web:browser-1  ") == "web:profile-a"
    assert service.get_session_overlay_id("web:browser-2") == "web:profile-b"
    assert service.get_session_overlay_id("default") == "web:profile-default"
    assert service.get_session_overlay_id("  ") == "web:profile-default"

    service.set_session_overlay_id("web:browser-1", None)

    assert service.get_session_overlay_id("web:browser-1") is None
    assert service.get_session_overlay_id("web:browser-2") == "web:profile-b"
    assert service.get_session_overlay_id("default") == "web:profile-default"

    service.set_session_overlay_id("default", "  ")

    assert service.get_session_overlay_id("default") is None
    assert service.get_session_overlay_id("web:browser-2") == "web:profile-b"
