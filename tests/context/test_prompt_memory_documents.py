from opensprite.context.message_history import (
    LearningLedger,
    PromptMemoryDocumentService,
    RelevantLearningContextService,
    RelevantUserOverlayContextService,
)
from opensprite.documents.memory import MemoryStore
from opensprite.documents.recent_summary import RecentSummaryStore
from opensprite.documents.user_overlay import UserOverlayIndexStore


def test_prompt_memory_documents_render_memory_and_recent_summary_sections(tmp_path):
    app_home = tmp_path / "home"
    workspace_root = tmp_path / "workspace"
    memory_dir = tmp_path / "memory"
    memory_store = MemoryStore(memory_dir, app_home=app_home, workspace_root=workspace_root)
    recent_summary_store = RecentSummaryStore(memory_dir, app_home=app_home, workspace_root=workspace_root)
    service = PromptMemoryDocumentService(
        memory_store=memory_store,
        recent_summary_store=recent_summary_store,
    )

    memory = "# User Preferences\n- concise replies"
    recent_summary = "# Active Threads\n- prompt refactor"
    memory_store.write("telegram:room-1", memory)
    recent_summary_store.write("telegram:room-1", recent_summary)

    sections = service.build_prompt_sections("telegram:room-1")

    assert sections == [
        f"# Memory\n\n{PromptMemoryDocumentService.size_hint(memory)}\n\n{memory}",
        f"# Recent Summary\n\n{PromptMemoryDocumentService.size_hint(recent_summary)}\n\n{recent_summary}",
    ]


def test_prompt_memory_documents_skip_empty_sections(tmp_path):
    memory_dir = tmp_path / "memory"
    service = PromptMemoryDocumentService(
        memory_store=MemoryStore(
            memory_dir,
            app_home=tmp_path / "home",
            workspace_root=tmp_path / "workspace",
        ),
        recent_summary_store=RecentSummaryStore(
            memory_dir,
            app_home=tmp_path / "home",
            workspace_root=tmp_path / "workspace",
        ),
    )

    assert service.build_prompt_sections("telegram:room-1") == []


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


def test_relevant_user_overlay_context_clears_session_overlay(tmp_path):
    service = RelevantUserOverlayContextService(index_store=UserOverlayIndexStore(app_home=tmp_path / "home"))

    service.set_session_overlay_id("web:browser-1", "web:profile-a")
    service.set_session_overlay_id("web:browser-1", None)

    assert service.get_session_overlay_id("web:browser-1") is None


def test_relevant_learning_context_uses_attached_learning_ledger():
    ledger = LearningLedger()
    service = RelevantLearningContextService()

    assert service.build_context("telegram:room-1", "pytest assertions") == ""

    service.set_learning_ledger(ledger)
    ledger.record_learning(
        "telegram:room-1",
        kind="skill",
        target_id="pytest-helper",
        summary="Reusable pytest workflow for updating assertions.",
        source_run_id="run-1",
    )

    context = service.build_context("telegram:room-1", "pytest assertions")

    assert "# Relevant Learned Context" in context
    assert "pytest-helper" in context
