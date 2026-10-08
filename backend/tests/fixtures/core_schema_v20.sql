-- Read-only v20 data compatibility fixture from main 4dc081e.

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
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter') OR (length(provider_id) = 36 AND substr(provider_id, 15, 1) = '4')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')),
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
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter') OR (length(provider_id) = 36 AND substr(provider_id, 15, 1) = '4')),
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
        'run.started', 'execution.selected', 'context.compaction.started', 'context.compaction.completed', 'context.compaction.failed', 'context.compaction.cancelled', 'model.started', 'model.attempt',
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
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter') OR (length(provider_id) = 36 AND substr(provider_id, 15, 1) = '4')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')),
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

CREATE TABLE agent_executions (
        id TEXT PRIMARY KEY,
        parent_run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        spawn_call_id TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash) = 64),
        agent_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        agent_revision INTEGER NOT NULL CHECK(agent_revision >= 1),
        definition_hash TEXT NOT NULL CHECK(length(definition_hash) = 64),
        provider_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN (
            'queued', 'running', 'cancelling', 'completed', 'failed',
            'cancelled', 'interrupted', 'timed_out')),
        result_text TEXT NOT NULL DEFAULT '' CHECK(length(result_text) <= 1048576),
        error_code TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        UNIQUE(parent_run_id, spawn_call_id)
    ) STRICT;
CREATE INDEX agent_executions_by_parent
        ON agent_executions(parent_run_id, created_at, id);
CREATE TABLE agent_execution_events (
        execution_id TEXT NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL CHECK(sequence >= 1),
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
        created_at TEXT NOT NULL,
        PRIMARY KEY(execution_id, sequence)
    ) STRICT;
ALTER TABLE runs ADD COLUMN reasoning_resolution_json TEXT CHECK(reasoning_resolution_json IS NULL OR length(reasoning_resolution_json) <= 512);
PRAGMA user_version = 20;
COMMIT;
