"""
opensprite/context/file_builder.py - File-based ContextBuilder.

Assembles the system prompt from:
- bootstrap/*.md startup files
- workspace/sessions/{session}/USER.md durable per-session profile (beside skills/ and subagent_prompts/)
- global + per-session skill metadata summaries (full skill content loads on demand)
- memory/<session>/MEMORY.md long-term memory
"""

import platform
import re
from pathlib import Path
from typing import Any

from .paths import (
    get_app_home,
    get_bootstrap_dir,
    get_memory_dir,
    get_session_workspace,
    get_session_skills_dir,
    get_skills_dir,
    get_tool_workspace,
    get_user_overlay_file,
    get_user_profile_file,
    load_bootstrap_files,
    resolve_session_memory_file,
)
from .runtime import RUNTIME_CONTEXT_TAG, build_runtime_context
from ..documents.memory import MemoryStore
from ..documents.recent_summary import RecentSummaryStore
from ..documents.user_profile import create_user_profile_store
from ..documents.user_overlay import UserOverlayIndexStore, UserOverlayStore
from ..skills import SkillsLoader
from ..subagent_prompts import get_all_subagents
from .message_history import (
    LearningLedger,
    PromptMemoryDocumentService,
    RelevantLearningContextService,
    RelevantUserOverlayContextService,
)


