"""Persistence helpers for provider/model settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .defaults import DEFAULT_LLM_PROVIDERS_FILE
from .json_files import write_json_dict
from .provider_errors import ProviderSettingsValidationError
from .schema import Config


def persist_llm_provider_state(
    config_path: str | Path,
    main_data: dict[str, Any],
    providers: dict[str, Any],
) -> None:
    """Persist main LLM settings and the split provider config file."""
    llm_data = main_data.setdefault("llm", {})
    if not isinstance(llm_data, dict):
        raise ProviderSettingsValidationError("llm config must be an object")
    llm_data.pop("providers", None)
    llm_data.setdefault("providers_file", DEFAULT_LLM_PROVIDERS_FILE)
    write_json_dict(Path(config_path), main_data)
    Config.ensure_llm_providers_file(config_path, main_data)
    Config.write_llm_providers_file(config_path, providers, llm_data)
