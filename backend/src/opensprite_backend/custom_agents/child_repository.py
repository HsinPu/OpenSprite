"""Durable child ownership and terminal results without conversation writes."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import re
import json
import sqlite3
from uuid import UUID, uuid4

from .models import AgentError


ACTIVE = frozenset({"queued", "running", "cancelling"})
TERMINAL = frozenset({"completed", "failed", "cancelled", "interrupted", "timed_out"})


@dataclass(frozen=True, slots=True)
class ChildExecution:
    id: str
    parent_run_id: str
    spawn_call_id: str
    request_hash: str
    agent_id: str
    agent_name: str
    agent_revision: int
    definition_hash: str
    provider_id: str
    model_id: str
    status: str
    result_text: str = field(repr=False)
    error_code: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class ChildExecutionRepository:
    def __init__(self, database_file: Path) -> None:
        self._file = database_file

    @contextmanager
    def _connection(self):
        connection = None
        try:
            # The conversation owner initializes/migrates the shared database.
            # Never silently create an empty second database here.
            connection = sqlite3.connect(
                self._file.resolve().as_uri() + "?mode=rw", uri=True,
                timeout=5, isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        except (sqlite3.Error, OSError, ValueError) as error:
            raise AgentError("store_unavailable") from error
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    @staticmethod
    def _identifier(value: str) -> None:
        try:
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise AgentError("invalid_request") from None

    @staticmethod
    def _owned(connection, parent_id: str, child_id: str) -> ChildExecution:
        row = connection.execute(
            "SELECT * FROM agent_executions WHERE id=? AND parent_run_id=?",
            (child_id, parent_id),
        ).fetchone()
        if row is None:
            raise AgentError("not_found")
        return ChildExecution(**dict(row))

    def create(self, *, parent_id: str, call_id: str, request_hash: str,
               agent_id: str, name: str, revision: int, definition_hash: str,
               provider_id: str, model_id: str) -> tuple[ChildExecution, bool]:
        self._identifier(parent_id)
        self._identifier(agent_id)
        if (
            not isinstance(call_id, str) or not 1 <= len(call_id) <= 256
            or not isinstance(name, str) or not 1 <= len(name) <= 80
            or type(revision) is not int or revision < 1
            or provider_id not in {"openai", "anthropic", "openrouter"}
            or not isinstance(model_id, str) or not 1 <= len(model_id) <= 256
            or any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
                   for value in (request_hash, definition_hash))
        ):
            raise AgentError("invalid_request")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM agent_executions WHERE parent_run_id=? AND spawn_call_id=?",
                (parent_id, call_id),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    raise AgentError("idempotency_conflict")
                connection.commit()
                return ChildExecution(**dict(row)), True
            parent = connection.execute("SELECT status FROM runs WHERE id=?", (parent_id,)).fetchone()
            if parent is None:
                raise AgentError("not_found")
            if parent["status"] != "running":
                raise AgentError("parent_not_running")
            count = connection.execute(
                "SELECT COUNT(*) FROM agent_executions WHERE parent_run_id=?", (parent_id,)
            ).fetchone()[0]
            if count >= 6:
                raise AgentError("child_limit_reached")
            child_id = str(uuid4())
            connection.execute(
                """INSERT INTO agent_executions (
                    id,parent_run_id,spawn_call_id,request_hash,agent_id,agent_name,
                    agent_revision,definition_hash,provider_id,model_id,status,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,'queued',?)""",
                (child_id, parent_id, call_id, request_hash, agent_id, name, revision,
                 definition_hash, provider_id, model_id, datetime.now(UTC).isoformat()),
            )
            result = self._owned(connection, parent_id, child_id)
            connection.commit()
            return result, False

    def get(self, parent_id: str, child_id: str) -> ChildExecution:
        self._identifier(parent_id)
        self._identifier(child_id)
        with self._connection() as connection:
            return self._owned(connection, parent_id, child_id)

    def list(self, parent_id: str) -> tuple[ChildExecution, ...]:
        self._identifier(parent_id)
        with self._connection() as connection:
            return tuple(ChildExecution(**dict(row)) for row in connection.execute(
                "SELECT * FROM agent_executions WHERE parent_run_id=? ORDER BY created_at,id",
                (parent_id,),
            ))

    def transition(self, parent_id: str, child_id: str, status: str, *,
                   result_text: str = "", error_code: str | None = None) -> ChildExecution:
        self._identifier(parent_id)
        self._identifier(child_id)
        if (status not in ACTIVE | TERMINAL or not isinstance(result_text, str)
            or len(result_text) > 1048576
            or (error_code is not None and (
                not isinstance(error_code, str) or re.fullmatch(r"[a-z_]{1,80}", error_code) is None))):
            raise AgentError("invalid_request")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = self._owned(connection, parent_id, child_id)
            if old.status in TERMINAL:
                connection.commit()
                return old
            allowed = {
                "queued": {"running", "cancelling", "cancelled", "failed", "interrupted", "timed_out"},
                "running": {"cancelling", *TERMINAL},
                "cancelling": {"cancelled", "interrupted", "timed_out", "failed"},
            }
            if status not in allowed[old.status]:
                raise AgentError("invalid_transition")
            now = datetime.now(UTC).isoformat()
            connection.execute(
                """UPDATE agent_executions SET status=?, result_text=?, error_code=?,
                    started_at=?, finished_at=? WHERE id=? AND parent_run_id=?""",
                (status, result_text, error_code,
                 now if status == "running" else old.started_at,
                 now if status in TERMINAL else None, child_id, parent_id),
            )
            result = self._owned(connection, parent_id, child_id)
            connection.commit()
            return result

    def interrupt_incomplete(self) -> int:
        if not self._file.exists():
            return 0
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE agent_executions SET status='interrupted',
                    error_code='backend_restarted', finished_at=?
                    WHERE status IN ('queued','running','cancelling')""",
                (datetime.now(UTC).isoformat(),),
            )
            return cursor.rowcount

    def mark_timeout(self, parent_id: str, child_id: str) -> ChildExecution:
        """The task owner distinguishes deadline cancellation from user cancel."""
        self._identifier(parent_id)
        self._identifier(child_id)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._owned(connection, parent_id, child_id)
            connection.execute(
                """UPDATE agent_executions SET status='timed_out', error_code='timeout',
                    finished_at=? WHERE id=? AND parent_run_id=?
                    AND status IN ('queued','running','cancelling','cancelled')""",
                (datetime.now(UTC).isoformat(), child_id, parent_id),
            )
            result = self._owned(connection, parent_id, child_id)
            connection.commit()
            return result

    def append_event(self, parent_id: str, child_id: str, event_type: str,
                     data: dict[str, object]) -> int:
        from opensprite_backend.conversations.models import RunEventType

        self._identifier(parent_id)
        self._identifier(child_id)
        try:
            RunEventType(event_type)
            payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if len(payload) > 65536:
                raise ValueError
        except (ValueError, TypeError):
            raise AgentError("invalid_request") from None
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._owned(connection, parent_id, child_id)
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM agent_execution_events WHERE execution_id=?",
                (child_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO agent_execution_events VALUES (?,?,?,?,?)",
                (child_id, sequence, event_type, payload, datetime.now(UTC).isoformat()),
            )
            connection.commit()
            return sequence
