"""Pure local-data path contract for the OpenSprite desktop application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved paths below one user-owned OpenSprite data root."""

    home: Path

    @property
    def user_home(self) -> Path:
        return Path.home().resolve(strict=False)

    @property
    def credential_file(self) -> Path:
        return self.home / "auth.json"

    @property
    def credential_key_file(self) -> Path:
        return self.config_dir / "credential.key"

    @property
    def access_file(self) -> Path:
        return self.config_dir / "access.json"

    @property
    def access_policy_file(self) -> Path:
        return self.config_dir / "access-policy.json"

    @property
    def access_bootstrap_file(self) -> Path:
        return self.state_dir / "access-bootstrap.json"

    @property
    def config_dir(self) -> Path:
        return self.home / "config"

    @property
    def settings_file(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def general_settings_file(self) -> Path:
        return self.config_dir / "general.json"

    @property
    def conversation_settings_file(self) -> Path:
        return self.config_dir / "conversation.json"

    @property
    def tool_settings_file(self) -> Path:
        return self.config_dir / "tools.json"

    @property
    def mcp_settings_file(self) -> Path:
        return self.config_dir / "mcp.json"

    @property
    def workspace_settings_file(self) -> Path:
        return self.config_dir / "workspaces.json"

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def database_file(self) -> Path:
        return self.data_dir / "opensprite.db"

    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    @property
    def provider_state_file(self) -> Path:
        return self.state_dir / "providers.json"

    @property
    def provider_transaction_file(self) -> Path:
        return self.state_dir / "provider-transaction.json"

    @property
    def conversations_dir(self) -> Path:
        return self.home / "conversations"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def system_prompt_logs_dir(self) -> Path:
        return self.logs_dir / "system-prompts"

    @property
    def backend_logs_dir(self) -> Path:
        return self.logs_dir / "backend"

    @property
    def prompt_logs_dir(self) -> Path:
        return self.logs_dir / "prompts"

    @property
    def tool_receipts_dir(self) -> Path:
        return self.logs_dir / "tool-receipts"

    @property
    def tool_receipt_key_file(self) -> Path:
        return self.config_dir / "tool-receipt.key"

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"


def build_app_paths(home: str | Path | None = None) -> AppPaths:
    """Build normalized paths without creating files or directories."""

    root = (
        Path(home).expanduser()
        if home is not None
        else Path.home() / ".opensprite"
    )
    return AppPaths(home=root.resolve(strict=False))
