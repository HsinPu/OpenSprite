# Managed Workspace catalog

## Objective

Replace the rootless Workspace catalog with managed roots and durable,
permission-aware external directory registrations.

## Changes

- Added the user-visible `OpenSprite/workspace` container, immutable managed
  directory names, explicit existing-directory import and catalog schema v2.
- Migrated v1 external roots into non-destructive legacy mounts and disabled
  ambiguous nested legacy paths.
- Added strict mount CRUD, read-only defaults, overlap prevention, active-Run
  mutation guards and live availability.
- Updated the authoritative Workspace API contract and strict validation/error
  matrix.

## Public impact

The fixed Workspace UUID now represents an available managed Default Workspace.
New Workspace roots are created by OpenSprite instead of accepting arbitrary
primary paths. External directories are attached explicitly as mounts.

## Verification

- Backend pytest: `701 passed, 2 skipped`; focused Workspace and migration
  tests pass.
- Python compileall, uv lock and dependency checks passed.

## Remaining work

- No push or installed-computer update is included.
