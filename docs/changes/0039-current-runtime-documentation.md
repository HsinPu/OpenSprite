# Current runtime documentation

## Objective

Align repository documentation with the implemented frontend, backend and local
runtime without changing product behavior.

## Changes

- Updated the root README to describe the implemented Provider, AI settings,
  Conversation, Run, SSE, Agent and encrypted local-data boundaries.
- Updated the frontend README to describe real HTTP/SSE-backed chat instead of
  session-only fake conversation data.
- Updated the backend README to include SQLite conversation persistence and the
  bounded Agent runtime.
- Added `.SymbolLattice/` to the local generated-index ignore list.

## Public impact

None. Runtime behavior, HTTP/SSE contracts, persisted data and UI behavior are
unchanged.

## Verification

- `npm test -- --run`: 78 tests passed before the documentation change.
- `uv run pytest -W error -p no:cacheprovider`: 336 tests passed before the
  documentation change.
- `git diff --check`

## Remaining work

- Move Agent chat application orchestration out of the HTTP API package.
- Split oversized frontend responsibilities.
- Add the approved frontend internationalization boundary.
