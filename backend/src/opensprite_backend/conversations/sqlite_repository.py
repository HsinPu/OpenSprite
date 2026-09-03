"""Strict SQLite implementation of the minimal conversation persistence model."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from .models import (
    CompletedRun,
    CompletionReason,
    ContextBudget,
    ConversationCompaction,
    ConversationPage,
    ConversationSummary,
    Message,
    MessagePage,
    OutputBudget,
    OutputContinuation,
    MAX_ASSISTANT_CHARS,
    ProviderId,
    PublicRunError,
    ResponseMode,
    RunEvent,
    RunEventType,
    RunSnapshot,
    RunStatus,
    StartRunResult,
    StoreFailure,
)
from .repository import ConversationStoreError
from .event_notifier import RunEventNotifier


_SCHEMA_VERSION = 11
_ACTIVE_STATUSES = (
    RunStatus.QUEUED.value,
    RunStatus.RUNNING.value,
    RunStatus.CANCELLING.value,
)
_TERMINAL_EVENT_TYPES = {
    RunEventType.RUN_STARTED,
    RunEventType.ASSISTANT_DELTA,
    RunEventType.RUN_COMPLETED,
    RunEventType.RUN_FAILED,
    RunEventType.RUN_CANCELLED,
    RunEventType.RUN_INTERRUPTED,
}
_PROVIDER_IDS = {"openai", "anthropic", "openrouter"}
_RESPONSE_MODES = {"default", "fast", "balanced", "deep"}
_CONTEXT_BUDGETS = {"auto", "32k", "64k", "128k", "256k", "max"}
_OUTPUT_BUDGETS = {"auto", "8k", "16k", "32k", "64k", "max"}
_OUTPUT_CONTINUATIONS = {"off", "1", "2", "3", "5", "10", "20", "50", "unlimited"}
_PUBLIC_ERROR_CODES = {
    "invalid_request",
    "not_found",
    "run_busy",
    "run_not_active",
    "model_not_selected",
    "provider_not_connected",
    "invalid_credentials",
    "provider_rate_limited",
    "provider_timeout",
    "provider_unreachable",
    "credential_store_unavailable",
    "settings_store_unavailable",
    "database_unavailable",
    "agent_limit_reached",
    "context_limit_exceeded",
    "context_preparation_failed",
    "tool_failure",
    "invalid_provider_response",
    "internal_error",
}
_MAX_EVENT_JSON_BYTES = 65536
_MAX_ASSISTANT_DELTA_CHARS = 16384
_ASSISTANT_DELTA_JSON_PREFIX_BYTES = len(b'{"text":"')
_ASSISTANT_DELTA_JSON_SUFFIX_BYTES = len(b'"}')


_SCHEMA_SQL = """
BEGIN IMMEDIATE;
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
    latest_message_preview TEXT CHECK(
        latest_message_preview IS NULL OR
        length(latest_message_preview) BETWEEN 1 AND 280
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK(length(content) BETWEEN 1 AND 1048576),
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    created_at TEXT NOT NULL,
    UNIQUE(conversation_id, sequence)
) STRICT;

CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    client_request_id TEXT NOT NULL UNIQUE,
    request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint) = 64),
    user_message_id TEXT NOT NULL REFERENCES messages(id),
    assistant_message_id TEXT,
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    output_continuation TEXT NOT NULL CHECK(output_continuation IN ('off', '1', '2', '3', '5', '10', '20', '50', 'unlimited')),
    log_full_prompts INTEGER NOT NULL CHECK(log_full_prompts IN (0, 1)),
    source TEXT NOT NULL DEFAULT 'user' CHECK(source IN ('user', 'schedule')),
    occurrence_id TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled', 'interrupted'
    )),
    completion_reason TEXT CHECK(completion_reason IN ('stop', 'output_limit', 'context_limit')),
    error_code TEXT,
    error_message TEXT,
    error_retryable INTEGER CHECK(error_retryable IN (0, 1)),
    partial_text TEXT NOT NULL DEFAULT '' CHECK(length(partial_text) <= 1048576),
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    CHECK(
        (error_code IS NULL AND error_message IS NULL AND error_retryable IS NULL) OR
        (error_code IS NOT NULL AND error_message IS NOT NULL AND error_retryable IS NOT NULL)
    )
) STRICT;

CREATE TABLE conversation_compactions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    covers_through_sequence INTEGER NOT NULL CHECK(covers_through_sequence >= 1),
    summary TEXT NOT NULL CHECK(length(summary) BETWEEN 1 AND 262144),
    summary_version INTEGER NOT NULL CHECK(summary_version = 1),
    source_hash TEXT NOT NULL CHECK(length(source_hash) = 64),
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    input_tokens INTEGER NOT NULL CHECK(input_tokens >= 0),
    output_tokens INTEGER NOT NULL CHECK(output_tokens >= 0),
    created_at TEXT NOT NULL,
    UNIQUE(conversation_id, covers_through_sequence)
) STRICT;

CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'context.compaction.started', 'model.started',
        'response.continuation.started',
        'assistant.delta', 'tool.approval_requested', 'tool.approval_decided',
        'tool.started', 'tool.completed', 'tool.failed',
        'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
    )),
    payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
) STRICT;

CREATE UNIQUE INDEX one_active_run_per_conversation
ON runs(conversation_id)
WHERE status IN ('queued', 'running', 'cancelling');

CREATE INDEX conversations_by_updated
ON conversations(updated_at DESC, id DESC);

CREATE INDEX messages_by_conversation_sequence
ON messages(conversation_id, sequence DESC);

CREATE INDEX compactions_by_conversation_coverage
ON conversation_compactions(conversation_id, covers_through_sequence DESC);

CREATE TABLE schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
    prompt TEXT NOT NULL CHECK(length(prompt) BETWEEN 1 AND 32768),
    cadence_type TEXT NOT NULL CHECK(cadence_type IN ('once', 'daily', 'weekly')),
    run_at TEXT,
    local_time TEXT,
    weekdays_json TEXT,
    time_zone TEXT NOT NULL CHECK(length(time_zone) BETWEEN 1 AND 128),
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    output_continuation TEXT NOT NULL CHECK(output_continuation IN ('off', '1', '2', '3', '5', '10', '20', '50', 'unlimited')),
    status TEXT NOT NULL CHECK(status IN ('active', 'paused', 'completed')),
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    next_run_at TEXT,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(
      (cadence_type = 'once' AND run_at IS NOT NULL AND local_time IS NULL AND weekdays_json IS NULL) OR
      (cadence_type = 'daily' AND run_at IS NULL AND local_time IS NOT NULL AND weekdays_json IS NULL) OR
      (cadence_type = 'weekly' AND run_at IS NULL AND local_time IS NOT NULL AND weekdays_json IS NOT NULL)
    )
) STRICT;

