"""SQLite schema creation and ordered migrations; caller owns the connection."""

import sqlite3
from opensprite_backend.custom_agents.child_schema import CHILD_SCHEMA_STATEMENTS, migrate_v14_to_v15
from opensprite_backend.workspaces import EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH, DEFAULT_WORKSPACE_ID
from opensprite_backend.workspaces.models import DEFAULT_WORKSPACE_NAME

SCHEMA_VERSION = 15

SCHEMA_SQL = """
BEGIN IMMEDIATE;
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL CHECK(length(workspace_id) = 36),
    revision INTEGER NOT NULL CHECK(revision >= 1),
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
    workspace_id TEXT NOT NULL CHECK(length(workspace_id) = 36),
    workspace_revision INTEGER NOT NULL CHECK(workspace_revision >= 1),
    workspace_name_snapshot TEXT NOT NULL CHECK(length(workspace_name_snapshot) BETWEEN 1 AND 80),
    workspace_root_hash TEXT CHECK(workspace_root_hash IS NULL OR length(workspace_root_hash) = 64),
    workspace_mount_manifest_hash TEXT NOT NULL CHECK(length(workspace_mount_manifest_hash) = 64),
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
        'skill.loaded', 'skill.load_failed',
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
    workspace_id TEXT NOT NULL DEFAULT '00000000-0000-4000-8000-000000000000' CHECK(length(workspace_id) = 36),
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

CREATE INDEX conversations_by_workspace_updated
ON conversations(workspace_id, updated_at DESC, id DESC);
CREATE INDEX active_runs_by_workspace
ON runs(workspace_id)
WHERE status IN ('queued', 'running', 'cancelling');
CREATE INDEX schedules_by_workspace
ON schedules(workspace_id, status, next_run_at, id);

""" + ";\n".join(CHILD_SCHEMA_STATEMENTS) + ";\nPRAGMA user_version = 15;\nCOMMIT;\n"

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

def _migrate_v11_to_v12(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        conversation_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(conversations)")
        }
        if "workspace_id" not in conversation_columns:
            connection.execute(
                "ALTER TABLE conversations ADD COLUMN workspace_id TEXT NOT NULL "
                "DEFAULT '00000000-0000-4000-8000-000000000000' "
                "CHECK(length(workspace_id) = 36)"
            )
        if "revision" not in conversation_columns:
            connection.execute(
                "ALTER TABLE conversations ADD COLUMN revision INTEGER NOT NULL "
                "DEFAULT 1 CHECK(revision >= 1)"
            )
        run_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(runs)")
        }
        additions = {
            "workspace_id": (
                "ALTER TABLE runs ADD COLUMN workspace_id TEXT NOT NULL "
                "DEFAULT '00000000-0000-4000-8000-000000000000' "
                "CHECK(length(workspace_id) = 36)"
            ),
            "workspace_revision": (
                "ALTER TABLE runs ADD COLUMN workspace_revision INTEGER NOT NULL "
                "DEFAULT 1 CHECK(workspace_revision >= 1)"
            ),
            "workspace_name_snapshot": (
                "ALTER TABLE runs ADD COLUMN workspace_name_snapshot TEXT NOT NULL "
                "DEFAULT 'Default workspace' "
                "CHECK(length(workspace_name_snapshot) BETWEEN 1 AND 80)"
            ),
            "workspace_root_hash": (
                "ALTER TABLE runs ADD COLUMN workspace_root_hash TEXT "
                "CHECK(workspace_root_hash IS NULL OR length(workspace_root_hash) = 64)"
            ),
        }
        for column, statement in additions.items():
            if column not in run_columns:
                connection.execute(statement)
        schedule_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(schedules)")
        }
        if "workspace_id" not in schedule_columns:
            connection.execute(
                "ALTER TABLE schedules ADD COLUMN workspace_id TEXT NOT NULL "
                "DEFAULT '00000000-0000-4000-8000-000000000000' "
                "CHECK(length(workspace_id) = 36)"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS conversations_by_workspace_updated "
            "ON conversations(workspace_id, updated_at DESC, id DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS active_runs_by_workspace ON runs(workspace_id) "
            "WHERE status IN ('queued', 'running', 'cancelling')"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS schedules_by_workspace "
            "ON schedules(workspace_id, status, next_run_at, id)"
        )
        connection.execute("PRAGMA user_version = 12")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migrate_v12_to_v13(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
        if "workspace_mount_manifest_hash" not in columns:
            connection.execute(
                "ALTER TABLE runs ADD COLUMN workspace_mount_manifest_hash TEXT "
                f"NOT NULL DEFAULT '{EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH}' "
                "CHECK(length(workspace_mount_manifest_hash) = 64)"
            )
        connection.execute(
            "UPDATE runs SET workspace_name_snapshot = ? "
            "WHERE workspace_id = ? AND workspace_name_snapshot = 'Unassigned workspace'",
            (DEFAULT_WORKSPACE_NAME, DEFAULT_WORKSPACE_ID),
        )
        connection.execute("PRAGMA user_version = 13")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def migrate_schema(connection: sqlite3.Connection) -> None:
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
        version = 11
    if version == 11:
        _migrate_v11_to_v12(connection)
        version = 12
    if version == 12:
        _migrate_v12_to_v13(connection)
        version = 13
    if version == 13:
        from .skill_event_migration import migrate
        migrate(connection)
        version = 14
    if version == 14:
        migrate_v14_to_v15(connection)
