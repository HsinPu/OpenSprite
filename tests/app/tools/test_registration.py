import asyncio
from pathlib import Path

from opensprite.app.tools.registration import (
    registered_browser_tool_names,
    register_browser_tools,
    register_config_tools,
    register_default_tools,
    register_web_tools,
    reload_browser_tools,
    reload_web_search_tools,
    unregister_browser_tools,
)
from opensprite.app.tools.media.audio import TranscribeAudioTool
from opensprite.config.schema import HistorySearchConfig, ToolsConfig, WebSearchToolConfig
from opensprite.modules.skills.loader import SkillsLoader
from opensprite.integrations.persistence.memory import MemoryStorage
from opensprite.app.tools.scheduling.cron import CronTool
from opensprite.modules.tools.batch import BatchTool
from opensprite.app.tools.web.browser import BrowserNavigateTool
from opensprite.integrations.browser.providers import FirecrawlCloudProvider
from opensprite.app.tools.mcp.configure import ConfigureMCPTool
from opensprite.app.tools.processes.management import ProcessTool
from opensprite.app.tools.skills.configure import ConfigureSkillTool
from opensprite.app.tools.subagents.configure import ConfigureSubagentTool
from opensprite.app.tools.processes.exec import ExecTool
from opensprite.app.tools.verification.verify import VerifyTool
from opensprite.app.tools.search.history import SearchHistoryTool
from opensprite.app.tools.web.fetch import WebFetchTool
from opensprite.app.tools.web.search import WebSearchTool
from opensprite.app.tools.media.outbound_media import SendMediaTool
from opensprite.modules.tools.registry import ToolRegistry
from opensprite.app.tools.runs.file_changes import (
    ListRunFileChangesTool,
    PreviewRunFileChangeRevertTool,
)


async def _fake_run_subagent(task: str, prompt_type: str | None, task_id: str | None) -> str:
    return f"{prompt_type or 'writer'}:{task_id or 'new'}:{task}"


async def _fake_run_subagents_many(tasks, max_parallel: int | None) -> str:
    return f"parallel:{len(tasks)}:{max_parallel}"


async def _fake_run_workflow(workflow: str, task: str, start_step: str | None = None) -> str:
    return f"workflow:{workflow}:{start_step or 'start'}:{task}"


async def _fake_reload_mcp() -> str:
    return "reloaded"


class FakeSearchStore:
    async def search_history(self, session_id: str, query: str, limit: int = 5):
        return []


def test_register_default_tools_includes_optional_skill_and_search_tools(tmp_path):
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
        skills_loader=SkillsLoader(skills_root=tmp_path / "skills"),
        history_search_store=FakeSearchStore(),
        history_search_config=HistorySearchConfig(history_top_k=7),
    )

    assert registry.tool_names == [
        "read_file",
        "glob_files",
        "grep_files",
        "code_navigation",
        "apply_patch",
        "write_file",
        "edit_file",
        "list_dir",
        "read_skill",
        "configure_skill",
        "configure_mcp",
        "configure_subagent",
        "credential_store",
        "exec",
        "process",
        "verify",
        "web_search",
        "web_fetch",
        "analyze_image",
        "ocr_image",
        "transcribe_audio",
        "analyze_video",
        "send_media",
        "delegate",
        "delegate_many",
        "run_workflow",
        "search_history",
        "cron",
        "batch",
    ]
    assert isinstance(registry.get("configure_skill"), ConfigureSkillTool)
    assert isinstance(registry.get("configure_subagent"), ConfigureSubagentTool)
    assert isinstance(registry.get("send_media"), SendMediaTool)
    assert isinstance(registry.get("transcribe_audio"), TranscribeAudioTool)
    assert isinstance(registry.get("batch"), BatchTool)
    assert isinstance(registry.get("search_history"), SearchHistoryTool)


