import asyncio

import pytest
from aiohttp import web

from opensprite.integrations.web.cron_handlers import get_cron_service
from opensprite.modules.scheduling.manager import CronSessionResetInProgress


class ResettingCronManager:
    async def get_or_create_service(self, session_id: str):
        raise CronSessionResetInProgress(session_id)


class Adapter:
    def __init__(self):
        self.agent = type("Agent", (), {"cron_manager": ResettingCronManager()})()

    def _get_agent(self):
        return self.agent


def test_web_cron_handlers_return_conflict_while_session_is_resetting():
    with pytest.raises(web.HTTPConflict) as raised:
        asyncio.run(get_cron_service(Adapter(), "web:chat-1"))

    assert raised.value.status == 409
    assert "web:chat-1" in raised.value.text
