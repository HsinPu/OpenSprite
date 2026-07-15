from agent_test_helpers import make_agent_loop

from opensprite.config.schema import Config
from opensprite.tools.audio import TranscribeAudioTool
from opensprite.tools.browser import BrowserNavigateTool
from opensprite.tools.registry import ToolRegistry
from opensprite.tools.web_search import WebSearchTool


def test_agent_reload_web_search_from_config_updates_registered_tools(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    agent = make_agent_loop(tmp_path / "workspace", tools=ToolRegistry(), config_path=config_path)

    config = Config.from_json(config_path)
    config.tools.web_search.provider = "searxng"
    config.tools.web_search.freshness = "week"
    config.tools.web_search.max_results = 7
    config.tools.web_search.searxng_max_pages = 4
    config.tools.web_search.searxng_engines = ["google", "bing"]
    config.tools.web_search.searxng_categories = ["general", "news"]
    config.tools.web_search.searxng_proxy = "http://proxy.local:8080"

    payload = agent.reload_web_search_from_config(config)

    web_search_tool = agent.tools.get("web_search")
    assert payload == {
        "provider": "searxng",
        "freshness": "week",
        "max_results": 7,
        "searxng_max_pages": 4,
        "searxng_engines": ["google", "bing"],
        "searxng_categories": ["general", "news"],
        "tool_updated": True,
    }
    assert agent.tools_config.web_search.provider == "searxng"
    assert isinstance(web_search_tool, WebSearchTool)
    assert web_search_tool.provider == "searxng"
    assert web_search_tool.max_results == 7
    assert web_search_tool.searxng_max_pages == 4
    assert web_search_tool.searxng_engines == ["google", "bing"]
    assert web_search_tool.searxng_categories == ["general", "news"]
    assert web_search_tool.searxng_proxy == "http://proxy.local:8080"


def test_agent_reload_media_from_config_updates_registered_media_router(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    agent = make_agent_loop(tmp_path / "workspace", tools=ToolRegistry(), config_path=config_path)

    transcribe_tool = agent.tools.get("transcribe_audio")
    assert isinstance(transcribe_tool, TranscribeAudioTool)
    assert transcribe_tool._media_router is agent.media_router
    assert transcribe_tool._media_router.speech_provider is None

    config = Config.from_json(config_path)
    config.speech.enabled = True
    config.speech.api_key = "speech-secret"
    config.speech.model = "whisper-1"

    payload = agent.reload_media_from_config(config)

    assert payload == {
        "vision_enabled": False,
        "ocr_enabled": False,
        "speech_enabled": True,
        "video_enabled": False,
    }
    assert transcribe_tool._media_router is agent.media_router
    assert transcribe_tool._media_router.speech_provider is agent.media_router.speech_provider
    assert transcribe_tool._media_router.speech_provider is not None


def test_agent_reload_browser_from_config_registers_and_removes_tools(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    agent = make_agent_loop(tmp_path / "workspace", tools=ToolRegistry(), config_path=config_path)

    config = Config.from_json(config_path)
    config.tools.browser.enabled = True
    config.tools.browser.backend = "agent-browser"
    config.tools.browser.command_timeout = 45
    config.tools.browser.session_timeout = 600
    config.tools.browser.cdp_url = "http://127.0.0.1:9222"
    config.tools.browser.launch_args = "--no-sandbox"
    config.tools.browser.allow_private_urls = True

    payload = agent.reload_browser_from_config(config)

    browser_tool = agent.tools.get("browser_navigate")
    assert payload == {
        "enabled": True,
        "backend": "agent-browser",
        "command_timeout": 45,
        "session_timeout": 600,
        "launch_args": "--no-sandbox",
        "tool_updated": True,
        "tool_removed": False,
    }
    assert agent.tools_config.browser.enabled is True
    assert isinstance(browser_tool, BrowserNavigateTool)
    assert browser_tool.runtime.command_timeout == 45
    assert browser_tool.runtime.session_timeout == 600
    assert browser_tool.runtime.cdp_url == "http://127.0.0.1:9222"
    assert browser_tool.runtime.launch_args == "--no-sandbox"
    assert browser_tool.browser_config.allow_private_urls is True

    config.tools.browser.enabled = False
    payload = agent.reload_browser_from_config(config)

    assert payload == {
        "enabled": False,
        "backend": "agent-browser",
        "command_timeout": 45,
        "session_timeout": 600,
        "launch_args": "--no-sandbox",
        "tool_updated": False,
        "tool_removed": True,
    }
    assert not any(name.startswith("browser_") for name in agent.tools.tool_names)
