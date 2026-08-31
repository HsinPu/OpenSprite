# Version 0.2.1

## Objective

Identify the current OpenSprite build as the next patch version after the
historical execution-panel fixes and Context usage indicator.

## Changes

- Bump the authoritative backend package and product version from `0.2.0` to
  `0.2.1`.
- Synchronize the locked package metadata so installation and build-info checks
  report the same version.
- Keep the frontend package private and continue reading the product version
  from the backend app-info contract.

## Public impact

The displayed product version becomes `0.2.1`. No HTTP, database, credential,
Context or frontend payload contract changes.

## Verification

- `uv lock --check --offline` and `uv pip check` pass after the metadata update.
- Backend package import/version and the Windows installer build-info check are
  run before the commit.

## Remaining work

This is a local versioned commit; no release artifact or remote tag is created
by this change.
