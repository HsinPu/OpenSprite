# Release 0.21.11

## Scope

- Synchronize backend package metadata, lockfile, and README to 0.21.11.
- Commit the accumulated approved settings UI slices documented in changes 0249 through 0262: user menu, execution record layout, full-page settings, compact workspace management, provider/model settings, General, Tools, and Skills settings.
- Skills now provides name search, status filters, compact read-only inheritance rows, explicit full-scope batch semantics, and stale-write protection after refresh failure.
- No dependency or backend behavior changes in this release.

## Verification

- Latest implementation verification: 459 frontend tests passed, typecheck and production build passed (change 0262).
- Release metadata: `uv lock --check --offline` and `git diff --check` passed.
- Desktop Skills preview verified; exact mobile viewport and 200% zoom remain unverified.
- Commit requested. No push or local installation requested for this release.
