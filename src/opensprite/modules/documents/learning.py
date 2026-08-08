"""Session learning policies and prompt-facing services."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Protocol

_LEARNING_LEDGER_LIMIT = 200
_LEARNING_RELEVANT_LIMIT = 4
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}|[\u4e00-\u9fff]{2,}")
_KIND_LABELS = {
    "skill": "Skill",
    "memory": "Memory",
    "user_profile": "User profile",
    "recent_summary": "Recent summary",
}
_TARGET_LABELS = {
    "memory": "Session memory",
    "user_profile": "Session profile",
    "recent_summary": "Recent summary",
}


class _LearningEntryStore(Protocol):
    def load_entries(self, session_id: str) -> list[dict[str, Any]]: ...

    def save_entries(self, session_id: str, entries: list[dict[str, Any]]) -> None: ...

    def clear_session(self, session_id: str) -> None: ...


class LearningLedger:
    """Session-scoped ledger for learned artifacts and reuse outcomes."""

    def __init__(self, store: _LearningEntryStore | None = None):
        self._store = store
        self._memory_sessions: dict[str, list[dict[str, Any]]] = {}

    def _load_entries(self, session_id: str) -> list[dict[str, Any]]:
        if self._store is None:
            entries = self._memory_sessions.setdefault(session_id, [])
            entries[:] = [
                self._normalize_entry(item)
                for item in entries
                if isinstance(item, dict)
            ][-_LEARNING_LEDGER_LIMIT:]
            return entries
        entries = self._store.load_entries(session_id)
        return [
            self._normalize_entry(item)
            for item in entries
            if isinstance(item, dict)
        ][-_LEARNING_LEDGER_LIMIT:]

    def _save_entries(self, session_id: str, entries: list[dict[str, Any]]) -> None:
        normalized_entries = [
            self._normalize_entry(item)
            for item in entries
            if isinstance(item, dict)
        ][-_LEARNING_LEDGER_LIMIT:]
        if self._store is None:
            self._memory_sessions[session_id] = normalized_entries
            return
        self._store.save_entries(session_id, normalized_entries)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def _session_entries(self, session_id: str) -> list[dict[str, Any]]:
        return self._load_entries(session_id)

    def _normalize_entry(
        self,
        entry: dict[str, Any],
        *,
        kind: str = "",
        target_id: str = "",
    ) -> dict[str, Any]:
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        return {
            "kind": str(entry.get("kind") or kind or "other").strip(),
            "target_id": str(entry.get("target_id") or target_id or "item").strip(),
            "summary": str(entry.get("summary") or "").strip(),
            "source_run_id": str(entry.get("source_run_id") or "").strip() or None,
            "metadata": dict(metadata),
            "created_at": str(entry.get("created_at") or self._now_iso()).strip()
            or self._now_iso(),
            "updated_at": str(
                entry.get("updated_at") or entry.get("created_at") or self._now_iso()
            ).strip()
            or self._now_iso(),
            "last_used_at": str(entry.get("last_used_at") or "").strip() or None,
            "use_count": self._safe_int(entry.get("use_count")),
            "last_outcome": str(entry.get("last_outcome") or "").strip() or None,
        }

    @staticmethod
    def _find_entry(
        entries: list[dict[str, Any]],
        *,
        kind: str,
        target_id: str,
    ) -> dict[str, Any] | None:
        for entry in entries:
            if entry["kind"] == kind and entry["target_id"] == target_id:
                return entry
        return None

    def record_learning(
        self,
        session_id: str,
        *,
        kind: str,
        target_id: str,
        summary: str,
        source_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entries = self._session_entries(session_id)
        entry = self._find_entry(entries, kind=kind, target_id=target_id)
        now = self._now_iso()
        if entry is None:
            entry = self._normalize_entry({}, kind=kind, target_id=target_id)
            entry["created_at"] = now
            entries.append(entry)
        entry["summary"] = str(summary or entry.get("summary") or "").strip()
        entry["source_run_id"] = source_run_id or entry.get("source_run_id")
        if metadata:
            entry["metadata"] = {**entry.get("metadata", {}), **metadata}
        entry["updated_at"] = now
        self._save_entries(session_id, entries)
        return dict(entry)

    def mark_used(
        self,
        session_id: str,
        *,
        kind: str,
        target_id: str,
        outcome: str,
        summary: str | None = None,
        source_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entries = self._session_entries(session_id)
        entry = self._find_entry(entries, kind=kind, target_id=target_id)
        now = self._now_iso()
        if entry is None:
            entry = self._normalize_entry({}, kind=kind, target_id=target_id)
            entry["created_at"] = now
            entries.append(entry)
        if summary:
            entry["summary"] = str(summary).strip()
        if source_run_id:
            entry["source_run_id"] = source_run_id
        if metadata:
            entry["metadata"] = {**entry.get("metadata", {}), **metadata}
        entry["last_used_at"] = now
        entry["last_outcome"] = str(outcome or "success").strip() or "success"
        entry["use_count"] = self._safe_int(entry.get("use_count")) + 1
        entry["updated_at"] = now
        self._save_entries(session_id, entries)
        return dict(entry)

    def recent_entries(self, session_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        entries = sorted(
            self._session_entries(session_id),
            key=lambda item: (
                str(item.get("updated_at") or ""),
                str(item.get("created_at") or ""),
            ),
            reverse=True,
        )
        return [dict(entry) for entry in entries[: max(1, int(limit or 1))]]

    def clear_session(self, session_id: str) -> None:
        """Delete all learned artifacts for one session."""
        self._memory_sessions.pop(session_id, None)
        if self._store is not None:
            self._store.clear_session(session_id)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        seen: list[str] = []
        for token in _TOKEN_PATTERN.findall(str(text or "").lower()):
            if token not in seen:
                seen.append(token)
        return seen

    @staticmethod
    def _entry_title(entry: dict[str, Any]) -> str:
        kind = str(entry.get("kind") or "other").strip()
        target_id = str(entry.get("target_id") or "item").strip()
        if kind == "skill":
            return target_id
        return _TARGET_LABELS.get(target_id, target_id.replace("_", " "))

    def _score_entry(self, entry: dict[str, Any], tokens: list[str]) -> int:
        haystack = " ".join(
            [
                str(entry.get("target_id") or ""),
                str(entry.get("summary") or ""),
                json.dumps(entry.get("metadata") or {}, ensure_ascii=False),
            ]
        ).lower()
        score = 0
        for token in tokens:
            if token and token in haystack:
                score += 6
        score += min(self._safe_int(entry.get("use_count")), 5)
        if entry.get("last_outcome") == "success":
            score += 2
        if entry.get("last_used_at"):
            score += 1
        if entry.get("kind") == "skill":
            score += 1
        return score

    def relevant_entries(
        self,
        session_id: str,
        current_message: str,
        *,
        limit: int = _LEARNING_RELEVANT_LIMIT,
    ) -> list[dict[str, Any]]:
        entries = self.recent_entries(session_id, limit=_LEARNING_LEDGER_LIMIT)
        if not entries:
            return []
        tokens = self._tokenize(current_message)
        scored = [
            (self._score_entry(entry, tokens), index, entry)
            for index, entry in enumerate(entries)
        ]
        matching = [item for item in scored if item[0] > 0]
        if not matching:
            return []
        matching.sort(
            key=lambda item: (
                item[0],
                str(item[2].get("updated_at") or ""),
                -item[1],
            ),
            reverse=True,
        )
        return [dict(item[2]) for item in matching[: max(1, int(limit or 1))]]

    def build_relevant_context(
        self,
        session_id: str,
        current_message: str,
        *,
        limit: int = _LEARNING_RELEVANT_LIMIT,
    ) -> str:
        entries = self.relevant_entries(session_id, current_message, limit=limit)
        if not entries:
            return ""
        lines = [
            "# Relevant Learned Context",
            "",
            "These items were learned earlier in this session and may help with the current request.",
            "",
        ]
        for entry in entries:
            kind_label = _KIND_LABELS.get(
                str(entry.get("kind") or "").strip(),
                str(entry.get("kind") or "item"),
            )
            title = self._entry_title(entry)
            summary = str(entry.get("summary") or "").strip() or title
            extras: list[str] = []
            use_count = self._safe_int(entry.get("use_count"))
            if use_count > 0:
                extras.append(f"used {use_count}x")
            last_outcome = str(entry.get("last_outcome") or "").strip()
            if last_outcome:
                extras.append(f"last outcome: {last_outcome}")
            detail = f" ({'; '.join(extras)})" if extras else ""
            lines.append(f"- [{kind_label}] {title}: {summary}{detail}")
        return "\n".join(lines)


class _RelevantLearningSource(Protocol):
    def build_relevant_context(self, session_id: str, current_message: str) -> str: ...


class RelevantLearningContextService:
    """Build prompt context from an attached session learning source."""

    def __init__(self, learning_ledger: _RelevantLearningSource | None = None):
        self.learning_ledger = learning_ledger

    def set_learning_ledger(self, ledger: _RelevantLearningSource | None) -> None:
        """Attach or clear the source used for relevant prompt hints."""
        self.learning_ledger = ledger

    def build_context(self, session_id: str, current_message: str) -> str:
        """Return relevant learned context for the current prompt."""
        if self.learning_ledger is None:
            return ""
        return self.learning_ledger.build_relevant_context(session_id, current_message)
