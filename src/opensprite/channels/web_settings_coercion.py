"""Settings coercion helpers for the web adapter."""

from __future__ import annotations

from typing import Any, Callable

from aiohttp import web

from ..config.defaults import (
    BROWSER_BACKENDS,
    DEFAULT_BROWSER_BACKEND,
    DEFAULT_LOG_LEVEL,
    DEFAULT_WEB_SEARCH_FRESHNESS,
    DEFAULT_WEB_SEARCH_PROVIDER,
    LOG_LEVELS,
    WEB_SEARCH_FRESHNESS_OPTIONS,
    WEB_SEARCH_PROVIDERS,
)
from ..utils.url import join_url_path


SEARXNG_FALLBACK_ENGINES = (
    "duckduckgo",
    "google",
    "bing",
    "qwant",
    "startpage",
    "wikipedia",
    "wikidata",
    "github",
    "stackoverflow",
    "reddit",
    "youtube",
    "arxiv",
    "semantic scholar",
)
SEARXNG_FALLBACK_CATEGORIES = ("general", "images", "videos", "news", "map", "music", "it", "science", "files", "social media")


def coerce_text_list(value: Any, *, field: str, default: list[str] | None = None) -> list[str]:
    if value is None or value == "":
        return list(default or [])
    if isinstance(value, str):
        candidates = value.replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        raise web.HTTPBadRequest(text=f"{field} must be a list or comma-separated text")
    items: list[str] = []
    for item in candidates:
        text = str(item or "").strip()
        if text and text not in items:
            items.append(text)
    return items


def apply_optional_secret_field(target: Any, body: dict[str, Any], field: str) -> None:
    clear_field = f"clear_{field}"
    if coerce_bool(body.get(clear_field), field=clear_field, default=False):
        setattr(target, field, "")
        return
    if field in body and (
        value := ("" if body.get(field) is None else str(body.get(field)).strip())
    ):
        setattr(target, field, value)


def coerce_log_level(
    value: Any,
    *,
    default_log_level: str = DEFAULT_LOG_LEVEL,
    log_levels: tuple[str, ...] | list[str] = LOG_LEVELS,
) -> str:
    level = str(value or default_log_level).strip().upper()
    if level not in log_levels:
        raise web.HTTPBadRequest(text=f"level must be one of: {', '.join(log_levels)}")
    return level


def coerce_positive_int(value: Any, *, field: str, default: int, minimum: int = 0, maximum: int = 3650) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise web.HTTPBadRequest(text=f"{field} must be an integer") from exc
    if number < minimum:
        raise web.HTTPBadRequest(text=f"{field} must be at least {minimum}")
    if number > maximum:
        raise web.HTTPBadRequest(text=f"{field} must be at most {maximum}")
    return number


def coerce_float_range(value: Any, *, field: str, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise web.HTTPBadRequest(text=f"{field} must be a number") from exc
    if number < minimum:
        raise web.HTTPBadRequest(text=f"{field} must be at least {minimum}")
    if number > maximum:
        raise web.HTTPBadRequest(text=f"{field} must be at most {maximum}")
    return number


def coerce_bool(value: Any, *, field: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise web.HTTPBadRequest(text=f"{field} must be a boolean")


def _coerce_choice(value: Any, *, field: str, default: str, choices: Any, lowercase: bool = False) -> str:
    choice = str(value or default).strip()
    choice = choice.lower() if lowercase else choice
    choice = choice or default
    if choice not in choices:
        raise web.HTTPBadRequest(text=f"{field} must be one of: {', '.join(choices)}")
    return choice


def coerce_browser_backend(
    value: Any,
    *,
    default_backend: str = DEFAULT_BROWSER_BACKEND,
    backends: tuple[str, ...] | list[str] = BROWSER_BACKENDS,
) -> str:
    return _coerce_choice(value, field="backend", default=default_backend, choices=backends)


def coerce_web_search_provider(
    value: Any,
    *,
    default_provider: str = DEFAULT_WEB_SEARCH_PROVIDER,
    providers: tuple[str, ...] | list[str] = WEB_SEARCH_PROVIDERS,
) -> str:
    return _coerce_choice(value, field="provider", default=default_provider, choices=providers, lowercase=True)


def coerce_web_search_freshness(
    value: Any,
    *,
    default_freshness: str = DEFAULT_WEB_SEARCH_FRESHNESS,
    freshness_values: tuple[str, ...] | list[str] = WEB_SEARCH_FRESHNESS_OPTIONS,
) -> str:
    return _coerce_choice(value, field="freshness", default=default_freshness, choices=freshness_values, lowercase=True)


def normalize_searxng_engine_options(engines: Any) -> list[dict[str, Any]]:
    if not isinstance(engines, list):
        return []
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for engine in engines:
        if isinstance(engine, str):
            engine_id = engine.strip()
            label = engine_id
            shortcut = ""
            categories: list[str] = []
            enabled = None
        elif isinstance(engine, dict):
            engine_id = str(engine.get("name") or engine.get("id") or "").strip()
            label = str(engine.get("display_name") or engine.get("displayName") or engine_id).strip()
            shortcut = str(engine.get("shortcut") or "").strip()
            categories = coerce_text_list(engine.get("categories", []), field="categories", default=[])
            enabled = engine.get("enabled") if isinstance(engine.get("enabled"), bool) else None
        else:
            continue
        if not engine_id or engine_id in seen:
            continue
        seen.add(engine_id)
        options.append({"id": engine_id, "label": label or engine_id, "shortcut": shortcut, "categories": categories, "enabled": enabled})
    return options


def normalize_searxng_category_options(categories: Any) -> list[dict[str, str]]:
    if isinstance(categories, dict):
        candidates = list(categories.keys())
    else:
        candidates = categories
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for category in coerce_text_list(candidates, field="categories", default=[]):
        if category in seen:
            continue
        seen.add(category)
        options.append({"id": category, "label": category})
    return options


def searxng_options_payload(config_payload: dict[str, Any], *, url: str) -> dict[str, Any]:
    engines = normalize_searxng_engine_options(config_payload.get("engines"))
    categories = normalize_searxng_category_options(config_payload.get("categories"))
    if not categories:
        category_names: list[str] = []
        for engine in engines:
            category_names.extend(engine.get("categories") or [])
        categories = normalize_searxng_category_options(category_names)
    return {"url": url, "engines": engines, "categories": categories, "fallback": False, "warning": ""}


def fallback_searxng_options_payload(
    *,
    url: str,
    warning: str,
    fallback_engines: tuple[str, ...] = SEARXNG_FALLBACK_ENGINES,
    fallback_categories: tuple[str, ...] = SEARXNG_FALLBACK_CATEGORIES,
) -> dict[str, Any]:
    return {
        "url": url,
        "engines": [{"id": engine, "label": engine, "shortcut": "", "categories": [], "enabled": None} for engine in fallback_engines],
        "categories": [{"id": category, "label": category} for category in fallback_categories],
        "fallback": True,
        "warning": warning,
    }


def searxng_config_url(searxng_url: str) -> str:
    base = str(searxng_url or "").strip().rstrip("/")
    if base.lower().endswith("/search"):
        base = base[:-len("/search")]
    return join_url_path(base, "/config")
