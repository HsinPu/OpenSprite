# Workspace release hardening

## Objective

Close the remaining Workspace snapshot, request-validation, path-safety and UI
gaps before OpenSprite 0.11.0 is pushed.

## Changes

- Passed one immutable Workspace execution context from Chat service through
  RunManager and every Agent loop round without re-reading the catalog.
- Added Workspace availability to `run.started` and version-3 Tool receipts
  while preserving verification of signed version-1 and version-2 receipts.
- Rejected unknown, duplicate, missing and invalid Workspace DELETE query data.
- Rejected every Windows reparse-point root in addition to symlink and junction
  checks.
- Added unavailable and missing Workspace warnings to Schedule cards and
  selector options in Traditional Chinese, English and Japanese.
- Added concurrency, migration rollback, catalog-limit, duplicate-name,
  path-safety, contract, receipt and frontend regression coverage.

## Public impact

Queued Runs keep the exact Workspace snapshot that was accepted, execution
history shows its availability, and Schedule users can see when a saved
Workspace folder is not usable. No full Workspace path is added to SQLite,
ordinary logs, Run events or Tool receipts.

## Verification

- Backend pytest: `682 passed, 3 skipped` on Python 3.13; the added symlink
  case skips when Windows does not grant symlink creation, while explicit
  reparse-attribute and junction paths remain covered.
- Frontend Vitest: `268 passed`; TypeScript typecheck and production build
  passed.
- Python compileall, uv lock/dependency checks, Windows installer isolation and
  Linux installer Bash syntax passed.

## Remaining work

Filesystem, Git, terminal, Skills and external channel capabilities remain out
of scope for 0.11.0.
