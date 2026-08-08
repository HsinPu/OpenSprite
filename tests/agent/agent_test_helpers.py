from __future__ import annotations

from pathlib import Path
from typing import Any

from opensprite.app.agent.agent import AgentLoop
from opensprite.app.tools.registration import (
    register_memory_tool,
    reload_browser_tools,
    reload_web_search_tools,
)
from opensprite.app.tools.setup import register_default_agent_tools
from opensprite.app.media import reload_media_router
from opensprite.config.schema import Config, HistorySearchConfig, LogConfig, MemoryConfig, ToolsConfig, UserProfileConfig
from opensprite.core.contracts.persistence import StoredMessage
from opensprite.integrations.persistence.memory import MemoryStorage
from opensprite.modules.tools.base import Tool
from opensprite.modules.tools.registry import ToolRegistry


class FakeContextBuilder:
    def __init__(
        self,
        workspace: Path,
        *,
        include_images: bool = False,
        app_home: Path | None = None,
        tool_workspace: Path | None = None,
    ):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.include_images = include_images
        self.last_history = None
        if app_home is not None:
            self.app_home = app_home
        if tool_workspace is not None:
            self.tool_workspace = tool_workspace

    def build_system_prompt(self, session_id: str = "default") -> str:
        return "system"

    def build_messages(self, history, current_message, current_images=None, channel=None, session_id=None):
        self.last_history = list(history)
        message = {"role": "user", "content": current_message}
        if self.include_images:
            message["images"] = current_images
        return [message]

    def add_tool_result(self, messages, tool_call_id, tool_name, result):
        return messages

    def add_assistant_message(self, messages, content, tool_calls=None):
        return messages


class NoCallProvider:
    async def chat(self, messages, tools=None, model=None, temperature=0.7, max_tokens=2048, **kwargs):
        raise AssertionError("provider.chat should not be called in this test")

    def get_default_model(self) -> str:
        return "fake-model"

class SavedMessageStorage(MemoryStorage):
    def __init__(self, messages: dict[str, list[StoredMessage]] | None = None):
        super().__init__()
        self.saved = []
        self.messages = self._messages
        for session_id, rows in (messages or {}).items():
            self.messages[session_id].extend(rows)

    async def add_message(self, session_id, message: StoredMessage):
        await super().add_message(session_id, message)
        self.saved.append((session_id, message.role, message.content, message.tool_name, dict(message.metadata)))


class DummyTool(Tool):
    def __init__(self, name: str = "dummy", *, result: str = "ok", echo_value: bool = False):
        self._name = name
        self._result = result
        self._echo_value = echo_value

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"value": {"type": "string"}}}

    async def _execute(self, value: str = "", **kwargs):
        if self._echo_value:
            return f"tool:{value}"
        return self._result


def make_tool_registry(*tools: Tool | str) -> ToolRegistry:
    registry = ToolRegistry()
    selected_tools = tools or (DummyTool(),)
    for tool in selected_tools:
        registry.register(DummyTool(tool) if isinstance(tool, str) else tool)
    return registry


def disabled_user_profile_config() -> UserProfileConfig:
    return UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False})


def make_agent_loop(
    workspace: Path,
    *,
    provider: Any | None = None,
    storage: Any | None = None,
    context_builder: Any | None = None,
    tools: ToolRegistry | None = None,
    tools_config: ToolsConfig | None = None,
    history_search_store: Any | None = None,
    config_path: str | Path | None = None,
    include_images: bool = False,
    app_home: Path | None = None,
    tool_workspace: Path | None = None,
    **agent_kwargs: Any,
) -> AgentLoop:
    return AgentLoop(
        config=agent_kwargs.pop("config", Config.load_agent_template_config()),
        provider=provider or NoCallProvider(),
        storage=storage if storage is not None else SavedMessageStorage(),
        context_builder=context_builder
        or FakeContextBuilder(
            workspace,
            include_images=include_images,
            app_home=app_home,
            tool_workspace=tool_workspace,
        ),
        tools=tools or make_tool_registry(),
        memory_config=agent_kwargs.pop("memory_config", MemoryConfig(**Config.load_template_data()["memory"])),
        tools_config=tools_config or ToolsConfig(),
        log_config=agent_kwargs.pop("log_config", LogConfig()),
        history_search_config=agent_kwargs.pop("history_search_config", HistorySearchConfig()),
        user_profile_config=agent_kwargs.pop("user_profile_config", disabled_user_profile_config()),
        history_search_store=history_search_store,
        config_path=config_path,
        media_router_reloader=agent_kwargs.pop("media_router_reloader", reload_media_router),
        default_tool_registrar=agent_kwargs.pop(
            "default_tool_registrar",
            register_default_agent_tools,
        ),
        memory_tool_registrar=agent_kwargs.pop(
            "memory_tool_registrar",
            register_memory_tool,
        ),
        web_search_tool_reloader=agent_kwargs.pop(
            "web_search_tool_reloader",
            reload_web_search_tools,
        ),
        browser_tool_reloader=agent_kwargs.pop(
            "browser_tool_reloader",
            reload_browser_tools,
        ),
        **Config.packaged_agent_llm_chat_kwargs(),
        **agent_kwargs,
    )
