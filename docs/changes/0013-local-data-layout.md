# 0013 — Centralized local data layout

## Objective

Make `%USERPROFILE%\.opensprite` on Windows and `~/.opensprite` on Linux the
single OpenSprite user-data root, then place the existing provider metadata
under that contract without creating speculative storage features.

## Changes

- Added the pure, injectable `AppPaths` mapping for config, database, provider
  state, conversations, logs, and cache locations.
- Made `state/providers.json` the only implemented filesystem consumer of the
  layout. Constructing paths, importing the backend, entering the system-app
  lifespan, and reading absent provider state remain side-effect free.
- Required `JsonProviderStateRepository` callers to provide an explicit path and
  replaced the direct provider-state path override with
  `create_provider_runtime(app_paths=...)`.
- Removed the previous application-data path dependency and regenerated the
  backend lockfile.
- Documented the program/data separation and the future installer obligation to
  preserve `.opensprite` by default.
- Added an architecture guard that prevents backend modules outside
  `app_paths.py` from owning the `.opensprite` root, calling `Path.home()`, or
  importing the removed path dependency.

## Public impact

Provider HTTP routes, request and response bodies, error semantics, credential
names, and OS credential storage are unchanged. This is an internal Python
composition change: the old default provider-state resolver and direct
state-file override no longer exist. No old metadata location is scanned or
migrated under the new-install-only policy.

## Verification

- Focused path/provider/runtime suite: 57 passed.
- Full backend suite with warnings as errors: 212 passed.
- Python `compileall`: passed.
- `uv lock --check --offline`: resolved 33 packages.
- `uv pip check`: 28 packages compatible.
- Frontend Vitest: 3 files, 34 tests passed.
- Frontend TypeScript check: passed.
- Frontend production build: passed; the existing 541.62 kB chunk advisory
  remains non-blocking.
- `git diff --check`: passed before final review.

All automated verification used temporary paths, fake credential stores, and
mock provider transports. It did not read or write an operating-system
credential, contact a provider, or create the real user data root.

## Remaining work

`settings.json`, `opensprite.db`, conversation uploads/outputs/memory, logs,
cache, and installer scripts remain unimplemented. Their documented paths are
ownership reservations only and no empty directory is created for them.
