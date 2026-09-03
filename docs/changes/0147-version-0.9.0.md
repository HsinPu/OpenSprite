# Version 0.9.0

## Objective

Identify the cross-platform access-mode and Linux installer release as
OpenSprite 0.9.0.

## Changes

- Updated backend package metadata, lock state, app-info expectations, and
  frontend version fixtures to `0.9.0`.
- Aligned Windows build metadata and Linux build-info generation with the same
  authoritative backend version.

## Public impact

Installed and development `/api/app-info` responses report version `0.9.0`.

## Verification

Backend metadata/contract tests, frontend tests/typecheck/build, Windows
installer isolation, portable Linux helper tests, Bash syntax, dependency
checks, and SymbolLattice freshness.

## Remaining work

A real Linux host must execute `installers/linux/test.sh` before claiming a
Linux release artifact has been operationally qualified.