CREATE TABLE schedule_occurrences (
    id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    scheduled_for TEXT NOT NULL,
    trigger TEXT NOT NULL CHECK(trigger IN ('scheduled', 'manual')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    error_code TEXT,
    missed_count INTEGER NOT NULL DEFAULT 0 CHECK(missed_count >= 0),
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(schedule_id, scheduled_for, trigger)
) STRICT;

CREATE INDEX schedules_by_next_run ON schedules(status, next_run_at, id);
CREATE INDEX schedule_occurrences_by_schedule ON schedule_occurrences(schedule_id, scheduled_for DESC, id DESC);
CREATE UNIQUE INDEX runs_by_occurrence ON runs(occurrence_id) WHERE occurrence_id IS NOT NULL;

PRAGMA user_version = 11;
COMMIT;
"""

_MIGRATE_V1_TO_V2_SQL = """
BEGIN IMMEDIATE;
ALTER TABLE runs ADD COLUMN context_budget TEXT NOT NULL DEFAULT 'auto'
CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max'));
CREATE TABLE conversation_compactions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    covers_through_sequence INTEGER NOT NULL CHECK(covers_through_sequence >= 1),
    summary TEXT NOT NULL CHECK(length(summary) BETWEEN 1 AND 262144),
    summary_version INTEGER NOT NULL CHECK(summary_version = 1),
    source_hash TEXT NOT NULL CHECK(length(source_hash) = 64),
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    input_tokens INTEGER NOT NULL CHECK(input_tokens >= 0),
    output_tokens INTEGER NOT NULL CHECK(output_tokens >= 0),
    created_at TEXT NOT NULL,
    UNIQUE(conversation_id, covers_through_sequence)
) STRICT;
CREATE INDEX compactions_by_conversation_coverage
ON conversation_compactions(conversation_id, covers_through_sequence DESC);
PRAGMA user_version = 2;
COMMIT;
"""

_MIGRATE_V2_TO_V3_SQL = """
BEGIN IMMEDIATE;
ALTER TABLE run_events RENAME TO run_events_v2;
CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'context.compaction.started', 'model.started',
        'assistant.delta', 'tool.started', 'tool.completed', 'tool.failed',
        'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
    )),
    payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
) STRICT;
INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
SELECT run_id, sequence, type, payload_json, created_at
FROM run_events_v2;
DROP TABLE run_events_v2;
PRAGMA user_version = 3;
COMMIT;
"""

_MIGRATE_V3_TO_V4_SQL = """
BEGIN IMMEDIATE;
ALTER TABLE runs ADD COLUMN completion_reason TEXT
CHECK(completion_reason IN ('stop', 'output_limit'));
UPDATE runs SET completion_reason = 'stop' WHERE status = 'completed';
UPDATE run_events
SET payload_json = json_set(payload_json, '$.completionReason', 'stop')
WHERE type = 'run.completed';
PRAGMA user_version = 4;
COMMIT;
"""

_MIGRATE_V4_TO_V5_SQL = """
BEGIN IMMEDIATE;
ALTER TABLE runs ADD COLUMN output_budget TEXT NOT NULL DEFAULT 'auto'
CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max'));
UPDATE run_events
SET payload_json = json_set(payload_json, '$.maxOutputTokens', 8192)
WHERE type = 'model.started';
PRAGMA user_version = 5;
COMMIT;
"""

_MIGRATE_V5_TO_V6_SQL = """
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
DROP INDEX one_active_run_per_conversation;
ALTER TABLE run_events RENAME TO run_events_v5;
ALTER TABLE runs RENAME TO runs_v5;
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    client_request_id TEXT NOT NULL UNIQUE,
    request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint) = 64),
    user_message_id TEXT NOT NULL REFERENCES messages(id),
    assistant_message_id TEXT,
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    auto_continue_output INTEGER NOT NULL CHECK(auto_continue_output IN (0, 1)),
    status TEXT NOT NULL CHECK(status IN (
        'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled', 'interrupted'
    )),
    completion_reason TEXT CHECK(completion_reason IN ('stop', 'output_limit', 'context_limit')),
    error_code TEXT,
    error_message TEXT,
    error_retryable INTEGER CHECK(error_retryable IN (0, 1)),
    partial_text TEXT NOT NULL DEFAULT '' CHECK(length(partial_text) <= 1048576),
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    CHECK(
        (error_code IS NULL AND error_message IS NULL AND error_retryable IS NULL) OR
        (error_code IS NOT NULL AND error_message IS NOT NULL AND error_retryable IS NOT NULL)
    )
) STRICT;
INSERT INTO runs(
    id, conversation_id, client_request_id, request_fingerprint,
    user_message_id, assistant_message_id, provider_id, model_id,
    response_mode, context_budget, output_budget, auto_continue_output,
    status, completion_reason, error_code, error_message, error_retryable,
    partial_text, created_at, started_at, finished_at
)
SELECT
    id, conversation_id, client_request_id, request_fingerprint,
    user_message_id, assistant_message_id, provider_id, model_id,
    response_mode, context_budget, output_budget, 1,
    status, completion_reason, error_code, error_message, error_retryable,
    partial_text, created_at, started_at, finished_at
FROM runs_v5;
CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'context.compaction.started', 'model.started',
        'response.continuation.started',
        'assistant.delta', 'tool.started', 'tool.completed', 'tool.failed',
        'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
    )),
    payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
) STRICT;
INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
SELECT run_id, sequence, type, payload_json, created_at
FROM run_events_v5;
DROP TABLE run_events_v5;
DROP TABLE runs_v5;
CREATE UNIQUE INDEX one_active_run_per_conversation
ON runs(conversation_id)
WHERE status IN ('queued', 'running', 'cancelling');
PRAGMA user_version = 6;
COMMIT;
PRAGMA foreign_keys = ON;
"""

_MIGRATE_V6_TO_V7_SQL = """
BEGIN IMMEDIATE;
ALTER TABLE runs ADD COLUMN log_full_prompts INTEGER NOT NULL DEFAULT 0
CHECK(log_full_prompts IN (0, 1));
PRAGMA user_version = 7;
COMMIT;
"""

_MIGRATE_V7_TO_V8_SQL = """
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
DROP INDEX one_active_run_per_conversation;
ALTER TABLE run_events RENAME TO run_events_v7;
ALTER TABLE runs RENAME TO runs_v7;
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    client_request_id TEXT NOT NULL UNIQUE,
    request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint) = 64),
    user_message_id TEXT NOT NULL REFERENCES messages(id),
    assistant_message_id TEXT,
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    output_continuation TEXT NOT NULL CHECK(output_continuation IN ('off', '1', '2', '3', '5', 'unlimited')),
    log_full_prompts INTEGER NOT NULL CHECK(log_full_prompts IN (0, 1)),
    status TEXT NOT NULL CHECK(status IN (
        'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled', 'interrupted'
    )),
    completion_reason TEXT CHECK(completion_reason IN ('stop', 'output_limit', 'context_limit')),
    error_code TEXT,
    error_message TEXT,
    error_retryable INTEGER CHECK(error_retryable IN (0, 1)),
    partial_text TEXT NOT NULL DEFAULT '' CHECK(length(partial_text) <= 1048576),
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    CHECK(
        (error_code IS NULL AND error_message IS NULL AND error_retryable IS NULL) OR
        (error_code IS NOT NULL AND error_message IS NOT NULL AND error_retryable IS NOT NULL)
    )
) STRICT;
INSERT INTO runs(
    id, conversation_id, client_request_id, request_fingerprint,
    user_message_id, assistant_message_id, provider_id, model_id,
    response_mode, context_budget, output_budget, output_continuation,
    log_full_prompts, status, completion_reason, error_code, error_message,
    error_retryable, partial_text, created_at, started_at, finished_at
)
SELECT
    id, conversation_id, client_request_id, request_fingerprint,
    user_message_id, assistant_message_id, provider_id, model_id,
    response_mode, context_budget, output_budget,
    CASE auto_continue_output WHEN 1 THEN '2' ELSE 'off' END,
    log_full_prompts, status, completion_reason, error_code, error_message,
    error_retryable, partial_text, created_at, started_at, finished_at
