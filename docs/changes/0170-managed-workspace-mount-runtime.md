# Managed Workspace mount runtime

## Objective

Carry an immutable managed-root and mount manifest through chat, scheduled
execution, System Prompt metadata and Tool receipts without persisting absolute
paths in execution records.

## Changes

- Added SQLite schema v13 and deterministic empty/non-empty mount manifest
  hashes to Run snapshots.
- Kept one immutable `WorkspaceExecutionContext` through retries, compaction,
  continuation, Tool rounds and scheduled Runs.
- Added safe mount aliases, permissions, availability and hashes to
  `run.started` and version-4 Tool receipts without absolute roots.
- Added full managed-root and mount metadata to the bounded, explicitly
  untrusted Workspace section of the System Prompt.
- Updated Agent chat and Schedule contracts for version 0.12.0 runtime data.

## Public impact

Models receive the Workspace directory map as untrusted metadata, while the
runtime continues to state that paths do not grant file capabilities. No file
tool is introduced by this change.

## Verification

- Backend pytest: `701 passed, 2 skipped`; snapshot, migration, Prompt,
  scheduled-run and receipt compatibility tests pass.
- Python compileall, uv lock and dependency checks passed.

## Remaining work

- No push or installed-computer update is included.
