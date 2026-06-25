"""Shared JSON file helpers for settings modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .provider_errors import ProviderSettingsValidationError


def load_json_dict(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ProviderSettingsValidationError(f"Config file must contain a JSON object: {path}")
    return data


def write_json_dict(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON object using the repository's standard formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
