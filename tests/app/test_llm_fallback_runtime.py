import asyncio

from opensprite.app.bootstrap import create_agent
from opensprite.app.llm_fallback import UnconfiguredLLM
from opensprite.app.llm.runtime_provider import is_llm_configured
from opensprite.config import Config


def test_create_agent_uses_fallback_llm_when_unconfigured(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    config = Config.from_json(config_path)
    config.storage.path = str(tmp_path / "messages.sqlite3")

    assert is_llm_configured(config) is False

    agent, mq, cron_manager = asyncio.run(create_agent(config))

    try:
        assert isinstance(agent.provider, UnconfiguredLLM)
        assert agent.llm_configured is False
        assert mq is not None
        assert cron_manager is not None
    finally:
        asyncio.run(agent.close_background_maintenance())
        asyncio.run(agent.close_background_skill_reviews())
        asyncio.run(agent.close_background_processes())
