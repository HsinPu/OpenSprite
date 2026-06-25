"""Provider model discovery helpers."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from ..utils.url import join_url_path


MODEL_DISCOVERY_TIMEOUT_SECONDS = 8.0
_OPENROUTER_MODEL_METADATA_CACHE: dict[str, dict[str, Any]] = {}


def _dedupe_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for model in models:
        normalized = str(model or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _read_json_url(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers=headers or {"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=MODEL_DISCOVERY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _models_from_openai_compatible_payload(payload: dict[str, Any] | None) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    return _dedupe_models([str(item.get("id") or "") for item in data if isinstance(item, dict)])


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.isdigit():
            parsed = int(normalized)
            return parsed if parsed > 0 else None
    return None


def _openrouter_model_metadata(item: dict[str, Any]) -> dict[str, Any]:
    context_length = _positive_int(item.get("context_length"))
    if context_length is None:
        top_provider = item.get("top_provider")
        if isinstance(top_provider, dict):
            context_length = _positive_int(top_provider.get("context_length"))
    return {"context_length": context_length} if context_length else {}


def cached_openrouter_model_metadata(models: list[str] | tuple[str, ...] | None = None) -> dict[str, dict[str, Any]]:
    """Return metadata captured during the last OpenRouter model discovery."""
    if models is None:
        return {model: dict(metadata) for model, metadata in _OPENROUTER_MODEL_METADATA_CACHE.items()}
    allowed = {str(model or "").strip() for model in models if str(model or "").strip()}
    return {
        model: dict(metadata)
        for model, metadata in _OPENROUTER_MODEL_METADATA_CACHE.items()
        if model in allowed and metadata
    }


def fetch_openai_compatible_models(api_key: str, base_url: str) -> list[str]:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        return []
    lowered = normalized.lower()
    probe_base = normalized[: -len("/models")] if lowered.endswith("/models") else normalized
    candidates = [normalized]
    if probe_base.lower().endswith("/v1"):
        candidates.append(probe_base[:-3].rstrip("/"))
    else:
        candidates.append(f"{probe_base}/v1")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for candidate in _dedupe_models(candidates):
        models = _models_from_openai_compatible_payload(_read_json_url(join_url_path(candidate, "/models"), headers=headers))
        if models:
            return models
    return []


def fetch_openrouter_models() -> list[str]:
    global _OPENROUTER_MODEL_METADATA_CACHE
    _OPENROUTER_MODEL_METADATA_CACHE = {}
    payload = _read_json_url("https://openrouter.ai/api/v1/models", headers={"Accept": "application/json"})
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    out: list[str] = []
    metadata_by_model: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        params = item.get("supported_parameters")
        if isinstance(params, list) and params and "tools" not in {str(param) for param in params}:
            continue
        out.append(model_id)
        metadata = _openrouter_model_metadata(item)
        if metadata and model_id not in metadata_by_model:
            metadata_by_model[model_id] = metadata
    _OPENROUTER_MODEL_METADATA_CACHE = metadata_by_model
    return _dedupe_models(out)


def fetch_openrouter_image_models() -> list[str]:
    payload = _read_json_url("https://openrouter.ai/api/v1/models", headers={"Accept": "application/json"})
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        architecture = item.get("architecture")
        modalities = architecture.get("input_modalities") if isinstance(architecture, dict) else None
        if not model_id or not isinstance(modalities, list):
            continue
        if "image" in {str(modality).strip().lower() for modality in modalities}:
            out.append(model_id)
    return _dedupe_models(out)


def fetch_copilot_provider_models(api_key: str) -> list[str]:
    try:
        from ..auth.copilot import fetch_copilot_models

        return fetch_copilot_models(api_key)
    except Exception:
        return []


def fetch_codex_models(app_home: str | Path | None = None) -> list[str]:
    try:
        from ..auth.codex import load_or_refresh_codex_token

        token = load_or_refresh_codex_token(app_home).access_token
    except Exception:
        return []
    payload = _read_json_url(
        "https://chatgpt.com/backend-api/codex/models?client_version=1.0.0",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    entries = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    sortable: list[tuple[int, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug or item.get("supported_in_api") is False:
            continue
        visibility = str(item.get("visibility") or "").strip().lower()
        if visibility in {"hide", "hidden"}:
            continue
        priority = item.get("priority")
        rank = int(priority) if isinstance(priority, (int, float)) else 10_000
        sortable.append((rank, slug))
    sortable.sort(key=lambda item: (item[0], item[1]))
    return _dedupe_models([slug for _, slug in sortable])
