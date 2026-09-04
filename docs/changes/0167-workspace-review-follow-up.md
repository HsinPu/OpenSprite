# Workspace review follow-up

## Objective

Resolve the final three defects found by the independent review of Workspace
release hardening.

## Changes

- Preserved both `run.started` and the latest Context-usage event when the
  browser trims a Run to its bounded 500-event display window.
- Restored FastAPI's declarative `expectedRevision` query parameter while
  retaining strict raw query validation for Workspace deletion.
- Propagated Workspace catalog loading, failure and retry state into Schedule
  settings; create and edit actions pause while the catalog is unavailable.
- Deduplicated concurrent Workspace reloads and cleared stale errors when a
  retry begins, preventing late responses from overwriting newer state.
- Made Workspace loading resilient to React StrictMode effect remounts and
  invalidated pre-mutation reloads before applying or refreshing new catalog
  state.
- Preserved the recoverable reload error when a successful Workspace update or
  deletion cannot refresh the catalog, so the existing retry path remains
  available.

## Public impact

Long execution histories keep their Workspace availability, live OpenAPI
clients can discover the required deletion revision, and Schedule users receive
a recoverable Workspace error instead of a permanent loading label.

## Verification

- Backend pytest: `683 passed, 3 skipped` on Python 3.13.
- Frontend Vitest: `273 passed`; TypeScript typecheck and production build
  passed.
- Focused Context retention, live OpenAPI and Schedule error-state tests passed.
- Python compileall, uv lock/dependency checks, Windows installer isolation and
  Linux installer Bash syntax passed.
