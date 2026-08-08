"""Stable cross-session user overlay promotion and retrieval policy."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Protocol


class _UserOverlayStore(Protocol):
    def read(self, overlay_id: str) -> str: ...

    def write(self, overlay_id: str, content: str) -> None: ...


class _UserOverlayIndexReader(Protocol):
    def read(self, overlay_id: str) -> dict[str, Any]: ...


class _UserOverlayIndexStore(_UserOverlayIndexReader, Protocol):
    def write(self, overlay_id: str, payload: dict[str, Any]) -> None: ...


_SECTION_HEADING_RE = re.compile(r"^#+\s+(?P<title>.+?)\s*$")
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,}")
_PLACEHOLDER_BULLETS = {
    "no learned communication preferences yet.",
    "no learned work context yet.",
    "no learned stable constraints yet.",
    "no learned user profile details yet.",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_bullets(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = str(line or "").strip()
        if not stripped.startswith("-"):
            continue
        text = stripped[1:].strip()
        if not text or text.lower() in _PLACEHOLDER_BULLETS or text == "not set":
            continue
        if text not in items:
            items.append(text)
    return items


def _section_block(markdown: str, heading: str) -> str:
    current_heading = ""
    collected: list[str] = []
    for raw_line in str(markdown or "").splitlines():
        heading_match = _SECTION_HEADING_RE.match(raw_line)
        if heading_match:
            current_heading = heading_match.group("title").strip().lower()
            continue
        if current_heading == heading.strip().lower():
            collected.append(raw_line)
    return "\n".join(collected)


def _section_bullets(markdown: str, heading: str) -> list[str]:
    return _normalize_bullets(_section_block(markdown, heading).splitlines())


def _profile_bullets(profile_block: str) -> list[str]:
    return _normalize_bullets(str(profile_block or "").splitlines())


def _response_language(response_language_block: str) -> str | None:
    items = _normalize_bullets(str(response_language_block or "").splitlines())
    return items[0] if items else None


def _render_overlay(preferences: list[str], stable_facts: list[str], response_language: str | None) -> str:
    preference_lines = "\n".join(f"- {item}" for item in preferences) if preferences else "- "
    fact_lines = "\n".join(f"- {item}" for item in stable_facts) if stable_facts else "- "
    language_line = f"- {response_language}" if response_language else "- not set"
    return (
        "# Stable Preferences\n"
        f"{preference_lines}\n\n"
        "# Stable Facts\n"
        f"{fact_lines}\n\n"
        "# Response Language\n"
        f"{language_line}\n"
    )


def _merge_stable_lists(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*existing, *incoming]:
        text = str(item or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return normalized or "item"


class UserOverlayPromotionService:
    """Deterministically promote stable session profile/facts into a cross-session overlay."""

    def __init__(self, *, overlay_store: _UserOverlayStore, index_store: _UserOverlayIndexStore):
        self.overlay_store = overlay_store
        self.index_store = index_store

    def update_from_session_documents(
        self,
        overlay_id: str,
        *,
        profile_block: str,
        response_language_block: str,
        memory_text: str,
        source_session_id: str,
        source_run_id: str | None = None,
    ) -> dict[str, Any]:
        current_overlay = self.overlay_store.read(overlay_id)
        existing_preferences = _section_bullets(current_overlay, "Stable Preferences")
        existing_facts = _section_bullets(current_overlay, "Stable Facts")
        existing_language = _response_language(_section_block(current_overlay, "Response Language"))

        profile_preferences = _profile_bullets(profile_block)
        memory_preferences = _section_bullets(memory_text, "User Preferences")
        memory_facts = _section_bullets(memory_text, "Important Facts")

        next_preferences = _merge_stable_lists(existing_preferences, [*profile_preferences, *memory_preferences])
        next_facts = _merge_stable_lists(existing_facts, memory_facts)
        next_language = _response_language(response_language_block) or existing_language

        rendered = _render_overlay(next_preferences, next_facts, next_language)
        changed = rendered.strip() != current_overlay.strip()
        if changed or not current_overlay:
            self.overlay_store.write(overlay_id, rendered)

        now = _now_iso()
        self.index_store.write(
            overlay_id,
            {
                "schema_version": 1,
                "overlay_id": overlay_id,
                "updated_at": now,
                "response_language": (
                    {
                        "text": next_language,
                        "confidence": 0.95,
                        "source_sessions": [source_session_id],
                        **({"source_runs": [source_run_id]} if source_run_id else {}),
                        "updated_at": now,
                    }
                    if next_language
                    else None
                ),
                "preferences": [
                    {
                        "id": f"pref:{_slug(item)}",
                        "text": item,
                        "confidence": 0.9,
                        "source_sessions": [source_session_id],
                        **({"source_runs": [source_run_id]} if source_run_id else {}),
                        "updated_at": now,
                    }
                    for item in next_preferences
                ],
                "stable_facts": [
                    {
                        "id": f"fact:{_slug(item)}",
                        "text": item,
                        "confidence": 0.85,
                        "source_sessions": [source_session_id],
                        **({"source_runs": [source_run_id]} if source_run_id else {}),
                        "updated_at": now,
                    }
                    for item in next_facts
                ],
            },
        )

        return {
            "changed": changed,
            "overlay_id": overlay_id,
            "preferences": next_preferences,
            "stable_facts": next_facts,
            "response_language": next_language,
        }


class UserOverlayRetrievalPlanner:
    """Select concise stable overlay context relevant to the current turn."""

    def __init__(self, *, index_store: _UserOverlayIndexReader, item_limit: int = 4):
        self.index_store = index_store
        self.item_limit = max(1, item_limit)

    def build_context(self, overlay_id: str | None, current_message: str) -> str:
        normalized_overlay_id = str(overlay_id or "").strip()
        if not normalized_overlay_id:
            return ""
        payload = self.index_store.read(normalized_overlay_id)
        tokens = self._tokenize(current_message)
        response_language = payload.get("response_language") if isinstance(payload.get("response_language"), dict) else None
        preferences = [dict(item) for item in payload.get("preferences", []) if isinstance(item, dict)]
        stable_facts = [dict(item) for item in payload.get("stable_facts", []) if isinstance(item, dict)]

        ranked_preferences = self._rank_entries(preferences, tokens)
        ranked_facts = self._rank_entries(stable_facts, tokens)
        selected_preferences = ranked_preferences[: min(2, self.item_limit)]
        remaining = max(0, self.item_limit - len(selected_preferences))
        selected_facts = ranked_facts[:remaining]

        if not response_language and not selected_preferences and not selected_facts:
            return ""

        lines = ["# Relevant Stable User Overlay"]
        if response_language and str(response_language.get("text") or "").strip():
            lines.extend(["", "## Response Language", f"- {str(response_language.get('text') or '').strip()}"])
        if selected_preferences:
            lines.extend(["", "## Relevant Stable Preferences", *[f"- {item['text']}" for item in selected_preferences]])
        if selected_facts:
            lines.extend(["", "## Relevant Stable Facts", *[f"- {item['text']}" for item in selected_facts]])
        return "\n".join(lines).strip()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        seen: list[str] = []
        for token in _TOKEN_PATTERN.findall(str(text or "").lower()):
            if token not in seen:
                seen.append(token)
        return seen

    @staticmethod
    def _score_entry(entry: dict[str, Any], tokens: list[str]) -> int:
        haystack = str(entry.get("text") or "").lower()
        score = 0
        for token in tokens:
            if token and token in haystack:
                score += 5
        score += int(float(entry.get("confidence") or 0) * 10)
        return score

    def _rank_entries(self, entries: list[dict[str, Any]], tokens: list[str]) -> list[dict[str, Any]]:
        ranked = sorted(
            entries,
            key=lambda entry: (
                self._score_entry(entry, tokens),
                str(entry.get("updated_at") or ""),
            ),
            reverse=True,
        )
        if tokens:
            matched = [entry for entry in ranked if self._score_entry(entry, tokens) > int(float(entry.get("confidence") or 0) * 10)]
            if matched:
                return matched
        return ranked


class RelevantUserOverlayContextService:
    """Tracks stable user overlay identity and renders relevant prompt context."""

    def __init__(self, *, index_store: _UserOverlayIndexReader):
        self.index_store = index_store
        self._retrieval_planner = UserOverlayRetrievalPlanner(index_store=index_store)
        self._session_overlay_ids: dict[str, str] = {}

    @staticmethod
    def _normalize_session_id(session_id: str | None) -> str:
        return str(session_id or "default").strip() or "default"

    @staticmethod
    def _normalize_overlay_id(overlay_id: str | None) -> str:
        return str(overlay_id or "").strip()

    def set_session_overlay_id(self, session_id: str, overlay_id: str | None) -> None:
        """Record or clear the stable overlay identity for one session."""
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_overlay_id = self._normalize_overlay_id(overlay_id)
        if not normalized_overlay_id:
            self._session_overlay_ids.pop(normalized_session_id, None)
            return
        self._session_overlay_ids[normalized_session_id] = normalized_overlay_id

    def get_session_overlay_id(self, session_id: str) -> str | None:
        """Return the stable overlay identity resolved for one session."""
        return self._session_overlay_ids.get(self._normalize_session_id(session_id))

    def build_context(self, session_id: str, current_message: str) -> str:
        """Return relevant stable overlay context for the current prompt."""
        overlay_id = self.get_session_overlay_id(session_id)
        if not overlay_id:
            return ""
        return self._retrieval_planner.build_context(overlay_id, current_message)