def test_register_default_tools_skips_optional_skill_and_search_tools_when_dependencies_missing():
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
    )

    assert registry.tool_names == [
        "read_file",
        "glob_files",
        "grep_files",
        "code_navigation",
        "apply_patch",
        "write_file",
        "edit_file",
        "list_dir",
        "configure_mcp",
        "configure_subagent",
        "credential_store",
        "exec",
        "process",
        "verify",
        "web_search",
        "web_fetch",
        "analyze_image",
        "ocr_image",
        "transcribe_audio",
        "analyze_video",
        "send_media",
        "delegate",
        "delegate_many",
        "run_workflow",
        "cron",
        "batch",
    ]


def test_register_default_tools_applies_typed_tools_config_values():
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
        tools_config=ToolsConfig(
            **{
                "exec": {
                    "timeout": 12,
                    "notify_on_exit": False,
                    "notify_on_exit_empty_success": True,
                },
                "web_search": {"provider": "searxng", "max_results": 7},
                "web_fetch": {
                    "max_chars": 1234,
                    "max_response_size": 2048,
                    "timeout": 9,
                    "prefer_trafilatura": False,
                    "firecrawl_api_key": "firecrawl-key",
                },
            }
        ),
    )

    exec_tool = registry.get("exec")
    process_tool = registry.get("process")
    verify_tool = registry.get("verify")
    web_search_tool = registry.get("web_search")
    web_fetch_tool = registry.get("web_fetch")
    cron_tool = registry.get("cron")
    configure_mcp_tool = registry.get("configure_mcp")

    assert isinstance(exec_tool, ExecTool)
    assert isinstance(process_tool, ProcessTool)
    assert isinstance(verify_tool, VerifyTool)
    assert isinstance(cron_tool, CronTool)
    assert isinstance(configure_mcp_tool, ConfigureMCPTool)
    assert isinstance(web_search_tool, WebSearchTool)
    assert isinstance(web_fetch_tool, WebFetchTool)
    assert exec_tool.timeout == 12
    assert exec_tool.notify_on_exit is False
    assert exec_tool.notify_on_exit_empty_success is True
    assert "UTC" in cron_tool.description
    assert web_search_tool.provider == "searxng"
    assert web_search_tool.max_results == 7
    assert web_fetch_tool.fetcher.max_chars == 1234
    assert web_fetch_tool.fetcher.max_response_size == 2048
    assert web_fetch_tool.fetcher.timeout == 9
    assert web_fetch_tool.fetcher.prefer_trafilatura is False
    assert web_fetch_tool.fetcher.firecrawl_api_key == "firecrawl-key"


def test_reload_web_search_tools_updates_registered_tool():
    registry = ToolRegistry()
    register_web_tools(registry)

    result = reload_web_search_tools(
        registry,
        WebSearchToolConfig(provider="searxng", max_results=7),
    )

    web_search_tool = registry.get("web_search")
    assert result == {"tool_updated": True}
    assert isinstance(web_search_tool, WebSearchTool)
    assert web_search_tool.provider == "searxng"
    assert web_search_tool.max_results == 7


async def _fake_preview_run_file_change_revert(session_id: str, run_id: str, change_id: int):
    return {"session_id": session_id, "run_id": run_id, "change_id": change_id, "status": "ready"}


def test_register_default_tools_includes_run_trace_tools_when_storage_is_available():
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
        storage=MemoryStorage(),
        preview_run_file_change_revert=_fake_preview_run_file_change_revert,
    )

    assert isinstance(registry.get("list_run_file_changes"), ListRunFileChangesTool)
    assert isinstance(registry.get("preview_run_file_change_revert"), PreviewRunFileChangeRevertTool)


def test_search_and_web_tools_describe_current_behavior():
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
        history_search_store=FakeSearchStore(),
        history_search_config=HistorySearchConfig(history_top_k=7),
    )

    web_search_tool = registry.get("web_search")
    web_fetch_tool = registry.get("web_fetch")
    search_history_tool = registry.get("search_history")

    assert isinstance(web_search_tool, WebSearchTool)
    assert isinstance(web_fetch_tool, WebFetchTool)
    assert isinstance(search_history_tool, SearchHistoryTool)
    assert "conversation history" in search_history_tool.description.lower()


