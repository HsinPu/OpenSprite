from pathlib import Path

from opensprite.core.contracts.runtime_context import RUNTIME_CONTEXT_TAG, build_runtime_context


def test_build_runtime_context_preserves_metadata_format():
    context = build_runtime_context(
        workspace=Path("workspace") / "session",
        channel="web",
        session_id="session-1",
        current_time="2026-07-22 10:30 (Wednesday)",
    )

    assert context == "\n".join(
        (
            RUNTIME_CONTEXT_TAG,
            "Current Time: 2026-07-22 10:30 (Wednesday)",
            f"Workspace: {Path('workspace') / 'session'}",
            "Channel: web",
            "Session ID: session-1",
        )
    )


def test_build_runtime_context_omits_optional_metadata():
    assert build_runtime_context(current_time="fixed") == "\n".join(
        (RUNTIME_CONTEXT_TAG, "Current Time: fixed")
    )