FROM runs_v7;
CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'context.compaction.started', 'model.started',
        'response.continuation.started',
        'assistant.delta', 'tool.started', 'tool.completed', 'tool.failed',
        'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
    )),
    payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
) STRICT;
INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
SELECT run_id, sequence, type, payload_json, created_at
FROM run_events_v7;
DROP TABLE run_events_v7;
DROP TABLE runs_v7;
CREATE UNIQUE INDEX one_active_run_per_conversation
ON runs(conversation_id)
WHERE status IN ('queued', 'running', 'cancelling');
PRAGMA user_version = 8;
COMMIT;
PRAGMA foreign_keys = ON;
"""

_MIGRATE_V8_TO_V9_SQL = """
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
ALTER TABLE run_events RENAME TO run_events_v8;
CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'context.compaction.started', 'model.started',
        'response.continuation.started',
        'assistant.delta', 'tool.approval_requested', 'tool.approval_decided',
        'tool.started', 'tool.completed', 'tool.failed',
        'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
    )),
    payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
) STRICT;
INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
SELECT run_id, sequence, type, payload_json, created_at
FROM run_events_v8;
DROP TABLE run_events_v8;
PRAGMA user_version = 9;
COMMIT;
PRAGMA foreign_keys = ON;
"""

_MIGRATE_V9_TO_V10_SQL = """
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
DROP INDEX one_active_run_per_conversation;
ALTER TABLE run_events RENAME TO run_events_v9;
ALTER TABLE runs RENAME TO runs_v9;
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    client_request_id TEXT NOT NULL UNIQUE,
    request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint) = 64),
    user_message_id TEXT NOT NULL REFERENCES messages(id),
    assistant_message_id TEXT,
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    output_continuation TEXT NOT NULL CHECK(output_continuation IN ('off', '1', '2', '3', '5', '10', '20', '50', 'unlimited')),
    log_full_prompts INTEGER NOT NULL CHECK(log_full_prompts IN (0, 1)),
    status TEXT NOT NULL CHECK(status IN (
        'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled', 'interrupted'
    )),
    completion_reason TEXT CHECK(completion_reason IN ('stop', 'output_limit', 'context_limit')),
    error_code TEXT,
    error_message TEXT,
    error_retryable INTEGER CHECK(error_retryable IN (0, 1)),
    partial_text TEXT NOT NULL DEFAULT '' CHECK(length(partial_text) <= 1048576),
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    CHECK(
        (error_code IS NULL AND error_message IS NULL AND error_retryable IS NULL) OR
        (error_code IS NOT NULL AND error_message IS NOT NULL AND error_retryable IS NOT NULL)
    )
) STRICT;
INSERT INTO runs(
    id, conversation_id, client_request_id, request_fingerprint,
    user_message_id, assistant_message_id, provider_id, model_id,
    response_mode, context_budget, output_budget, output_continuation,
    log_full_prompts, status, completion_reason, error_code, error_message,
    error_retryable, partial_text, created_at, started_at, finished_at
)
SELECT
    id, conversation_id, client_request_id, request_fingerprint,
    user_message_id, assistant_message_id, provider_id, model_id,
    response_mode, context_budget, output_budget, output_continuation,
    log_full_prompts, status, completion_reason, error_code, error_message,
    error_retryable, partial_text, created_at, started_at, finished_at
FROM runs_v9;
CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'context.compaction.started', 'model.started',
        'response.continuation.started',
        'assistant.delta', 'tool.approval_requested', 'tool.approval_decided',
        'tool.started', 'tool.completed', 'tool.failed',
        'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
    )),
    payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
) STRICT;
INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
SELECT run_id, sequence, type, payload_json, created_at FROM run_events_v9;
DROP TABLE run_events_v9;
DROP TABLE runs_v9;
CREATE UNIQUE INDEX one_active_run_per_conversation
ON runs(conversation_id)
WHERE status IN ('queued', 'running', 'cancelling');
PRAGMA user_version = 10;
COMMIT;
PRAGMA foreign_keys = ON;
"""

_MIGRATE_V10_TO_V11_SQL = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
    prompt TEXT NOT NULL CHECK(length(prompt) BETWEEN 1 AND 32768),
    cadence_type TEXT NOT NULL CHECK(cadence_type IN ('once', 'daily', 'weekly')),
    run_at TEXT, local_time TEXT, weekdays_json TEXT,
    time_zone TEXT NOT NULL CHECK(length(time_zone) BETWEEN 1 AND 128),
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    output_continuation TEXT NOT NULL CHECK(output_continuation IN ('off', '1', '2', '3', '5', '10', '20', '50', 'unlimited')),
    status TEXT NOT NULL CHECK(status IN ('active', 'paused', 'completed')),
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    next_run_at TEXT,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    CHECK((cadence_type='once' AND run_at IS NOT NULL AND local_time IS NULL AND weekdays_json IS NULL) OR (cadence_type='daily' AND run_at IS NULL AND local_time IS NOT NULL AND weekdays_json IS NULL) OR (cadence_type='weekly' AND run_at IS NULL AND local_time IS NOT NULL AND weekdays_json IS NOT NULL))
) STRICT;
CREATE TABLE IF NOT EXISTS schedule_occurrences (
    id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    scheduled_for TEXT NOT NULL,
    trigger TEXT NOT NULL CHECK(trigger IN ('scheduled', 'manual')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    error_code TEXT,
    missed_count INTEGER NOT NULL DEFAULT 0 CHECK(missed_count >= 0),
    started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL,
    UNIQUE(schedule_id, scheduled_for, trigger)
) STRICT;
CREATE INDEX IF NOT EXISTS schedules_by_next_run ON schedules(status, next_run_at, id);
CREATE INDEX IF NOT EXISTS schedule_occurrences_by_schedule ON schedule_occurrences(schedule_id, scheduled_for DESC, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS runs_by_occurrence ON runs(occurrence_id) WHERE occurrence_id IS NOT NULL;
PRAGMA user_version = 11;
COMMIT;
"""


