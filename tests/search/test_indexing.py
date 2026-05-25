from opensprite.search.indexing import build_history_chunks, chunk_text


def test_chunk_text_normalizes_and_splits_overlap():
    chunks = chunk_text("alpha   beta gamma delta", chunk_size=12, chunk_overlap=4)

    assert chunks == ["alpha beta g", "ta gamma del", "delta"]


def test_build_history_chunks_marks_message_source():
    chunks = build_history_chunks(
        role="assistant",
        content="Earlier we fixed the cleanup path.",
        tool_name=None,
        created_at=10.0,
    )

    assert len(chunks) == 1
    assert chunks[0].source_type == "history"
    assert chunks[0].role == "assistant"
    assert chunks[0].content == "Earlier we fixed the cleanup path."
