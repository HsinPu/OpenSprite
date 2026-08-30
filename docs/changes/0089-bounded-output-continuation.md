# 0089 — Bounded output continuation

## Objective

Continue useful output-limited model responses without creating synthetic user
Messages, unbounded retries, or a second task lifecycle.

## Changes

- Added the persisted `autoContinueOutput` AI setting, defaulting to enabled.
- Snapshotted the setting on every Run in SQLite schema v6.
- Continued output-limited responses at most twice, with tools disabled and all
  deltas retained on the same Run and final assistant Message.
- Added a bounded provider-neutral continuation transcript using the original
  request context and at most 4K estimated tokens from the assistant tail.
- Reused the existing one-compaction Context recovery boundary. If Context
  remains unavailable after useful output exists, that output is committed with
  completion reason `context_limit`.
- Added a semantic continuation event, execution progress, terminal notices,
  strict contracts, and Traditional Chinese, English, and Japanese copy.

## Public impact

AI settings now require `autoContinueOutput`. Run completion reasons add
`context_limit`, and Run events add `response.continuation.started` with bounded
attempt metadata. Existing schema-v4 AI settings and schema-v5 databases load
with automatic continuation enabled.

## Verification

Backend and frontend targeted suites cover disabled continuation, normal
completion, two-attempt continuation, exhausted attempts, Context recovery,
settings persistence, schema migration, strict SSE parsing and UI state. The
final backend suite passed 461 tests with 2 platform skips; the frontend suite
passed 173 tests. Python compileall, offline lock, dependency checks, TypeScript,
the production build, Windows installer isolation, `git diff --check`, and the
fresh SymbolLattice architecture scan also passed.

## Deferred

Manual continuation, configurable attempt counts, Provider-specific response
state, process-restart recovery, output-file artifacts and unbounded generation
remain out of scope.
