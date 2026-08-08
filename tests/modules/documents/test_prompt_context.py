from opensprite.modules.documents.prompt_context import (
    PromptMemoryDocument,
    PromptMemoryDocumentService,
)


class _StaticReader:
    def __init__(self, content: str):
        self.content = content
        self.session_ids: list[str] = []

    def read(self, session_id: str) -> str:
        self.session_ids.append(session_id)
        return self.content


def test_prompt_memory_documents_render_in_stable_order():
    memory = "# User Preferences\n- concise replies"
    recent_summary = "# Active Threads\n- prompt refactor"
    memory_reader = _StaticReader(memory)
    summary_reader = _StaticReader(recent_summary)
    service = PromptMemoryDocumentService(
        memory_store=memory_reader,
        recent_summary_store=summary_reader,
    )

    sections = service.build_prompt_sections("telegram:room-1")

    assert sections == [
        f"# Memory\n\n{PromptMemoryDocumentService.size_hint(memory)}\n\n{memory}",
        f"# Recent Summary\n\n{PromptMemoryDocumentService.size_hint(recent_summary)}\n\n{recent_summary}",
    ]
    assert memory_reader.session_ids == ["telegram:room-1"]
    assert summary_reader.session_ids == ["telegram:room-1"]


def test_prompt_memory_documents_skip_empty_sections():
    service = PromptMemoryDocumentService(
        memory_store=_StaticReader(""),
        recent_summary_store=_StaticReader(""),
    )

    assert service.build_prompt_sections("telegram:room-1") == []


def test_prompt_memory_documents_skip_whitespace_only_sections():
    service = PromptMemoryDocumentService(
        memory_store=_StaticReader("  \n"),
        recent_summary_store=_StaticReader("\t"),
    )

    assert service.build_prompt_sections("telegram:room-1") == []


def test_prompt_memory_documents_skip_only_the_empty_reader():
    recent_summary = "# Active Threads\n- keep current work"
    service = PromptMemoryDocumentService(
        memory_store=_StaticReader(""),
        recent_summary_store=_StaticReader(recent_summary),
    )

    assert service.build_prompt_sections("telegram:room-1") == [
        f"# Recent Summary\n\n{PromptMemoryDocumentService.size_hint(recent_summary)}\n\n{recent_summary}"
    ]


def test_prompt_memory_document_render_trims_outer_whitespace():
    content = "memory entry"
    document = PromptMemoryDocument(title="Memory", content=f"  {content}\n")

    assert document.render() == (
        f"# Memory\n\n{PromptMemoryDocumentService.size_hint(content)}\n\n{content}"
    )
