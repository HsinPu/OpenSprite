import asyncio

from opensprite.modules.documents.user_profile import UserProfileUpdateService


def test_user_profile_update_service_delegates_to_consolidator():
    calls: list[str] = []

    class Consolidator:
        async def maybe_update(self, session_id: str) -> None:
            calls.append(session_id)

    asyncio.run(UserProfileUpdateService(Consolidator()).maybe_update("chat-1"))

    assert calls == ["chat-1"]


def test_user_profile_update_service_tolerates_missing_or_failed_consolidator():
    calls: list[str] = []

    class FailingConsolidator:
        async def maybe_update(self, session_id: str) -> None:
            calls.append(session_id)
            raise RuntimeError("profile update failed")

    asyncio.run(UserProfileUpdateService().maybe_update("chat-1"))
    asyncio.run(UserProfileUpdateService(FailingConsolidator()).maybe_update("chat-1"))

    assert calls == ["chat-1"]
