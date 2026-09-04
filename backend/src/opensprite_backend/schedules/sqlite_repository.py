"""SQLite schedule persistence sharing the conversation database schema."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import UTC, datetime, time
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import UUID, uuid4

from ..conversations.sqlite_repository import SqliteConversationRepository
from .models import (
    Cadence, CadenceType, ExecutionProfile, Occurrence, OccurrencePage,
    OccurrenceStatus, OccurrenceTrigger, Schedule, ScheduleDraft, SchedulePage,
    ScheduleStatus,
)
from .repository import ScheduleFailure, ScheduleStoreError


class SqliteScheduleRepository:
    def __init__(self, database_file: str | Path, *, clock=None, identifier_factory=None) -> None:
        self._database_file = Path(database_file)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._identifier_factory = identifier_factory or (lambda: str(uuid4()))
        self._lock = RLock()

    def create(self, draft: ScheduleDraft, *, next_run_at: datetime | None) -> Schedule:
        self._validate_draft(draft)
        now = self._now(); identifier = self._new_id()
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO schedules(id,workspace_id,name,prompt,cadence_type,run_at,local_time,weekdays_json,time_zone,provider_id,model_id,response_mode,context_budget,output_budget,output_continuation,status,conversation_id,next_run_at,revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,1,?,?)""",
                self._draft_values(identifier, draft, ScheduleStatus.ACTIVE, next_run_at, now),
            )
            connection.commit()
            return self._schedule(self._require_row(connection, identifier))

    def get(self, schedule_id: str) -> Schedule | None:
        self._require_id(schedule_id)
        connection = self._read()
        if connection is None: return None
        try:
            row = connection.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
            return None if row is None else self._schedule(row)
        finally: connection.close()

    def list(self, *, limit: int, before: str | None) -> SchedulePage:
        if type(limit) is not int or not 1 <= limit <= 100: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        cursor = self._decode(before) if before else None
        connection = self._read()
        if connection is None: return SchedulePage((), None)
        try:
            if cursor is None:
                rows = connection.execute("SELECT * FROM schedules ORDER BY updated_at DESC,id DESC LIMIT ?", (limit + 1,)).fetchall()
            else:
                stamp, identifier = cursor
                rows = connection.execute("SELECT * FROM schedules WHERE updated_at<? OR (updated_at=? AND id<?) ORDER BY updated_at DESC,id DESC LIMIT ?", (stamp, stamp, identifier, limit + 1)).fetchall()
            selected = rows[:limit]
            return SchedulePage(tuple(self._schedule(row) for row in selected), self._encode(selected[-1]["updated_at"], selected[-1]["id"]) if len(rows) > limit and selected else None)
        finally: connection.close()

    def update(self, schedule_id: str, revision: int, draft: ScheduleDraft, *, next_run_at: datetime | None) -> Schedule:
        self._require_id(schedule_id); self._validate_draft(draft); self._require_revision(revision)
        now = self._now()
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM schedules WHERE id=?",
                (schedule_id,),
            ).fetchone()
            if current is None:
                raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
            if int(current["revision"]) != revision:
                raise ScheduleStoreError(ScheduleFailure.REVISION_CONFLICT)
            if current["workspace_id"] != draft.workspace_id:
                if connection.execute(
                    "SELECT 1 FROM schedule_occurrences WHERE schedule_id=? "
                    "AND status IN ('pending','running') LIMIT 1",
                    (schedule_id,),
                ).fetchone() is not None:
                    raise ScheduleStoreError(ScheduleFailure.WORKSPACE_BUSY)
                conversation_id = current["conversation_id"]
                if conversation_id is not None:
                    if connection.execute(
                        "SELECT 1 FROM runs WHERE conversation_id=? "
                        "AND status IN ('queued','running','cancelling') LIMIT 1",
                        (conversation_id,),
                    ).fetchone() is not None:
                        raise ScheduleStoreError(ScheduleFailure.WORKSPACE_BUSY)
                    connection.execute(
                        "UPDATE conversations SET workspace_id=?, revision=revision+1 "
                        "WHERE id=?",
                        (draft.workspace_id, conversation_id),
                    )
            changed = connection.execute(
                """UPDATE schedules SET workspace_id=?,name=?,prompt=?,cadence_type=?,run_at=?,local_time=?,weekdays_json=?,time_zone=?,provider_id=?,model_id=?,response_mode=?,context_budget=?,output_budget=?,output_continuation=?,status=CASE WHEN status='paused' THEN 'paused' ELSE 'active' END,next_run_at=CASE WHEN status='paused' THEN NULL ELSE ? END,revision=revision+1,updated_at=? WHERE id=? AND revision=?""",
                self._editable_values(draft, next_run_at, now) + (schedule_id, revision),
            ).rowcount
            if changed == 0: self._raise_missing_or_conflict(connection, schedule_id)
            connection.commit(); return self._schedule(self._require_row(connection, schedule_id))

    def set_status(self, schedule_id: str, revision: int, status: ScheduleStatus, *, next_run_at: datetime | None) -> Schedule:
        self._require_id(schedule_id); self._require_revision(revision)
        if not isinstance(status, ScheduleStatus): raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute("UPDATE schedules SET status=?,next_run_at=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?", (status.value, self._stamp(next_run_at), self._stamp(self._now()), schedule_id, revision)).rowcount
            if changed == 0: self._raise_missing_or_conflict(connection, schedule_id)
            connection.commit(); return self._schedule(self._require_row(connection, schedule_id))

    def delete(self, schedule_id: str) -> None:
        self._require_id(schedule_id)
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("DELETE FROM schedules WHERE id=?", (schedule_id,)).rowcount == 0: raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
            connection.commit()

    def create_occurrence(self, schedule_id: str, *, scheduled_for: datetime, trigger: OccurrenceTrigger, status: OccurrenceStatus, error_code: str | None = None, missed_count: int = 0) -> Occurrence:
        self._require_id(schedule_id)
        if scheduled_for.tzinfo is None or not isinstance(trigger, OccurrenceTrigger) or not isinstance(status, OccurrenceStatus) or type(missed_count) is not int or missed_count < 0: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        identifier = self._new_id(); now = self._now()
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("INSERT INTO schedule_occurrences(id,schedule_id,scheduled_for,trigger,status,run_id,error_code,missed_count,started_at,finished_at,created_at) VALUES(?,?,?,?,?,NULL,?,?,NULL,?,?)", (identifier, schedule_id, self._stamp(scheduled_for), trigger.value, status.value, error_code, missed_count, self._stamp(now) if status in {OccurrenceStatus.COMPLETED,OccurrenceStatus.FAILED,OccurrenceStatus.SKIPPED} else None, self._stamp(now)))
            except sqlite3.IntegrityError as error:
                raise ScheduleStoreError(ScheduleFailure.REVISION_CONFLICT) from error
            connection.commit()
            return self._occurrence(connection.execute("SELECT * FROM schedule_occurrences WHERE id=?", (identifier,)).fetchone())

    def list_occurrences(self, schedule_id: str, *, limit: int, before: str | None) -> OccurrencePage:
        self._require_id(schedule_id)
        if type(limit) is not int or not 1 <= limit <= 100: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        cursor = self._decode(before) if before else None; connection = self._read()
        if connection is None: return OccurrencePage((), None)
        try:
            if connection.execute("SELECT 1 FROM schedules WHERE id=?", (schedule_id,)).fetchone() is None: raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
            if cursor is None: rows=connection.execute("SELECT * FROM schedule_occurrences WHERE schedule_id=? ORDER BY scheduled_for DESC,id DESC LIMIT ?",(schedule_id,limit+1)).fetchall()
            else:
                stamp, identifier=cursor; rows=connection.execute("SELECT * FROM schedule_occurrences WHERE schedule_id=? AND (scheduled_for<? OR (scheduled_for=? AND id<?)) ORDER BY scheduled_for DESC,id DESC LIMIT ?",(schedule_id,stamp,stamp,identifier,limit+1)).fetchall()
            selected=rows[:limit]
            return OccurrencePage(tuple(self._occurrence(row) for row in selected),self._encode(selected[-1]["scheduled_for"],selected[-1]["id"]) if len(rows)>limit and selected else None)
        finally: connection.close()

    def latest_occurrences(self, schedule_ids: tuple[str, ...]) -> dict[str, Occurrence]:
        if not schedule_ids:
            return {}
        if len(schedule_ids) > 100:
            raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        for schedule_id in schedule_ids:
            self._require_id(schedule_id)
        connection = self._read()
        if connection is None:
            return {}
        placeholders = ",".join("?" for _ in schedule_ids)
        try:
            rows = connection.execute(
                f"""SELECT * FROM (
                    SELECT occurrence.*, ROW_NUMBER() OVER (
                        PARTITION BY schedule_id
                        ORDER BY scheduled_for DESC, id DESC
                    ) AS occurrence_rank
                    FROM schedule_occurrences AS occurrence
                    WHERE schedule_id IN ({placeholders})
                ) WHERE occurrence_rank=1""",
                schedule_ids,
            ).fetchall()
            return {
                row["schedule_id"]: self._occurrence(row)
                for row in rows
            }
        except sqlite3.Error as error:
            raise ScheduleStoreError(ScheduleFailure.DATABASE_UNAVAILABLE) from error
        finally:
            connection.close()

    def list_due(self, *, now: datetime, limit: int = 100) -> tuple[Schedule, ...]:
        if now.tzinfo is None or type(limit) is not int or not 1 <= limit <= 100: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        connection=self._read()
        if connection is None: return ()
        try: return tuple(self._schedule(row) for row in connection.execute("SELECT * FROM schedules WHERE status='active' AND next_run_at IS NOT NULL AND next_run_at<=? ORDER BY next_run_at,id LIMIT ?",(self._stamp(now),limit)).fetchall())
        finally: connection.close()

    def list_incomplete_occurrences(self, *, limit: int = 100) -> tuple[Occurrence, ...]:
        if type(limit) is not int or not 1 <= limit <= 100: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        connection=self._read()
        if connection is None: return ()
        try: return tuple(self._occurrence(row) for row in connection.execute("SELECT * FROM schedule_occurrences WHERE status IN ('pending','running') ORDER BY scheduled_for,id LIMIT ?",(limit,)).fetchall())
        finally: connection.close()

    def claim_scheduled(self, schedule: Schedule, *, scheduled_for: datetime, next_run_at: datetime | None, next_status: ScheduleStatus, missed_count: int = 0, skipped_error: str | None = None) -> Occurrence:
        self._require_id(schedule.id); identifier=self._new_id(); now=self._now()
        occurrence_status=OccurrenceStatus.SKIPPED if skipped_error else OccurrenceStatus.PENDING
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("INSERT INTO schedule_occurrences(id,schedule_id,scheduled_for,trigger,status,run_id,error_code,missed_count,started_at,finished_at,created_at) VALUES(?,?,?,'scheduled',?,NULL,?,?,NULL,?,?)",(identifier,schedule.id,self._stamp(scheduled_for),occurrence_status.value,skipped_error,missed_count,self._stamp(now) if skipped_error else None,self._stamp(now)))
            except sqlite3.IntegrityError as error: raise ScheduleStoreError(ScheduleFailure.REVISION_CONFLICT) from error
            changed=connection.execute("UPDATE schedules SET status=?,next_run_at=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?",(next_status.value,self._stamp(next_run_at),self._stamp(now),schedule.id,schedule.revision)).rowcount
            if changed==0: self._raise_missing_or_conflict(connection,schedule.id)
            connection.commit(); return self._occurrence(connection.execute("SELECT * FROM schedule_occurrences WHERE id=?",(identifier,)).fetchone())

    def mark_occurrence_running(self, occurrence_id: str, run_id: str) -> Occurrence:
        self._require_id(occurrence_id);self._require_id(run_id)
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("UPDATE schedule_occurrences SET status='running',run_id=?,started_at=? WHERE id=? AND status='pending'",(run_id,self._stamp(self._now()),occurrence_id)).rowcount!=1: raise ScheduleStoreError(ScheduleFailure.REVISION_CONFLICT)
            connection.commit();return self._occurrence(connection.execute("SELECT * FROM schedule_occurrences WHERE id=?",(occurrence_id,)).fetchone())

    def finish_occurrence(self, occurrence_id: str, status: OccurrenceStatus, error_code: str | None = None) -> Occurrence:
        self._require_id(occurrence_id)
        if status not in {OccurrenceStatus.COMPLETED,OccurrenceStatus.FAILED,OccurrenceStatus.SKIPPED}: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("UPDATE schedule_occurrences SET status=?,error_code=?,finished_at=? WHERE id=? AND status IN ('pending','running')",(status.value,error_code,self._stamp(self._now()),occurrence_id)).rowcount!=1: raise ScheduleStoreError(ScheduleFailure.REVISION_CONFLICT)
            connection.commit();return self._occurrence(connection.execute("SELECT * FROM schedule_occurrences WHERE id=?",(occurrence_id,)).fetchone())

    def bind_conversation(self, schedule_id: str, conversation_id: str) -> Schedule:
        self._require_id(schedule_id);self._require_id(conversation_id)
        with self._write() as connection:
            connection.execute("BEGIN IMMEDIATE")
            schedule = self._require_row(connection, schedule_id)
            conversation = connection.execute(
                "SELECT workspace_id FROM conversations WHERE id=?",
                (conversation_id,),
            ).fetchone()
            if conversation is None:
                raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
            if conversation["workspace_id"] != schedule["workspace_id"]:
                raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
            changed=connection.execute("UPDATE schedules SET conversation_id=COALESCE(conversation_id,?),revision=revision+1,updated_at=? WHERE id=?",(conversation_id,self._stamp(self._now()),schedule_id)).rowcount
            if changed!=1: raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
            connection.commit();return self._schedule(self._require_row(connection,schedule_id))

    def has_running_occurrence(self, schedule_id: str) -> bool:
        self._require_id(schedule_id);connection=self._read()
        if connection is None:return False
        try:return connection.execute("SELECT 1 FROM schedule_occurrences WHERE schedule_id=? AND status='running' LIMIT 1",(schedule_id,)).fetchone() is not None
        finally:connection.close()

    @contextmanager
    def _write(self):
        SqliteConversationRepository(self._database_file).ensure_schema()
        connection = None
        try:
            connection=sqlite3.connect(self._database_file,timeout=5,isolation_level=None); connection.row_factory=sqlite3.Row; connection.execute("PRAGMA foreign_keys=ON"); connection.execute("PRAGMA busy_timeout=5000"); yield connection
        except sqlite3.Error as error: raise ScheduleStoreError(ScheduleFailure.DATABASE_UNAVAILABLE) from error
        finally:
            if connection is not None: connection.close()

    def _read(self):
        if not self._database_file.exists(): return None
        SqliteConversationRepository(self._database_file).ensure_schema()
        try:
            connection=sqlite3.connect(self._database_file,timeout=5,isolation_level=None); connection.row_factory=sqlite3.Row; connection.execute("PRAGMA query_only=ON"); return connection
        except sqlite3.Error as error: raise ScheduleStoreError(ScheduleFailure.DATABASE_UNAVAILABLE) from error

    def _draft_values(self, identifier, draft, status, next_run_at, now): return (identifier,draft.workspace_id) + self._editable_values(draft,next_run_at,now)[1:14] + (status.value,self._stamp(next_run_at),self._stamp(now),self._stamp(now))
    def _editable_values(self,draft,next_run_at,now):
        c=draft.cadence;p=draft.profile
        return (draft.workspace_id,draft.name.strip(),draft.prompt,c.type.value,self._stamp(c.run_at),c.local_time.isoformat(timespec="minutes") if c.local_time else None,json.dumps(c.weekdays,separators=(",",":")) if c.weekdays else None,draft.time_zone,p.provider_id,p.model_id,p.response_mode,p.context_budget,p.output_budget,p.output_continuation,self._stamp(next_run_at),self._stamp(now))

    def _validate_draft(self,draft):
        if not isinstance(draft,ScheduleDraft) or not 1<=len(draft.name.strip())<=120 or not 1<=len(draft.prompt)<=32768: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        self._require_id(draft.workspace_id)
        c=draft.cadence
        if c.type is CadenceType.ONCE and (c.run_at is None or c.run_at.tzinfo is None or c.local_time is not None or c.weekdays): raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        if c.type is CadenceType.DAILY and (c.run_at is not None or c.local_time is None or c.weekdays): raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        if c.type is CadenceType.WEEKLY and (c.run_at is not None or c.local_time is None or not c.weekdays or tuple(sorted(set(c.weekdays)))!=c.weekdays): raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
    def _require_row(self,c,id):
        row=c.execute("SELECT * FROM schedules WHERE id=?",(id,)).fetchone()
        if row is None: raise ScheduleStoreError(ScheduleFailure.NOT_FOUND)
        return row
    def _raise_missing_or_conflict(self,c,id): raise ScheduleStoreError(ScheduleFailure.REVISION_CONFLICT if c.execute("SELECT 1 FROM schedules WHERE id=?",(id,)).fetchone() else ScheduleFailure.NOT_FOUND)
    def _schedule(self,r):
        cadence=Cadence(CadenceType(r["cadence_type"]),self._time(r["run_at"]),time.fromisoformat(r["local_time"]) if r["local_time"] else None,tuple(json.loads(r["weekdays_json"])) if r["weekdays_json"] else ())
        profile=ExecutionProfile(r["provider_id"],r["model_id"],r["response_mode"],r["context_budget"],r["output_budget"],r["output_continuation"])
        return Schedule(r["id"],r["name"],r["prompt"],cadence,r["time_zone"],profile,ScheduleStatus(r["status"]),r["conversation_id"],self._time(r["next_run_at"]),r["revision"],self._time(r["created_at"]),self._time(r["updated_at"]),r["workspace_id"])
    def _occurrence(self,r): return Occurrence(r["id"],r["schedule_id"],self._time(r["scheduled_for"]),OccurrenceTrigger(r["trigger"]),OccurrenceStatus(r["status"]),r["run_id"],r["error_code"],r["missed_count"],self._time(r["started_at"]),self._time(r["finished_at"]),self._time(r["created_at"]))
    def _now(self):
        value=self._clock()
        if value.tzinfo is None: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
        return value.astimezone(UTC)
    def _new_id(self):
        value=self._identifier_factory();self._require_id(value);return value
    @staticmethod
    def _require_id(value):
        try: parsed=UUID(str(value))
        except ValueError: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST) from None
        if str(parsed)!=value: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
    @staticmethod
    def _require_revision(value):
        if type(value) is not int or value<1: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
    @staticmethod
    def _stamp(value): return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00","Z")
    @staticmethod
    def _time(value): return None if value is None else datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(UTC)
    @staticmethod
    def _encode(stamp,identifier): return base64.urlsafe_b64encode(json.dumps([stamp,identifier],separators=(",",":")).encode()).decode().rstrip("=")
    @staticmethod
    def _decode(value):
        try:
            raw=json.loads(base64.urlsafe_b64decode(value+"="*(-len(value)%4))); stamp,identifier=raw
            if type(stamp)is not str or type(identifier)is not str: raise ValueError
            return stamp,identifier
        except Exception: raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST) from None