def test_register_default_tools_applies_cron_default_timezone_from_tools_config():
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
        tools_config=ToolsConfig(**{"cron": {"default_timezone": "Asia/Taipei"}}),
    )

    cron_tool = registry.get("cron")

    assert isinstance(cron_tool, CronTool)
    assert "Asia/Taipei" in cron_tool.description


def test_workflow_tool_accepts_optional_start_step():
    registry = ToolRegistry()

    register_default_tools(
        registry,
        workspace_resolver=lambda: Path.cwd(),
        get_session_id=lambda: "chat-1",
        run_subagent=_fake_run_subagent,
        run_subagents_many=_fake_run_subagents_many,
        run_workflow=_fake_run_workflow,
        workflow_catalog_getter=lambda: {"implement_then_review": "Run implementer then reviewer."},
        config_path_resolver=lambda: Path.cwd() / "opensprite.json",
        reload_mcp=_fake_reload_mcp,
    )

    tool = registry.get("run_workflow")

    result = asyncio.run(
        tool.execute(workflow="implement_then_review", task="Ship it", start_step="review")
    )

    assert result == "workflow:implement_then_review:review:Ship it"


def test_register_browser_tools_adds_mvp_tools():
    registry = ToolRegistry()

    register_browser_tools(registry, get_session_id=lambda: "session")

    assert {
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_press",
        "browser_scroll",
        "browser_back",
        "browser_console",
    }.issubset(set(registry.tool_names))


def test_browser_tool_lifecycle_helpers_report_and_remove_tools():
    registry = ToolRegistry()
    register_browser_tools(registry, get_session_id=lambda: "session")

    registered = registered_browser_tool_names(registry)
    removed = unregister_browser_tools(registry)

    assert set(registered) == set(removed)
    assert registered_browser_tool_names(registry) == []


def test_reload_browser_tools_applies_enabled_and_disabled_config():
    registry = ToolRegistry()

    result = reload_browser_tools(
        registry,
        get_session_id=lambda: "session",
        tools_config=ToolsConfig(browser={"enabled": True, "command_timeout": 45}),
    )

    browser_tool = registry.get("browser_navigate")
    assert result == {"tool_updated": True, "tool_removed": False}
    assert isinstance(browser_tool, BrowserNavigateTool)
    assert browser_tool.runtime.command_timeout == 45

    result = reload_browser_tools(
        registry,
        get_session_id=lambda: "session",
        tools_config=ToolsConfig(browser={"enabled": False}),
    )

    assert result == {"tool_updated": False, "tool_removed": True}
    assert registered_browser_tool_names(registry) == []


def test_register_browser_tools_skips_when_disabled():
    registry = ToolRegistry()

    register_browser_tools(registry, get_session_id=lambda: "session", tools_config=ToolsConfig())

    assert not any(name.startswith("browser_") for name in registry.tool_names)


def test_register_browser_tools_configures_cloud_provider_runtime():
    registry = ToolRegistry()

    register_browser_tools(
        registry,
        get_session_id=lambda: "session",
        tools_config=ToolsConfig(
            browser={
                "enabled": True,
                "backend": "firecrawl",
                "firecrawl_api_key": "fc-key",
            }
        ),
    )

    tool = registry.get("browser_navigate")
    assert isinstance(tool.runtime.cloud_provider, FirecrawlCloudProvider)


def test_register_config_tools_includes_credential_store(tmp_path):
    registry = ToolRegistry()

    async def reload_mcp():
        return "reloaded"

    register_config_tools(
        registry,
        config_path_resolver=lambda: tmp_path / "opensprite.json",
        reload_mcp=reload_mcp,
        app_home=tmp_path,
        workspace_resolver=lambda: tmp_path,
    )

    assert "credential_store" in registry.tool_names
