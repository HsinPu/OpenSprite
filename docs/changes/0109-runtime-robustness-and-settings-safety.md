# Runtime robustness and settings safety

## Objective

Keep the current OpenSprite modular-monolith workflow reliable at the existing
frontend, Agent, SQLite and local-settings boundaries without changing the
public HTTP contract or introducing a new runtime service.

## Changes

- Split oversized UTF-8 assistant deltas into validated semantic events so
  multi-byte text cannot exceed the SQLite event payload limit while the
  durable partial response remains unchanged.
- Record an error-level Agent traceback with only the Run identifier when an
  unexpected background failure is converted to `internal_error`.
- Added a provider-operation generation to invalidate the in-memory OpenRouter
  capability cache after credential mutations and wired it through runtime
  composition.
- Centralized atomic settings-file replacement with owner-only permissions and
  parent-directory fsync on Unix-like systems.
- Blocked AI preference changes and automatic model reconciliation until the
  initial AI settings read succeeds, with a retry action for read failures.
- Corrected backend architecture guard coverage and synchronized Context,
  SQLite-table and historical design-document descriptions.

## Public impact

The HTTP/SSE contracts, persisted schema versions, Provider behavior and
frontend model payloads remain unchanged. Only malformed edge handling,
diagnostic logging, cache freshness, local-file durability and the initial
settings loading state are changed.

## Verification

- Focused backend regression tests for delta splitting, Agent diagnostics,
  capability invalidation and settings persistence passed.
- Full backend suite passed with an isolated repository-local pytest temp root:
  492 passed, 2 skipped.
- Full frontend suite passed: 194 tests in 24 files.
- Frontend typecheck and production build passed.
- `git diff --check` and working-tree inspection are run before commit.

## Remaining work

Incremental SQLite write batching, retention and cleanup for full Prompt and
System Prompt receipts, request-body limits, generated contract clients, CI
automation, and large-module extraction remain separate follow-up slices.
