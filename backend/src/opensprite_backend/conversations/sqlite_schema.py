"""Current core schema; preserve the v20 baseline without activating retired data."""

import sqlite3

SCHEMA_VERSION = 23
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
    provider_id TEXT NOT NULL CHECK(provider_id IN ('openai', 'anthropic', 'openrouter') OR (length(provider_id) = 36 AND substr(provider_id, 15, 1) = '4')),
    model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
    response_mode TEXT NOT NULL CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')),
    context_budget TEXT NOT NULL CHECK(context_budget IN ('auto', '32k', '64k', '128k', '256k', 'max')),
    output_budget TEXT NOT NULL CHECK(output_budget IN ('auto', '8k', '16k', '32k', '64k', 'max')),
    output_continuation TEXT CHECK(output_continuation IN ('off', '1', '2', '3', '5', '10', '20', '50', 'unlimited')),
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
    producer_plugin_id TEXT NOT NULL DEFAULT 'legacy',
    producer_plugin_version TEXT NOT NULL DEFAULT 'unknown',
    summary_format TEXT NOT NULL DEFAULT 'opensprite.text.v1',
    source_step_id TEXT REFERENCES run_steps(id),
    source_first_sequence INTEGER CHECK(source_first_sequence IS NULL OR source_first_sequence >= 1),
    previous_summary_id TEXT REFERENCES conversation_compactions(id),
    UNIQUE(conversation_id, summary_format, covers_through_sequence)
) STRICT;

CREATE TABLE run_events (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    type TEXT NOT NULL CHECK(type IN (
        'run.started', 'execution.selected', 'context.compaction.started', 'context.compaction.completed', 'context.compaction.failed', 'context.compaction.cancelled', 'model.started', 'model.attempt', 'step.started', 'step.completed',
        'response.continuation.started',
        'assistant.delta', 'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted'
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

CREATE INDEX conversations_by_workspace_updated
ON conversations(workspace_id, updated_at DESC, id DESC);
CREATE INDEX active_runs_by_workspace
ON runs(workspace_id)
WHERE status IN ('queued', 'running', 'cancelling');
ALTER TABLE runs ADD COLUMN reasoning_resolution_json TEXT CHECK(reasoning_resolution_json IS NULL OR length(reasoning_resolution_json) <= 512);
PRAGMA user_version = 23;
COMMIT;

"""

STEP_SCHEMA_SQL = """
CREATE TABLE run_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence BETWEEN 1 AND 2048),
    label TEXT NOT NULL CHECK(length(label) BETWEEN 1 AND 64),
    channel TEXT NOT NULL CHECK(channel IN ('draft', 'answer')),
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed', 'cancelled', 'interrupted')),
    text TEXT NOT NULL DEFAULT '' CHECK(length(text) <= 1048576),
    finish_reason TEXT CHECK(finish_reason IN ('final', 'output_limit')),
    error_code TEXT,
    input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens >= 0),
    output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens >= 0),
    retry_of TEXT REFERENCES run_steps(id),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    UNIQUE(run_id, sequence)
) STRICT;
CREATE INDEX steps_by_run_sequence ON run_steps(run_id, sequence);
"""
SCHEMA_SQL = SCHEMA_SQL.replace("PRAGMA user_version = 23;", STEP_SCHEMA_SQL + "\nPRAGMA user_version = 23;")

def _migrate_to_v22(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in {20, 21}:
        raise ValueError("Upgrade older data to OpenSprite 0.21.30 before using the clean core")
    required = {
        "conversations": {"id", "workspace_id", "revision"},
        "messages": {"id", "conversation_id", "run_id", "content"},
        "runs": {"id", "workspace_id", "workspace_mount_manifest_hash", "reasoning_resolution_json"},
        "run_events": {"run_id", "sequence", "type", "payload_json"},
        "conversation_compactions": {"id", "conversation_id", "summary"},
    }
    for table, columns in required.items():
        actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if not columns.issubset(actual):
            raise ValueError("Incomplete core schema")
    try:
        import re
        # Keep the original allowed historical event types and all original rows.
        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='run_events'").fetchone()[0]
        new_sql = re.sub(r"(?i)(CREATE TABLE\s+)(?:\"run_events\"|run_events)", r"\1run_events_v22", sql, count=1)
        new_sql, count = re.subn(r"(?is)(CHECK\s*\(\s*type\s+IN\s*\()(.*?)(\)\s*\))",
                                r"\1\2, 'step.started', 'step.completed'\3", new_sql, count=1)
        if count != 1:
            raise ValueError("Unsupported event schema")
        connection.execute(new_sql)
        connection.execute("INSERT INTO run_events_v22 SELECT * FROM run_events")
        connection.execute("DROP TABLE run_events")
        connection.execute("ALTER TABLE run_events_v22 RENAME TO run_events")

        # The old unique coverage bound becomes format-scoped. Copy every column
        # and preserve historical IDs/content before replacing the schema.
        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='conversation_compactions'").fetchone()[0]
        new_sql = re.sub(r"(?i)(CREATE TABLE\s+)(?:\"conversation_compactions\"|conversation_compactions)",
                         r"\1conversation_compactions_v22", sql, count=1)
        new_sql, count = re.subn(r"(?i)UNIQUE\s*\(\s*conversation_id\s*,\s*covers_through_sequence\s*\)",
                                "UNIQUE(conversation_id, summary_format, covers_through_sequence)", new_sql, count=1)
        if count != 1:
            raise ValueError("Unsupported compaction schema")
        position = new_sql.upper().index("UNIQUE(CONVERSATION_ID, SUMMARY_FORMAT, COVERS_THROUGH_SEQUENCE)")
        new_sql = new_sql[:position] + """
    producer_plugin_id TEXT NOT NULL DEFAULT 'legacy',
    producer_plugin_version TEXT NOT NULL DEFAULT 'unknown',
    summary_format TEXT NOT NULL DEFAULT 'opensprite.text.v1',
