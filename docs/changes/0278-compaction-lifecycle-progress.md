# Compaction lifecycle (phase 1)

## Implemented

- Schema 17 admits completed, failed, and cancelled compaction events while
  preserving legacy events through a transactional table migration.
- Each compaction emits a distinct ID and a terminal outcome. Event metadata is
  allowlisted and does not include prompts, summary text, or raw provider errors.
- Execution history retains separate compactions and only marks explicit
  completion as successful. Missing terminal records remain unknown, including
  legacy records and interrupted runs.
- Completion means summary generation completed, not proof that the next
  assembled model request fits its budget. Existing budget/retry policy is unchanged.

## Verification

- Backend focused suite: 83 passed (agent loop, event payload validation,
  compaction migration, SQLite conversation repository).
- Frontend focused suite: 38 passed (ExecutionContext, agentChat, compaction metadata).
- API contract document: 7 passed. TypeScript passed.
- Migration preserves the existing primary-key index and outgoing run foreign key;
  no additional run_events indexes or incoming foreign keys exist in schema 16.
- Injected migration copy failure verifies transactional rollback of DDL and version.
- Tests use an isolated temporary Python environment and unique pytest base
  directories because the repository virtual environment and shared pytest temp
  directory are unavailable in this execution environment.

## Remaining final gates

- Full regression suites and rendered browser review.

Phases 2–4 remain pending. No version bump, deployment, or push has occurred.
