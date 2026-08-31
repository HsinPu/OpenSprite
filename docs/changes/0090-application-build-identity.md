# 0090 — Application build identity

## Objective

Make the running OpenSprite version and exact installed build visible and
machine-verifiable without maintaining separate frontend and backend versions.

## Changes

- Defined the backend package version as the only product-version source.
- Added strict, side-effect-free build metadata loading and `GET /api/app-info`.
- Enabled the Settings About page with version, revision, environment, dirty
  state and installation time in all supported locales.
- Updated the Windows installer to create `build-info.json`, verify its version
  against the installed Python package and return version/build fields.
- Kept `/healthz` liveness-only and kept build metadata outside `.opensprite`.

## Public impact

The new read-only App Info contract exposes no user data, credentials, paths or
Git remote. Development runs report revision `development`; installed builds
report a short source revision or `unknown` when Git is unavailable.

## Verification

The backend suite passed 471 tests with 2 platform skips. The frontend suite
passed 178 tests, TypeScript and the production build passed, and the Windows
installer isolation test verified build metadata against the installed package.
Compileall, offline lock and dependency checks also passed. Final local-install,
browser, diff and SymbolLattice evidence is recorded in the task handoff.
