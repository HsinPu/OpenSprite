"""Transactional step persistence, sharing the conversation writer and lock."""
from __future__ import annotations

import sqlite3
from .models import MAX_ASSISTANT_CHARS, RunEventType, RunStep, StoreFailure
from .repository import ConversationStoreError
from .step_events import STEP_ERROR_CODES


class SqliteRunSteps:
    def start_step(self, run_id, *, label, channel, retry_of=None):
        self._require_identifier(run_id)
        if not isinstance(label, str) or not 1 <= len(label) <= 64 or channel not in {"draft", "answer"}:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if retry_of is not None:
            self._require_identifier(retry_of)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                run = self._require_run_row(connection, run_id)
                if run["status"] != "running":
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                if retry_of is not None and connection.execute(
                        "SELECT 1 FROM run_steps WHERE id=? AND run_id=?", (retry_of, run_id)).fetchone() is None:
                    raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
                sequence = connection.execute("SELECT COALESCE(MAX(sequence), 0)+1 FROM run_steps WHERE run_id=?", (run_id,)).fetchone()[0]
                step_id, now = self._new_identifier(), self._timestamp(self._now())
                connection.execute(
                    "INSERT INTO run_steps(id,run_id,sequence,label,channel,status,retry_of,created_at) VALUES(?,?,?,?,?,'running',?,?)",
                    (step_id, run_id, sequence, label, channel, retry_of, now))
                self._append_event(connection, run_id, run["conversation_id"], RunEventType.STEP_STARTED,
                                   {"stepId": step_id, "sequence": sequence, "label": label, "channel": channel}, self._now())
                connection.commit()
                self._signal_run_event(run_id)
                return self._step(connection.execute("SELECT * FROM run_steps WHERE id=?", (step_id,)).fetchone())
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from error
            finally:
                connection.close()

    def append_step_delta(self, step_id, text):
        self._require_identifier(step_id)
        if not isinstance(text, str) or not text or len(text) > 4096:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                step = connection.execute("SELECT * FROM run_steps WHERE id=?", (step_id,)).fetchone()
                if step is None:
                    raise ConversationStoreError(StoreFailure.NOT_FOUND)
                run = self._require_run_row(connection, step["run_id"])
                if step["status"] != "running" or run["status"] not in {"running", "cancelling"}:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                if len(step["text"]) + len(text) > MAX_ASSISTANT_CHARS:
                    raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
                connection.execute("UPDATE run_steps SET text=text || ? WHERE id=?", (text, step_id))
                if step["channel"] == "answer":
                    if len(run["partial_text"]) + len(text) > MAX_ASSISTANT_CHARS:
                        raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
                    connection.execute("UPDATE runs SET partial_text=partial_text || ? WHERE id=?", (text, step["run_id"]))
                    self._append_event(connection, step["run_id"], run["conversation_id"], RunEventType.ASSISTANT_DELTA, {"text": text}, self._now())
                connection.commit()
                self._signal_run_event(step["run_id"])
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from error
            finally:
                connection.close()

    def finish_step(self, step_id, *, status, finish_reason=None, error_code=None,
                    input_tokens=None, output_tokens=None):
        self._require_identifier(step_id)
        if status not in {"completed", "failed", "cancelled"} or finish_reason not in {None, "final", "output_limit"}:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if error_code is not None and error_code not in STEP_ERROR_CODES:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if any(value is not None and (type(value) is not int or not 0 <= value <= 2**53-1)
               for value in (input_tokens, output_tokens)):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                step = connection.execute("SELECT * FROM run_steps WHERE id=?", (step_id,)).fetchone()
                if step is None:
                    raise ConversationStoreError(StoreFailure.NOT_FOUND)
                run = self._require_run_row(connection, step["run_id"])
                if step["status"] != "running" or run["status"] not in {"running", "cancelling"}:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                connection.execute(
                    "UPDATE run_steps SET status=?,finish_reason=?,error_code=?,input_tokens=?,output_tokens=?,finished_at=? WHERE id=?",
                    (status, finish_reason, error_code, input_tokens, output_tokens, self._timestamp(self._now()), step_id))
                self._append_event(connection, step["run_id"], run["conversation_id"], RunEventType.STEP_COMPLETED,
                    {"stepId": step_id, "status": status, "finishReason": finish_reason, "errorCode": error_code,
                     "inputTokens": input_tokens, "outputTokens": output_tokens}, self._now())
                connection.commit()
                self._signal_run_event(step["run_id"])
                return self._step(connection.execute("SELECT * FROM run_steps WHERE id=?", (step_id,)).fetchone())
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from error
            finally:
                connection.close()

    def list_run_steps(self, run_id, *, after_sequence=0, limit=100):
        self._require_identifier(run_id)
        if type(after_sequence) is not int or not 0 <= after_sequence <= 2**53-1 or type(limit) is not int or not 1 <= limit <= 101:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return ()
            try:
                self._require_run_row(connection, run_id)
                return tuple(self._step(row) for row in connection.execute(
                    "SELECT * FROM run_steps WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                    (run_id, after_sequence, limit)).fetchall())
            except ConversationStoreError:
                raise
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from error
            finally:
                connection.close()

    @staticmethod
    def _step(row):
        from .sqlite_repository import SqliteConversationRepository
        parse = SqliteConversationRepository._parse_timestamp
        return RunStep(row["id"], row["run_id"], row["sequence"], row["label"], row["channel"],
                       row["status"], row["text"], row["finish_reason"], row["error_code"],
                       row["input_tokens"], row["output_tokens"], row["retry_of"], parse(row["created_at"]),
                       None if row["finished_at"] is None else parse(row["finished_at"]))
