# Version 0.11.0

## Objective

Identify the first Workspace foundation release as OpenSprite 0.11.0 and make
its storage, execution and capability boundaries discoverable from current
documentation.

## Changes

- Updated the authoritative backend package version and lock entry to `0.11.0`.
- Updated app-info contract assertions and frontend authentication fixtures.
- Updated the Schedule contract version after adding explicit Workspace
  ownership.
- Added the Workspace architecture record and aligned the overview, Agent chat,
  Schedule, System Prompt, local-data layout and README documentation.
- Closed read connections when schema validation fails and made migration tests
  commit then close their temporary SQLite connections, keeping the declared
  Python 3.13 support clean under `-W error`.

## Public impact

Development and future installed `/api/app-info` responses report `0.11.0`.
The About and authentication screens therefore distinguish this Workspace
release from `0.10.1`.

## Verification

- Complete backend pytest (`678 passed, 2 skipped`) on Python 3.13 and bytecode
  compilation.
- Backend lock consistency and installed dependency checks.
- Complete frontend Vitest (`262 passed`), TypeScript and production build
  checks.
- Windows installer isolation, Linux helper/unit and Bash syntax checks.
- Repository diff, clean-worktree and SymbolLattice freshness checks.

## Remaining work

Skills remain planned for 0.12.0. Filesystem, Git, terminal and external channel
capabilities are not part of this release.
