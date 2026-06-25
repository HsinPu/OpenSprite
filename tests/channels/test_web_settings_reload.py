from opensprite.channels import web_settings_reload
from opensprite.config.schema import Config


class _Logger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append((message, args))


class _Adapter:
    def __init__(self, agent, config_path):
        self.agent = agent
        self.config_path = config_path

    def _get_agent(self):
        return self.agent

    def _get_config_path(self):
        return self.config_path

    def _json_safe(self, value):
        return {"safe": value}


class _RuntimeAgent:
    def __init__(self):
        self.calls = []

    def reload_browser_from_config(self, config):
        self.calls.append(("browser", config.source_path))
        return {"browser": True}

    def reload_llm_from_config(self, config):
        self.calls.append(("llm", config.source_path))
        return {"llm": True}

    def reload_media_from_config(self, config):
        self.calls.append(("media", config.source_path))
        return {"media": True}

    def reload_web_search_from_config(self, config):
        self.calls.append(("web_search", config.source_path))
        return {"web_search": True}


def _config_path(tmp_path):
    path = tmp_path / "opensprite.json"
    Config.copy_template(path)
    return path


def test_agent_runtime_reload_skips_when_restart_is_not_required(tmp_path):
    agent = _RuntimeAgent()
    adapter = _Adapter(agent, _config_path(tmp_path))
    logger = _Logger()
    payload = {"restart_required": False}

    result = web_settings_reload.reload_browser_from_config(adapter, payload, logger=logger)

    assert result is payload
    assert agent.calls == []
    assert logger.warnings == []


def test_agent_runtime_reload_updates_payload_with_json_safe_runtime(tmp_path):
    agent = _RuntimeAgent()
    config_path = _config_path(tmp_path)
    adapter = _Adapter(agent, config_path)

    result = web_settings_reload.reload_browser_from_config(
        adapter,
        {"restart_required": True, "section": "browser"},
        logger=_Logger(),
    )

    assert result == {
        "restart_required": False,
        "section": "browser",
        "runtime_reloaded": True,
        "runtime": {"safe": {"browser": True}},
    }
    assert agent.calls == [("browser", config_path)]


def test_agent_runtime_reload_reports_agent_errors(tmp_path):
    class FailingAgent:
        def reload_browser_from_config(self, _config):
            raise RuntimeError("reload failed")

    logger = _Logger()
    adapter = _Adapter(FailingAgent(), _config_path(tmp_path))

    result = web_settings_reload.reload_browser_from_config(
        adapter,
        {"restart_required": True},
        logger=logger,
    )

    assert result == {
        "restart_required": True,
        "runtime_reloaded": False,
        "reload_error": "reload failed",
    }
    assert len(logger.warnings) == 1
    message, args = logger.warnings[0]
    assert message == "Browser runtime reload failed after settings change: {}"
    assert str(args[0]) == "reload failed"


def test_agent_runtime_reload_wrappers_call_expected_agent_methods(tmp_path):
    agent = _RuntimeAgent()
    config_path = _config_path(tmp_path)
    adapter = _Adapter(agent, config_path)
    logger = _Logger()

    wrappers = [
        web_settings_reload.reload_agent_llm_from_config,
        web_settings_reload.reload_media_from_config,
        web_settings_reload.reload_web_search_from_config,
        web_settings_reload.reload_browser_from_config,
    ]

    for wrapper in wrappers:
        wrapper(adapter, {"restart_required": True}, logger=logger)

    assert agent.calls == [
        ("llm", config_path),
        ("media", config_path),
        ("web_search", config_path),
        ("browser", config_path),
    ]
