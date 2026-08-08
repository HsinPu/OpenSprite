"""Persistence port used by the OpenSprite application core."""

from abc import ABC, abstractmethod
from typing import Any

from ..contracts import persistence as persistence_contracts


class StorageProvider(ABC):
    """Abstract persistence boundary implemented by storage adapters."""

    @abstractmethod
    async def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[persistence_contracts.StoredMessage]:
        """
        取得對話歷史

        參數：
            session_id: 聊天室 ID
            limit: 最多取幾筆（可選）

        回傳：
            list[StoredMessage]: 訊息清單
        """
        pass

    async def get_message_count(self, session_id: str) -> int:
        """Return the total persisted message count for one chat."""
        return len(await self.get_messages(session_id))

    async def get_messages_slice(
        self,
        session_id: str,
        *,
        start_index: int = 0,
        end_index: int | None = None,
    ) -> list[persistence_contracts.StoredMessage]:
        """Return one contiguous message slice using Python slice semantics."""
        messages = await self.get_messages(session_id)
        return messages[max(0, start_index):end_index]

    @abstractmethod
    async def add_message(self, session_id: str, message: persistence_contracts.StoredMessage) -> None:
        """
        加入訊息到歷史

        參數：
            session_id: 聊天室 ID
            message: StoredMessage 訊息
        """
        pass

    @abstractmethod
    async def clear_messages(self, session_id: str) -> None:
        """
        清除指定聊天室的歷史

        參數：
            session_id: 聊天室 ID
        """
        pass

    @abstractmethod
    async def get_consolidated_index(self, session_id: str) -> int:
        """Get the last consolidated message index for a chat."""
        pass

    @abstractmethod
    async def set_consolidated_index(self, session_id: str, index: int) -> None:
        """Persist the last consolidated message index for a chat."""
        pass

    @abstractmethod
    async def create_run(
        self,
        session_id: str,
        run_id: str,
        *,
        status: str = "running",
        metadata: dict[str, Any] | None = None,
        created_at: float | None = None,
    ) -> persistence_contracts.StoredRun | None:
        """Persist a run and return the durable record."""
        pass

    @abstractmethod
    async def update_run_status(
        self,
        session_id: str,
        run_id: str,
        status: str,
        *,
        metadata: dict[str, Any] | None = None,
        finished_at: float | None = None,
    ) -> persistence_contracts.StoredRun | None:
        """Update a run lifecycle state and return the durable record when found."""
        pass

    @abstractmethod
    async def get_runs(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[persistence_contracts.StoredRun]:
        """Return persisted runs for one chat from newest to oldest."""
        pass

    async def get_run(self, session_id: str, run_id: str) -> persistence_contracts.StoredRun | None:
        """Return one persisted run for a chat."""
        for run in await self.get_runs(session_id):
            if run.run_id == run_id:
                return run
        return None

    async def get_latest_run(self, session_id: str) -> persistence_contracts.StoredRun | None:
        """Return the newest persisted run for one chat."""
        runs = await self.get_runs(session_id, limit=1)
        return runs[0] if runs else None

    @abstractmethod
    async def add_run_event(
        self,
        session_id: str,
        run_id: str,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        created_at: float | None = None,
    ) -> persistence_contracts.StoredRunEvent | None:
        """Persist one structured run event."""
        pass

    @abstractmethod
    async def get_run_events(
        self,
        session_id: str,
        run_id: str,
    ) -> list[persistence_contracts.StoredRunEvent]:
        """Return persisted events for one run."""
        pass

    @abstractmethod
    async def add_run_part(
        self,
        session_id: str,
        run_id: str,
        part_type: str,
        *,
        content: str = "",
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: float | None = None,
    ) -> persistence_contracts.StoredRunPart | None:
        """Persist one ordered run artifact."""
        pass

    @abstractmethod
    async def get_run_parts(
        self,
        session_id: str,
        run_id: str,
    ) -> list[persistence_contracts.StoredRunPart]:
        """Return ordered run artifacts for one run."""
        pass

    @abstractmethod
    async def add_run_file_change(
        self,
        session_id: str,
        run_id: str,
        tool_name: str,
        path: str,
        action: str,
        *,
        before_sha256: str | None = None,
        after_sha256: str | None = None,
        before_content: str | None = None,
        after_content: str | None = None,
        diff: str = "",
        metadata: dict[str, Any] | None = None,
        created_at: float | None = None,
    ) -> persistence_contracts.StoredRunFileChange | None:
        """Persist one file mutation captured during a run."""
        pass

    @abstractmethod
    async def get_run_file_changes(
        self,
        session_id: str,
        run_id: str,
    ) -> list[persistence_contracts.StoredRunFileChange]:
        """Return ordered file mutations captured for one run."""
        pass

    async def get_run_file_change(
        self,
        session_id: str,
        run_id: str,
        change_id: int,
    ) -> persistence_contracts.StoredRunFileChange | None:
        """Return one captured file mutation for a run."""
        for change in await self.get_run_file_changes(session_id, run_id):
            if change.change_id == change_id:
                return change
        return None

    async def get_run_trace(
        self,
        session_id: str,
        run_id: str,
    ) -> persistence_contracts.StoredRunTrace | None:
        """Return a run with its ordered events and durable parts."""
        run = await self.get_run(session_id, run_id)
        if run is None:
            return None
        return persistence_contracts.StoredRunTrace(
            run=run,
            events=await self.get_run_events(session_id, run_id),
            parts=await self.get_run_parts(session_id, run_id),
            file_changes=await self.get_run_file_changes(session_id, run_id),
        )

    @abstractmethod
    async def upsert_background_process(
        self,
        process: persistence_contracts.StoredBackgroundProcess,
    ) -> persistence_contracts.StoredBackgroundProcess | None:
        """Create or update persisted background process metadata."""
        pass

    @abstractmethod
    async def get_background_process(
        self,
        process_session_id: str,
    ) -> persistence_contracts.StoredBackgroundProcess | None:
        """Return one persisted background process by process session id."""
        pass

    @abstractmethod
    async def list_background_processes(
        self,
        *,
        owner_session_id: str | None = None,
        states: tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> list[persistence_contracts.StoredBackgroundProcess]:
        """Return persisted background processes from newest to oldest."""
        pass

    async def get_recent_sessions(self, limit: int | None = None) -> list[str]:
        """Return known session ids from newest to oldest."""
        session_ids = await self.get_all_sessions()
        if limit is not None:
            return session_ids[: max(0, int(limit))]
        return session_ids

    @abstractmethod
    async def get_all_sessions(self) -> list[str]:
        """
        取得所有聊天室 ID

        回傳：
            list[str]: 聊天室 ID 清單
        """
        pass
