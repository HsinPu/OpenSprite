# Skill folder Unicode policy alignment

## Objective

Align the browser's advisory Skill folder path validation with the backend's
portable Unicode policy. Version remains 0.14.0.

## Changes

- Allow contextual U+200C ZERO WIDTH NON-JOINER and U+200D ZERO WIDTH JOINER in
  folder and supporting-file path segments when they are internal, not adjacent
  to another joiner, and otherwise pass the shared portable-name constraints.
- Continue rejecting other Unicode format characters, controls, surrogates, and
  joiners at the start, end, or next to another joiner.
- Add browser regressions for emoji and language joiners plus invalid positions.
- Confirm that the browser accepts a UTF-8 BOM for preview while retaining the
  original `File` object for the multipart upload. `TextDecoder` already strips
  the signature from the preview string, so no BOM production change was needed.

## Public impact

Users can import backend-valid folders containing common joined emoji or
language filenames. No API, persistence, error-code, or uploaded-byte behavior
changes.

## Verification

- Frontend Skill folder import suite: 17 passed.
- Combined Skill folder and Skills settings suites: 26 passed.
- TypeScript typecheck and production build passed.

## Remaining work

Real browser folder selection and Linux filesystem verification were not rerun.
The SymbolLattice guidance remains 0.511.0 while the installed CLI is 0.513.0,
and the existing index is stale.
