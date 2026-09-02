"""Process-local wakeups for consumers of persisted Run events."""

from __future__ import annotations

from threading import Condition


class RunEventNotifier:
    """Signal event-stream readers without polling SQLite on every tick."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._versions: dict[str, int] = {}

    def version(self, run_id: str) -> int:
        with self._condition:
            return self._versions.get(run_id, 0)

    def signal(self, run_id: str) -> None:
        with self._condition:
            self._versions[run_id] = self._versions.get(run_id, 0) + 1
            self._condition.notify_all()

    def wait(self, run_id: str, version: int, timeout: float) -> int:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        with self._condition:
            self._condition.wait_for(
                lambda: self._versions.get(run_id, 0) != version,
                timeout=timeout,
            )
            return self._versions.get(run_id, 0)