class SqliteConversationRepository:
    """Own four chat tables below one explicit AppPaths database file."""

    def __init__(
        self,
        database_file: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
        identifier_factory: Callable[[], str] | None = None,
        event_notifier: RunEventNotifier | None = None,
    ) -> None:
        self._database_file = Path(database_file)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._identifier_factory = identifier_factory or (lambda: str(uuid4()))
        self._event_notifier = event_notifier
        self._lock = RLock()

    @property
    def database_file(self) -> Path:
        return self._database_file

    def ensure_schema(self) -> None:
        with self._lock:
            connection = self._open_write()
            connection.close()

    def list_conversations(
        self,
        *,
        limit: int,
        before: str | None,
    ) -> ConversationPage:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        cursor = self._decode_cursor(before) if before is not None else None
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return ConversationPage(items=(), next_cursor=None)
            try:
                if cursor is None:
                    rows = connection.execute(
                        """
                        SELECT * FROM conversations
                        ORDER BY updated_at DESC, id DESC
                        LIMIT ?
                        """,
                        (limit + 1,),
                    ).fetchall()
                else:
                    updated_at, identifier = cursor
                    rows = connection.execute(
                        """
                        SELECT * FROM conversations
                        WHERE updated_at < ? OR (updated_at = ? AND id < ?)
                        ORDER BY updated_at DESC, id DESC
                        LIMIT ?
                        """,
                        (updated_at, updated_at, identifier, limit + 1),
                    ).fetchall()
                has_more = len(rows) > limit
                selected = rows[:limit]
                items = tuple(self._conversation(row) for row in selected)
                next_cursor = (
                    self._encode_cursor(selected[-1]["updated_at"], selected[-1]["id"])
                    if has_more and selected
                    else None
                )
                return ConversationPage(items=items, next_cursor=next_cursor)
            except ConversationStoreError:
                raise
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def get_conversation(self, conversation_id: str) -> ConversationSummary | None:
        self._require_identifier(conversation_id)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return None
            try:
                row = connection.execute(
                    "SELECT * FROM conversations WHERE id = ?",
                    (conversation_id,),
                ).fetchone()
                return None if row is None else self._conversation(row)
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ) -> MessagePage:
        self._require_identifier(conversation_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if before_sequence is not None and (
            not isinstance(before_sequence, int)
            or isinstance(before_sequence, bool)
            or before_sequence < 1
        ):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return MessagePage(items=(), next_before_sequence=None)
            try:
                if before_sequence is None:
                    rows = connection.execute(
                        """
                        SELECT * FROM messages
                        WHERE conversation_id = ?
                        ORDER BY sequence DESC
                        LIMIT ?
                        """,
                        (conversation_id, limit + 1),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT * FROM messages
                        WHERE conversation_id = ? AND sequence < ?
                        ORDER BY sequence DESC
                        LIMIT ?
                        """,
                        (conversation_id, before_sequence, limit + 1),
                    ).fetchall()
                has_more = len(rows) > limit
                selected = rows[:limit]
                selected.reverse()
                items = tuple(self._message(row) for row in selected)
                next_before = items[0].sequence if has_more and items else None
                return MessagePage(
                    items=items,
                    next_before_sequence=next_before,
                )
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def get_latest_compaction(
        self,
        conversation_id: str,
    ) -> ConversationCompaction | None:
        self._require_identifier(conversation_id)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return None
            try:
                row = connection.execute(
                    """
                    SELECT * FROM conversation_compactions
                    WHERE conversation_id = ?
                    ORDER BY covers_through_sequence DESC
                    LIMIT 1
                    """,
                    (conversation_id,),
                ).fetchone()
                return None if row is None else self._compaction(row)
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def list_messages_after(
        self,
        conversation_id: str,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[Message, ...]:
        self._require_identifier(conversation_id)
        if (
            not isinstance(after_sequence, int)
            or isinstance(after_sequence, bool)
            or after_sequence < 0
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
        ):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return ()
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM messages
                    WHERE conversation_id = ? AND sequence > ?
                    ORDER BY sequence ASC
                    LIMIT ?
                    """,
                    (conversation_id, after_sequence, limit),
                ).fetchall()
                return tuple(self._message(row) for row in rows)
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def append_compaction(
        self,
        *,
        conversation_id: str,
        covers_through_sequence: int,
        summary: str,
        source_hash: str,
        provider_id: ProviderId,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> ConversationCompaction:
        self._require_identifier(conversation_id)
        normalized_summary = self._require_text(summary, maximum=262_144)
        normalized_model = self._require_text(model_id, maximum=256)
        if (
            not isinstance(covers_through_sequence, int)
            or isinstance(covers_through_sequence, bool)
            or covers_through_sequence < 1
            or not isinstance(source_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None
            or provider_id not in _PROVIDER_IDS
            or not isinstance(input_tokens, int)
            or isinstance(input_tokens, bool)
            or input_tokens < 0
            or not isinstance(output_tokens, int)
            or isinstance(output_tokens, bool)
            or output_tokens < 0
        ):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                conversation = connection.execute(
                    "SELECT 1 FROM conversations WHERE id = ?",
                    (conversation_id,),
                ).fetchone()
                covered_message = connection.execute(
                    """
                    SELECT 1 FROM messages
                    WHERE conversation_id = ? AND sequence = ?
                    """,
                    (conversation_id, covers_through_sequence),
                ).fetchone()
                if conversation is None or covered_message is None:
                    raise ConversationStoreError(StoreFailure.NOT_FOUND)
                latest = connection.execute(
                    """
                    SELECT MAX(covers_through_sequence)
                    FROM conversation_compactions
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()[0]
                if latest is not None and covers_through_sequence <= int(latest):
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                item = ConversationCompaction(
                    id=self._new_identifier(),
                    conversation_id=conversation_id,
                    covers_through_sequence=covers_through_sequence,
                    summary=normalized_summary,
                    summary_version=1,
                    source_hash=source_hash,
                    provider_id=provider_id,
                    model_id=normalized_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    created_at=self._now(),
                )
                connection.execute(
                    """
                    INSERT INTO conversation_compactions(
                        id, conversation_id, covers_through_sequence, summary,
                        summary_version, source_hash, provider_id, model_id,
                        input_tokens, output_tokens, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        item.conversation_id,
                        item.covers_through_sequence,
                        item.summary,
                        item.summary_version,
                        item.source_hash,
                        item.provider_id,
                        item.model_id,
                        item.input_tokens,
                        item.output_tokens,
                        self._timestamp(item.created_at),
                    ),
                )
                connection.commit()
                return item
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def get_run(self, run_id: str) -> RunSnapshot | None:
        self._require_identifier(run_id)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return None
            try:
                row = connection.execute(
                    "SELECT * FROM runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                return None if row is None else self._run(row)
            except (sqlite3.Error, TypeError, ValueError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def start_run(
        self,
        *,
        conversation_id: str | None,
        client_request_id: str,
        message: str,
        provider_id: ProviderId,
        model_id: str,
        response_mode: ResponseMode,
        context_budget: ContextBudget = "auto",
        output_budget: OutputBudget = "auto",
        output_continuation: OutputContinuation = "5",
        log_full_prompts: bool = False,
    ) -> StartRunResult:
        if conversation_id is not None:
            self._require_identifier(conversation_id)
        self._require_identifier(client_request_id)
        normalized_message = self._require_text(message, maximum=32768)
        if provider_id not in _PROVIDER_IDS:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        normalized_model = self._require_text(model_id, maximum=256)
        if response_mode not in _RESPONSE_MODES:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if context_budget not in _CONTEXT_BUDGETS:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if output_budget not in _OUTPUT_BUDGETS:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if output_continuation not in _OUTPUT_CONTINUATIONS:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        if not isinstance(log_full_prompts, bool):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        request_fingerprint = self._request_fingerprint(
            conversation_id,
            normalized_message,
        )
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT * FROM runs WHERE client_request_id = ?",
                    (client_request_id,),
                ).fetchone()
                if existing is not None:
                    if existing["request_fingerprint"] != request_fingerprint:
                        raise ConversationStoreError(
                            StoreFailure.IDEMPOTENCY_CONFLICT
                        )
                    conversation_row = connection.execute(
                        "SELECT * FROM conversations WHERE id = ?",
                        (existing["conversation_id"],),
                    ).fetchone()
                    if conversation_row is None:
                        raise ConversationStoreError(
                            StoreFailure.DATABASE_UNAVAILABLE
                        )
                    connection.commit()
                    return StartRunResult(
                        conversation=self._conversation(conversation_row),
                        run=self._run(existing),
                        replayed=True,
                    )

                now = self._now()
                now_text = self._timestamp(now)
                resolved_conversation_id = conversation_id
                if resolved_conversation_id is None:
                    resolved_conversation_id = self._new_identifier()
                    title = self._display_text(normalized_message, maximum=160)
                    preview = self._display_text(normalized_message, maximum=280)
                    connection.execute(
                        """
                        INSERT INTO conversations(
                            id, title, latest_message_preview, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            resolved_conversation_id,
                            title,
                            preview,
                            now_text,
                            now_text,
                        ),
                    )
                else:
                    conversation_row = connection.execute(
                        "SELECT * FROM conversations WHERE id = ?",
                        (resolved_conversation_id,),
                    ).fetchone()
                    if conversation_row is None:
                        raise ConversationStoreError(StoreFailure.NOT_FOUND)

                active = connection.execute(
                    """
                    SELECT 1 FROM runs
                    WHERE conversation_id = ? AND status IN (?, ?, ?)
                    LIMIT 1
                    """,
                    (resolved_conversation_id, *_ACTIVE_STATUSES),
                ).fetchone()
                if active is not None:
                    raise ConversationStoreError(StoreFailure.RUN_BUSY)

                sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM messages WHERE conversation_id = ?
                        """,
                        (resolved_conversation_id,),
                    ).fetchone()[0]
                )
                run_id = self._new_identifier()
                message_id = self._new_identifier()
                connection.execute(
                    """
                    INSERT INTO messages(
                        id, conversation_id, run_id, role, content, sequence, created_at
                    ) VALUES (?, ?, ?, 'user', ?, ?, ?)
                    """,
                    (
                        message_id,
                        resolved_conversation_id,
                        run_id,
                        normalized_message,
                        sequence,
                        now_text,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO runs(
                        id, conversation_id, client_request_id, request_fingerprint,
                        user_message_id, assistant_message_id, provider_id, model_id,
                        response_mode, context_budget, output_budget, output_continuation,
                        log_full_prompts,
                        status, partial_text, created_at,
                        started_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 'queued', '', ?, NULL, NULL)
                    """,
                    (
                        run_id,
                        resolved_conversation_id,
                        client_request_id,
                        request_fingerprint,
                        message_id,
                        provider_id,
                        normalized_model,
                        response_mode,
                        context_budget,
                        output_budget,
                        output_continuation,
                        int(log_full_prompts),
                        now_text,
                    ),
                )
                connection.execute(
                    """
                    UPDATE conversations
                    SET latest_message_preview = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        self._display_text(normalized_message, maximum=280),
                        now_text,
                        resolved_conversation_id,
                    ),
                )
                conversation_row = connection.execute(
                    "SELECT * FROM conversations WHERE id = ?",
                    (resolved_conversation_id,),
                ).fetchone()
                run_row = connection.execute(
                    "SELECT * FROM runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                if conversation_row is None or run_row is None:
                    raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
                connection.commit()
                return StartRunResult(
                    conversation=self._conversation(conversation_row),
                    run=self._run(run_row),
                    replayed=False,
                )
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def mark_run_started(self, run_id: str) -> RunSnapshot:
        self._require_identifier(run_id)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                if row["status"] != RunStatus.QUEUED.value:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                now = self._now()
                connection.execute(
                    "UPDATE runs SET status = 'running', started_at = ? WHERE id = ?",
                    (self._timestamp(now), run_id),
                )
                self._append_event(
                    connection,
                    run_id,
                    row["conversation_id"],
                    RunEventType.RUN_STARTED,
                    {},
                    now,
                )
                result = self._require_run_row(connection, run_id)
                connection.commit()
                snapshot = self._run(result)
                self._signal_run_event(run_id)
                return snapshot
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def append_run_event(
        self,
        run_id: str,
        event_type: RunEventType,
        data: Mapping[str, object],
    ) -> RunEvent:
        self._require_identifier(run_id)
        if event_type in _TERMINAL_EVENT_TYPES:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                if row["status"] not in {
                    RunStatus.RUNNING.value,
                    RunStatus.CANCELLING.value,
                }:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                event = self._append_event(
                    connection,
                    run_id,
                    row["conversation_id"],
                    event_type,
                    data,
                    self._now(),
                )
                connection.commit()
                self._signal_run_event(run_id)
                return event
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def append_assistant_delta(self, run_id: str, text: str) -> RunEvent:
        self._require_identifier(run_id)
        if (
            not isinstance(text, str)
            or not text
            or len(text) > _MAX_ASSISTANT_DELTA_CHARS
        ):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        chunks = self._split_assistant_delta(text)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                if row["status"] != RunStatus.RUNNING.value:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                partial_text = row["partial_text"] + text
                if len(partial_text) > MAX_ASSISTANT_CHARS:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                connection.execute(
                    "UPDATE runs SET partial_text = ? WHERE id = ?",
                    (partial_text, run_id),
                )
                created_at = self._now()
                event = self._append_event(
                    connection,
                    run_id,
                    row["conversation_id"],
                    RunEventType.ASSISTANT_DELTA,
                    {"text": chunks[0]},
                    created_at,
                )
                for chunk in chunks[1:]:
                    event = self._append_event(
                        connection,
                        run_id,
                        row["conversation_id"],
                        RunEventType.ASSISTANT_DELTA,
                        {"text": chunk},
                        created_at,
                    )
                connection.commit()
                self._signal_run_event(run_id)
                return event
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    @staticmethod
    def _split_assistant_delta(text: str) -> tuple[str, ...]:
        max_content_bytes = (
            _MAX_EVENT_JSON_BYTES
            - _ASSISTANT_DELTA_JSON_PREFIX_BYTES
            - _ASSISTANT_DELTA_JSON_SUFFIX_BYTES
        )
        chunks: list[str] = []
        current: list[str] = []
        current_bytes = 0
        for character in text:
            encoded = json.dumps(
                character,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            character_bytes = len(encoded) - 2
            if character_bytes > max_content_bytes:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if current and current_bytes + character_bytes > max_content_bytes:
                chunks.append("".join(current))
                current = []
                current_bytes = 0
            current.append(character)
            current_bytes += character_bytes
        if current:
            chunks.append("".join(current))
        return tuple(chunks)

    def complete_run(
        self,
        run_id: str,
        assistant_text: str,
        completion_reason: CompletionReason = CompletionReason.STOP,
    ) -> CompletedRun:
        self._require_identifier(run_id)
        if not isinstance(completion_reason, CompletionReason):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        normalized_text = self._require_text(
            assistant_text,
            maximum=MAX_ASSISTANT_CHARS,
        )
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                if row["status"] != RunStatus.RUNNING.value:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                now = self._now()
                now_text = self._timestamp(now)
                sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM messages WHERE conversation_id = ?
                        """,
                        (row["conversation_id"],),
                    ).fetchone()[0]
                )
                message_id = self._new_identifier()
                connection.execute(
                    """
                    INSERT INTO messages(
                        id, conversation_id, run_id, role, content, sequence, created_at
                    ) VALUES (?, ?, ?, 'assistant', ?, ?, ?)
                    """,
                    (
                        message_id,
                        row["conversation_id"],
                        run_id,
                        normalized_text,
                        sequence,
                        now_text,
                    ),
                )
                connection.execute(
                    """
                    UPDATE runs
                    SET status = 'completed', assistant_message_id = ?,
                        completion_reason = ?, partial_text = ?, finished_at = ?
                    WHERE id = ?
                    """,
                    (
                        message_id,
                        completion_reason.value,
                        normalized_text,
                        now_text,
                        run_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE conversations
                    SET latest_message_preview = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        self._display_text(normalized_text, maximum=280),
                        now_text,
                        row["conversation_id"],
                    ),
                )
                self._append_event(
                    connection,
                    run_id,
                    row["conversation_id"],
                    RunEventType.RUN_COMPLETED,
                    {
                        "assistantMessageId": message_id,
                        "completionReason": completion_reason.value,
                    },
                    now,
                )
                run_row = self._require_run_row(connection, run_id)
                message_row = connection.execute(
                    "SELECT * FROM messages WHERE id = ?",
                    (message_id,),
                ).fetchone()
                if message_row is None:
                    raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
                connection.commit()
                self._signal_run_event(run_id)
                return CompletedRun(
                    run=self._run(run_row),
                    message=self._message(message_row),
                )
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def fail_run(self, run_id: str, error: PublicRunError) -> RunSnapshot:
        return self._terminal_error_transition(
            run_id,
            RunStatus.FAILED,
            RunEventType.RUN_FAILED,
            error,
        )

    def request_cancel(self, run_id: str) -> RunSnapshot:
        self._require_identifier(run_id)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                status = RunStatus(row["status"])
                if status is RunStatus.QUEUED:
                    now = self._now()
                    connection.execute(
                        """
                        UPDATE runs
                        SET status = 'cancelled', finished_at = ?
                        WHERE id = ?
                        """,
                        (self._timestamp(now), run_id),
                    )
                    self._append_event(
                        connection,
                        run_id,
                        row["conversation_id"],
                        RunEventType.RUN_CANCELLED,
                        {},
                        now,
                    )
                elif status is RunStatus.RUNNING:
                    connection.execute(
                        "UPDATE runs SET status = 'cancelling' WHERE id = ?",
                        (run_id,),
                    )
                elif status is not RunStatus.CANCELLING:
                    raise ConversationStoreError(StoreFailure.RUN_NOT_ACTIVE)
                result = self._require_run_row(connection, run_id)
                connection.commit()
                self._signal_run_event(run_id)
                return self._run(result)
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def mark_run_cancelled(self, run_id: str) -> RunSnapshot:
        self._require_identifier(run_id)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                if row["status"] not in {
                    RunStatus.RUNNING.value,
                    RunStatus.CANCELLING.value,
                }:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                now = self._now()
                connection.execute(
                    """
                    UPDATE runs SET status = 'cancelled', finished_at = ?
                    WHERE id = ?
                    """,
                    (self._timestamp(now), run_id),
                )
                self._append_event(
                    connection,
                    run_id,
                    row["conversation_id"],
                    RunEventType.RUN_CANCELLED,
                    {},
                    now,
                )
                result = self._require_run_row(connection, run_id)
                connection.commit()
                self._signal_run_event(run_id)
                return self._run(result)
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def interrupt_incomplete_runs(self) -> tuple[str, ...]:
        with self._lock:
            if not self._database_file.exists():
                return ()
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT * FROM runs
                    WHERE status IN (?, ?, ?)
                    ORDER BY created_at, id
                    """,
                    _ACTIVE_STATUSES,
                ).fetchall()
                if not rows:
                    connection.commit()
                    return ()
                now = self._now()
                error = PublicRunError(
                    code="internal_error",
                    message="本機服務在執行完成前重新啟動。",
                    retryable=True,
                )
                for row in rows:
                    connection.execute(
                        """
                        UPDATE runs
                        SET status = 'interrupted', error_code = ?,
                            error_message = ?, error_retryable = ?, finished_at = ?
                        WHERE id = ?
                        """,
                        (
                            error.code,
                            error.message,
                            int(error.retryable),
                            self._timestamp(now),
                            row["id"],
                        ),
                    )
                    self._append_event(
                        connection,
                        row["id"],
                        row["conversation_id"],
                        RunEventType.RUN_INTERRUPTED,
                        {"error": self._error_data(error)},
                        now,
                    )
                connection.commit()
                run_ids = tuple(row["id"] for row in rows)
                for run_id in run_ids:
                    self._signal_run_event(run_id)
                return run_ids
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as error:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def list_run_events(
        self,
        run_id: str,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[RunEvent, ...]:
        self._require_identifier(run_id)
        if (
            not isinstance(after_sequence, int)
            or isinstance(after_sequence, bool)
            or after_sequence < 0
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1000
        ):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        with self._lock:
            connection = self._open_read()
            if connection is None:
                return ()
            try:
                rows = connection.execute(
                    """
                    SELECT e.*, r.conversation_id
                    FROM run_events AS e
                    JOIN runs AS r ON r.id = e.run_id
                    WHERE e.run_id = ? AND e.sequence > ?
                    ORDER BY e.sequence
                    LIMIT ?
                    """,
                    (run_id, after_sequence, limit),
                ).fetchall()
                return tuple(self._event(row) for row in rows)
            except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from error
            finally:
                connection.close()

    def _terminal_error_transition(
        self,
        run_id: str,
        status: RunStatus,
        event_type: RunEventType,
        error: PublicRunError,
    ) -> RunSnapshot:
        self._require_identifier(run_id)
        self._validate_public_error(error)
        with self._lock:
            connection = self._open_write()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_run_row(connection, run_id)
                if row["status"] not in _ACTIVE_STATUSES:
                    raise ConversationStoreError(StoreFailure.INVALID_STATE)
                now = self._now()
                connection.execute(
                    """
                    UPDATE runs
                    SET status = ?, error_code = ?, error_message = ?,
                        error_retryable = ?, finished_at = ?
                    WHERE id = ?
                    """,
                    (
                        status.value,
                        error.code,
                        error.message,
                        int(error.retryable),
                        self._timestamp(now),
                        run_id,
                    ),
                )
                self._append_event(
                    connection,
                    run_id,
                    row["conversation_id"],
                    event_type,
                    {"error": self._error_data(error)},
                    now,
                )
                result = self._require_run_row(connection, run_id)
                connection.commit()
                self._signal_run_event(run_id)
                return self._run(result)
            except ConversationStoreError:
                connection.rollback()
                raise
            except (sqlite3.Error, OSError, TypeError, ValueError) as caught:
                connection.rollback()
                raise ConversationStoreError(
                    StoreFailure.DATABASE_UNAVAILABLE
                ) from caught
            finally:
                connection.close()

    def _open_read(self) -> sqlite3.Connection | None:
        if not self._database_file.exists():
            return None
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self._database_file,
                timeout=5,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            self._validate_schema(connection)
            return connection
        except (sqlite3.Error, OSError, ValueError) as error:
            if connection is not None:
                connection.close()
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from error

    def _open_write(self) -> sqlite3.Connection:
        was_missing = not self._database_file.exists()
        connection: sqlite3.Connection | None = None
        try:
            self._database_file.parent.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                os.chmod(self._database_file.parent, 0o700)
            connection = sqlite3.connect(
                self._database_file,
                timeout=5,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            if was_missing:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = FULL")
                connection.executescript(_SCHEMA_SQL)
                if os.name != "nt":
                    os.chmod(self._database_file, 0o600)
            else:
                version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                if version == 1:
                    connection.executescript(_MIGRATE_V1_TO_V2_SQL)
                    version = 2
                if version == 2:
                    connection.executescript(_MIGRATE_V2_TO_V3_SQL)
                    version = 3
                if version == 3:
                    connection.executescript(_MIGRATE_V3_TO_V4_SQL)
                    version = 4
                if version == 4:
                    connection.executescript(_MIGRATE_V4_TO_V5_SQL)
                    version = 5
                if version == 5:
                    connection.executescript(_MIGRATE_V5_TO_V6_SQL)
                    version = 6
                if version == 6:
                    connection.executescript(_MIGRATE_V6_TO_V7_SQL)
                    version = 7
                if version == 7:
                    connection.executescript(_MIGRATE_V7_TO_V8_SQL)
                    version = 8
                if version == 8:
                    connection.executescript(_MIGRATE_V8_TO_V9_SQL)
                    version = 9
                if version == 9:
                    connection.executescript(_MIGRATE_V9_TO_V10_SQL)
                    version = 10
                if version == 10:
                    run_columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(runs)")
                    }
                    if "source" not in run_columns:
                        connection.execute("ALTER TABLE runs ADD COLUMN source TEXT NOT NULL DEFAULT 'user' CHECK(source IN ('user', 'schedule'))")
                    if "occurrence_id" not in run_columns:
                        connection.execute("ALTER TABLE runs ADD COLUMN occurrence_id TEXT")
                    connection.executescript(_MIGRATE_V10_TO_V11_SQL)
                self._validate_schema(connection)
            return connection
        except ConversationStoreError:
            if connection is not None:
                connection.close()
            raise
        except (sqlite3.Error, OSError, ValueError) as error:
            if connection is not None:
                connection.close()
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from error

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != _SCHEMA_VERSION:
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }
        if tables != {
            "conversations",
            "conversation_compactions",
            "messages",
            "runs",
            "run_events",
            "schedules",
            "schedule_occurrences",
        }:
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)

    @staticmethod
    def _require_run_row(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ConversationStoreError(StoreFailure.NOT_FOUND)
        return row

    def _append_event(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        conversation_id: str,
        event_type: RunEventType,
        data: Mapping[str, object],
        created_at: datetime,
    ) -> RunEvent:
        if not isinstance(data, Mapping):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        normalized_data = dict(data)
        self._validate_event_data(event_type, normalized_data)
        try:
            payload = json.dumps(
                normalized_data,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as error:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST) from error
        if len(payload.encode("utf-8")) > _MAX_EVENT_JSON_BYTES:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        sequence = int(
            connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM run_events WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO run_events(run_id, sequence, type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                sequence,
                event_type.value,
                payload,
                self._timestamp(created_at),
            ),
        )
        return RunEvent(
            sequence=sequence,
            type=event_type,
            run_id=run_id,
            conversation_id=conversation_id,
            created_at=created_at,
            data=normalized_data,
        )

    @staticmethod
    def _conversation(row: sqlite3.Row) -> ConversationSummary:
        return ConversationSummary(
            id=row["id"],
            title=row["title"],
            latest_message_preview=row["latest_message_preview"],
            created_at=SqliteConversationRepository._parse_timestamp(
                row["created_at"]
            ),
            updated_at=SqliteConversationRepository._parse_timestamp(
                row["updated_at"]
            ),
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            run_id=row["run_id"],
            role=row["role"],
            content=row["content"],
            sequence=int(row["sequence"]),
            created_at=SqliteConversationRepository._parse_timestamp(
                row["created_at"]
            ),
        )

    @staticmethod
    def _compaction(row: sqlite3.Row) -> ConversationCompaction:
        return ConversationCompaction(
            id=row["id"],
            conversation_id=row["conversation_id"],
            covers_through_sequence=int(row["covers_through_sequence"]),
            summary=row["summary"],
            summary_version=int(row["summary_version"]),
            source_hash=row["source_hash"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            created_at=SqliteConversationRepository._parse_timestamp(
                row["created_at"]
            ),
        )

    @staticmethod
    def _run(row: sqlite3.Row) -> RunSnapshot:
        status = RunStatus(row["status"])
        completion_reason = (
            None
            if row["completion_reason"] is None
            else CompletionReason(row["completion_reason"])
        )
        if (status is RunStatus.COMPLETED) != (completion_reason is not None):
            raise ValueError("invalid Run completion reason")
        error = None
        if row["error_code"] is not None:
            error = PublicRunError(
                code=row["error_code"],
                message=row["error_message"],
                retryable=bool(row["error_retryable"]),
            )
        return RunSnapshot(
            id=row["id"],
            conversation_id=row["conversation_id"],
            user_message_id=row["user_message_id"],
            assistant_message_id=row["assistant_message_id"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            response_mode=row["response_mode"],
            context_budget=row["context_budget"],
            output_budget=row["output_budget"],
            output_continuation=row["output_continuation"],
            log_full_prompts=bool(row["log_full_prompts"]),
            status=status,
            error=error,
            partial_text=row["partial_text"],
            created_at=SqliteConversationRepository._parse_timestamp(
                row["created_at"]
            ),
            started_at=(
                None
                if row["started_at"] is None
                else SqliteConversationRepository._parse_timestamp(
                    row["started_at"]
                )
            ),
            finished_at=(
                None
                if row["finished_at"] is None
                else SqliteConversationRepository._parse_timestamp(
                    row["finished_at"]
                )
            ),
            completion_reason=completion_reason,
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> RunEvent:
        data = json.loads(
            row["payload_json"],
            object_pairs_hook=SqliteConversationRepository._strict_object,
        )
        if not isinstance(data, dict):
            raise ValueError("event payload must be an object")
        return RunEvent(
            sequence=int(row["sequence"]),
            type=RunEventType(row["type"]),
            run_id=row["run_id"],
            conversation_id=row["conversation_id"],
            created_at=SqliteConversationRepository._parse_timestamp(
                row["created_at"]
            ),
            data=data,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
        return value.astimezone(UTC)

    def _signal_run_event(self, run_id: str) -> None:
        if self._event_notifier is not None:
            self._event_notifier.signal(run_id)

    def _new_identifier(self) -> str:
        value = self._identifier_factory()
        self._require_identifier(value)
        return value

    @staticmethod
    def _require_identifier(value: str) -> None:
        if not isinstance(value, str):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        try:
            parsed = UUID(value)
        except (ValueError, TypeError, AttributeError) as error:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST) from error
        if str(parsed) != value:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)

    @staticmethod
    def _require_text(
        value: str,
        *,
        maximum: int,
    ) -> str:
        if not isinstance(value, str):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        normalized = value.strip()
        length = len(normalized)
        if not normalized or length > maximum:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        return normalized

    @staticmethod
    def _display_text(value: str, *, maximum: int) -> str:
        collapsed = " ".join(value.split())
        return collapsed[:maximum]

    @staticmethod
    def _request_fingerprint(
        conversation_id: str | None,
        message: str,
    ) -> str:
        canonical = json.dumps(
            {"conversationId": conversation_id, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _encode_cursor(updated_at: str, identifier: str) -> str:
        raw = json.dumps(
            [updated_at, identifier],
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[str, str]:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 512:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.b64decode(
                cursor + padding,
                altchars=b"-_",
                validate=True,
            )
            value = json.loads(decoded.decode("utf-8"))
            if (
                not isinstance(value, list)
                or len(value) != 2
                or not all(isinstance(item, str) for item in value)
            ):
                raise ValueError("invalid cursor")
            SqliteConversationRepository._parse_timestamp(value[0])
            SqliteConversationRepository._require_identifier(value[1])
            return value[0], value[1]
        except ConversationStoreError:
            raise
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST) from error

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
            "+00:00",
            "Z",
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        if not isinstance(value, str) or not value.endswith("Z"):
            raise ValueError("invalid UTC timestamp")
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("invalid UTC timestamp")
        return parsed.astimezone(UTC)

    @staticmethod
    def _validate_public_error(error: PublicRunError) -> None:
        if (
            not isinstance(error, PublicRunError)
            or not isinstance(error.code, str)
            or error.code not in _PUBLIC_ERROR_CODES
            or not isinstance(error.message, str)
            or not error.message
            or len(error.message) > 512
            or not isinstance(error.retryable, bool)
        ):
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)

    @staticmethod
    def _validate_event_data(
        event_type: RunEventType,
        data: dict[str, object],
    ) -> None:
        keys = set(data)
        if event_type in {
            RunEventType.RUN_STARTED,
            RunEventType.CONTEXT_COMPACTION_STARTED,
            RunEventType.RUN_CANCELLED,
        }:
            if keys:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            return
        if event_type is RunEventType.MODEL_STARTED:
            legacy_keys = {"providerId", "modelId", "responseMode", "maxOutputTokens"}
            context_keys = legacy_keys | {
                "contextTokens",
                "contextLimitTokens",
                "inputBudgetTokens",
            }
            tool_context_keys = context_keys | {"toolNames"}
            if (
                keys != legacy_keys
                and keys != context_keys
                and keys != tool_context_keys
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if data["providerId"] not in _PROVIDER_IDS:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if not SqliteConversationRepository._is_bounded_text(
                data["modelId"],
                maximum=256,
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if data["responseMode"] not in _RESPONSE_MODES:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            max_output_tokens = data["maxOutputTokens"]
            if (
                not isinstance(max_output_tokens, int)
                or isinstance(max_output_tokens, bool)
                or not 1 <= max_output_tokens <= 131_072
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if keys == context_keys or keys == tool_context_keys:
                context_tokens = data["contextTokens"]
                context_limit_tokens = data["contextLimitTokens"]
                input_budget_tokens = data["inputBudgetTokens"]
                if (
                    not isinstance(context_tokens, int)
                    or isinstance(context_tokens, bool)
                    or context_tokens < 1
                    or not isinstance(context_limit_tokens, int)
                    or isinstance(context_limit_tokens, bool)
                    or not 1 <= context_limit_tokens <= 4_000_000
                    or not isinstance(input_budget_tokens, int)
                    or isinstance(input_budget_tokens, bool)
                    or not 1 <= input_budget_tokens <= context_limit_tokens
                    or context_tokens > input_budget_tokens
                ):
                    raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if keys == tool_context_keys:
                tool_names = data["toolNames"]
                if (
                    not isinstance(tool_names, list)
                    or len(tool_names) > 64
                    or any(
                        not SqliteConversationRepository._is_bounded_text(
                            name,
                            maximum=64,
                        )
                        for name in tool_names
                    )
                    or len(set(tool_names)) != len(tool_names)
                ):
                    raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            return
        if event_type is RunEventType.RESPONSE_CONTINUATION_STARTED:
            if keys != {"attempt", "maxAttempts"}:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            attempt = data["attempt"]
            maximum = data["maxAttempts"]
            if (
                not isinstance(attempt, int)
                or isinstance(attempt, bool)
                or not 1 <= attempt <= 64
                or (
                    maximum is not None
                    and (
                        not isinstance(maximum, int)
                        or isinstance(maximum, bool)
                        or maximum not in {1, 2, 3, 5, 10, 20, 50}
                        or attempt > maximum
                    )
                )
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            return
        if event_type is RunEventType.TOOL_APPROVAL_REQUESTED:
            if keys != {
                "approvalId",
                "toolName",
                "toolDisplayName",
                "serverId",
                "argumentHash",
                "expiresAt",
            }:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if (
                not SqliteConversationRepository._is_bounded_text(data["approvalId"], maximum=36)
                or not SqliteConversationRepository._is_bounded_text(data["toolName"], maximum=64)
                or not SqliteConversationRepository._is_bounded_text(data["toolDisplayName"], maximum=256)
                or not SqliteConversationRepository._is_bounded_text(data["serverId"], maximum=36)
                or not SqliteConversationRepository._is_bounded_text(data["argumentHash"], maximum=64)
                or not SqliteConversationRepository._is_bounded_text(data["expiresAt"], maximum=40)
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            return
        if event_type is RunEventType.TOOL_APPROVAL_DECIDED:
            if keys != {"approvalId", "decision"} or not SqliteConversationRepository._is_bounded_text(data["approvalId"], maximum=36) or data["decision"] not in {"allow_once", "deny", "expired"}:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            return
        if event_type is RunEventType.ASSISTANT_DELTA:
            if keys != {"text"} or not SqliteConversationRepository._is_bounded_text(
                data.get("text"),
                maximum=_MAX_ASSISTANT_DELTA_CHARS,
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            return
        if event_type in {
            RunEventType.TOOL_STARTED,
            RunEventType.TOOL_COMPLETED,
            RunEventType.TOOL_FAILED,
        }:
            required = {"callId", "toolName"}
            if event_type is RunEventType.TOOL_COMPLETED:
                required.add("summary")
            if event_type is RunEventType.TOOL_FAILED:
                required.add("error")
            if keys != required:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if not SqliteConversationRepository._is_bounded_text(
                data["callId"],
                maximum=128,
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            tool_name = data["toolName"]
            if not isinstance(tool_name, str) or re.fullmatch(
                r"[a-z][a-z0-9_]{0,63}",
                tool_name,
            ) is None:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if event_type is RunEventType.TOOL_COMPLETED and not (
                SqliteConversationRepository._is_bounded_text(
                    data["summary"],
                    maximum=4096,
                )
            ):
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            if event_type is RunEventType.TOOL_FAILED:
                SqliteConversationRepository._validate_error_mapping(data["error"])
            return
        if event_type is RunEventType.RUN_COMPLETED:
            if keys != {"assistantMessageId", "completionReason"}:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            SqliteConversationRepository._require_identifier(
                data["assistantMessageId"]  # type: ignore[arg-type]
            )
            try:
                CompletionReason(data["completionReason"])  # type: ignore[arg-type]
            except (TypeError, ValueError) as error:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST) from error
            return
        if event_type in {
            RunEventType.RUN_FAILED,
            RunEventType.RUN_INTERRUPTED,
        }:
            if keys != {"error"}:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            SqliteConversationRepository._validate_error_mapping(data["error"])
            return
        raise ConversationStoreError(StoreFailure.INVALID_REQUEST)

    @staticmethod
    def _validate_error_mapping(value: object) -> None:
        if not isinstance(value, Mapping) or set(value) != {
            "code",
            "message",
            "retryable",
        }:
            raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
        error = PublicRunError(
            code=value["code"],  # type: ignore[arg-type]
            message=value["message"],  # type: ignore[arg-type]
            retryable=value["retryable"],  # type: ignore[arg-type]
        )
        SqliteConversationRepository._validate_public_error(error)

    @staticmethod
    def _is_bounded_text(value: object, *, maximum: int) -> bool:
        return isinstance(value, str) and bool(value) and len(value) <= maximum

    @staticmethod
    def _error_data(error: PublicRunError) -> dict[str, object]:
        return {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        }

    @staticmethod
    def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate event payload key")
            result[key] = value
        return result
