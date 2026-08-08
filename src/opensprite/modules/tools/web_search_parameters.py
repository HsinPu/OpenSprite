"""Parameter schema for the web search tool."""

from __future__ import annotations

from typing import Any

from ..search.web_policy import FRESHNESS_VALUES as _FRESHNESS_VALUES
from .validation import NON_EMPTY_STRING_PATTERN


def web_search_parameters(*, max_results: int, freshness: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query", "pattern": NON_EMPTY_STRING_PATTERN},
            "count": {
                "type": "integer",
                "description": f"Results (1-{max_results})",
                "default": max_results,
                "minimum": 1,
                "maximum": max_results,
            },
            "freshness": {
                "type": "string",
                "enum": list(_FRESHNESS_VALUES),
                "description": "Recency filter. none searches all time; fixed windows limit results by age.",
                "default": freshness,
            },
        },
        "required": ["query"],
    }