class FileContextBuilder:
    """Context builder backed by bootstrap files, skills, and memory."""

    BOOTSTRAP_FILES = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "TOOLS.md", "USER.md"]
    CONTEXT_FILE_MAX_CHARS = 20_000
    CONTEXT_TRUNCATE_HEAD_RATIO = 0.7
    CONTEXT_TRUNCATE_TAIL_RATIO = 0.2
    _CONTEXT_INVISIBLE_CHARS = frozenset(
        {
            "\u200b",
            "\u200c",
            "\u200d",
            "\u2060",
            "\ufeff",
            "\u202a",
            "\u202b",
            "\u202c",
            "\u202d",
            "\u202e",
        }
    )
    _CONTEXT_THREAT_PATTERNS = (
        (re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.IGNORECASE), "prompt_injection"),
        (re.compile(r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", re.IGNORECASE), "disregard_rules"),
        (re.compile(r"do\s+not\s+tell\s+the\s+user", re.IGNORECASE), "deception_hide"),
        (re.compile(r"system\s+prompt\s+override", re.IGNORECASE), "system_prompt_override"),
        (re.compile(r"<!--[^>]*(ignore|override|system|secret|hidden)[^>]*-->", re.IGNORECASE), "html_comment_injection"),
        (re.compile(r"<\s*div\s+style\s*=\s*[\"'][\s\S]*?display\s*:\s*none", re.IGNORECASE), "hidden_div"),
        (re.compile(r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)", re.IGNORECASE), "secret_exfiltration"),
        (re.compile(r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)", re.IGNORECASE), "secret_file_access"),
    )
    _RUNTIME_CONTEXT_TAG = RUNTIME_CONTEXT_TAG
    def _build_mcp_tools_summary(self) -> str:
        """Describe currently connected MCP tools for the main agent."""
        if not self._runtime_mcp_tools:
            return ""

        tool_lines = "\n".join(
            f"- `{name}`: {description}" for name, description in self._runtime_mcp_tools
        )
        return f"""# Available MCP Tools

These MCP tools are already connected and available through normal tool calling.

{tool_lines}
"""

    def _build_subagent_summary(self, session_id: str) -> str:
        """Describe the available delegate prompt types for the main agent."""
        session_ws = self.get_session_workspace(session_id)
        subagents = get_all_subagents(self.app_home, session_workspace=session_ws)
        if not subagents:
            return ""

        subagent_lines = "\n".join(
            f"- `{name}`: {description}" for name, description in subagents.items()
        )
        return f"""# Available Subagents

Use `delegate` when a focused subproblem would benefit from a dedicated prompt.
Ids and descriptions below are **merged**: this session's `subagent_prompts/<id>.md` overrides `~/.opensprite/subagent_prompts/<id>.md` when both exist. Use `configure_subagent` for adds and edits under this session's `subagent_prompts/`.

{subagent_lines}
"""

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        app_home: Path | None = None,
        bootstrap_dir: Path | None = None,
        memory_dir: Path | None = None,
        tool_workspace: Path | None = None,
        skills_loader: SkillsLoader | None = None,
        skills_root: Path | None = None,
        personal_skills_dir: Path | None = None,
        learning_ledger: LearningLedger | None = None,
    ):
        self.app_home = get_app_home(app_home)
        self.bootstrap_dir = Path(bootstrap_dir).expanduser() if bootstrap_dir else get_bootstrap_dir(self.app_home)
        self.memory_dir = Path(memory_dir).expanduser() if memory_dir else get_memory_dir(self.app_home)
        self.tool_workspace = (
            Path(tool_workspace).expanduser()
            if tool_workspace is not None
            else Path(workspace).expanduser() if workspace is not None else get_tool_workspace(self.app_home)
        )
        self.workspace = self.tool_workspace
        self.memory_store = MemoryStore(self.memory_dir, app_home=self.app_home, workspace_root=self.tool_workspace)
        self.recent_summary_store = RecentSummaryStore(self.memory_dir, app_home=self.app_home, workspace_root=self.tool_workspace)
        self.prompt_memory_documents = PromptMemoryDocumentService(
            memory_store=self.memory_store,
            recent_summary_store=self.recent_summary_store,
        )
        self.user_overlay_store = UserOverlayStore(app_home=self.app_home)
        self.user_overlay_index = UserOverlayIndexStore(app_home=self.app_home)
        self.relevant_user_overlay = RelevantUserOverlayContextService(index_store=self.user_overlay_index)
        self._runtime_mcp_tools: list[tuple[str, str]] = []
        self.learning_ledger = learning_ledger
        self.relevant_learning = RelevantLearningContextService(learning_ledger=learning_ledger)
        self.skills_loader = skills_loader or SkillsLoader(
            skills_root=skills_root or get_skills_dir(self.app_home),
            personal_skills_dir=personal_skills_dir,
        )

    def set_learning_ledger(self, ledger: LearningLedger | None) -> None:
        """Attach the session learning ledger used for relevant prompt hints."""
        self.learning_ledger = ledger
        self.relevant_learning.set_learning_ledger(ledger)

    def set_runtime_mcp_tools(self, tools: list[tuple[str, str]]) -> None:
        """Store the connected MCP tool summary for prompt generation."""
        self._runtime_mcp_tools = list(tools)

    def set_session_overlay_id(self, session_id: str, overlay_id: str | None) -> None:
        """Record the stable overlay identity to use for one session's prompt build."""
        self.relevant_user_overlay.set_session_overlay_id(session_id, overlay_id)

    def get_session_overlay_id(self, session_id: str) -> str | None:
        """Return the currently resolved overlay identity for one session, if any."""
        return self.relevant_user_overlay.get_session_overlay_id(session_id)

    def get_session_workspace(self, session_id: str = "default") -> Path:
        """Resolve the current session's isolated workspace."""
        return get_session_workspace(session_id, workspace_root=self.tool_workspace)

    def get_session_skills_dir(self, session_id: str = "default") -> Path:
        """Resolve the personal skills directory for the current session."""
        return get_session_skills_dir(session_id, workspace_root=self.tool_workspace)

    def get_user_profile_path(self, session_id: str = "default") -> Path:
        """Resolve the USER.md path for the current user/session scope."""
        return get_user_profile_file(self.app_home, session_id=session_id, workspace_root=self.tool_workspace)

    def get_workspace_agents_path(self, session_id: str = "default") -> Path:
        """Resolve the current workspace's AGENTS.md instructions path."""
        return self.get_session_workspace(session_id) / "AGENTS.md"

    def _read_user_profile(self, session_id: str) -> str:
        """Load the current user/session profile text, creating it from the template when needed."""
        return create_user_profile_store(
            self.app_home,
            session_id,
            bootstrap_dir=self.bootstrap_dir,
            workspace_root=self.tool_workspace,
        ).read_text()

    def _read_user_overlay(self, session_id: str) -> str:
        """Load the stable cross-session overlay for this session when one is resolved."""
        overlay_id = self.get_session_overlay_id(session_id)
        if not overlay_id:
            return ""
        content = self.user_overlay_store.read(overlay_id)
        if not content:
            return ""
        overlay_path = get_user_overlay_file(overlay_id, app_home=self.app_home).expanduser().resolve()
        return f"# Stable User Overlay\n\nLoaded from: `{overlay_path}`\n\n{content.strip()}"

    @staticmethod
    def _size_hint(content: str) -> str:
        """Return a compact size hint for durable prompt documents."""
        return f"Approx size: {len(str(content or '')):,} chars. Keep this document concise; use search tools for detailed past transcripts."

    def _build_relevant_user_overlay_context(self, session_id: str, current_message: str) -> str:
        return self.relevant_user_overlay.build_context(session_id, current_message)

    def _read_workspace_agents(self, session_id: str) -> str:
        """Load AGENTS.md from the active workspace when present."""
        agents_path = self.get_workspace_agents_path(session_id)
        if not agents_path.is_file():
            return ""
        content = agents_path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        content = self._sanitize_context_file_content(content, "AGENTS.md")
        return f"# Workspace AGENTS.md\n\nLoaded from: `{agents_path.expanduser().resolve()}`\n\n{content}"

    @classmethod
    def _sanitize_context_file_content(cls, content: str, filename: str) -> str:
        """Block suspicious context files and truncate large trusted ones."""
        findings = cls._context_file_findings(content)
        if findings:
            return f"[BLOCKED: {filename} contained potential prompt injection ({', '.join(findings)}). Content not loaded.]"
        return cls._truncate_context_file_content(content, filename)

    @classmethod
    def _context_file_findings(cls, content: str) -> list[str]:
        findings: list[str] = []
        for char in cls._CONTEXT_INVISIBLE_CHARS:
            if char in content:
                findings.append(f"invisible unicode U+{ord(char):04X}")
        for pattern, finding in cls._CONTEXT_THREAT_PATTERNS:
            if pattern.search(content):
                findings.append(finding)
        return findings

    @classmethod
    def _truncate_context_file_content(cls, content: str, filename: str) -> str:
        if len(content) <= cls.CONTEXT_FILE_MAX_CHARS:
            return content
        head_chars = int(cls.CONTEXT_FILE_MAX_CHARS * cls.CONTEXT_TRUNCATE_HEAD_RATIO)
        tail_chars = int(cls.CONTEXT_FILE_MAX_CHARS * cls.CONTEXT_TRUNCATE_TAIL_RATIO)
        head = content[:head_chars].rstrip()
        tail = content[-tail_chars:].lstrip()
        marker = (
            f"\n\n[...truncated {filename}: kept {head_chars}+{tail_chars} of "
            f"{len(content)} chars. Use file tools to read the full file.]\n\n"
        )
        return f"{head}{marker}{tail}"

    def build_system_prompt(self, session_id: str = "default") -> str:
        """Build the system prompt from bootstrap files, skills, and memory."""
        parts = [self._build_session_context(session_id)]

        user_overlay = self._read_user_overlay(session_id)
        if user_overlay:
            parts.append(user_overlay)

        bootstrap = load_bootstrap_files(self.bootstrap_dir)
        bootstrap["USER"] = self._read_user_profile(session_id)
        for key, content in bootstrap.items():
            if content:
                section = content.strip()
                if key == "USER":
                    section = f"{section}\n\n{self._size_hint(section)}"
                if section.startswith("#"):
                    parts.append(section)
                else:
                    parts.append(f"## {key}\n\n{section}")

        workspace_agents = self._read_workspace_agents(session_id)
        if workspace_agents:
            parts.append(workspace_agents)

        # Skills follow the on-demand model from OpenCode docs: list available
        # skill metadata in the main prompt, then load a full SKILL.md only when
        # the model decides a skill is relevant via read_skill.
        skills_summary = self.skills_loader.build_skills_summary(
            personal_skills_dir=self.get_session_skills_dir(session_id)
        )
        if skills_summary:
            parts.append(f"""# Available Skills

To use a skill, read its SKILL.md file using the read_skill tool.

{skills_summary}
""")

        subagent_summary = self._build_subagent_summary(session_id)
        if subagent_summary:
            parts.append(subagent_summary)

        mcp_tools_summary = self._build_mcp_tools_summary()
        if mcp_tools_summary:
            parts.append(mcp_tools_summary)

        parts.extend(self.prompt_memory_documents.build_prompt_sections(session_id))

        return "\n\n---\n\n".join(parts)

    def _build_session_context(self, session_id: str) -> str:
        """Build the runtime session context block."""
        app_home_path = str(self.app_home.expanduser().resolve())
        bootstrap_path = str(self.bootstrap_dir.expanduser().resolve())
        workspace_path = str(self.get_session_workspace(session_id).expanduser().resolve())
        user_profile_path = str(self.get_user_profile_path(session_id).expanduser().resolve())
        memory_path = str(
            resolve_session_memory_file(
                session_id,
                workspace_root=self.tool_workspace,
                app_home=self.app_home,
            ).expanduser().resolve()
        )
        system = platform.system()
        runtime = f"{system} {platform.machine()}, Python {platform.python_version()}"

        return f"""# Session Context

You are OpenSprite — operate as a **chief-of-staff / Jarvis-class** partner: omnicompetent within this workspace, proactive, economical with words, ruthless about correctness.

## Runtime
{runtime}

        ## App Paths
        - App home: {app_home_path}
        - Bootstrap files: {bootstrap_path}
        - User profile: {user_profile_path}
        - Long-term memory: {memory_path}

## Active Workspace
{workspace_path}

## Workspace Operating Policy
Treat the active workspace as trusted working context. For workspace-local tasks, proceed without asking first when you need to read files, search files, edit files, apply patches, run focused tests, build, or verify results. Use the normal inspect -> edit -> verify -> summarize loop for code and project work.

Be conservative only for actions with external side effects or boundaries outside the active workspace, such as sending messages, scheduling jobs, using external MCP services, network operations, credential handling, or modifying OpenSprite runtime configuration.
"""

    @staticmethod
    def _build_runtime_context(channel: str | None, session_id: str | None) -> str:
        """Build an untrusted runtime metadata block."""
        return build_runtime_context(channel=channel, session_id=session_id)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        current_images: list[str] | None = None,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        session_id = session_id or "default"

        if current_images:
            content: list[Any] = [{"type": "text", "text": current_message}]
            for image in current_images:
                content.append({"type": "image_url", "image_url": {"url": image}})
            user_message = {"role": "user", "content": content}
        else:
            user_message = {"role": "user", "content": current_message}

        messages = [{"role": "system", "content": self.build_system_prompt(session_id)}]
        relevant_user_overlay = self._build_relevant_user_overlay_context(session_id, current_message)
        if relevant_user_overlay:
            messages.append({"role": "system", "content": relevant_user_overlay})
        relevant_learning = self._build_relevant_learning_context(session_id, current_message)
        if relevant_learning:
            messages.append({"role": "system", "content": relevant_learning})
        messages.extend(history)
        messages.extend([
            {"role": "user", "content": self._build_runtime_context(channel, session_id)},
            user_message,
        ])
        return messages

    def _build_relevant_learning_context(self, session_id: str, current_message: str) -> str:
        """Return concise learned-context hints for the current message when available."""
        return self.relevant_learning.build_context(session_id, current_message)

    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": result,
            }
        )
        return messages

    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        messages.append(message)
        return messages
