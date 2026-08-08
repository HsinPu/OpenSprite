import asyncio

from opensprite.modules.documents.recent_summary import RecentSummaryUpdateService


def test_recent_summary_update_service_delegates_to_consolidator():
    calls: list[str] = []

    class Consolidator:
        async def maybe_update(self, session_id: str) -> None:
            calls.append(session_id)

    asyncio.run(RecentSummaryUpdateService(Consolidator()).maybe_update("chat-1"))

    assert calls == ["chat-1"]


def test_recent_summary_update_service_tolerates_missing_or_failed_consolidator():
    calls: list[str] = []

    class FailingConsolidator:
        async def maybe_update(self, session_id: str) -> None:
            calls.append(session_id)
            raise RuntimeError("recent summary update failed")

    asyncio.run(RecentSummaryUpdateService().maybe_update("chat-1"))
    asyncio.run(RecentSummaryUpdateService(FailingConsolidator()).maybe_update("chat-1"))

    assert calls == ["chat-1"]
