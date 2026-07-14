"""Integration coverage for the system prompt passed to the main LLM call."""

from __future__ import annotations

import asyncio
from pathlib import Path

from opensprite.agent.agent import AgentLoop
from opensprite.config.schema import Config, LogConfig, MemoryConfig, SearchConfig, ToolsConfig, UserProfileConfig
from opensprite.context.file_builder import FileContextBuilder
from opensprite.context.paths import sync_templates
from opensprite.llms.base import LLMResponse
from opensprite.storage.base import StoredMessage
from opensprite.tools.base import Tool
from opensprite.tools.registry import ToolRegistry


class CapturingProvider:
    """Record each provider call so tests can inspect the complete prompt."""

    def __init__(self) -> None:
        self.calls: list[list] = []

    async def chat(self, messages, tools=None, model=None, temperature=0.7, max_tokens=2048, **kwargs):
        self.calls.append(list(messages))
        return LLMResponse(content="done", model="fake-model")

    def get_default_model(self) -> str:
        return "fake-model"


class _MinimalTool(Tool):
    def __init__(self, name: str = "noop") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs):
        return "ok"


class _MinimalMCPTool(Tool):
    @property
    def name(self) -> str:
        return "mcp_demo_echo"

    @property
    def description(self) -> str:
        return "Echo text through demo MCP"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs):
        return "ok"


class _EmptyStorage:
    async def get_messages(self, session_id, limit=None):
        return []

    async def add_message(self, session_id, message: StoredMessage):
        return None

    async def clear_messages(self, session_id):
        return None

    async def get_consolidated_index(self, session_id):
        return 0

    async def set_consolidated_index(self, session_id, index):
        return None

    async def get_all_sessions(self):
        return []


def _minimal_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_MinimalTool())
    return registry


def _context_builder(app_home: Path) -> FileContextBuilder:
    sync_templates(app_home, silent=True)
    return FileContextBuilder(
        app_home=app_home,
        bootstrap_dir=app_home / "bootstrap",
        memory_dir=app_home / "memory",
        tool_workspace=app_home / "workspace",
    )


def _agent(provider: CapturingProvider, context_builder: FileContextBuilder, registry: ToolRegistry) -> AgentLoop:
    return AgentLoop(
        config=Config.load_agent_template_config(),
        provider=provider,
        storage=_EmptyStorage(),
        context_builder=context_builder,
        tools=registry,
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(log_system_prompt=False),
        search_config=SearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )


def test_main_agent_call_llm_passes_full_file_builder_system_prompt_to_provider(tmp_path: Path) -> None:
    context_builder = _context_builder(tmp_path / "home")
    provider = CapturingProvider()
    agent = _agent(provider, context_builder, _minimal_registry())
    session_id = "telegram:room-1"

    result = asyncio.run(
        agent.call_llm(
            session_id,
            "hello from integration test",
            channel="telegram",
            allow_tools=False,
        )
    )

    assert result.content == "done"
    assert len(provider.calls) == 1
    llm_messages = provider.calls[0]
    assert llm_messages[0].role == "system"
    system_text = llm_messages[0].content
    assert isinstance(system_text, str)
    assert system_text == context_builder.build_system_prompt(session_id)
    assert "You are OpenSprite" in system_text
    assert "# Session Context" in system_text
    assert "# Retrieval Strategy" in system_text
    assert "Do not end a turn with a promise of future action" in system_text
    assert 'When the user says things like "earlier", "before", "again"' in system_text
    assert "When the conversation has been compacted, treat the compacted state as a handoff" in system_text
    assert "For command or program version questions, run the direct version command" in system_text
    assert "# MCP Configuration" in system_text
    assert "prefer using `configure_mcp` instead of telling the user to edit config files manually" in system_text
    assert "# Available Subagents" in system_text
    assert "Use `delegate` when a focused subproblem would benefit from a dedicated prompt." in system_text
    assert "\n\n---\n\n" in system_text


def test_main_agent_system_prompt_lists_connected_mcp_tools(tmp_path: Path) -> None:
    context_builder = _context_builder(tmp_path / "home")
    registry = _minimal_registry()
    registry.register(_MinimalMCPTool())
    provider = CapturingProvider()
    agent = _agent(provider, context_builder, registry)

    result = asyncio.run(
        agent.call_llm(
            "telegram:room-1",
            "show me available mcp tools",
            channel="telegram",
            allow_tools=False,
        )
    )

    assert result.content == "done"
    system_text = provider.calls[0][0].content
    assert "# MCP Configuration" in system_text
    assert "Use `configure_mcp` first for MCP setup or changes." in system_text
    assert "# Available MCP Tools" in system_text
    assert "These MCP tools are already connected and available through normal tool calling." in system_text
    assert "`mcp_demo_echo`: Echo text through demo MCP" in system_text
