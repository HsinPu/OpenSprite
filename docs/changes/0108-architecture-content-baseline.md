# Architecture and content baseline

## Objective

Align the repository documentation and frontend architecture guard with the
implemented OpenSprite boundaries so that future changes are reviewed against
the current system rather than an earlier demo description.

## Changes

- Updated the root, backend, frontend and contracts READMEs with the current
  AI settings schema-v8 fields, response-delivery semantics, prompt logging,
  implemented runtime data, app-info boundary and Windows installer status.
- Corrected the architecture overview's outdated AI schema and installer
  statements.
- Documented that full Prompt receipt retention and cleanup is not implemented
  yet; the receipts remain sensitive local diagnostic data.
- Extended the frontend dependency guard to cover the
  `conversation-settings` and `app-info` feature boundaries and their explicit
  allowed dependencies.

## Public impact

There is no runtime, HTTP, persistence, or frontend behavior change. This
slice only improves documentation accuracy and makes existing frontend module
boundaries enforceable by the architecture test.

## Verification

- Frontend architecture test passed after adding both feature boundaries.
- Frontend typecheck, build and test suite are run for this revision.
- Backend architecture tests remain unchanged and are run as a regression
  check.
- `git diff --check` and working-tree checks are clean before commit.

## Remaining work

The following reviewed items remain separate, measured changes: batching
incremental SQLite writes for long streaming outputs, an approved retention
and cleanup policy for full Prompt receipts, stale Windows installer rollback
directory cleanup, and repository-wide CI/verification automation. Large module
splits should wait until a concrete feature makes a smaller seam necessary.
