# 0044 Frontend architecture guard

## Objective

Make the intended frontend dependency direction executable so feature boundaries cannot silently couple again.

## Changes

- Added a Vitest architecture check that scans every frontend TypeScript source static import and re-export declaration.
- Defined allowed dependency directions for `app`, `chat`, `settings`, `ai-settings`, `api` and `i18n`.
- Prevented Chat and Settings from importing each other while allowing both to consume the explicit AI-settings boundary.
- Prevented API and localization code from depending back on UI features.

## Public impact

None. This is a repository verification rule and does not alter runtime behavior or public contracts.

## Verification

- `npm test -- --run`: includes the new architecture test.
- `npm run typecheck`: validates the test and source types.

## Remaining work

- The guard intentionally covers current product boundaries rather than imposing speculative shared layers.
