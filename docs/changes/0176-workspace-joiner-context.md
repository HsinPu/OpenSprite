# Workspace joiner context validation

## Objective

Close advisory `OS-WS-R3-001` without removing support for composed emoji or
languages that use Unicode ZWNJ and ZWJ.

## Changes

- Required each allowed joiner to appear inside a non-empty Workspace name,
  managed directory name or mount alias.
- Rejected leading, trailing and consecutive ZWNJ/ZWJ sequences.
- Applied the same current policy to v1 migration so legacy invalid joiner
  placement receives the deterministic safe fallback.
- Added real-filesystem and migration regression cases for every boundary.

## Verification

- Eight focused cases first reproduced the advisory; the corrected Unicode
  set passed `24` cases and the complete Workspace suite passed `52` tests.
- Backend pytest passed `720` tests with `2` skipped; frontend Vitest passed
  `279` tests.
- Python compileall, uv lock, dependency checks, TypeScript typecheck,
  production build and Windows installer isolation passed.

## Remaining work

- No push or installed-computer update is included.