""" + new_sql[position:]
        connection.execute(new_sql)
        columns = [row[1] for row in connection.execute("PRAGMA table_info(conversation_compactions)")]
        names = ", ".join('"' + name.replace('"', '""') + '"' for name in columns)
        connection.execute(f"INSERT INTO conversation_compactions_v22 ({names}) SELECT {names} FROM conversation_compactions")
        connection.execute("DROP TABLE conversation_compactions")
        connection.execute("ALTER TABLE conversation_compactions_v22 RENAME TO conversation_compactions")
        connection.execute("CREATE INDEX compactions_by_conversation_coverage ON conversation_compactions(conversation_id, covers_through_sequence DESC)")
        for statement in STEP_SCHEMA_SQL.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("PRAGMA user_version = 22")
    except BaseException:
        raise


def migrate_schema(connection: sqlite3.Connection) -> None:
    """One transaction upgrades v20/v21/v22, preserving every historical row."""
    import re
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version == SCHEMA_VERSION:
        return
    if version not in {20, 21, 22}:
        raise ValueError("Upgrade older data to OpenSprite 0.21.30 before using the clean core")
    foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("BEGIN IMMEDIATE")
    try:
        if version in {20, 21}:
            _migrate_to_v22(connection)
        required = {"run_steps": {"id", "run_id"}, "runs": {"output_continuation", "reasoning_resolution_json"},
                    "conversation_compactions": {"summary_format", "producer_plugin_id"}}
        for table, columns in required.items():
            actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not columns.issubset(actual):
                raise ValueError("Incomplete v22 schema")
        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='runs'").fetchone()[0]
        new_sql = re.sub(r'(?i)(CREATE TABLE\s+)(?:"runs"|runs)', r'\1runs_v23', sql, count=1)
        new_sql, count = re.subn(r'(?i)(output_continuation\s+TEXT)\s+NOT\s+NULL', r'\1', new_sql, count=1)
        if count != 1:
            raise ValueError("Unsupported continuation schema")
        indexes = [row[0] for row in connection.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='runs' AND sql IS NOT NULL")]
        connection.execute(new_sql)
        connection.execute("INSERT INTO runs_v23 SELECT * FROM runs")
        connection.execute("DROP TABLE runs")
        connection.execute("ALTER TABLE runs_v23 RENAME TO runs")
        for index in indexes:
            connection.execute(index)
        connection.execute("ALTER TABLE conversation_compactions ADD COLUMN source_step_id TEXT REFERENCES run_steps(id)")
        connection.execute("ALTER TABLE conversation_compactions ADD COLUMN source_first_sequence INTEGER CHECK(source_first_sequence IS NULL OR source_first_sequence >= 1)")
        connection.execute("ALTER TABLE conversation_compactions ADD COLUMN previous_summary_id TEXT REFERENCES conversation_compactions(id)")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Invalid historical relationships")
        connection.execute("PRAGMA user_version = 23")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON" if foreign_keys else "PRAGMA foreign_keys = OFF")
