"""Tool for explicit credential-vault operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..auth.credentials import (
    CredentialStoreError,
    add_credential,
    list_credentials,
    remove_credential,
    set_capability_default,
    set_provider_default,
)
from .base import Tool
from .result_status import tool_error_result


_TOOL_NAME = "credential_store"


def _credential_store_error_result(
    error: str,
    *,
    category: str,
    error_type: str = "CredentialStoreToolError",
    invalid_arguments: bool = False,
) -> str:
    return tool_error_result(
        error,
        error_type=error_type,
        category=category,
        repeated_error_key=error if invalid_arguments else None,
        invalid_arguments=invalid_arguments,
        metadata={"tool_name": _TOOL_NAME},
    )


class CredentialStoreTool(Tool):
    """Manage credentials only when the user explicitly asks to save them."""

    name = _TOOL_NAME
    description = (
        "Store, list, remove, or set defaults for local API-key credentials in the OpenSprite credential vault. "
        "Use action='add' only after the user explicitly asks to save/store a key, or after they clearly confirm "
        "a previous save prompt. Never call this tool just because a key appears in chat. Results are redacted."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "remove", "set_default"],
                "description": "Credential operation to perform.",
            },
            "provider": {
                "type": "string",
                "description": "Provider id, for example openrouter, openai, minimax, or anthropic.",
            },
            "secret": {
                "type": "string",
                "description": "API key or token. Required for action='add'. Do not echo it back to the user.",
            },
            "credential_id": {
                "type": "string",
                "description": "Credential id. Required for remove and set_default.",
            },
            "label": {
                "type": "string",
                "description": "Optional human-readable label for action='add'.",
            },
            "base_url": {
                "type": "string",
                "description": "Optional runtime base URL for action='add'.",
            },
            "capability": {
                "type": "string",
                "description": "Capability default to set, for example llm.chat. Used by set_default.",
            },
            "scopes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional capabilities/scopes this credential can satisfy. Defaults to llm.chat.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, app_home: str | Path | None = None):
        self.app_home = Path(app_home).expanduser() if app_home is not None else None

    def sanitize_params_for_display(self, params: Any) -> Any:
        if not isinstance(params, dict):
            return params
        safe = dict(params)
        for key in ("secret", "api_key", "access_token", "refresh_token", "token"):
            if key in safe and safe[key]:
                safe[key] = "***redacted***"
        return safe

    def sanitize_input_delta_for_display(self, delta: str) -> str:
        return "***redacted***" if delta else delta

    async def _execute(self, **kwargs: Any) -> str:
        action = str(kwargs.get("action") or "").strip()
        provider = str(kwargs.get("provider") or "").strip()
        credential_id = str(kwargs.get("credential_id") or "").strip()
        try:
            if action == "add":
                secret = str(kwargs.get("secret") or kwargs.get("api_key") or "").strip()
                if not provider or not secret:
                    return _credential_store_error_result(
                        "provider and secret are required for credential_store add.",
                        category="invalid_arguments",
                        error_type="ToolValidationError",
                        invalid_arguments=True,
                    )
                scopes = kwargs.get("scopes")
                if not isinstance(scopes, list):
                    scopes = None
                credential = add_credential(
                    provider,
                    secret,
                    label=str(kwargs.get("label") or "").strip() or None,
                    base_url=str(kwargs.get("base_url") or "").strip() or None,
                    scopes=scopes,
                    app_home=self.app_home,
                )
                return json.dumps({"ok": True, "credential": credential}, ensure_ascii=False)
            if action == "list":
                return json.dumps({"credentials": list_credentials(provider or None, app_home=self.app_home)}, ensure_ascii=False)
            if action == "remove":
                if not provider or not credential_id:
                    return _credential_store_error_result(
                        "provider and credential_id are required for credential_store remove.",
                        category="invalid_arguments",
                        error_type="ToolValidationError",
                        invalid_arguments=True,
                    )
                return json.dumps(remove_credential(provider, credential_id, app_home=self.app_home), ensure_ascii=False)
            if action == "set_default":
                if not credential_id:
                    return _credential_store_error_result(
                        "credential_id is required for credential_store set_default.",
                        category="invalid_arguments",
                        error_type="ToolValidationError",
                        invalid_arguments=True,
                    )
                capability = str(kwargs.get("capability") or "").strip()
                if provider:
                    credential = set_provider_default(provider, credential_id, app_home=self.app_home)
                elif capability:
                    credential = set_capability_default(capability, credential_id, app_home=self.app_home)
                else:
                    return _credential_store_error_result(
                        "provider or capability is required for credential_store set_default.",
                        category="invalid_arguments",
                        error_type="ToolValidationError",
                        invalid_arguments=True,
                    )
                return json.dumps({"ok": True, "credential": credential}, ensure_ascii=False)
        except CredentialStoreError as exc:
            return _credential_store_error_result(str(exc), category="credential_store_error")
        return _credential_store_error_result(
            "action must be one of add, list, remove, or set_default.",
            category="invalid_arguments",
            error_type="ToolValidationError",
            invalid_arguments=True,
        )
