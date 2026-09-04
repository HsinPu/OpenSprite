# Workspace conversation and Run binding

## Objective

Make Workspace identity a durable part of Conversation and Run creation without
persisting absolute Workspace roots in SQLite.

## Changes

- Migrated the shared SQLite schema from v11 to v12 with Workspace identity,
  revision, name snapshot and root-hash fields.
- Scoped conversation listing and new Runs to an explicit Workspace and added
  safe Conversation lookup and move operations.
- Composed the Workspace catalog in the production runtime behind the same
  mutation gate used for Run acceptance.
- Updated the strict backend and frontend Agent Chat contracts for Workspace
  identity while keeping the existing chat UI on the reserved unassigned
  Workspace until the management interface lands.

## Public impact

Conversation listing and Run creation now require `workspaceId`. Conversation
and Run responses expose non-secret Workspace identity and revision metadata.

## Verification

- SQLite migration, scope, usage, idempotency and move tests.
- Agent Chat service, HTTP contract and runtime tests.
- Frontend Agent Chat parsing, hook, App and TypeScript checks.

## Remaining work

Schedule ownership, ToolContext, System Prompt and Workspace management UI are
implemented in later slices.
