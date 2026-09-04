# Version 0.12.0

## Objective

Release managed Workspace roots and permission-aware external directory mounts
as OpenSprite 0.12.0.

## Changes

- Raised the authoritative backend and lockfile version to `0.12.0`.
- Updated README, architecture and static contracts for catalog v2, SQLite v13,
  managed roots, mount snapshots and receipt v4.
- Kept file tools and Skills outside this release; Skills move to `0.13.0`.

## Public impact

New and upgraded installations always expose an available Default Workspace
when its managed root can be created. Existing v1 roots are retained as mounts
without moving or deleting files.

## Verification

- Backend pytest: `701 passed, 2 skipped`; compileall, uv lock and dependency
  checks passed.
- Frontend Vitest: `277 passed`; typecheck and production build passed.
- Windows installer isolation and Git Bash installer syntax checks passed.

## Remaining work

- File tools, Git, Terminal, Skills and real Linux GUI/systemd execution remain
  outside this release. No push or installed-computer update is included.
